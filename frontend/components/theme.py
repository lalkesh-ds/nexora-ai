"""Nexora visual system: design tokens, CSS, icons and small HTML helpers.

Everything here is presentation only. HTML is always emitted as a single
line (see `html`) so Markdown never mistakes indented tags for code blocks,
and every dynamic string is escaped with `esc`.
"""
import html as _html
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"
AVATAR = ASSETS / "nexora_small.png"
FULL_LOGO = ASSETS / "nexora.png"


def esc(value) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def html(fragment: str) -> str:
    """Collapse a multi-line HTML fragment into one physical line."""
    return "".join(line.strip() for line in fragment.strip().splitlines())


def render(fragment: str):
    st.markdown(html(fragment), unsafe_allow_html=True)


def assistant_avatar():
    for p in (AVATAR, FULL_LOGO):
        if p.exists():
            return str(p)
    return None


def page_icon():
    p = AVATAR if AVATAR.exists() else FULL_LOGO
    return str(p) if p.exists() else "✦"


# ---------------------------------------------------------------- icons ----
_ICON_PATHS = {
    "doc": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "spark": '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.7 1.8 1.8.7-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7z"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="m21 16-5-5-8 9"/>',
    "sheet": '<rect x="3.5" y="4" width="17" height="16" rx="2.5"/><path d="M3.5 10h17M3.5 15h17M10 4v16"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "clip": '<path d="m21 11-8.6 8.6a5 5 0 0 1-7-7L14 4a3.4 3.4 0 0 1 4.8 4.8l-8.5 8.5a1.8 1.8 0 0 1-2.6-2.6L15 7"/>',
    "alert": '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5M12 17.4v.1"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "brain": '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-5.04z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-5.04z"/>',
    "refresh": '<path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>',
}


def icon(name: str, size: int = 16) -> str:
    return (
        f'<svg class="nx-i" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{_ICON_PATHS.get(name, "")}</svg>'
    )


def file_kind(filename: str) -> tuple[str, str]:
    """(icon name, tint class) for a filename."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return "doc", "pdf"
    if ext in ("docx", "doc", "txt"):
        return "doc", "word"
    if ext in ("csv", "xlsx", "xls"):
        return "sheet", "sheet"
    if ext in ("jpg", "jpeg", "png", "webp", "gif"):
        return "image", "img"
    return "doc", "word"


def brand_mark(uid: str, size: int = 34) -> str:
    g = f"nxg-{uid}"
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 32 32" fill="none" aria-hidden="true">'
        f'<defs><linearGradient id="{g}" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#4F6BFF"/><stop offset="1" stop-color="#9B5CF6"/></linearGradient></defs>'
        f'<rect width="32" height="32" rx="9.5" fill="url(#{g})"/>'
        f'<path d="M10.5 23V9.5L21.5 22.5V9" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M25 3.6l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9z" fill="#fff" opacity=".9"/></svg>'
    )


# ------------------------------------------------------------------ CSS ----
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@600;700;800&display=swap');

:root{
  --bg:#F6F7FB; --surface:#FFFFFF; --surface-2:#F9FAFD;
  --border:#E6E8F0; --border-strong:#D5D9E6;
  --text:#0F172A; --text-2:#475569; --muted:#7A8497;
  --accent:#5B5BF0; --accent-2:#8B5CF6; --accent-soft:#EEEFFF; --accent-ring:rgba(91,91,240,.16);
  --ok:#059669; --ok-soft:#E7F7F0; --warn:#B45309; --warn-soft:#FEF3E2; --err:#DC2626; --err-soft:#FDECEC;
  --shadow-sm:0 1px 2px rgba(15,23,42,.04),0 1px 3px rgba(15,23,42,.05);
  --shadow-md:0 4px 14px rgba(30,41,90,.07),0 1px 3px rgba(15,23,42,.05);
  --shadow-lg:0 12px 36px rgba(40,50,120,.12);
  --grad:linear-gradient(135deg,#4F6BFF 0%,#8B5CF6 100%);
}

html, body, .stApp, [data-testid="stAppViewContainer"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  color:var(--text);
}
.stApp{
  background-color:var(--bg);
  background-image:
    radial-gradient(900px 420px at 85% -8%, rgba(139,92,246,.10), transparent 60%),
    radial-gradient(800px 420px at 8% -10%, rgba(79,107,255,.09), transparent 60%);
  background-attachment:fixed;
}
[data-testid="stHeader"]{background:transparent;}
.stAppDeployButton,[data-testid="stDecoration"],footer{display:none !important;}
h1,h2,h3{font-family:'Manrope','Inter',sans-serif;letter-spacing:-.01em;color:var(--text);}
.nx-i{display:inline-block;vertical-align:-3px;flex:none;}

/* ---------- layout ---------- */
[data-testid="stMainBlockContainer"], .block-container{
  max-width:920px; padding:1.1rem 2rem 7.5rem;
}
[data-testid="stBottomBlockContainer"]{max-width:920px;padding:.5rem 2rem 1.25rem;}
[data-testid="stBottom"] > div{background:transparent;}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--border);}
[data-testid="stSidebar"][aria-expanded="true"]{width:304px !important;min-width:304px !important;}
[data-testid="stSidebarUserContent"]{padding:1.1rem 1rem 1.5rem !important;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.55rem;}
.nx-brand{display:flex;align-items:center;gap:.7rem;margin:.1rem 0 .35rem;}
.nx-brand-name{font-family:'Manrope',sans-serif;font-weight:800;font-size:1.02rem;letter-spacing:.14em;color:var(--text);line-height:1.1;}
.nx-brand-tag{font-size:.7rem;color:var(--muted);margin-top:.15rem;line-height:1.2;}
.nx-side-title{display:flex;align-items:center;justify-content:space-between;font-size:.68rem;font-weight:600;
  letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:.85rem 0 .1rem;}
.nx-count{background:var(--accent-soft);color:var(--accent);border-radius:999px;padding:.05rem .5rem;font-size:.68rem;letter-spacing:0;}
.nx-empty-note{font-size:.8rem;color:var(--muted);background:var(--surface-2);border:1px dashed var(--border-strong);
  border-radius:12px;padding:.7rem .8rem;line-height:1.45;}
[data-testid="stSidebar"] hr{margin:.6rem 0;border-color:var(--border);}

/* ---------- buttons ---------- */
.stButton > button,[data-testid="stDownloadButton"] > button{
  border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--text);
  font-size:.84rem;font-weight:500;padding:.42rem .8rem;box-shadow:var(--shadow-sm);
  transition:border-color .15s,background .15s,box-shadow .15s,transform .05s;
}
.stButton > button:hover,[data-testid="stDownloadButton"] > button:hover{
  border-color:#C4C8F5;background:var(--accent-soft);color:var(--accent);
}
.stButton > button:active{transform:translateY(1px);}
.stButton > button[kind="primary"],.stButton > button[data-testid="stBaseButton-primary"]{
  background:var(--grad);color:#fff;border:none;box-shadow:0 4px 14px rgba(91,91,240,.32);
}
.stButton > button[kind="primary"]:hover,.stButton > button[data-testid="stBaseButton-primary"]:hover{
  background:var(--grad);color:#fff;filter:brightness(1.06);
}
.stButton > button[kind="primary"] p,.stButton > button[data-testid="stBaseButton-primary"] p{color:#fff;}
.stButton > button:disabled{opacity:.5;box-shadow:none;}

.st-key-nx_new button{width:100%;padding:.6rem .9rem;font-weight:600;font-size:.88rem;justify-content:flex-start;}
[class*="st-key-nx_recent_"] button{
  width:100%;justify-content:flex-start;text-align:left;background:transparent;border:1px solid transparent;
  box-shadow:none;color:var(--text-2);font-weight:450;padding:.38rem .6rem;
}
[class*="st-key-nx_recent_"] button p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left;}
[class*="st-key-nx_recent_"] button:hover{background:var(--surface-2);border-color:var(--border);color:var(--text);}
[class*="st-key-nx_recent_active_"] button{background:var(--accent-soft);color:var(--accent);border-color:#DDE0FF;font-weight:600;}
[class*="st-key-nx_del_"] button{
  background:transparent;border:1px solid transparent;box-shadow:none;color:var(--muted);
  padding:.2rem;min-height:2rem;width:2rem;
}
[class*="st-key-nx_del_"] button:hover{background:var(--err-soft);color:var(--err);border-color:#F6CACA;}
[class*="st-key-nx_prompt_"] button{
  justify-content:flex-start;text-align:left;height:auto;white-space:normal;padding:.65rem .85rem;
  color:var(--text-2);font-weight:450;line-height:1.35;border-radius:12px;
}

/* ---------- inputs ---------- */
[data-testid="stFileUploaderDropzone"]{
  border:1.5px dashed #C9CEF3;border-radius:12px;background:#FAFAFF;padding:.7rem .75rem;
}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--accent);background:var(--accent-soft);}
[data-testid="stFileUploaderDropzoneInstructions"] span,[data-testid="stFileUploaderDropzoneInstructions"] small{font-size:.74rem;}
[data-testid="stFileUploader"] section button{font-size:.78rem;padding:.25rem .6rem;}
[data-testid="stExpander"]{border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:none;}
[data-testid="stExpander"] summary{font-size:.86rem;font-weight:500;padding:.5rem .75rem;}
[data-testid="stSelectbox"] > div > div,[data-baseweb="select"] > div{border-radius:10px;border-color:var(--border);background:var(--surface);}
[data-testid="stMultiSelect"] label,[data-testid="stToggle"] label{font-size:.82rem;color:var(--text-2);}
[data-baseweb="tag"]{background:var(--accent-soft) !important;color:var(--accent) !important;border-radius:8px !important;}

/* ---------- top bar ---------- */
.nx-top{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.15rem 0 1rem;
  border-bottom:1px solid var(--border);margin-bottom:1.25rem;}
.nx-crumb{display:flex;align-items:center;gap:.5rem;font-size:.9rem;color:var(--muted);min-width:0;}
.nx-crumb b{color:var(--text);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:34ch;}
.nx-crumb .sep{opacity:.5;}
.nx-pills{display:flex;gap:.45rem;flex-wrap:wrap;justify-content:flex-end;}
.nx-pill{display:inline-flex;align-items:center;gap:.4rem;font-size:.76rem;color:var(--text-2);background:var(--surface);
  border:1px solid var(--border);border-radius:999px;padding:.28rem .7rem;box-shadow:var(--shadow-sm);white-space:nowrap;}
.nx-pill.on{color:var(--accent);background:var(--accent-soft);border-color:#DDE0FF;}
.nx-dot{width:7px;height:7px;border-radius:50%;background:var(--muted);}
.nx-dot.ok{background:#10B981;box-shadow:0 0 0 3px rgba(16,185,129,.15);}
.nx-dot.bad{background:#EF4444;box-shadow:0 0 0 3px rgba(239,68,68,.15);}

/* ---------- empty state ---------- */
.nx-hero{text-align:center;padding:2.6rem 0 1.6rem;}
.nx-kicker{display:inline-flex;align-items:center;gap:.45rem;font-size:.7rem;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);background:var(--accent-soft);border:1px solid #DDE0FF;
  border-radius:999px;padding:.32rem .8rem;}
.nx-hero h1{font-family:'Manrope',sans-serif;font-weight:800;font-size:3.5rem;line-height:1.05;margin:1.1rem 0 .55rem;
  background:linear-gradient(90deg,#3F51E8 0%,#7C4DF0 55%,#A855F7 100%);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;color:transparent;padding-bottom:.1em;}
.nx-hero p{font-size:1.1rem;color:var(--text-2);margin:0;}
.nx-hero small{display:block;margin-top:.8rem;color:var(--muted);font-size:.86rem;}
.nx-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.9rem;margin:1.2rem 0 1.4rem;}
.nx-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:1.05rem 1.1rem 1.15rem;
  box-shadow:var(--shadow-sm);transition:box-shadow .18s,transform .18s,border-color .18s;}
.nx-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);border-color:#D6D9F8;}
.nx-card-ic{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;margin-bottom:.8rem;}
.nx-card-ic.a{background:#EDEFFF;color:#4F5BE8;} .nx-card-ic.b{background:#F3EAFE;color:#8B45E0;}
.nx-card-ic.c{background:#E6F6FB;color:#0E86A8;} .nx-card-ic.d{background:#FDEEF3;color:#D6407A;}
.nx-card h4{font-family:'Manrope',sans-serif;font-size:.98rem;font-weight:700;margin:0 0 .3rem;color:var(--text);}
.nx-card p{font-size:.83rem;line-height:1.5;color:var(--text-2);margin:0;}
.nx-try{font-size:.72rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:.4rem 0 .5rem;}

/* ---------- chat ---------- */
[data-testid="stChatMessage"]{
  background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:1rem 1.15rem;
  box-shadow:var(--shadow-sm);gap:.9rem;margin-bottom:.8rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){
  background:linear-gradient(180deg,#F5F6FF 0%,#F8F7FF 100%);border-color:#E2E4FF;box-shadow:none;
}
[data-testid="stChatMessageAvatarUser"]{background:var(--grad) !important;color:#fff !important;border-radius:10px;}
[data-testid="stChatMessageAvatarAssistant"]{background:transparent !important;border-radius:50%;}
[data-testid="stChatMessageAvatarAssistant"] img{border-radius:50%;}
[data-testid="stChatMessageContent"]{font-size:.95rem;line-height:1.68;color:var(--text);min-width:0;}
[data-testid="stChatMessageContent"] p{margin-bottom:.6rem;}
[data-testid="stChatMessageContent"] a{color:var(--accent);}
[data-testid="stChatMessageContent"] pre{background:#F3F4FA !important;border:1px solid var(--border);border-radius:12px;}
[data-testid="stChatMessageContent"] code{font-size:.84rem;}
[data-testid="stChatMessageContent"] table{border-collapse:collapse;width:100%;font-size:.88rem;display:block;overflow-x:auto;}
[data-testid="stChatMessageContent"] th{background:var(--surface-2);text-align:left;font-weight:600;}
[data-testid="stChatMessageContent"] th,[data-testid="stChatMessageContent"] td{border:1px solid var(--border);padding:.45rem .7rem;}
[data-testid="stChatMessageContent"] blockquote{border-left:3px solid var(--accent);color:var(--text-2);}

.nx-meta{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;margin-top:.55rem;}
.nx-badge{display:inline-flex;align-items:center;gap:.35rem;font-size:.72rem;font-weight:600;letter-spacing:.02em;
  padding:.2rem .6rem;border-radius:999px;background:var(--accent-soft);color:var(--accent);box-shadow:var(--shadow-sm);}
.nx-badge.web{background:#E6F6FB;color:#0E7490;border:1px solid #BAE6FD;}
.nx-badge.vision{background:#F3EAFE;color:#7E3AD0;border:1px solid #E9D5FF;}
.nx-badge.doc{background:#EEF2FF;color:#4338CA;border:1px solid #C7D2FE;}
.nx-badge.hybrid{background:#F0FDF4;color:#15803D;border:1px solid #BBF7D0;}
.nx-badge.general{background:#F8FAFC;color:#475569;border:1px solid #E2E8F0;}
.nx-badge.shield-ok{background:#ECFDF5;color:#047857;border:1px solid #A7F3D0;}
.nx-badge.shield-warn{background:#FFFBEB;color:#B45309;border:1px solid #FDE68A;}
.nx-badge.shield-err{background:#FEF2F2;color:#B91C1C;border:1px solid #FECACA;}
.nx-badge.repaired{background:#FAF5FF;color:#6B21A8;border:1px solid #E9D5FF;}

.nx-verify-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:.75rem .9rem;margin-top:.6rem;box-shadow:var(--shadow-sm);}
.nx-metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:.55rem;margin-top:.45rem;}
.nx-metric-item{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:.45rem .6rem;}
.nx-metric-lbl{font-size:.66rem;color:var(--muted);text-transform:uppercase;font-weight:600;letter-spacing:.05em;}
.nx-metric-val{font-size:.9rem;font-weight:700;color:var(--text);margin-top:.15rem;}
.nx-meter{height:5px;background:#E2E8F0;border-radius:999px;margin-top:.3rem;overflow:hidden;}
.nx-meter-fill{height:100%;border-radius:999px;}
.nx-meter-fill.ok{background:#10B981;} .nx-meter-fill.warn{background:#F59E0B;} .nx-meter-fill.err{background:#EF4444;}
.nx-reasoning{font-size:.78rem;color:var(--text-2);background:var(--surface-2);border-left:3px solid var(--accent);border-radius:4px;padding:.4rem .65rem;margin-top:.5rem;}

.nx-sources{margin-top:.8rem;padding-top:.7rem;border-top:1px solid var(--border);}
.nx-src-label{font-size:.68rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem;}
.nx-src-chips{display:flex;flex-wrap:wrap;gap:.4rem;}
.nx-chip{display:inline-flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-2);background:var(--surface-2);
  border:1px solid var(--border);border-radius:9px;padding:.28rem .6rem;max-width:100%;text-decoration:none !important;}
.nx-chip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.nx-chip i{font-style:normal;color:var(--muted);}
a.nx-chip:hover{border-color:#C4C8F5;background:var(--accent-soft);color:var(--accent);}
.nx-chip .nx-i{color:var(--accent);}
.nx-attach{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem;}

.nx-note{display:flex;gap:.6rem;align-items:flex-start;font-size:.86rem;line-height:1.45;border-radius:12px;padding:.7rem .85rem;margin-top:.5rem;}
.nx-note.warn{background:var(--warn-soft);color:var(--warn);} .nx-note.err{background:var(--err-soft);color:#B42323;}
.nx-note.ok{background:var(--ok-soft);color:#047857;}

.nx-loading{display:flex;align-items:center;gap:.7rem;color:var(--text-2);font-size:.92rem;padding:.2rem 0;}
.nx-dots{display:inline-flex;gap:4px;}
.nx-dots i{width:7px;height:7px;border-radius:50%;background:var(--grad);animation:nxb 1.1s infinite ease-in-out;}
.nx-dots i:nth-child(2){animation-delay:.15s;} .nx-dots i:nth-child(3){animation-delay:.3s;}
@keyframes nxb{0%,80%,100%{transform:scale(.55);opacity:.45}40%{transform:scale(1);opacity:1}}
.nx-skel{height:9px;border-radius:6px;margin-top:.55rem;background:linear-gradient(90deg,#ECEEF6 25%,#F6F7FC 50%,#ECEEF6 75%);
  background-size:200% 100%;animation:nxs 1.4s infinite linear;}
@keyframes nxs{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* composer status pills sit right above the input */
.nx-composer-pills{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0 .2rem;}

/* ---------- document cards (sidebar) ---------- */
.nx-doc{display:flex;align-items:center;gap:.65rem;background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:.5rem .65rem;box-shadow:var(--shadow-sm);min-height:2.7rem;}
.nx-doc-ic{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;flex:none;}
.nx-doc-ic.pdf{background:#FEEBEB;color:#DC3B3B;} .nx-doc-ic.word{background:#E8F0FF;color:#3B6FE0;}
.nx-doc-ic.sheet{background:#E6F6EE;color:#12905A;} .nx-doc-ic.img{background:#FFF1DD;color:#D9821A;}
.nx-doc-body{min-width:0;flex:1;}
.nx-doc-name{font-size:.82rem;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.25;}
.nx-doc-meta{display:flex;align-items:center;gap:.4rem;font-size:.7rem;color:var(--muted);margin-top:.12rem;line-height:1.2;}
.nx-st{display:inline-flex;align-items:center;gap:.28rem;font-weight:600;}
.nx-st::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;}
.nx-st.ok{color:var(--ok);} .nx-st.warn{color:var(--warn);} .nx-st.err{color:var(--err);}
.nx-doc.busy{position:relative;overflow:hidden;}
.nx-doc.busy::after{content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(139,92,246,.10),transparent);animation:nxsh 1.3s infinite;}
@keyframes nxsh{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.nx-doc.busy .nx-st{color:var(--accent);}
.nx-src-row{display:flex;align-items:center;justify-content:space-between;font-size:.8rem;color:var(--text-2);
  background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:.45rem .65rem;}

@media (max-width:640px){
  [data-testid="stMainBlockContainer"], .block-container{padding:.8rem 1rem 7rem;}
  [data-testid="stBottomBlockContainer"]{padding:.5rem 1rem 1rem;}
  .nx-hero h1{font-size:2.4rem;} .nx-hero{padding-top:1.4rem;}
  .nx-pills{display:none;}
}
</style>
"""


def inject_styles():
    """Emit the stylesheet on EVERY run.

    Streamlit drops elements that a run does not re-emit, so a "load once"
    guard makes the theme disappear after the first interaction.
    """
    if hasattr(st, "html"):
        st.html(CSS)
    else:  # very old Streamlit
        st.markdown(CSS, unsafe_allow_html=True)
