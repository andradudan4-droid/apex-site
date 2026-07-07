# Apex Home Transformations — website

Bespoke Flask site for Claud (Apex Home Transformations, Woking): painter &
decorator, with a friendly AI quote bot (Groq), photo upload, and email lead
notifications (Resend). Same setup as the other sites.

## Everything you edit is at the top of `app.py`
`BUSINESS` (name, phone, email, area), `SERVICES`, `GALLERY`, `REVIEWS`.

## The photos
The gallery loads Claud's own photos straight from his **MyJobQuote** profile
(the `GALLERY` list of image URLs). That works immediately, but it depends on
MyJobQuote keeping them online. For a fully self-owned site, get Claud to send
his original photos, drop them in a `static/images/` folder, and swap the
`GALLERY` list to point at the local files. (Send them over and I'll do it.)

## Keys you'll need (free tiers)
- **Groq** – the chat bot – https://console.groq.com → API Keys
- **Resend** – lead emails – https://resend.com → API Keys
- **GitHub** + **Render** – code + hosting

## Deploy (same as before)

**1. GitHub** — new empty repo, then in this folder:
```
git init
git add .
git commit -m "Apex website"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/apex-site.git
git push -u origin main
```

**2. Render** — New → Web Service → connect the repo →
Build: `pip install -r requirements.txt`, Start: `gunicorn app:app`, Free tier.

**3. Environment variables** (Render → Environment):
| Key | Value |
|---|---|
| `GROQ_API_KEY` | your Groq key |
| `SECRET_KEY` | long random string (`python -c "import secrets;print(secrets.token_hex(32))"`) |
| `RESEND_API_KEY` | your Resend key |
| `NOTIFY_TO` | the email that should receive leads |
| `MAIL_FROM` | leave as `Apex Website <onboarding@resend.dev>` to start |

**4. Future edits:** `git add . && git commit -m "..." && git push` → Render redeploys.

## Notes
- **Email:** currently set to `gfnclaud@gmail.com`. Swap `email_public` (and
  `NOTIFY_TO`) to `info@apexhome.co.uk` once that inbox is live.
- **Brand:** black + orange, from his business card. Logo is a built-in SVG
  rooftop mark — if Claud has a proper logo file, send it and I'll drop it in.
- No fabricated reviews were added — only his two genuine MyJobQuote reviews.
  Two more *real* ones from past customers would strengthen it a lot.
