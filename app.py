"""
═══════════════════════════════════════════════════════════════
 PRAVA KOLEVKA v7.0 — Modernizovani Pravni AI za Kosovo
 Refaktorizovan kod, poboljšan UI, priprema za AI optimizaciju
═══════════════════════════════════════════════════════════════
"""

# ═══════════════════════════════════════════════════════════════
#  IMPORTI
# ═══════════════════════════════════════════════════════════════

try:
    from supabase_db import (
        sb_save_law_with_articles, sb_get_laws_summary, sb_get_articles,
        sb_delete_law, sb_update_law, sb_delete_articles, sb_search_articles,
        sb_search_articles_by_number, sb_get_law_basic,
        sb_get_all_articles_with_laws, sb_get_all_laws, sb_find_laws_by_name,
        sb_count_articles, sb_find_parent_law,
        sb_get_user_by_email, sb_create_user, sb_update_user,
        sb_get_all_users, sb_create_case, sb_get_user_cases, sb_delete_case,
        sb_get_case_messages, sb_save_case_message, sb_add_case_document,
        sb_get_case_documents, sb_get_document_text, sb_delete_case_document,
        sb_save_submission, sb_get_case_submissions, sb_delete_submission,
        sb_save_payment, sb_get_payments, sb_log_action,
        sb_search_articles_multi, sb_get_first_articles,
        sb_get_law_ids_by_area, sb_test_connection,
    )
    SUPABASE_READY = True
except ImportError:
    SUPABASE_READY = False
    def dummy(*args, **kwargs): return None
    for fn in ['sb_get_user_by_email', 'sb_create_user', 'sb_update_user',
               'sb_get_all_users', 'sb_create_case', 'sb_get_user_cases',
               'sb_delete_case', 'sb_get_case_messages', 'sb_save_case_message',
               'sb_add_case_document', 'sb_get_case_documents',
               'sb_get_document_text', 'sb_delete_case_document',
               'sb_save_submission', 'sb_get_case_submissions',
               'sb_delete_submission', 'sb_save_payment', 'sb_get_payments',
               'sb_log_action']:
        globals()[fn] = dummy

import streamlit as st
import os, re, io, json, sqlite3, hashlib, secrets, base64
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
from contextlib import contextmanager

from pypdf import PdfReader
from PIL import Image
import openai
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from docx import Document as DocxDocument
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

try:
    import stripe as stripe_lib
    STRIPE_AVAILABLE = True
except ImportError:
    stripe_lib = None
    STRIPE_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
#  KONFIGURACIJA I BOJE
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Prava Kolevka | Pravni AI za Kosovo",
    page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

def get_secret(key, default=""):
    try: return st.secrets[key]
    except: return os.getenv(key, default)

OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
STRIPE_SECRET_KEY = get_secret("STRIPE_SECRET_KEY")
STRIPE_SUCCESS_URL = get_secret("STRIPE_SUCCESS_URL", "https://pravakolevka.rs/success")
STRIPE_CANCEL_URL = get_secret("STRIPE_CANCEL_URL", "https://pravakolevka.rs/cancel")

# Tvoje originalne boje - zadržane
PRIMARY = "#13294B"
PRIMARY_DARK = "#0F1F38"
ACCENT = "#C6363C"
ACCENT_DARK = "#A61E2A"
SURFACE = "#F7F8FA"
CARD_BG = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4B5563"
SUCCESS_C = "#059669"
ERROR_C = "#DC2626"
WARNING_C = "#D97706"

# ═══════════════════════════════════════════════════════════════
#  MODERNI CSS STILOVI
# ═══════════════════════════════════════════════════════════════

MODERN_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');

* {{ font-family: 'Inter', sans-serif !important; }}

/* Globalno */
.stApp {{ background: {SURFACE} !important; }}
#MainMenu, footer, header {{ visibility: hidden; }}
[data-testid="stSidebar"] {{ display: none !important; }}

/* Login box - moderniji izgled */
.login-container {{ 
    max-width: 440px; 
    margin: 10vh auto; 
    padding: 3rem 2.5rem; 
    background: {CARD_BG}; 
    border-radius: 20px; 
    box-shadow: 0 8px 32px rgba(19, 41, 75, 0.12);
    border: 1px solid {BORDER};
}}
.login-header {{ text-align: center; margin-bottom: 2.5rem; }}
.login-header h1 {{ 
    font-family: 'Playfair Display', serif !important; 
    font-size: 2rem; 
    margin: 1rem 0 0.5rem;
    color: {PRIMARY};
}}
.login-header .accent {{ color: {ACCENT}; }}
.login-header p {{ color: {TEXT_SECONDARY}; font-size: 0.9rem; }}

/* Top bar - cleaner */
.top-bar {{ 
    background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
    color: white; 
    padding: 1rem 2rem; 
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    border-radius: 0 0 16px 16px; 
    margin: -1rem -1rem 2rem -1rem; 
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}}
.top-bar h2 {{ 
    font-family: 'Playfair Display', serif !important; 
    margin: 0; 
    font-size: 1.4rem;
    display: flex; 
    align-items: center; 
    gap: 8px;
}}
.top-bar .accent {{ color: #FF6B6B; }}

/* Badge-ovi */
.badge {{ 
    background: rgba(255,255,255,0.15); 
    padding: 4px 12px; 
    border-radius: 8px; 
    font-weight: 500; 
    font-size: 0.8rem;
    backdrop-filter: blur(4px);
}}
.badge-active {{ background: {ACCENT}; color: white; }}
.badge-warn {{ background: {WARNING_C}; color: white; }}
.badge-err {{ background: {ERROR_C}; color: white; }}

/* Kartice - modernije */
.pk-card {{ 
    background: {CARD_BG}; 
    border-radius: 16px; 
    padding: 2rem; 
    margin: 1rem 0; 
    border: 1px solid {BORDER};
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    transition: all 0.3s ease;
}}
.pk-card:hover {{ 
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    transform: translateY(-2px);
}}
.pk-card-accent {{ 
    background: {CARD_BG}; 
    border-radius: 16px; 
    padding: 2rem; 
    margin: 1rem 0; 
    border-left: 4px solid {ACCENT};
    border: 1px solid {BORDER};
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}}
.pk-card h3, .pk-card-accent h3 {{ 
    font-family: 'Playfair Display', serif !important; 
    color: {PRIMARY}; 
    margin-top: 0;
    font-size: 1.3rem;
}}

/* Dugmići */
.stButton > button {{ 
    border-radius: 10px !important; 
    font-weight: 600 !important; 
    border: none !important; 
    background: {PRIMARY} !important; 
    color: white !important; 
    padding: 0.6rem 1.5rem !important;
    transition: all 0.2s !important;
    box-shadow: 0 2px 8px rgba(19, 41, 75, 0.2);
}}
.stButton > button:hover {{ 
    background: {PRIMARY_DARK} !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(19, 41, 75, 0.3);
}}

/* Inputi */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{ 
    border-radius: 10px !important; 
    border: 1.5px solid {BORDER} !important; 
    padding: 0.7rem !important;
    font-size: 0.95rem !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{ 
    border-color: {ACCENT} !important; 
    box-shadow: 0 0 0 3px rgba(198, 54, 60, 0.1) !important;
}}

/* Tabovi - cleaner */
.stTabs [data-baseweb="tab-list"] {{ 
    gap: 0; 
    background: transparent; 
    border-bottom: 2px solid {BORDER}; 
    padding: 0; 
}}
.stTabs [data-baseweb="tab"] {{ 
    border-radius: 0 !important; 
    font-weight: 500 !important; 
    color: {TEXT_SECONDARY} !important; 
    padding: 0.75rem 1.5rem !important; 
    background: transparent !important;
    transition: all 0.2s !important;
}}
.stTabs [aria-selected="true"] {{ 
    color: {PRIMARY} !important; 
    background: transparent !important; 
    border-bottom: 3px solid {ACCENT} !important; 
    font-weight: 600 !important;
}}

/* Chat poruke */
[data-testid="stChatMessage"] {{ 
    border-radius: 16px !important; 
    padding: 1rem 1.25rem !important;
    margin: 0.75rem 0 !important;
}}

/* Expander */
[data-testid="stExpander"] {{ 
    border: 1px solid {BORDER} !important; 
    border-radius: 12px !important;
    overflow: hidden;
}}

/* File uploader */
.stFileUploader > div {{ 
    border-radius: 12px !important; 
    border: 2px dashed {BORDER} !important; 
    background: {SURFACE} !important;
    padding: 1.5rem !important;
}}

/* Responsive */
@media (max-width: 768px) {{ 
    .top-bar {{ padding: 0.75rem 1rem; flex-direction: column; gap: 1rem; }}
    .top-bar h2 {{ font-size: 1.2rem; }}
    .login-container {{ margin: 5vh 1rem; padding: 2rem 1.5rem; }}
}}
</style>
"""

# ═══════════════════════════════════════════════════════════════
#  LOGO SVG
# ═══════════════════════════════════════════════════════════════

LOGO_SVG = f'''
<svg width="48" height="48" viewBox="0 0 36 36" fill="none">
    <line x1="18" y1="4" x2="18" y2="28" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <line x1="6" y1="12" x2="30" y2="12" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <circle cx="18" cy="4" r="2.5" fill="{ACCENT}"/>
    <path d="M6 12 L3 22 H9 Z" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M30 12 L27 22 H33 Z" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
    <rect x="13" y="28" width="10" height="3" rx="1.5" fill="white"/>
</svg>
'''

DISCLAIMER_TEXT = """
<strong>⚠️ Odricanje od odgovornosti:</strong> 
Ovaj AI sistem pruža informativne pravne informacije i ne zamenjuje profesionalnog pravnika. 
Uvek konsultujte licenciranog advokata za konkretne pravne savete.
"""

# ═══════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "logged_in": False, "current_user": None,
        "law_vs": None, "law_vs_version": "",
        "login_time": None, "active_case_id": None,
        "case_doc_vs": None, "case_doc_vs_id": None,
        "preview_articles": None, "preview_warnings": None,
        "preview_meta": None, "current_case": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ═══════════════════════════════════════════════════════════════
#  POMOĆNE FUNKCIJE
# ═══════════════════════════════════════════════════════════════

def safe_text(text):
    if not text: return ""
    return str(text).strip()

def anonymize_for_ai(text):
    patterns = [
        (r'\b\d{13}\b', '[JMBG REDIGOVAN]'),
        (r'\b\d{8,10}\b', '[BR. LIČNE KARTE REDIGOVAN]'),
        (r'[A-Z]{2}\d{6,8}', '[PASSPORT REDIGOVAN]'),
        (r'\b\d{4}-\d{4}-\d{4}\b', '[RAČUN REDIGOVAN]'),
    ]
    for pat, repl in patterns:
        text = re.sub(pat, repl, text)
    return text

def safe_html(text):
    if not text: return ""
    t = str(text)
    t = t.replace("&", "&amp;").replace("<", "&lt;")
    t = t.replace(">", "&gt;").replace('"', "&quot;")
    return t

def clean_text(text):
    if not text: return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def remove_toc(text):
    lines = text.split('\n')
    filtered = []
    in_toc = False
    for line in lines:
        if 'SADRŽAJ' in line or 'SADRZAJ' in line:
            in_toc = True
            continue
        if in_toc and re.match(r'^\s*\d+\.\s+', line):
            continue
        if in_toc and line.strip() == '':
            continue
        if in_toc and re.match(r'^\s*GLAVA\s', line, re.I):
            in_toc = False
        filtered.append(line)
    return '\n'.join(filtered)

# ═══════════════════════════════════════════════════════════════
#  KREIRANJE/VERIFIKACIJA LOZINKE
# ═══════════════════════════════════════════════════════════════

def create_password_hash(password):
    if BCRYPT_AVAILABLE:
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8'), base64.b64encode(salt).decode('utf-8')
    else:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hashed, salt

def verify_password(password, stored_hash, stored_salt):
    if BCRYPT_AVAILABLE:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except: return False
    else:
        computed = hashlib.sha256((password + stored_salt).encode()).hexdigest()
        return secrets.compare_digest(computed, stored_hash)

def authenticate_user(email, password):
    email = email.strip().lower()
    user = sb_get_user_by_email(email) if SUPABASE_READY else None
    
    if not user:
        try:
            with get_db() as conn:
                row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if row: user = dict(row)
        except: pass
    
    if not user: return None
    
    if verify_password(password, user['password_hash'], user.get('password_salt', '')):
        if user.get('status') == 'suspended': return None
        return user
    return None

# ═══════════════════════════════════════════════════════════════
#  SQLITE DATABASE (FALLBACK)
# ═══════════════════════════════════════════════════════════════

@contextmanager
def get_db():
    conn = sqlite3.connect("prava_kolevka.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT,
            password_salt TEXT, full_name TEXT, role TEXT DEFAULT 'user',
            plan TEXT DEFAULT 'free', subscription_status TEXT DEFAULT 'active',
            subscription_end TEXT, created_at TEXT, last_login TEXT, status TEXT DEFAULT 'active')''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, user_id TEXT, title TEXT, 
            created_at TEXT, status TEXT DEFAULT 'active',
            FOREIGN KEY(user_id) REFERENCES users(id))''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, case_id TEXT, role TEXT, 
            content TEXT, timestamp TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(id))''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, case_id TEXT, filename TEXT, 
            file_data BLOB, uploaded_at TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(id))''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY, case_id TEXT, user_id TEXT,
            submission_type TEXT, court TEXT, content TEXT,
            pdf_data BLOB, created_at TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(id),
            FOREIGN KEY(user_id) REFERENCES users(id))''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY, user_id TEXT, amount REAL,
            currency TEXT, status TEXT, stripe_id TEXT,
            created_at TEXT, FOREIGN KEY(user_id) REFERENCES users(id))''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY, user_id TEXT, action TEXT,
            details TEXT, timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id))''')
        
        admin_check = conn.execute("SELECT 1 FROM users WHERE email='admin@pravakolevka.rs'").fetchone()
        if not admin_check:
            h, s = create_password_hash("Admin123!")
            conn.execute("""INSERT INTO users (id, email, password_hash, password_salt, full_name, role)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (secrets.token_hex(16), 'admin@pravakolevka.rs', h, s, 'Administrator', 'admin'))

# ═══════════════════════════════════════════════════════════════
#  LOGIRANJE AKCIJA
# ═══════════════════════════════════════════════════════════════

def log_action(uid, action, details=""):
    try:
        sb_log_action(uid, action, details)
    except:
        try:
            with get_db() as conn:
                conn.execute("INSERT INTO actions (id, user_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (secrets.token_hex(16), uid, action, details, datetime.now().isoformat()))
        except: pass

# ═══════════════════════════════════════════════════════════════
#  RENDER FUNKCIJE - UI
# ═══════════════════════════════════════════════════════════════

def render_footer():
    st.markdown(f"""
    <div style="text-align: center; margin-top: 3rem; padding: 2rem 1rem; 
                border-top: 1px solid {BORDER}; color: {TEXT_SECONDARY}; 
                font-size: 0.8rem; background: {CARD_BG}; 
                border-radius: 12px;">
        <p style="margin: 0 0 0.5rem;"><strong>Prava Kolevka v7.0</strong> | Pravni AI za Kosovo ⚖️</p>
        <p style="margin: 0; opacity: 0.8;">{DISCLAIMER_TEXT}</p>
    </div>
    """, unsafe_allow_html=True)

def render_login():
    st.markdown(f"""
    <div class="login-container">
        <div class="login-header">
            <div style="width: 80px; height: 80px; background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_DARK});
                        border-radius: 20px; margin: 0 auto 1.5rem; display: flex; 
                        align-items: center; justify-content: center; 
                        box-shadow: 0 8px 24px rgba(19, 41, 75, 0.2);">
                {LOGO_SVG}
            </div>
            <h1><span class="brand-prava">Prava</span> <span class="accent">Kolevka</span></h1>
            <p>Moderni pravni AI asistent za Kosovo</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email adresa", placeholder="korisnik@primer.com")
            password = st.text_input("Lozinka", type="password", placeholder="••••••••")
            submit = st.form_submit_button("🔐 Prijavi se", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Unesite email i lozinku.")
                else:
                    user = authenticate_user(email, password)
                    if user:
                        st.session_state.current_user = user
                        st.session_state.logged_in = True
                        st.session_state.login_time = datetime.now()
                        log_action(user["id"], "login")
                        st.rerun()
                    else:
                        st.error("Neispravan email ili lozinka.")
        
        st.markdown("---")
        st.info("🔒 Sigurna platforma za pravne profesionalce • Automatska odjava nakon 8h")
    
    render_footer()

def do_logout():
    uid = st.session_state.get("current_user", {}).get("id")
    if uid: log_action(uid, "logout")
    for k in list(st.session_state.keys()): del st.session_state[k]
    init_session()

def check_session_timeout():
    lt = st.session_state.get("login_time")
    if not lt: return False
    if isinstance(lt, str): lt = datetime.fromisoformat(lt)
    return datetime.now() - lt > timedelta(hours=8)

# ═══════════════════════════════════════════════════════════════
#  GLAVNA APLIKACIJA
# ═══════════════════════════════════════════════════════════════

def main():
    st.markdown(MODERN_CSS, unsafe_allow_html=True)
    init_database()
    
    if not st.session_state.get("logged_in", False):
        render_login()
        return
    
    if check_session_timeout():
        do_logout()
        st.warning("Automatska odjava nakon 8 sati iz bezbednosnih razloga.")
        render_login()
        return
    
    user = st.session_state.get("current_user")
    if not user:
        st.session_state.logged_in = False
        st.rerun()
        return
    
    # Refresh user data
    if SUPABASE_READY:
        try:
            fresh = sb_get_user_by_email(user["email"])
            if fresh: st.session_state.current_user = fresh
        except: pass
    
    current_user = st.session_state.current_user
    
    if current_user.get("role") == "admin":
        render_admin_panel()
    else:
        render_user_panel()

def render_admin_panel():
    st.title("🛡️ Admin Panel")
    st.sidebar.title("Navigacija")
    
    menu = st.sidebar.radio(
        "Odaberite sekciju",
        ["📊 Dashboard", "⚖️ Zakoni", "👥 Korisnici", "💰 Plaćanja", "⚙️ Podešavanja"],
        label_visibility="collapsed"
    )
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_DARK});
                color: white; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem;">
        <h3 style="margin: 0; font-family: 'Playfair Display', serif;">Administratorski panel</h3>
        <p style="margin: 0.5rem 0 0; opacity: 0.9;">Trenutno ulogovani: {safe_html(st.session_state.current_user.get('full_name', 'Admin'))}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if menu == "📊 Dashboard":
        st.info("Dashboard funkcionalnosti u izradi...")
    elif menu == "⚖️ Zakoni":
        st.info("Upravljanje zakonima u izradi...")
    elif menu == "👥 Korisnici":
        st.info("Upravljanje korisnicima u izradi...")
    elif menu == "💰 Plaćanja":
        st.info("Pregled plaćanja u izradi...")
    elif menu == "⚙️ Podešavanja":
        st.info("Sistemska podešavanja u izradi...")
    
    render_footer()

def render_user_panel():
    user = st.session_state.current_user
    
    st.markdown(f"""
    <div class="top-bar">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 40px; height: 40px; background: rgba(255,255,255,0.2);
                        border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                {LOGO_SVG}
            </div>
            <h2>Prava <span class="accent">Kolevka</span></h2>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <span class="badge">{safe_html(user.get('plan', 'free').upper())}</span>
            <span class="badge badge-active">Aktivan</span>
            <span class="badge">{safe_html(user.get('full_name', 'Korisnik'))}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not OPENAI_API_KEY:
        st.error("⚠️ OpenAI API ključ nije konfigurisan.")
        return
    
    tabs = st.tabs([
        "📁 Predmeti",
        "🔍 Pretraga zakona",
        "🌐 Prevodilac SR↔AL",
        "🏛️ Sudska nadležnost",
        "💳 Pretplata"
    ])
    
    with tabs[0]:
        render_tab_predmeti()
    with tabs[1]:
        render_tab_pretraga()
    with tabs[2]:
        render_tab_prevodilac()
    with tabs[3]:
        render_tab_nadleznost()
    with tabs[4]:
        render_tab_pretplata()
    
    render_footer()
    
    if st.button("🚪 Odjavi se"):
        do_logout()
        st.rerun()

# ═══════════════════════════════════════════════════════════════
#  TABOVI - KORISNIČKI INTERFEJS
# ═══════════════════════════════════════════════════════════════

def render_tab_predmeti():
    user = st.session_state.current_user
    
    st.markdown(f"""
    <div class="pk-card">
        <h3>📁 Moji predmeti</h3>
        <p style="color: {TEXT_SECONDARY}; margin: 0;">Organizujte i pratite svoje pravne predmete na jednom mestu</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_title = st.text_input("Naziv novog predmeta", 
                                 placeholder="npr. Parnica br. 123/2024 - Naknada štete",
                                 label_visibility="collapsed")
    with col2:
        if st.button("➕ Kreiraj", use_container_width=True):
            if new_title.strip():
                try:
                    case_id = secrets.token_hex(16)
                    sb_create_case(case_id, user["id"], new_title.strip())
                    st.success("Predmet uspešno kreiran!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Greška: {str(e)}")
    
    st.markdown("---")
    
    try:
        cases = sb_get_user_cases(user["id"]) if SUPABASE_READY else []
    except:
        cases = []
    
    if not cases:
        st.info("📭 Nemate kreiranih predmeta. Kreirajte svoj prvi predmet!")
    else:
        for case in cases:
            with st.expander(f"📂 {case.get('title', 'Predmet')} • {case.get('created_at', '')[:10]}"):
                st.write(f"**ID:** `{case.get('id', 'N/A')[:12]}...`")
                st.write(f"**Status:** {'✅ Aktivan' if case.get('status') == 'active' else '⏸️ Arhiviran'}")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Otvori predmet", key=f"open_{case['id']}", use_container_width=True):
                        st.session_state.current_case = case
                        st.success("Predmet otvoren!")
                with c2:
                    if st.button("🗑️ Obriši", key=f"del_{case['id']}", type="secondary", use_container_width=True):
                        try:
                            sb_delete_case(case['id'], user['id'])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Greška: {str(e)}")
                with c3:
                    st.write("")

def render_tab_pretraga():
    st.markdown(f"""
    <div class="pk-card">
        <h3>🔍 Pretraga zakona i članova</h3>
        <p style="color: {TEXT_SECONDARY}; margin: 0;">Pretražujte celu bazu zakona Republike Kosovo</p>
    </div>
    """, unsafe_allow_html=True)
    
    query = st.text_input("", 
                         placeholder="Unesite pojam za pretragu (npr. naknada štete, radni odnos, zakup...)",
                         label_visibility="collapsed")
    
    if query:
        with st.spinner("🔎 Pretražujem bazu zakona..."):
            # Ovde će biti implementirana prava pretraga
            st.info("Funkcionalnost pretrage se implementira...")
            st.write(f"Upit: **{query}**")

def render_tab_prevodilac():
    st.markdown(f"""
    <div class="pk-card">
        <h3>🌐 Prevodilac Srpski ↔ Albanski</h3>
        <p style="color: {TEXT_SECONDARY}; margin: 0;">Profesionalni prevod pravnih tekstova</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        source = st.text_area("Tekst za prevod", height=250,
                             placeholder="Unesite tekst na srpskom ili albanskom jeziku...")
        lang = st.radio("Jezik izvornog teksta:", ["Srpski → Albanski", "Albanski → Srpski"])
    
    with col2:
        st.markdown("**Prevod:**")
        if source and st.button("🔄 Prevedi sada"):
            with st.spinner("Prevodim..."):
                # Ovde će biti implementiran prevod
                st.text_area("", value="[Prevod će se pojaviti ovde]", height=250, label_visibility="collapsed")

def render_tab_nadleznost():
    st.markdown(f"""
    <div class="pk-card">
        <h3>🏛️ Određivanje sudske nadležnosti</h3>
        <p style="color: {TEXT_SECONDARY}; margin: 0;">AI analiza za određivanje nadležnog suda</p>
    </div>
    """, unsafe_allow_html=True)
    
    desc = st.text_area("Detaljan opis slučaja", height=200,
                       placeholder="Opišite slučaj što detaljnije da bismo odredili nadležni sud...")
    
    sub_type = st.selectbox("Vrsta podneska:", 
                           ["Tužba", "Zahtev", "Molba", "Žalba", "Predlog", "Drugo"])
    
    if st.button("⚖️ Utvrdi nadležnost"):
        if desc.strip():
            with st.spinner("AI analizira slučaj..."):
                # Ovde će biti implementirana AI analiza
                st.success("Analiza u toku...")
        else:
            st.warning("Unesite opis slučaja.")

def render_tab_pretplata():
    user = st.session_state.current_user
    
    st.markdown(f"""
    <div class="pk-card-accent">
        <h3>💳 Upravljajte pretplatom</h3>
        <p style="color: {TEXT_SECONDARY}; margin: 0;">Odaberite plan koji najbolje odgovara vašim potrebama</p>
    </div>
    """, unsafe_allow_html=True)
    
    current_plan = user.get('plan', 'free').upper()
    st.info(f"Trenutni plan: **{current_plan}**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        ### 🆓 Free
        - Osnovne funkcije
        - 10 upita mesečno
        - Email podrška
        """)
        if current_plan == "FREE":
            st.button("Trenutni plan", disabled=True, use_container_width=True)
        else:
            st.button("Odaberi Free", use_container_width=True)
    
    with col2:
        st.markdown(f"""
        ### ⭐ Basic - €29/mes
        - 100 upita mesečno
        - Pretraga zakona
        - Prioritetna podrška
        """)
        if current_plan == "BASIC":
            st.button("Trenutni plan", disabled=True, use_container_width=True)
        else:
            if st.button("Nadogradi na Basic", use_container_width=True):
                st.info("Stripe integracija u izradi...")
    
    with col3:
        st.markdown(f"""
        ### 🚀 Pro - €79/mes
        - Neograničeni upiti
        - AI podnesci
        - 24/7 podrška
        """)
        if current_plan == "PRO":
            st.button("Trenutni plan", disabled=True, use_container_width=True)
        else:
            if st.button("Nadogradi na Pro", use_container_width=True):
                st.info("Stripe integracija u izradi...")

# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
