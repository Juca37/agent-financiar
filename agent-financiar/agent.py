#!/usr/bin/env python3
"""
Agent Financiar - fabricacucadouri.ro
Citeste zilnic Gmail-ul, proceseaza facturile PDF cu AI
si actualizeaza dashboard-ul financiar.
"""

import os, json, base64, imaplib, email, sqlite3, re
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
import requests

# ============================================================
# CONFIGURARE
# ============================================================
CONFIG = {
    "gmail_user":         "fabricacucadouri@gmail.com",
    "gmail_password":     "vddw fedb nygk ytid",
    "anthropic_api_key":  "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",
    "oblio_api_key":      "adab3f3a82acfd9965da74cb27ebc927c5b4ed8b",
    "mp_user":            "882da5e6de986f8c4277c314bcb5f333",
    "mp_password":        "i33iEJPB42fNAuXJHDnWPpDCY",
    "zile_cautare":       7,
    "db_path":            "financiar.db",
}

MATERIALE = [
    "Sasiu canvas 14 cm","Sasiu canvas 20 cm","Sasiu canvas 23 cm","Sasiu canvas 25 cm",
    "Sasiu canvas 30 cm","Sasiu canvas 35 cm","Sasiu canvas 40 cm","Sasiu canvas 50 cm",
    "Sasiu canvas 60 cm","Sasiu canvas 70 cm","Sasiu canvas 80 cm","Sasiu canvas 100 cm",
    "Rama foto A3","Rama foto A4","Rama foto 13x18","Rama foto 10x15",
    "Hartie fotografica 180 gm A3 lucios","Hartie fotografica 135 gm A4 lucios",
    "Hartie fotografica 230 gm A4 mat","Hartie fotografica 180 gm A4 lucios",
    "Hartie fotografica 230 gm 13x18 mat","Hartie fotografica 230 gm 13x18 lucios",
    "Hartie 160 gm color copy","Hartie 200 gm color copy","Carton carti de vizita 220 gm A4",
    "Hartie stickere A3 lucios","Hartie calc",
    "Hartie canvas A3 mat","Hartie canvas A3 lucios","Hartie canvas A4 mat","Hartie canvas A4 lucios",
    "Carton albastru regal 160 gm","Carton verde padure 120 gm","Carton negru","Carton rosu",
    "Carton roz","Carton roz deschis","Carton verde menta","Carton bordeaux","Carton bej",
]

# ============================================================
# DATABASE
# ============================================================
def init_db():
    con = sqlite3.connect(CONFIG["db_path"])
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS documente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tip TEXT,
        furnizor TEXT,
        numar TEXT,
        data_doc TEXT,
        total REAL,
        moneda TEXT DEFAULT 'RON',
        procesat_la TEXT,
        email_subiect TEXT,
        raw_json TEXT
    );
    CREATE TABLE IF NOT EXISTS linii (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        nume TEXT,
        cantitate REAL,
        unitate TEXT,
        pret_unitar REAL,
        total REAL,
        FOREIGN KEY(document_id) REFERENCES documente(id)
    );
    CREATE TABLE IF NOT EXISTS stoc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material TEXT UNIQUE,
        cantitate REAL DEFAULT 0,
        unitate TEXT DEFAULT 'buc',
        actualizat TEXT
    );
    CREATE TABLE IF NOT EXISTS emailuri_procesate (
        message_id TEXT PRIMARY KEY,
        procesat_la TEXT
    );
    """)
    # Initializeaza stocurile daca nu exista
    for m in MATERIALE:
        cur.execute("INSERT OR IGNORE INTO stoc(material,cantitate,actualizat) VALUES(?,0,?)",
                    (m, datetime.now().isoformat()))
    con.commit()
    con.close()

def get_db():
    return sqlite3.connect(CONFIG["db_path"])

# ============================================================
# LOGGING
# ============================================================
def log(msg, nivel="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{nivel}] {msg}")
    with open("agent.log","a",encoding="utf-8") as f:
        f.write(f"[{ts}] [{nivel}] {msg}\n")

# ============================================================
# GMAIL
# ============================================================
def get_gmail_pdfs():
    """Conectare Gmail si extragere PDF-uri noi."""
    pdfs = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(CONFIG["gmail_user"], CONFIG["gmail_password"])
        mail.select("INBOX")

        since = (datetime.now()-timedelta(days=CONFIG["zile_cautare"])).strftime("%d-%b-%Y")
        _, msgs = mail.search(None, f'SINCE {since}')

        con = get_db()
        cur = con.cursor()

        for num in msgs[0].split():
            _, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            msg_id = msg.get("Message-ID","") or str(num)

            # Skip deja procesate
            cur.execute("SELECT 1 FROM emailuri_procesate WHERE message_id=?", (msg_id,))
            if cur.fetchone():
                continue

            subiect = msg.get("Subject","")
            expeditor = msg.get("From","")

            for parte in msg.walk():
                ct = parte.get_content_type()
                if ct == "application/pdf" or (ct=="application/octet-stream" and
                   (parte.get_filename() or "").lower().endswith(".pdf")):
                    continut = parte.get_payload(decode=True)
                    if continut:
                        pdfs.append({
                            "message_id": msg_id,
                            "subiect": subiect,
                            "expeditor": expeditor,
                            "fisier": parte.get_filename() or "document.pdf",
                            "continut": continut,
                            "data_email": msg.get("Date","")
                        })
                        log(f"PDF nou: {parte.get_filename()} de la {expeditor}")

        con.close()
        mail.logout()
    except Exception as e:
        log(f"Eroare Gmail: {e}", "ERROR")
    return pdfs

# ============================================================
# AI PROCESARE FACTURA
# ============================================================
def proceseaza_pdf_cu_ai(pdf_info):
    """Foloseste Claude AI sa extraga datele din PDF."""
    try:
        client = anthropic.Anthropic(api_key=CONFIG["anthropic_api_key"])
        pdf_b64 = base64.standard_b64encode(pdf_info["continut"]).decode()

        lista_materiale = "\n".join(f"- {m}" for m in MATERIALE)

        prompt = f"""Analizeaza acest document PDF si extrage informatiile financiare.

Lista materialelor pe care le folosim (pentru matching stoc):
{lista_materiale}

Returneaza DOAR un JSON valid, fara explicatii, in acest format exact:
{{
  "tip": "factura_furnizor|borderou_dpd|raport_netopia|factura_curier|altele",
  "furnizor": "Numele firmei/furnizorului",
  "numar": "Numarul documentului",
  "data": "YYYY-MM-DD",
  "total": 123.45,
  "moneda": "RON",
  "linii": [
    {{
      "nume": "Numele produsului/serviciului",
      "cantitate": 10,
      "unitate": "buc|coli|kg|etc",
      "pret_unitar": 5.50,
      "total": 55.00,
      "material_stoc": "Numele exact din lista de mai sus sau null daca nu se potriveste"
    }}
  ],
  "observatii": "orice info relevant"
}}

Tipuri de documente:
- factura_furnizor: factura de la un furnizor de materiale (JLI Print, Homemade, etc.)
- borderou_dpd: borderou rambursuri de la DPD sau alt curier
- raport_netopia: raport incasari card de la Netopia
- factura_curier: factura de transport/curierat
- altele: orice alt document

Returneaza DOAR JSON-ul, absolut nimic altceva."""

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type":"document","source":{"type":"base64","media_type":"application/pdf","data":pdf_b64}},
                    {"type":"text","text":prompt}
                ]
            }]
        )

        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        log(f"Eroare JSON: {e}", "ERROR")
        return None
    except Exception as e:
        log(f"Eroare AI: {e}", "ERROR")
        return None

# ============================================================
# SALVEAZA IN DB
# ============================================================
def salveaza_document(pdf_info, date_ai):
    """Salveaza documentul procesat in baza de date."""
    try:
        con = get_db()
        cur = con.cursor()

        # Salveaza documentul
        cur.execute("""
            INSERT INTO documente(tip,furnizor,numar,data_doc,total,moneda,procesat_la,email_subiect,raw_json)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            date_ai.get("tip","altele"),
            date_ai.get("furnizor",""),
            date_ai.get("numar",""),
            date_ai.get("data",""),
            date_ai.get("total",0),
            date_ai.get("moneda","RON"),
            datetime.now().isoformat(),
            pdf_info.get("subiect",""),
            json.dumps(date_ai, ensure_ascii=False)
        ))
        doc_id = cur.lastrowid

        # Salveaza liniile si actualizeaza stocul
        for linie in date_ai.get("linii", []):
            cur.execute("""
                INSERT INTO linii(document_id,nume,cantitate,unitate,pret_unitar,total)
                VALUES(?,?,?,?,?,?)
            """, (
                doc_id,
                linie.get("nume",""),
                linie.get("cantitate",0),
                linie.get("unitate","buc"),
                linie.get("pret_unitar",0),
                linie.get("total",0)
            ))

            # Actualizeaza stocul daca e material cunoscut
            material_stoc = linie.get("material_stoc")
            if material_stoc and date_ai.get("tip") == "factura_furnizor":
                cantitate = linie.get("cantitate", 0)
                cur.execute("""
                    UPDATE stoc SET cantitate = cantitate + ?, actualizat = ?
                    WHERE material = ?
                """, (cantitate, datetime.now().isoformat(), material_stoc))
                if cur.rowcount > 0:
                    log(f"  Stoc actualizat: {material_stoc} +{cantitate}")

        # Marcheaza emailul ca procesat
        cur.execute("INSERT OR IGNORE INTO emailuri_procesate VALUES(?,?)",
                    (pdf_info["message_id"], datetime.now().isoformat()))

        con.commit()
        con.close()
        log(f"Document salvat: {date_ai.get('tip')} / {date_ai.get('furnizor')} / {date_ai.get('total')} RON")
        return doc_id

    except Exception as e:
        log(f"Eroare salvare DB: {e}", "ERROR")
        return None

# ============================================================
# GENEREAZA DATE PENTRU DASHBOARD
# ============================================================
def get_stats_json():
    """Returneaza statistici pentru dashboard."""
    con = get_db()
    cur = con.cursor()

    luna_curenta = datetime.now().strftime("%Y-%m")

    # Total cheltuieli luna curenta (facturi furnizori + curierat)
    cur.execute("""
        SELECT COALESCE(SUM(total),0) FROM documente
        WHERE tip IN ('factura_furnizor','factura_curier','altele')
        AND data_doc LIKE ?
    """, (f"{luna_curenta}%",))
    cheltuieli_luna = cur.fetchone()[0]

    # Total incasari DPD luna curenta
    cur.execute("""
        SELECT COALESCE(SUM(total),0) FROM documente
        WHERE tip = 'borderou_dpd' AND data_doc LIKE ?
    """, (f"{luna_curenta}%",))
    incasari_dpd = cur.fetchone()[0]

    # Total incasari Netopia luna curenta
    cur.execute("""
        SELECT COALESCE(SUM(total),0) FROM documente
        WHERE tip = 'raport_netopia' AND data_doc LIKE ?
    """, (f"{luna_curenta}%",))
    incasari_netopia = cur.fetchone()[0]

    # Toate documentele
    cur.execute("""
        SELECT id, tip, furnizor, numar, data_doc, total, moneda, procesat_la
        FROM documente ORDER BY procesat_la DESC LIMIT 50
    """)
    docs = [{"id":r[0],"tip":r[1],"furnizor":r[2],"numar":r[3],
              "data":r[4],"total":r[5],"moneda":r[6],"procesat_la":r[7]}
            for r in cur.fetchall()]

    # Stocuri
    cur.execute("SELECT material, cantitate, unitate, actualizat FROM stoc ORDER BY material")
    stocuri = [{"material":r[0],"cantitate":r[1],"unitate":r[2],"actualizat":r[3]}
               for r in cur.fetchall()]

    # Cheltuieli pe luna (ultimele 6 luni)
    cur.execute("""
        SELECT strftime('%Y-%m', data_doc) as luna, SUM(total)
        FROM documente WHERE tip IN ('factura_furnizor','factura_curier')
        AND data_doc != ''
        GROUP BY luna ORDER BY luna DESC LIMIT 6
    """)
    cheltuieli_history = [{"luna":r[0],"total":r[1]} for r in cur.fetchall()]

    con.close()

    total_incasat = incasari_dpd + incasari_netopia
    profit_estimat = total_incasat - cheltuieli_luna

    return {
        "luna_curenta": luna_curenta,
        "cheltuieli_luna": round(cheltuieli_luna, 2),
        "incasari_dpd": round(incasari_dpd, 2),
        "incasari_netopia": round(incasari_netopia, 2),
        "total_incasat": round(total_incasat, 2),
        "profit_estimat": round(profit_estimat, 2),
        "documente": docs,
        "stocuri": stocuri,
        "cheltuieli_history": cheltuieli_history,
        "ultima_rulare": datetime.now().isoformat()
    }

# ============================================================
# MAIN
# ============================================================
def ruleaza():
    log("=" * 50)
    log("Agent Financiar pornit!")
    init_db()

    pdfs = get_gmail_pdfs()
    log(f"PDF-uri noi gasite: {len(pdfs)}")

    procesate = 0
    for pdf in pdfs:
        log(f"Procesez: {pdf['fisier']} ({pdf['expeditor']})")
        date = proceseaza_pdf_cu_ai(pdf)
        if date:
            salveaza_document(pdf, date)
            procesate += 1
        else:
            log(f"Nu s-au putut extrage date din: {pdf['fisier']}", "WARN")

    # Salveaza stats pentru dashboard
    stats = get_stats_json()
    with open("stats.json","w",encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log(f"Gata! {procesate}/{len(pdfs)} documente procesate.")
    return stats

if __name__ == "__main__":
    ruleaza()
