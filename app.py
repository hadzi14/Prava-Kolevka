"""
═══════════════════════════════════════════════════════════════
 PRAVA KOLEVKA v5.4 — Pravni AI za Kosovo
 Clean import, preview, export, stroži retrieval
═══════════════════════════════════════════════════════════════
"""

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

# ═══════════════════════════════════════════════════════════════
#  KONFIGURACIJA
# ═══════════════════════════════════════════════════════════════

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

NAVY = "#0A1628"
NAVY_MID = "#1B2A4A"
GOLD = "#C5962C"
GOLD_LIGHT = "#F0E6C8"
GOLD_PALE = "#FBF7ED"
SURFACE = "#F5F4F0"
CARD_BG = "#FFFFFF"
TEXT_MUTED = "#6B7280"
SUCCESS = "#059669"
ERROR = "#DC2626"
WARNING = "#D97706"

PLANS = {
    "obican": {
        "name": "Običan paket", "price": 19,
        "max_users": 1, "icon": "📦", "can_share": False},
    "bolji": {
        "name": "Bolji paket", "price": 29,
        "max_users": 5, "icon": "⭐", "can_share": True},
    "dogovor": {
        "name": "Paket po dogovoru", "price": 0,
        "max_users": 999, "icon": "💎", "can_share": True},
    "enterprise": {
        "name": "Enterprise", "price": 0,
        "max_users": 999, "icon": "🔧", "can_share": True},
}
GRACE_PERIOD_DAYS = 3
LANG_NAMES = {"sr": "Srpski", "al": "Albanski", "en": "Engleski"}

HIERARCHY_LEVELS = {
    1: {"name": "Ustav", "icon": "👑", "weight": 15,
        "desc": "Najviši pravni akt"},
    2: {"name": "Međunarodni sporazum", "icon": "🌍",
        "weight": 10, "desc": "Ratifikovani ugovori"},
    3: {"name": "Zakon", "icon": "📜", "weight": 5,
        "desc": "Zakon Skupštine Kosova"},
    4: {"name": "Podzakonski akt", "icon": "📋",
        "weight": 2, "desc": "Uredba, pravilnik"},
    5: {"name": "Opštinski propis", "icon": "🏘️",
        "weight": 0, "desc": "Lokalni propisi"},
}

LEGAL_AREAS = [
    "Ustavno pravo", "Krivično pravo", "Krivični postupak",
    "Građansko pravo", "Parnični postupak", "Upravno pravo",
    "Radno pravo", "Porodično pravo", "Prekršajno pravo",
    "Pravosuđe", "Tužilaštvo", "Advokatura",
    "Policijsko pravo", "Obligaciono pravo",
    "Imovinsko pravo", "Ostalo",
]

AREA_KEYWORDS = {
    "Krivično pravo": [
        "krivičn", "kazna", "kazne", "kažnjav", "delo",
        "krađa", "ubistvo", "razbojništvo", "prevara",
        "falsifik", "nasilj", "pretnja", "silovanj",
        "zlostavljanj", "korupcij", "mito", "pranje novca",
        "terorizam", "oružje", "droga", "narkotik",
        "zatvor", "robija", "uslovn", "probacij",
        "umišljaj", "nehat", "recidiv", "nužna odbrana",
    ],
    "Krivični postupak": [
        "postupak", "pritvor", "hapšenj", "istrag",
        "optužnic", "suđenj", "presud", "žalb", "dokaz",
        "svedok", "veštačenj", "pretres", "branilac",
        "okrivljeni", "osumnjičeni", "tužilac",
        "saslušanj", "ročišt", "nadležnost",
    ],
    "Građansko pravo": [
        "obligacij", "ugovor", "šteta", "naknada",
        "odgovornost", "potraživanj", "dug", "zajam",
        "hipoteka", "zakup", "prodaj", "zastarelost",
    ],
    "Parnični postupak": [
        "parnič", "tužba", "tužilac", "tuženi",
        "prvostepen", "drugostepen", "revizija",
        "izvršenje", "presuda", "rešenje",
    ],
    "Porodično pravo": [
        "brak", "razvod", "alimentacij", "izdržavanj",
        "starateljstv", "usvojenj", "roditeljsk",
        "dete", "deca", "porodičn",
    ],
    "Radno pravo": [
        "rad", "zaposlen", "radni odnos", "otkaz",
        "plata", "odmor", "ugovor o radu", "sindikat",
        "štrajk", "penzij", "bolovanje",
    ],
    "Upravno pravo": [
        "upravn", "organ", "rešenj", "inspekcij",
        "dozvol", "javna nabavka",
    ],
    "Prekršajno pravo": [
        "prekršaj", "novčana kazna", "mandatna",
    ],
    "Pravosuđe": [
        "sudij", "sud", "sudski", "vrhovni sud",
        "apelacion", "osnovni sud",
    ],
    "Tužilaštvo": [
        "tužilaštv", "tužilac", "javni tužilac",
        "krivično gonjenje",
    ],
    "Advokatura": [
        "advokat", "advokatsk", "branilac",
        "punomoćnik", "advokatska komora",
    ],
    "Policijsko pravo": [
        "policij", "policajac", "privođenj",
        "hapšenj", "upotreba sile",
    ],
    "Ustavno pravo": [
        "ustav", "ustavni", "osnovna prava",
        "ljudska prava", "slobode", "ustavni sud",
    ],
}

SHORTNAME_MAP = {
    "kz": ["Krivični zakonik"],
    "krivični zakonik": ["Krivični zakonik"],
    "zkp": ["Zakonik o krivičnom postupku",
            "Zakon o krivičnom postupku"],
    "zoo": ["Zakon o obligacionim odnosima"],
    "zpp": ["Zakon o parničnom postupku"],
    "zor": ["Zakon o radu"],
    "pz": ["Porodični zakon"],
    "zup": ["Zakon o upravnom postupku"],
    "zakon o sudovima": ["Zakon o sudovima"],
    "zakon o tužilaštvu": ["Zakon o tužilaštvu"],
    "zakon o advokaturi": ["Zakon o advokaturi"],
    "zakon o policiji": ["Zakon o policiji"],
    "zakon o prekršajima": ["Zakon o prekršajima"],
    "ustav": ["Ustav Kosova", "Ustav Republike Kosovo"],
    "ustav kosova": ["Ustav Kosova"],
}

SERBIA_MARKERS = [
    "zakon republike srbije", "zakon rs",
    "službeni glasnik rs", "krivični zakonik srbije",
    "republika srbija", "narodna skupština",
    "vrhovni kasacioni sud", "po srpskom pravu",
    "u srbiji", "zakon srbije",
]


# ═══════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════

def init_ss():
    defaults = {
        "logged_in": False, "current_user": None,
        "docs": [], "vs": None, "chat": [],
        "law_vs": None, "law_vs_version": "",
        "login_time": None,
        "preview_articles": None,
        "preview_warnings": None,
        "preview_meta": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_ss()
# ═══════════════════════════════════════════════════════════════
#  LOZINKE — bcrypt
# ═══════════════════════════════════════════════════════════════

def create_password_hash(password: str) -> Tuple[str, str]:
    if BCRYPT_AVAILABLE:
        h = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)).decode('utf-8')
        return h, "bcrypt"
    salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
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


# ═══════════════════════════════════════════════════════════════
#  BAZA PODATAKA
# ═══════════════════════════════════════════════════════════════

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
                firm_name TEXT DEFAULT '',
                phone TEXT DEFAULT '',
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
                notes TEXT DEFAULT '',
                recorded_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
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
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (law_id) REFERENCES laws(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_filename TEXT,
                source_language TEXT,
                source_text TEXT,
                translated_text TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS generated_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                doc_type TEXT, content TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
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
    except Exception as e:
        st.error(f"DB init: {e}")


# ═══════════════════════════════════════════════════════════════
#  CLEAN IMPORT PARSER v5.4
# ═══════════════════════════════════════════════════════════════

def clean_text(text: str) -> str:
    """Čisti tekst od PDF artefakata."""
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


def remove_toc(text: str) -> Tuple[str, bool]:
    """Uklanja Table of Contents."""
    toc_re = re.compile(
        r'^\s*(?:Član|ČLAN|Neni|NENI|Članak)\s+\d+[a-zA-Z]?'
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


def parse_articles(full_text: str) -> Tuple[List[Dict], List[str]]:
    """
    Clean Import Parser.
    - SAMO "Član X" na početku reda = novi član
    - Stavovi ostaju unutar člana
    - Jedan red u bazi po članu
    """
    warnings = []
    text = clean_text(full_text)
    text, had_toc = remove_toc(text)
    if had_toc:
        warnings.append("Uklonjen sadržaj (TOC).")

    lines = text.split('\n')

    # Strogi patern: samo "Član X" ili "Član X - Naslov"
    hdr_solo = re.compile(
        r'^\s*(?:Član|ČLAN|Članak|ČLANAK|Neni|NENI)'
        r'\s+(\d+[a-zA-Z]?)\s*\.?\s*$', re.IGNORECASE)
    hdr_titled = re.compile(
        r'^\s*(?:Član|ČLAN|Članak|ČLANAK|Neni|NENI)'
        r'\s+(\d+[a-zA-Z]?)\s*[.\s]*[-–—:]\s*(.+)$',
        re.IGNORECASE)
    toc_chk = re.compile(r'(?:\.{3,}|…{2,})\s*\d{1,4}\s*$')

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
                (i, m.group(1).strip(), m.group(2).strip()))

    # Fallback
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
            warnings.append("Korišćen relaksirani pattern.")

    if not starts:
        warnings.append(
            "Nije pronađena struktura članova."
            " Ceo tekst kao jedan blok.")
        return [{
            "article_number": "0",
            "paragraph_number": "",
            "title": "(Neparsirani tekst)",
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
        if not body:
            continue

        articles.append({
            "article_number": num,
            "paragraph_number": "",
            "title": title,
            "content": body
        })

    # Validacija
    if len(starts) < 3:
        warnings.append(
            f"Samo {len(starts)} članova pronađeno.")
    empty = sum(1 for a in articles if len(a["content"]) < 10)
    if articles and empty > len(articles) * 0.3:
        warnings.append(
            f"{empty}/{len(articles)} članova kratko.")
    nums = set(a['article_number'] for a in articles)
    max_n = 0
    for a in articles:
        try:
            n = int(re.match(
                r'(\d+)', a['article_number']).group(1))
            max_n = max(max_n, n)
        except Exception:
            pass
    if max_n > 0 and len(nums) > max_n * 1.3:
        warnings.append(
            f"{len(nums)} članova, ali max broj {max_n}."
            " Proverite tekst.")

    return articles, warnings


def save_law_to_db(name_sr, name_al, short_name,
                   law_number, area, gazette_info,
                   effective_date, language, full_text,
                   hierarchy_level=3):
    try:
        articles, warnings = parse_articles(full_text)
        with get_db() as conn:
            conn.execute("""
                INSERT INTO laws (name_sr, name_al,
                short_name, law_number, area, gazette_info,
                effective_date, language, full_text,
                hierarchy_level) VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (name_sr, name_al, short_name, law_number,
                  area, gazette_info, effective_date,
                  language, full_text, hierarchy_level))
            law_id = conn.execute(
                "SELECT last_insert_rowid()").fetchone()[0]
            for art in articles:
                conn.execute("""
                    INSERT INTO law_articles
                    (law_id, article_number,
                    paragraph_number, title, content)
                    VALUES(?,?,?,?,?)
                """, (law_id, art["article_number"],
                      art.get("paragraph_number", ""),
                      art.get("title", ""),
                      art["content"]))
            st.session_state.law_vs = None
            st.session_state.law_vs_version = ""
            return law_id, len(articles), warnings
    except Exception as e:
        return None, 0, [f"Greška: {e}"]


def reparse_law(law_id: int) -> Tuple[int, List[str]]:
    """Ponovo parsira zakon iz sačuvanog full_text."""
    try:
        with get_db() as conn:
            law = conn.execute(
                "SELECT full_text FROM laws WHERE id=?",
                (law_id,)).fetchone()
            if not law:
                return 0, ["Zakon nije pronađen."]
            conn.execute(
                "DELETE FROM law_articles WHERE law_id=?",
                (law_id,))
            articles, warnings = parse_articles(
                law["full_text"])
            for art in articles:
                conn.execute("""
                    INSERT INTO law_articles
                    (law_id, article_number,
                    paragraph_number, title, content)
                    VALUES(?,?,?,?,?)
                """, (law_id, art["article_number"],
                      art.get("paragraph_number", ""),
                      art.get("title", ""),
                      art["content"]))
            st.session_state.law_vs = None
            st.session_state.law_vs_version = ""
            return len(articles), warnings
    except Exception as e:
        return 0, [f"Greška: {e}"]


def export_laws_json() -> str:
    """Izvozi sve zakone kao JSON string."""
    try:
        with get_db() as conn:
            laws = conn.execute(
                "SELECT * FROM laws WHERE is_active=1"
            ).fetchall()
            result = []
            for law in laws:
                law = dict(law)
                arts = conn.execute(
                    "SELECT article_number, paragraph_number,"
                    " title, content FROM law_articles"
                    " WHERE law_id=?"
                    " ORDER BY CAST(article_number"
                    " AS INTEGER)",
                    (law["id"],)).fetchall()
                law["articles"] = [dict(a) for a in arts]
                del law["full_text"]
                result.append(law)
        return json.dumps(
            result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════
#  VEKTORSKA PRETRAGA
# ═══════════════════════════════════════════════════════════════

def get_law_vs_version():
    try:
        with get_db() as conn:
            c = conn.execute(
                "SELECT COUNT(*) FROM law_articles"
            ).fetchone()[0]
            l = conn.execute(
                "SELECT MAX(created_at)"
                " FROM law_articles"
            ).fetchone()[0] or ""
            return f"{c}_{l}"
    except Exception:
        return "0_"


def build_law_vector_store():
    if not OPENAI_API_KEY:
        return None
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT la.article_number,
                       la.paragraph_number,
                       la.title, la.content,
                       l.name_sr, l.short_name,
                       l.law_number, l.area,
                       l.hierarchy_level
                FROM law_articles la
                JOIN laws l ON la.law_id = l.id
                WHERE l.is_active = 1
            """).fetchall()
        if not rows:
            return None
        docs = []
        for row in rows:
            row = dict(row)
            src = row.get('short_name') or row['name_sr']
            ref = f"Član {row['article_number']}"
            if row.get('paragraph_number'):
                ref += f" st.{row['paragraph_number']}"
            hl = row.get('hierarchy_level', 3)
            hi = HIERARCHY_LEVELS.get(hl, HIERARCHY_LEVELS[3])
            txt = f"{hi['name']}: {src} {ref}"
            if row.get('title'):
                txt += f" {row['title']}"
            txt += f"\n{row['content']}"
            docs.append(Document(
                page_content=txt,
                metadata={
                    "article_number": row['article_number'],
                    "paragraph_number": row.get(
                        'paragraph_number', ''),
                    "title": row.get('title', ''),
                    "content": row['content'],
                    "name_sr": row['name_sr'],
                    "short_name": row.get('short_name', ''),
                    "law_number": row.get('law_number', ''),
                    "area": row.get('area', ''),
                    "hierarchy_level": hl}))
        sp = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200)
        final = []
        for d in docs:
            if len(d.page_content) > 1200:
                final.extend(sp.split_documents([d]))
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
    q = q.lower()
    det = []
    for area, kws in AREA_KEYWORDS.items():
        sc = sum(1 for kw in kws if kw in q)
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


def search_laws(query, max_results=15):
    q = query.lower()
    stop = {
        'je', 'su', 'da', 'li', 'se', 'na', 'u', 'i',
        'za', 'od', 'sa', 'po', 'ne', 'ni', 'što', 'šta',
        'kako', 'koji', 'koja', 'koje', 'ko', 'ako', 'ali',
        'ili', 'kad', 'kada', 'gde', 'iz', 'do', 'bi', 'mi',
        'ti', 'on', 'ona', 'oni', 'vi', 'taj', 'ta', 'to',
        'ovo', 'može', 'mora', 'treba', 'prema', 'biti',
        'bude', 'sam', 'jedan', 'neki', 'sve', 'svi', 'svoj',
        'ima', 'nema', 'radi', 'kaže', 'član', 'stav',
        'zakon', 'pravo', 'pravni', 'molim', 'pitanje',
    }
    words = re.findall(r'[a-zA-ZčćžšđČĆŽŠĐ]+', q)
    kws = [w for w in words if len(w) > 2 and w not in stop]

    am = re.search(
        r'(?:član|članu|člana|neni)\s*[:\s]*(\d+[a-zA-Z]?)',
        q)
    t_art = am.group(1) if am else None
    t_laws = detect_target_law(query)
    t_areas = detect_legal_area(query)

    rd = {}

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
            bq = """SELECT la.article_number,
                la.paragraph_number, la.title, la.content,
                l.name_sr, l.short_name, l.law_number,
                l.area, l.hierarchy_level
                FROM law_articles la
                JOIN laws l ON la.law_id=l.id
                WHERE l.is_active=1"""

            if t_art and t_laws:
                for ln in t_laws:
                    for r in conn.execute(
                            bq + " AND la.article_number=?"
                            " AND (l.name_sr LIKE ?"
                            " OR l.short_name LIKE ?)",
                            (t_art, f"%{ln}%",
                             f"%{ln}%")).fetchall():
                        add(dict(r), 200)

            if t_art:
                for r in conn.execute(
                        bq + " AND la.article_number=?",
                        (t_art,)).fetchall():
                    d = dict(r)
                    ab = 50 if d.get('area') in t_areas else 0
                    add(d, 150 + ab)

            if t_laws and kws:
                for ln in t_laws:
                    for kw in kws[:6]:
                        for r in conn.execute(
                                bq + " AND (l.name_sr LIKE ?"
                                " OR l.short_name LIKE ?)"
                                " AND (la.content LIKE ?"
                                " OR la.title LIKE ?)"
                                " LIMIT 5",
                                (f"%{ln}%", f"%{ln}%",
                                 f"%{kw}%",
                                 f"%{kw}%")).fetchall():
                            d = dict(r)
                            kc = sum(1 for k in kws
                                     if k in
                                     d['content'].lower())
                            add(d, 100 + kc * 10)

            if kws and t_areas:
                for kw in kws[:5]:
                    for area in t_areas[:2]:
                        for r in conn.execute(
                                bq + " AND l.area=?"
                                " AND (la.content LIKE ?"
                                " OR la.title LIKE ?)"
                                " LIMIT 5",
                                (area, f"%{kw}%",
                                 f"%{kw}%")).fetchall():
                            d = dict(r)
                            kc = sum(1 for k in kws
                                     if k in
                                     d['content'].lower())
                            add(d, 60 + kc * 10)

            if kws:
                for kw in kws[:5]:
                    for r in conn.execute(
                            bq + " AND (la.content LIKE ?"
                            " OR la.title LIKE ?)"
                            " LIMIT 8",
                            (f"%{kw}%",
                             f"%{kw}%")).fetchall():
                        d = dict(r)
                        kc = sum(1 for k in kws
                                 if k in
                                 d['content'].lower())
                        ab = (15 if d.get('area')
                              in t_areas else 0)
                        add(d, 20 + kc * 10 + ab)
    except Exception as e:
        st.error(f"Greška: {e}")

    vs = get_law_vector_store()
    if vs:
        try:
            for doc, dist in vs.similarity_search_with_score(
                    query, k=15):
                m = doc.metadata
                if dist < 1.3:
                    sc = max(5, int(85 * (1 - dist / 1.3)))
                    r = {
                        'article_number': m.get(
                            'article_number', ''),
                        'paragraph_number': m.get(
                            'paragraph_number', ''),
                        'title': m.get('title', ''),
                        'content': m.get(
                            'content', doc.page_content),
                        'name_sr': m.get('name_sr', ''),
                        'short_name': m.get(
                            'short_name', ''),
                        'law_number': m.get(
                            'law_number', ''),
                        'area': m.get('area', ''),
                        'hierarchy_level': m.get(
                            'hierarchy_level', 3)}
                    if t_areas and r.get('area') in t_areas:
                        sc += 15
                    if t_laws:
                        for tl in t_laws:
                            if tl.lower() in r.get(
                                    'name_sr', '').lower():
                                sc += 20
                                break
                    add(r, sc)
        except Exception:
            pass

    res = sorted(rd.values(),
                 key=lambda x: x.get('score', 0),
                 reverse=True)
    return res[:max_results]


def format_results(results):
    if not results:
        return "PRONAĐENO: 0 članova.\nNEMA IZVORA."
    parts = [f"PRONAĐENO: {len(results)} članova.\n"]
    for i, r in enumerate(results):
        src = r.get('short_name') or r['name_sr']
        ln = f" ({r['law_number']})" \
            if r.get('law_number') else ""
        art = f"Član {r['article_number']}"
        if r.get('paragraph_number'):
            art += f", stav {r['paragraph_number']}"
        ttl = f" — {r['title']}" if r.get('title') else ""
        hl = r.get('hierarchy_level', 3)
        hi = HIERARCHY_LEVELS.get(hl, HIERARCHY_LEVELS[3])
        parts.append(
            f"[IZVOR #{i+1} | {hi['icon']}"
            f" {hi['name'].upper()}"
            f" | {src}{ln}, {art}{ttl}]\n"
            f"{r['content']}\n[KRAJ #{i+1}]")
    allowed = sorted(set(
        f"{r.get('short_name') or r['name_sr']},"
        f" Član {r['article_number']}"
        for r in results))
    parts.append(
        "\n═══ DOZVOLJENI CITATI ═══\n"
        "SMEŠ citirati ISKLJUČIVO:\n"
        + "\n".join(f"• {a}" for a in allowed))
    return "\n\n".join(parts)


def determine_confidence(results, query):
    if not results:
        return "INSUFFICIENT_SOURCES"
    top = results[0].get('score', 0)
    hq = sum(1 for r in results if r.get('score', 0) >= 80)
    if hq >= 2 and top >= 100:
        return "GROUNDED"
    if hq >= 1 or (len(results) >= 3 and top >= 40):
        return "PARTIALLY_GROUNDED"
    return "INSUFFICIENT_SOURCES"


def verify_citations(resp, results):
    cited = re.findall(
        r'[Čč]lan(?:u|a|om|ku)?\s+(\d+[a-zA-Z]?)',
        resp, re.IGNORECASE)
    avail = set(r['article_number'] for r in results)
    bad = [c for c in set(cited) if c not in avail]
    if bad:
        resp += (
            f"\n\n⚠️ **UPOZORENJE:** AI pomenuo"
            f" Član {', '.join(bad)} koji nisu"
            f" među izvorima.")
    return resp


def render_sources_html(results):
    if not results:
        return ""
    parts = ['<div style="margin-top:1rem;">']
    shown = set()
    for r in results[:8]:
        src = r.get('short_name') or r['name_sr']
        art = f"Član {r['article_number']}"
        if r.get('paragraph_number'):
            art += f", st. {r['paragraph_number']}"
        ttl = f" — {r['title']}" if r.get('title') else ""
        k = f"{src}|{art}"
        if k in shown:
            continue
        shown.add(k)
        hl = r.get('hierarchy_level', 3)
        hi = HIERARCHY_LEVELS.get(hl, HIERARCHY_LEVELS[3])
        sn = r['content'][:200]
        if len(r['content']) > 200:
            sn += "..."
        parts.append(
            f'<div style="background:white;'
            f'border-left:3px solid #C5962C;'
            f'border-radius:0 12px 12px 0;'
            f'padding:10px 14px;margin:6px 0;'
            f'font-size:.85rem;">'
            f'<div style="font-weight:600;'
            f'color:#0A1628;">'
            f'{hi["icon"]} {src}: {art}{ttl}</div>'
            f'<div style="color:#888;font-size:.7rem;">'
            f'Pravna snaga: {hi["name"]}</div>'
            f'<div style="color:#6B7280;margin-top:4px;'
            f'font-size:.8rem;">{sn}</div></div>')
    parts.append('</div>')
    return ''.join(parts)


SYSTEM_PROMPT = """Ti si "Prava Kolevka" — pravni AI za KOSOVO.

PRAVILA:
1. Odgovaraj ISKLJUČIVO iz priloženih [IZVOR] članova.
2. Za svaku tvrdnju citiraj: "Prema [Zakon], član X..."
3. Citiraj SAMO iz sekcije DOZVOLJENI CITATI.
4. Ako nema odgovora: "Na osnovu zakona u bazi, ne postoje odredbe."
5. Samo zakoni Kosova. Za drugu državu: "Sistem sadrži samo zakone Kosova."
6. Hijerarhija: 👑USTAV > 🌍MEĐUNARODNI > 📜ZAKON > 📋PODZAKONSKI > 🏘️OPŠTINSKI

FORMAT:
## Odgovor
[2-3 rečenice]
## Obrazloženje
[Sa citatima]
## Korišćeni izvori
[Lista]
## Napomena
[Ograničenja]

═══ ČLANOVI ═══
{law_context}

═══ DOKUMENTI ═══
{doc_context}

═══ PITANJE ═══
{question}"""


def query_ai(question, vector_store=None):
    ji = detect_jurisdiction_issue(question)
    tl = detect_target_law(question)
    missing = []
    if tl:
        try:
            with get_db() as conn:
                for t in tl:
                    c = conn.execute(
                        "SELECT COUNT(*) c FROM laws"
                        " WHERE is_active=1"
                        " AND (name_sr LIKE ?"
                        " OR short_name LIKE ?)",
                        (f"%{t}%", f"%{t}%")
                    ).fetchone()["c"]
                    if c == 0:
                        missing.append(t)
        except Exception:
            pass

    results = search_laws(question)
    ctx = format_results(results)
    conf = determine_confidence(results, question)

    doc_ctx = "(Nema dokumenata.)"
    if vector_store:
        try:
            ds = vector_store.as_retriever(
                search_kwargs={"k": 4}).invoke(question)
            if ds:
                doc_ctx = "\n---\n".join(
                    f"[{d.metadata.get('source', '?')}]"
                    f"\n{d.page_content}" for d in ds)
        except Exception:
            pass

    if missing and not results:
        ans = (
            f"## Odgovor\n"
            f"Zakon(i) {', '.join(missing)}"
            f" nisu u bazi.\n\n"
            f"## Obrazloženje\n"
            f"Sistem odgovara samo iz unetih zakona.\n\n"
            f"## Korišćeni izvori\nNijedan.\n\n"
            f"## Napomena\nKontaktirajte admina.")
        if ji:
            ans += f"\n\n⚠️ '{ji}' — druga država."
        return ans, "INSUFFICIENT_SOURCES", results

    if conf == "INSUFFICIENT_SOURCES" and not vector_store:
        ans = (
            "## Odgovor\nNisam pronašao odredbe.\n\n"
            "## Obrazloženje\n"
            "Nema relevantnih rezultata.\n\n"
            "## Korišćeni izvori\nNijedan.\n\n"
            "## Napomena\nKonsultujte advokata.")
        if missing:
            ans += f"\n\n⚠️ {', '.join(missing)} — nije u bazi."
        if ji:
            ans += f"\n\n⚠️ '{ji}' — druga država."
        return ans, conf, results

    extra = ""
    if ji:
        extra += f"\nVAŽNO: '{ji}' — samo Kosovo."
    if missing:
        extra += (
            f"\nVAŽNO: {', '.join(missing)}"
            f" NIJE u bazi.")

    prompt = SYSTEM_PROMPT.format(
        law_context=ctx, doc_context=doc_ctx,
        question=question + extra)

    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini", api_key=OPENAI_API_KEY,
            temperature=0.05, max_tokens=4096)
        ans = llm.invoke(
            [HumanMessage(content=prompt)]).content
        ans = verify_citations(ans, results)
        labels = {
            "GROUNDED": "🟢 UTEMELJEN",
            "PARTIALLY_GROUNDED": "🟡 DELIMIČNO",
            "INSUFFICIENT_SOURCES": "🔴 NEDOVOLJNO"}
        ans += f"\n\n---\n**Pouzdanost:** {labels.get(conf, '')}"
        return ans, conf, results
    except Exception as e:
        return f"⚠️ {e}", "INSUFFICIENT_SOURCES", results
     # ═══════════════════════════════════════════════════════════════
#  POMOĆNE FUNKCIJE
# ═══════════════════════════════════════════════════════════════

def check_subscription(user):
    if user["role"] == "admin":
        return {"active": True, "status": "admin",
                "days_left": 99999, "message": ""}
    if not user["is_active"]:
        return {"active": False, "status": "suspended",
                "days_left": 0,
                "message": user.get(
                    "suspended_reason", "Suspendovan.")}
    if not user.get("subscription_end"):
        return {"active": False, "status": "no_sub",
                "days_left": 0, "message": "Nema pretplate."}
    try:
        end = date.fromisoformat(user["subscription_end"])
    except Exception:
        return {"active": False, "status": "error",
                "days_left": 0, "message": "Greška."}
    dl = (end - date.today()).days
    if dl < -GRACE_PERIOD_DAYS:
        return {"active": False, "status": "expired",
                "days_left": dl,
                "message": f"Istekla pre {abs(dl)}d."}
    if dl < 0:
        return {"active": True, "status": "grace",
                "days_left": dl,
                "message":
                    f"Istekla! Još {GRACE_PERIOD_DAYS+dl}d."}
    if dl <= 7:
        return {"active": True, "status": "expiring",
                "days_left": dl,
                "message": f"Ističe za {dl}d."}
    return {"active": True, "status": "active",
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
                "suspended_reason='Auto: istekla'"
                " WHERE role='user' AND is_active=1"
                " AND subscription_end<?", (cutoff,))
        st.session_state["_susp"] = True
    except Exception:
        pass


def log_action(uid, action, details=""):
    try:
        safe = re.sub(
            r'[a-zA-Z0-9._%+-]+@[^\s]+',
            '[EMAIL]', (details or "")[:80])
        with get_db() as conn:
            conn.execute(
                "INSERT INTO usage_logs"
                "(user_id,action,details)"
                "VALUES(?,?,?)", (uid, action, safe))
    except Exception:
        pass


def get_llm(temp=0.1, tokens=4096):
    return ChatOpenAI(
        model="gpt-4o-mini", api_key=OPENAI_API_KEY,
        temperature=temp, max_tokens=tokens)


def detect_language(text):
    s = text.lower()[:2000]
    if len(re.findall(r'[а-яА-Я]', s)) > len(s) * 0.1:
        return "sr"
    al = sum(1 for m in [
        'është', 'dhe', 'për', 'nga', 'në'] if m in s)
    en = sum(1 for m in [
        'the', 'and', 'for', 'that', 'court'] if m in s)
    sr = sum(1 for m in [
        ' je ', ' su ', ' ili ', 'zakon'] if m in s)
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


def process_file(file):
    n = file.name
    if n.lower().endswith('.pdf'):
        t = extract_pdf(file)
    elif n.lower().endswith('.txt'):
        raw = file.read()
        t = ""
        for enc in ['utf-8', 'latin-1', 'cp1250']:
            try:
                t = raw.decode(enc)
                break
            except Exception:
                continue
        if not t:
            t = raw.decode('utf-8', errors='replace')
    else:
        return "", "", ""
    return t, n, detect_language(t) if t else "sr"


def build_vs(docs_data, api_key):
    sp = RecursiveCharacterTextSplitter(
        chunk_size=1500, chunk_overlap=300)
    all_d = []
    for d in docs_data:
        if not d.get("text"):
            continue
        for c in sp.split_text(d["text"]):
            all_d.append(Document(
                page_content=c,
                metadata={"source": d["name"]}))
    if not all_d:
        return None
    return FAISS.from_documents(
        all_d, OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key))


def translate_full(text, lang):
    ln = {"al": "albanski", "en": "engleski"}.get(
        lang, "nepoznat")
    if lang == "sr":
        return text
    llm = get_llm(temp=0.05, tokens=8000)
    if len(text) < 6000:
        try:
            return llm.invoke([HumanMessage(
                content=f"Prevedi na srpski:\n{text}"
            )]).content
        except Exception as e:
            return f"⚠️ {e}"
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
            parts.append(llm.invoke([HumanMessage(
                content=f"Prevedi na srpski:\n{ch}"
            )]).content)
        except Exception as e:
            parts.append(f"[Greška {i+1}: {e}]")
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
            doc.add_paragraph(s[2:], style='List Bullet')
        elif s:
            doc.add_paragraph(s)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


LEGAL_DICT = {
    "Gjykata Themelore": "Osnovni sud",
    "Gjykata e Apelit": "Apelacioni sud",
    "Vendim": "Odluka", "Aktvendim": "Rešenje",
    "Ankesë": "Žalba", "Ligj": "Zakon",
    "Neni": "Član", "Afat": "Rok",
}

DOC_TEMPLATES = {
    "zalba": {"name": "Žalba", "icon": "📋",
              "prompt": "Napiši žalbu za Kosovo."
                        " Info:\n{info}\nSrpski."},
    "tuzba": {"name": "Tužba", "icon": "⚖️",
              "prompt": "Napiši tužbu za Kosovo."
                        " Info:\n{info}\nSrpski."},
    "zahtev": {"name": "Zahtev", "icon": "🏠",
               "prompt": "Napiši zahtev za Kosovo."
                         " Info:\n{info}\nSrpski."},
    "punomocje": {"name": "Punomoćje", "icon": "✍️",
                  "prompt": "Napiši punomoćje SR+AL."
                            " Info:\n{info}"},
}


# ═══════════════════════════════════════════════════════════════
#  CSS
# ═══════════════════════════════════════════════════════════════

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@300;400;500;600;700&display=swap');
body,p,h1,h2,h3,h4,h5,h6,span,div,input,textarea,button,label,a{{font-family:'Inter',sans-serif!important}}
.stApp{{background:{SURFACE}!important}}
#MainMenu,footer,header{{visibility:hidden}}
[data-testid="stSidebar"]{{display:none!important}}
.login-box{{max-width:440px;margin:6vh auto;padding:2.5rem;background:{CARD_BG};border-radius:24px;box-shadow:0 20px 60px rgba(10,22,40,.12)}}
.login-logo{{text-align:center;margin-bottom:2rem}}
.login-logo .icon{{width:72px;height:72px;background:linear-gradient(135deg,{NAVY},{NAVY_MID});border-radius:20px;display:inline-flex;align-items:center;justify-content:center;font-size:2.2rem;margin-bottom:1rem}}
.login-logo h1{{font-family:'Playfair Display',serif!important;font-size:1.8rem;color:{NAVY};margin:0}}
.login-logo p{{color:{TEXT_MUTED};font-size:.85rem}}
.top-bar{{background:linear-gradient(135deg,{NAVY},{NAVY_MID});color:white;padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center;border-radius:0 0 20px 20px;margin:-1rem -1rem 1.5rem -1rem;box-shadow:0 4px 20px rgba(10,22,40,.25);flex-wrap:wrap;gap:8px}}
.top-bar h2{{font-family:'Playfair Display',serif!important;margin:0;font-size:1.3rem}}
.top-bar .gold{{color:{GOLD}}}
.badge{{background:rgba(255,255,255,.15);padding:4px 12px;border-radius:20px;font-weight:500;font-size:.8rem}}
.badge-gold{{background:{GOLD};color:{NAVY};font-weight:700}}
.badge-warn{{background:{WARNING};color:white}}
.badge-err{{background:{ERROR};color:white}}
.pk-card{{background:{CARD_BG};border-radius:20px;padding:1.75rem;margin:.75rem 0;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.pk-card-gold{{background:{CARD_BG};border-radius:20px;padding:1.75rem;margin:.75rem 0;border-left:4px solid {GOLD}}}
.pk-card h3,.pk-card-gold h3{{font-family:'Playfair Display',serif!important;color:{NAVY};margin-top:0}}
.metric-box{{background:{CARD_BG};border-radius:16px;padding:1.25rem;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.metric-box .num{{font-family:'Playfair Display',serif!important;font-size:2rem;font-weight:700;color:{NAVY}}}
.metric-box .lbl{{font-size:.8rem;color:{TEXT_MUTED}}}
.stButton>button{{border-radius:12px!important;font-weight:600!important;border:none!important;background:{NAVY}!important;color:white!important}}
.stButton>button:hover{{background:{NAVY_MID}!important}}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{{border-radius:12px!important;border:2px solid #E5E7EB!important}}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{{border-color:{GOLD}!important}}
.stTabs [data-baseweb="tab-list"]{{gap:4px;background:{CARD_BG};border-radius:14px;padding:4px}}
.stTabs [data-baseweb="tab"]{{border-radius:10px!important;font-weight:500!important}}
.stTabs [aria-selected="true"]{{background:{NAVY}!important;color:white!important}}
.stFileUploader>div{{border-radius:16px!important;border:2px dashed {GOLD_LIGHT}!important;background:{GOLD_PALE}!important}}
[data-testid="stChatMessage"]{{border-radius:16px!important}}
@media(max-width:768px){{.top-bar{{padding:.75rem 1rem}}.top-bar h2{{font-size:1rem}}.pk-card,.pk-card-gold{{padding:1.25rem}}}}
</style>
"""


# ═══════════════════════════════════════════════════════════════
#  LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════

def render_login():
    st.markdown(
        '<div class="login-box"><div class="login-logo">'
        '<div class="icon">⚖️</div>'
        '<h1>Prava Kolevka</h1>'
        '<p>Pravni AI za Kosovo</p>'
        '</div></div>', unsafe_allow_html=True)
    if not BCRYPT_AVAILABLE:
        st.warning("⚠️ bcrypt nije instaliran.")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login", clear_on_submit=False):
            email = st.text_input("📧 Email")
            pw = st.text_input("🔒 Lozinka", type="password")
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
                        st.error("❌ Pogrešni podaci.")


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
    return ((datetime.now() - lt).total_seconds() / 60
            > SESSION_TIMEOUT_MINUTES)
 # ═══════════════════════════════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════════════════════════════

def render_admin():
    st.markdown(
        '<div class="top-bar">'
        '<div style="display:flex;align-items:center;'
        'gap:12px"><span style="font-size:1.5rem">⚖️</span>'
        '<h2>Prava <span class="gold">Kolevka</span>'
        ' — Admin</h2></div>'
        '<span class="badge badge-gold">ADMIN</span>'
        '</div>', unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(
        ["📊 Pregled", "📜 Zakoni", "👥 Korisnici",
         "💰 Uplate", "⚙️ Podešavanja"])
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
    st.markdown("---")
    if st.button("🚪 Odjavi se", key="adm_out"):
        do_logout()
        st.rerun()


def admin_dashboard():
    try:
        with get_db() as conn:
            active = conn.execute(
                "SELECT COUNT(*) c FROM users"
                " WHERE role='user' AND is_active=1"
            ).fetchone()["c"]
            ms = date.today().replace(day=1).isoformat()
            rev = conn.execute(
                "SELECT COALESCE(SUM(amount),0) s"
                " FROM payments"
                " WHERE status='completed'"
                " AND payment_date>=?",
                (ms,)).fetchone()["s"]
            nl = conn.execute(
                "SELECT COUNT(*) c FROM laws"
                " WHERE is_active=1").fetchone()["c"]
            na = conn.execute(
                "SELECT COUNT(*) c"
                " FROM law_articles").fetchone()["c"]
    except Exception as e:
        st.error(f"{e}")
        return
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in [
            (c1, active, "Aktivnih"),
            (c2, f"€{rev:.0f}", "Mesec"),
            (c3, nl, "Zakona"),
            (c4, na, "Članova")]:
        with col:
            st.markdown(
                f'<div class="metric-box">'
                f'<div class="num">{val}</div>'
                f'<div class="lbl">{lbl}</div></div>',
                unsafe_allow_html=True)


def admin_laws():
    st.markdown("### 📜 Zakoni")

    # ── DODAVANJE SA PREVIEW-OM ───────────────────────────────
    with st.expander("➕ Dodaj novi zakon", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            name_sr = st.text_input(
                "Naziv *", placeholder="Krivični zakonik",
                key="al_name")
            name_al = st.text_input(
                "Albanski", key="al_nameal")
            short = st.text_input(
                "Skraćenica", placeholder="KZ",
                key="al_short")
            hlevel = st.selectbox(
                "👑 Pravna snaga",
                list(HIERARCHY_LEVELS.keys()), index=2,
                format_func=lambda x: (
                    f"{HIERARCHY_LEVELS[x]['icon']}"
                    f" {HIERARCHY_LEVELS[x]['name']}"),
                key="al_hl")
        with c2:
            lawnum = st.text_input(
                "Broj zakona", key="al_num")
            area = st.selectbox(
                "Oblast", LEGAL_AREAS, key="al_area")
            gazette = st.text_input(
                "Sl. glasnik", key="al_gaz")
            effdate = st.text_input(
                "Datum", key="al_date")
        full_text = st.text_area(
            "Tekst zakona *", height=400,
            placeholder="Član 1\nNaslov\n1. Tekst...",
            key="al_text")

        col_prev, col_save = st.columns(2)
        with col_prev:
            if st.button("👁️ Preview",
                         use_container_width=True,
                         disabled=not full_text):
                arts, warns = parse_articles(full_text)
                st.session_state.preview_articles = arts
                st.session_state.preview_warnings = warns
                st.session_state.preview_meta = {
                    "name_sr": name_sr, "name_al": name_al,
                    "short_name": short,
                    "law_number": lawnum, "area": area,
                    "gazette_info": gazette,
                    "effective_date": effdate,
                    "hierarchy_level": hlevel}

        # Prikaz preview-a
        if st.session_state.preview_articles is not None:
            arts = st.session_state.preview_articles
            warns = st.session_state.preview_warnings
            st.success(f"Pronađeno {len(arts)} članova")
            for w in (warns or []):
                st.warning(f"⚠️ {w}")
            for a in arts[:5]:
                t = f" — {a['title']}" if a['title'] else ""
                st.caption(
                    f"**Čl. {a['article_number']}{t}:**"
                    f" {a['content'][:200]}...")
            if len(arts) > 5:
                st.info(f"...i još {len(arts)-5} članova")

            with col_save:
                if st.button("✅ Sačuvaj",
                             use_container_width=True,
                             disabled=not name_sr):
                    meta = st.session_state.preview_meta
                    lid, narts, ws = save_law_to_db(
                        meta["name_sr"], meta["name_al"],
                        meta["short_name"],
                        meta["law_number"],
                        meta["area"], meta["gazette_info"],
                        meta["effective_date"], "sr",
                        full_text,
                        meta["hierarchy_level"])
                    if lid:
                        hi = HIERARCHY_LEVELS.get(
                            meta["hierarchy_level"],
                            HIERARCHY_LEVELS[3])
                        st.success(
                            f"✅ '{meta['name_sr']}'"
                            f" — {narts} čl."
                            f" {hi['icon']}")
                        st.session_state.preview_articles \
                            = None
                        st.session_state.preview_warnings \
                            = None
                        st.session_state.preview_meta = None
                        st.rerun()

    # ── EXPORT ────────────────────────────────────────────────
    with st.expander("📦 Export / Backup"):
        if st.button("📥 Izvezi sve zakone (JSON)"):
            data = export_laws_json()
            st.download_button(
                "💾 Preuzmi backup",
                data=data,
                file_name=f"laws_backup_{date.today()}.json",
                mime="application/json")

    # ── LISTA ZAKONA ──────────────────────────────────────────
    st.markdown("### 📋 Zakoni u bazi")
    try:
        with get_db() as conn:
            laws = conn.execute(
                "SELECT l.*, COUNT(la.id) as num_articles"
                " FROM laws l LEFT JOIN law_articles la"
                " ON l.id=la.law_id"
                " GROUP BY l.id"
                " ORDER BY l.hierarchy_level,"
                " l.area, l.name_sr").fetchall()
    except Exception:
        laws = []

    if not laws:
        st.warning("Nema zakona.")
    else:
        cur_lvl = None
        for law in laws:
            law = dict(law)
            hl = law.get('hierarchy_level', 3)
            hi = HIERARCHY_LEVELS.get(hl, HIERARCHY_LEVELS[3])
            if hl != cur_lvl:
                cur_lvl = hl
                st.markdown(
                    f"#### {hi['icon']} {hi['name']}")
            with st.expander(
                    f"{hi['icon']} {law['name_sr']}"
                    f" ({law.get('law_number', '')})"
                    f" — {law['num_articles']} čl."):
                st.markdown(
                    f"**Oblast:** {law.get('area', '')}"
                    f" | **Skr:** {law.get('short_name', '')}"
                    f" | **Snaga:** {hi['name']}")
                try:
                    with get_db() as conn:
                        arts = conn.execute(
                            "SELECT article_number,title,"
                            "content FROM law_articles"
                            " WHERE law_id=?"
                            " ORDER BY CAST(article_number"
                            " AS INTEGER) LIMIT 5",
                            (law["id"],)).fetchall()
                    for a in arts:
                        t = f" — {a['title']}" \
                            if a['title'] else ""
                        st.caption(
                            f"Čl. {a['article_number']}"
                            f"{t}: {a['content'][:150]}...")
                except Exception:
                    pass
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("🔄 Ponovo obradi",
                                 key=f"rep_{law['id']}"):
                        n, w = reparse_law(law["id"])
                        st.success(f"Ponovo: {n} čl.")
                        for ww in w:
                            st.warning(f"⚠️ {ww}")
                        st.rerun()
                with bc2:
                    if st.button("🗑️ Obriši",
                                 key=f"del_{law['id']}"):
                        with get_db() as conn:
                            conn.execute(
                                "DELETE FROM law_articles"
                                " WHERE law_id=?",
                                (law["id"],))
                            conn.execute(
                                "DELETE FROM laws"
                                " WHERE id=?",
                                (law["id"],))
                        st.session_state.law_vs = None
                        st.session_state.law_vs_version = ""
                        st.rerun()


def admin_users():
    st.markdown("### 👥 Korisnici")
    with st.expander("➕ Dodaj"):
        with st.form("add_u"):
            c1, c2 = st.columns(2)
            with c1:
                nn = st.text_input("Ime *", key="nu_n")
                ne = st.text_input("Email *", key="nu_e")
            with c2:
                npl = st.selectbox(
                    "Plan", list(PLANS.keys()),
                    format_func=lambda x: (
                        f"{PLANS[x]['icon']}"
                        f" {PLANS[x]['name']}"
                        f" (€{PLANS[x]['price']})"),
                    key="nu_pl")
                nd = st.number_input(
                    "Dana", 1, value=30, key="nu_d")
            npw = st.text_input(
                "Lozinka *", value="Kolevka2024!",
                key="nu_pw")
            if st.form_submit_button("✅ Kreiraj"):
                if not nn or not ne or not npw:
                    st.error("Popunite.")
                else:
                    try:
                        ph, salt = create_password_hash(npw)
                        se = (date.today() + timedelta(
                            days=nd)).isoformat()
                        with get_db() as conn:
                            conn.execute(
                                "INSERT INTO users"
                                "(email,password_hash,salt,"
                                "full_name,role,plan,"
                                "is_active,"
                                "subscription_start,"
                                "subscription_end)"
                                "VALUES(?,?,?,?,'user',"
                                "?,1,?,?)",
                                (ne.lower().strip(), ph,
                                 salt, nn, npl,
                                 date.today().isoformat(),
                                 se))
                        st.success(f"✅ {nn}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Email postoji.")
                    except Exception as e:
                        st.error(f"{e}")
    try:
        with get_db() as conn:
            users = conn.execute(
                "SELECT * FROM users WHERE role='user'"
                " ORDER BY is_active DESC,"
                "full_name").fetchall()
    except Exception:
        return
    for u in users:
        u = dict(u)
        pl = PLANS.get(u["plan"], {"name": "?", "icon": "?"})
        with st.expander(
                f"{pl['icon']} {u['full_name']}"
                f" — {u['email']}"):
            st.markdown(
                f"**Plan:** {pl['name']}"
                f" | **Do:** {u.get('subscription_end', '-')}"
                f" | {'🟢' if u['is_active'] else '🔴'}")
            c1, c2 = st.columns(2)
            with c1:
                ext = st.number_input(
                    "Dana", 1, value=30,
                    key=f"e_{u['id']}")
                if st.button("📅 Produži",
                             key=f"ext_{u['id']}"):
                    curr = (date.fromisoformat(
                        u["subscription_end"])
                        if u.get("subscription_end")
                        else date.today())
                    ne = (max(curr, date.today())
                          + timedelta(days=ext)).isoformat()
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE users SET"
                            " subscription_end=?,"
                            "is_active=1 WHERE id=?",
                            (ne, u["id"]))
                    st.rerun()
            with c2:
                if u["is_active"]:
                    if st.button("🔴 Suspenduj",
                                 key=f"s_{u['id']}"):
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users SET"
                                " is_active=0 WHERE id=?",
                                (u["id"],))
                        st.rerun()
                else:
                    if st.button("🟢 Aktiviraj",
                                 key=f"a_{u['id']}"):
                        ne = (date.today() + timedelta(
                            days=30)).isoformat()
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users SET"
                                " is_active=1,"
                                "subscription_end=?"
                                " WHERE id=?",
                                (ne, u["id"]))
                        st.rerun()


def admin_payments():
    st.markdown("### 💰 Uplate")
    with st.expander("➕ Nova"):
        try:
            with get_db() as conn:
                users = conn.execute(
                    "SELECT id,full_name,email"
                    " FROM users WHERE role='user'"
                    " ORDER BY full_name").fetchall()
        except Exception:
            return
        if not users:
            return
        with st.form("pay"):
            opts = {u["id"]: f"{u['full_name']}"
                    for u in users}
            uid = st.selectbox(
                "Korisnik", list(opts.keys()),
                format_func=lambda x: opts[x])
            c1, c2 = st.columns(2)
            with c1:
                amt = st.number_input("€", 1.0, value=19.0)
                pd = st.date_input("Datum", value=date.today())
            with c2:
                days = st.number_input("Dana", 1, value=30)
                meth = st.selectbox(
                    "Način", ["Transfer", "Gotovina",
                              "PayPal"])
            if st.form_submit_button("✅"):
                pe = (pd + timedelta(days=days)).isoformat()
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO payments"
                        "(user_id,amount,payment_date,"
                        "period_start,period_end,"
                        "method,recorded_by)"
                        "VALUES(?,?,?,?,?,?,?)",
                        (uid, amt, pd.isoformat(),
                         pd.isoformat(), pe, meth,
                         st.session_state
                         .current_user["id"]))
                    conn.execute(
                        "UPDATE users SET"
                        " subscription_end=?,"
                        "is_active=1 WHERE id=?",
                        (pe, uid))
                st.success(f"€{amt}")
                st.rerun()


def admin_settings():
    st.markdown(
        f"### ⚙️ Podešavanja\n"
        f"**bcrypt:** {'✅' if BCRYPT_AVAILABLE else '❌'}"
        f" | **Timeout:** {SESSION_TIMEOUT_MINUTES}min")
    with st.expander("🔒 Promena lozinke"):
        with st.form("chpw"):
            old = st.text_input("Trenutna", type="password")
            new = st.text_input("Nova", type="password")
            conf = st.text_input("Potvrdi", type="password")
            if st.form_submit_button("Promeni"):
                if new != conf:
                    st.error("Ne poklapaju se.")
                elif len(new) < 8:
                    st.error("Min 8.")
                else:
                    u = st.session_state.current_user
                    ok, _ = verify_password(
                        old, u["password_hash"], u["salt"])
                    if ok:
                        nh, ns = create_password_hash(new)
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users SET"
                                " password_hash=?,salt=?"
                                " WHERE id=?",
                                (nh, ns, u["id"]))
                        st.success("✅")
                    else:
                        st.error("Pogrešna.")


# ═══════════════════════════════════════════════════════════════
#  KORISNIČKI PANEL
# ═══════════════════════════════════════════════════════════════

def render_user():
    user = st.session_state.current_user
    sub = check_subscription(user)
    if not sub["active"]:
        st.markdown(
            '<div style="text-align:center;padding:4rem">'
            '<h2>🔒 Pretplata istekla</h2>'
            f'<p>{sub["message"]}</p></div>',
            unsafe_allow_html=True)
        if st.button("🚪 Odjavi se", key="exp_out"):
            do_logout()
            st.rerun()
        return
    pl = PLANS.get(user["plan"], {"name": "?", "icon": "?"})
    bc = "badge-gold"
    bt = f"{sub['days_left']}d"
    if sub["status"] == "expiring":
        bc = "badge-warn"
    elif sub["status"] == "grace":
        bc = "badge-err"
        bt = "ISTEKLO"
    st.markdown(
        '<div class="top-bar">'
        '<div style="display:flex;align-items:center;'
        'gap:12px"><span style="font-size:1.5rem">⚖️</span>'
        '<h2>Prava <span class="gold">Kolevka</span></h2>'
        '</div><div style="display:flex;gap:8px;'
        'align-items:center;flex-wrap:wrap">'
        f'<span class="badge">{pl["icon"]}'
        f' {pl["name"]}</span>'
        f'<span class="badge {bc}">{bt}</span>'
        f'<span class="badge">{user["full_name"]}</span>'
        '</div></div>', unsafe_allow_html=True)
    if sub["message"]:
        st.warning(f"⚠️ {sub['message']}")
    if not OPENAI_API_KEY:
        st.error("AI nije podešen.")
        return
    tabs = st.tabs(
        ["⚖️ Pravni AI", "🔄 Prevod",
         "📝 Podnesci", "🔍 Pretraga", "🌉 Most"])
    with tabs[0]:
        tab_ai()
    with tabs[1]:
        tab_translate()
    with tabs[2]:
        tab_docs()
    with tabs[3]:
        tab_search()
    with tabs[4]:
        tab_bridge()
    st.markdown("---")
    if st.button("🚪 Odjavi se", key="usr_out"):
        do_logout()
        st.rerun()


def tab_ai():
    user = st.session_state.current_user
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>⚖️ Pravni AI za Kosovo</h3></div>',
        unsafe_allow_html=True)
    with st.expander("📁 Učitaj dokument"):
        up = st.file_uploader(
            "PDF/TXT", type=["pdf", "txt"],
            accept_multiple_files=True, key="a_up")
        if up:
            ex = {d["name"] for d in st.session_state.docs}
            nw = [f for f in up if f.name not in ex]
            if nw:
                with st.spinner("⏳"):
                    for f in nw:
                        t, n, l = process_file(f)
                        if t:
                            st.session_state.docs.append(
                                {"name": n, "text": t})
                    try:
                        st.session_state.vs = build_vs(
                            st.session_state.docs,
                            OPENAI_API_KEY)
                        st.success(f"✅ {len(nw)}")
                    except Exception as e:
                        st.error(f"{e}")
    for msg in st.session_state.chat:
        av = "👤" if msg["role"] == "user" else "⚖️"
        with st.chat_message(msg["role"], avatar=av):
            st.markdown(msg["content"])
            if msg.get("sources_html"):
                st.markdown(
                    msg["sources_html"],
                    unsafe_allow_html=True)
    if not st.session_state.chat:
        sugs = [
            "Koja je kazna za krađu po KZ?",
            "Rokovi za žalbu u krivičnom postupku?",
            "Uslovi za razvod braka?",
            "Koja prava garantuje Ustav?"]
        cols = st.columns(2)
        for i, s in enumerate(sugs):
            with cols[i % 2]:
                if st.button(s, key=f"s_{i}",
                             use_container_width=True):
                    _ask(s, user)
                    st.rerun()
    if p := st.chat_input("Postavite pitanje..."):
        _ask(p, user)
        st.rerun()


def _ask(q, user):
    st.session_state.chat.append(
        {"role": "user", "content": q})
    ans, conf, res = query_ai(
        q, st.session_state.get("vs"))
    sh = render_sources_html(res) if res else ""
    st.session_state.chat.append({
        "role": "assistant", "content": ans,
        "sources_html": sh, "confidence": conf})
    log_action(user["id"], "query",
               f"[{conf}] len={len(q)}")


def tab_search():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>🔍 Pretraga</h3></div>',
        unsafe_allow_html=True)
    q = st.text_input("🔍", placeholder="krađa, član 325...")
    if q:
        res = search_laws(q)
        if res:
            st.success(f"{len(res)} rezultata")
            for r in res:
                src = r.get('short_name') or r['name_sr']
                art = f"Čl. {r['article_number']}"
                hl = r.get('hierarchy_level', 3)
                hi = HIERARCHY_LEVELS.get(
                    hl, HIERARCHY_LEVELS[3])
                with st.expander(
                        f"{hi['icon']} {src}: {art}"
                        f" (rel: {r.get('score', 0)})"):
                    st.markdown(r['content'])
        else:
            st.info("Nema rezultata.")


def tab_translate():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>🔄 Prevod</h3></div>',
        unsafe_allow_html=True)
    f = st.file_uploader("PDF/TXT", type=["pdf", "txt"],
                         key="tr_up")
    if f:
        t, n, l = process_file(f)
        if t and l != "sr":
            if st.button("🔄 Prevedi", type="primary",
                         use_container_width=True):
                with st.spinner("⏳"):
                    tr = translate_full(t, l)
                st.markdown(tr)
                w = create_word("Prevod", tr)
                st.download_button("📥 Word", data=w,
                                   file_name="prevod.docx")
        elif t:
            st.info("Već srpski.")


def tab_docs():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>📝 Podnesci</h3></div>',
        unsafe_allow_html=True)
    dt = st.selectbox(
        "Tip", list(DOC_TEMPLATES.keys()),
        format_func=lambda x: (
            f"{DOC_TEMPLATES[x]['icon']}"
            f" {DOC_TEMPLATES[x]['name']}"))
    info = st.text_area("Opišite slučaj", height=200)
    if st.button("📝 Generiši", disabled=not info,
                 use_container_width=True, type="primary"):
        tmpl = DOC_TEMPLATES[dt]
        with st.spinner("⏳"):
            try:
                r = get_llm(0.15, 6000).invoke(
                    [HumanMessage(
                        content=tmpl["prompt"].format(
                            info=info))])
                st.markdown(r.content)
                w = create_word(tmpl["name"], r.content)
                st.download_button("📥 Word", data=w,
                                   file_name="podnesak.docx")
            except Exception as e:
                st.error(f"{e}")


def tab_bridge():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>🌉 AL→SR</h3></div>',
        unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        al = st.text_area("🇦🇱", height=300,
                           placeholder="Vendim...",
                           label_visibility="collapsed",
                           key="br_in")
        btn = st.button("🔄 Prevedi",
                        use_container_width=True,
                        disabled=not al, key="br_go")
    with c2:
        if btn and al:
            with st.spinner("⏳"):
                st.markdown(translate_full(al, "al"))
            found = [(a, s) for a, s in LEGAL_DICT.items()
                     if a.lower() in al.lower()]
            if found:
                st.markdown("---\n**Termini:**")
                for a, s in found:
                    st.markdown(f"- **{a}** → {s}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_database()
    run_auto_suspension()
    if not st.session_state.get("logged_in", False):
        render_login()
        return
    if check_session_timeout():
        do_logout()
        st.warning("⏰ Sesija istekla.")
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
                st.session_state.current_user = dict(fresh)
            else:
                do_logout()
                st.rerun()
                return
    except Exception:
        pass
    if st.session_state.current_user["role"] == "admin":
        render_admin()
    else:
        render_user()


if __name__ == "__main__":
    main()
