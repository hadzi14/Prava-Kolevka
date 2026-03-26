"""
═══════════════════════════════════════════════════════════════
 PRAVA KOLEVKA v5.3 — Pravni AI za Kosovo
 Semantička pretraga, hijerarhija, bcrypt, session timeout
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
import plotly.graph_objects as go
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# NOVO v5.3: bcrypt sa fallback-om
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
#  KONFIGURACIJA
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="Prava Kolevka | Pravni AI za Kosovo",
    page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

def get_secret(key, default=""):
    try: return st.secrets[key]
    except: return os.environ.get(key, default)

OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
ADMIN_EMAIL = get_secret("ADMIN_EMAIL", "admin@pravakolevka.rs")
ADMIN_DEFAULT_PASSWORD = get_secret("ADMIN_PASSWORD", "PravaKolevka2024!")

# NOVO v5.3: Session timeout (minuti)
SESSION_TIMEOUT_MINUTES = 480  # 8 sati

NAVY = "#0A1628"; NAVY_MID = "#1B2A4A"
GOLD = "#C5962C"; GOLD_LIGHT = "#F0E6C8"; GOLD_PALE = "#FBF7ED"
SURFACE = "#F5F4F0"; CARD_BG = "#FFFFFF"; TEXT_MUTED = "#6B7280"
SUCCESS = "#059669"; ERROR = "#DC2626"; WARNING = "#D97706"

PLANS = {
    "solo":{"name":"Solo Advokat","price":29,"max_users":1,"icon":"🥉","can_share":False},
    "kancelarija":{"name":"Kancelarija","price":79,"max_users":5,"icon":"🥈","can_share":True},
    "firma":{"name":"Firma","price":149,"max_users":15,"icon":"🥇","can_share":True},
    "enterprise":{"name":"Enterprise","price":0,"max_users":999,"icon":"💎","can_share":True},
}
GRACE_PERIOD_DAYS = 3
LANG_NAMES = {"sr":"Srpski","al":"Albanski","en":"Engleski"}

HIERARCHY_LEVELS = {
    1: {"name": "Ustav", "icon": "👑", "weight": 15,
        "desc": "Najviši pravni akt — ima prednost nad svim zakonima"},
    2: {"name": "Međunarodni sporazum", "icon": "🌍", "weight": 10,
        "desc": "Ratifikovani međunarodni ugovori i konvencije"},
    3: {"name": "Zakon", "icon": "📜", "weight": 5,
        "desc": "Zakon usvojen u Skupštini Kosova"},
    4: {"name": "Podzakonski akt", "icon": "📋", "weight": 2,
        "desc": "Uredba, pravilnik, uputstvo"},
    5: {"name": "Opštinski propis", "icon": "🏘️", "weight": 0,
        "desc": "Lokalni propisi opštinskog nivoa"},
}

LEGAL_AREAS = [
    "Krivično pravo","Krivični postupak","Građansko pravo",
    "Parnični postupak","Upravno pravo","Radno pravo",
    "Porodično pravo","Prekršajno pravo","Pravosuđe",
    "Tužilaštvo","Advokatura","Policijsko pravo",
    "Obligaciono pravo","Imovinsko pravo","Ustavno pravo","Ostalo",
]

AREA_KEYWORDS = {
    "Krivično pravo": [
        "krivičn","kazna","kazne","kažnjav","delo","krađa","ubistvo",
        "razbojništvo","prevara","falsifik","nasilj","pretnja","silovanj",
        "zlostavljanj","korupcij","mito","pranje novca","terorizam",
        "oružje","droga","narkotik","polni","seksualni","maloletnič",
        "saobraćaj","krivic","zatvor","robija","uslovn","probacij",
        "saučesniš","pokušaj","pripremne radnje","nužna odbrana",
        "krajnja nužda","uračunljiv","umišljaj","nehat","recidiv",
    ],
    "Krivični postupak": [
        "postupak","pritvor","hapšenj","istrag","optužnic","suđenj",
        "presud","žalb","dokaz","svedok","veštačenj","pretres",
        "branilac","okrivljeni","osumnjičeni","tužilac","odbranu",
        "saslušanj","ročišt","prigovor","revizij","obnova postupka",
        "troškovi postupka","nadležnost","izuzeće",
        "pritvorsk","zadržavanj","jemstv","mera","privremen",
    ],
    "Građansko pravo": [
        "obligacij","ugovor","šteta","naknada","odgovornost",
        "potraživanj","dug","zajam","kredit","jemstv","zalog",
        "hipoteka","zakup","prodaj","kupovin","poklon","razmena",
        "zastupanj","punomoć","zastarelost","kamata","penali",
    ],
    "Parnični postupak": [
        "parnič","tužba","tužilac","tuženi","suđenje","prvostepen",
        "drugostepen","revizija","vanredni pravni lek","troškovi",
        "nadležnost","mesna nadležnost","stvarna nadležnost","dokaz",
        "izvršenje","presuda","rešenje","veštačenje","svedok",
    ],
    "Porodično pravo": [
        "brak","razvod","supružni","alimentacij","izdržavanj",
        "starateljstv","usvojenj","roditeljsk","dete","deca",
        "porodičn","bračn","zajednic","imovina supružnika",
        "nasilj u porodici","skrbnišstv","hraniteljstv",
    ],
    "Radno pravo": [
        "rad","zaposlen","radni odnos","otkaz","plata","odmor",
        "prekovremeni","ugovor o radu","kolektivni","sindikat",
        "štrajk","penzij","invalidsk","bolovanje","trudnoć",
        "porodiljsko","diskriminacij","mobbing","zlostavljanj na radu",
    ],
    "Upravno pravo": [
        "upravn","organ","rešenj","žalba","inspekcij","dozvol",
        "građevinska","lokalna samouprava","opštin","ministarstv",
        "služben","javna nabavka","koncesij","eksproprijacij",
    ],
    "Prekršajno pravo": [
        "prekršaj","novčana kazna","mandatna","saobraćajni prekršaj",
        "komunalni","prekršajn","opomena","zabrana","oduzimanje",
    ],
    "Pravosuđe": [
        "sudij","sud","sudski","imenovanje sudija","razrešenje",
        "sudski savet","vrhovni sud","apelacion","osnovni sud",
        "nezavisnost","nepristrasnost",
    ],
    "Tužilaštvo": [
        "tužilaštv","tužilac","javni tužilac","državni tužilac",
        "krivično gonjenje","istraga","optužba",
    ],
    "Advokatura": [
        "advokat","advokatsk","odbrana","branilac","punomoćnik",
        "zastupnik","advokatska komora","licenc","disciplinsk",
    ],
    "Policijsko pravo": [
        "policij","policajac","privođenj","legitimisanj","pretresanj",
        "upotreba sile","ovlašćenj","patrola","hapšenj",
    ],
    "Ustavno pravo": [
        "ustav","ustavni","osnovna prava","ljudska prava","slobode",
        "građanin","državljanstvo","referendum","ustavni sud",
        "amandman","preambula","suverenitet",
    ],
}

SHORTNAME_MAP = {
    "kz": ["Krivični zakonik", "Krivicni zakonik"],
    "krivični zakonik": ["Krivični zakonik"],
    "krivicni zakonik": ["Krivični zakonik"],
    "zkp": ["Zakonik o krivičnom postupku", "Zakon o krivičnom postupku"],
    "zakonik o krivičnom postupku": ["Zakonik o krivičnom postupku"],
    "zoo": ["Zakon o obligacionim odnosima"],
    "zakon o obligacionim odnosima": ["Zakon o obligacionim odnosima"],
    "zpp": ["Zakon o parničnom postupku"],
    "zakon o parničnom postupku": ["Zakon o parničnom postupku"],
    "zor": ["Zakon o radu"],
    "zakon o radu": ["Zakon o radu"],
    "pz": ["Porodični zakon"],
    "porodični zakon": ["Porodični zakon", "Porodicni zakon"],
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
    "zakon republike srbije","zakon rs","službeni glasnik rs",
    "krivični zakonik srbije","zakonik srbije","republika srbija",
    "narodna skupština","vrhovni kasacioni sud","vrhovni sud srbije",
    "po srpskom pravu","u srbiji","zakon srbije","prema pravu srbije",
]


# ═══════════════════════════════════════════════════════════════
#  SESSION STATE — NOVO v5.3: login_time za timeout
# ═══════════════════════════════════════════════════════════════

def init_ss():
    for k, v in {"logged_in":False,"current_user":None,"docs":[],"vs":None,
                 "events":[],"chat":[],"ocr_text":"",
                 "law_vs":None,"law_vs_version":"",
                 "login_time":None}.items():
        if k not in st.session_state:
            st.session_state[k] = v
init_ss()


# ═══════════════════════════════════════════════════════════════
#  NOVO v5.3: BEZBEDNOST LOZINKI — bcrypt + migracija
# ═══════════════════════════════════════════════════════════════

def hash_password_legacy(pw, salt):
    """Stari SHA-256 hash — samo za proveru postojećih korisnika."""
    return hashlib.sha256((pw + salt).encode()).hexdigest()


def create_password_hash(password: str) -> Tuple[str, str]:
    """Kreira hash lozinke. Koristi bcrypt ako je dostupan, inače SHA-256."""
    if BCRYPT_AVAILABLE:
        hashed = bcrypt.hashpw(password.encode('utf-8'),
                               bcrypt.gensalt(rounds=12)).decode('utf-8')
        return hashed, "bcrypt"
    else:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hashed, salt


def verify_password(password: str, stored_hash: str,
                    stored_salt: str) -> Tuple[bool, bool]:
    """
    Proverava lozinku. Vraća (tačna_lozinka, treba_upgrade).
    Podržava i stari SHA-256 i novi bcrypt format.
    """
    # Ako je bcrypt hash (počinje sa $2b$ ili $2a$)
    if BCRYPT_AVAILABLE and (stored_hash.startswith('$2b$')
                             or stored_hash.startswith('$2a$')):
        try:
            valid = bcrypt.checkpw(password.encode('utf-8'),
                                   stored_hash.encode('utf-8'))
            return valid, False
        except Exception:
            return False, False

    # Stari SHA-256 format
    if stored_salt and stored_salt != "bcrypt":
        legacy = hashlib.sha256(
            (password + stored_salt).encode()).hexdigest()
        if legacy == stored_hash:
            return True, BCRYPT_AVAILABLE  # Treba upgrade ako bcrypt postoji
        return False, False

    return False, False


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Autentifikacija sa automatskom migracijom na bcrypt."""
    try:
        with get_db() as conn:
            u = conn.execute(
                "SELECT * FROM users WHERE email=?",
                (email.lower().strip(),)
            ).fetchone()
            if not u:
                return None

            is_valid, needs_upgrade = verify_password(
                password, u["password_hash"], u["salt"])

            if not is_valid:
                return None

            # Auto-upgrade na bcrypt
            if needs_upgrade and BCRYPT_AVAILABLE:
                new_hash, new_salt = create_password_hash(password)
                conn.execute(
                    "UPDATE users SET password_hash=?, salt=? WHERE id=?",
                    (new_hash, new_salt, u["id"]))

            return dict(u)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  BAZA PODATAKA
# ═══════════════════════════════════════════════════════════════

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "prava_kolevka.db")

@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn; conn.commit()
    except sqlite3.Error as e:
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()

def init_database():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                salt TEXT NOT NULL, full_name TEXT NOT NULL,
                role TEXT DEFAULT 'user', firm_name TEXT DEFAULT '',
                phone TEXT DEFAULT '', plan TEXT DEFAULT 'solo',
                is_active INTEGER DEFAULT 1,
                subscription_start TEXT, subscription_end TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT, auto_suspended INTEGER DEFAULT 0,
                suspended_reason TEXT DEFAULT '', notes TEXT DEFAULT ''
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, amount REAL NOT NULL,
                payment_date TEXT NOT NULL, period_start TEXT,
                period_end TEXT, status TEXT DEFAULT 'completed',
                method TEXT DEFAULT 'manual', notes TEXT DEFAULT '',
                recorded_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, action TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS laws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_sr TEXT NOT NULL, name_al TEXT DEFAULT '',
                short_name TEXT DEFAULT '', law_number TEXT DEFAULT '',
                area TEXT DEFAULT 'Ostalo', gazette_info TEXT DEFAULT '',
                effective_date TEXT DEFAULT '', is_active INTEGER DEFAULT 1,
                language TEXT DEFAULT 'sr', full_text TEXT DEFAULT '',
                hierarchy_level INTEGER DEFAULT 3,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS law_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_id INTEGER NOT NULL, article_number TEXT NOT NULL,
                paragraph_number TEXT DEFAULT '', title TEXT DEFAULT '',
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (law_id) REFERENCES laws(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, source_filename TEXT,
                source_language TEXT, source_text TEXT,
                translated_text TEXT, legal_analysis TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS generated_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, doc_type TEXT,
                content TEXT, created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL, title TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS case_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL, shared_with_email TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (case_id) REFERENCES cases(id)
            )""")
            # Migracija: dodaj hierarchy_level ako ne postoji
            try:
                c.execute("SELECT hierarchy_level FROM laws LIMIT 1")
            except Exception:
                c.execute(
                    "ALTER TABLE laws ADD COLUMN hierarchy_level"
                    " INTEGER DEFAULT 3")
            # Admin korisnik — NOVO v5.3: bcrypt
            admin = c.execute(
                "SELECT id FROM users WHERE email=?",
                (ADMIN_EMAIL,)).fetchone()
            if not admin:
                ph, salt = create_password_hash(ADMIN_DEFAULT_PASSWORD)
                c.execute("""INSERT INTO users
                    (email,password_hash,salt,full_name,role,plan,
                     is_active,subscription_start,subscription_end)
                    VALUES (?,?,?,?,'admin','enterprise',1,?,?)""",
                    (ADMIN_EMAIL, ph, salt, "Administrator",
                     date.today().isoformat(),
                     (date.today()+timedelta(days=36500)).isoformat()))
    except Exception as e:
        st.error(f"DB init: {e}")


# ═══════════════════════════════════════════════════════════════
#  PARSIRANJE ZAKONA
# ═══════════════════════════════════════════════════════════════

def clean_pdf_text(text: str) -> str:
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^ +| +$', '', text, flags=re.MULTILINE)
    return text.strip()


def parse_law_into_articles(full_text: str) -> Tuple[List[Dict], List[str]]:
    warnings = []
    text = clean_pdf_text(full_text)
    articles = []

    patterns = [
        re.compile(
            r'(?:^|\n)\s*(?:Član|ČLAN|Članak|ČLANAK)\s+(\d+[a-zA-Z]?)'
            r'\s*\.?\s*\n(.*?)'
            r'(?=\n\s*(?:Član|ČLAN|Članak|ČLANAK)\s+\d|\Z)',
            re.DOTALL | re.IGNORECASE),
        re.compile(
            r'(?:^|\n)\s*(?:Neni|NENI)\s+(\d+[a-zA-Z]?)'
            r'\s*\.?\s*\n(.*?)'
            r'(?=\n\s*(?:Neni|NENI)\s+\d|\Z)',
            re.DOTALL | re.IGNORECASE),
        re.compile(
            r'(?:^|\n)\s*(?:Član|ČLAN)\s+(\d+[a-zA-Z]?)'
            r'\s*[.\s]*[-–—]\s*(.*?)'
            r'(?=\n\s*(?:Član|ČLAN)\s+\d|\Z)',
            re.DOTALL | re.IGNORECASE),
        re.compile(
            r'(?:^|\n)\s*(?:Član|ČLAN|Neni|NENI)\s*[:\s]*(\d+[a-zA-Z]?)'
            r'\s*[.:\-–—]?\s*(.*?)'
            r'(?=\n\s*(?:Član|ČLAN|Neni|NENI)\s*[:\s]*\d|\Z)',
            re.DOTALL | re.IGNORECASE),
    ]

    best_matches = []
    for pattern in patterns:
        matches = list(pattern.finditer(text))
        if len(matches) > len(best_matches):
            best_matches = matches

    if not best_matches:
        warnings.append(
            "Nije pronađena struktura članova."
            " Ceo tekst tretiran kao jedan blok.")
        articles.append({
            "article_number": "0", "paragraph_number": "",
            "title": "(Neparsirani tekst)",
            "content": text[:10000]
        })
        return articles, warnings

    if len(best_matches) < 3:
        warnings.append(
            f"Pronađeno samo {len(best_matches)} članova."
            " Moguće da format nije prepoznat u celosti.")

    for match in best_matches:
        article_num = match.group(1).strip()
        article_body = match.group(2).strip()
        if not article_body:
            continue

        lines = article_body.split('\n')
        title = ""
        content_start = 0
        if lines:
            first_line = lines[0].strip()
            if (len(first_line) < 120
                    and not re.match(r'^\d+[\.\)]', first_line)
                    and len(lines) > 1):
                title = first_line
                content_start = 1

        content = '\n'.join(lines[content_start:]).strip()
        if not content and title:
            content = title
            title = ""

        para_pattern = re.compile(r'(?:^|\n)\s*(\d+)\s*[\.\)]\s+')
        para_splits = list(para_pattern.finditer(content))

        if len(para_splits) >= 2:
            pre_text = content[:para_splits[0].start()].strip()
            if pre_text:
                articles.append({
                    "article_number": article_num,
                    "paragraph_number": "",
                    "title": title, "content": pre_text
                })
            for i, pm in enumerate(para_splits):
                para_num = pm.group(1)
                start = pm.end()
                end = (para_splits[i+1].start()
                       if i+1 < len(para_splits) else len(content))
                para_text = content[start:end].strip()
                if para_text:
                    articles.append({
                        "article_number": article_num,
                        "paragraph_number": para_num,
                        "title": title, "content": para_text
                    })
        else:
            articles.append({
                "article_number": article_num,
                "paragraph_number": "",
                "title": title, "content": content
            })

    empty_count = sum(1 for a in articles if len(a["content"]) < 10)
    if empty_count > len(articles) * 0.3:
        warnings.append(
            f"{empty_count} od {len(articles)} članova"
            " ima vrlo kratak sadržaj.")

    return articles, warnings


def save_law_to_db(name_sr, name_al, short_name, law_number, area,
                   gazette_info, effective_date, language, full_text,
                   hierarchy_level=3):
    try:
        articles, warnings = parse_law_into_articles(full_text)
        with get_db() as conn:
            conn.execute("""
                INSERT INTO laws (name_sr, name_al, short_name, law_number,
                area, gazette_info, effective_date, language, full_text,
                hierarchy_level)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (name_sr, name_al, short_name, law_number, area,
                  gazette_info, effective_date, language, full_text,
                  hierarchy_level))
            law_id = conn.execute(
                "SELECT last_insert_rowid()").fetchone()[0]
            for art in articles:
                conn.execute("""
                    INSERT INTO law_articles (law_id, article_number,
                    paragraph_number, title, content)
                    VALUES (?,?,?,?,?)
                """, (law_id, art["article_number"],
                      art.get("paragraph_number", ""),
                      art.get("title", ""), art["content"]))
            st.session_state.law_vs = None
            st.session_state.law_vs_version = ""
            return law_id, len(articles), warnings
    except Exception as e:
        return None, 0, [f"Greška: {e}"]


# ═══════════════════════════════════════════════════════════════
#  VEKTORSKA PRETRAGA ZAKONA
# ═══════════════════════════════════════════════════════════════

def get_law_vs_version():
    try:
        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM law_articles").fetchone()[0]
            last = conn.execute(
                "SELECT MAX(created_at) FROM law_articles"
            ).fetchone()[0] or ""
            return f"{count}_{last}"
    except:
        return "0_"


def build_law_vector_store():
    if not OPENAI_API_KEY:
        return None
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT la.id, la.article_number, la.paragraph_number,
                       la.title, la.content,
                       l.name_sr, l.short_name, l.law_number, l.area,
                       l.hierarchy_level
                FROM law_articles la JOIN laws l ON la.law_id = l.id
                WHERE l.is_active = 1
            """).fetchall()
        if not rows:
            return None
        documents = []
        for row in rows:
            row = dict(row)
            source = row.get('short_name') or row['name_sr']
            art_ref = f"Član {row['article_number']}"
            if row.get('paragraph_number'):
                art_ref += f", stav {row['paragraph_number']}"
            h_level = row.get('hierarchy_level', 3)
            h_info = HIERARCHY_LEVELS.get(h_level, HIERARCHY_LEVELS[3])
            embed_text = f"{h_info['name']}: {source} {art_ref}"
            if row.get('title'):
                embed_text += f" {row['title']}"
            embed_text += f"\n{row['content']}"
            doc = Document(
                page_content=embed_text,
                metadata={
                    "article_number": row['article_number'],
                    "paragraph_number": row.get('paragraph_number', ''),
                    "title": row.get('title', ''),
                    "content": row['content'],
                    "name_sr": row['name_sr'],
                    "short_name": row.get('short_name', ''),
                    "law_number": row.get('law_number', ''),
                    "area": row.get('area', ''),
                    "hierarchy_level": h_level,
                })
            documents.append(doc)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200)
        final_docs = []
        for doc in documents:
            if len(doc.page_content) > 1200:
                chunks = splitter.split_documents([doc])
                final_docs.extend(chunks)
            else:
                final_docs.append(doc)
        if not final_docs:
            return None
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", api_key=OPENAI_API_KEY)
        return FAISS.from_documents(final_docs, embeddings)
    except Exception:
        return None


def get_law_vector_store():
    current_version = get_law_vs_version()
    if (st.session_state.get("law_vs") is not None
            and st.session_state.get("law_vs_version") == current_version
            and current_version != "0_"):
        return st.session_state.law_vs
    vs = build_law_vector_store()
    st.session_state.law_vs = vs
    st.session_state.law_vs_version = current_version
    return vs


# ═══════════════════════════════════════════════════════════════
#  PRETRAGA ZAKONA (SQL + SEMANTIČKA + HIJERARHIJA)
# ═══════════════════════════════════════════════════════════════

def detect_legal_area(query: str) -> List[str]:
    q = query.lower()
    detected = []
    for area, keywords in AREA_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q)
        if score >= 1:
            detected.append((area, score))
    detected.sort(key=lambda x: x[1], reverse=True)
    return [a for a, s in detected[:3]]


def detect_target_law(query: str) -> List[str]:
    q = query.lower()
    targets = []
    for shortname, full_names in SHORTNAME_MAP.items():
        if shortname in q:
            targets.extend(full_names)
    return list(set(targets))


def detect_jurisdiction_issue(query: str) -> Optional[str]:
    q = query.lower()
    for marker in SERBIA_MARKERS:
        if marker in q:
            return marker
    return None


def search_laws(query: str, max_results: int = 15) -> List[Dict]:
    q_lower = query.lower()
    stop_words = {
        'je','su','da','li','se','na','u','i','za','od','sa','po',
        'ne','ni','što','šta','kako','koji','koja','koje','ko',
        'ako','ali','ili','kad','kada','gde','iz','do','bi','mi',
        'ti','on','ona','oni','vi','taj','ta','to','ovo','može',
        'mora','treba','prema','biti','bude','sam','jedan','neki',
        'sve','svi','svoj','ima','nema','radi','kaže','član','stav',
        'zakon','pravo','pravni','zakonski','molim','pitanje',
    }
    words = re.findall(r'[a-zA-ZčćžšđČĆŽŠĐ]+', q_lower)
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]

    article_match = re.search(
        r'(?:član|članu|člana|članka|neni)\s*[:\s]*(\d+[a-zA-Z]?)',
        q_lower)
    target_article = article_match.group(1) if article_match else None
    target_laws = detect_target_law(query)
    target_areas = detect_legal_area(query)

    results = []
    seen_keys = set()

    def add_result(row_dict, base_score):
        key = (f"{row_dict['name_sr']}"
               f"|{row_dict['article_number']}"
               f"|{row_dict.get('paragraph_number','')}")
        if key in seen_keys:
            return
        seen_keys.add(key)
        h_level = row_dict.get('hierarchy_level', 3)
        h_bonus = HIERARCHY_LEVELS.get(
            h_level, HIERARCHY_LEVELS[3])['weight']
        row_dict['score'] = base_score + h_bonus
        row_dict['hierarchy_level'] = h_level
        results.append(row_dict)

    try:
        with get_db() as conn:
            bq = """
                SELECT la.article_number, la.paragraph_number,
                       la.title, la.content,
                       l.name_sr, l.short_name, l.law_number, l.area,
                       l.hierarchy_level
                FROM law_articles la JOIN laws l ON la.law_id = l.id
                WHERE l.is_active=1
            """
            if target_article and target_laws:
                for ln in target_laws:
                    rows = conn.execute(
                        bq + " AND la.article_number=?"
                        " AND (l.name_sr LIKE ? OR l.short_name LIKE ?)",
                        (target_article, f"%{ln}%", f"%{ln}%")).fetchall()
                    for row in rows:
                        add_result(dict(row), 200)

            if target_article:
                rows = conn.execute(
                    bq + " AND la.article_number=?",
                    (target_article,)).fetchall()
                for row in rows:
                    r = dict(row)
                    ab = 50 if r.get('area') in target_areas else 0
                    add_result(r, 150 + ab)

            if target_laws and keywords:
                for ln in target_laws:
                    for kw in keywords[:6]:
                        rows = conn.execute(
                            bq + " AND (l.name_sr LIKE ? OR l.short_name"
                            " LIKE ?) AND (la.content LIKE ? OR"
                            " la.title LIKE ?) LIMIT 5",
                            (f"%{ln}%", f"%{ln}%",
                             f"%{kw}%", f"%{kw}%")).fetchall()
                        for row in rows:
                            r = dict(row)
                            cl = r['content'].lower()
                            kc = sum(1 for k in keywords if k in cl)
                            add_result(r, 100 + kc * 10)

            if keywords and target_areas:
                for kw in keywords[:5]:
                    for area in target_areas[:2]:
                        rows = conn.execute(
                            bq + " AND l.area=? AND (la.content LIKE ?"
                            " OR la.title LIKE ?) LIMIT 5",
                            (area, f"%{kw}%", f"%{kw}%")).fetchall()
                        for row in rows:
                            r = dict(row)
                            cl = r['content'].lower()
                            kc = sum(1 for k in keywords if k in cl)
                            add_result(r, 60 + kc * 10)

            if keywords:
                for kw in keywords[:5]:
                    rows = conn.execute(
                        bq + " AND (la.content LIKE ? OR la.title LIKE ?)"
                        " LIMIT 8",
                        (f"%{kw}%", f"%{kw}%")).fetchall()
                    for row in rows:
                        r = dict(row)
                        cl = r['content'].lower()
                        kc = sum(1 for k in keywords if k in cl)
                        ab = 15 if r.get('area') in target_areas else 0
                        add_result(r, 20 + kc * 10 + ab)
    except Exception as e:
        st.error(f"Greška pretrage: {e}")

    law_vs = get_law_vector_store()
    if law_vs:
        try:
            sem_docs = law_vs.similarity_search_with_score(query, k=10)
            for doc, distance in sem_docs:
                meta = doc.metadata
                if distance < 1.5:
                    sem_score = max(5, int(90 * (1 - distance / 1.5)))
                    r = {
                        'article_number': meta.get('article_number', ''),
                        'paragraph_number': meta.get(
                            'paragraph_number', ''),
                        'title': meta.get('title', ''),
                        'content': meta.get(
                            'content', doc.page_content),
                        'name_sr': meta.get('name_sr', ''),
                        'short_name': meta.get('short_name', ''),
                        'law_number': meta.get('law_number', ''),
                        'area': meta.get('area', ''),
                        'hierarchy_level': meta.get(
                            'hierarchy_level', 3),
                    }
                    if target_areas and r.get('area') in target_areas:
                        sem_score += 15
                    if target_laws:
                        for tl in target_laws:
                            if tl.lower() in r.get(
                                    'name_sr', '').lower():
                                sem_score += 20
                                break
                    add_result(r, sem_score)
        except Exception:
            pass

    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    return results[:max_results]


 """
═══════════════════════════════════════════════════════════════
 PRAVA KOLEVKA v5.3 — Pravni AI za Kosovo
 Semantička pretraga, hijerarhija, bcrypt, session timeout
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
import plotly.graph_objects as go
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# NOVO v5.3: bcrypt sa fallback-om
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
 

# ═══════════════════════════════════════════════════════════════
#  KONFIGURACIJA
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="Prava Kolevka | Pravni AI za Kosovo",
    page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

def get_secret(key, default=""):
    try: return st.secrets[key]
    except: return os.environ.get(key, default)

OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
ADMIN_EMAIL = get_secret("ADMIN_EMAIL", "admin@pravakolevka.rs")
ADMIN_DEFAULT_PASSWORD = get_secret("ADMIN_PASSWORD", "PravaKolevka2024!")

# NOVO v5.3: Session timeout (minuti)
SESSION_TIMEOUT_MINUTES = 480  # 8 sati

NAVY = "#0A1628"; NAVY_MID = "#1B2A4A"
GOLD = "#C5962C"; GOLD_LIGHT = "#F0E6C8"; GOLD_PALE = "#FBF7ED"
SURFACE = "#F5F4F0"; CARD_BG = "#FFFFFF"; TEXT_MUTED = "#6B7280"
SUCCESS = "#059669"; ERROR = "#DC2626"; WARNING = "#D97706"

PLANS = {
    "solo":{"name":"Solo Advokat","price":29,"max_users":1,"icon":"🥉","can_share":False},
    "kancelarija":{"name":"Kancelarija","price":79,"max_users":5,"icon":"🥈","can_share":True},
    "firma":{"name":"Firma","price":149,"max_users":15,"icon":"🥇","can_share":True},
    "enterprise":{"name":"Enterprise","price":0,"max_users":999,"icon":"💎","can_share":True},
}
GRACE_PERIOD_DAYS = 3
LANG_NAMES = {"sr":"Srpski","al":"Albanski","en":"Engleski"}

HIERARCHY_LEVELS = {
    1: {"name": "Ustav", "icon": "👑", "weight": 15,
        "desc": "Najviši pravni akt — ima prednost nad svim zakonima"},
    2: {"name": "Međunarodni sporazum", "icon": "🌍", "weight": 10,
        "desc": "Ratifikovani međunarodni ugovori i konvencije"},
    3: {"name": "Zakon", "icon": "📜", "weight": 5,
        "desc": "Zakon usvojen u Skupštini Kosova"},
    4: {"name": "Podzakonski akt", "icon": "📋", "weight": 2,
        "desc": "Uredba, pravilnik, uputstvo"},
    5: {"name": "Opštinski propis", "icon": "🏘️", "weight": 0,
        "desc": "Lokalni propisi opštinskog nivoa"},
}

LEGAL_AREAS = [
    "Krivično pravo","Krivični postupak","Građansko pravo",
    "Parnični postupak","Upravno pravo","Radno pravo",
    "Porodično pravo","Prekršajno pravo","Pravosuđe",
    "Tužilaštvo","Advokatura","Policijsko pravo",
    "Obligaciono pravo","Imovinsko pravo","Ustavno pravo","Ostalo",
]

AREA_KEYWORDS = {
    "Krivično pravo": [
        "krivičn","kazna","kazne","kažnjav","delo","krađa","ubistvo",
        "razbojništvo","prevara","falsifik","nasilj","pretnja","silovanj",
        "zlostavljanj","korupcij","mito","pranje novca","terorizam",
        "oružje","droga","narkotik","polni","seksualni","maloletnič",
        "saobraćaj","krivic","zatvor","robija","uslovn","probacij",
        "saučesniš","pokušaj","pripremne radnje","nužna odbrana",
        "krajnja nužda","uračunljiv","umišljaj","nehat","recidiv",
    ],
    "Krivični postupak": [
        "postupak","pritvor","hapšenj","istrag","optužnic","suđenj",
        "presud","žalb","dokaz","svedok","veštačenj","pretres",
        "branilac","okrivljeni","osumnjičeni","tužilac","odbranu",
        "saslušanj","ročišt","prigovor","revizij","obnova postupka",
        "troškovi postupka","nadležnost","izuzeće",
        "pritvorsk","zadržavanj","jemstv","mera","privremen",
    ],
    "Građansko pravo": [
        "obligacij","ugovor","šteta","naknada","odgovornost",
        "potraživanj","dug","zajam","kredit","jemstv","zalog",
        "hipoteka","zakup","prodaj","kupovin","poklon","razmena",
        "zastupanj","punomoć","zastarelost","kamata","penali",
    ],
    "Parnični postupak": [
        "parnič","tužba","tužilac","tuženi","suđenje","prvostepen",
        "drugostepen","revizija","vanredni pravni lek","troškovi",
        "nadležnost","mesna nadležnost","stvarna nadležnost","dokaz",
        "izvršenje","presuda","rešenje","veštačenje","svedok",
    ],
    "Porodično pravo": [
        "brak","razvod","supružni","alimentacij","izdržavanj",
        "starateljstv","usvojenj","roditeljsk","dete","deca",
        "porodičn","bračn","zajednic","imovina supružnika",
        "nasilj u porodici","skrbnišstv","hraniteljstv",
    ],
    "Radno pravo": [
        "rad","zaposlen","radni odnos","otkaz","plata","odmor",
        "prekovremeni","ugovor o radu","kolektivni","sindikat",
        "štrajk","penzij","invalidsk","bolovanje","trudnoć",
        "porodiljsko","diskriminacij","mobbing","zlostavljanj na radu",
    ],
    "Upravno pravo": [
        "upravn","organ","rešenj","žalba","inspekcij","dozvol",
        "građevinska","lokalna samouprava","opštin","ministarstv",
        "služben","javna nabavka","koncesij","eksproprijacij",
    ],
    "Prekršajno pravo": [
        "prekršaj","novčana kazna","mandatna","saobraćajni prekršaj",
        "komunalni","prekršajn","opomena","zabrana","oduzimanje",
    ],
    "Pravosuđe": [
        "sudij","sud","sudski","imenovanje sudija","razrešenje",
        "sudski savet","vrhovni sud","apelacion","osnovni sud",
        "nezavisnost","nepristrasnost",
    ],
    "Tužilaštvo": [
        "tužilaštv","tužilac","javni tužilac","državni tužilac",
        "krivično gonjenje","istraga","optužba",
    ],
    "Advokatura": [
        "advokat","advokatsk","odbrana","branilac","punomoćnik",
        "zastupnik","advokatska komora","licenc","disciplinsk",
    ],
    "Policijsko pravo": [
        "policij","policajac","privođenj","legitimisanj","pretresanj",
        "upotreba sile","ovlašćenj","patrola","hapšenj",
    ],
    "Ustavno pravo": [
        "ustav","ustavni","osnovna prava","ljudska prava","slobode",
        "građanin","državljanstvo","referendum","ustavni sud",
        "amandman","preambula","suverenitet",
    ],
}

SHORTNAME_MAP = {
    "kz": ["Krivični zakonik", "Krivicni zakonik"],
    "krivični zakonik": ["Krivični zakonik"],
    "krivicni zakonik": ["Krivični zakonik"],
    "zkp": ["Zakonik o krivičnom postupku", "Zakon o krivičnom postupku"],
    "zakonik o krivičnom postupku": ["Zakonik o krivičnom postupku"],
    "zoo": ["Zakon o obligacionim odnosima"],
    "zakon o obligacionim odnosima": ["Zakon o obligacionim odnosima"],
    "zpp": ["Zakon o parničnom postupku"],
    "zakon o parničnom postupku": ["Zakon o parničnom postupku"],
    "zor": ["Zakon o radu"],
    "zakon o radu": ["Zakon o radu"],
    "pz": ["Porodični zakon"],
    "porodični zakon": ["Porodični zakon", "Porodicni zakon"],
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
    "zakon republike srbije","zakon rs","službeni glasnik rs",
    "krivični zakonik srbije","zakonik srbije","republika srbija",
    "narodna skupština","vrhovni kasacioni sud","vrhovni sud srbije",
    "po srpskom pravu","u srbiji","zakon srbije","prema pravu srbije",
]


# ═══════════════════════════════════════════════════════════════
#  SESSION STATE — NOVO v5.3: login_time za timeout
# ═══════════════════════════════════════════════════════════════

def init_ss():
    for k, v in {"logged_in":False,"current_user":None,"docs":[],"vs":None,
                 "events":[],"chat":[],"ocr_text":"",
                 "law_vs":None,"law_vs_version":"",
                 "login_time":None}.items():
        if k not in st.session_state:
            st.session_state[k] = v
init_ss()


# ═══════════════════════════════════════════════════════════════
#  NOVO v5.3: BEZBEDNOST LOZINKI — bcrypt + migracija
# ═══════════════════════════════════════════════════════════════

def hash_password_legacy(pw, salt):
    """Stari SHA-256 hash — samo za proveru postojećih korisnika."""
    return hashlib.sha256((pw + salt).encode()).hexdigest()


def create_password_hash(password: str) -> Tuple[str, str]:
    """Kreira hash lozinke. Koristi bcrypt ako je dostupan, inače SHA-256."""
    if BCRYPT_AVAILABLE:
        hashed = bcrypt.hashpw(password.encode('utf-8'),
                               bcrypt.gensalt(rounds=12)).decode('utf-8')
        return hashed, "bcrypt"
    else:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hashed, salt


def verify_password(password: str, stored_hash: str,
                    stored_salt: str) -> Tuple[bool, bool]:
    """
    Proverava lozinku. Vraća (tačna_lozinka, treba_upgrade).
    Podržava i stari SHA-256 i novi bcrypt format.
    """
    # Ako je bcrypt hash (počinje sa $2b$ ili $2a$)
    if BCRYPT_AVAILABLE and (stored_hash.startswith('$2b$')
                             or stored_hash.startswith('$2a$')):
        try:
            valid = bcrypt.checkpw(password.encode('utf-8'),
                                   stored_hash.encode('utf-8'))
            return valid, False
        except Exception:
            return False, False

    # Stari SHA-256 format
    if stored_salt and stored_salt != "bcrypt":
        legacy = hashlib.sha256(
            (password + stored_salt).encode()).hexdigest()
        if legacy == stored_hash:
            return True, BCRYPT_AVAILABLE  # Treba upgrade ako bcrypt postoji
        return False, False

    return False, False


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Autentifikacija sa automatskom migracijom na bcrypt."""
    try:
        with get_db() as conn:
            u = conn.execute(
                "SELECT * FROM users WHERE email=?",
                (email.lower().strip(),)
            ).fetchone()
            if not u:
                return None

            is_valid, needs_upgrade = verify_password(
                password, u["password_hash"], u["salt"])

            if not is_valid:
                return None

            # Auto-upgrade na bcrypt
            if needs_upgrade and BCRYPT_AVAILABLE:
                new_hash, new_salt = create_password_hash(password)
                conn.execute(
                    "UPDATE users SET password_hash=?, salt=? WHERE id=?",
                    (new_hash, new_salt, u["id"]))

            return dict(u)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  BAZA PODATAKA
# ═══════════════════════════════════════════════════════════════

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "prava_kolevka.db")

@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn; conn.commit()
    except sqlite3.Error as e:
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()

def init_database():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                salt TEXT NOT NULL, full_name TEXT NOT NULL,
                role TEXT DEFAULT 'user', firm_name TEXT DEFAULT '',
                phone TEXT DEFAULT '', plan TEXT DEFAULT 'solo',
                is_active INTEGER DEFAULT 1,
                subscription_start TEXT, subscription_end TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT, auto_suspended INTEGER DEFAULT 0,
                suspended_reason TEXT DEFAULT '', notes TEXT DEFAULT ''
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, amount REAL NOT NULL,
                payment_date TEXT NOT NULL, period_start TEXT,
                period_end TEXT, status TEXT DEFAULT 'completed',
                method TEXT DEFAULT 'manual', notes TEXT DEFAULT '',
                recorded_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, action TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS laws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_sr TEXT NOT NULL, name_al TEXT DEFAULT '',
                short_name TEXT DEFAULT '', law_number TEXT DEFAULT '',
                area TEXT DEFAULT 'Ostalo', gazette_info TEXT DEFAULT '',
                effective_date TEXT DEFAULT '', is_active INTEGER DEFAULT 1,
                language TEXT DEFAULT 'sr', full_text TEXT DEFAULT '',
                hierarchy_level INTEGER DEFAULT 3,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS law_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_id INTEGER NOT NULL, article_number TEXT NOT NULL,
                paragraph_number TEXT DEFAULT '', title TEXT DEFAULT '',
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (law_id) REFERENCES laws(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, source_filename TEXT,
                source_language TEXT, source_text TEXT,
                translated_text TEXT, legal_analysis TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS generated_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, doc_type TEXT,
                content TEXT, created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL, title TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS case_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL, shared_with_email TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (case_id) REFERENCES cases(id)
            )""")
            # Migracija: dodaj hierarchy_level ako ne postoji
            try:
                c.execute("SELECT hierarchy_level FROM laws LIMIT 1")
            except Exception:
                c.execute(
                    "ALTER TABLE laws ADD COLUMN hierarchy_level"
                    " INTEGER DEFAULT 3")
            # Admin korisnik — NOVO v5.3: bcrypt
            admin = c.execute(
                "SELECT id FROM users WHERE email=?",
                (ADMIN_EMAIL,)).fetchone()
            if not admin:
                ph, salt = create_password_hash(ADMIN_DEFAULT_PASSWORD)
                c.execute("""INSERT INTO users
                    (email,password_hash,salt,full_name,role,plan,
                     is_active,subscription_start,subscription_end)
                    VALUES (?,?,?,?,'admin','enterprise',1,?,?)""",
                    (ADMIN_EMAIL, ph, salt, "Administrator",
                     date.today().isoformat(),
                     (date.today()+timedelta(days=36500)).isoformat()))
    except Exception as e:
        st.error(f"DB init: {e}")


# ═══════════════════════════════════════════════════════════════
#  PARSIRANJE ZAKONA
# ═══════════════════════════════════════════════════════════════

def clean_pdf_text(text: str) -> str:
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^ +| +$', '', text, flags=re.MULTILINE)
    return text.strip()


def parse_law_into_articles(full_text: str) -> Tuple[List[Dict], List[str]]:
    warnings = []
    text = clean_pdf_text(full_text)
    articles = []

    patterns = [
        re.compile(
            r'(?:^|\n)\s*(?:Član|ČLAN|Članak|ČLANAK)\s+(\d+[a-zA-Z]?)'
            r'\s*\.?\s*\n(.*?)'
            r'(?=\n\s*(?:Član|ČLAN|Članak|ČLANAK)\s+\d|\Z)',
            re.DOTALL | re.IGNORECASE),
        re.compile(
            r'(?:^|\n)\s*(?:Neni|NENI)\s+(\d+[a-zA-Z]?)'
            r'\s*\.?\s*\n(.*?)'
            r'(?=\n\s*(?:Neni|NENI)\s+\d|\Z)',
            re.DOTALL | re.IGNORECASE),
        re.compile(
            r'(?:^|\n)\s*(?:Član|ČLAN)\s+(\d+[a-zA-Z]?)'
            r'\s*[.\s]*[-–—]\s*(.*?)'
            r'(?=\n\s*(?:Član|ČLAN)\s+\d|\Z)',
            re.DOTALL | re.IGNORECASE),
        re.compile(
            r'(?:^|\n)\s*(?:Član|ČLAN|Neni|NENI)\s*[:\s]*(\d+[a-zA-Z]?)'
            r'\s*[.:\-–—]?\s*(.*?)'
            r'(?=\n\s*(?:Član|ČLAN|Neni|NENI)\s*[:\s]*\d|\Z)',
            re.DOTALL | re.IGNORECASE),
    ]

    best_matches = []
    for pattern in patterns:
        matches = list(pattern.finditer(text))
        if len(matches) > len(best_matches):
            best_matches = matches

    if not best_matches:
        warnings.append(
            "Nije pronađena struktura članova."
            " Ceo tekst tretiran kao jedan blok.")
        articles.append({
            "article_number": "0", "paragraph_number": "",
            "title": "(Neparsirani tekst)",
            "content": text[:10000]
        })
        return articles, warnings

    if len(best_matches) < 3:
        warnings.append(
            f"Pronađeno samo {len(best_matches)} članova."
            " Moguće da format nije prepoznat u celosti.")

    for match in best_matches:
        article_num = match.group(1).strip()
        article_body = match.group(2).strip()
        if not article_body:
            continue

        lines = article_body.split('\n')
        title = ""
        content_start = 0
        if lines:
            first_line = lines[0].strip()
            if (len(first_line) < 120
                    and not re.match(r'^\d+[\.\)]', first_line)
                    and len(lines) > 1):
                title = first_line
                content_start = 1

        content = '\n'.join(lines[content_start:]).strip()
        if not content and title:
            content = title
            title = ""

        para_pattern = re.compile(r'(?:^|\n)\s*(\d+)\s*[\.\)]\s+')
        para_splits = list(para_pattern.finditer(content))

        if len(para_splits) >= 2:
            pre_text = content[:para_splits[0].start()].strip()
            if pre_text:
                articles.append({
                    "article_number": article_num,
                    "paragraph_number": "",
                    "title": title, "content": pre_text
                })
            for i, pm in enumerate(para_splits):
                para_num = pm.group(1)
                start = pm.end()
                end = (para_splits[i+1].start()
                       if i+1 < len(para_splits) else len(content))
                para_text = content[start:end].strip()
                if para_text:
                    articles.append({
                        "article_number": article_num,
                        "paragraph_number": para_num,
                        "title": title, "content": para_text
                    })
        else:
            articles.append({
                "article_number": article_num,
                "paragraph_number": "",
                "title": title, "content": content
            })

    empty_count = sum(1 for a in articles if len(a["content"]) < 10)
    if empty_count > len(articles) * 0.3:
        warnings.append(
            f"{empty_count} od {len(articles)} članova"
            " ima vrlo kratak sadržaj.")

    return articles, warnings


def save_law_to_db(name_sr, name_al, short_name, law_number, area,
                   gazette_info, effective_date, language, full_text,
                   hierarchy_level=3):
    try:
        articles, warnings = parse_law_into_articles(full_text)
        with get_db() as conn:
            conn.execute("""
                INSERT INTO laws (name_sr, name_al, short_name, law_number,
                area, gazette_info, effective_date, language, full_text,
                hierarchy_level)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (name_sr, name_al, short_name, law_number, area,
                  gazette_info, effective_date, language, full_text,
                  hierarchy_level))
            law_id = conn.execute(
                "SELECT last_insert_rowid()").fetchone()[0]
            for art in articles:
                conn.execute("""
                    INSERT INTO law_articles (law_id, article_number,
                    paragraph_number, title, content)
                    VALUES (?,?,?,?,?)
                """, (law_id, art["article_number"],
                      art.get("paragraph_number", ""),
                      art.get("title", ""), art["content"]))
            st.session_state.law_vs = None
            st.session_state.law_vs_version = ""
            return law_id, len(articles), warnings
    except Exception as e:
        return None, 0, [f"Greška: {e}"]


# ═══════════════════════════════════════════════════════════════
#  VEKTORSKA PRETRAGA ZAKONA
# ═══════════════════════════════════════════════════════════════

def get_law_vs_version():
    try:
        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM law_articles").fetchone()[0]
            last = conn.execute(
                "SELECT MAX(created_at) FROM law_articles"
            ).fetchone()[0] or ""
            return f"{count}_{last}"
    except:
        return "0_"


def build_law_vector_store():
    if not OPENAI_API_KEY:
        return None
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT la.id, la.article_number, la.paragraph_number,
                       la.title, la.content,
                       l.name_sr, l.short_name, l.law_number, l.area,
                       l.hierarchy_level
                FROM law_articles la JOIN laws l ON la.law_id = l.id
                WHERE l.is_active = 1
            """).fetchall()
        if not rows:
            return None
        documents = []
        for row in rows:
            row = dict(row)
            source = row.get('short_name') or row['name_sr']
            art_ref = f"Član {row['article_number']}"
            if row.get('paragraph_number'):
                art_ref += f", stav {row['paragraph_number']}"
            h_level = row.get('hierarchy_level', 3)
            h_info = HIERARCHY_LEVELS.get(h_level, HIERARCHY_LEVELS[3])
            embed_text = f"{h_info['name']}: {source} {art_ref}"
            if row.get('title'):
                embed_text += f" {row['title']}"
            embed_text += f"\n{row['content']}"
            doc = Document(
                page_content=embed_text,
                metadata={
                    "article_number": row['article_number'],
                    "paragraph_number": row.get('paragraph_number', ''),
                    "title": row.get('title', ''),
                    "content": row['content'],
                    "name_sr": row['name_sr'],
                    "short_name": row.get('short_name', ''),
                    "law_number": row.get('law_number', ''),
                    "area": row.get('area', ''),
                    "hierarchy_level": h_level,
                })
            documents.append(doc)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200)
        final_docs = []
        for doc in documents:
            if len(doc.page_content) > 1200:
                chunks = splitter.split_documents([doc])
                final_docs.extend(chunks)
            else:
                final_docs.append(doc)
        if not final_docs:
            return None
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", api_key=OPENAI_API_KEY)
        return FAISS.from_documents(final_docs, embeddings)
    except Exception:
        return None


def get_law_vector_store():
    current_version = get_law_vs_version()
    if (st.session_state.get("law_vs") is not None
            and st.session_state.get("law_vs_version") == current_version
            and current_version != "0_"):
        return st.session_state.law_vs
    vs = build_law_vector_store()
    st.session_state.law_vs = vs
    st.session_state.law_vs_version = current_version
    return vs


# ═══════════════════════════════════════════════════════════════
#  PRETRAGA ZAKONA (SQL + SEMANTIČKA + HIJERARHIJA)
# ═══════════════════════════════════════════════════════════════

def detect_legal_area(query: str) -> List[str]:
    q = query.lower()
    detected = []
    for area, keywords in AREA_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q)
        if score >= 1:
            detected.append((area, score))
    detected.sort(key=lambda x: x[1], reverse=True)
    return [a for a, s in detected[:3]]


def detect_target_law(query: str) -> List[str]:
    q = query.lower()
    targets = []
    for shortname, full_names in SHORTNAME_MAP.items():
        if shortname in q:
            targets.extend(full_names)
    return list(set(targets))


def detect_jurisdiction_issue(query: str) -> Optional[str]:
    q = query.lower()
    for marker in SERBIA_MARKERS:
        if marker in q:
            return marker
    return None


def search_laws(query: str, max_results: int = 15) -> List[Dict]:
    q_lower = query.lower()
    stop_words = {
        'je','su','da','li','se','na','u','i','za','od','sa','po',
        'ne','ni','što','šta','kako','koji','koja','koje','ko',
        'ako','ali','ili','kad','kada','gde','iz','do','bi','mi',
        'ti','on','ona','oni','vi','taj','ta','to','ovo','može',
        'mora','treba','prema','biti','bude','sam','jedan','neki',
        'sve','svi','svoj','ima','nema','radi','kaže','član','stav',
        'zakon','pravo','pravni','zakonski','molim','pitanje',
    }
    words = re.findall(r'[a-zA-ZčćžšđČĆŽŠĐ]+', q_lower)
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]

    article_match = re.search(
        r'(?:član|članu|člana|članka|neni)\s*[:\s]*(\d+[a-zA-Z]?)',
        q_lower)
    target_article = article_match.group(1) if article_match else None
    target_laws = detect_target_law(query)
    target_areas = detect_legal_area(query)

    results = []
    seen_keys = set()

    def add_result(row_dict, base_score):
        key = (f"{row_dict['name_sr']}"
               f"|{row_dict['article_number']}"
               f"|{row_dict.get('paragraph_number','')}")
        if key in seen_keys:
            return
        seen_keys.add(key)
        h_level = row_dict.get('hierarchy_level', 3)
        h_bonus = HIERARCHY_LEVELS.get(
            h_level, HIERARCHY_LEVELS[3])['weight']
        row_dict['score'] = base_score + h_bonus
        row_dict['hierarchy_level'] = h_level
        results.append(row_dict)

    try:
        with get_db() as conn:
            bq = """
                SELECT la.article_number, la.paragraph_number,
                       la.title, la.content,
                       l.name_sr, l.short_name, l.law_number, l.area,
                       l.hierarchy_level
                FROM law_articles la JOIN laws l ON la.law_id = l.id
                WHERE l.is_active=1
            """
            if target_article and target_laws:
                for ln in target_laws:
                    rows = conn.execute(
                        bq + " AND la.article_number=?"
                        " AND (l.name_sr LIKE ? OR l.short_name LIKE ?)",
                        (target_article, f"%{ln}%", f"%{ln}%")).fetchall()
                    for row in rows:
                        add_result(dict(row), 200)

            if target_article:
                rows = conn.execute(
                    bq + " AND la.article_number=?",
                    (target_article,)).fetchall()
                for row in rows:
                    r = dict(row)
                    ab = 50 if r.get('area') in target_areas else 0
                    add_result(r, 150 + ab)

            if target_laws and keywords:
                for ln in target_laws:
                    for kw in keywords[:6]:
                        rows = conn.execute(
                            bq + " AND (l.name_sr LIKE ? OR l.short_name"
                            " LIKE ?) AND (la.content LIKE ? OR"
                            " la.title LIKE ?) LIMIT 5",
                            (f"%{ln}%", f"%{ln}%",
                             f"%{kw}%", f"%{kw}%")).fetchall()
                        for row in rows:
                            r = dict(row)
                            cl = r['content'].lower()
                            kc = sum(1 for k in keywords if k in cl)
                            add_result(r, 100 + kc * 10)

            if keywords and target_areas:
                for kw in keywords[:5]:
                    for area in target_areas[:2]:
                        rows = conn.execute(
                            bq + " AND l.area=? AND (la.content LIKE ?"
                            " OR la.title LIKE ?) LIMIT 5",
                            (area, f"%{kw}%", f"%{kw}%")).fetchall()
                        for row in rows:
                            r = dict(row)
                            cl = r['content'].lower()
                            kc = sum(1 for k in keywords if k in cl)
                            add_result(r, 60 + kc * 10)

            if keywords:
                for kw in keywords[:5]:
                    rows = conn.execute(
                        bq + " AND (la.content LIKE ? OR la.title LIKE ?)"
                        " LIMIT 8",
                        (f"%{kw}%", f"%{kw}%")).fetchall()
                    for row in rows:
                        r = dict(row)
                        cl = r['content'].lower()
                        kc = sum(1 for k in keywords if k in cl)
                        ab = 15 if r.get('area') in target_areas else 0
                        add_result(r, 20 + kc * 10 + ab)
    except Exception as e:
        st.error(f"Greška pretrage: {e}")

    law_vs = get_law_vector_store()
    if law_vs:
        try:
            sem_docs = law_vs.similarity_search_with_score(query, k=10)
            for doc, distance in sem_docs:
                meta = doc.metadata
                if distance < 1.5:
                    sem_score = max(5, int(90 * (1 - distance / 1.5)))
                    r = {
                        'article_number': meta.get('article_number', ''),
                        'paragraph_number': meta.get(
                            'paragraph_number', ''),
                        'title': meta.get('title', ''),
                        'content': meta.get(
                            'content', doc.page_content),
                        'name_sr': meta.get('name_sr', ''),
                        'short_name': meta.get('short_name', ''),
                        'law_number': meta.get('law_number', ''),
                        'area': meta.get('area', ''),
                        'hierarchy_level': meta.get(
                            'hierarchy_level', 3),
                    }
                    if target_areas and r.get('area') in target_areas:
                        sem_score += 15
                    if target_laws:
                        for tl in target_laws:
                            if tl.lower() in r.get(
                                    'name_sr', '').lower():
                                sem_score += 20
                                break
                    add_result(r, sem_score)
        except Exception:
            pass

    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    return results[:max_results]


 # ═══════════════════════════════════════════════════════════════
#  LOGIN / LOGOUT — NOVO v5.3: session timeout + čišćenje
# ═══════════════════════════════════════════════════════════════

def render_login():
    st.markdown(
        f'<div class="login-box"><div class="login-logo">'
        f'<div class="icon">⚖️</div>'
        f'<h1>Prava Kolevka</h1>'
        f'<p>Pravni AI za Kosovo</p></div></div>',
        unsafe_allow_html=True)

    # NOVO v5.3: Upozorenje ako bcrypt nije instaliran
    if not BCRYPT_AVAILABLE:
        st.warning(
            "⚠️ bcrypt nije instaliran — lozinke koriste slabiju"
            " zaštitu. Dodajte 'bcrypt' u requirements.txt.")

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login", clear_on_submit=False):
            email = st.text_input("📧 Email")
            pw = st.text_input("🔒 Lozinka", type="password")
            if st.form_submit_button("Prijavi se",
                                     use_container_width=True):
                if not email or not pw:
                    st.error("Unesite podatke.")
                else:
                    u = authenticate_user(email, pw)
                    if u:
                        st.session_state.current_user = u
                        st.session_state.logged_in = True
                        # NOVO v5.3: Zabeleži vreme logina
                        st.session_state.login_time = datetime.now()
                        try:
                            with get_db() as conn:
                                conn.execute(
                                    "UPDATE users SET last_login=?"
                                    " WHERE id=?",
                                    (datetime.now().isoformat(),
                                     u["id"]))
                        except Exception:
                            pass
                        log_action(u["id"], "login")
                        st.rerun()
                    else:
                        st.error("❌ Pogrešni podaci.")


# NOVO v5.3: Poboljšano čišćenje na logout
def do_logout():
    uid = None
    cu = st.session_state.get("current_user")
    if cu and isinstance(cu, dict):
        uid = cu.get("id")
    if uid:
        log_action(uid, "logout")

    # Obriši SVE osetljive podatke iz sesije
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    init_ss()


def check_session_timeout() -> bool:
    """Proverava da li je sesija istekla. Vraća True ako jeste."""
    login_time = st.session_state.get("login_time")
    if not login_time:
        return False
    elapsed = (datetime.now() - login_time).total_seconds() / 60
    if elapsed > SESSION_TIMEOUT_MINUTES:
        return True
    return False


# ═══════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ═══════════════════════════════════════════════════════════════

def render_admin():
    st.markdown(
        f'<div class="top-bar"><div style="display:flex;'
        f'align-items:center;gap:12px">'
        f'<span style="font-size:1.5rem">⚖️</span>'
        f'<h2>Prava <span class="gold">Kolevka</span> — Admin</h2>'
        f'</div><div style="display:flex;gap:8px;align-items:center">'
        f'<span class="badge badge-gold">ADMIN</span>'
        f'</div></div>', unsafe_allow_html=True)
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
                " WHERE role='user' AND is_active=1").fetchone()["c"]
            ms = date.today().replace(day=1).isoformat()
            revenue = conn.execute(
                "SELECT COALESCE(SUM(amount),0) s FROM payments"
                " WHERE status='completed' AND payment_date>=?",
                (ms,)).fetchone()["s"]
            num_laws = conn.execute(
                "SELECT COUNT(*) c FROM laws"
                " WHERE is_active=1").fetchone()["c"]
            num_articles = conn.execute(
                "SELECT COUNT(*) c FROM law_articles").fetchone()["c"]
            all_users = conn.execute(
                "SELECT full_name,email,plan,is_active,"
                "subscription_end FROM users WHERE role='user'"
                " ORDER BY subscription_end ASC").fetchall()
    except Exception as e:
        st.error(f"{e}")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-box"><div class="num">{active}'
            f'</div><div class="lbl">Aktivnih</div></div>',
            unsafe_allow_html=True)
    with c2:
        st.markdown(
            f'<div class="metric-box"><div class="num"'
            f' style="color:{SUCCESS}">€{revenue:.0f}</div>'
            f'<div class="lbl">Ovaj mesec</div></div>',
            unsafe_allow_html=True)
    with c3:
        st.markdown(
            f'<div class="metric-box"><div class="num">{num_laws}'
            f'</div><div class="lbl">Zakona</div></div>',
            unsafe_allow_html=True)
    with c4:
        st.markdown(
            f'<div class="metric-box"><div class="num">'
            f'{num_articles}</div>'
            f'<div class="lbl">Članova</div></div>',
            unsafe_allow_html=True)

    st.markdown("### 📜 Zakoni po pravnoj snazi")
    try:
        with get_db() as conn:
            h_stats = conn.execute(
                "SELECT hierarchy_level, COUNT(*) as cnt"
                " FROM laws WHERE is_active=1"
                " GROUP BY hierarchy_level"
                " ORDER BY hierarchy_level").fetchall()
        for hs in h_stats:
            hl = hs['hierarchy_level'] if hs['hierarchy_level'] else 3
            h_info = HIERARCHY_LEVELS.get(hl, HIERARCHY_LEVELS[3])
            st.markdown(
                f"{h_info['icon']} **{h_info['name']}:**"
                f" {hs['cnt']} propisa")
    except Exception:
        pass

    st.markdown("### 📋 Korisnici")
    for u in all_users:
        u = dict(u)
        plan = PLANS.get(u["plan"], {"name": "?", "icon": "?"})
        dl = 0
        if u.get("subscription_end"):
            try:
                dl = (date.fromisoformat(
                    u["subscription_end"]) - date.today()).days
            except Exception:
                pass
        if dl > 7:
            tag = f"🟢 {dl}d"
        elif dl > 0:
            tag = f"🟡 {dl}d"
        else:
            tag = f"🔴 {dl}d"
        st.markdown(
            f"{plan['icon']} **{u['full_name']}**"
            f" ({u['email']}) — {plan['name']} — {tag}")


def admin_laws():
    st.markdown("### 📜 Upravljanje zakonima")
    st.markdown(
        '<div class="pk-card-gold"><h3>Kako da dodaš zakon</h3>'
        '<p style="color:#6B7280;margin:0">'
        '1. Pronađi tekst zakona<br>'
        '2. Kopiraj CEO tekst<br>'
        '3. Izaberi <b>pravnu snagu</b><br>'
        '4. Sistem razbija na članove automatski'
        '</p></div>', unsafe_allow_html=True)

    with st.expander("➕ Dodaj novi zakon", expanded=False):
        with st.form("add_law"):
            c1, c2 = st.columns(2)
            with c1:
                name_sr = st.text_input(
                    "Naziv (srpski) *",
                    placeholder="Krivični zakonik Kosova")
                name_al = st.text_input(
                    "Naziv (albanski)",
                    placeholder="Kodi Penal i Kosovës")
                short_name = st.text_input(
                    "Skraćenica", placeholder="KZ, ZKP, ZOO")
                hierarchy_level = st.selectbox(
                    "👑 Pravna snaga *",
                    options=list(HIERARCHY_LEVELS.keys()),
                    index=2,
                    format_func=lambda x: (
                        f"{HIERARCHY_LEVELS[x]['icon']}"
                        f" {HIERARCHY_LEVELS[x]['name']}"
                        f" — {HIERARCHY_LEVELS[x]['desc']}"))
            with c2:
                law_number = st.text_input(
                    "Broj zakona",
                    placeholder="Nr. 06/L-074")
                area = st.selectbox("Oblast prava", LEGAL_AREAS)
                gazette_info = st.text_input(
                    "Službeni glasnik",
                    placeholder="Sl. glasnik KS br. 2/2019")
                effective_date = st.text_input("Stupanje na snagu")
            full_text = st.text_area(
                "Tekst zakona (CEO tekst) *", height=400,
                placeholder="Član 1\nOpšte odredbe\n"
                            "1. Ovim zakonom...\n\nČlan 2\n...")

            if st.form_submit_button("✅ Sačuvaj zakon",
                                     use_container_width=True):
                if not name_sr or not full_text:
                    st.error("Unesite naziv i tekst.")
                else:
                    law_id, num_articles, warnings = save_law_to_db(
                        name_sr, name_al, short_name, law_number,
                        area, gazette_info, effective_date, "sr",
                        full_text, hierarchy_level)
                    if law_id:
                        h_info = HIERARCHY_LEVELS.get(
                            hierarchy_level, HIERARCHY_LEVELS[3])
                        st.success(
                            f"✅ '{name_sr}' — {num_articles} čl."
                            f" — {h_info['icon']} {h_info['name']}")
                        for w in warnings:
                            st.warning(f"⚠️ {w}")
                        st.rerun()

    st.markdown("### 📋 Zakoni u bazi")
    try:
        with get_db() as conn:
            laws = conn.execute(
                "SELECT l.*, COUNT(la.id) as num_articles"
                " FROM laws l LEFT JOIN law_articles la"
                " ON l.id=la.law_id"
                " GROUP BY l.id"
                " ORDER BY l.hierarchy_level, l.area,"
                " l.name_sr").fetchall()
    except Exception:
        laws = []

    if not laws:
        st.warning("⚠️ Nema zakona! Dodajte iznad.")
    else:
        current_level = None
        for law in laws:
            law = dict(law)
            h_level = law.get('hierarchy_level', 3)
            h_info = HIERARCHY_LEVELS.get(h_level, HIERARCHY_LEVELS[3])
            if h_level != current_level:
                current_level = h_level
                st.markdown(
                    f"#### {h_info['icon']} {h_info['name']}")

            with st.expander(
                    f"{h_info['icon']} {law['name_sr']}"
                    f" ({law.get('law_number','')}) —"
                    f" {law['num_articles']} čl."):
                st.markdown(
                    f"**Oblast:** {law.get('area','')}"
                    f" | **Skr:** {law.get('short_name','')}"
                    f" | **Snaga:** {h_info['name']}")
                try:
                    with get_db() as conn:
                        arts = conn.execute(
                            "SELECT article_number,title,content"
                            " FROM law_articles WHERE law_id=?"
                            " ORDER BY CAST(article_number"
                            " AS INTEGER) LIMIT 5",
                            (law["id"],)).fetchall()
                    for a in arts:
                        t = (f" — {a['title']}"
                             if a['title'] else "")
                        st.caption(
                            f"Čl. {a['article_number']}{t}:"
                            f" {a['content'][:150]}...")
                except Exception:
                    pass
                if st.button("🗑️ Obriši",
                             key=f"del_{law['id']}"):
                    with get_db() as conn:
                        conn.execute(
                            "DELETE FROM law_articles"
                            " WHERE law_id=?", (law["id"],))
                        conn.execute(
                            "DELETE FROM laws WHERE id=?",
                            (law["id"],))
                    st.session_state.law_vs = None
                    st.session_state.law_vs_version = ""
                    st.rerun()


# NOVO v5.3: admin_users koristi bcrypt
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
                        f"{PLANS[x]['icon']} {PLANS[x]['name']}"
                        f" (€{PLANS[x]['price']})"),
                    key="nu_pl")
                nd = st.number_input(
                    "Dana", 1, value=30, key="nu_d")
            npw = st.text_input(
                "Lozinka *", value="Kolevka2024!", key="nu_pw")
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
                                "INSERT INTO users(email,"
                                "password_hash,salt,full_name,"
                                "role,plan,is_active,"
                                "subscription_start,"
                                "subscription_end)"
                                "VALUES(?,?,?,?,'user',?,1,?,?)",
                                (ne.lower().strip(), ph, salt, nn,
                                 npl, date.today().isoformat(), se))
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
                " ORDER BY is_active DESC,full_name").fetchall()
    except Exception:
        return

    for u in users:
        u = dict(u)
        plan = PLANS.get(u["plan"], {"name": "?", "icon": "?"})
        with st.expander(
                f"{plan['icon']} {u['full_name']}"
                f" — {u['email']}"):
            st.markdown(
                f"**Plan:** {plan['name']}"
                f" | **Do:** {u.get('subscription_end','-')}"
                f" | {'🟢' if u['is_active'] else '🔴'}")
            c1, c2 = st.columns(2)
            with c1:
                ext = st.number_input(
                    "Dana", 1, value=30, key=f"e_{u['id']}")
                if st.button("📅 Produži",
                             key=f"ext_{u['id']}"):
                    curr = (date.fromisoformat(
                        u["subscription_end"])
                        if u.get("subscription_end")
                        else date.today())
                    ne = (max(curr, date.today()) + timedelta(
                        days=ext)).isoformat()
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE users SET subscription_end=?,"
                            "is_active=1,auto_suspended=0,"
                            "suspended_reason='' WHERE id=?",
                            (ne, u["id"]))
                    st.rerun()
            with c2:
                if u["is_active"]:
                    if st.button("🔴 Suspenduj",
                                 key=f"s_{u['id']}"):
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users SET is_active=0,"
                                "suspended_reason='Ručno'"
                                " WHERE id=?", (u["id"],))
                        st.rerun()
                else:
                    if st.button("🟢 Aktiviraj",
                                 key=f"a_{u['id']}"):
                        ne = (date.today() + timedelta(
                            days=30)).isoformat()
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users SET is_active=1,"
                                "subscription_end=? WHERE id=?",
                                (ne, u["id"]))
                        st.rerun()


def admin_payments():
    st.markdown("### 💰 Uplate")
    with st.expander("➕ Nova"):
        try:
            with get_db() as conn:
                users = conn.execute(
                    "SELECT id,full_name,email FROM users"
                    " WHERE role='user'"
                    " ORDER BY full_name").fetchall()
        except Exception:
            return
        if not users:
            return
        with st.form("pay"):
            opts = {u["id"]: f"{u['full_name']} ({u['email']})"
                    for u in users}
            uid = st.selectbox(
                "Korisnik", list(opts.keys()),
                format_func=lambda x: opts[x])
            c1, c2 = st.columns(2)
            with c1:
                amt = st.number_input(
                    "€", min_value=1.0, value=29.0)
                pd = st.date_input("Datum", value=date.today())
            with c2:
                days = st.number_input("Dana", 1, value=30)
                meth = st.selectbox(
                    "Način",
                    ["Transfer", "Gotovina", "PayPal", "Kripto"])
            if st.form_submit_button("✅"):
                pe = (pd + timedelta(days=days)).isoformat()
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO payments(user_id,amount,"
                        "payment_date,period_start,period_end,"
                        "method,recorded_by)"
                        "VALUES(?,?,?,?,?,?,?)",
                        (uid, amt, pd.isoformat(),
                         pd.isoformat(), pe, meth,
                         st.session_state.current_user["id"]))
                    conn.execute(
                        "UPDATE users SET subscription_end=?,"
                        "is_active=1 WHERE id=?", (pe, uid))
                st.success(f"€{amt} do {pe}")
                st.rerun()

    try:
        with get_db() as conn:
            pays = conn.execute(
                "SELECT p.*,u.full_name FROM payments p"
                " JOIN users u ON p.user_id=u.id"
                " ORDER BY p.payment_date DESC"
                " LIMIT 30").fetchall()
    except Exception:
        pays = []
    for p in pays:
        st.markdown(
            f"✅ **{p['payment_date']}** —"
            f" {p['full_name']} — **€{p['amount']:.0f}**")


# NOVO v5.3: admin_settings koristi bcrypt
def admin_settings():
    st.markdown(
        f"### ⚙️ Podešavanja\n"
        f"**Admin:** `{ADMIN_EMAIL}`"
        f" | **API:** {'✅' if OPENAI_API_KEY else '❌'}"
        f" | **bcrypt:** {'✅' if BCRYPT_AVAILABLE else '❌ SHA-256'}"
        f" | **Session timeout:** {SESSION_TIMEOUT_MINUTES} min")

    # Šta se čuva trajno
    with st.expander("🔐 Zaštita podataka — info"):
        st.markdown("""
        **Šta se čuva TRAJNO u bazi:**
        - Korisnici (email, ime, hash lozinke)
        - Zakoni i članovi zakona
        - Evidencija uplata
        - Log akcija (bez osetljivih detalja)

        **Šta se NE čuva trajno:**
        - Uploadovani dokumenti (samo u sesiji — brišu se na logout)
        - Chat istorija (samo u sesiji)
        - AI odgovori (samo u sesiji)

        **Lozinke:**
        """ + ("✅ Koristi se bcrypt (industrijki standard)"
               if BCRYPT_AVAILABLE
               else "⚠️ Koristi se SHA-256 — instalirajte bcrypt"))

    with st.expander("🔒 Promena lozinke"):
        with st.form("chpw"):
            old = st.text_input("Trenutna", type="password")
            new = st.text_input("Nova", type="password")
            conf = st.text_input("Potvrdi", type="password")
            if st.form_submit_button("Promeni"):
                if new != conf:
                    st.error("Ne poklapaju se.")
                elif len(new) < 8:
                    st.error("Minimum 8 karaktera.")
                else:
                    u = st.session_state.current_user
                    is_valid, _ = verify_password(
                        old, u["password_hash"], u["salt"])
                    if is_valid:
                        nh, ns = create_password_hash(new)
                        with get_db() as conn:
                            conn.execute(
                                "UPDATE users SET"
                                " password_hash=?, salt=?"
                                " WHERE id=?",
                                (nh, ns, u["id"]))
                        st.success("✅ Lozinka promenjena.")
                    else:
                        st.error("Pogrešna trenutna lozinka.")


# ═══════════════════════════════════════════════════════════════
#  KORISNIČKI PANEL
# ═══════════════════════════════════════════════════════════════

def render_user():
    user = st.session_state.current_user
    sub = check_subscription(user)
    if not sub["active"]:
        st.markdown(
            f'<div style="text-align:center;padding:4rem">'
            f'<h2>🔒 Pretplata istekla</h2>'
            f'<p>{sub["message"]}</p>'
            f'<p>Kontakt: <b>{ADMIN_EMAIL}</b></p></div>',
            unsafe_allow_html=True)
        if st.button("🚪 Odjavi se", key="exp_out"):
            do_logout()
            st.rerun()
        return

    plan = PLANS.get(
        user["plan"], {"name": "?", "icon": "?", "can_share": False})
    bc = "badge-gold"
    bt = f"{sub['days_left']}d"
    if sub["status"] == "expiring":
        bc = "badge-warn"
        bt = f"⚠{sub['days_left']}d"
    elif sub["status"] == "grace":
        bc = "badge-err"
        bt = "ISTEKLO"

    st.markdown(
        f'<div class="top-bar"><div style="display:flex;'
        f'align-items:center;gap:12px">'
        f'<span style="font-size:1.5rem">⚖️</span>'
        f'<h2>Prava <span class="gold">Kolevka</span></h2>'
        f'</div><div style="display:flex;gap:8px;'
        f'align-items:center;flex-wrap:wrap">'
        f'<span class="badge">{plan["icon"]}'
        f' {plan["name"]}</span>'
        f'<span class="badge {bc}">{bt}</span>'
        f'<span class="badge">{user["full_name"]}</span>'
        f'</div></div>', unsafe_allow_html=True)

    if sub["message"]:
        st.warning(f"⚠️ {sub['message']}")
    if not OPENAI_API_KEY:
        st.error("AI nije podešen.")
        return

    try:
        with get_db() as conn:
            num_laws = conn.execute(
                "SELECT COUNT(*) c FROM laws"
                " WHERE is_active=1").fetchone()["c"]
    except Exception:
        num_laws = 0
    if num_laws == 0:
        st.warning("⚠️ Nema zakona u bazi. AI ne može da odgovara.")

    tabs = st.tabs(
        ["⚖️ Pravni AI", "🔄 Prevod",
         "📝 Podnesci", "🔍 Pretraga", "🌉 Most"])
    with tabs[0]:
        tab_legal_ai()
    with tabs[1]:
        tab_translate()
    with tabs[2]:
        tab_documents()
    with tabs[3]:
        tab_search_laws()
    with tabs[4]:
        tab_bridge()
    st.markdown("---")
    if st.button("🚪 Odjavi se", key="usr_out"):
        do_logout()
        st.rerun()


def tab_legal_ai():
    user = st.session_state.current_user
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>⚖️ Pravni AI — Odgovori iz zakona Kosova</h3>'
        '<p style="color:#6B7280;margin:0">'
        'AI odgovara <b>ISKLJUČIVO</b> iz zakona u sistemu.'
        ' Svaki odgovor ima pouzdanost, proveru citata'
        ' i pravnu snagu izvora.</p></div>',
        unsafe_allow_html=True)

    with st.expander("📁 Učitaj dokument (opciono)"):
        uploaded = st.file_uploader(
            "PDF/TXT", type=["pdf", "txt"],
            accept_multiple_files=True, key="a_upload")
        if uploaded:
            existing = {d["name"] for d in st.session_state.docs}
            new = [f for f in uploaded if f.name not in existing]
            if new:
                with st.spinner("⏳"):
                    for f in new:
                        text, name, lang = process_file(f)
                        if text:
                            st.session_state.docs.append({
                                "name": name, "lang": lang,
                                "lang_name": LANG_NAMES.get(
                                    lang, "?"),
                                "text": text, "size": len(text)})
                    try:
                        st.session_state.vs = build_vs(
                            st.session_state.docs, OPENAI_API_KEY)
                        st.success(f"✅ {len(new)} fajl(ova)")
                    except Exception as e:
                        st.error(f"{e}")

    for msg in st.session_state.chat:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="⚖️"):
                st.markdown(msg["content"])
                if msg.get("sources_html"):
                    st.markdown(
                        msg["sources_html"], unsafe_allow_html=True)

    if not st.session_state.chat:
        st.markdown("#### 💡 Primeri pitanja:")
        sugs = [
            "Koja je kazna za krađu po KZ Kosova?",
            "Koji su rokovi za žalbu u krivičnom postupku?",
            "Koji su uslovi za razvod braka?",
            "Koja prava garantuje Ustav Kosova?",
        ]
        cols = st.columns(2)
        for i, s in enumerate(sugs):
            with cols[i % 2]:
                if st.button(s, key=f"s_{i}",
                             use_container_width=True):
                    _ask_strict(s, user)
                    st.rerun()

    if prompt := st.chat_input("Postavite pravno pitanje..."):
        _ask_strict(prompt, user)
        st.rerun()


def _ask_strict(q, user):
    st.session_state.chat.append({"role": "user", "content": q})
    answer, confidence, results = query_ai_strict(
        q, st.session_state.get("vs"))
    sources_html = (render_sources_html(results)
                    if results else "")
    st.session_state.chat.append({
        "role": "assistant", "content": answer,
        "sources_html": sources_html,
        "confidence": confidence,
    })
    log_action(user["id"], "query",
               f"[{confidence}] len={len(q)}")


def tab_search_laws():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>🔍 Pretraga zakona</h3></div>',
        unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1:
        query = st.text_input(
            "🔍 Pretraži",
            placeholder="krađa, razvod, član 325...")
    with c2:
        try:
            with get_db() as conn:
                law_list = conn.execute(
                    "SELECT id,name_sr,short_name FROM laws"
                    " WHERE is_active=1"
                    " ORDER BY name_sr").fetchall()
        except Exception:
            law_list = []
        law_options = (["Svi zakoni"]
                       + [l['short_name'] or l['name_sr']
                          for l in law_list])
        selected = st.selectbox("Zakon", law_options)

    if query:
        results = search_laws(query)
        if selected != "Svi zakoni":
            results = [r for r in results
                       if (r.get('short_name')
                           or r['name_sr']) == selected]
        if results:
            st.success(f"Pronađeno {len(results)} rezultata")
            for r in results:
                source = r.get('short_name') or r['name_sr']
                art = f"Član {r['article_number']}"
                if r.get('paragraph_number'):
                    art += f", st. {r['paragraph_number']}"
                title = (f" — {r['title']}"
                         if r.get('title') else "")
                score = r.get('score', 0)
                h_level = r.get('hierarchy_level', 3)
                h_info = HIERARCHY_LEVELS.get(
                    h_level, HIERARCHY_LEVELS[3])
                with st.expander(
                        f"{h_info['icon']} {source}: {art}"
                        f"{title} (rel: {score})"):
                    st.markdown(
                        f"**Pravna snaga:** {h_info['name']}")
                    st.markdown(r['content'])
        else:
            st.info("Nema rezultata.")
    else:
        try:
            with get_db() as conn:
                stats = conn.execute(
                    "SELECT l.name_sr,l.short_name,l.area,"
                    "l.hierarchy_level,"
                    "COUNT(la.id) as num FROM laws l"
                    " LEFT JOIN law_articles la"
                    " ON l.id=la.law_id"
                    " WHERE l.is_active=1 GROUP BY l.id"
                    " ORDER BY l.hierarchy_level,"
                    "l.area").fetchall()
            for s in stats:
                hl = s['hierarchy_level'] if s[
                    'hierarchy_level'] else 3
                h_info = HIERARCHY_LEVELS.get(
                    hl, HIERARCHY_LEVELS[3])
                st.markdown(
                    f"{h_info['icon']} **{s['name_sr']}**"
                    f" ({s.get('short_name','')})"
                    f" — {s['area']} — {s['num']} čl.")
        except Exception:
            pass


def tab_translate():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>🔄 Prevod dokumenta</h3></div>',
        unsafe_allow_html=True)
    f = st.file_uploader("PDF/TXT", type=["pdf", "txt"],
                         key="tr_upload")
    if f:
        text, filename, lang = process_file(f)
        if text and lang != "sr":
            st.info(
                f"📄 {filename} | {LANG_NAMES.get(lang, '?')}")
            if st.button("🔄 Prevedi", type="primary",
                         use_container_width=True):
                with st.spinner("⏳"):
                    translated = translate_full(text, lang)
                st.markdown(translated)
                word = create_word("Prevod", translated,
                                   filename, lang)
                st.download_button(
                    "📥 Word", data=word,
                    file_name=f"Prevod_{date.today()}.docx",
                    mime="application/vnd.openxmlformats-"
                         "officedocument.wordprocessingml"
                         ".document",
                    use_container_width=True)
        elif text:
            st.info("Već na srpskom.")


def tab_documents():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>📝 Podnesci</h3></div>',
        unsafe_allow_html=True)
    doc_type = st.selectbox(
        "Tip", list(DOCUMENT_TEMPLATES.keys()),
        format_func=lambda x: (
            f"{DOCUMENT_TEMPLATES[x]['icon']}"
            f" {DOCUMENT_TEMPLATES[x]['name']}"))
    case_info = st.text_area("Opišite slučaj", height=200)
    if st.button("📝 Generiši", disabled=not case_info,
                 use_container_width=True, type="primary"):
        tmpl = DOCUMENT_TEMPLATES[doc_type]
        with st.spinner("⏳"):
            llm = get_llm(temp=0.15, tokens=6000)
            try:
                r = llm.invoke([HumanMessage(
                    content=tmpl["prompt"].format(
                        case_info=case_info, documents=""))])
                st.markdown(r.content)
                word = create_word(tmpl["name"], r.content)
                st.download_button(
                    "📥 Word", data=word,
                    file_name=(f"{tmpl['name']}_"
                               f"{date.today()}.docx"),
                    mime="application/vnd.openxmlformats-"
                         "officedocument.wordprocessingml"
                         ".document",
                    use_container_width=True)
            except Exception as e:
                st.error(f"{e}")


def tab_bridge():
    st.markdown(
        '<div class="pk-card-gold">'
        '<h3>🌉 Pravni most AL→SR</h3></div>',
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
#  MAIN — NOVO v5.3: session timeout
# ═══════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_database()
    run_auto_suspension()

    if not st.session_state.get("logged_in", False):
        render_login()
        return

    # NOVO v5.3: Provera session timeout-a
    if check_session_timeout():
        do_logout()
        st.warning(
            "⏰ Sesija je istekla iz bezbednosnih razloga."
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
