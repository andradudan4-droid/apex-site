from flask import Flask, request, jsonify, render_template_string, session, Response
import os
import re
import uuid
import html
import base64
import time
import requests
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

_groq_client = None


def client_chat(**kwargs):
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _groq_client.chat.completions.create(**kwargs)


# ---------------------------------------------------------------------------
# BUSINESS DETAILS  --  edit in one place
# ---------------------------------------------------------------------------
BUSINESS = {
    "name": "Apex Home Transformations",
    "short": "Apex",
    "tagline": "Elevating homes, transforming lives.",
    "owner": "Claud",                 # owner Claudiu ("Claud")
    "phone_display": "07512 918722",
    "phone_e164": "447512918722",
    "email_public": "gfnclaud@gmail.com",   # <-- swap to info@apexhome.co.uk once that inbox is live
    "area_line": "Woking, Chobham, Brookwood & across Surrey",
    "postcode": "GU22 7LJ",
    "instagram": "",                  # add when he has one
    "facebook": "",
}

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
NOTIFY_TO = os.environ.get("NOTIFY_TO", "gfnclaud@gmail.com")
MAIL_FROM = os.environ.get("MAIL_FROM", "Apex Website <onboarding@resend.dev>")

MAX_IMAGES_PER_SESSION = 6
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024


# ---------------------------------------------------------------------------
# SERVICES
# ---------------------------------------------------------------------------
def _icon(path):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
            + path + '</svg>')

SERVICES = [
    {"title": "Interior Painting & Decorating",
     "desc": "Walls, ceilings, woodwork and whole rooms — prepped properly and finished clean and sharp.",
     "icon": _icon('<path d="M3 7h14a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h-7"/><path d="M10 13v4a2 2 0 0 1-2 2H7"/><rect x="3" y="4" width="4" height="6" rx="1"/>')},
    {"title": "Exterior Painting",
     "desc": "Render, masonry, soffits and fascias — weatherproof finishes that lift your whole home.",
     "icon": _icon('<path d="M3 21V10l9-7 9 7v11z"/><path d="M9 21v-6h6v6"/>')},
    {"title": "Windows, Doors & Woodwork",
     "desc": "Frames, doors, skirting and trim brought back to life with a smooth, hard-wearing finish.",
     "icon": _icon('<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M12 3v18M4 12h16"/>')},
    {"title": "Feature Walls & Murals",
     "desc": "Statement colours, wallpaper and paint effects to give a room real character.",
     "icon": _icon('<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 15l5-5 4 4 3-3 6 6"/><circle cx="8.5" cy="8.5" r="1.5"/>')},
    {"title": "Fence Painting & Staining",
     "desc": "Sprayed and brushed fence treatments — panels, gravel boards and posts, tidy every time.",
     "icon": _icon('<path d="M4 21V8l3-3 3 3v13"/><path d="M14 21V8l3-3 3 3v13"/><path d="M2 12h20"/>')},
    {"title": "Handyman & Odd Jobs",
     "desc": "Repairs, flat-pack, fixings and the little jobs that keep your home ticking over.",
     "icon": _icon('<path d="M14 7l3 3-7 7-3-3z"/><path d="M17 10l3-3a3 3 0 0 0-4-4l-3 3"/><path d="M7 14l-4 4 3 3 4-4"/>')},
]

# ---------------------------------------------------------------------------
# WORK  --  Claud's own photos, self-hosted from static/images/
# ---------------------------------------------------------------------------
# Before / after transformations. Each project has a before + one or more afters.
PROJECTS = [
    {"title": "Garden fence \u2014 sprayed & restained",
     "blurb": "Tired bare-timber panels taken to a rich anthracite grey \u2014 posts and gravel boards masked off, even coats, tidied up throughout.",
     "shots": [
        {"src": "/static/images/fence-before.jpg",  "label": "Before"},
        {"src": "/static/images/fence-after-1.jpg", "label": "After"},
        {"src": "/static/images/fence-after-2.jpg", "label": "After"},
     ]},
    {"title": "Living room \u2014 full redecoration",
     "blurb": "Patched, bare plaster prepped properly and lifted into a warm terracotta scheme with a crisp white ceiling and coving.",
     "shots": [
        {"src": "/static/images/room-before.webp",  "label": "Before"},
        {"src": "/static/images/room-after-1.webp", "label": "After"},
        {"src": "/static/images/room-after-2.webp", "label": "After"},
     ]},
    {"title": "Front door & porch \u2014 restored",
     "blurb": "Weathered, flaking blue brought back to a deep gloss black \u2014 sharp lines cut in around the porthole and frame.",
     "shots": [
        {"src": "/static/images/door1-before.jpg", "label": "Before"},
        {"src": "/static/images/door1-after.jpg", "label": "After"},
     ]},
    {"title": "Front entrance \u2014 repaint",
     "blurb": "Faded planked door and surround refinished in hard-wearing black for a smart, modern entrance.",
     "shots": [
        {"src": "/static/images/door2-before.jpg", "label": "Before"},
        {"src": "/static/images/door2-after.jpg", "label": "After"},
     ]},
    {"title": "Panelled feature wall \u2014 decorated",
     "blurb": "Dated lilac and pink panelling repainted in a soft, contemporary greige \u2014 mouldings cut in clean and even.",
     "shots": [
        {"src": "/static/images/panels-before-1.webp", "label": "Before"},
        {"src": "/static/images/panels-before-2.webp", "label": "Before"},
        {"src": "/static/images/panels-after.webp",    "label": "After"},
     ]},
]

# Recent finished work (general masonry gallery)
GALLERY = [
    "/static/images/work-lounge-blue.webp",
    "/static/images/work-kitchen-green.webp",
    "/static/images/work-bedroom-grey.webp",
    "/static/images/work-hallway.webp",
    "/static/images/work-kitchen-black-1.webp",
    "/static/images/work-kitchen-black-2.webp",
]

# ---------------------------------------------------------------------------
# COVERAGE  --  Woking + ~15-mile radius (drives the map section & the bot)
# ---------------------------------------------------------------------------
COVERAGE = {
    "hub": "Woking",
    "radius_miles": 15,
    "towns": [
        "Guildford", "Horsell", "Knaphill", "Brookwood", "West Byfleet",
        "Byfleet", "Pyrford", "Send", "Ripley", "Old Woking", "Mayford",
        "Worplesdon", "Chobham", "Bisley", "Bagshot", "Lightwater",
        "Windlesham", "Addlestone", "Ottershaw", "Chertsey", "Weybridge",
        "Cobham", "Camberley", "Frimley", "Leatherhead", "Egham",
        "Sunningdale", "Ascot", "Godalming",
    ],
}

# ---------------------------------------------------------------------------
# REVIEWS  --  the two genuine reviews from Claud's MyJobQuote profile.
# ---------------------------------------------------------------------------
REVIEWS = [
    {"text": "Job completed in a timely manner, happy with the work completed. A tidy painter and decorator.",
     "name": "Lorraine", "where": "Office walls, 3–4 rooms · MyJobQuote"},
    {"text": "Taped up the gravel boards and concrete posts, three coats on the new panels and touched up the edges and tops by brush. Very efficient, completed over three visits and cleaned up after themselves. Would use again. A+",
     "name": "Matt", "where": "Painted & stained 15 fence panels · MyJobQuote"},
]

# ===========================================================================
# LEAD CAPTURE
# ===========================================================================
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+44|0)\d[\d\s\-\.]{8,11}(?!\d)")
POSTCODE_RE = re.compile(r"\b[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}\b")


def _customer_text(conv):
    return " ".join(m["content"] for m in conv if m.get("role") == "user")


def find_email(conv):
    m = EMAIL_RE.search(_customer_text(conv))
    return m.group(0) if m else None


def find_phone(conv):
    for cand in PHONE_RE.findall(_customer_text(conv)):
        digits = re.sub(r"\D", "", cand)
        if digits.startswith("00"):
            continue
        if digits.startswith("44"):
            digits = "0" + digits[2:]
        if len(digits) == 11 and digits.startswith("0"):
            return f"{digits[:5]} {digits[5:]}"
    return None


def find_postcode(conv):
    m = POSTCODE_RE.search(_customer_text(conv))
    if not m:
        return None
    raw = re.sub(r"\s+", "", m.group(0)).upper()
    return raw[:-3] + " " + raw[-3:]


def has_contact_info(conv):
    return bool(find_email(conv) or find_phone(conv))


CLOSING_RE = re.compile(
    r"\b(no longer interested|not interested|no thanks|no thank you|"
    r"that'?s all|that'?s it|that'?s everything|nothing else|all good|"
    r"that'?s great thank|thanks that'?s|goodbye|bye for now|no more|"
    r"i'?m good|im good)\b", re.I)


def _looks_like_closing(text):
    return bool(CLOSING_RE.search(text or ""))


def _transcript(conv):
    out = []
    for m in conv:
        if m["role"] == "user":
            out.append(f"Customer: {m['content']}")
        elif m["role"] == "assistant":
            out.append(f"Apex Assistant: {m['content']}")
    return "\n\n".join(out)


LEAD_SUMMARY_PROMPT = """You are turning a website chat into a clean lead for a
painting & decorating company. Read the conversation and output EXACTLY these
labelled lines and nothing else. Fill each in from what the customer actually
said; write "Not specified" if they didn't. Keep each line short.

Name:
Job / work wanted:
Property type (domestic or commercial):
Rooms / areas:
Approx budget (in GBP £; note if total or a rate):
Preferred timing:
Urgency (1-5 where 1=no rush, 5=urgent - infer from what they said):
Location / area:
Other notes:"""


def summarise_lead(conv):
    try:
        resp = client_chat(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": LEAD_SUMMARY_PROMPT},
                      {"role": "user", "content": _transcript(conv)}],
            max_tokens=250, temperature=0.2)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"Lead summary failed: {e}")
        return None


def _post_resend(subject, text, html_body=None, attachments=None):
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set, skipping email")
        return
    payload = {"from": MAIL_FROM, "to": [NOTIFY_TO], "subject": subject, "text": text}
    if html_body:
        payload["html"] = html_body
    if attachments:
        payload["attachments"] = [{"filename": a["filename"], "content": a["b64"]} for a in attachments]
    try:
        r = requests.post("https://api.resend.com/emails",
                          headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                          json=payload, timeout=15)
        if r.status_code >= 300:
            print(f"Resend error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Failed to send email: {e}")


def _parse_summary(structured):
    out = {}
    if not structured:
        return out
    for line in structured.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def _lead_fields(conv):
    s = _parse_summary(summarise_lead(conv))

    def pick(*keys):
        for k in keys:
            v = s.get(k)
            if v and v.lower() not in ("not specified", "not provided", "n/a", "none", "-"):
                return v
        return None

    return {
        "Name": pick("name"),
        "Phone": find_phone(conv),
        "Email": find_email(conv),
        "Postcode": find_postcode(conv),
        "Area": pick("location / area", "location", "area"),
        "Job": pick("job / work wanted", "job", "work wanted"),
        "Property": pick("property type (domestic or commercial)", "property type", "property"),
        "Rooms": pick("rooms / areas", "rooms"),
        "Budget": pick("approx budget", "budget"),
        "Preferred timing": pick("preferred timing", "timing"),
        "Urgency": pick("urgency (1-5 where 1=no rush, 5=urgent - infer from what they said)", "urgency"),
        "Notes": pick("other notes", "notes"),
    }


def _row(label, value):
    if not value:
        return ""
    return ('<tr>'
            f'<td style="padding:10px 16px;border-bottom:1px solid #eee;color:#8a8a8a;'
            f'font-size:13px;white-space:nowrap;vertical-align:top;width:130px">{html.escape(label)}</td>'
            f'<td style="padding:10px 16px;border-bottom:1px solid #eee;color:#1a1a1a;'
            f'font-size:14px;font-weight:600">{html.escape(str(value))}</td></tr>')


def _transcript_html(conv):
    rows = []
    for m in conv:
        if m["role"] == "user":
            who, color, bg = "Customer", "#0a0a0a", "#f5f4f0"
        elif m["role"] == "assistant":
            who, color, bg = "Apex Assistant", "#c2410c", "#ffffff"
        else:
            continue
        text = html.escape(m["content"]).replace("\n", "<br>")
        rows.append(f'<div style="margin:0 0 12px"><div style="font-size:11px;letter-spacing:.05em;'
                    f'text-transform:uppercase;color:{color};font-weight:700;margin-bottom:4px">{who}</div>'
                    f'<div style="background:{bg};border:1px solid #ececec;border-radius:10px;padding:11px 14px;'
                    f'font-size:14px;color:#2a2a2a;line-height:1.5">{text}</div></div>')
    return "".join(rows)


def _urgency_badge(u):
    if not u:
        return ""
    m = re.search(r"[1-5]", str(u))
    if not m:
        return ""
    score = int(m.group(0))
    colours = {1: ("#e8f5e9", "#2e7d32", "1 — No rush"), 2: ("#f1f8e9", "#558b2f", "2 — Low"),
               3: ("#fff8e1", "#f57f17", "3 — Moderate"), 4: ("#fff3e0", "#e65100", "4 — Fairly urgent"),
               5: ("#ffebee", "#b71c1c", "5 — URGENT — reply ASAP")}
    bg, fg, label = colours.get(score, ("#f5f5f5", "#555", str(score)))
    return (f'<div style="margin:0 0 20px"><div style="font-size:11px;letter-spacing:.08em;'
            f'text-transform:uppercase;color:#999;font-weight:700;margin-bottom:6px">Urgency</div>'
            f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {fg};'
            f'border-radius:999px;padding:5px 14px;font-size:13px;font-weight:700">{label}</span></div>')


def _lead_email_html(fields, conv, image_count):
    urgency_val = fields.pop("Urgency", None)
    rows = "".join(_row(k, v) for k, v in fields.items())
    photos_line = ""
    if image_count:
        photos_line = ('<p style="margin:0 0 20px;font-size:14px;color:#1a1a1a">'
                       f'\U0001F4CE <strong>{image_count} photo(s)</strong> attached to this email.</p>')
    return ('<!DOCTYPE html><html><body style="margin:0;background:#f0efea;padding:24px;'
            'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif">'
            '<div style="max-width:620px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;'
            'box-shadow:0 2px 12px rgba(0,0,0,.07)"><div style="background:#0d0c0b;padding:24px 28px">'
            '<div style="color:#f97316;font-size:12px;letter-spacing:.18em;text-transform:uppercase;'
            'font-weight:700">Apex Home Transformations</div>'
            '<div style="color:#fff;font-size:21px;font-weight:700;margin-top:5px">New enquiry from your website</div></div>'
            '<div style="padding:26px 28px"><p style="margin:0 0 20px;font-size:14px;color:#666">'
            'Here are the details captured by your website assistant:</p>'
            f'{_urgency_badge(urgency_val)}{photos_line}'
            '<table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-radius:8px;'
            f'overflow:hidden;margin-bottom:28px">{rows}</table>'
            '<div style="font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:#999;'
            'font-weight:700;margin-bottom:14px">Full conversation</div>'
            f'{_transcript_html(conv)}</div>'
            '<div style="background:#faf9f6;padding:16px 28px;border-top:1px solid #eee;font-size:12px;color:#aaa">'
            'Sent automatically by the Apex Home Transformations website assistant.</div>'
            '</div></body></html>')


def send_lead_email(conv, images=None):
    images = images or []
    fields = _lead_fields(conv)
    text_lines = ["NEW LEAD - Apex Home Transformations", "===================================="]
    for k, v in fields.items():
        if v:
            text_lines.append(f"{k}: {v}")
    if images:
        text_lines.append(f"Photos attached: {len(images)}")
    text_lines += ["====================================", "", "Full conversation:", "", _transcript(conv)]
    html_body = _lead_email_html(fields, conv, len(images))
    urgency_m = re.search(r"[1-5]", str(fields.get("Urgency", "")))
    score = int(urgency_m.group(0)) if urgency_m else 0
    prefix = "🔴 URGENT — " if score >= 5 else ("🟠 " if score >= 4 else "")
    contact = fields.get("Phone") or fields.get("Email") or "no number yet"
    bits = [b for b in (fields.get("Name"), fields.get("Area") or fields.get("Postcode")) if b]
    subject = prefix + "New lead - " + (" \u00b7 ".join(bits + [contact]) if bits else contact)
    _post_resend(subject, "\n".join(text_lines), html_body=html_body, attachments=images)


def send_photo_followup(conv, images):
    if not images:
        return
    phone = find_phone(conv) or "Not provided"
    email = find_email(conv) or "Not provided"
    postcode = find_postcode(conv) or "Not provided"
    text = (f"ADDITIONAL PHOTO(S) - Apex\nRelates to a lead you've already been emailed about.\n"
            f"Phone: {phone}\nEmail: {email}\nPostcode: {postcode}\nPhotos attached: {len(images)}\n")
    _post_resend(f"Photo added - lead: {phone}", text, attachments=images)


# ===========================================================================
# CHAT BOT
# ===========================================================================
SYSTEM_PROMPT = f"""
You are the friendly virtual assistant for {BUSINESS['name']}, a painting &
decorating and handyman business run by Claud (Claudiu) in Woking, covering
{BUSINESS['area_line']}. You're the first point of contact for new enquiries.

About the business:
- Painter & decorator, sole trader, established 2025, ID-checked. Domestic and
  commercial work. Free, no-obligation quotes.
- Services: interior painting & decorating, exterior painting (render, masonry,
  soffits, fascias), windows/doors/woodwork, feature walls & murals, fence
  painting & staining, and general handyman / odd jobs.
- Tidy, reliable, professional finish. Tagline: "Elevating homes, transforming lives."
- Coverage: based in Woking, covers roughly a {COVERAGE['radius_miles']}-mile radius — including {', '.join([COVERAGE['hub']] + COVERAGE['towns'])}. If someone is just outside that, say Claud will happily take a look rather than turning them away.

YOUR TONE — important:
Warm, friendly and down-to-earth, like a helpful local tradesperson sending a
quick message. Short and natural. No corporate filler ("Great question!",
"Certainly!"). One or two sentences per message. Ask ONE thing at a time and
wait. Never use bullet points or long paragraphs in chat.

Good example: "Happy to help! What are you looking to have done — a room or two,
the outside of the house, fences?"

CONVERSATION FLOW — one at a time, in order:
1. Find out what the job is (inside, outside, fences, etc.).
2. Get a bit more detail — how many rooms / walls / panels, rough size, colours.
3. Ask if it's a domestic or commercial property.
4. Offer photos via the paperclip — "Got a photo of the space? Pop it in with the
   paperclip, it really helps Claud quote. Or we can arrange a quick visit."
5. Ask for a rough budget — frame it as helpful for the quote; fine if they'd
   rather not say. Note whether it's a total or a rate, in pounds.
6. Ask how soon they'd like it done.
7. Get their name, postcode or area, and best contact number or email. Repeat
   the number/email back to check it's right.
8. Once you've been through everything, wrap up warmly and confirm the enquiry
   has been sent to Claud, who'll be in touch about a free quote — usually the
   same day.

WHEN TO FINISH: Only add the [[READY]] signal once you have ASKED about ALL of
these: the job, detail/scope, domestic/commercial, offered photos/visit, budget,
timing, name, postcode/area, and contact details (and confirmed them). It's fine
if they decline some, but you must have ASKED each. Do NOT add [[READY]] just
because they gave a number. [[READY]] is a hidden tag stripped automatically —
never show it. Put it on its own line at the very end of the final message only.
"""

all_conversations = {}
notified_sessions = set()
chat_activity = {}
session_images = {}


def _decode_image_data_url(data_url):
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        return None
    try:
        header, b64 = data_url.split(",", 1)
    except ValueError:
        return None
    if ";base64" not in header:
        return None
    content_type = header[len("data:"):].split(";", 1)[0].lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        return None
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:
        return None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        return None
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]
    return {"filename": f"job-photo-{uuid.uuid4().hex[:8]}.{ext}", "content_type": content_type,
            "b64": base64.b64encode(raw).decode("ascii")}


# ===========================================================================
# THE PAGE
# ===========================================================================
LOGO_SVG = ('<svg viewBox="0 0 52 34" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<path d="M3 30 L17 8 L31 30 Z" fill="var(--orange)"/>'
            '<path d="M22 30 L36 4 L50 30 Z" fill="var(--orange-soft)"/>'
            '<rect x="14" y="22" width="6" height="8" fill="#0d0c0b"/>'
            '<rect x="33" y="20" width="6" height="10" fill="#0d0c0b"/></svg>')

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ b.name }} | Painters & Decorators in Woking, Surrey</title>
<meta name="description" content="Apex Home Transformations — trusted painter & decorator in Woking covering {{ b.area_line }}. Interior & exterior painting, feature walls, fences and handyman work. Free quotes.">
<meta property="og:title" content="{{ b.name }} | Painters & Decorators in Woking">
<meta property="og:description" content="Interior & exterior painting, decorating, fences and handyman work across Surrey. Free quotes.">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --ink:#0d0c0b; --ink2:#17140f; --panel:#1e1913; --cream:#f5efe8; --mut:#a99f92;
  --orange:#f97316; --orange-soft:#ffb066; --line:rgba(249,115,22,.22); --rad:16px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--ink);color:var(--cream);font-family:'Inter',system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit;text-decoration:none}
img{max-width:100%;display:block}
.serif{font-family:'Fraunces',Georgia,serif}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
.eyebrow{font-size:12px;letter-spacing:.34em;text-transform:uppercase;color:var(--orange);font-weight:600}
h2.title{font-family:'Fraunces',serif;font-weight:600;font-size:clamp(28px,4.2vw,44px);line-height:1.08;margin:14px 0 10px}
.lede{color:var(--mut);max-width:620px;font-size:clamp(15px,1.8vw,17px)}
.reveal{opacity:0;transform:translateY(22px);transition:opacity .7s ease,transform .7s ease}
.reveal.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}}
.progress{position:fixed;top:0;left:0;height:3px;width:0;z-index:100;background:linear-gradient(90deg,var(--orange),var(--orange-soft));transition:width .1s linear}

nav{position:sticky;top:0;z-index:60;background:rgba(13,12,11,.8);backdrop-filter:blur(12px) saturate(140%);border-bottom:1px solid var(--line)}
nav .bar{display:flex;align-items:center;justify-content:space-between;height:70px}
.brand{display:flex;align-items:center;gap:12px;font-family:'Fraunces',serif;font-weight:600}
.brand svg{width:40px;height:28px}
.brand b{color:var(--cream);font-size:17px;letter-spacing:.02em;line-height:1}
.brand span{font-size:10.5px;color:var(--orange);letter-spacing:.2em;text-transform:uppercase;display:block;margin-top:3px}
.navlinks{display:flex;align-items:center;gap:30px}
.navlinks a{font-size:14px;color:#e9e2d3;opacity:.85}
.navlinks a:hover{color:var(--orange);opacity:1}
.navcta{border:1px solid var(--orange);color:var(--orange)!important;padding:9px 18px;border-radius:999px;opacity:1!important;font-weight:500;transition:.2s}
.navcta:hover{background:var(--orange);color:#fff!important}
.burger{display:none;background:none;border:0;color:var(--orange);cursor:pointer;padding:6px}
@media(max-width:860px){
  .navlinks{position:fixed;inset:70px 0 auto 0;flex-direction:column;gap:0;background:var(--ink2);border-bottom:1px solid var(--line);padding:8px 0;transform:translateY(-130%);transition:.35s;opacity:0}
  .navlinks.open{transform:none;opacity:1}
  .navlinks a{width:100%;padding:14px 24px}.navcta{margin:10px 24px;text-align:center}
  .burger{display:block}
}

.hero{position:relative;min-height:90vh;display:flex;align-items:center;isolation:isolate;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;z-index:-2;background-color:#0d0c0b;background:
  linear-gradient(90deg,rgba(13,12,11,.94),rgba(13,12,11,.74) 46%,rgba(13,12,11,.5)),
  linear-gradient(180deg,rgba(13,12,11,.18),rgba(13,12,11,.58)),
  radial-gradient(90% 70% at 78% 8%,rgba(249,115,22,.2),transparent 55%),
  url('/static/images/room-after-1.webp') center/cover no-repeat}
@media(max-width:860px){.hero::before{background:
  linear-gradient(180deg,rgba(13,12,11,.72),rgba(13,12,11,.9)),
  url('/static/images/room-after-1.webp') center/cover no-repeat}}
.hero::after{content:"";position:absolute;inset:0;z-index:-2;opacity:.5;
  background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
  background-size:64px 64px;-webkit-mask-image:radial-gradient(circle at 78% 20%,#000,transparent 60%);mask-image:radial-gradient(circle at 78% 20%,#000,transparent 60%)}
.hero .inner{padding:40px 0;max-width:800px}
.hero .badge-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}
.hero .badge-row span{font-size:12px;color:#e7ddcd;border:1px solid var(--line);border-radius:999px;padding:6px 13px;background:rgba(249,115,22,.06)}
.hero h1{font-family:'Fraunces',serif;font-weight:600;font-size:clamp(40px,7vw,76px);line-height:1.02;margin:0 0 20px;color:#fff;letter-spacing:-.01em}
.hero h1 em{font-style:italic;color:var(--orange-soft)}
.hero p{font-size:clamp(16px,2.2vw,20px);color:#e5ddcd;max-width:560px;margin-bottom:32px}
.cta-row{display:flex;gap:14px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:9px;padding:14px 26px;border-radius:999px;font-weight:600;font-size:15px;cursor:pointer;border:1px solid transparent;transition:.22s;font-family:inherit}
.btn-orange{background:var(--orange);color:#fff}
.btn-orange:hover{background:#ea6a0c;transform:translateY(-2px)}
.btn-ghost{border-color:rgba(245,239,232,.3);color:#fff}
.btn-ghost:hover{border-color:var(--orange);color:var(--orange)}
.hero .meta{display:flex;gap:26px;flex-wrap:wrap;margin-top:40px;color:var(--mut);font-size:13.5px}
.hero .meta b{color:var(--cream);font-weight:600}

.strip{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--ink2)}
.strip .wrap{display:flex;flex-wrap:wrap;gap:14px 40px;padding:20px 24px;align-items:center;justify-content:center}
.strip span{display:inline-flex;align-items:center;gap:9px;font-size:13.5px;color:#d9d0bd}
.strip svg{width:18px;height:18px;color:var(--orange)}

.sec{padding:clamp(64px,9vw,110px) 0}
.svc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:42px}
.svc{background:linear-gradient(180deg,var(--panel),var(--ink2));border:1px solid var(--line);border-radius:var(--rad);padding:28px 26px;transition:.25s}
.svc:hover{transform:translateY(-4px);border-color:rgba(249,115,22,.5);box-shadow:0 18px 40px -24px rgba(249,115,22,.45)}
.svc .ic{width:46px;height:46px;border-radius:12px;display:grid;place-items:center;background:rgba(249,115,22,.1);border:1px solid var(--line);color:var(--orange);margin-bottom:16px}
.svc .ic svg{width:24px;height:24px}
.svc h3{font-family:'Fraunces',serif;font-size:19px;font-weight:600;margin-bottom:7px}
.svc p{font-size:14px;color:var(--mut)}

.gallery{columns:3 280px;column-gap:14px;margin-top:42px}
.shot{position:relative;break-inside:avoid;margin-bottom:14px;border-radius:14px;overflow:hidden;cursor:pointer;border:1px solid var(--line);background:var(--ink2)}
.shot img{width:100%;transition:transform .5s ease;display:block}
.shot:hover img{transform:scale(1.05)}
.shot .tag{position:absolute;top:10px;left:10px;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--orange);background:rgba(7,6,5,.72);border:1px solid var(--line);padding:4px 9px;border-radius:999px}

/* before / after projects */
.ba-wrap{display:flex;flex-direction:column;gap:26px;margin-top:42px}
.ba{background:linear-gradient(180deg,var(--panel),var(--ink2));border:1px solid var(--line);border-radius:var(--rad);padding:22px 22px 24px}
.ba-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;margin-bottom:16px}
.ba-head h3{font-family:'Fraunces',serif;font-weight:600;font-size:20px;color:var(--cream)}
.ba-head p{font-size:14px;color:var(--mut);flex:1 1 300px;min-width:220px}
.ba-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.ba-row.two{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.ba .shot{margin:0}
.ba .shot img{width:100%;height:100%;aspect-ratio:4/3;object-fit:cover}
.tag.before{color:#ece3d2;background:rgba(7,6,5,.8)}
.tag.after{color:#fff;background:var(--orange);border-color:transparent}
.ba-more{font-family:'Fraunces',serif;font-weight:600;font-size:22px;color:var(--cream);margin:52px 0 2px}

/* coverage / areas */
.cov{display:grid;grid-template-columns:300px 1fr;gap:44px;align-items:center;margin-top:42px}
.radar{justify-self:center;width:100%;max-width:300px}
.radar svg{width:100%;height:auto;display:block}
.pills{display:flex;flex-wrap:wrap;gap:9px}
.pill{font-size:13.5px;color:#e9e2d3;border:1px solid var(--line);background:rgba(249,115,22,.05);border-radius:999px;padding:7px 14px;transition:.2s}
.pill:hover{border-color:rgba(249,115,22,.55);color:var(--orange)}
.pill.hub{background:var(--orange);color:#fff;border-color:transparent;font-weight:600}
.cov-note{margin-top:20px;font-size:13.5px;color:var(--mut);max-width:560px}
@media(max-width:760px){.cov{grid-template-columns:1fr;gap:26px}.radar{max-width:260px}}

.lb{position:fixed;inset:0;z-index:120;background:rgba(6,5,4,.94);display:none;align-items:center;justify-content:center;padding:24px}
.lb.open{display:flex}
.lb img{max-width:92vw;max-height:84vh;border-radius:10px;box-shadow:0 30px 80px -20px rgba(0,0,0,.8)}
.lb button{position:absolute;background:rgba(255,255,255,.06);border:1px solid var(--line);color:#fff;width:48px;height:48px;border-radius:50%;font-size:22px;cursor:pointer;display:grid;place-items:center}
.lb .x{top:20px;right:20px}.lb .prev{left:20px;top:50%;transform:translateY(-50%)}.lb .next{right:20px;top:50%;transform:translateY(-50%)}
@media(max-width:600px){.lb .prev,.lb .next{display:none}}

.why{background:var(--ink2);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.why-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:30px;margin-top:42px}
.why-grid .n{font-family:'Fraunces',serif;color:var(--orange);font-size:34px;font-weight:600}
.why-grid h3{font-family:'Fraunces',serif;font-size:20px;margin:8px 0 6px}
.why-grid p{color:var(--mut);font-size:14.5px}

.rev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;margin-top:40px}
.rev{background:linear-gradient(180deg,var(--panel),var(--ink2));border:1px solid var(--line);border-radius:var(--rad);padding:28px 26px}
.stars{color:var(--orange);letter-spacing:3px;font-size:15px;margin-bottom:14px}
.rev p{font-size:15px;color:#ece4d3;line-height:1.65}
.rev .who{margin-top:16px;font-size:13px;color:var(--mut)}
.rev .who b{color:var(--cream);font-weight:600}

.contact{background:radial-gradient(120% 90% at 50% -10%,rgba(249,115,22,.12),transparent 60%),var(--ink)}
.cgrid{display:grid;grid-template-columns:1.1fr .9fr;gap:40px;margin-top:42px;align-items:start}
@media(max-width:820px){.cgrid{grid-template-columns:1fr}}
.ccard{background:var(--ink2);border:1px solid var(--line);border-radius:var(--rad);padding:30px}
.crow{display:flex;align-items:center;gap:14px;padding:15px 0;border-bottom:1px solid rgba(249,115,22,.12)}
.crow:last-child{border-bottom:0}
.crow .ic{width:42px;height:42px;border-radius:11px;display:grid;place-items:center;background:rgba(249,115,22,.1);border:1px solid var(--line);color:var(--orange);flex:none}
.crow .ic svg{width:20px;height:20px}
.crow .lbl{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.crow .val{font-size:16px;color:var(--cream);font-weight:500}
.socials{display:flex;gap:12px;margin-top:22px}
.socials a{width:44px;height:44px;border-radius:11px;display:grid;place-items:center;border:1px solid var(--line);color:var(--orange);transition:.2s}
.socials a:hover{background:var(--orange);color:#fff}
.socials svg{width:20px;height:20px}

footer{border-top:1px solid var(--line);background:var(--ink2);padding:34px 0;color:var(--mut);font-size:13px}
footer .wrap{display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;align-items:center}

.wa{position:fixed;left:20px;bottom:22px;z-index:90;width:56px;height:56px;border-radius:50%;background:#25D366;display:grid;place-items:center;box-shadow:0 10px 30px -8px rgba(37,211,102,.7);transition:.2s}
.wa:hover{transform:scale(1.07)}.wa svg{width:30px;height:30px;color:#fff}

.chat-btn{position:fixed;right:20px;bottom:22px;z-index:95;background:var(--orange);color:#fff;border:0;border-radius:999px;padding:14px 22px;font-weight:600;font-family:inherit;font-size:15px;cursor:pointer;display:flex;align-items:center;gap:9px;box-shadow:0 12px 34px -10px rgba(249,115,22,.8);transition:.2s}
.chat-btn:hover{transform:translateY(-2px)}
.chat-btn svg{width:20px;height:20px}
.chat-panel{position:fixed;right:20px;bottom:22px;z-index:96;width:min(390px,calc(100vw - 40px));height:min(620px,calc(100vh - 44px));background:#17140f;border:1px solid var(--line);border-radius:20px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 30px 80px -20px rgba(0,0,0,.7)}
.chat-panel.open{display:flex}
.chat-head{background:linear-gradient(120deg,#201a13,#15110c);padding:16px 18px;display:flex;align-items:center;gap:12px;border-bottom:1px solid var(--line)}
.chat-head .logo{width:40px;height:40px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:#0d0c0b}
.chat-head .logo svg{width:24px;height:16px}
.chat-head .t{font-family:'Fraunces',serif;font-weight:600;color:var(--orange)}
.chat-head .s{font-size:11.5px;color:var(--mut)}
.chat-head .close{margin-left:auto;background:none;border:0;color:var(--mut);font-size:22px;cursor:pointer}
.msgs{flex:1;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:82%;padding:11px 14px;border-radius:14px;font-size:14.5px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}
.msg.bot{align-self:flex-start;background:#241d15;border:1px solid var(--line);color:#ece4d3;border-bottom-left-radius:4px}
.msg.user{align-self:flex-end;background:var(--orange);color:#fff;border-bottom-right-radius:4px;font-weight:500}
.msg.img{padding:4px;background:#241d15;border:1px solid var(--line)}
.msg.img img{border-radius:10px;max-width:180px}
.typing{align-self:flex-start;color:var(--mut);font-size:13px;padding:4px 6px}
.chat-in{display:flex;gap:8px;padding:12px;border-top:1px solid var(--line);background:#15110c;align-items:center}
.chat-in input[type=text]{flex:1;background:#241d15;border:1px solid var(--line);color:var(--cream);border-radius:999px;padding:11px 16px;font-size:14.5px;font-family:inherit;outline:none}
.chat-in input[type=text]:focus{border-color:var(--orange)}
.iconbtn{background:#241d15;border:1px solid var(--line);color:var(--orange);width:42px;height:42px;border-radius:50%;cursor:pointer;display:grid;place-items:center;flex:none;transition:.2s}
.iconbtn:hover{background:var(--orange);color:#fff}.iconbtn svg{width:19px;height:19px}
.iconbtn.busy{opacity:.5;pointer-events:none}
.hp{position:absolute;left:-9999px}
</style>
</head>
<body>
<div class="progress" id="progress"></div>

<nav>
  <div class="wrap bar">
    <a class="brand" href="#top">{{ logo|safe }}<span style="display:inline-block"><b>APEX</b><span>Home Transformations</span></span></a>
    <button class="burger" onclick="document.getElementById('nl').classList.toggle('open')" aria-label="Menu">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
    </button>
    <div class="navlinks" id="nl">
      <a href="#services" onclick="closeNav()">Services</a>
      <a href="#work" onclick="closeNav()">Our Work</a>
      <a href="#reviews" onclick="closeNav()">Reviews</a>
      <a href="#areas" onclick="closeNav()">Areas</a>
      <a href="#contact" onclick="closeNav()">Contact</a>
      <a class="navcta" href="#contact" onclick="closeNav();openChat()">Free Quote</a>
    </div>
  </div>
</nav>

<header class="hero" id="top">
  <div class="wrap inner">
    <div class="badge-row reveal">
      <span>★ Painter &amp; Decorator</span><span>Woking · Surrey</span><span>ID-checked · Est. 2025</span>
    </div>
    <h1 class="reveal">Elevating homes,<br><em>transforming lives.</em></h1>
    <p class="reveal">Interior &amp; exterior painting, decorating, feature walls, fences and handyman work across {{ b.area_line }} — done properly, tidy, and finished to a professional standard.</p>
    <div class="cta-row reveal">
      <button class="btn btn-orange" onclick="openChat()">Get a free quote
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </button>
      <a class="btn btn-ghost" href="tel:+{{ b.phone_e164 }}">Call {{ b.phone_display }}</a>
    </div>
    <div class="meta reveal">
      <div><b>Free</b> no-obligation quotes</div><div><b>Tidy</b> &amp; reliable</div><div><b>Interior &amp; exterior</b></div>
    </div>
  </div>
</header>

<div class="strip">
  <div class="wrap">
    {% for t in ["Interior Painting","Exterior Painting","Feature Walls","Woodwork","Fence Painting","Handyman"] %}
    <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>{{ t }}</span>
    {% endfor %}
  </div>
</div>

<section class="sec" id="services">
  <div class="wrap">
    <div class="eyebrow reveal">What we do</div>
    <h2 class="title reveal">Painting, decorating<br>&amp; everything in between.</h2>
    <p class="lede reveal">Whether it's a single feature wall or the whole house inside and out, Claud gets it prepped, painted and finished cleanly.</p>
    <div class="svc-grid">
      {% for s in services %}
      <div class="svc reveal"><div class="ic">{{ s.icon|safe }}</div><h3>{{ s.title }}</h3><p>{{ s.desc }}</p></div>
      {% endfor %}
    </div>
  </div>
</section>

<section class="sec" id="work" style="padding-top:0">
  <div class="wrap">
    <div class="eyebrow reveal">Our work</div>
    <h2 class="title reveal">Before &amp; after</h2>
    <p class="lede reveal">Real jobs around Woking and Surrey \u2014 see the difference on each one. Tap any photo to enlarge.</p>
    <div class="ba-wrap">
      {% for p in projects %}
      <div class="ba reveal">
        <div class="ba-head"><h3>{{ p.title }}</h3><p>{{ p.blurb }}</p></div>
        <div class="ba-row{% if p.shots|length == 2 %} two{% endif %}">
          {% for s in p.shots %}
          <figure class="shot">
            <span class="tag {{ 'after' if s.label == 'After' else 'before' }}">{{ s.label }}</span>
            <img src="{{ s.src }}" alt="{{ p.title }} \u2014 {{ s.label|lower }}" loading="lazy">
          </figure>
          {% endfor %}
        </div>
      </div>
      {% endfor %}
    </div>

    <h3 class="ba-more reveal">More recent work</h3>
    <div class="gallery" id="gallery">
      {% for url in gallery %}
      <figure class="shot reveal">
        <span class="tag">Apex</span>
        <img src="{{ url }}" alt="Apex Home Transformations \u2014 recent painting &amp; decorating work" loading="lazy">
      </figure>
      {% endfor %}
    </div>
  </div>
</section>

<section class="sec why">
  <div class="wrap">
    <div class="eyebrow reveal">Why Apex</div>
    <h2 class="title reveal">Done right, left tidy.</h2>
    <div class="why-grid">
      <div class="reveal"><div class="n">01</div><h3>Proper prep</h3><p>Filling, sanding and masking done first — because that's what makes a finish last and look sharp.</p></div>
      <div class="reveal"><div class="n">02</div><h3>Clean &amp; considerate</h3><p>Dust sheets down, tidy as we go, and your home left spotless at the end of every day.</p></div>
      <div class="reveal"><div class="n">03</div><h3>Free, honest quotes</h3><p>Clear pricing up front with no surprises — and a finish you'll be happy to show off.</p></div>
    </div>
  </div>
</section>

<section class="sec" id="reviews">
  <div class="wrap">
    <div class="eyebrow reveal">Reviews</div>
    <h2 class="title reveal">What customers say</h2>
    <p class="lede reveal">Verified reviews from real jobs booked through MyJobQuote.</p>
    <div class="rev-grid">
      {% for r in reviews %}
      <div class="rev reveal"><div class="stars">★★★★★</div><p>“{{ r.text }}”</p>
        <div class="who"><b>{{ r.name }}</b> · {{ r.where }}</div></div>
      {% endfor %}
    </div>
  </div>
</section>

<section class="sec" id="areas">
  <div class="wrap">
    <div class="eyebrow reveal">Where we work</div>
    <h2 class="title reveal">Covering Woking &amp; 15 miles around.</h2>
    <p class="lede reveal">Based in Woking and working right across west Surrey and over the Berkshire border. If you're within about 15 miles, Claud can get to you.</p>
    <div class="cov reveal">
      <div class="radar">
        <svg viewBox="0 0 320 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Map showing Apex covers roughly 15 miles around Woking">
          <defs>
            <radialGradient id="cg" cx="50%" cy="53%" r="52%">
              <stop offset="0%" stop-color="rgba(249,115,22,.18)"/>
              <stop offset="60%" stop-color="rgba(249,115,22,.05)"/>
              <stop offset="100%" stop-color="rgba(249,115,22,0)"/>
            </radialGradient>
          </defs>
          <circle cx="160" cy="160" r="135" fill="url(#cg)"/>
          <circle cx="160" cy="160" r="135" fill="none" stroke="rgba(249,115,22,.34)" stroke-width="1" stroke-dasharray="3 5"/>
          <circle cx="160" cy="160" r="90"  fill="none" stroke="rgba(249,115,22,.26)" stroke-width="1" stroke-dasharray="3 5"/>
          <circle cx="160" cy="160" r="45"  fill="none" stroke="rgba(249,115,22,.2)"  stroke-width="1" stroke-dasharray="3 5"/>
          <line x1="160" y1="22" x2="160" y2="298" stroke="rgba(249,115,22,.1)" stroke-width="1"/>
          <line x1="25"  y1="160" x2="295" y2="160" stroke="rgba(249,115,22,.1)" stroke-width="1"/>
          <text x="160" y="16" text-anchor="middle" fill="#a99f92" font-size="10" font-family="Inter,sans-serif" letter-spacing=".14em">15 MILES</text>
          <g font-family="Inter,sans-serif" font-size="9.5" fill="#cfc6b6">
            <circle cx="177" cy="113" r="2.6" fill="#f97316"/><text x="183" y="112">Chertsey</text>
            <circle cx="203" cy="130" r="2.6" fill="#f97316"/><text x="209" y="129">Weybridge</text>
            <circle cx="218" cy="181" r="2.6" fill="#f97316"/><text x="224" y="184">Cobham</text>
            <circle cx="126" cy="209" r="2.6" fill="#f97316"/><text x="120" y="221" text-anchor="end">Guildford</text>
            <circle cx="92"  cy="154" r="2.6" fill="#f97316"/><text x="86"  y="153" text-anchor="end">Camberley</text>
            <circle cx="143" cy="131" r="2.6" fill="#f97316"/><text x="138" y="126" text-anchor="end">Chobham</text>
          </g>
          <circle cx="160" cy="160" r="7" fill="#f97316"/>
          <circle cx="160" cy="160" r="7" fill="none" stroke="#fff" stroke-width="1.5" opacity=".85"/>
          <text x="160" y="182" text-anchor="middle" fill="#fff" font-size="12.5" font-weight="600" font-family="Fraunces,serif">Woking</text>
        </svg>
      </div>
      <div>
        <div class="pills">
          <span class="pill hub">{{ coverage.hub }}</span>
          {% for t in coverage.towns %}<span class="pill">{{ t }}</span>{% endfor %}
        </div>
        <p class="cov-note">\u2026and everywhere in between. Just outside the circle? Get in touch \u2014 Claud will happily take a look.</p>
      </div>
    </div>
  </div>
</section>

<section class="sec contact" id="contact">
  <div class="wrap">
    <div class="eyebrow reveal">Get in touch</div>
    <h2 class="title reveal">Free quote, no obligation.</h2>
    <p class="lede reveal">Tell Claud about the job and he'll get straight back to you — usually the same day. Use the chat for the quickest quote, or reach out any way you like.</p>
    <div class="cgrid">
      <div class="ccard reveal">
        <div class="crow"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg></div>
          <div><div class="lbl">Call us</div><a class="val" href="tel:+{{ b.phone_e164 }}">{{ b.phone_display }}</a></div></div>
        <div class="crow"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16v16H4z"/><path d="m4 6 8 6 8-6"/></svg></div>
          <div><div class="lbl">Email</div><a class="val" href="mailto:{{ b.email_public }}">{{ b.email_public }}</a></div></div>
        <div class="crow"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg></div>
          <div><div class="lbl">Area covered</div><div class="val">{{ b.area_line }}</div></div></div>
        <div class="socials">
          <a href="https://wa.me/{{ b.phone_e164 }}" aria-label="WhatsApp" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2-.2.3-.7.9-.9 1.1-.2.2-.3.2-.6.1-1.8-.9-3-1.6-4.2-3.6-.3-.5.3-.5.8-1.6.1-.2 0-.4 0-.5 0-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.3 5.2 4.6 2 .8 2.7.9 3.7.8.6-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3z"/><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2c-1.5 0-3-.4-4.3-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2z"/></svg></a>
        </div>
      </div>
      <div class="ccard reveal" style="display:flex;flex-direction:column;justify-content:center;text-align:center;gap:14px">
        <div style="font-family:'Fraunces',serif;font-size:24px;color:var(--orange-soft)">Quickest way to a quote</div>
        <p style="color:var(--mut);font-size:15px">Chat to our assistant — describe the job, drop a photo, and Claud will do the rest.</p>
        <button class="btn btn-orange" style="align-self:center" onclick="openChat()">Start a chat
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></button>
      </div>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <div>© <span id="yr"></span> {{ b.name }} · {{ b.postcode }} Woking, Surrey</div>
    <div>Interior &amp; Exterior Painting · Decorating · Feature Walls · Fences · Handyman</div>
  </div>
</footer>

<a class="wa" href="https://wa.me/{{ b.phone_e164 }}" target="_blank" rel="noopener" aria-label="WhatsApp us">
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2-.2.3-.7.9-.9 1.1-.2.2-.3.2-.6.1-1.8-.9-3-1.6-4.2-3.6-.3-.5.3-.5.8-1.6.1-.2 0-.4 0-.5 0-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.3 5.2 4.6 2 .8 2.7.9 3.7.8.6-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3z"/><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2c-1.5 0-3-.4-4.3-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2z"/></svg>
</a>

<div class="lb" id="lb">
  <button class="x" onclick="closeLb()">×</button>
  <button class="prev" onclick="stepLb(-1)">‹</button>
  <button class="next" onclick="stepLb(1)">›</button>
  <img id="lbimg" src="" alt="">
</div>

<button class="chat-btn" id="chatBtn" onclick="openChat()">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
  Chat for a quote
</button>
<div class="chat-panel" id="chatPanel">
  <div class="chat-head">
    <div class="logo">{{ logo|safe }}</div>
    <div><div class="t">Apex Assistant</div><div class="s">Typically replies in seconds</div></div>
    <button class="close" onclick="closeChat()">×</button>
  </div>
  <div class="msgs" id="msgs"></div>
  <div class="chat-in">
    <input type="text" class="hp" id="website" tabindex="-1" autocomplete="off" aria-hidden="true">
    <button class="iconbtn" id="attachBtn" onclick="document.getElementById('fileIn').click()" aria-label="Attach photo">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.4 11.05 12.25 20.2a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-9.2 9.19a1 1 0 0 1-1.41-1.41l8.49-8.49"/></svg>
    </button>
    <input type="file" id="fileIn" accept="image/*" multiple style="display:none">
    <input type="text" id="chatInput" placeholder="Describe your job…" autocomplete="off">
    <button class="iconbtn" onclick="sendMsg()" aria-label="Send">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/></svg>
    </button>
  </div>
</div>

<script>
document.getElementById('yr').textContent = new Date().getFullYear();
function closeNav(){document.getElementById('nl').classList.remove('open')}
const prog=document.getElementById('progress');
addEventListener('scroll',()=>{const h=document.documentElement;prog.style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight)*100)+'%'},{passive:true});
const io=new IntersectionObserver((es)=>{es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

let lbi=0;
function shots(){return [...document.querySelectorAll('.shot img')]}
document.getElementById('work').addEventListener('click',e=>{const img=e.target.closest('.shot')&&e.target.closest('.shot').querySelector('img');
  if(!img)return;lbi=shots().indexOf(img);showLb()});
function showLb(){const im=shots()[lbi];if(!im)return;document.getElementById('lbimg').src=im.src;document.getElementById('lb').classList.add('open')}
function stepLb(d){const s=shots();lbi=(lbi+d+s.length)%s.length;showLb()}
function closeLb(){document.getElementById('lb').classList.remove('open')}
document.getElementById('lb').onclick=e=>{if(e.target.id==='lb')closeLb()};
document.addEventListener('keydown',e=>{if(!document.getElementById('lb').classList.contains('open'))return;
  if(e.key==='Escape')closeLb();if(e.key==='ArrowRight')stepLb(1);if(e.key==='ArrowLeft')stepLb(-1)});

let greeted=false;
function openChat(){document.getElementById('chatPanel').classList.add('open');document.getElementById('chatBtn').style.display='none';
  if(!greeted){greeted=true;addMsg("Hi! 👋 I'm here for Apex Home Transformations. What are you looking to have done — a room or two, the outside of the house, fences?","bot")}
  document.getElementById('chatInput').focus()}
function closeChat(){document.getElementById('chatPanel').classList.remove('open');document.getElementById('chatBtn').style.display='flex'}
function addMsg(t,who){const m=document.createElement('div');m.className='msg '+who;m.textContent=t;const box=document.getElementById('msgs');box.appendChild(m);box.scrollTop=box.scrollHeight}
function addImg(src){const m=document.createElement('div');m.className='msg img user';const i=document.createElement('img');i.src=src;m.appendChild(i);const box=document.getElementById('msgs');box.appendChild(m);box.scrollTop=box.scrollHeight}
function typing(on){const box=document.getElementById('msgs');let t=document.getElementById('typing');
  if(on&&!t){t=document.createElement('div');t.id='typing';t.className='typing';t.textContent='Apex is typing…';box.appendChild(t);box.scrollTop=box.scrollHeight}else if(!on&&t){t.remove()}}
async function sendMsg(){const inp=document.getElementById('chatInput');const text=inp.value.trim();if(!text)return;
  addMsg(text,'user');inp.value='';typing(true);
  try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({message:text,website:document.getElementById('website').value})});
    const d=await r.json();typing(false);addMsg(d.reply,'bot');
  }catch(e){typing(false);addMsg("Sorry, something glitched there — give that another go?","bot")}}
document.getElementById('chatInput').addEventListener('keydown',e=>{if(e.key==='Enter')sendMsg()});
function resizeImage(file){return new Promise((res,rej)=>{const r=new FileReader();
  r.onload=()=>{const img=new Image();img.onload=()=>{const max=1280;let{width:w,height:h}=img;
    if(w>max||h>max){if(w>h){h=Math.round(h*max/w);w=max}else{w=Math.round(w*max/h);h=max}}
    const c=document.createElement('canvas');c.width=w;c.height=h;c.getContext('2d').drawImage(img,0,0,w,h);
    res(c.toDataURL('image/jpeg',0.82))};img.onerror=rej;img.src=r.result};r.onerror=rej;r.readAsDataURL(file)})}
document.getElementById('fileIn').addEventListener('change',async e=>{const files=[...e.target.files];e.target.value='';
  const ab=document.getElementById('attachBtn');ab.classList.add('busy');
  for(const file of files){if(!file.type||file.type.indexOf('image/')!==0){addMsg("That doesn't look like a photo — try an image file.","bot");continue}
    let url;try{url=await resizeImage(file)}catch(_){addMsg("Couldn't read that one. If it's a HEIC iPhone photo, save it as JPG first.","bot");continue}
    addImg(url);try{const r=await fetch('/upload',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({image:url})});
      const d=await r.json();addMsg(d.reply,'bot')}catch(_){addMsg("The photo didn't upload — try again in a sec.","bot")}}
  ab.classList.remove('busy')});
</script>
</body></html>"""


def ensure_session():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())


@app.route("/")
def home():
    ensure_session()
    return render_template_string(PAGE, b=BUSINESS, services=SERVICES,
                                  projects=PROJECTS, gallery=GALLERY,
                                  coverage=COVERAGE, reviews=REVIEWS, logo=LOGO_SVG)


@app.route("/sitemap.xml")
def sitemap():
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           '<url><loc>https://www.apexhome.co.uk/</loc></url></urlset>')
    return Response(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nAllow: /\n", mimetype="text/plain")


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    session_id = session.get("session_id") or str(uuid.uuid4())
    session["session_id"] = session_id
    if session_id not in all_conversations:
        all_conversations[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation = all_conversations[session_id]

    data = request.get_json(silent=True) or {}
    if (data.get("website") or "").strip():
        return jsonify({"reply": "Thanks!"})

    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"reply": "Sorry, I didn't catch that — could you type that again?"})

    now = time.time()
    recent = [t for t in chat_activity.get(session_id, []) if now - t < 60]
    if len(recent) >= 20:
        return jsonify({"reply": "You're sending messages very quickly — give it a few seconds and try again."})
    if len(conversation) >= 60:
        return jsonify({"reply": "Thanks for all the detail! Drop your name and number and Claud will pick this up with you personally."})
    recent.append(now)
    chat_activity[session_id] = recent

    conversation.append({"role": "user", "content": user_message})
    try:
        response = client_chat(model="llama-3.3-70b-versatile", messages=conversation, max_tokens=256, timeout=20)
        ai_reply = response.choices[0].message.content
    except Exception as e:
        print(f"Chat completion failed: {e}")
        conversation.pop()
        return jsonify({"reply": "Sorry, I had a brief hiccup there — could you send that again?"})

    lead_ready = bool(re.search(r"\[\[?\s*READY\s*\]?\]", ai_reply, re.I))
    ai_reply = re.sub(r"\[\[?\s*READY\s*\]?\]", "", ai_reply).replace("[LEAD_CAPTURED]", "").strip()
    if not ai_reply:
        ai_reply = "Thanks — that's everything we need for now. Claud will be in touch shortly to arrange your free quote."
    conversation.append({"role": "assistant", "content": ai_reply})

    if session_id not in notified_sessions and has_contact_info(conversation):
        if lead_ready or _looks_like_closing(user_message) or len(conversation) >= 24:
            notified_sessions.add(session_id)
            send_lead_email(list(conversation), list(session_images.get(session_id, [])))

    return jsonify({"reply": ai_reply})


@app.route("/upload", methods=["POST"])
def upload_endpoint():
    session_id = session.get("session_id") or str(uuid.uuid4())
    session["session_id"] = session_id
    if session_id not in all_conversations:
        all_conversations[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation = all_conversations[session_id]

    data = request.get_json(silent=True) or {}
    image = _decode_image_data_url(data.get("image", ""))
    if image is None:
        return jsonify({"reply": "Sorry, I couldn't read that image. Please try a JPG or PNG."}), 400

    images = session_images.setdefault(session_id, [])
    if len(images) >= MAX_IMAGES_PER_SESSION:
        return jsonify({"reply": "Thanks — that's plenty of photos for now. Leave your name and number and we'll take a look."})
    images.append(image)
    conversation.append({"role": "user", "content": "(Customer attached a photo of the job)"})
    reply = ("Thanks, got your photo — that really helps. Add more if you like, or leave your name and "
             "number and Claud will get you a free quote.")
    conversation.append({"role": "assistant", "content": reply})
    if session_id in notified_sessions:
        send_photo_followup(list(conversation), [image])
    return jsonify({"reply": reply})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)
