# track.hell — Deploy Guide

## What you need (all free)
- GitHub account
- Vercel account (sign up at vercel.com with GitHub)
- Groq API key (console.groq.com → sign up → API Keys → Create)

---

## Step 1 — Push to GitHub

```bash
cd track-hell
git init
git add .
git commit -m "init"
# create a new repo on github.com called track-hell, then:
git remote add origin https://github.com/YOUR_USERNAME/track-hell.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Deploy on Vercel

1. Go to vercel.com → **Add New Project**
2. Import your `track-hell` GitHub repo
3. Framework preset: **Other** (leave as is)
4. Click **Deploy** — first deploy will fail, that's fine (no env vars yet)

---

## Step 3 — Add Vercel Postgres

1. In your Vercel project → **Storage** tab → **Create Database**
2. Choose **Postgres** → name it `track-hell-db` → Create
3. It will auto-add `POSTGRES_URL` to your environment variables ✓

---

## Step 4 — Add Groq API Key

1. Vercel project → **Settings** → **Environment Variables**
2. Add:
   - Name: `GROQ_API_KEY`
   - Value: your key from console.groq.com
3. Save

---

## Step 5 — Redeploy

1. Vercel project → **Deployments** → click the latest → **Redeploy**
2. Wait ~30 seconds
3. Open `track-hell.vercel.app` ✓

---

## Step 6 — Custom domain (optional)

1. Vercel → **Settings** → **Domains**
2. Add `track-hell.vercel.app` is already your domain
3. If you own `track.hell` or similar, add it here

---

## Making edits in the future

```bash
# edit any file locally
# then:
git add .
git commit -m "your change description"
git push
# Vercel auto-redeploys in ~30 seconds
```

### Common edits:
| What | Where |
|------|-------|
| Protein target (g/day) | `index.html` → `const proteinTarget = 120` |
| LLM model | `api/_shared.py` → `model="llama3-70b-8192"` |
| Add a new tracking field | `_shared.py` → `PARSE_SYSTEM` prompt |
| Add a new insight | `_shared.py` → `INSIGHT_SYSTEM` prompt + card in `index.html` |
| Change colors | `index.html` → `:root { }` CSS variables at top |

---

## File structure

```
track-hell/
├── api/
│   ├── _shared.py      ← Groq LLM + Postgres utils + prompts
│   ├── submit_log.py   ← POST /api/submit_log
│   ├── goals.py        ← GET/POST/DELETE /api/goals
│   └── history.py      ← GET /api/history + /api/stats
├── index.html          ← Full UI
├── vercel.json         ← Routing config
├── requirements.txt    ← Python deps
└── README.md
```
