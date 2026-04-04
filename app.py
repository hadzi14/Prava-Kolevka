"""
═══════════════════════════════════════════════════════════════
 PRAVA KOLEVKA v6.2 — Pravni AI za Kosovo
 UI fix, disclaimer, čist prikaz
═══════════════════════════════════════════════════════════════
"""
try:
    from supabase_db import (
        sb_save_law_with_articles,
        sb_get_laws_summary,
        sb_get_articles,
        sb_delete_law,
        sb_update_law,
        sb_delete_articles,
        sb_search_articles,
        sb_search_articles_by_number,
        sb_get_law_basic,
        sb_get_all_articles_with_laws,
        sb_get_all_laws,
        sb_find_laws_by_name,
        sb_count_articles,
        sb_find_parent_law,
    )
    SUPABASE_READY = True
except ImportError:
    SUPABASE_READY = False
    SUPABASE_READY = False

try:
    from supabase_db import (
        sb_search_articles_multi,
        sb_get_first_articles,
        sb_get_law_ids_by_area,
        sb_test_connection,
    )
except ImportError:
    sb_search_articles_multi = None
    sb_get_first_articles = None
    sb_get_law_ids_by_area = None
    sb_test_connection = None
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

st.set_page_config(
    page_title="Prava Kolevka | Pravni AI za Kosovo",
    page_icon="⚖️", layout="wide",
    initial_sidebar_state="collapsed")


def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
ADMIN_EMAIL = get_secret("ADMIN_EMAIL", "admin@pravakolevka.rs")
ADMIN_DEFAULT_PASSWORD = get_secret(
    "ADMIN_PASSWORD", "PravaKolevka2024!")
SESSION_TIMEOUT_MINUTES = 480

STRIPE_SECRET_KEY = get_secret("STRIPE_SECRET_KEY")
STRIPE_SUCCESS_URL = get_secret(
    "STRIPE_SUCCESS_URL", "https://pravakolevka.rs/success")
STRIPE_CANCEL_URL = get_secret(
    "STRIPE_CANCEL_URL", "https://pravakolevka.rs/cancel")

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

SCALE_SVG_LOGIN = (
    f'<div style="width:64px;height:64px;'
    f'background:{PRIMARY};border-radius:16px;'
    f'margin:0 auto 1rem;display:flex;'
    f'align-items:center;justify-content:center;">'
    f'<svg width="36" height="36" viewBox="0 0 36 36" fill="none">'
    f'<line x1="18" y1="4" x2="18" y2="28" stroke="white" stroke-width="2" stroke-linecap="round"/>'
    f'<line x1="6" y1="12" x2="30" y2="12" stroke="white" stroke-width="2" stroke-linecap="round"/>'
    f'<circle cx="18" cy="4" r="2.5" fill="{ACCENT}"/>'
    f'<path d="M6 12 L3 22 H9 Z" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>'
    f'<path d="M30 12 L27 22 H33 Z" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>'
    f'<rect x="13" y="28" width="10" height="3" rx="1.5" fill="white"/>'
    f'</svg></div>')

SCALE_SVG_HEADER = (
    f'<svg width="24" height="24" viewBox="0 0 36 36" fill="none" style="vertical-align:middle;margin-right:6px;">'
    f'<line x1="18" y1="4" x2="18" y2="28" stroke="white" stroke-width="2" stroke-linecap="round"/>'
    f'<line x1="6" y1="12" x2="30" y2="12" stroke="white" stroke-width="2" stroke-linecap="round"/>'
    f'<circle cx="18" cy="4" r="2.5" fill="{ACCENT}"/>'
    f'<path d="M6 12 L3 22 H9 Z" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>'
    f'<path d="M30 12 L27 22 H33 Z" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>'
    f'<rect x="13" y="28" width="10" height="3" rx="1.5" fill="white"/>'
    f'</svg>')

DISCLAIMER_TEXT = (
    "Prava Kolevka je AI pomoćni alat za pravnu pretragu"
    " i rad sa izvorima prava. Ne predstavlja advokatsko"
    " zastupanje niti konačno pravno mišljenje.")

PLANS = {
    "obican": {
        "name": "Običan paket", "price": 19,
        "max_users": 1, "icon": "📦",
        "stripe_price": "price_obican_PLACEHOLDER"},
    "bolji": {
        "name": "Bolji paket", "price": 29,
        "max_users": 5, "icon": "⭐",
        "stripe_price": "price_bolji_PLACEHOLDER"},
    "dogovor": {
        "name": "Paket po dogovoru", "price": 0,
        "max_users": 999, "icon": "💎",
        "stripe_price": ""},
    "enterprise": {
        "name": "Enterprise", "price": 0,
        "max_users": 999, "icon": "🔧",
        "stripe_price": ""},
}
GRACE_PERIOD_DAYS = 3
LANG_NAMES = {
    "sr": "Srpski", "al": "Albanski", "en": "Engleski"}

HIERARCHY_LEVELS = {
    1: {"name": "Ustav", "icon": "👑", "weight": 15},
    2: {"name": "Međunarodni sporazum", "icon": "🌍",
        "weight": 10},
    3: {"name": "Zakon", "icon": "📜", "weight": 5},
    4: {"name": "Podzakonski akt", "icon": "📋",
        "weight": 2},
    5: {"name": "Opštinski propis", "icon": "🏘️",
        "weight": 0},
}

LEGAL_AREAS = [
    "Ustavno pravo", "Krivično pravo",
    "Krivični postupak", "Građansko pravo",
    "Parnični postupak", "Upravno pravo",
    "Radno pravo", "Porodično pravo",
    "Prekršajno pravo", "Pravosuđe",
    "Tužilaštvo", "Advokatura",
    "Policijsko pravo", "Obligaciono pravo",
    "Imovinsko pravo", "Ostalo",
]

AREA_KEYWORDS = {
    "Krivično pravo": [
        "krivičn", "kazna", "delo", "krađa",
        "ubistvo", "prevara", "nasilj", "pretnja",
        "korupcij", "zatvor", "umišljaj", "nehat",
        "nužna odbrana", "krivic", "zlocin",
        "krivično delo", "učinilac", "saučesni"],
    "Krivični postupak": [
        "postupak", "pritvor", "hapšenj", "istrag",
        "optužnic", "presud", "žalb", "dokaz",
        "branilac", "okrivljeni", "tužilac",
        "krivični postupak", "glavni pretres",
        "optuženi", "osumnjičen"],
    "Građansko pravo": [
        "obligacij", "ugovor", "šteta", "naknada",
        "odgovornost", "hipoteka", "zastarelost",
        "dug", "poverilac", "dužnik", "naknada štete"],
    "Obligaciono pravo": [
        "obligacij", "ugovor", "šteta", "naknada",
        "odgovornost", "dug", "poverilac", "dužnik",
        "naknada štete", "raskid ugovora",
        "ispunjenje", "zakup"],
    "Parnični postupak": [
        "parnič", "tužba", "prvostepen", "revizija",
        "izvršenje", "presuda", "rešenje", "parnica",
        "tužilac", "tuženi", "parnični"],
    "Porodično pravo": [
        "brak", "razvod", "alimentacij",
        "starateljstv", "dete", "deca", "porodičn",
        "suprug", "izdržavanje", "roditeljsk"],
    "Radno pravo": [
        "rad", "zaposlen", "otkaz", "plata",
        "ugovor o radu", "sindikat", "penzij",
        "poslodavac", "radnik", "zarada",
        "radni odnos", "zaposlenje", "radno mesto",
        "neisplaćen", "otpremnina", "odmor",
        "prekovremeni", "radni staž", "mobbing",
        "mobbing", "diskriminacij", "zapošljavanje",
        "kolektivni ugovor", "štrajk",
        "radno vreme", "zaradu", "platu",
        "plate", "zarade", "radnog odnosa",
        "zaposlenog", "poslodavca", "otkazu"],
    "Upravno pravo": [
        "upravn", "organ", "inspekcij", "dozvol",
        "upravni postupak", "upravni spor",
        "rešenje organa"],
    "Prekršajno pravo": [
        "prekršaj", "novčana kazna", "mandatna",
        "prekršajn"],
    "Ustavno pravo": [
        "ustav", "ustavni", "osnovna prava",
        "ljudska prava", "slobode", "ustavni sud",
        "ustavna žalba"],
    "Imovinsko pravo": [
        "imovina", "svojina", "posed", "vlasništvo",
        "katastar", "nepokretnost", "pravo svojine",
        "uzurpacija", "eksproprijacija"],
}

AREA_KEY_LAWS = {
    "Radno pravo": {
        "laws": ["zakon o radu", "zor"],
        "label": "Zakon o radu",
        "incompatible": [
            "Krivično pravo",
            "Krivični postupak",
            "Prekršajno pravo"],
    },
    "Krivično pravo": {
        "laws": ["krivični zakonik", "kz",
                 "krivicni zakonik"],
        "label": "Krivični zakonik",
        "incompatible": [
            "Radno pravo", "Porodično pravo",
            "Parnični postupak"],
    },
    "Krivični postupak": {
        "laws": ["zakonik o krivičnom postupku",
                 "zakon o krivičnom postupku",
                 "zkp", "zkpk"],
        "label": "Zakonik o krivičnom postupku",
        "incompatible": [
            "Radno pravo", "Porodično pravo",
            "Parnični postupak"],
    },
    "Građansko pravo": {
        "laws": ["zakon o obligacionim odnosima",
                 "zoo"],
        "label": "Zakon o obligacionim odnosima",
        "incompatible": [
            "Krivično pravo",
            "Krivični postupak"],
    },
    "Obligaciono pravo": {
        "laws": ["zakon o obligacionim odnosima",
                 "zoo"],
        "label": "Zakon o obligacionim odnosima",
        "incompatible": [
            "Krivično pravo",
            "Krivični postupak"],
    },
    "Parnični postupak": {
        "laws": ["zakon o parničnom postupku",
                 "zpp", "zppk"],
        "label": "Zakon o parničnom postupku",
        "incompatible": [
            "Krivični postupak"],
    },
    "Porodično pravo": {
        "laws": ["porodični zakon", "pz"],
        "label": "Porodični zakon",
        "incompatible": [
            "Krivično pravo",
            "Krivični postupak"],
    },
    "Upravno pravo": {
        "laws": ["zakon o upravnom postupku",
                 "zup"],
        "label": "Zakon o upravnom postupku",
        "incompatible": [],
    },
    "Ustavno pravo": {
        "laws": ["ustav", "ustav kosova"],
        "label": "Ustav Kosova",
        "incompatible": [],
    },
}
SCOPE_KEYWORDS = [
    "cilj", "delokrug", "oblast primene",
    "predmet", "šta uređuje", "sta uredjuje",
    "šta reguliše", "sta regulise",
    "definicij", "pojmov", "značenje",
    "primena zakona", "oblast zakona",
    "svrha", "opšte odredbe", "opste odredbe",
    "osnovna načela", "osnovna nacela",
]

IRRELEVANT_PATTERNS = {
    "Radno pravo": [
        "prodaja po uzorku", "predugovor",
        "punomoćje", "punomocje", "oglas",
        "poklonu", "poklon", "testament",
        "nasledj", "menic", "zaloga",
        "skladište", "skladiste", "prevoz robe",
        "osiguranje imovine", "lizing",
        "komisioni", "posredovanje u prometu",
        "turistički", "turisticki",
    ],
    "Krivično pravo": [
        "zakup", "najam", "kupoprodaj",
        "alimentacij", "razvod", "bračn",
        "zarada", "plata", "radni odnos",
    ],
    "Porodično pravo": [
        "krivičn", "krivicn", "kazna zatvora",
        "optužnic", "optuznic", "pritvor",
    ],
    "Obligaciono pravo": [
        "otkaz", "radni odnos", "zaposleni",
        "poslodavac", "sindikat", "štrajk",
        "radno vreme", "prekovremeni",
    ],
}

SHORTNAME_MAP = {
    "kz": ["Krivični zakonik"],
    "zkp": ["Zakonik o krivičnom postupku",
            "Zakon o krivičnom postupku"],
    "zoo": ["Zakon o obligacionim odnosima"],
    "zpp": ["Zakon o parničnom postupku"],
    "zor": ["Zakon o radu"],
    "pz": ["Porodični zakon"],
    "zup": ["Zakon o upravnom postupku"],
    "ustav": ["Ustav Kosova", "Ustav Republike Kosovo"],
    "ustav kosova": ["Ustav Kosova"],
}

SERBIA_MARKERS = [
    "zakon republike srbije", "zakon rs",
    "službeni glasnik rs", "republika srbija",
    "po srpskom pravu", "u srbiji", "zakon srbije",
]


# ═══════════════════════════════════════════════════════════════
#  HELPER: ČIST PRIKAZ STRINGOVA
# ═══════════════════════════════════════════════════════════════

def safe_text(text):
    """Čisti string od problematičnih karaktera za prikaz."""
    if not text:
        return ""
    t = str(text)
    t = t.replace('\x00', '')
    t = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f]', '', t)
    t = t.replace('\u200b', '')
    t = t.replace('\ufeff', '')
    return t.strip()


def safe_html(text):
    """Escapuje HTML karaktere u stringu."""
    if not text:
        return ""
    t = safe_text(text)
    t = t.replace("&", "&amp;")
    t = t.replace("<", "&lt;")
    t = t.replace(">", "&gt;")
    t = t.replace('"', "&quot;")
    return t


def render_footer():
    st.markdown("---")
    st.markdown(
        f'<div style="text-align:center;'
        f'padding:1rem 0;color:{TEXT_SECONDARY};'
        f'font-size:0.75rem;">'
        f'{DISCLAIMER_TEXT}'
        f'</div>',
        unsafe_allow_html=True)

def init_ss():
    defaults = {
        "logged_in": False, "current_user": None,
        "law_vs": None, "law_vs_version": "",
        "login_time": None,
        "active_case_id": None,
        "case_doc_vs": None, "case_doc_vs_id": None,
        "preview_articles": None,
        "preview_warnings": None,
        "preview_meta": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_ss()
# ═══════════════════════════════════════════════════════════════
#  LOZINKE + BAZA
# ═══════════════════════════════════════════════════════════════

def create_password_hash(password):
    if BCRYPT_AVAILABLE:
        h = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)).decode('utf-8')
        return h, "bcrypt"
    salt = secrets.token_hex(16)
    h = hashlib.sha256(
        (password + salt).encode()).hexdigest()
    return h, salt


def verify_password(password, stored_hash, stored_salt):
    if BCRYPT_AVAILABLE and stored_hash.startswith('$2'):
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                stored_hash.encode('utf-8')), False
        except Exception:
            return False, False
    if stored_salt and stored_salt != "bcrypt":
        legacy = hashlib.sha256(
            (password + stored_salt).encode()).hexdigest()
        if legacy == stored_hash:
            return True, BCRYPT_AVAILABLE
    return False, False


def authenticate_user(email, password):
    try:
        with get_db() as conn:
            u = conn.execute(
                "SELECT * FROM users WHERE email=?",
                (email.lower().strip(),)).fetchone()
            if not u:
                return None
            ok, upgrade = verify_password(
                password, u["password_hash"], u["salt"])
            if not ok:
                return None
            if upgrade and BCRYPT_AVAILABLE:
                nh, ns = create_password_hash(password)
                conn.execute(
                    "UPDATE users SET password_hash=?,"
                    "salt=? WHERE id=?",
                    (nh, ns, u["id"]))
            return dict(u)
    except Exception:
        return None


DB_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "prava_kolevka.db")


@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(
            DB_PATH, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    except sqlite3.Error:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                plan TEXT DEFAULT 'obican',
                is_active INTEGER DEFAULT 1,
                subscription_start TEXT,
                subscription_end TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT,
                auto_suspended INTEGER DEFAULT 0,
                suspended_reason TEXT DEFAULT '',
                notes TEXT DEFAULT ''
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_date TEXT NOT NULL,
                period_start TEXT, period_end TEXT,
                status TEXT DEFAULT 'completed',
                method TEXT DEFAULT 'manual',
                recorded_by INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS laws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_sr TEXT NOT NULL,
                name_al TEXT DEFAULT '',
                short_name TEXT DEFAULT '',
                law_number TEXT DEFAULT '',
                area TEXT DEFAULT 'Ostalo',
                gazette_info TEXT DEFAULT '',
                effective_date TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                language TEXT DEFAULT 'sr',
                full_text TEXT DEFAULT '',
                hierarchy_level INTEGER DEFAULT 3,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS law_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_id INTEGER NOT NULL,
                article_number TEXT NOT NULL,
                paragraph_number TEXT DEFAULT '',
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS case_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_html TEXT DEFAULT '',
                confidence TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS case_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                text_content TEXT NOT NULL,
                language TEXT DEFAULT 'sr',
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            try:
                c.execute(
                    "SELECT hierarchy_level FROM laws LIMIT 1")
            except Exception:
                c.execute(
                    "ALTER TABLE laws ADD COLUMN"
                    " hierarchy_level INTEGER DEFAULT 3")
            admin = c.execute(
                "SELECT id FROM users WHERE email=?",
                (ADMIN_EMAIL,)).fetchone()
            if not admin:
                ph, salt = create_password_hash(
                    ADMIN_DEFAULT_PASSWORD)
                c.execute(
                    "INSERT INTO users"
                    " (email,password_hash,salt,full_name,"
                    "role,plan,is_active,"
                    "subscription_start,subscription_end)"
                    " VALUES(?,?,?,?,'admin','enterprise',"
                    "1,?,?)",
                    (ADMIN_EMAIL, ph, salt, "Administrator",
                     date.today().isoformat(),
                     (date.today() + timedelta(
                         days=36500)).isoformat()))
                         # Sync iz Supabase u lokalni SQLite
            try:
                sb_laws = sb_get_all_laws(
                    active_only=True)
                if sb_laws:
                    local_count = c.execute(
                        "SELECT COUNT(*) FROM laws"
                    ).fetchone()[0]
                    if local_count == 0:
                        for law in sb_laws:
                            c.execute(
                                "INSERT OR IGNORE"
                                " INTO laws"
                                " (name_sr,name_al,"
                                "short_name,"
                                "law_number,area,"
                                "gazette_info,"
                                "effective_date,"
                                "language,full_text,"
                                "hierarchy_level,"
                                "is_active)"
                                " VALUES"
                                "(?,?,?,?,?,?,?,?,?,?,1)",
                                (law["name_sr"],
                                 law.get("name_al", ""),
                                 law.get(
                                     "short_name", ""),
                                 law.get(
                                     "law_number", ""),
                                 law.get(
                                     "area", "Ostalo"),
                                 law.get(
                                     "gazette_info", ""),
                                 law.get(
                                     "effective_date",
                                     ""),
                                 law.get(
                                     "language", "sr"),
                                 law.get(
                                     "full_text", ""),
                                 law.get(
                                     "hierarchy_level",
                                     3)))
                            local_id = c.execute(
                                "SELECT"
                                " last_insert_rowid()"
                            ).fetchone()[0]
                            sb_arts = sb_get_articles(
                                law["id"])
                            for art in sb_arts:
                                c.execute(
                                    "INSERT INTO"
                                    " law_articles"
                                    " (law_id,"
                                    "article_number,"
                                    "paragraph_number,"
                                    "title,content)"
                                    " VALUES"
                                    "(?,?,?,?,?)",
                                    (local_id,
                                     art.get(
                                         "article_number",
                                         "0"),
                                     "",
                                     art.get(
                                         "title", ""),
                                     art.get(
                                         "content",
                                         "")))
            except Exception:
                pass
    except Exception as e:
        st.error(f"DB init: {e}")
     # ═══════════════════════════════════════════════════════════════
#  PARSER
# ═══════════════════════════════════════════════════════════════

def clean_text(text):
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(
        r'\n\s*[-—–]\s*\d{1,4}\s*[-—–]\s*\n', '\n', text)
    text = re.sub(r'\n\s*\d{1,4}\s*\n', '\n', text)
    text = re.sub(
        r'\n\s*(?:Page|Strana|Faqe)\s+\d+\s*\n',
        '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*[-=_.·]{5,}\s*\n', '\n', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^ +| +$', '', text, flags=re.MULTILINE)
    return text.strip()


def remove_toc(text):
    toc_re = re.compile(
        r'^\s*(?:Član|ČLAN|Neni|Članak)\s+\d+[a-zA-Z]?'
        r'.*?(?:\.{3,}|…{2,}|·{3,})\s*\d{1,4}\s*$',
        re.IGNORECASE)
    lines = text.split('\n')
    toc_idx = set()
    i = 0
    while i < len(lines):
        if toc_re.match(lines[i].strip()):
            start = i
            while i < len(lines):
                s = lines[i].strip()
                if toc_re.match(s) or s == '':
                    i += 1
                else:
                    break
            cnt = sum(1 for j in range(start, i)
                      if toc_re.match(lines[j].strip()))
            if cnt >= 3:
                for j in range(start, i):
                    toc_idx.add(j)
        else:
            i += 1
    if not toc_idx:
        return text, False
    return '\n'.join(
        l for idx, l in enumerate(lines)
        if idx not in toc_idx), True


def parse_articles(full_text):
    warnings = []
    text = clean_text(full_text)
    text, had_toc = remove_toc(text)
    if had_toc:
        warnings.append("Uklonjen TOC.")
    lines = text.split('\n')

    hdr_solo = re.compile(
        r'^\s*(?:Član|ČLAN|Članak|ČLANAK|Neni|NENI)'
        r'\s+(\d+[a-zA-Z]?)\s*\.?\s*$', re.IGNORECASE)
    hdr_titled = re.compile(
        r'^\s*(?:Član|ČLAN|Članak|ČLANAK|Neni|NENI)'
        r'\s+(\d+[a-zA-Z]?)\s*[.\s]*[-–—:]\s*(.+)$',
        re.IGNORECASE)
    toc_chk = re.compile(
        r'(?:\.{3,}|…{2,})\s*\d{1,4}\s*$')

    starts = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or toc_chk.search(s):
            continue
        m = hdr_solo.match(s)
        if m:
            starts.append((i, m.group(1).strip(), ""))
            continue
        m = hdr_titled.match(s)
        if m and len(m.group(2).strip()) < 150:
            starts.append(
                (i, m.group(1).strip(),
                 m.group(2).strip()))

    if not starts:
        hdr_relax = re.compile(
            r'^\s*(?:Član|ČLAN|Neni|NENI)\s*[:\s]*'
            r'(\d+[a-zA-Z]?)\s*[.:\-–—]?\s*(.*)',
            re.IGNORECASE)
        for i, line in enumerate(lines):
            s = line.strip()
            if not s or toc_chk.search(s):
                continue
            m = hdr_relax.match(s)
            if m and len(m.group(2).strip()) < 150:
                starts.append(
                    (i, m.group(1).strip(),
                     m.group(2).strip()))
        if starts:
            warnings.append("Relaksirani pattern.")

    if not starts:
        warnings.append("Nema clanova. Jedan blok.")
        return [{
            "article_number": "0",
            "paragraph_number": "",
            "title": "(Ceo tekst)",
            "content": text[:10000]
        }], warnings

    articles = []
    for idx in range(len(starts)):
        ln, num, htitle = starts[idx]
        c_start = ln + 1
        c_end = (starts[idx + 1][0]
                 if idx + 1 < len(starts) else len(lines))
        c_lines = lines[c_start:c_end]
        title = htitle
        body_start = 0
        if not title and c_lines:
            first = c_lines[0].strip()
            if (first and len(first) < 150
                    and not re.match(
                        r'^\s*(?:\d+\s*[\.\)]|\(\d+\))',
                        first)
                    and len(c_lines) > 1):
                title = first
                body_start = 1
        body = '\n'.join(c_lines[body_start:]).strip()
        if not body and title:
            body = title
            title = ""
        if body:
            articles.append({
                "article_number": num,
                "paragraph_number": "",
                "title": title,
                "content": body})

    if len(starts) < 3:
        warnings.append(
            f"Samo {len(starts)} clanova.")
    return articles, warnings


def save_law_to_db(name_sr, name_al, short_name,
                   law_number, area, gazette_info,
                   effective_date, language, full_text,
                   hierarchy_level=3):
    try:
        articles, warnings = parse_articles(full_text)
        
        # Sačuvaj u Supabase
        law_data = {
            "name_sr": name_sr,
            "name_al": name_al,
            "short_name": short_name,
            "law_number": law_number,
            "area": area,
            "gazette_info": gazette_info,
            "effective_date": effective_date,
            "is_active": True,
            "language": language,
            "full_text": full_text,
            "hierarchy_level": hierarchy_level
        }
        law_id, num = sb_save_law_with_articles(
            law_data, articles)
        
        if not law_id:
            # Fallback na SQLite
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO laws (name_sr,name_al,"
                    "short_name,law_number,area,"
                    "gazette_info,effective_date,"
                    "language,full_text,hierarchy_level)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (name_sr, name_al, short_name,
                     law_number, area, gazette_info,
                     effective_date, language,
                     full_text, hierarchy_level))
                law_id = conn.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                for art in articles:
                    conn.execute(
                        "INSERT INTO law_articles"
                        " (law_id,article_number,"
                        "paragraph_number,title,content)"
                        " VALUES(?,?,?,?,?)",
                        (law_id,
                         art["article_number"],
                         art.get("paragraph_number", ""),
                         art.get("title", ""),
                         art["content"]))
            warnings.append(
                "Sačuvano u lokalnu bazu"
                " (Supabase nedostupan).")
        
        st.session_state.law_vs = None
        st.session_state.law_vs_version = ""
        return law_id, len(articles), warnings
    except Exception as e:
        return None, 0, [f"Greška: {e}"]
def reparse_law(law_id):
    try:
        with get_db() as conn:
            law = conn.execute(
                "SELECT full_text FROM laws"
                " WHERE id=?",
                (law_id,)).fetchone()
            if not law:
                return 0, ["Nije pronađen."]
            conn.execute(
                "DELETE FROM law_articles"
                " WHERE law_id=?",
                (law_id,))
            articles, warnings = parse_articles(
                law["full_text"])
            for art in articles:
                conn.execute(
                    "INSERT INTO law_articles"
                    " (law_id,article_number,"
                    "paragraph_number,title,content)"
                    " VALUES(?,?,?,?,?)",
                    (law_id,
                     art["article_number"],
                     art.get("paragraph_number", ""),
                     art.get("title", ""),
                     art["content"]))
            st.session_state.law_vs = None
            st.session_state.law_vs_version = ""
            return len(articles), warnings
    except Exception as e:
        return 0, [f"Greška: {e}"]

def export_laws_json():
    try:
        with get_db() as conn:
            laws = conn.execute(
                "SELECT * FROM laws WHERE is_active=1"
            ).fetchall()
            result = []
            for law in laws:
                ld = dict(law)
                arts = conn.execute(
                    "SELECT article_number,title,content"
                    " FROM law_articles WHERE law_id=?"
                    " ORDER BY CAST(article_number"
                    " AS INTEGER)", (ld["id"],)).fetchall()
                ld["articles"] = [dict(a) for a in arts]
                ld.pop("full_text", None)
                result.append(ld)
        return json.dumps(
            result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════
#  VEKTORSKA PRETRAGA
# ═══════════════════════════════════════════════════════════════

def get_law_vs_version():
    try:
        cnt = sb_count_articles()
        return f"{cnt}_sb"
    except Exception:
        try:
            with get_db() as conn:
                c = conn.execute(
                    "SELECT COUNT(*) FROM law_articles"
                ).fetchone()[0]
                return f"{c}_local"
        except Exception:
            return "0_"

def build_law_vector_store():
    if not OPENAI_API_KEY:
        return None
    try:
        rows = sb_get_all_articles_with_laws()
        if not rows:
            return None
        docs = []
        for r in rows:
            src = r.get('short_name') or r['name_sr']
            ref = f"Clan {r['article_number']}"
            hl = r.get('hierarchy_level', 3)
            hi = HIERARCHY_LEVELS.get(
                hl, HIERARCHY_LEVELS[3])
            txt = f"{hi['name']}: {src} {ref}"
            if r.get('title'):
                txt += f" {r['title']}"
            txt += f"\n{r['content']}"
            docs.append(Document(
                page_content=txt, metadata={
                    "article_number":
                        r['article_number'],
                    "paragraph_number": "",
                    "title": r.get('title', ''),
                    "content": r['content'],
                    "name_sr": r['name_sr'],
                    "short_name":
                        r.get('short_name', ''),
                    "law_number":
                        r.get('law_number', ''),
                    "area": r.get('area', ''),
                    "hierarchy_level": hl}))
        sp = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200)
        final = []
        for d in docs:
            if len(d.page_content) > 1200:
                final.extend(
                    sp.split_documents([d]))
            else:
                final.append(d)
        if not final:
            return None
        return FAISS.from_documents(
            final, OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=OPENAI_API_KEY))
    except Exception:
        return None


def get_law_vector_store():
    cv = get_law_vs_version()
    if (st.session_state.get("law_vs") is not None
            and st.session_state.get(
                "law_vs_version") == cv
            and cv != "0_"):
        return st.session_state.law_vs
    vs = build_law_vector_store()
    st.session_state.law_vs = vs
    st.session_state.law_vs_version = cv
    return vs
 # ═══════════════════════════════════════════════════════════════
#  PRETRAGA + AI
# ═══════════════════════════════════════════════════════════════

def detect_legal_area(q):
    q_lower = q.lower()
    det = []
    for area, kws in AREA_KEYWORDS.items():
        sc = 0
        for kw in kws:
            if kw in q_lower:
                # Duže ključne reči nose više
                sc += 1 + (len(kw) > 6)
        if sc >= 1:
            det.append((area, sc))
    det.sort(key=lambda x: x[1], reverse=True)
    return [a for a, _ in det[:3]]

def detect_target_law(q):
    q = q.lower()
    t = []
    for sn, fns in SHORTNAME_MAP.items():
        if sn in q:
            t.extend(fns)
    return list(set(t))


def detect_jurisdiction_issue(q):
    q = q.lower()
    for m in SERBIA_MARKERS:
        if m in q:
            return m
    return None

def check_key_law_present(areas, results):
    """Proverava da li ključni zakon za
    detektovanu oblast postoji u rezultatima."""
    if not areas or not results:
        return False, []
    missing = []
    for area in areas[:2]:
        akl = AREA_KEY_LAWS.get(area)
        if not akl:
            continue
        found = False
        for r in results:
            rname = (
                r.get('name_sr', '') or ''
            ).lower()
            rshort = (
                r.get('short_name', '') or ''
            ).lower()
            for kl in akl["laws"]:
                if kl in rname or kl in rshort:
                    found = True
                    break
            if found:
                break
        if not found:
            missing.append(akl["label"])
    has_key = len(missing) == 0
    return has_key, missing


def filter_irrelevant_sources(results, areas):
    """Penalizuje izvore iz nekompatibilne
    oblasti prava."""
    if not areas or not results:
        return results
    primary_area = areas[0]
    akl = AREA_KEY_LAWS.get(primary_area)
    if not akl:
        return results
    incomp = set(akl.get("incompatible", []))
    if not incomp:
        return results
    filtered = []
    for r in results:
        r_area = r.get('area', '')
        if r_area in incomp:
            r = dict(r)
            r['score'] = max(1,
                             r.get('score', 0) // 5)
            r['_penalized'] = True
        filtered.append(r)
    filtered.sort(
        key=lambda x: x.get('score', 0),
        reverse=True)
    return filtered

def search_laws(query, max_results=15):
    q = query.lower()
    stop = {
        'je', 'su', 'da', 'li', 'se', 'na', 'u', 'i',
        'za', 'od', 'sa', 'po', 'ne', 'ni', 'sto', 'sta',
        'kako', 'koji', 'koja', 'koje', 'ko', 'ako', 'ali',
        'ili', 'kad', 'gde', 'iz', 'do', 'bi', 'moze',
        'mora', 'treba', 'prema', 'biti', 'bude', 'sam',
        'jedan', 'neki', 'sve', 'clan', 'stav', 'zakon',
        'pravo', 'pravni', 'molim', 'pitanje'}
    words = re.findall(r'[a-zA-ZčćžšđČĆŽŠĐ]+', q)
    kws = [w for w in words
           if len(w) > 2 and w not in stop]

    am = re.search(
        r'(?:član|članu|člana|neni)'
        r'\s*[:\s]*(\d+[a-zA-Z]?)', q)
    t_art = am.group(1) if am else None
    t_laws = detect_target_law(query)
    t_areas = detect_legal_area(query)
    rd = {}

    # Da li je pitanje o cilju/oblasti/definicijama?
    is_scope_q = any(
        sk in q for sk in SCOPE_KEYWORDS)

    # Nekompatibilni termini za detekovanu oblast
    irr_terms = []
    if t_areas:
        for area in t_areas[:2]:
            irr_terms.extend(
                IRRELEVANT_PATTERNS.get(area, []))

    def score_article(art, law, base):
        """Računa score za članak."""
        content_l = art.get("content", "").lower()
        title_l = (
            art.get("title", "") or "").lower()
        score = base

        # 1. Keyword match — koliko kw se poklapa
        kw_hits = sum(
            1 for k in kws
            if k in content_l or k in title_l)
        score += kw_hits * 12

        # 2. Title match bonus — naslov je precizniji
        title_kw = sum(
            1 for k in kws if k in title_l)
        score += title_kw * 20

        # 3. Oblast match
        if t_areas and law.get("area") in t_areas:
            score += 25

        # 4. Tačan zakon match
        if t_laws:
            name_l = law.get(
                "name_sr", "").lower()
            short_l = law.get(
                "short_name", "").lower()
            for ln in t_laws:
                ln_l = ln.lower()
                if ln_l in name_l or ln_l in short_l:
                    score += 40
                    break

        # 5. Scope boost — rani članci za opšta
        #    pitanja
        if is_scope_q:
            art_num_str = art.get(
                "article_number", "999")
            try:
                art_num = int(
                    re.sub(r'[^0-9]', '',
                           art_num_str) or 999)
            except Exception:
                art_num = 999
            if art_num <= 3:
                score += 40
            elif art_num <= 10:
                score += 15
            # Boost za naslove o cilju itd.
            scope_title = [
                "cilj", "predmet", "oblast",
                "definicij", "pojm", "načel",
                "nacela", "svrha", "primena",
                "opšte", "opste", "osnov"]
            if any(st in title_l
                   for st in scope_title):
                score += 35

        # 6. Penalizacija nerelevantnih
        if irr_terms:
            irr_hits = sum(
                1 for it in irr_terms
                if it in content_l
                or it in title_l)
            if irr_hits > 0:
                # Što više nerelevantnih termina,
                # veća penalizacija
                score -= irr_hits * 25
                score = max(1, score)

        # 7. Penalizacija ako 0 keyword matcheva
        #    i nije scope pitanje
        if kw_hits == 0 and not is_scope_q:
            score = max(1, score // 3)

        return score

    def add(r, score):
        k = (f"{r.get('name_sr', '')}|"
             f"{r.get('article_number', '')}|"
             f"{r.get('paragraph_number', '')}")
        hl = r.get('hierarchy_level', 3)
        hb = HIERARCHY_LEVELS.get(
            hl, HIERARCHY_LEVELS[3])['weight']
        total = score + hb
        r['score'] = total
        r['hierarchy_level'] = hl
        if k not in rd or total > rd[k]['score']:
            rd[k] = r

    def art_to_result(art, law):
        return {
            "article_number":
                art["article_number"],
            "paragraph_number": "",
            "title": art.get("title", ""),
            "content": art["content"],
            "name_sr": law["name_sr"],
            "short_name":
                law.get("short_name", ""),
            "law_number":
                law.get("law_number", ""),
            "area": law.get("area", ""),
            "hierarchy_level":
                law.get("hierarchy_level", 3),
        }

    # ═══ SUPABASE PRETRAGA ═══
    try:
        # Cache za law_basic da ne dohvatamo
        # isti zakon više puta
        _law_cache = {}

        def get_law_cached(law_id):
            if law_id not in _law_cache:
                _law_cache[law_id] = \
                    sb_get_law_basic(law_id)
            return _law_cache[law_id]

        # 1. Tačan broj člana
        if t_art:
            arts = sb_search_articles_by_number(
                t_art)
            for art in arts:
                law = get_law_cached(
                    art["law_id"])
                if not law:
                    continue
                r = art_to_result(art, law)
                sc = score_article(
                    art, law, 150)
                add(r, sc)

        # 2. Multi-keyword pretraga
        if kws:
            # Ako znamo tačan zakon, pretražuj
            # samo unutar njega
            target_law_ids = None
            if t_laws:
                target_law_ids = []
                for ln in t_laws:
                    found = sb_find_laws_by_name(ln)
                    for f in found:
                        target_law_ids.append(
                            f["id"])
                        _law_cache[f["id"]] = f
                if not target_law_ids:
                    target_law_ids = None

            arts = sb_search_articles_multi(
                kws, target_law_ids)
            for art in arts:
                law = get_law_cached(
                    art["law_id"])
                if not law:
                    continue
                r = art_to_result(art, law)
                # Bazni score zavisi od broja
                # matchovanih ključnih reči
                mc = art.get("_match_count", 1)
                base = 20 + mc * 15
                sc = score_article(
                    art, law, base)
                add(r, sc)

            # Ako nemamo target zakon, pretražuj
            # i po oblasti
            if not target_law_ids and t_areas:
                for area in t_areas[:2]:
                    area_ids = \
                        sb_get_law_ids_by_area(area)
                    if area_ids:
                        area_arts = \
                            sb_search_articles_multi(
                                kws, area_ids)
                        for art in area_arts:
                            law = get_law_cached(
                                art["law_id"])
                            if not law:
                                continue
                            r = art_to_result(
                                art, law)
                            mc = art.get(
                                "_match_count", 1)
                            base = 30 + mc * 15
                            sc = score_article(
                                art, law, base)
                            add(r, sc)

        # 3. Scope pitanja — dodaj rane članke
        if is_scope_q and t_laws:
            for ln in t_laws:
                found = sb_find_laws_by_name(ln)
                for f in found:
                    _law_cache[f["id"]] = f
                    early = sb_get_first_articles(
                        f["id"], 5)
                    for art in early:
                        r = art_to_result(art, f)
                        sc = score_article(
                            art, f, 80)
                        add(r, sc)

        # Scope bez tačnog zakona — rani članci
        # iz zakona relevantne oblasti
        if is_scope_q and not t_laws and t_areas:
            for area in t_areas[:2]:
                area_ids = \
                    sb_get_law_ids_by_area(area)
                for lid in area_ids[:3]:
                    law = get_law_cached(lid)
                    if not law:
                        continue
                    early = sb_get_first_articles(
                        lid, 5)
                    for art in early:
                        r = art_to_result(art, law)
                        sc = score_article(
                            art, law, 60)
                        add(r, sc)

    except Exception as e:
        st.error(f"Greška pretrage: {e}")

    # ═══ VEKTORSKA PRETRAGA ═══
    vs = get_law_vector_store()
    if vs:
        try:
            for doc, dist in \
                    vs.similarity_search_with_score(
                        query, k=15):
                m = doc.metadata
                if dist < 1.3:
                    sc = max(5, int(
                        85 * (1 - dist / 1.3)))
                    r = {k: m.get(k, '') for k in [
                        'article_number',
                        'paragraph_number',
                        'title', 'content',
                        'name_sr', 'short_name',
                        'law_number', 'area',
                        'hierarchy_level']}
                    if not r['content']:
                        r['content'] = \
                            doc.page_content
                    if (t_areas
                            and r.get('area')
                            in t_areas):
                        sc += 15
                    add(r, sc)
        except Exception:
            pass

    sorted_results = sorted(
        rd.values(),
        key=lambda x: x.get('score', 0),
        reverse=True)[:max_results]
    if t_areas:
        sorted_results = filter_irrelevant_sources(
            sorted_results, t_areas)
    return sorted_results

    def add(r, base):
        k = (f"{r.get('name_sr', '')}|"
             f"{r.get('article_number', '')}|"
             f"{r.get('paragraph_number', '')}")
        hl = r.get('hierarchy_level', 3)
        hb = HIERARCHY_LEVELS.get(
            hl, HIERARCHY_LEVELS[3])['weight']
        total = base + hb
        r['score'] = total
        r['hierarchy_level'] = hl
        if k not in rd or total > rd[k]['score']:
            rd[k] = r

    # ═══ SUPABASE PRETRAGA ═══
    try:
        # 1. Po broju člana
        if t_art:
            arts = sb_search_articles_by_number(
                t_art)
            for art in arts:
                law = sb_get_law_basic(
                    art["law_id"])
                if not law:
                    continue
                r = {
                    "article_number":
                        art["article_number"],
                    "paragraph_number": "",
                    "title": art.get("title", ""),
                    "content": art["content"],
                    "name_sr": law["name_sr"],
                    "short_name":
                        law.get("short_name", ""),
                    "law_number":
                        law.get("law_number", ""),
                    "area": law.get("area", ""),
                    "hierarchy_level":
                        law.get(
                            "hierarchy_level", 3),
                }
                base = 150
                # Bonus ako je tačan zakon
                if t_laws:
                    for ln in t_laws:
                        ln_l = ln.lower()
                        if (ln_l in law["name_sr"]
                                .lower()
                                or ln_l in law.get(
                                    "short_name",
                                    "").lower()):
                            base = 200
                            break
                # Bonus ako je tačna oblast
                if (t_areas and law.get("area")
                        in t_areas):
                    base += 50
                add(r, base)

        # 2. Po ključnim rečima
        for kw in kws[:6]:
            arts = sb_search_articles(kw)
            for art in arts:
                law = sb_get_law_basic(
                    art["law_id"])
                if not law:
                    continue
                r = {
                    "article_number":
                        art["article_number"],
                    "paragraph_number": "",
                    "title": art.get("title", ""),
                    "content": art["content"],
                    "name_sr": law["name_sr"],
                    "short_name":
                        law.get("short_name", ""),
                    "law_number":
                        law.get("law_number", ""),
                    "area": law.get("area", ""),
                    "hierarchy_level":
                        law.get(
                            "hierarchy_level", 3),
                }
                content_l = art["content"].lower()
                kc = sum(1 for k in kws
                         if k in content_l)
                base = 20 + kc * 10
                # Bonus za tačan zakon
                if t_laws:
                    for ln in t_laws:
                        ln_l = ln.lower()
                        if (ln_l in law["name_sr"]
                                .lower()
                                or ln_l in law.get(
                                    "short_name",
                                    "").lower()):
                            base += 50
                            break
                # Bonus za tačnu oblast
                if (t_areas and law.get("area")
                        in t_areas):
                    base += 15
                add(r, base)

        # 3. Po nazivu zakona
        if t_laws:
            for ln in t_laws:
                found = sb_find_laws_by_name(ln)
                for law in found:
                    arts = sb_search_articles(
                        kws[0] if kws else "")
                    law_arts = [
                        a for a in arts
                        if a["law_id"] == law["id"]]
                    for art in law_arts[:10]:
                        r = {
                            "article_number":
                                art[
                                    "article_number"],
                            "paragraph_number": "",
                            "title":
                                art.get("title", ""),
                            "content":
                                art["content"],
                            "name_sr":
                                law["name_sr"],
                            "short_name":
                                law.get(
                                    "short_name",
                                    ""),
                            "law_number":
                                law.get(
                                    "law_number",
                                    ""),
                            "area":
                                law.get("area", ""),
                            "hierarchy_level":
                                law.get(
                                    "hierarchy_level",
                                    3),
                        }
                        content_l = art[
                            "content"].lower()
                        kc = sum(1 for k in kws
                                 if k in content_l)
                        add(r, 100 + kc * 10)

    except Exception as e:
        st.error(f"Greška pretrage: {e}")

    # ═══ VEKTORSKA PRETRAGA ═══
    vs = get_law_vector_store()
    if vs:
        try:
            for doc, dist in \
                    vs.similarity_search_with_score(
                        query, k=15):
                m = doc.metadata
                if dist < 1.3:
                    sc = max(5, int(
                        85 * (1 - dist / 1.3)))
                    r = {k: m.get(k, '') for k in [
                        'article_number',
                        'paragraph_number',
                        'title', 'content',
                        'name_sr', 'short_name',
                        'law_number', 'area',
                        'hierarchy_level']}
                    if not r['content']:
                        r['content'] = \
                            doc.page_content
                    if (t_areas
                            and r.get('area')
                            in t_areas):
                        sc += 15
                    add(r, sc)
        except Exception:
            pass

    sorted_results = sorted(
        rd.values(),
        key=lambda x: x.get('score', 0),
        reverse=True)[:max_results]
    if t_areas:
        sorted_results = filter_irrelevant_sources(
            sorted_results, t_areas)
    return sorted_results
    def add(r, base):
        k = (f"{r['name_sr']}|{r['article_number']}"
             f"|{r.get('paragraph_number', '')}")
        hl = r.get('hierarchy_level', 3)
        hb = HIERARCHY_LEVELS.get(
            hl, HIERARCHY_LEVELS[3])['weight']
        total = base + hb
        r['score'] = total
        r['hierarchy_level'] = hl
        if k not in rd or total > rd[k]['score']:
            rd[k] = r

    try:
        with get_db() as conn:
            bq = ("SELECT la.article_number,"
                  "la.paragraph_number,la.title,"
                  "la.content,"
                  "l.name_sr,l.short_name,"
                  "l.law_number,"
                  "l.area,l.hierarchy_level"
                  " FROM law_articles la"
                  " JOIN laws l ON la.law_id=l.id"
                  " WHERE l.is_active=1")

            if t_art and t_laws:
                for ln in t_laws:
                    for r in conn.execute(
                            bq + " AND"
                            " la.article_number=?"
                            " AND (l.name_sr LIKE ?"
                            " OR l.short_name"
                            " LIKE ?)",
                            (t_art, f"%{ln}%",
                             f"%{ln}%")).fetchall():
                        add(dict(r), 200)
            if t_art:
                for r in conn.execute(
                        bq + " AND"
                        " la.article_number=?",
                        (t_art,)).fetchall():
                    d = dict(r)
                    ab = (50 if d.get('area')
                          in t_areas else 0)
                    add(d, 150 + ab)
            if t_laws and kws:
                for ln in t_laws:
                    for kw in kws[:6]:
                        for r in conn.execute(
                                bq + " AND"
                                " (l.name_sr LIKE ?"
                                " OR l.short_name"
                                " LIKE ?)"
                                " AND (la.content"
                                " LIKE ?"
                                " OR la.title"
                                " LIKE ?)"
                                " LIMIT 5",
                                (f"%{ln}%",
                                 f"%{ln}%",
                                 f"%{kw}%",
                                 f"%{kw}%"
                                 )).fetchall():
                            d = dict(r)
                            kc = sum(
                                1 for k in kws
                                if k in d['content']
                                .lower())
                            add(d, 100 + kc * 10)
            if kws and t_areas:
                for kw in kws[:5]:
                    for area in t_areas[:2]:
                        for r in conn.execute(
                                bq + " AND l.area=?"
                                " AND (la.content"
                                " LIKE ?"
                                " OR la.title"
                                " LIKE ?)"
                                " LIMIT 5",
                                (area, f"%{kw}%",
                                 f"%{kw}%"
                                 )).fetchall():
                            d = dict(r)
                            kc = sum(
                                1 for k in kws
                                if k in d['content']
                                .lower())
                            add(d, 60 + kc * 10)
            if kws:
                for kw in kws[:5]:
                    for r in conn.execute(
                            bq + " AND"
                            " (la.content LIKE ?"
                            " OR la.title LIKE ?)"
                            " LIMIT 8",
                            (f"%{kw}%",
                             f"%{kw}%")).fetchall():
                        d = dict(r)
                        kc = sum(
                            1 for k in kws
                            if k in d['content']
                            .lower())
                        ab = (15 if d.get('area')
                              in t_areas else 0)
                        add(d, 20 + kc * 10 + ab)
    except Exception as e:
        st.error(f"Greska pretrage: {e}")

    vs = get_law_vector_store()
    if vs:
        try:
            for doc, dist in vs.similarity_search_with_score(query, k=15):
                m = doc.metadata
                if dist < 1.3:
                    sc = max(5, int(85 * (1 - dist / 1.3)))
                    r = {k: m.get(k, '') for k in [
                        'article_number', 'paragraph_number',
                        'title', 'content', 'name_sr', 'short_name',
                        'law_number', 'area', 'hierarchy_level']}
                    if not r['content']:
                        r['content'] = doc.page_content
                    if t_areas and r.get('area') in t_areas:
                        sc += 15
                    add(r, sc)
        except Exception:
            pass

    sorted_results = sorted(
        rd.values(),
        key=lambda x: x.get('score', 0),
        reverse=True)[:max_results]
    if t_areas:
        sorted_results = filter_irrelevant_sources(
            sorted_results, t_areas)
    return sorted_results


def format_results(results):
    if not results:
        return "PRONADJENO: 0 clanova.\nNEMA IZVORA."
    parts = [f"PRONADJENO: {len(results)} clanova.\n"]
    for i, r in enumerate(results):
        src = (r.get('short_name')
               or r.get('name_sr', ''))
        ln = (f" ({r['law_number']})"
              if r.get('law_number') else "")
        art = f"Clan {r.get('article_number', '?')}"
        ttl = (f" - {r['title']}"
               if r.get('title') else "")
        hl = r.get('hierarchy_level', 3)
        hi = HIERARCHY_LEVELS.get(
            hl, HIERARCHY_LEVELS[3])
        parts.append(
            f"[IZVOR #{i+1} | {hi['icon']}"
            f" {hi['name'].upper()}"
            f" | {src}{ln}, {art}{ttl}]\n"
            f"{r.get('content', '')}\n"
            f"[KRAJ #{i+1}]")
    allowed = sorted(set(
        f"{r.get('short_name') or r.get('name_sr', '')},"
        f" Clan {r.get('article_number', '?')}"
        for r in results))
    parts.append(
        "\n=== DOZVOLJENI CITATI ===\n"
        "SMES citirati ISKLJUCIVO:\n"
        + "\n".join(f"* {a}" for a in allowed))
    return "\n\n".join(parts)


def determine_confidence(results, query,
                         areas=None):
    """4 nivoa pouzdanosti sa proverom oblasti
    i ključnog zakona."""
    if not results:
        return "LOW", "Nisu pronađeni izvori."

    # Bazične metrike
    top_score = results[0].get('score', 0)
    total = len(results)
    penalized = sum(
        1 for r in results
        if r.get('_penalized'))
    clean = total - penalized
    hq = sum(1 for r in results
             if r.get('score', 0) >= 80
             and not r.get('_penalized'))

    # Provera ključnog zakona
    has_key = True
    missing_laws = []
    if areas:
        has_key, missing_laws = \
            check_key_law_present(areas, results)

    # Provera oblasti — koliko rezultata je
    # iz prave oblasti
    area_match = 0
    if areas:
        for r in results:
            if r.get('area') in areas:
                area_match += 1

    # VISOKA: mnogo dobrih izvora + ključni zakon
    # + većina iz prave oblasti
    if (hq >= 3 and top_score >= 100
            and has_key
            and area_match >= 2):
        return ("HIGH",
                "Odgovor je utemeljen u izvorima"
                " iz odgovarajuće oblasti.")

    # SREDNJA: ima dobrih izvora ali možda fali
    # ključni zakon ili oblast nije savršena
    if (hq >= 1 and top_score >= 60
            and (has_key or area_match >= 1)):
        note = ""
        if not has_key and missing_laws:
            note = (
                f" Ključni izvor"
                f" ({', '.join(missing_laws)})"
                f" nije pronađen u bazi.")
        return ("MEDIUM",
                "Odgovor je delimično utemeljen"
                " u izvorima." + note)

    # OGRANIČENA: ima nešto ali nije ubedljivo
    if clean >= 1 and top_score >= 30:
        note = ""
        if not has_key and missing_laws:
            note = (
                f" Ključni izvor"
                f" ({', '.join(missing_laws)})"
                f" nije pronađen u bazi.")
        if penalized > clean:
            note += (
                " Većina pronađenih izvora"
                " je iz druge oblasti prava.")
        return ("LIMITED",
                "Pronađeni su ograničeni"
                " izvori." + note)

    # NISKA: nema relevantnih izvora
    note = "Nisu pronađeni relevantni izvori."
    if missing_laws:
        note += (
            f" Ključni izvor"
            f" ({', '.join(missing_laws)})"
            f" nije u bazi.")
    return ("LOW", note)


def verify_citations(resp, results):
    cited = re.findall(
        r'[Čč]lan(?:u|a|om|ku)?\s+(\d+[a-zA-Z]?)',
        resp, re.IGNORECASE)
    avail = set(
        r.get('article_number', '') for r in results)
    bad = [c for c in set(cited) if c not in avail]
    if bad:
        resp += (
            "\n\n**Napomena:** AI je pomenuo Clan "
            + ", ".join(bad)
            + " koji nisu medju izvorima.")
    return resp


def render_sources_html(results):
    if not results:
        return ""
    parts = ['<div style="margin-top:12px;">']
    shown = set()
    for r in results[:8]:
        src = safe_text(
            r.get('short_name')
            or r.get('name_sr', ''))
        art_num = safe_text(
            r.get('article_number', '?'))
        art = f"Clan {art_num}"
        key = f"{src}|{art}"
        if key in shown:
            continue
        shown.add(key)
        hl = r.get('hierarchy_level', 3)
        hi = HIERARCHY_LEVELS.get(
            hl, HIERARCHY_LEVELS[3])
        title = safe_text(r.get('title', ''))
        title_str = f" - {title}" if title else ""
        content = r.get('content', '')
        snippet = safe_html(content[:200])
        if len(content) > 200:
            snippet += "..."
        parts.append(
            '<div style="background:white;'
            'border-left:3px solid #C5962C;'
            'border-radius:0 10px 10px 0;'
            'padding:10px 14px;margin:6px 0;'
            'font-size:0.85rem;'
            'word-wrap:break-word;'
            'overflow-wrap:break-word;">'
            '<div style="font-weight:600;'
            'color:#0A1628;">'
            f'{safe_html(hi["icon"])} '
            f'{safe_html(src)}: '
            f'{safe_html(art)}'
            f'{safe_html(title_str)}'
            '</div>'
            '<div style="color:#999;'
            'font-size:0.7rem;margin:2px 0;">'
            f'{safe_html(hi["name"])}'
            '</div>'
            '<div style="color:#6B7280;'
            'margin-top:4px;font-size:0.8rem;">'
            f'{snippet}'
            '</div>'
            '</div>')
    parts.append('</div>')
    return ''.join(parts)


SYSTEM_PROMPT = (
    'Ti si "Prava Kolevka" - pravni AI za KOSOVO.\n\n'
    'PRAVILA:\n'
    '1. Odgovaraj ISKLJUCIVO iz prilozenih [IZVOR].\n'
    '2. Za svaku tvrdnju citiraj: '
    '"Prema [Zakon], clan X..."\n'
    '3. Citiraj SAMO iz sekcije DOZVOLJENI CITATI.\n'
    '4. Ako nema odgovora: "Na osnovu zakona u bazi, '
    'ne postoje odredbe."\n'
    '5. Samo Kosovo. Za drugu drzavu: '
    '"Sistem sadrzi samo zakone Kosova."\n'
    '6. Hijerarhija: USTAV > MEDJUNARODNI > '
    'ZAKON > PODZAKONSKI\n'
    '7. Koristi SAMO izvore iz PRAVE OBLASTI.\n'
    '   Ako je pitanje o radnom pravu, ne citiraj '
    'krivicni zakonik ili krivicni postupak.\n'
    '   Ako je pitanje o krivicnom delu, ne citiraj '
    'zakon o radu ili porodicni zakon.\n'
    '8. Ako medju izvorima nema odgovarajuceg zakona '
    'za oblast pitanja, jasno navedi da kljucni '
    'zakon nije pronadjen u bazi.\n\n'
    'DETEKTOVANA OBLAST: {detected_area}\n'
    'NAPOMENA O IZVORIMA: {source_note}\n\n'
    'FORMAT:\n'
    '## Odgovor\n[2-3 recenice]\n'
    '## Obrazlozenje\n[Sa citatima iz PRAVE oblasti]\n'
    '## Korisceni izvori\n[Lista]\n'
    '## Pouzdanost\n[Nivo i objasnjenje]\n'
    '## Napomena\n[Ogranicenja]\n\n'
    '=== CLANOVI ===\n{law_context}\n'
    '=== DOKUMENTI ===\n{doc_context}\n'
    '=== PITANJE ===\n{question}')

def query_ai(question, case_doc_vs=None):
    ji = detect_jurisdiction_issue(question)
    tl = detect_target_law(question)
    t_areas = detect_legal_area(question)
    missing = []
        if tl:
        try:
            for t in tl:
                found = sb_find_laws_by_name(t)
                if not found:
                    missing.append(t)
        except Exception:
            pass

    results = search_laws(question)
    conf_level, conf_note = determine_confidence(
        results, question, t_areas)

    # Proveri ključni zakon
    has_key, missing_key = check_key_law_present(
        t_areas, results)

    ctx = format_results(results)

    doc_ctx = "(Nema dokumenata.)"
    if case_doc_vs:
        try:
            ds = case_doc_vs.as_retriever(
                search_kwargs={"k": 4}).invoke(
                    question)
            if ds:
                doc_ctx = "\n---\n".join(
                    f"[{d.metadata.get('source', '?')}]"
                    f"\n{d.page_content}" for d in ds)
        except Exception:
            pass

    # Detektovana oblast za AI
    area_str = (
        ", ".join(t_areas) if t_areas
        else "Nije detektovana specifična oblast")

    # Napomena o izvorima za AI
    source_note_parts = []
    if missing_key:
        source_note_parts.append(
            f"KLJUCNI ZAKON NIJE U BAZI:"
            f" {', '.join(missing_key)}."
            f" Nemoj davati odgovor kao da"
            f" je potpuno utemeljen.")
    if missing:
        source_note_parts.append(
            f"Trazeni zakon nije u bazi:"
            f" {', '.join(missing)}.")
    if conf_level == "LOW":
        source_note_parts.append(
            "NEMA DOVOLJNO IZVORA."
            " Odgovori ograniceno i upozori"
            " korisnika.")
    if conf_level == "LIMITED":
        source_note_parts.append(
            "OGRANICENI IZVORI."
            " Budi oprezan i navedi ogranicenja.")
    source_note = (
        " ".join(source_note_parts)
        if source_note_parts
        else "Izvori izgledaju adekvatno.")

    # Ako nema traženog zakona i nema rezultata
    if missing and not results:
        ans = (
            "## Odgovor\n"
            + ", ".join(missing)
            + " nisu u bazi.\n\n"
            "## Korišćeni izvori\nNijedan.\n\n"
            "## Pouzdanost\nNiska — ključni"
            " izvor nije u bazi.\n\n"
            "## Napomena\nKontaktirajte admina"
            " da doda potrebne zakone.")
        if ji:
            ans += (f"\n\nNapomena: '{ji}'"
                    " — druga država.")
        return ans, "LOW", results

    # Ako je pouzdanost niska i nema dokumenata
    if conf_level == "LOW" and not case_doc_vs:
        ans = "## Odgovor\n"
        if missing_key:
            ans += (
                "U bazi nisu pronađeni dovoljno"
                " relevantni izvori za potpuno"
                " pouzdan odgovor.\n\n"
                f"**Nedostaje ključni propis:**"
                f" {', '.join(missing_key)}\n\n")
        else:
            ans += (
                "Nisu pronađene odgovarajuće"
                " odredbe u bazi zakona.\n\n")
        ans += (
            "## Korišćeni izvori\nNijedan"
            " relevantan.\n\n"
            "## Pouzdanost\nNiska\n\n"
            "## Napomena\n"
            "Potrebna je dopuna baze ili"
            " dodatna provera izvora."
            " Konsultujte advokata.")
        if missing:
            ans += ("\n\n"
                    + ", ".join(missing)
                    + " — nije u bazi.")
        if ji:
            ans += (f"\n\nNapomena: '{ji}'"
                    " — druga država.")
        return ans, conf_level, results

    extra = ""
    if ji:
        extra += (f"\nVAZNO: '{ji}'"
                  " - samo Kosovo.")
    if missing:
        extra += ("\nVAZNO: "
                  + ", ".join(missing)
                  + " NIJE u bazi.")

    prompt = SYSTEM_PROMPT.format(
        law_context=ctx, doc_context=doc_ctx,
        question=question + extra,
        detected_area=area_str,
        source_note=source_note)
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=OPENAI_API_KEY,
            temperature=0.05, max_tokens=4096)
        ans = llm.invoke(
            [HumanMessage(content=prompt)]).content
        ans = verify_citations(ans, results)

        # Dodaj pouzdanost na kraj
        conf_labels = {
            "HIGH": "Visoka",
            "MEDIUM": "Srednja",
            "LIMITED": "Ograničena",
            "LOW": "Niska"}
        conf_icons = {
            "HIGH": "🟢",
            "MEDIUM": "🟡",
            "LIMITED": "🟠",
            "LOW": "🔴"}
        icon = conf_icons.get(conf_level, "⚪")
        label = conf_labels.get(
            conf_level, "Nepoznata")

        ans += (
            f"\n\n---\n"
            f"**Pouzdanost:** {icon}"
            f" {label}\n\n"
            f"*{conf_note}*")
        if missing_key:
            ans += (
                f"\n\n**Nedostaje u bazi:**"
                f" {', '.join(missing_key)}")
        return ans, conf_level, results
    except Exception as e:
        return (f"Greška: {e}",
                "LOW", results)
     # ═══════════════════════════════════════════════════════════════
#  PREDMETI + DOKUMENTI + POMOCNE
# ═══════════════════════════════════════════════════════════════

def create_case(user_id, title):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO cases (owner_id,title)"
            " VALUES(?,?)", (user_id, title))
        return conn.execute(
            "SELECT last_insert_rowid()").fetchone()[0]


def get_user_cases(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM cases WHERE owner_id=?"
            " ORDER BY created_at DESC",
            (user_id,)).fetchall()
        return [dict(r) for r in rows]


def delete_case(case_id, user_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM case_messages"
            " WHERE case_id=?", (case_id,))
        conn.execute(
            "DELETE FROM case_documents"
            " WHERE case_id=?", (case_id,))
        conn.execute(
            "DELETE FROM cases"
            " WHERE id=? AND owner_id=?",
            (case_id, user_id))
    if st.session_state.get(
            "active_case_id") == case_id:
        st.session_state.active_case_id = None
    if st.session_state.get(
            "case_doc_vs_id") == case_id:
        st.session_state.case_doc_vs = None
        st.session_state.case_doc_vs_id = None


def get_case_messages(case_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content,"
            " sources_html, confidence"
            " FROM case_messages"
            " WHERE case_id=?"
            " ORDER BY created_at",
            (case_id,)).fetchall()
        return [dict(r) for r in rows]


def save_case_message(case_id, role, content,
                      sources_html="",
                      confidence=""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO case_messages"
            " (case_id,role,content,"
            "sources_html,confidence)"
            " VALUES(?,?,?,?,?)",
            (case_id, role, content,
             sources_html, confidence))


def add_case_document(case_id, filename,
                      text_content, language="sr"):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO case_documents"
            " (case_id,filename,text_content,language)"
            " VALUES(?,?,?,?)",
            (case_id, filename, text_content, language))
    if st.session_state.get(
            "case_doc_vs_id") == case_id:
        st.session_state.case_doc_vs = None
        st.session_state.case_doc_vs_id = None


def get_case_documents(case_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id,filename,language,"
            "LENGTH(text_content) as size,"
            "created_at"
            " FROM case_documents"
            " WHERE case_id=?"
            " ORDER BY created_at",
            (case_id,)).fetchall()
        return [dict(r) for r in rows]


def delete_case_document(doc_id, case_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM case_documents"
            " WHERE id=? AND case_id=?",
            (doc_id, case_id))
    if st.session_state.get(
            "case_doc_vs_id") == case_id:
        st.session_state.case_doc_vs = None
        st.session_state.case_doc_vs_id = None


def build_case_doc_vs(case_id):
    if not OPENAI_API_KEY:
        return None
    try:
        with get_db() as conn:
            docs = conn.execute(
                "SELECT filename,text_content"
                " FROM case_documents"
                " WHERE case_id=?",
                (case_id,)).fetchall()
        if not docs:
            return None
        sp = RecursiveCharacterTextSplitter(
            chunk_size=1500, chunk_overlap=300)
        all_d = []
        for d in docs:
            for chunk in sp.split_text(
                    d["text_content"]):
                all_d.append(Document(
                    page_content=chunk,
                    metadata={
                        "source": d["filename"]}))
        if not all_d:
            return None
        return FAISS.from_documents(
            all_d, OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=OPENAI_API_KEY))
    except Exception:
        return None


def get_case_doc_vs(case_id):
    if (st.session_state.get(
            "case_doc_vs_id") == case_id
            and st.session_state.get(
                "case_doc_vs") is not None):
        return st.session_state.case_doc_vs
    vs = build_case_doc_vs(case_id)
    st.session_state.case_doc_vs = vs
    st.session_state.case_doc_vs_id = case_id
    return vs


def check_subscription(user):
    if user["role"] == "admin":
        return {"active": True, "status": "admin",
                "days_left": 99999, "message": ""}
    if not user["is_active"]:
        return {"active": False,
                "status": "suspended",
                "days_left": 0,
                "message": user.get(
                    "suspended_reason",
                    "Suspendovan.")}
    if not user.get("subscription_end"):
        return {"active": False,
                "status": "no_sub",
                "days_left": 0,
                "message": "Nema pretplate."}
    try:
        end = date.fromisoformat(
            user["subscription_end"])
    except Exception:
        return {"active": False,
                "status": "error",
                "days_left": 0,
                "message": "Greska."}
    dl = (end - date.today()).days
    if dl < -GRACE_PERIOD_DAYS:
        return {"active": False,
                "status": "expired",
                "days_left": dl,
                "message":
                    f"Istekla pre {abs(dl)}d."}
    if dl < 0:
        return {"active": True,
                "status": "grace",
                "days_left": dl,
                "message":
                    f"Istekla! Jos "
                    f"{GRACE_PERIOD_DAYS + dl}d."}
    if dl <= 7:
        return {"active": True,
                "status": "expiring",
                "days_left": dl,
                "message": f"Istice za {dl}d."}
    return {"active": True,
            "status": "active",
            "days_left": dl, "message": ""}


def run_auto_suspension():
    if st.session_state.get("_susp"):
        return
    try:
        cutoff = (date.today() - timedelta(
            days=GRACE_PERIOD_DAYS)).isoformat()
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET is_active=0,"
                "auto_suspended=1,"
                "suspended_reason="
                "'Auto: istekla'"
                " WHERE role='user'"
                " AND is_active=1"
                " AND subscription_end<?",
                (cutoff,))
        st.session_state["_susp"] = True
    except Exception:
        pass


def log_action(uid, action, details=""):
    try:
        safe = re.sub(
            r'[a-zA-Z0-9._%+-]+@[^\s]+',
            '[EMAIL]',
            (details or "")[:80])
        with get_db() as conn:
            conn.execute(
                "INSERT INTO usage_logs"
                "(user_id,action,details)"
                "VALUES(?,?,?)",
                (uid, action, safe))
    except Exception:
        pass


def get_llm(temp=0.1, tokens=4096):
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=OPENAI_API_KEY,
        temperature=temp,
        max_tokens=tokens)


def detect_language(text):
    s = text.lower()[:2000]
    if len(re.findall(r'[а-яА-Я]', s)) > len(s) * 0.1:
        return "sr"
    al = sum(1 for m in ['është', 'dhe', 'për']
             if m in s)
    en = sum(1 for m in ['the', 'and', 'for']
             if m in s)
    sr = sum(1 for m in [' je ', ' su ', 'zakon']
             if m in s)
    sc = {"al": al, "en": en, "sr": sr}
    b = max(sc, key=sc.get)
    return b if sc[b] >= 2 else "sr"


def extract_pdf(file):
    try:
        r = PdfReader(file)
        return "\n\n".join(
            f"[Strana {i+1}]\n{p.extract_text()}"
            for i, p in enumerate(r.pages)
            if p.extract_text())
    except Exception:
        return ""
def ai_extract_metadata(text_preview):
    """AI ekstrakcija metapodataka iz teksta
    prve strane PDF-a."""
    if not OPENAI_API_KEY or not text_preview:
        return None

    prompt = """Analiziraj sledeći tekst sa prve strane pravnog dokumenta sa Kosova.
Vrati ISKLJUČIVO validan JSON bez ikakvih komentara ili objašnjenja.

Ako neki podatak nije pronađen, stavi null.
Ne izmišljaj podatke koji ne postoje u tekstu.

Vrati JSON sa ovim poljima:
{
  "title": "pun naziv dokumenta na srpskom ili originalnom jeziku",
  "title_al": "naziv na albanskom ako postoji, inače null",
  "short_name": "skraćenica ako je očigledna (npr. ZOR, ZOO, KZ), inače null",
  "document_number": "broj dokumenta ako postoji (npr. 03/L-212), inače null",
  "legal_area": "jedna od: Ustavno pravo, Krivično pravo, Krivični postupak, Građansko pravo, Parnični postupak, Upravno pravo, Radno pravo, Porodično pravo, Prekršajno pravo, Obligaciono pravo, Imovinsko pravo, Ostalo",
  "gazette_info": "informacija o službenom glasniku ako postoji, inače null",
  "effective_date": "datum stupanja na snagu ako postoji, inače null",
  "document_type": "jedna od: law, amendment_law, bylaw, other",
  "hierarchy_level": 3,
  "is_amendment": false,
  "is_bylaw": false,
  "related_parent_title": "naziv osnovnog zakona ako je ovo izmena/dopuna ili podzakonski akt, inače null",
  "relation_type": "jedna od: amends, issued_under, none"
}

PRAVILA ZA KLASIFIKACIJU:
- Ako naslov sadrži "ZAKON O IZMENAMA" ili "IZMENA I DOPUNA" → document_type: "amendment_law", is_amendment: true
- Ako naslov sadrži "ADMINISTRATIVNO UPUTSTVO" ili "UREDBA" ili "PRAVILNIK" → document_type: "bylaw", is_bylaw: true, hierarchy_level: 4
- Ako je USTAV → hierarchy_level: 1
- Ako je ZAKON → hierarchy_level: 3
- Ako je MEĐUNARODNI SPORAZUM → hierarchy_level: 2

TEKST DOKUMENTA:
""" + text_preview[:3000]

    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=OPENAI_API_KEY,
            temperature=0.0, max_tokens=1000)
        response = llm.invoke(
            [HumanMessage(content=prompt)]).content

        # Očisti response — izvuci JSON
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(
                r'^```(?:json)?\s*', '',
                response)
            response = re.sub(
                r'\s*```$', '', response)

        meta = json.loads(response)
        return meta
    except json.JSONDecodeError:
        return None
    except Exception:
        return None

def ocr_image(image_bytes):
    b64 = base64.b64encode(
        image_bytes).decode('utf-8')
    try:
        client = openai.OpenAI(
            api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": [
                {"type": "text",
                 "text": "Izvuci KOMPLETAN tekst"
                         " sa slike."},
                {"type": "image_url",
                 "image_url": {
                     "url": "data:image/jpeg;"
                            f"base64,{b64}"}}]}],
            max_tokens=4096)
        return r.choices[0].message.content
    except Exception as e:
        return f"OCR greska: {e}"


def process_upload(file):
    name = file.name
    ext = (name.lower().rsplit('.', 1)[-1]
           if '.' in name else '')
    if ext == 'pdf':
        text = extract_pdf(file)
    elif ext == 'txt':
        raw = file.read()
        text = ""
        for enc in ['utf-8', 'latin-1', 'cp1250']:
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        if not text:
            text = raw.decode(
                'utf-8', errors='replace')
    elif ext in ('jpg', 'jpeg', 'png',
                 'gif', 'webp'):
        img = Image.open(file).convert("RGB")
        if img.width > 2000:
            img = img.resize(
                (2000,
                 int(img.height * 2000
                     / img.width)),
                Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        text = ocr_image(buf.getvalue())
    else:
        return "", name, "sr"
    lang = detect_language(text) if text else "sr"
    return text, name, lang


def translate_full(text, lang):
    if lang == "sr":
        return text
    llm = get_llm(temp=0.05, tokens=8000)
    if len(text) < 6000:
        try:
            return llm.invoke([HumanMessage(
                content="Prevedi na srpski:\n"
                        + text)]).content
        except Exception as e:
            return f"Greska: {e}"
    chunks = []
    cur = ""
    for s in re.split(r'(?<=[.!?])\s+', text):
        if len(cur) + len(s) < 4000:
            cur += s + " "
        else:
            if cur.strip():
                chunks.append(cur.strip())
            cur = s + " "
    if cur.strip():
        chunks.append(cur.strip())
    parts = []
    for i, ch in enumerate(chunks):
        try:
            parts.append(llm.invoke(
                [HumanMessage(
                    content="Prevedi na srpski:\n"
                            + ch)]).content)
        except Exception as e:
            parts.append(f"[Greska {i+1}: {e}]")
    return "\n\n".join(parts)


def create_word(title, body):
    doc = DocxDocument()
    doc.styles['Normal'].font.name = 'Arial'
    doc.styles['Normal'].font.size = Pt(11)
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("PRAVA KOLEVKA")
    r.bold = True
    r.font.size = Pt(14)
    doc.add_paragraph("")
    doc.add_heading(title, level=1)
    for p in body.split("\n"):
        s = p.strip()
        if s.startswith("## "):
            doc.add_heading(s[3:], level=2)
        elif s.startswith("- "):
            doc.add_paragraph(
                s[2:], style='List Bullet')
        elif s:
            doc.add_paragraph(s)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def create_stripe_checkout(plan_key, user_email):
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        return None
    plan = PLANS.get(plan_key)
    if not plan or not plan.get("stripe_price"):
        return None
    try:
        stripe_lib.api_key = STRIPE_SECRET_KEY
        session = stripe_lib.checkout.Session.create(
            payment_method_types=["card"],
            customer_email=user_email,
            line_items=[{
                "price": plan["stripe_price"],
                "quantity": 1}],
            mode="subscription",
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL)
        return session.url
    except Exception:
        return None


LEGAL_DICT = {
    "Gjykata Themelore": "Osnovni sud",
    "Vendim": "Odluka",
    "Aktvendim": "Resenje",
    "Ankese": "Zalba",
    "Ligj": "Zakon",
    "Neni": "Clan",
    "Afat": "Rok",
}

DOC_TEMPLATES = {
    "zalba": {
        "name": "Zalba", "icon": "Z",
        "prompt": "Napisi zalbu za Kosovo."
                  " Info:\n{info}\nSrpski."},
    "tuzba": {
        "name": "Tuzba", "icon": "T",
        "prompt": "Napisi tuzbu za Kosovo."
                  " Info:\n{info}\nSrpski."},
    "zahtev": {
        "name": "Zahtev", "icon": "Z",
        "prompt": "Napisi zahtev za Kosovo."
                  " Info:\n{info}\nSrpski."},
    "punomocje": {
        "name": "Punomocje", "icon": "P",
        "prompt": "Napisi punomocje SR+AL."
                  " Info:\n{info}"},
}
# ═══════════════════════════════════════════════════════════════
#  CSS + LOGIN + ADMIN
# ═══════════════════════════════════════════════════════════════

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@300;400;500;600;700&display=swap');
body,p,h1,h2,h3,h4,h5,h6,div,input,textarea,button,label,a{{font-family:'Inter',sans-serif!important}}
.stApp{{background:{SURFACE}!important}}
#MainMenu,footer,header{{visibility:hidden}}
[data-testid="stSidebar"]{{display:none!important}}
.login-box{{max-width:420px;margin:8vh auto;padding:2.5rem;background:{CARD_BG};border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);border:1px solid {BORDER}}}
.login-logo{{text-align:center;margin-bottom:2rem}}
.login-logo h1{{font-family:'Playfair Display',serif!important;font-size:1.8rem;margin:0}}
.login-logo .brand-prava{{color:{PRIMARY}}}
.login-logo .brand-kolevka{{color:{ACCENT}}}
.login-logo p{{color:{TEXT_SECONDARY};font-size:.85rem;margin-top:4px}}
.top-bar{{background:{PRIMARY};color:white;padding:.875rem 1.5rem;display:flex;justify-content:space-between;align-items:center;border-radius:0 0 12px 12px;margin:-1rem -1rem 1.5rem -1rem;box-shadow:0 2px 8px rgba(0,0,0,.12);flex-wrap:wrap;gap:8px}}
.top-bar h2{{font-family:'Playfair Display',serif!important;margin:0;font-size:1.2rem;display:flex;align-items:center;gap:4px}}
.top-bar .accent{{color:{ACCENT}}}
.badge{{background:rgba(255,255,255,.15);padding:3px 10px;border-radius:6px;font-weight:500;font-size:.78rem}}
.badge-active{{background:{ACCENT};color:white;font-weight:600}}
.badge-warn{{background:{WARNING_C};color:white}}
.badge-err{{background:{ERROR_C};color:white}}
.pk-card{{background:{CARD_BG};border-radius:12px;padding:1.5rem;margin:.75rem 0;border:1px solid {BORDER}}}
.pk-card-accent{{background:{CARD_BG};border-radius:12px;padding:1.5rem;margin:.75rem 0;border-left:3px solid {ACCENT};border-top:1px solid {BORDER};border-right:1px solid {BORDER};border-bottom:1px solid {BORDER}}}
.pk-card h3,.pk-card-accent h3{{font-family:'Playfair Display',serif!important;color:{PRIMARY};margin-top:0}}
.stButton>button{{border-radius:8px!important;font-weight:600!important;border:none!important;background:{PRIMARY}!important;color:white!important;transition:background .2s!important}}
.stButton>button:hover{{background:{PRIMARY_DARK}!important}}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{{border-radius:8px!important;border:1px solid {BORDER}!important}}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{{border-color:{ACCENT}!important;box-shadow:0 0 0 1px {ACCENT}!important}}
.stTabs [data-baseweb="tab-list"]{{gap:0;background:transparent;border-bottom:1px solid {BORDER};padding:0;border-radius:0}}
.stTabs [data-baseweb="tab"]{{border-radius:0!important;font-weight:500!important;color:{TEXT_SECONDARY}!important;border-bottom:2px solid transparent!important;padding:.5rem 1rem!important;background:transparent!important}}
.stTabs [aria-selected="true"]{{color:{PRIMARY}!important;background:transparent!important;border-bottom:2px solid {ACCENT}!important;font-weight:600!important}}
.stFileUploader>div{{border-radius:10px!important;border:1px dashed {BORDER}!important;background:{SURFACE}!important}}
[data-testid="stChatMessage"]{{border-radius:12px!important;word-wrap:break-word!important;overflow-wrap:break-word!important}}
[data-testid="stExpander"]{{border:1px solid {BORDER}!important;border-radius:8px!important}}
[data-testid="stExpander"] summary{{word-wrap:break-word!important;overflow-wrap:break-word!important}}
@media(max-width:768px){{.top-bar{{padding:.5rem .75rem}}.top-bar h2{{font-size:1rem}}}}
</style>
"""


def render_login():
    st.markdown(
        '<div class="login-box">'
        '<div class="login-logo">'
        f'{SCALE_SVG_LOGIN}'
        '<h1><span class="brand-prava">Prava</span> '
        '<span class="brand-kolevka">Kolevka</span></h1>'
        '<p>Pravni AI za Kosovo</p>'
        '</div></div>',
        unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login", clear_on_submit=False):
            email = st.text_input("Email")
            pw = st.text_input(
                "Lozinka", type="password")
            if st.form_submit_button(
                    "Prijavi se",
                    use_container_width=True):
                if not email or not pw:
                    st.error("Unesite podatke.")
                else:
                    u = authenticate_user(email, pw)
                    if u:
                        st.session_state.current_user = u
                        st.session_state.logged_in = True
                        st.session_state.login_time = \
                            datetime.now()
                        try:
                            with get_db() as conn:
                                conn.execute(
                                    "UPDATE users"
                                    " SET last_login=?"
                                    " WHERE id=?",
                                    (datetime.now()
                                     .isoformat(),
                                     u["id"]))
                        except Exception:
                            pass
                        log_action(u["id"], "login")
                        st.rerun()
                    else:
                        st.error(
                            "Pogrešni podaci.")
    render_footer()

def do_logout():
    uid = None
    cu = st.session_state.get("current_user")
    if cu and isinstance(cu, dict):
        uid = cu.get("id")
    if uid:
        log_action(uid, "logout")
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    init_ss()


def check_session_timeout():
    lt = st.session_state.get("login_time")
    if not lt:
        return False
    return ((datetime.now() - lt)
            .total_seconds() / 60
            > SESSION_TIMEOUT_MINUTES)


def render_admin():
    st.markdown(
        '<div class="top-bar">'
        '<div style="display:flex;'
        'align-items:center;gap:8px">'
        f'{SCALE_SVG_HEADER}'
        '<h2>Prava <span class="accent">'
        'Kolevka</span></h2>'
        '</div>'
        '<span class="badge badge-active">'
        'ADMIN</span></div>',
        unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(
        ["Pregled", "Zakoni", "Korisnici",
         "Uplate", "Podešavanja"])
    with t1:
        admin_dashboard()
    with t2:
        admin_laws()
    with t3:
        admin_users()
    with t4:
        admin_payments()
    with t5:
        admin_settings()
    if st.button("Odjavi se", key="adm_out"):
        do_logout()
        st.rerun()
    render_footer()


def admin_dashboard():
    try:
        with get_db() as conn:
            active = conn.execute(
                "SELECT COUNT(*) c FROM users"
                " WHERE role='user'"
                " AND is_active=1"
            ).fetchone()["c"]
            ms = date.today().replace(
                day=1).isoformat()
            rev = conn.execute(
                "SELECT COALESCE(SUM(amount),0) s"
                " FROM payments"
                " WHERE status='completed'"
                " AND payment_date>=?",
                (ms,)).fetchone()["s"]
            nl = conn.execute(
                "SELECT COUNT(*) c FROM laws"
                " WHERE is_active=1"
            ).fetchone()["c"]
            na = conn.execute(
                "SELECT COUNT(*) c"
                " FROM law_articles"
            ).fetchone()["c"]
    except Exception as e:
        st.error(f"{e}")
        return
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in [
            (c1, str(active), "Aktivnih korisnika"),
            (c2, f"€{rev:.0f}", "Prihod ovog meseca"),
            (c3, str(nl), "Ukupno zakona"),
            (c4, str(na), "Ukupno članova")]:
        with col:
            st.metric(lbl, val)

    # Statistika po pravnoj snazi
    st.markdown("### Pravni akti po vrsti")
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT hierarchy_level,"
                " COUNT(*) as cnt"
                " FROM laws"
                " WHERE is_active=1"
                " GROUP BY hierarchy_level"
                " ORDER BY hierarchy_level"
            ).fetchall()
        if rows:
            cols = st.columns(len(rows))
            for i, row in enumerate(rows):
                row = dict(row)
                hl = row.get("hierarchy_level", 3)
                hi = HIERARCHY_LEVELS.get(
                    hl, HIERARCHY_LEVELS[3])
                with cols[i]:
                    st.metric(
                        hi["name"],
                        f"{row['cnt']} akata")
    except Exception:
        pass

    # Supabase status
    with st.expander("Supabase status"):
        if st.button("Testiraj konekciju",
                     key="sb_test"):
            try:
                from supabase_db import (
                    sb_test_connection)
                status = sb_test_connection()
                if status["connected"]:
                    st.success(
                        f"Povezano! "
                        f"{status['laws_count']}"
                        f" zakona, "
                        f"{status['articles_count']}"
                        f" članova")
                    for l in status.get(
                            "laws", []):
                        st.text(l)
                    st.text(
                        status.get(
                            "test_article", ""))
                else:
                    st.error(
                        f"Greška: "
                        f"{status.get('error')}")
            except Exception as e:
                st.error(f"{e}")

    # Debug retrieval
    with st.expander("Test pretrage"):
        test_q = st.text_input(
            "Test upit",
            placeholder="neisplaćena zarada...",
            key="debug_query")
        if test_q and st.button(
                "Testiraj",
                key="debug_search"):
            res = search_laws(test_q, 10)
            if res:
                st.success(
                    f"{len(res)} rezultata")
                for i, r in enumerate(res):
                    src = safe_text(
                        r.get('short_name')
                        or r.get('name_sr', ''))
                    art = r.get(
                        'article_number', '?')
                    sc = r.get('score', 0)
                    ttl = safe_text(
                        r.get('title', ''))
                    area = r.get('area', '')
                    pen = (" [PEN]"
                           if r.get('_penalized')
                           else "")
                    st.text(
                        f"#{i+1} [{sc}]{pen}"
                        f" {src} čl.{art}"
                        f" | {area}"
                        f" | {ttl}")
                    with st.expander(
                            f"Sadržaj #{i+1}",
                            expanded=False):
                        st.text(
                            r.get('content',
                                  '')[:300])
            else:
                st.warning("0 rezultata")

def admin_laws():
    st.markdown("### Zakoni")

    with st.expander("Test: sb_find_parent_law"):
        hint = st.text_input(
            "Unesi hint za parent zakon",
            placeholder="npr. radu, ZOR, 03/L-212...",
            key="parent_test_hint")
        if hint and st.button(
                "Traži", key="parent_test_btn"):
            try:
                results = sb_find_parent_law(hint)
                if results:
                    st.success(
                        f"{len(results)} rezultata")
                    st.json(results)
                else:
                    st.warning("Nema rezultata.")
            except Exception as e:
                st.error(f"Greška: {e}")

    if st.session_state.get("_save_law"):
        st.session_state["_save_law"] = False
        m = st.session_state.get("preview_meta")
        if m and m.get("name_sr") and m.get("full_text"):
            law_data = {
                "name_sr": m.get("name_sr", ""),
                "name_al": m.get("name_al", ""),
                "short_name": m.get("short_name", ""),
                "law_number": m.get("law_number", ""),
                "area": m.get("area", "Ostalo"),
                "gazette_info": m.get("gazette_info", ""),
                "effective_date": m.get("effective_date", ""),
                "is_active": True,
                "language": "sr",
                "full_text": m.get("full_text", ""),
                "hierarchy_level": m.get("hierarchy_level", 3),
                "document_type": m.get("document_type", "law"),
                "is_amendment": m.get("is_amendment", False),
                "is_bylaw": m.get("is_bylaw", False),
                "relation_type": m.get("relation_type", "none"),
                "is_consolidated": False,
            }
            parent_id = m.get("parent_law_id")
            if parent_id:
                law_data["parent_law_id"] = parent_id
            articles, warnings = parse_articles(
                m.get("full_text", ""))
            try:
                lid, num = sb_save_law_with_articles(
                    law_data, articles)
                if lid:
                    st.success(
                        f"Zakon sačuvan: {num}"
                        " članova u Supabase")
                    for w in warnings:
                        st.warning(w)
                    st.session_state.preview_articles = None
                    st.session_state.preview_warnings = None
                    st.session_state.preview_meta = None
                    st.session_state.ai_metadata = None
                    st.session_state.law_vs = None
                    st.session_state.law_vs_version = ""
                    st.rerun()
                else:
                    st.error("Greška pri čuvanju.")
            except Exception as e:
                st.error(f"Greška: {e}")
        else:
            st.error("Nedostaju podaci za čuvanje.")

    with st.expander("Dodaj novi zakon",
                     expanded=False):
        method = st.radio(
            "Način unosa",
            ["PDF", "Tekst"],
            horizontal=True,
            key="law_input_method")

        full_text = ""

        if method == "PDF":
            pdf_file = st.file_uploader(
                "Upload PDF zakona",
                type=["pdf"],
                key="al_pdf")

            if pdf_file is not None:
                pkey = (f"_pdf_text_{pdf_file.name}"
                        f"_{pdf_file.size}")
                if pkey not in st.session_state:
                    with st.spinner("Čitam PDF..."):
                        st.session_state[pkey] = \
                            extract_pdf(pdf_file)
                full_text = st.session_state.get(
                    pkey, "")

                if full_text:
                    st.success(
                        f"Izvučeno {len(full_text)}"
                        " karaktera")

                    ai_key = f"_ai_meta_{pkey}"
                    if ai_key not in st.session_state:
                        if st.button(
                                "AI analiza dokumenta",
                                use_container_width=True,
                                type="primary",
                                key="ai_analyze"):
                            with st.spinner(
                                    "AI analizira"
                                    " dokument..."):
                                meta = ai_extract_metadata(
                                    full_text)
                                if meta:
                                    st.session_state[
                                        ai_key] = meta
                                    st.rerun()
                                else:
                                    st.error(
                                        "AI nije mogao"
                                        " da obradi"
                                        " dokument.")

                    ai_meta = st.session_state.get(ai_key)
                    if ai_meta:
                        st.markdown("#### AI predlog metapodataka")

                        doc_type = ai_meta.get("document_type", "law")
                        type_labels = {
                            "law": "Osnovni zakon",
                            "amendment_law": "Izmena i dopuna",
                            "bylaw": "Podzakonski akt",
                            "other": "Ostalo"}
                        st.info(
                            f"Tip: **"
                            f"{type_labels.get(doc_type, doc_type)}"
                            f"**")

                        if ai_meta.get("is_amendment"):
                            st.warning(
                                "Dokument je klasifikovan"
                                " kao IZMENA I DOPUNA")
                        if ai_meta.get("is_bylaw"):
                            st.warning(
                                "Dokument je klasifikovan"
                                " kao PODZAKONSKI AKT")

                        c1, c2 = st.columns(2)
                        with c1:
                            name_sr = st.text_input(
                                "Naziv zakona",
                                value=ai_meta.get("title", ""),
                                key="al_name")
                            short = st.text_input(
                                "Skraćenica",
                                value=ai_meta.get("short_name", "") or "",
                                key="al_short")
                            hl_val = ai_meta.get("hierarchy_level", 3)
                            hl_keys = list(HIERARCHY_LEVELS.keys())
                            hl_idx = (
                                hl_keys.index(hl_val)
                                if hl_val in hl_keys
                                else 2)
                            hlevel = st.selectbox(
                                "Pravna snaga",
                                hl_keys,
                                index=hl_idx,
                                format_func=lambda x: (
                                    HIERARCHY_LEVELS[x]['name']),
                                key="al_hl")
                            ai_area = ai_meta.get("legal_area", "Ostalo")
                            area_idx = (
                                LEGAL_AREAS.index(ai_area)
                                if ai_area in LEGAL_AREAS
                                else len(LEGAL_AREAS) - 1)
                            area = st.selectbox(
                                "Oblast prava",
                                LEGAL_AREAS,
                                index=area_idx,
                                key="al_area")
                            gazette = st.text_input(
                                "Službeni glasnik",
                                value=ai_meta.get("gazette_info", "") or "",
                                key="al_gazette")
                        with c2:
                            lawnum = st.text_input(
                                "Broj zakona",
                                value=ai_meta.get("document_number", "") or "",
                                key="al_num")
                            name_al = st.text_input(
                                "Naziv na albanskom",
                                value=ai_meta.get("title_al", "") or "",
                                key="al_nameal")
                            eff_date = st.text_input(
                                "Datum stupanja na snagu",
                                value=ai_meta.get("effective_date", "") or "",
                                key="al_effdate")
                            dt_opts = [
                                "law", "amendment_law",
                                "bylaw", "other"]
                            dt_idx = (
                                dt_opts.index(doc_type)
                                if doc_type in dt_opts
                                else 0)
                            doc_type_sel = st.selectbox(
                                "Tip dokumenta",
                                dt_opts,
                                index=dt_idx,
                                format_func=lambda x: type_labels.get(x, x),
                                key="al_doctype")

                        parent_id = None
                        rel_type = "none"

                        if doc_type_sel in ("amendment_law", "bylaw"):
                            st.markdown(
                                "#### Povezivanje sa osnovnim zakonom")
                            parent_hint = ai_meta.get(
                                "related_parent_title", "")
                            if parent_hint:
                                st.info(
                                    f"AI predlog: **{parent_hint}**")
                            search_parent = st.text_input(
                                "Pretraži osnovni zakon",
                                value=parent_hint or "",
                                key="parent_search")
                            if search_parent:
                                try:
                                    candidates = sb_find_parent_law(
                                        search_parent)
                                    if candidates:
                                        opts = {0: "(Bez povezivanja)"}
                                        for c in candidates:
                                            opts[c["id"]] = (
                                                f"{c['name_sr']}"
                                                f" ({c.get('short_name', '')})"
                                                f" {c.get('law_number', '')}")
                                        sel_parent = st.selectbox(
                                            "Izaberi osnovni zakon",
                                            list(opts.keys()),
                                            format_func=lambda x: opts[x],
                                            key="parent_sel")
                                        if sel_parent:
                                            parent_id = sel_parent
                                    else:
                                        st.warning("Nije pronađen u bazi.")
                                except Exception:
                                    pass
                            if doc_type_sel == "amendment_law":
                                rel_type = "amends"
                            elif doc_type_sel == "bylaw":
                                rel_type = "issued_under"

                        if st.button(
                                "Preview članova",
                                use_container_width=True,
                                key="preview_btn"):
                            arts, warns = parse_articles(full_text)
                            st.session_state.preview_articles = arts
                            st.session_state.preview_warnings = warns
                            st.session_state.preview_meta = {
                                "name_sr": name_sr,
                                "name_al": name_al,
                                "short_name": short,
                                "law_number": lawnum,
                                "area": area,
                                "hierarchy_level": hlevel,
                                "gazette_info": gazette,
                                "effective_date": eff_date,
                                "full_text": full_text,
                                "document_type": doc_type_sel,
                                "is_amendment": doc_type_sel == "amendment_law",
                                "is_bylaw": doc_type_sel == "bylaw",
                                "is_consolidated": False,
                                "parent_law_id": parent_id,
                                "relation_type": rel_type,
                            }

                        if st.session_state.get(
                                "preview_articles") is not None:
                            arts = st.session_state.preview_articles
                            warns = st.session_state.get(
                                "preview_warnings", [])
                            st.success(f"{len(arts)} članova")
                            for w in (warns or []):
                                st.warning(w)
                            for a in arts[:5]:
                                t = (f" - {a['title']}"
                                     if a.get('title') else "")
                                st.text(
                                    f"Čl. {a['article_number']}{t}:"
                                    f" {safe_text(a['content'][:200])}...")
                            if len(arts) > 5:
                                st.info(f"...i još {len(arts) - 5}")
                            if st.button(
                                    "Sačuvaj zakon",
                                    use_container_width=True,
                                    type="primary",
                                    key="save_law_btn"):
                                st.session_state["_save_law"] = True
                                st.rerun()
                    else:
                        st.info(
                            "Kliknite 'AI analiza dokumenta'"
                            " za automatsko popunjavanje.")
                else:
                    st.error("Nije moguće pročitati PDF.")

        else:
            c1, c2 = st.columns(2)
            with c1:
                name_sr = st.text_input(
                    "Naziv zakona",
                    key="al_name_manual")
                short = st.text_input(
                    "Skraćenica",
                    key="al_short_manual")
                hlevel = st.selectbox(
                    "Pravna snaga",
                    list(HIERARCHY_LEVELS.keys()),
                    index=2,
                    format_func=lambda x: (
                        HIERARCHY_LEVELS[x]['name']),
                    key="al_hl_manual")
                area = st.selectbox(
                    "Oblast prava", LEGAL_AREAS,
                    key="al_area_manual")
                gazette = st.text_input(
                    "Službeni glasnik / izvor",
                    key="al_gazette_manual")
            with c2:
                lawnum = st.text_input(
                    "Broj zakona",
                    key="al_num_manual")
                name_al = st.text_input(
                    "Naziv na albanskom",
                    key="al_nameal_manual")
                eff_date = st.text_input(
                    "Datum stupanja na snagu",
                    key="al_effdate_manual")
            full_text = st.text_area(
                "Tekst zakona", height=400,
                key="al_text_manual")

            if st.button(
                    "Preview",
                    disabled=not full_text,
                    use_container_width=True,
                    key="preview_btn_manual"):
                arts, warns = parse_articles(full_text)
                st.session_state.preview_articles = arts
                st.session_state.preview_warnings = warns
                st.session_state.preview_meta = {
                    "name_sr": name_sr,
                    "name_al": name_al,
                    "short_name": short,
                    "law_number": lawnum,
                    "area": area,
                    "hierarchy_level": hlevel,
                    "gazette_info": gazette,
                    "effective_date": eff_date,
                    "full_text": full_text,
                    "document_type": "law",
                    "is_amendment": False,
                    "is_bylaw": False,
                    "parent_law_id": None,
                    "relation_type": "none",
                }

            if st.session_state.get(
                    "preview_articles") is not None:
                arts = st.session_state.preview_articles
                warns = st.session_state.get(
                    "preview_warnings", [])
                st.success(f"{len(arts)} članova")
                for w in (warns or []):
                    st.warning(w)
                for a in arts[:5]:
                    t = (f" - {a['title']}"
                         if a.get('title') else "")
                    st.text(
                        f"Čl. {a['article_number']}{t}:"
                        f" {safe_text(a['content'][:200])}...")
                if len(arts) > 5:
                    st.info(f"...i još {len(arts) - 5}")
                if st.button(
                        "Sačuvaj zakon",
                        use_container_width=True,
                        type="primary",
                        key="save_law_btn_manual"):
                    st.session_state["_save_law"] = True
                    st.rerun()

    with st.expander("Export"):
        if st.button("Izvezi sve (JSON)"):
            data = export_laws_json()
            st.download_button(
                "Preuzmi",
                data=data,
                file_name=(f"backup_{date.today()}.json"),
                mime="application/json")

    st.markdown("### Zakoni u bazi")
    search_q = st.text_input(
        "Pretraži zakone",
        placeholder="Naziv, skraćenica, broj...",
        key="admin_law_search")

    try:
        with get_db() as conn:
            if search_q and search_q.strip():
                sq = f"%{search_q.strip()}%"
                laws = conn.execute(
                    "SELECT l.id, l.name_sr,"
                    " l.short_name,"
                    " l.law_number, l.area,"
                    " l.hierarchy_level,"
                    " l.gazette_info,"
                    " l.effective_date,"
                    " COUNT(la.id) as num_articles"
                    " FROM laws l"
                    " LEFT JOIN law_articles la"
                    " ON l.id=la.law_id"
                    " WHERE l.is_active=1"
                    " AND (l.name_sr LIKE ?"
                    " OR l.short_name LIKE ?"
                    " OR l.law_number LIKE ?"
                    " OR l.area LIKE ?)"
                    " GROUP BY l.id"
                    " ORDER BY l.hierarchy_level,"
                    " l.name_sr",
                    (sq, sq, sq, sq)).fetchall()
            else:
                laws = conn.execute(
                    "SELECT l.id, l.name_sr,"
                    " l.short_name,"
                    " l.law_number, l.area,"
                    " l.hierarchy_level,"
                    " l.gazette_info,"
                    " l.effective_date,"
                    " COUNT(la.id) as num_articles"
                    " FROM laws l"
                    " LEFT JOIN law_articles la"
                    " ON l.id=la.law_id"
                    " WHERE l.is_active=1"
                    " GROUP BY l.id"
                    " ORDER BY l.hierarchy_level,"
                    " l.name_sr").fetchall()
    except Exception:
        laws = []

    if not laws:
        st.info("Nema zakona u bazi.")
        return

    cur_lvl = None
    for law in laws:
        law = dict(law)
        hl = law.get('hierarchy_level', 3)
        hi = HIERARCHY_LEVELS.get(hl, HIERARCHY_LEVELS[3])
        if hl != cur_lvl:
            cur_lvl = hl
            st.markdown(f"**{hi['name']}**")
        na = law.get('num_articles', 0)
        sn = safe_text(law.get('short_name', ''))
        ln = safe_text(law.get('law_number', ''))
        ar = safe_text(law.get('area', ''))
        name = safe_text(law.get('name_sr', ''))
        gi = safe_text(law.get('gazette_info', ''))
        info_parts = []
        if ln:
            info_parts.append(ln)
        if sn:
            info_parts.append(sn)
        if ar:
            info_parts.append(ar)
        if gi:
            info_parts.append(gi)
        info_parts.append(f"{na} čl.")
        info_str = " | ".join(info_parts)
        lid = law["id"]

        with st.expander(f"{name} — {info_str}"):
            et1, et2, et3 = st.tabs(
                ["Info", "Izmeni podatke", "Izmeni tekst"])

            with et1:
                st.markdown(f"**Pravna snaga:** {hi['name']}")
                if law.get('gazette_info'):
                    st.markdown(f"**Izvor:** {law['gazette_info']}")
                if law.get('effective_date'):
                    st.markdown(f"**Na snagu:** {law['effective_date']}")
                try:
                    with get_db() as conn:
                        arts = conn.execute(
                            "SELECT article_number, title, content"
                            " FROM law_articles"
                            " WHERE law_id=?"
                            " ORDER BY CAST(article_number AS INTEGER)"
                            " LIMIT 5",
                            (lid,)).fetchall()
                    for a in arts:
                        t = (f" - {a['title']}" if a['title'] else "")
                        st.text(
                            f"Čl. {a['article_number']}{t}:"
                            f" {safe_text(a['content'][:150])}")
                except Exception:
                    pass
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Ponovo obradi", key=f"rep_{lid}"):
                        n, w = reparse_law(lid)
                        st.success(f"{n} čl.")
                        for ww in w:
                            st.warning(ww)
                        st.rerun()
                with b2:
                    if st.button("Obriši", key=f"del_{lid}"):
                        with get_db() as conn:
                            conn.execute(
                                "DELETE FROM law_articles WHERE law_id=?",
                                (lid,))
                            conn.execute(
                                "DELETE FROM laws WHERE id=?",
                                (lid,))
                        st.session_state.law_vs = None
                        st.session_state.law_vs_version = ""
                        st.rerun()

            with et2:
                ec1, ec2 = st.columns(2)
                with ec1:
                    ed_name = st.text_input(
                        "Naziv",
                        value=law.get('name_sr', ''),
                        key=f"edn_{lid}")
                    ed_short = st.text_input(
                        "Skraćenica",
                        value=law.get('short_name', ''),
                        key=f"eds_{lid}")
                with ec2:
                    ed_num = st.text_input(
                        "Broj",
                        value=law.get('law_number', ''),
                        key=f"ednum_{lid}")
                    ed_gaz = st.text_input(
                        "Glasnik",
                        value=law.get('gazette_info', ''),
                        key=f"edg_{lid}")
                if st.button(
                        "Sačuvaj izmene",
                        key=f"edsave_{lid}",
                        type="primary"):
                    try:
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE laws SET"
                                " name_sr=?, short_name=?,"
                                " law_number=?, gazette_info=?"
                                " WHERE id=?",
                                (ed_name, ed_short,
                                 ed_num, ed_gaz, lid))
                        st.success("Ažurirano.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"{e}")

            with et3:
                st.warning("Ovo će ponovo obraditi sve članove.")
                try:
                    with get_db() as conn:
                        ft = conn.execute(
                            "SELECT full_text FROM laws WHERE id=?",
                            (lid,)).fetchone()
                    cur_text = (ft["full_text"] if ft else "")
                except Exception:
                    cur_text = ""
                new_text = st.text_area(
                    "Tekst",
                    value=cur_text,
                    height=400,
                    key=f"edtxt_{lid}")
                if st.button(
                        "Sačuvaj tekst",
                        key=f"edtxtsave_{lid}",
                        type="primary"):
                    if new_text.strip():
                        try:
                            with get_db() as conn:
                                conn.execute(
                                    "UPDATE laws SET full_text=?"
                                    " WHERE id=?",
                                    (new_text, lid))
                            n, w = reparse_law(lid)
                            st.success(f"{n} čl.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"{e}")

def admin_users():
    st.markdown("### Korisnici")
    with st.expander("Dodaj"):
        with st.form("add_u"):
            c1, c2 = st.columns(2)
            with c1:
                nn = st.text_input(
                    "Ime", key="nu_n")
                ne = st.text_input(
                    "Email", key="nu_e")
            with c2:
                npl = st.selectbox(
                    "Plan",
                    list(PLANS.keys()),
                    format_func=lambda x: (
                        f"{PLANS[x]['name']}"
                        f" (E{PLANS[x]['price']})"),
                    key="nu_pl")
                nd = st.number_input(
                    "Dana", 1, value=30,
                    key="nu_d")
            npw = st.text_input(
                "Lozinka",
                value="Kolevka2024!",
                key="nu_pw")
            if st.form_submit_button("Kreiraj"):
                if not nn or not ne or not npw:
                    st.error("Popunite.")
                else:
                    try:
                        ph, salt = \
                            create_password_hash(npw)
                        se = (date.today()
                              + timedelta(
                                  days=nd)).isoformat()
                        with get_db() as conn:
                            conn.execute(
                                "INSERT INTO users"
                                "(email,"
                                "password_hash,"
                                "salt,full_name,"
                                "role,plan,"
                                "is_active,"
                                "subscription_start,"
                                "subscription_end)"
                                "VALUES(?,?,?,?,"
                                "'user',?,1,?,?)",
                                (ne.lower().strip(),
                                 ph, salt, nn, npl,
                                 date.today()
                                 .isoformat(), se))
                        st.success(f"Kreiran: {nn}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Email postoji.")
                    except Exception as e:
                        st.error(f"{e}")
    try:
        with get_db() as conn:
            users = conn.execute(
                "SELECT * FROM users"
                " WHERE role='user'"
                " ORDER BY is_active DESC,"
                "full_name").fetchall()
    except Exception:
        return
    for u in users:
        u = dict(u)
        pl = PLANS.get(
            u["plan"],
            {"name": "?", "icon": "?"})
        label = (
            f"{safe_text(u['full_name'])}"
            f" -- {safe_text(u['email'])}")
        with st.expander(label):
            st.markdown(
                f"Plan: {pl['name']}"
                f" | Do: "
                f"{u.get('subscription_end', '-')}"
                f" | {'Aktivan' if u['is_active'] else 'Neaktivan'}")
            c1, c2 = st.columns(2)
            with c1:
                ext = st.number_input(
                    "Dana", 1, value=30,
                    key=f"e_{u['id']}")
                if st.button(
                        "Produzi",
                        key=f"ext_{u['id']}"):
                    curr = (date.fromisoformat(
                        u["subscription_end"])
                        if u.get(
                            "subscription_end")
                        else date.today())
                    ne = (max(curr, date.today())
                          + timedelta(
                              days=ext)).isoformat()
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE users SET"
                            " subscription_end=?,"
                            "is_active=1"
                            " WHERE id=?",
                            (ne, u["id"]))
                    st.rerun()
            with c2:
                if u["is_active"]:
                    if st.button(
                            "Suspenduj",
                            key=f"s_{u['id']}"):
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users"
                                " SET is_active=0"
                                " WHERE id=?",
                                (u["id"],))
                        st.rerun()
                else:
                    if st.button(
                            "Aktiviraj",
                            key=f"a_{u['id']}"):
                        ne = (date.today()
                              + timedelta(
                                  days=30)
                              ).isoformat()
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users"
                                " SET is_active=1,"
                                "subscription_end=?"
                                " WHERE id=?",
                                (ne, u["id"]))
                        st.rerun()


def admin_payments():
    st.markdown("### Uplate")
    with st.expander("Nova uplata"):
        try:
            with get_db() as conn:
                users = conn.execute(
                    "SELECT id,full_name,email"
                    " FROM users"
                    " WHERE role='user'"
                    " ORDER BY full_name"
                ).fetchall()
        except Exception:
            return
        if not users:
            return
        with st.form("pay"):
            opts = {u["id"]:
                    safe_text(u['full_name'])
                    for u in users}
            uid = st.selectbox(
                "Korisnik",
                list(opts.keys()),
                format_func=lambda x: opts[x])
            c1, c2 = st.columns(2)
            with c1:
                amt = st.number_input(
                    "EUR", 1.0, value=19.0)
                pd = st.date_input(
                    "Datum",
                    value=date.today())
            with c2:
                days = st.number_input(
                    "Dana", 1, value=30)
                meth = st.selectbox(
                    "Nacin",
                    ["Transfer", "Gotovina",
                     "PayPal", "Stripe"])
            if st.form_submit_button("Sacuvaj"):
                pe = (pd + timedelta(
                    days=days)).isoformat()
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO payments"
                        "(user_id,amount,"
                        "payment_date,"
                        "period_start,"
                        "period_end,"
                        "method,recorded_by)"
                        "VALUES(?,?,?,?,?,?,?)",
                        (uid, amt,
                         pd.isoformat(),
                         pd.isoformat(), pe,
                         meth,
                         st.session_state
                         .current_user["id"]))
                    conn.execute(
                        "UPDATE users SET"
                        " subscription_end=?,"
                        "is_active=1"
                        " WHERE id=?",
                        (pe, uid))
                st.success(f"E{amt}")
                st.rerun()


def admin_settings():
    st.markdown("### Podesavanja")
    st.markdown(
        f"bcrypt: "
        f"{'Da' if BCRYPT_AVAILABLE else 'Ne'}"
        f" | Stripe: "
        f"{'Da' if STRIPE_SECRET_KEY else 'Ne'}"
        f" | Auto-odjava: "
        f"{SESSION_TIMEOUT_MINUTES // 60}h"
        f" (automatska odjava iz"
        f" bezbednosnih razloga)")
    with st.expander("Promena lozinke"):
        with st.form("chpw"):
            old = st.text_input(
                "Trenutna", type="password")
            new = st.text_input(
                "Nova", type="password")
            conf = st.text_input(
                "Potvrdi", type="password")
            if st.form_submit_button("Promeni"):
                if new != conf:
                    st.error("Ne poklapaju se.")
                elif len(new) < 8:
                    st.error("Min 8.")
                else:
                    u = st.session_state \
                        .current_user
                    ok, _ = verify_password(
                        old,
                        u["password_hash"],
                        u["salt"])
                    if ok:
                        nh, ns = \
                            create_password_hash(
                                new)
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users"
                                " SET"
                                " password_hash=?,"
                                "salt=?"
                                " WHERE id=?",
                                (nh, ns,
                                 u["id"]))
                        st.success("Promenjeno.")
                    else:
                        st.error("Pogresna.")
                     # ═══════════════════════════════════════════════════════════════
#  KORISNICKI PANEL + MAIN
# ═══════════════════════════════════════════════════════════════

def render_user():
    user = st.session_state.current_user
    sub = check_subscription(user)
    if not sub["active"]:
        st.warning(sub["message"])
        if st.button("Odjavi se", key="exp_out"):
            do_logout()
            st.rerun()
        return
    pl = PLANS.get(
        user["plan"],
        {"name": "?", "icon": "?"})
    bc = "badge-active"
    bt = f"{sub['days_left']}d"
    if sub["status"] == "expiring":
        bc = "badge-warn"
    elif sub["status"] == "grace":
        bc = "badge-err"
        bt = "ISTEKLO"
    st.markdown(
        '<div class="top-bar">'
        '<div style="display:flex;'
        'align-items:center;gap:8px">'
        f'{SCALE_SVG_HEADER}'
        '<h2>Prava <span class="accent">'
        'Kolevka</span></h2></div>'
        '<div style="display:flex;gap:8px;'
        'align-items:center;flex-wrap:wrap">'
        f'<span class="badge">'
        f'{safe_html(pl["name"])}</span>'
        f'<span class="badge {bc}">{bt}</span>'
        f'<span class="badge">'
        f'{safe_html(user["full_name"])}</span>'
        '</div></div>',
        unsafe_allow_html=True)
    if sub["message"]:
        st.warning(sub['message'])
    if not OPENAI_API_KEY:
        st.error("AI nije podešen.")
        return

    tabs = st.tabs(
        ["Predmeti", "Pretraga",
         "Prevod", "Podnesci",
         "Most AL-SR", "Pretplata"])
    with tabs[0]:
        tab_cases()
    with tabs[1]:
        tab_search()
    with tabs[2]:
        tab_translate()
    with tabs[3]:
        tab_docs()
    with tabs[4]:
        tab_bridge()
    with tabs[5]:
        tab_subscription()
    render_footer()
    if st.button("Odjavi se", key="usr_out"):
        do_logout()
        st.rerun()


def tab_cases():
    user = st.session_state.current_user
    uid = user["id"]
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>Predmeti</h3>'
        '<p style="color:#6B7280;margin:0">'
        'Svaki predmet ima svoju istoriju'
        ' i dokumente.</p></div>',
        unsafe_allow_html=True)

    cases = get_user_cases(uid)
    c1, c2, c3 = st.columns([4, 2, 1])
    with c1:
        if cases:
            opts = {c["id"]: safe_text(c["title"])
                    for c in cases}
            keys = list(opts.keys())
            active = st.session_state.get(
                "active_case_id")
            idx = 0
            if active in keys:
                idx = keys.index(active)
            sel = st.selectbox(
                "Izaberi predmet", keys,
                index=idx,
                format_func=lambda x: opts[x],
                key="case_sel")
            st.session_state.active_case_id = sel
        else:
            st.info("Nemate predmeta.")
            st.session_state.active_case_id = None
    with c2:
        new_title = st.text_input(
            "Naziv",
            placeholder="Novi predmet...",
            label_visibility="collapsed",
            key="new_case_title")
    with c3:
        if st.button("Kreiraj",
                      use_container_width=True,
                      key="new_case_btn"):
            if new_title and new_title.strip():
                cid = create_case(
                    uid, new_title.strip())
                st.session_state \
                    .active_case_id = cid
                st.rerun()
            else:
                st.error("Unesite naziv.")

    active_id = st.session_state.get(
        "active_case_id")
    if not active_id:
        return

    with st.expander("Opcije predmeta"):
        if st.button(
                "Obrisi ovaj predmet",
                key="del_case"):
            delete_case(active_id, uid)
            st.rerun()

    case_docs = get_case_documents(active_id)
    with st.expander(
            f"Dokumenti ({len(case_docs)})"):
        uploaded = st.file_uploader(
            "Dodaj dokument",
            type=["pdf", "txt", "jpg", "jpeg",
                  "png", "gif", "webp"],
            accept_multiple_files=True,
            key=f"doc_up_{active_id}")
        if uploaded:
            existing_names = [
                d["filename"] for d in case_docs]
            for f in uploaded:
                if f.name not in existing_names:
                    with st.spinner(
                            f"Obrada {f.name}..."):
                        text, name, lang = \
                            process_upload(f)
                        if text and not text.startswith(
                                "OCR greska"):
                            add_case_document(
                                active_id, name,
                                text, lang)
                            st.success(
                                f"Dodato: {name}")
                        elif text:
                            st.error(text)
            st.rerun()
        if case_docs:
            for d in case_docs:
                dc1, dc2 = st.columns([5, 1])
                with dc1:
                    sz = d.get('size', 0) or 0
                    st.text(
                        f"{safe_text(d['filename'])}"
                        f" ({sz // 1000}KB)")
                with dc2:
                    if st.button(
                            "X",
                            key=f"deldoc_{d['id']}"):
                        delete_case_document(
                            d['id'], active_id)
                        st.rerun()
        else:
            st.text("Nema dokumenata.")

    messages = get_case_messages(active_id)
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        sources = msg.get(
            "sources_html", "") or ""
        with st.chat_message(role):
            st.markdown(content)
            if sources.strip():
                st.markdown(
                    sources,
                    unsafe_allow_html=True)

    if not messages:
        sugs = [
            "Koja je kazna za kradju po KZ?",
            "Rokovi za zalbu?",
            "Koja prava garantuje Ustav?"]
        cols = st.columns(3)
        for i, s in enumerate(sugs):
            with cols[i]:
                if st.button(
                        s, key=f"sug_{i}",
                        use_container_width=True):
                    _ask_case(
                        active_id, s, user)
                    st.rerun()

    if prompt := st.chat_input(
            "Postavite pitanje..."):
        _ask_case(active_id, prompt, user)
        st.rerun()


def _ask_case(case_id, question, user):
    save_case_message(
        case_id, "user", question)
    case_vs = get_case_doc_vs(case_id)
    answer, conf, results = query_ai(
        question, case_vs)
    sources_html = (
        render_sources_html(results)
        if results else "")
    save_case_message(
        case_id, "assistant", answer,
        sources_html, conf)
    log_action(
        user["id"], "query",
        f"[{conf}] case={case_id}")

def tab_search():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>Pretraga zakona</h3></div>',
        unsafe_allow_html=True)
    q = st.text_input(
        "Pretrazi",
        placeholder="kradja, clan 325...")
    if q:
        res = search_laws(q)
        if res:
            st.success(
                f"{len(res)} rezultata")
            for r in res:
                src = safe_text(
                    r.get('short_name')
                    or r.get('name_sr', ''))
                art = (
                    f"Cl. "
                    f"{r.get('article_number', '?')}")
                score = r.get('score', 0)
                with st.expander(
                        f"{src}: {art}"
                        f" (rel: {score})"):
                    hl = r.get(
                        'hierarchy_level', 3)
                    hi = HIERARCHY_LEVELS.get(
                        hl, HIERARCHY_LEVELS[3])
                    st.text(
                        f"Snaga: {hi['name']}")
                    st.markdown(
                        safe_text(
                            r.get('content', '')))
        else:
            st.info("Nema rezultata.")


def tab_translate():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>Prevod</h3></div>',
        unsafe_allow_html=True)
    f = st.file_uploader(
        "PDF/TXT",
        type=["pdf", "txt"],
        key="tr_up")
    if f:
        text, name, lang = process_upload(f)
        if text and lang != "sr":
            if st.button(
                    "Prevedi",
                    type="primary",
                    use_container_width=True):
                with st.spinner("Prevodim..."):
                    tr = translate_full(text, lang)
                st.markdown(tr)
                w = create_word("Prevod", tr)
                st.download_button(
                    "Preuzmi Word",
                    data=w,
                    file_name="prevod.docx")
        elif text:
            st.info("Vec srpski.")


def tab_docs():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>Podnesci</h3></div>',
        unsafe_allow_html=True)
    dt = st.selectbox(
        "Tip",
        list(DOC_TEMPLATES.keys()),
        format_func=lambda x: (
            DOC_TEMPLATES[x]['name']))
    info = st.text_area(
        "Opisite slucaj", height=200)
    if st.button(
            "Generisi",
            disabled=not info,
            use_container_width=True,
            type="primary"):
        tmpl = DOC_TEMPLATES[dt]
        with st.spinner("Generisem..."):
            try:
                r = get_llm(0.15, 6000).invoke(
                    [HumanMessage(
                        content=tmpl["prompt"]
                        .format(info=info))])
                st.markdown(r.content)
                w = create_word(
                    tmpl["name"], r.content)
                st.download_button(
                    "Preuzmi Word",
                    data=w,
                    file_name="podnesak.docx")
            except Exception as e:
                st.error(f"{e}")


def tab_bridge():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>Most AL - SR</h3></div>',
        unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        al = st.text_area(
            "Albanski tekst",
            height=300,
            placeholder="Vendim...",
            key="br_in")
        btn = st.button(
            "Prevedi",
            use_container_width=True,
            disabled=not al,
            key="br_go")
    with c2:
        if btn and al:
            with st.spinner("Prevodim..."):
                st.markdown(
                    translate_full(al, "al"))
            found = [
                (a, s)
                for a, s in LEGAL_DICT.items()
                if a.lower() in al.lower()]
            if found:
                st.markdown("**Termini:**")
                for a, s in found:
                    st.text(f"{a} = {s}")


def tab_subscription():
    user = st.session_state.current_user
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>Pretplata</h3></div>',
        unsafe_allow_html=True)
    current_plan = PLANS.get(
        user["plan"],
        {"name": "?", "price": 0})
    st.markdown(
        f"Trenutni plan: {current_plan['name']}"
        f" | Do: "
        f"{user.get('subscription_end', '-')}")
    st.markdown("### Dostupni paketi")
    for key, plan in PLANS.items():
        if key == "enterprise":
            continue
        price_text = (
            f"E{plan['price']}/mesec"
            if plan['price'] > 0
            else "Po dogovoru")
        st.markdown(
            f"**{plan['name']}**"
            f" -- {price_text}")
        if (plan['price'] > 0
                and key != user.get("plan")):
            if (STRIPE_SECRET_KEY
                    and STRIPE_AVAILABLE):
                url = create_stripe_checkout(
                    key, user["email"])
                if url:
                    st.link_button(
                        f"Pretplati se"
                        f" -- {price_text}",
                        url,
                        use_container_width=True)
                else:
                    st.text(
                        "Stripe nije konfigurisan.")
            else:
                st.text(
                    f"Kontakt: {ADMIN_EMAIL}")
    if not STRIPE_SECRET_KEY:
        st.info(
            "Stripe placanje uskoro."
            f" Kontakt: {ADMIN_EMAIL}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_database()
    run_auto_suspension()
    if not st.session_state.get(
            "logged_in", False):
        render_login()
        return
    if check_session_timeout():
        do_logout()
        st.warning(
            "Automatska odjava nakon 8 sati"
            " iz bezbednosnih razloga."
            " Prijavite se ponovo.")
        render_login()
        return
    user = st.session_state.get("current_user")
    if not user:
        st.session_state["logged_in"] = False
        st.rerun()
        return
    try:
        with get_db() as conn:
            fresh = conn.execute(
                "SELECT * FROM users WHERE id=?",
                (user["id"],)).fetchone()
            if fresh:
                st.session_state.current_user = \
                    dict(fresh)
            else:
                do_logout()
                st.rerun()
                return
    except Exception:
        pass
    if st.session_state.current_user[
            "role"] == "admin":
        render_admin()
    else:
        render_user()


if __name__ == "__main__":
    main()
