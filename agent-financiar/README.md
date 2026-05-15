# 💰 Agent Financiar — fabricacucadouri.ro

Sistem automat care citeste zilnic Gmail-ul si centralizeaza:
- 📦 Facturi furnizori (JLI Print, Homemade, etc.) → actualizeaza stocul
- 🚚 Borderouri DPD → inregistreaza rambursurile
- 💳 Rapoarte Netopia → inregistreaza incasarile card
- 🧾 Orice alta factura de cheltuiala

---

## 🚀 Publicare pe Railway (gratuit / ~20-40 RON/luna)

### Pas 1 — Cont Railway
1. Mergi la **railway.app**
2. Click **"Start a New Project"**
3. Loghează-te cu GitHub (creează cont GitHub dacă nu ai)

### Pas 2 — Urca fisierele
1. Pe Railway click **"Deploy from GitHub repo"** sau **"Empty Project"**
2. Alege **"Deploy from local directory"**
3. Sau foloseste Railway CLI:
```
npm install -g @railway/cli
railway login
railway init
railway up
```

### Pas 3 — Variabile de mediu (optional)
Toate datele sunt deja configurate in cod. Nu ai nevoie de variabile extra.

### Pas 4 — Domeniu
Railway iti da automat un link de forma:
`https://agent-financiar-production.up.railway.app`

Il salvezi in telefon ca bookmark si il deschizi oricand!

---

## 📱 Cum folosesti

**Dashboard-ul arata:**
- Total incasat luna aceasta (DPD + Netopia)
- Total cheltuit (facturi furnizori)  
- Profit estimat
- Toate documentele procesate
- Stocul de materiale actualizat

**Butonul "Ruleaza acum"** — cauta manual facturi noi in Gmail

**Automat** — agentul ruleaza singur o data pe zi

---

## 📧 Ce documente recunoaste

| Document | Ce face |
|----------|---------|
| Factura JLI Print | Cheltuiala + actualizeaza stoc hartie/canvas |
| Factura Homemade | Cheltuiala + actualizeaza stoc sasiu/rame |
| Borderou DPD | Inregistreaza rambursurile primite |
| Raport Netopia | Inregistreaza incasarile cu cardul |
| Orice alta factura PDF | Inregistreaza ca cheltuiala |

---

## 🔧 Date configurate
- ✅ Gmail: fabricacucadouri@gmail.com
- ✅ Gmail App Password: configurata
- ✅ Anthropic API: configurata
- ✅ Oblio API: configurata
- ✅ MerchantPro API: configurata
