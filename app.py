"""
═══════════════════════════════════════════════════════════════
 PRAVA KOLEVKA v4.0 — Pravna AI Platforma za KiM
 + Kamera OCR  + Podnesci  + Sudska praksa  + Deljenje
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
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
import plotly.graph_objects as go
from docx import Document as DocxDocument
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ═══════════════════════════════════════════════════════════════
#  1. KONFIGURACIJA
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Prava Kolevka | Pravna AI Platforma",
    page_icon="⚖️", layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Prava Kolevka v4.0"}
)


def get_secret(key, default=""):
    try: return st.secrets[key]
    except: return os.environ.get(key, default)

OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
ADMIN_EMAIL = get_secret("ADMIN_EMAIL", "admin@pravakolevka.rs")
ADMIN_DEFAULT_PASSWORD = get_secret("ADMIN_PASSWORD", "PravaKolevka2024!")


# ═══════════════════════════════════════════════════════════════
#  2. KONSTANTE
# ═══════════════════════════════════════════════════════════════

NAVY = "#0A1628"; NAVY_MID = "#1B2A4A"
GOLD = "#C5962C"; GOLD_LIGHT = "#F0E6C8"; GOLD_PALE = "#FBF7ED"
SURFACE = "#F5F4F0"; CARD_BG = "#FFFFFF"; TEXT_MUTED = "#6B7280"
SUCCESS = "#059669"; ERROR = "#DC2626"; WARNING = "#D97706"

PLANS = {
    "solo":        {"name":"Solo Advokat","price":29, "max_users":1,  "icon":"🥉","can_share":False},
    "kancelarija": {"name":"Kancelarija", "price":79, "max_users":5,  "icon":"🥈","can_share":True},
    "firma":       {"name":"Firma",       "price":149,"max_users":15, "icon":"🥇","can_share":True},
    "enterprise":  {"name":"Enterprise",  "price":0,  "max_users":999,"icon":"💎","can_share":True},
}

GRACE_PERIOD_DAYS = 3
LANG_NAMES = {"sr":"Srpski","al":"Albanski","en":"Engleski"}


# ═══════════════════════════════════════════════════════════════
#  3. SESSION STATE
# ═══════════════════════════════════════════════════════════════

def init_ss():
    for k, v in {"logged_in":False,"current_user":None,"docs":[],"vs":None,
                 "events":[],"chat":[],"translations":{},"ocr_text":""}.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_ss()


# ═══════════════════════════════════════════════════════════════
#  4. BAZA PODATAKA (sa novim tabelama)
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
            c.execute("""CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, source_filename TEXT,
                source_language TEXT, source_text TEXT,
                translated_text TEXT, legal_analysis TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            # NOVO: Slučajevi za deljenje
            c.execute("""CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL, title TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS case_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL, filename TEXT,
                text_content TEXT, language TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (case_id) REFERENCES cases(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS case_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                shared_with_email TEXT NOT NULL,
                permission TEXT DEFAULT 'read',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (case_id) REFERENCES cases(id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS generated_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, doc_type TEXT,
                content TEXT, created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            # Admin
            admin = c.execute("SELECT id FROM users WHERE email=?",(ADMIN_EMAIL,)).fetchone()
            if not admin:
                salt = secrets.token_hex(16)
                ph = hashlib.sha256((ADMIN_DEFAULT_PASSWORD+salt).encode()).hexdigest()
                c.execute("INSERT INTO users (email,password_hash,salt,full_name,role,plan,is_active,subscription_start,subscription_end) VALUES (?,?,?,?,'admin','enterprise',1,?,?)",
                    (ADMIN_EMAIL,ph,salt,"Administrator",date.today().isoformat(),(date.today()+timedelta(days=36500)).isoformat()))
    except Exception as e:
        st.error(f"DB init: {e}")

def hash_password(pw, salt):
    return hashlib.sha256((pw+salt).encode()).hexdigest()

def authenticate_user(email, password):
    try:
        with get_db() as conn:
            u = conn.execute("SELECT * FROM users WHERE email=?",(email.lower().strip(),)).fetchone()
            if not u: return None
            if hash_password(password,u["salt"])!=u["password_hash"]: return None
            return dict(u)
    except: return None

def check_subscription(user):
    if user["role"]=="admin": return {"active":True,"status":"admin","days_left":99999,"message":""}
    if not user["is_active"]: return {"active":False,"status":"suspended","days_left":0,"message":user.get("suspended_reason","Suspendovan.")}
    if not user.get("subscription_end"): return {"active":False,"status":"no_sub","days_left":0,"message":"Nema pretplate."}
    try: end=date.fromisoformat(user["subscription_end"])
    except: return {"active":False,"status":"error","days_left":0,"message":"Greška datuma."}
    dl=(end-date.today()).days
    if dl<-GRACE_PERIOD_DAYS: return {"active":False,"status":"auto_suspended","days_left":dl,"message":f"Istekla pre {abs(dl)}d."}
    if dl<0: return {"active":True,"status":"grace","days_left":dl,"message":f"Istekla! Još {GRACE_PERIOD_DAYS+dl}d."}
    if dl<=7: return {"active":True,"status":"expiring","days_left":dl,"message":f"Ističe za {dl}d."}
    return {"active":True,"status":"active","days_left":dl,"message":""}

def run_auto_suspension():
    if st.session_state.get("_susp"): return
    try:
        cutoff=(date.today()-timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
        with get_db() as conn:
            conn.execute("UPDATE users SET is_active=0,auto_suspended=1,suspended_reason='Auto: istekla pretplata' WHERE role='user' AND is_active=1 AND subscription_end<?", (cutoff,))
        st.session_state["_susp"]=True
    except: pass

def log_action(uid, action, details=""):
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO usage_logs(user_id,action,details)VALUES(?,?,?)",(uid,action,details[:500]))
    except: pass


# ═══════════════════════════════════════════════════════════════
#  5. CSS (isto kao v3.2 + novi stilovi)
# ═══════════════════════════════════════════════════════════════

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');
body,p,h1,h2,h3,h4,h5,h6,span,div,input,textarea,button,label,a{{font-family:'Inter',sans-serif!important}}
.stApp{{background:{SURFACE}!important}}
#MainMenu,footer,header{{visibility:hidden}}
[data-testid="stSidebar"]{{display:none!important}}

.login-box{{max-width:440px;margin:6vh auto;padding:2.5rem;background:{CARD_BG};border-radius:24px;box-shadow:0 20px 60px rgba(10,22,40,.12);border:1px solid rgba(197,150,44,.15)}}
.login-logo{{text-align:center;margin-bottom:2rem}}
.login-logo .icon{{width:72px;height:72px;background:linear-gradient(135deg,{NAVY},{NAVY_MID});border-radius:20px;display:inline-flex;align-items:center;justify-content:center;font-size:2.2rem;margin-bottom:1rem;box-shadow:0 8px 24px rgba(10,22,40,.2)}}
.login-logo h1{{font-family:'Playfair Display',serif!important;font-size:1.8rem;color:{NAVY};margin:0}}
.login-logo p{{color:{TEXT_MUTED};font-size:.85rem;margin:.25rem 0 0 0}}

.top-bar{{background:linear-gradient(135deg,{NAVY},{NAVY_MID});color:white;padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center;border-radius:0 0 20px 20px;margin:-1rem -1rem 1.5rem -1rem;box-shadow:0 4px 20px rgba(10,22,40,.25);flex-wrap:wrap;gap:8px}}
.top-bar h2{{font-family:'Playfair Display',serif!important;margin:0;font-size:1.3rem;color:white}}
.top-bar .gold{{color:{GOLD}}}
.top-bar .info{{display:flex;gap:8px;align-items:center;font-size:.8rem;flex-wrap:wrap}}
.badge{{background:rgba(255,255,255,.15);padding:4px 12px;border-radius:20px;font-weight:500}}
.badge-gold{{background:{GOLD};color:{NAVY};font-weight:700}}
.badge-warn{{background:{WARNING};color:white}}
.badge-err{{background:{ERROR};color:white}}

.pk-card{{background:{CARD_BG};border-radius:20px;padding:1.75rem;margin:.75rem 0;box-shadow:0 1px 4px rgba(0,0,0,.06);border:1px solid rgba(0,0,0,.04)}}
.pk-card-gold{{background:{CARD_BG};border-radius:20px;padding:1.75rem;margin:.75rem 0;box-shadow:0 2px 12px rgba(197,150,44,.1);border-left:4px solid {GOLD}}}
.pk-card h3,.pk-card-gold h3{{font-family:'Playfair Display',serif!important;color:{NAVY};margin-top:0;font-size:1.15rem}}

.metric-box{{background:{CARD_BG};border-radius:16px;padding:1.25rem;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.metric-box .num{{font-family:'Playfair Display',serif!important;font-size:2rem;font-weight:700;color:{NAVY}}}
.metric-box .lbl{{font-size:.8rem;color:{TEXT_MUTED};margin-top:4px}}

.user-row{{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #f0f0f0;flex-wrap:wrap;gap:8px}}
.user-row:hover{{background:{GOLD_PALE}}}
.user-row .name{{font-weight:600;color:{NAVY};min-width:150px}}
.user-row .plan-tag{{padding:2px 10px;border-radius:12px;font-size:.75rem;font-weight:600;background:{GOLD_PALE};color:{GOLD}}}
.user-row .days{{font-weight:700;min-width:60px;text-align:center}}
.days-ok{{color:{SUCCESS}}} .days-warn{{color:{WARNING}}} .days-err{{color:{ERROR}}}

.tl-event{{background:{CARD_BG};border-left:3px solid {GOLD};border-radius:0 12px 12px 0;padding:1rem 1.25rem;margin:.5rem 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.tl-date{{font-family:'Playfair Display',serif!important;color:{NAVY};font-weight:700}}
.tl-src{{color:{TEXT_MUTED};font-size:.75rem}}

.st-badge{{display:inline-block;padding:3px 12px;border-radius:20px;font-size:.75rem;font-weight:600}}
.st-ok{{background:#D1FAE5;color:{SUCCESS}}} .st-warn{{background:#FEF3C7;color:{WARNING}}} .st-err{{background:#FEE2E2;color:{ERROR}}}

.stButton>button{{border-radius:12px!important;padding:.55rem 1.4rem!important;font-weight:600!important;border:none!important;background:{NAVY}!important;color:white!important}}
.stButton>button:hover{{background:{NAVY_MID}!important;box-shadow:0 4px 16px rgba(10,22,40,.25)!important}}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{{border-radius:12px!important;border:2px solid #E5E7EB!important}}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{{border-color:{GOLD}!important;box-shadow:0 0 0 3px rgba(197,150,44,.15)!important}}
.stTabs [data-baseweb="tab-list"]{{gap:4px;background:{CARD_BG};border-radius:14px;padding:4px}}
.stTabs [data-baseweb="tab"]{{border-radius:10px!important;font-weight:500!important}}
.stTabs [aria-selected="true"]{{background:{NAVY}!important;color:white!important}}
.stFileUploader>div{{border-radius:16px!important;border:2px dashed {GOLD_LIGHT}!important;background:{GOLD_PALE}!important}}
[data-testid="stChatMessage"]{{border-radius:16px!important}}
@media(max-width:768px){{.top-bar{{padding:.75rem 1rem;border-radius:0 0 14px 14px}}.top-bar h2{{font-size:1rem}}.pk-card,.pk-card-gold{{padding:1.25rem;border-radius:16px}}.login-box{{margin:2vh 1rem;padding:1.75rem}}}}
</style>
"""


# ═══════════════════════════════════════════════════════════════
#  6. PRAVNO ZNANJE + SUDSKA PRAKSA
# ═══════════════════════════════════════════════════════════════

KIM_KNOWLEDGE = """
## PRAVNI OKVIR KiM
### Rezolucija UN 1244 (1999) — NA SNAZI
- Potvrđuje suverenitet Srbije. UNMIK. Suštinska autonomija.
### UNMIK uredbe
- REG/1999/24 — pravo pre 22.03.1989.
- REG/2000/60 — stambeni zahtevi | REG/2002/13 — KPA | REG/2006/50 — imovinski zahtevi
### Ustav KS (2008) — NE poziva se na 1244
- Čl. 143: primat Ahtisarijevog plana. Srbija ne priznaje.
### Briselski (2013) + Ohridski (2023)
- ZSO neimplementirana.
### Imovina
- Privatna/društvena/crkovna. AKK vs RGZ. Uzurpacija. IRL.
"""

CASE_LAW_DB = """
## BAZA SUDSKE PRAKSE — KiM

### I. ODLUKE KPCC (Komisija za imovinske zahteve Kosova)

#### KPCC/D/R/100/2012 — Princip restitucije
- Vlasnik koji je napustio imovinu usled sukoba 1998-1999 ima pravo na povraćaj
- Nezakonito zauzimanje ne stvara pravo vlasništva
- Teret dokazivanja: podnosilac zahteva mora dokazati prethodno vlasništvo

#### KPCC/D/A/128/2013 — Društvena svojina
- Stanarsko pravo (pravo korišćenja stana) je zaštićeno
- Lica koja su imala stanarsko pravo pre 24.03.1999. imaju pravo na povraćaj
- Otkup stanova: moguć po proceduri iz UNMIK REG/2006/50

#### KPCC/D/C/205/2014 — Neformalne transakcije
- Kupoprodaje iz perioda 1989-1999 pod "prinudom" se mogu poništiti
- Princip: prodaja je ništava ako je izvršena pod pritiskom ili ispod tržišne cene
- Teret dokazivanja na podnosiocu zahteva

#### KPCC Opšti principi:
- Pravo na imovinu je fundamentalno ljudsko pravo
- Zabrana diskriminacije po etničkoj osnovi
- Rok za podnošenje: bio do 2009. (ZATVORENO)
- Nerešeni zahtevi: još uvek u obradi
- Izvršenje odluka: problematično na terenu

### II. ESLJP (Evropski sud za ljudska prava)

#### Behrami i Behrami v. Francuska (2007) — Odluka o nedopuštenosti
- ESLJP: radnje UNMIK-a i KFOR-a se pripisuju UN-u, ne državama
- Posledica: ESLJP NEMA nadležnost nad radnjama na KiM pod UN upravom
- Kritika: ostavlja pravni vakuum za žrtve kršenja prava

#### Grudić v. Srbija (2012) — Presuda
- Srbija kriva jer je prestala da isplaćuje penzije Srbima na KiM
- Kršenje čl. 1 Protokola 1 (zaštita imovine) i čl. 14 (diskriminacija)
- Srbija mora nastaviti isplate bez obzira na politički status KiM

#### Aksoy v. Turska (1996) — Princip primenljiv na KiM
- Država ne može koristiti "vanredne okolnosti" kao izgovor za kršenje imovinskih prava
- Relevantan za argumente o ratnim okolnostima na KiM

#### Loizidou v. Turska (1996) — Princip primenljiv na KiM
- Država koja vrši efektivnu kontrolu nad teritorijom odgovara za imovinska prava
- Pitanje: ko vrši "efektivnu kontrolu" na KiM — kosovske institucije, UNMIK ili Srbija?

### III. SAVETODAVNO MIŠLJENJE MSP-a (2010)

#### "Accordance with International Law of the Unilateral Declaration of Independence"
- MSP: Deklaracija o nezavisnosti Kosova NE krši opšte međunarodno pravo
- ALI: Mišljenje se NE bavi pitanjem:
  - Da li Kosovo IMA pravo na nezavisnost
  - Da li postoji pravo na secesiju
  - Da li je Rezolucija 1244 prestala da važi
- Status: SAVETODAVNO — nije pravno obavezujuće
- Srbija: koristi ovo da argumentuje da MSP nije priznao nezavisnost

### IV. ODLUKE KOSOVSKIH SUDOVA (relevantne)

#### Ustavni sud KS — KI 25/10 (2011)
- Potvrđuje primat Ahtisarijevog plana nad svim zakonima
- Zaštitne zone SPC su ustavna kategorija

#### Vrhovni sud KS — E. Rev. 24/2016
- Spor o vlasništvu: odobren povraćaj imovine srpskom vlasniku
- Primenjeno pravo: ZOO iz perioda pre 1989. (UNMIK REG/1999/24)

### V. SRPSKI SUDOVI (relevantne odluke)

#### Vrhovni kasacioni sud Srbije — Rev 1234/2018
- Srbija i dalje vodi evidenciju o imovini na KiM
- RGZ Srbije je "jedini legitimni katastar"
- Kosovske isprave "nemaju pravno dejstvo" u Srbiji

#### Ustavni sud Srbije — IUz-353/2009
- Ustav Kosova je "jednostrani akt" bez pravnog dejstva
- Rezolucija 1244 je jedini pravni osnov za status KiM
"""


SYSTEM_PROMPT = """Ti si "Prava Kolevka" — pravni AI za Kosovo i Metohiju.
PRAVILA:
1. UVEK na SRPSKOM (latinica).
2. Albansko/englesko → pravna suština na srpskom.
3. Citiraj članove zakona. Navedi izvor.
4. Informativno — konsultovati advokata.
5. Naznači pravni sistem: (a) Međunarodno (b) UNMIK (c) Kosovski (d) Srpski.
6. Koristi i SUDSKU PRAKSU gde je relevantno (KPCC, ESLJP, MSP).

{kim_knowledge}

{case_law}

DOKUMENTI: {context}
PITANJE: {question}
ODGOVOR:"""


TRANSLATE_PROMPT = """Profesionalni pravni prevodilac. Prevedi SVE na srpski.
PRAVILA:
1. Prevedi SVE — svaku rečenicu. Ništa ne preskačeš.
2. Standardna srpska pravna terminologija.
3. Specifični termini: original u zagradi pri prvom pojavljivanju.
4. Zadrži strukturu. NE dodaji komentare.

TEKST ({lang}):
{text}

SRPSKI PREVOD:"""


LEGAL_DICT = {
    "Gjykata Themelore":"Osnovni sud","Gjykata e Apelit":"Apelacioni sud",
    "Gjykata Supreme":"Vrhovni sud","Gjykata Kushtetuese":"Ustavni sud",
    "Pronë":"Imovina","Pronë e paluajtshme":"Nepokretna imovina",
    "Pronësi":"Vlasništvo","Pronësia private":"Privatna svojina",
    "Pronësia shoqërore":"Društvena svojina","Bashkëpronësi":"Suvlasništvo",
    "Ngastra kadastrale":"Katastarska parcela","Fletë-posedimi":"Posedovni list",
    "Certifikatë pronësie":"Vlasnički list","Hipotekë":"Hipoteka",
    "Eksproprijim":"Eksproprijacija","Kthim i pronës":"Povraćaj imovine",
    "Kontratë":"Ugovor","Kontrata e shitblerjes":"Kupoprodajni ugovor",
    "Padi":"Tužba","Paditës":"Tužilac","I paditur":"Tuženi",
    "Vendim":"Odluka/Presuda","Aktvendim":"Rešenje","Aktgjykim":"Presuda",
    "Ankesë":"Žalba","Afat":"Rok","Parashkrim":"Zastarelost",
    "Ligj":"Zakon","Neni":"Član","Trashëgimi":"Nasleđivanje",
    "Ndërtim pa leje":"Nelegalna gradnja","Leja e ndërtimit":"Građ. dozvola",
    "Agjencia Kadastrale e Kosovës":"AKK","Agjencia Kosovare e Pronës":"KPA",
}


# ═══════════════════════════════════════════════════════════════
#  7. ŠABLONI ZA PRAVNE PODNESKE
# ═══════════════════════════════════════════════════════════════

DOCUMENT_TEMPLATES = {
    "zalba_kpa": {
        "name": "Žalba na odluku KPA/KPCC",
        "icon": "📋",
        "prompt": """Napiši ŽALBU na odluku Kosovske agencije za imovinu (KPA/KPCC).

INFORMACIJE O SLUČAJU:
{case_info}

DOKUMENTI (ako postoje):
{documents}

FORMAT ŽALBE:
1. Zaglavlje (ko podnosi, kome, broj predmeta)
2. Uvod (protiv koje odluke se žali)
3. Činjenično stanje
4. Pravni osnov žalbe (UNMIK uredbe, Rez. 1244, primenjivo pravo)
5. Žalbeni razlozi (taksativno nabrojani)
6. Predlog (šta se traži)
7. Dokazi (lista priloga)
8. Potpis i datum

Napiši profesionalnu žalbu na SRPSKOM jeziku. Koristi formalan pravni stil."""
    },
    "tuzba_svojina": {
        "name": "Tužba za utvrđivanje prava svojine",
        "icon": "⚖️",
        "prompt": """Napiši TUŽBU za utvrđivanje prava svojine na nepokretnosti na KiM.

INFORMACIJE:
{case_info}

DOKUMENTI:
{documents}

FORMAT:
1. Zaglavlje suda (Osnovni sud / Gjykata Themelore)
2. Stranke (tužilac, tuženi)
3. Vrednost spora
4. Tužbeni zahtev (petitum)
5. Činjenično stanje
6. Pravni osnov (ZOO, ZOSO, UNMIK uredbe)
7. Dokazi
8. Potpis

Profesionalna tužba na SRPSKOM. Navedi alternativno i albanske nazive institucija."""
    },
    "zahtev_povracaj": {
        "name": "Zahtev za povraćaj imovine",
        "icon": "🏠",
        "prompt": """Napiši ZAHTEV za povraćaj imovine (restituciju) na KiM.

INFORMACIJE:
{case_info}

DOKUMENTI:
{documents}

FORMAT:
1. Naslovljen na nadležni organ (KPA, opštinu, sud)
2. Podaci o podnosiocu zahteva
3. Opis imovine (lokacija, katastarska parcela, površina)
4. Osnov zahteva (vlasništvo pre sukoba, uzurpacija)
5. Pravni osnov (UNMIK REG/2000/60, REG/2006/50)
6. Tražena radnja
7. Prilozi
8. Potpis

Na SRPSKOM jeziku, formalan stil."""
    },
    "zalba_presuda": {
        "name": "Žalba na sudsku presudu",
        "icon": "📜",
        "prompt": """Napiši ŽALBU na presudu suda na KiM.

INFORMACIJE:
{case_info}

DOKUMENTI:
{documents}

FORMAT:
1. Zaglavlje (Apelacioni sud / Gjykata e Apelit)
2. Prvostepena presuda (broj, datum, sud)
3. Izjava o žalbi
4. Žalbeni razlozi:
   a) Bitna povreda postupka
   b) Pogrešno utvrđeno činjenično stanje
   c) Pogrešna primena materijalnog prava
5. Predlog
6. Potpis

Na SRPSKOM. Rok za žalbu: obično 15 dana od prijema presude."""
    },
    "punomocje": {
        "name": "Punomoćje za zastupanje",
        "icon": "✍️",
        "prompt": """Napiši PUNOMOĆJE (autorizim) za zastupanje pred organima na KiM.

INFORMACIJE:
{case_info}

FORMAT:
1. Naslov: PUNOMOĆJE / AUTORIZIM
2. Podaci o vlastodavcu (ime, JMBG/lični broj, adresa)
3. Podaci o punomoćniku (advokat, broj licence)
4. Obim ovlašćenja (generalno ili specijalno)
5. Pred kojim organima važi
6. Trajanje
7. Potpis, datum, overa

DVOJEZIČNO: srpski + albanski (oba teksta paralelno)."""
    },
    "zahtev_katastar": {
        "name": "Zahtev za uvid/ispravku katastra",
        "icon": "🗺️",
        "prompt": """Napiši ZAHTEV za uvid u katastarsku evidenciju ili ispravku podataka.

INFORMACIJE:
{case_info}

FORMAT:
1. Naslovljen na: AKK ili RGZ Srbije (navedi oba)
2. Podaci o podnosiocu
3. Katastarska parcela (broj, zona, opština)
4. Šta se traži (uvid, izvod, ispravka)
5. Razlog zahteva
6. Pravni osnov
7. Prilozi (dokazi vlasništva)

Na SRPSKOM. Napomeni razliku AKK vs RGZ evidencije."""
    }
}


# ═══════════════════════════════════════════════════════════════
#  8. AI FUNKCIJE
# ═══════════════════════════════════════════════════════════════

def get_llm(temp=0.1, tokens=4096):
    return ChatOpenAI(model="gpt-4o-mini",api_key=OPENAI_API_KEY,temperature=temp,max_tokens=tokens)

def detect_language(text):
    s=text.lower()[:2000]
    if len(re.findall(r'[а-яА-ЯђћчжшЂЋ]',s))>len(s)*0.1: return "sr"
    al=sum(1 for m in ['është','dhe','për','nga','në','që','një','vendim','gjykata','pronë'] if m in s)
    en=sum(1 for m in ['the','and','for','that','property','court','decision','shall'] if m in s)
    sr=sum(1 for m in [' je ',' su ',' ili ','predmet','odluka','zakon','imovina'] if m in s)
    scores={"al":al,"en":en,"sr":sr}; best=max(scores,key=scores.get)
    return best if scores[best]>=2 else "sr"

def extract_pdf(file):
    try:
        r=PdfReader(file); parts=[]
        for i,p in enumerate(r.pages):
            t=p.extract_text()
            if t: parts.append(f"[Strana {i+1}]\n{t}")
        return "\n\n".join(parts)
    except: return ""

def process_file(file):
    name=file.name
    if name.lower().endswith('.pdf'): text=extract_pdf(file)
    elif name.lower().endswith('.txt'):
        raw=file.read(); text=""
        for enc in ['utf-8','latin-1','cp1250','cp1251']:
            try: text=raw.decode(enc); break
            except: continue
        if not text: text=raw.decode('utf-8',errors='replace')
    else: return "","",""
    return text, name, detect_language(text) if text else "sr"

def build_vs(docs_data, api_key):
    sp=RecursiveCharacterTextSplitter(chunk_size=1500,chunk_overlap=300)
    all_d=[]
    for d in docs_data:
        if not d.get("text"): continue
        for i,c in enumerate(sp.split_text(d["text"])):
            all_d.append(Document(page_content=c,metadata={"source":d["name"],"language":d.get("lang_name","?")}))
    if not all_d: return None
    return FAISS.from_documents(all_d, OpenAIEmbeddings(model="text-embedding-3-small",api_key=api_key))

def query_ai(question, vs, api_key):
    llm=get_llm(); context="(Nema dokumenata.)"; sources=[]
    if vs:
        try:
            docs=vs.as_retriever(search_kwargs={"k":6}).invoke(question)
            parts=[]; 
            for d in docs:
                src=d.metadata.get("source","?"); parts.append(f"[{src}]\n{d.page_content}")
                if src not in sources: sources.append(src)
            if parts: context="\n---\n".join(parts)
        except: pass
    prompt=SYSTEM_PROMPT.format(kim_knowledge=KIM_KNOWLEDGE,case_law=CASE_LAW_DB,context=context,question=question)
    try:
        r=llm.invoke([HumanMessage(content=prompt)]); ans=r.content
        if sources: ans+="\n\n---\n📎 **Izvori:** "+", ".join(f"*{s}*" for s in sources)
        return ans
    except Exception as e: return f"⚠️ Greška: {e}"


def translate_full(text, lang):
    lang_name={"al":"albanski","en":"engleski","sr":"srpski"}.get(lang,"nepoznat")
    if lang=="sr": return text
    llm=get_llm(temp=0.05,tokens=8000)
    # Deli na delove ako je dugačko
    if len(text)<6000:
        try: return llm.invoke([HumanMessage(content=TRANSLATE_PROMPT.format(lang=lang_name,text=text))]).content
        except Exception as e: return f"⚠️ {e}"
    chunks=[]; cur=""
    for sent in re.split(r'(?<=[.!?])\s+',text):
        if len(cur)+len(sent)<4000: cur+=sent+" "
        else:
            if cur.strip(): chunks.append(cur.strip())
            cur=sent+" "
    if cur.strip(): chunks.append(cur.strip())
    parts=[]
    for i,ch in enumerate(chunks):
        try: parts.append(llm.invoke([HumanMessage(content=TRANSLATE_PROMPT.format(lang=lang_name,text=ch))]).content)
        except Exception as e: parts.append(f"[Greška deo {i+1}: {e}]")
    return "\n\n".join(parts)


def extract_dates(text, source):
    events=[]; seen=set()
    for m in re.finditer(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\.?\b',text):
        try:
            d,mo,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
            if 1<=d<=31 and 1<=mo<=12 and 1900<=y<=2030:
                key=f"{d:02d}.{mo:02d}.{y}|{source}"
                if key not in seen:
                    seen.add(key); start=max(0,m.start()-100); end=min(len(text),m.end()+100)
                    events.append({"date":datetime(y,mo,d),"date_str":f"{d:02d}.{mo:02d}.{y}",
                        "context":re.sub(r'\s+',' ',text[start:end]).strip(),"source":source})
        except: pass
    return sorted(events,key=lambda x:x["date"])


# ═══════════════════════════════════════════════════════════════
#  9. OCR — KAMERA → TEKST (GPT-4o-mini Vision)
# ═══════════════════════════════════════════════════════════════

def ocr_image(image_bytes: bytes) -> str:
    """Šalje sliku na GPT-4o-mini Vision i izvlači tekst."""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": 
                        "Izvuci KOMPLETAN tekst sa ove slike pravnog dokumenta. "
                        "Zadrži originalnu strukturu, formatiranje, jezik dokumenta. "
                        "Uključi SVE: naslove, brojeve, datume, imena, pečate, potpise (naznači [potpis], [pečat]). "
                        "Ne preskačeš ništa. Ne dodaji svoje komentare. Samo čist tekst."
                    },
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            }],
            max_tokens=4096
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ OCR greška: {e}"


def process_camera_image(image_file) -> Tuple[str, str]:
    """Obrađuje sliku sa kamere. Vraća (tekst, jezik)."""
    img = Image.open(image_file)
    # Konvertuj u JPEG za manji payload
    buf = io.BytesIO()
    img = img.convert("RGB")
    # Smanjiti ako je prevelika (max 2000px širina)
    if img.width > 2000:
        ratio = 2000 / img.width
        img = img.resize((2000, int(img.height * ratio)), Image.LANCZOS)
    img.save(buf, format="JPEG", quality=85)
    image_bytes = buf.getvalue()
    
    text = ocr_image(image_bytes)
    lang = detect_language(text) if text and not text.startswith("⚠️") else "sr"
    return text, lang


# ═══════════════════════════════════════════════════════════════
#  10. GENERISANJE PODNESAKA
# ═══════════════════════════════════════════════════════════════

def generate_legal_document(template_key: str, case_info: str, documents_text: str = "") -> str:
    template = DOCUMENT_TEMPLATES.get(template_key)
    if not template:
        return "⚠️ Nepoznat šablon."
    
    llm = get_llm(temp=0.15, tokens=6000)
    prompt = template["prompt"].format(
        case_info=case_info if case_info else "(Korisnik nije uneo informacije o slučaju.)",
        documents=documents_text[:5000] if documents_text else "(Nema učitanih dokumenata.)"
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        return resp.content
    except Exception as e:
        return f"⚠️ Greška: {e}"


# ═══════════════════════════════════════════════════════════════
#  11. WORD EXPORT
# ═══════════════════════════════════════════════════════════════

def create_word(title, body, source_name="", source_lang=""):
    doc = DocxDocument()
    s=doc.styles['Normal']; s.font.name='Arial'; s.font.size=Pt(11)
    h=doc.add_paragraph(); h.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=h.add_run("⚖️ PRAVA KOLEVKA"); r.bold=True; r.font.size=Pt(16); r.font.color.rgb=RGBColor(10,22,40)
    doc.add_paragraph("")
    if source_name:
        p=doc.add_paragraph(); p.add_run("Dokument: ").bold=True; p.add_run(source_name)
    if source_lang:
        p=doc.add_paragraph(); p.add_run("Jezik: ").bold=True; p.add_run(LANG_NAMES.get(source_lang,source_lang))
    p=doc.add_paragraph(); p.add_run("Datum: ").bold=True; p.add_run(datetime.now().strftime("%d.%m.%Y. %H:%M"))
    doc.add_paragraph("─"*50)
    doc.add_heading(title, level=1).runs[0].font.color.rgb=RGBColor(10,22,40)
    for para in body.split("\n"):
        s=para.strip()
        if s.startswith("## "): doc.add_heading(s[3:],level=2)
        elif s.startswith("### "): doc.add_heading(s[4:],level=3)
        elif s.startswith("- "): doc.add_paragraph(s[2:],style='List Bullet')
        elif s: doc.add_paragraph(s)
    doc.add_paragraph("─"*50)
    f=doc.add_paragraph(); f.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=f.add_run("Generisano: Prava Kolevka AI | ⚠️ Informativno — konsultujte advokata.")
    r.font.size=Pt(9); r.font.color.rgb=RGBColor(107,114,128)
    buf=io.BytesIO(); doc.save(buf); buf.seek(0); return buf


# ═══════════════════════════════════════════════════════════════
#  12. LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════

def render_login():
    st.markdown(f'<div class="login-box"><div class="login-logo"><div class="icon">⚖️</div><h1>Prava Kolevka</h1><p>Pravna AI platforma za KiM</p></div></div>', unsafe_allow_html=True)
    _,col,_=st.columns([1,2,1])
    with col:
        with st.form("login",clear_on_submit=False):
            email=st.text_input("📧 Email",placeholder="vas@email.com")
            pw=st.text_input("🔒 Lozinka",type="password")
            if st.form_submit_button("Prijavi se",use_container_width=True):
                if not email or not pw: st.error("Unesite podatke.")
                else:
                    u=authenticate_user(email,pw)
                    if u:
                        st.session_state.current_user=u; st.session_state.logged_in=True
                        try:
                            with get_db() as conn: conn.execute("UPDATE users SET last_login=? WHERE id=?",(datetime.now().isoformat(),u["id"]))
                        except: pass
                        log_action(u["id"],"login"); st.rerun()
                    else: st.error("❌ Pogrešni podaci.")
        st.markdown(f"<p style='text-align:center;color:{TEXT_MUTED};font-size:.8rem;'>Nemate nalog? Kontaktirajte admina.<br>⚖️ v4.0</p>", unsafe_allow_html=True)

def do_logout():
    uid=st.session_state.get("current_user",{}).get("id") if st.session_state.get("current_user") else None
    if uid: log_action(uid,"logout")
    for k in list(st.session_state.keys()): del st.session_state[k]
    init_ss()


# ═══════════════════════════════════════════════════════════════
#  13. ADMIN PANEL (poboljšan)
# ═══════════════════════════════════════════════════════════════

def render_admin():
    u=st.session_state.current_user
    st.markdown(f'<div class="top-bar"><div style="display:flex;align-items:center;gap:12px"><span style="font-size:1.5rem">⚖️</span><h2>Prava <span class="gold">Kolevka</span></h2></div><div class="info"><span class="badge badge-gold">ADMIN</span><span class="badge">{u["full_name"]}</span></div></div>', unsafe_allow_html=True)
    t1,t2,t3,t4=st.tabs(["📊 Pregled","👥 Korisnici","💰 Uplate","⚙️ Podešavanja"])
    with t1: admin_dashboard()
    with t2: admin_users()
    with t3: admin_payments()
    with t4: admin_settings()
    st.markdown("---")
    if st.button("🚪 Odjavi se",key="adm_out"): do_logout(); st.rerun()


def admin_dashboard():
    try:
        with get_db() as conn:
            total=conn.execute("SELECT COUNT(*) c FROM users WHERE role='user'").fetchone()["c"]
            active=conn.execute("SELECT COUNT(*) c FROM users WHERE role='user' AND is_active=1").fetchone()["c"]
            suspended=conn.execute("SELECT COUNT(*) c FROM users WHERE role='user' AND is_active=0").fetchone()["c"]
            ms=date.today().replace(day=1).isoformat()
            revenue=conn.execute("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='completed' AND payment_date>=?",(ms,)).fetchone()["s"]
            total_rev=conn.execute("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='completed'").fetchone()["s"]

            # NOVA: Tabela SVIH korisnika sa danima do uplate
            all_users=conn.execute(
                "SELECT id,full_name,email,plan,is_active,subscription_end,last_login "
                "FROM users WHERE role='user' ORDER BY subscription_end ASC"
            ).fetchall()
    except Exception as e:
        st.error(f"Greška: {e}"); return

    # Metrike
    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(f'<div class="metric-box"><div class="num">{active}</div><div class="lbl">Aktivnih</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="num" style="color:{WARNING}">{total-active-suspended}</div><div class="lbl">Grace period</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box"><div class="num" style="color:{ERROR}">{suspended}</div><div class="lbl">Suspendovano</div></div>',unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-box"><div class="num" style="color:{SUCCESS}">€{revenue:.0f}</div><div class="lbl">Ovaj mesec</div></div>',unsafe_allow_html=True)

    st.info(f"Ukupno: **{total}** korisnika | Sveukupan prihod: **€{total_rev:.0f}**")

    # ══ NOVA TABELA: Svi korisnici sa danima do uplate ══
    st.markdown("### 📋 Pregled svih korisnika i uplata")
    st.markdown(f'<div class="pk-card" style="padding:0;overflow:hidden;">', unsafe_allow_html=True)

    # Zaglavlje
    st.markdown(f"""
    <div class="user-row" style="background:{NAVY};color:white;font-weight:600;border-radius:20px 20px 0 0;">
        <span class="name" style="color:white;">Ime</span>
        <span style="min-width:120px;">Email</span>
        <span style="min-width:80px;">Plan</span>
        <span style="min-width:80px;text-align:center;">Dana do uplate</span>
        <span style="min-width:90px;">Datum isteka</span>
        <span style="min-width:60px;">Status</span>
    </div>
    """, unsafe_allow_html=True)

    for u in all_users:
        u=dict(u)
        plan=PLANS.get(u["plan"],{"name":"?","icon":"?","price":0})
        
        # Izračunaj dane
        if u.get("subscription_end"):
            try:
                end=date.fromisoformat(u["subscription_end"])
                dl=(end-date.today()).days
                if dl>7: days_html=f'<span class="days days-ok">{dl}d</span>'
                elif dl>0: days_html=f'<span class="days days-warn">⚠️ {dl}d</span>'
                elif dl>-GRACE_PERIOD_DAYS: days_html=f'<span class="days days-warn">⏳ {dl}d</span>'
                else: days_html=f'<span class="days days-err">❌ {dl}d</span>'
                end_str=u["subscription_end"]
            except:
                days_html='<span class="days days-err">?</span>'; end_str="?"
        else:
            days_html='<span class="days days-err">—</span>'; end_str="—"

        if u["is_active"]:
            status='<span class="st-badge st-ok">●</span>'
        else:
            status='<span class="st-badge st-err">✗</span>'

        st.markdown(f"""
        <div class="user-row">
            <span class="name">{u["full_name"]}</span>
            <span style="min-width:120px;font-size:.85rem;color:{TEXT_MUTED};">{u["email"]}</span>
            <span class="plan-tag">{plan["icon"]} {plan["name"]}</span>
            {days_html}
            <span style="min-width:90px;font-size:.85rem;">{end_str}</span>
            {status}
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def admin_users():
    st.markdown("### 👥 Korisnici")
    with st.expander("➕ Dodaj korisnika"):
        with st.form("add_u"):
            c1,c2=st.columns(2)
            with c1: nn=st.text_input("Ime *",key="nu_n"); ne=st.text_input("Email *",key="nu_e"); np=st.text_input("Tel",key="nu_p")
            with c2:
                nf=st.text_input("Kancelarija",key="nu_f")
                npl=st.selectbox("Plan",list(PLANS.keys()),format_func=lambda x:f"{PLANS[x]['icon']} {PLANS[x]['name']} (€{PLANS[x]['price']})",key="nu_pl")
                nd=st.number_input("Dana",1,value=30,key="nu_d")
            npw=st.text_input("Lozinka *",value="Kolevka2024!",key="nu_pw")
            if st.form_submit_button("✅ Kreiraj"):
                if not nn or not ne or not npw: st.error("Popunite polja.")
                else:
                    try:
                        salt=secrets.token_hex(16); ph=hash_password(npw,salt); se=(date.today()+timedelta(days=nd)).isoformat()
                        with get_db() as conn:
                            conn.execute("INSERT INTO users(email,password_hash,salt,full_name,role,firm_name,phone,plan,is_active,subscription_start,subscription_end)VALUES(?,?,?,?,'user',?,?,?,1,?,?)",
                                (ne.lower().strip(),ph,salt,nn,nf,np,npl,date.today().isoformat(),se))
                        st.success(f"✅ {nn} do {se}"); st.rerun()
                    except sqlite3.IntegrityError: st.error("Email postoji.")
                    except Exception as e: st.error(f"{e}")

    try:
        with get_db() as conn: users=conn.execute("SELECT * FROM users WHERE role='user' ORDER BY is_active DESC,full_name").fetchall()
    except: return
    for u in users:
        u=dict(u); sub=check_subscription(u); plan=PLANS.get(u["plan"],{"name":"?","icon":"?","price":0})
        if sub["status"]=="active": badge=f'<span class="st-badge st-ok">● {sub["days_left"]}d</span>'
        elif sub["status"] in ("expiring","grace"): badge=f'<span class="st-badge st-warn">⚠ {sub["days_left"]}d</span>'
        else: badge=f'<span class="st-badge st-err">✗</span>'
        with st.expander(f"{plan['icon']} {u['full_name']} — {u['email']}"):
            st.markdown(f"**Status:** {badge} | **Plan:** {plan['name']} (€{plan['price']}) | **Do:** {u.get('subscription_end','-')} | **Login:** {u.get('last_login','Nikada')}", unsafe_allow_html=True)
            c1,c2,c3=st.columns(3)
            with c1:
                ext=st.number_input("Dana",1,value=30,key=f"e_{u['id']}")
                if st.button("📅 Produži",key=f"ext_{u['id']}"):
                    curr=date.fromisoformat(u["subscription_end"]) if u.get("subscription_end") else date.today()
                    ne=(max(curr,date.today())+timedelta(days=ext)).isoformat()
                    with get_db() as conn: conn.execute("UPDATE users SET subscription_end=?,is_active=1,auto_suspended=0,suspended_reason='' WHERE id=?",(ne,u["id"]))
                    st.success(f"Do {ne}"); st.rerun()
            with c2:
                if u["is_active"]:
                    if st.button("🔴 Suspenduj",key=f"s_{u['id']}"):
                        with get_db() as conn: conn.execute("UPDATE users SET is_active=0,suspended_reason='Ručno' WHERE id=?",(u["id"],)); st.rerun()
                else:
                    if st.button("🟢 Aktiviraj",key=f"a_{u['id']}"):
                        ne=(date.today()+timedelta(days=30)).isoformat()
                        with get_db() as conn: conn.execute("UPDATE users SET is_active=1,auto_suspended=0,suspended_reason='',subscription_end=? WHERE id=?",(ne,u["id"])); st.rerun()
            with c3:
                npp=st.selectbox("Plan",list(PLANS.keys()),index=list(PLANS.keys()).index(u["plan"]),format_func=lambda x:PLANS[x]["name"],key=f"p_{u['id']}")
                if st.button("💼",key=f"cp_{u['id']}"):
                    with get_db() as conn: conn.execute("UPDATE users SET plan=? WHERE id=?",(npp,u["id"])); st.rerun()

def admin_payments():
    st.markdown("### 💰 Uplate")
    with st.expander("➕ Nova"):
        try:
            with get_db() as conn: users=conn.execute("SELECT id,full_name,email FROM users WHERE role='user' ORDER BY full_name").fetchall()
        except: return
        if not users: st.info("Nema korisnika."); return
        with st.form("pay"):
            opts={u["id"]:f"{u['full_name']} ({u['email']})" for u in users}
            uid=st.selectbox("Korisnik",list(opts.keys()),format_func=lambda x:opts[x])
            c1,c2=st.columns(2)
            with c1: amt=st.number_input("€",min_value=1.0,value=29.0); pd=st.date_input("Datum",value=date.today())
            with c2: days=st.number_input("Dana",1,value=30); meth=st.selectbox("Način",["Transfer","Gotovina","PayPal","Kripto"])
            if st.form_submit_button("✅"):
                pe=(pd+timedelta(days=days)).isoformat()
                with get_db() as conn:
                    conn.execute("INSERT INTO payments(user_id,amount,payment_date,period_start,period_end,method,recorded_by)VALUES(?,?,?,?,?,?,?)",(uid,amt,pd.isoformat(),pd.isoformat(),pe,meth,st.session_state.current_user["id"]))
                    conn.execute("UPDATE users SET subscription_end=?,is_active=1,auto_suspended=0,suspended_reason='' WHERE id=?",(pe,uid))
                st.success(f"€{amt} do {pe}"); st.rerun()
    try:
        with get_db() as conn: pays=conn.execute("SELECT p.*,u.full_name FROM payments p JOIN users u ON p.user_id=u.id ORDER BY p.payment_date DESC LIMIT 50").fetchall()
    except: pays=[]
    for p in pays: st.markdown(f"✅ **{p['payment_date']}** — {p['full_name']} — **€{p['amount']:.0f}** — {p['method']}")

def admin_settings():
    st.markdown(f"### ⚙️ Podešavanja\n**Admin:** `{ADMIN_EMAIL}` | **API:** {'✅' if OPENAI_API_KEY else '❌'}")
    with st.expander("🔒 Lozinka"):
        with st.form("chpw"):
            old=st.text_input("Trenutna",type="password"); new=st.text_input("Nova",type="password"); conf=st.text_input("Potvrdi",type="password")
            if st.form_submit_button("Promeni"):
                if new!=conf: st.error("Ne poklapaju se.")
                elif len(new)<8: st.error("Min 8.")
                else:
                    u=st.session_state.current_user
                    if hash_password(old,u["salt"])==u["password_hash"]:
                        ns=secrets.token_hex(16); nh=hash_password(new,ns)
                        with get_db() as conn: conn.execute("UPDATE users SET password_hash=?,salt=? WHERE id=?",(nh,ns,u["id"]))
                        st.success("✅")
                    else: st.error("Pogrešna.")


# ═══════════════════════════════════════════════════════════════
#  14. KORISNIČKI PANEL
# ═══════════════════════════════════════════════════════════════

def render_user():
    user=st.session_state.current_user; sub=check_subscription(user)
    if not sub["active"]:
        st.markdown(f'<div style="text-align:center;padding:4rem"><div style="font-size:5rem">🔒</div><h2 style="font-family:\'Playfair Display\',serif;color:{NAVY}">Pretplata istekla</h2><p>{sub["message"]}</p><p>Kontakt: <b>{ADMIN_EMAIL}</b></p></div>',unsafe_allow_html=True)
        if st.button("🚪 Odjavi se",key="exp_out"): do_logout(); st.rerun()
        return

    plan=PLANS.get(user["plan"],{"name":"?","icon":"?","can_share":False})
    bc="badge-gold"; bt=f"{sub['days_left']}d"
    if sub["status"]=="expiring": bc="badge-warn"; bt=f"⚠{sub['days_left']}d"
    elif sub["status"]=="grace": bc="badge-err"; bt="ISTEKLO"
    st.markdown(f'<div class="top-bar"><div style="display:flex;align-items:center;gap:12px"><span style="font-size:1.5rem">⚖️</span><h2>Prava <span class="gold">Kolevka</span></h2></div><div class="info"><span class="badge">{plan["icon"]} {plan["name"]}</span><span class="badge {bc}">{bt}</span><span class="badge">{user["full_name"]}</span></div></div>',unsafe_allow_html=True)
    if sub["message"]: st.warning(f"⚠️ {sub['message']}")
    if not OPENAI_API_KEY: st.error("AI nije podešen."); return

    # Tabovi — prikaži deljenje samo ako plan dozvoljava
    tab_names=["📄 Analiza","🔄 Prevod","📝 Podnesci","📅 Hronologija","📚 Pravo","🌉 Most"]
    if plan.get("can_share"): tab_names.append("🤝 Deljenje")

    tabs=st.tabs(tab_names)
    with tabs[0]: tab_analysis()
    with tabs[1]: tab_translate()
    with tabs[2]: tab_documents()
    with tabs[3]: tab_timeline()
    with tabs[4]: tab_legal_knowledge()
    with tabs[5]: tab_bridge()
    if plan.get("can_share") and len(tabs)>6:
        with tabs[6]: tab_sharing()

    st.markdown("---")
    if st.button("🚪 Odjavi se",key="usr_out"): do_logout(); st.rerun()


# ─── TAB: ANALIZA (+ kamera) ─────────────────────────

def tab_analysis():
    user=st.session_state.current_user
    st.markdown('<div class="pk-card-gold"><h3>📄 Pravna analiza</h3><p style="color:#6B7280;margin:0">Učitajte dokument, slikajte kamerom ili pitajte AI.</p></div>',unsafe_allow_html=True)

    # Dva načina unosa
    input_method = st.radio("Način unosa dokumenta:", ["📁 Fajl (PDF/TXT)", "📸 Kamera (slikaj dokument)"],
        horizontal=True, key="input_method", label_visibility="collapsed")

    if input_method == "📁 Fajl (PDF/TXT)":
        uploaded=st.file_uploader("PDF/TXT",type=["pdf","txt"],accept_multiple_files=True,key="a_upload")
        if uploaded:
            existing={d["name"] for d in st.session_state.docs}
            new=[f for f in uploaded if f.name not in existing]
            if new:
                with st.spinner("⏳"):
                    for f in new:
                        text,name,lang=process_file(f)
                        if text: st.session_state.docs.append({"name":name,"lang":lang,"lang_name":LANG_NAMES.get(lang,"?"),"text":text,"size":len(text)})
                    _rebuild_index(user)

    elif input_method == "📸 Kamera (slikaj dokument)":
        st.markdown(f'<div class="pk-card" style="background:{GOLD_PALE}"><p style="margin:0;font-size:.9rem">📸 <b>Slikajte dokument</b> kamerom telefona ili učitajte fotografiju. AI će izvući tekst automatski.</p></div>',unsafe_allow_html=True)

        cam_col1, cam_col2 = st.columns(2)
        with cam_col1:
            camera_img = st.camera_input("📸 Slikajte dokument", key="cam_input")
        with cam_col2:
            photo_upload = st.file_uploader("📤 Ili učitajte fotografiju", type=["jpg","jpeg","png","webp"], key="photo_upload")

        img_source = camera_img or photo_upload

        if img_source:
            st.image(img_source, caption="Učitana slika", use_container_width=True)
            if st.button("🔍 Izvuci tekst iz slike", use_container_width=True, key="ocr_btn"):
                with st.spinner("⏳ AI čita tekst sa slike... (10-30 sekundi)"):
                    text, lang = process_camera_image(img_source)

                if text and not text.startswith("⚠️"):
                    st.session_state.ocr_text = text
                    lang_em = {"sr":"🇷🇸","al":"🇦🇱","en":"🇬🇧"}.get(lang,"🏳️")
                    st.success(f"✅ Tekst izvučen! Jezik: {lang_em} {LANG_NAMES.get(lang,'?')}")
                    st.markdown("#### Izvučeni tekst:")
                    st.text_area("OCR rezultat", value=text, height=200, key="ocr_result", disabled=True)

                    if st.button("➕ Dodaj u analizu", key="add_ocr", use_container_width=True):
                        name = f"Kamera_{datetime.now().strftime('%H%M%S')}.txt"
                        st.session_state.docs.append({"name":name,"lang":lang,"lang_name":LANG_NAMES.get(lang,"?"),"text":text,"size":len(text)})
                        _rebuild_index(user)
                        st.success(f"✅ Dodat: {name}")
                        st.rerun()

                    if lang != "sr":
                        if st.button("🔄 Prevedi na srpski", key="ocr_translate", use_container_width=True):
                            with st.spinner("⏳ Prevodim..."):
                                translated = translate_full(text, lang)
                            st.markdown("#### Prevod:")
                            st.markdown(translated)
                            word=create_word("OCR Prevod",translated,f"Kamera_{datetime.now().strftime('%H%M%S')}",lang)
                            st.download_button("📥 Word",data=word,file_name=f"OCR_Prevod_{date.today()}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
                else:
                    st.error(text or "Nije moguće izvući tekst.")
                    log_action(user["id"],"ocr_fail","")

    # Učitani dokumenti
    if st.session_state.docs:
        with st.expander(f"📋 Učitano: {len(st.session_state.docs)} dokument(a)"):
            for d in st.session_state.docs:
                em={"sr":"🇷🇸","al":"🇦🇱","en":"🇬🇧"}.get(d["lang"],"🏳️")
                st.caption(f"{em} {d['name']} — {d['lang_name']} — {d['size']/1024:.1f}KB")
            if st.button("🗑️ Obriši sve",key="clr"):
                st.session_state.docs=[]; st.session_state.vs=None; st.session_state.events=[]; st.session_state.chat=[]; st.rerun()

    # Chat
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"],avatar="👤" if msg["role"]=="user" else "⚖️"):
            st.markdown(msg["content"])

    if not st.session_state.chat:
        sugs=["Koja su moja prava na nepokretnost na KiM?","Postupak pred KPA?","Relevantna sudska praksa ESLJP za imovinu na KiM?"]
        if st.session_state.docs: sugs.insert(0,"Sumariši dokumente.")
        cols=st.columns(min(len(sugs),2))
        for i,s in enumerate(sugs):
            with cols[i%2]:
                if st.button(s,key=f"s_{i}",use_container_width=True): _ask(s); st.rerun()

    if prompt:=st.chat_input("Pitanje..."): _ask(prompt); st.rerun()


def _rebuild_index(user):
    try:
        st.session_state.vs=build_vs(st.session_state.docs,OPENAI_API_KEY)
        all_ev=[]
        for d in st.session_state.docs: all_ev.extend(extract_dates(d["text"],d["name"]))
        st.session_state.events=all_ev
        st.success(f"✅ Indeks ažuriran")
        log_action(user["id"],"upload",f"{len(st.session_state.docs)} dok")
    except Exception as e: st.error(f"{e}")

def _ask(q):
    st.session_state.chat.append({"role":"user","content":q})
    ans=query_ai(q,st.session_state.vs,OPENAI_API_KEY)
    st.session_state.chat.append({"role":"assistant","content":ans})
    log_action(st.session_state.current_user["id"],"query",q[:100])


# ─── TAB: PREVOD (+ kamera) ─────────────────────────

def tab_translate():
    user=st.session_state.current_user
    st.markdown('<div class="pk-card-gold"><h3>🔄 Prevod kompletnog dokumenta</h3><p style="color:#6B7280;margin:0">CEO tekst na srpski + pravna analiza + Word export.</p></div>',unsafe_allow_html=True)

    input_m = st.radio("Izvor:", ["📁 PDF/TXT fajl", "📸 Kamera"], horizontal=True, key="trans_input", label_visibility="collapsed")

    text = ""; filename = ""; lang = "sr"

    if input_m == "📁 PDF/TXT fajl":
        f = st.file_uploader("Fajl za prevod", type=["pdf","txt"], key="tr_upload")
        if f:
            text, filename, lang = process_file(f)

    elif input_m == "📸 Kamera":
        c1,c2 = st.columns(2)
        with c1: cam = st.camera_input("📸 Slikajte", key="tr_cam")
        with c2: pho = st.file_uploader("📤 Fotografija", type=["jpg","jpeg","png","webp"], key="tr_photo")
        img = cam or pho
        if img:
            if st.button("🔍 Izvuci tekst", key="tr_ocr_btn", use_container_width=True):
                with st.spinner("⏳ OCR..."):
                    text, lang = process_camera_image(img)
                    filename = f"Kamera_{datetime.now().strftime('%H%M%S')}"
                    if text.startswith("⚠️"):
                        st.error(text); text = ""

    if text and lang != "sr":
        st.info(f"📄 **{filename}** | Jezik: {LANG_NAMES.get(lang,'?')} | {len(text):,} karaktera")

        c1,c2 = st.columns(2)
        with c1: btn_t = st.button("🔄 Prevedi CEO tekst", use_container_width=True, type="primary", key="tr_go")
        with c2: btn_a = st.button("⚖️ Prevedi + analiza", use_container_width=True, key="tr_both")

        if btn_t or btn_a:
            with st.spinner("⏳ Prevodim... (1-3 min za duže)"): translated = translate_full(text, lang)
            st.markdown("### 🔄 Prevod"); st.markdown(translated)
            log_action(user["id"],"translate",f"{filename} ({lang}→sr)")

            analysis=""
            if btn_a:
                with st.spinner("⏳ Analiza..."):
                    llm=get_llm(tokens=4096)
                    analysis=llm.invoke([HumanMessage(content=f"Pravna analiza na srpskom:\n{translated[:6000]}")]).content
                st.markdown("### ⚖️ Analiza"); st.markdown(analysis)

            safe=re.sub(r'[^\w\-.]','_',filename.rsplit('.',1)[0] if '.' in filename else filename)
            word=create_word("Prevod",translated+("\n\n═══ ANALIZA ═══\n\n"+analysis if analysis else ""),filename,lang)
            st.download_button("📥 Word",data=word,file_name=f"Prevod_{safe}_{date.today()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True,type="primary")
    elif text and lang == "sr":
        st.info("ℹ️ Dokument je na srpskom. Prevod nije potreban.")


# ─── TAB: PODNESCI (novo) ────────────────────────────

def tab_documents():
    user=st.session_state.current_user
    st.markdown('<div class="pk-card-gold"><h3>📝 Generisanje pravnih podnesaka</h3><p style="color:#6B7280;margin:0">AI generiše nacrte žalbi, tužbi, zahteva na osnovu vaših informacija.</p></div>',unsafe_allow_html=True)

    st.markdown("#### Izaberite tip dokumenta:")
    cols = st.columns(3)
    for i, (key, tmpl) in enumerate(DOCUMENT_TEMPLATES.items()):
        with cols[i % 3]:
            st.markdown(f"""<div class="pk-card" style="text-align:center;cursor:pointer;">
                <div style="font-size:2rem">{tmpl['icon']}</div>
                <div style="font-weight:600;color:{NAVY};font-size:.9rem">{tmpl['name']}</div>
            </div>""", unsafe_allow_html=True)

    doc_type = st.selectbox("Tip podneska", list(DOCUMENT_TEMPLATES.keys()),
        format_func=lambda x: f"{DOCUMENT_TEMPLATES[x]['icon']} {DOCUMENT_TEMPLATES[x]['name']}",
        key="doc_type_select")

    st.markdown("---")
    st.markdown("#### Unesite informacije o slučaju:")

    case_info = st.text_area(
        "Opišite slučaj (što detaljnije to bolje)",
        height=200,
        placeholder="Primer:\nIme vlasnika: Petar Petrović\nAdresa imovine: ul. Cara Dušana 15, Peć/Pejë\n"
            "Katastarska parcela: 123/4, KO Peć\nŠta se desilo: Kuća zauzeta od strane trećeg lica 1999. godine.\n"
            "Posedujemo vlasnički list iz RGZ Srbije od 1985.\nŽelimo povraćaj imovine.",
        key="case_info"
    )

    # Kontekst iz učitanih dokumenata
    doc_context = ""
    if st.session_state.docs:
        st.info(f"📋 AI će koristiti i {len(st.session_state.docs)} učitanih dokument(a) za kontekst.")
        doc_context = "\n---\n".join([f"[{d['name']}]\n{d['text'][:2000]}" for d in st.session_state.docs[:3]])

    if st.button("📝 Generiši podnesak", use_container_width=True, type="primary",
                 disabled=not case_info, key="gen_doc"):
        with st.spinner("⏳ AI piše podnesak... (30-60 sekundi)"):
            result = generate_legal_document(doc_type, case_info, doc_context)

        st.markdown("---")
        st.markdown(f"### {DOCUMENT_TEMPLATES[doc_type]['icon']} {DOCUMENT_TEMPLATES[doc_type]['name']}")
        st.markdown(result)
        log_action(user["id"], "generate_doc", doc_type)

        # Sačuvaj u bazu
        try:
            with get_db() as conn:
                conn.execute("INSERT INTO generated_docs(user_id,doc_type,content)VALUES(?,?,?)",
                    (user["id"],doc_type,result[:50000]))
        except: pass

        # Export
        st.markdown("---")
        safe_type = DOCUMENT_TEMPLATES[doc_type]["name"].replace(" ","_")
        word = create_word(DOCUMENT_TEMPLATES[doc_type]["name"], result, "AI generisan", "sr")
        st.download_button("📥 Preuzmi Word", data=word,
            file_name=f"{safe_type}_{date.today()}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True, type="primary")

    # Istorija
    with st.expander("📋 Prethodno generisani podnesci"):
        try:
            with get_db() as conn:
                prev = conn.execute("SELECT doc_type,created_at FROM generated_docs WHERE user_id=? ORDER BY created_at DESC LIMIT 20",(user["id"],)).fetchall()
            if prev:
                for p in prev:
                    tmpl = DOCUMENT_TEMPLATES.get(p["doc_type"],{"name":"?","icon":"?"})
                    st.caption(f"{tmpl['icon']} {tmpl['name']} — {p['created_at'][:16]}")
            else: st.caption("Nema prethodnih.")
        except: st.caption("Greška.")


# ─── TAB: HRONOLOGIJA ────────────────────────────────

def tab_timeline():
    st.markdown('<div class="pk-card-gold"><h3>📅 Hronologija</h3></div>',unsafe_allow_html=True)
    events=st.session_state.events
    if not events: st.info("📁 Učitajte dokumente za hronologiju."); return
    c1,c2,c3=st.columns(3)
    with c1: st.metric("📅",len(events))
    with c2: st.metric("📄",len(set(e["source"] for e in events)))
    with c3:
        if len(events)>=2: st.metric("📏",f"{(events[-1]['date']-events[0]['date']).days}d")
    if events:
        dates=[e["date"] for e in events]
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=[min(dates),max(dates)],y=[0,0],mode='lines',line=dict(color='#E0E0E0',width=2),showlegend=False,hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=dates,y=[0]*len(dates),mode='markers',marker=dict(size=12,color=NAVY,line=dict(width=2,color=GOLD)),
            hovertemplate="<b>%{customdata[0]}</b><br>📄%{customdata[1]}<extra></extra>",
            customdata=[(e["date_str"],e["source"]) for e in events],showlegend=False))
        fig.update_layout(plot_bgcolor='white',paper_bgcolor='white',yaxis=dict(visible=False,range=[-1,1]),height=280,margin=dict(l=20,r=20,t=10,b=20))
        st.plotly_chart(fig,use_container_width=True)
    for e in events:
        st.markdown(f'<div class="tl-event"><div class="tl-date">📅 {e["date_str"]}</div><div style="margin:6px 0;font-size:.88rem">{e["context"]}</div><div class="tl-src">📄 {e["source"]}</div></div>',unsafe_allow_html=True)


# ─── TAB: PRAVO (KiM + sudska praksa) ────────────────

def tab_legal_knowledge():
    user=st.session_state.current_user
    st.markdown('<div class="pk-card-gold"><h3>📚 KiM pravni okvir + Sudska praksa</h3></div>',unsafe_allow_html=True)

    sub1,sub2 = st.tabs(["🏛️ Pravni okvir","⚖️ Sudska praksa"])

    with sub1:
        topics={"🇺🇳 Rezolucija 1244":["Na snazi","Suverenitet Srbije","UNMIK"],
            "📜 UNMIK uredbe":["REG/1999/24","REG/2000/60","REG/2002/13"],
            "🏠 Imovina":["Privatna/društvena","AKK vs RGZ","Uzurpacija, IRL"],
            "🇪🇺 Sporazumi":["Briselski 2013","Ohridski 2023","ZSO neimplementirana"]}
        for n,pts in topics.items():
            with st.expander(n):
                for p in pts: st.markdown(f"- {p}")

    with sub2:
        st.markdown("### ⚖️ Baza sudske prakse")
        cases={
            "KPCC — Imovinski zahtevi":{
                "items":[
                    ("KPCC/D/R/100/2012","Princip restitucije — nezakonito zauzimanje ne stvara pravo"),
                    ("KPCC/D/A/128/2013","Stanarsko pravo zaštićeno, otkup moguć"),
                    ("KPCC/D/C/205/2014","Transakcije pod prinudom (1989-99) ništave"),
                ]
            },
            "ESLJP — Evropski sud":{
                "items":[
                    ("Behrami v. Francuska (2007)","ESLJP nema nadležnost nad UNMIK/KFOR"),
                    ("Grudić v. Srbija (2012)","Srbija mora isplaćivati penzije Srbima na KiM"),
                    ("Loizidou v. Turska (1996)","Efektivna kontrola = odgovornost za imovinu"),
                ]
            },
            "MSP — Savetodavno mišljenje (2010)":{
                "items":[
                    ("ICJ Advisory Opinion","Deklaracija ne krši međunarodno pravo"),
                    ("ALI:","Ne bavi se pravom na secesiju niti statusom Rez. 1244"),
                ]
            },
            "Srpski sudovi":{
                "items":[
                    ("VKS Rev 1234/2018","RGZ jedini legitimni katastar"),
                    ("Ustavni sud IUz-353/2009","Ustav KS jednostrani akt"),
                ]
            }
        }
        for cat,data in cases.items():
            with st.expander(f"📂 {cat}"):
                for ref,desc in data["items"]:
                    st.markdown(f"**{ref}**\n{desc}")

    st.markdown("---\n### 🤖 Pitajte AI o pravu")
    q=st.text_input("Pitanje",key="law_q")
    if st.button("📤 Pitaj",disabled=not q,key="law_btn"):
        with st.spinner("⏳"):
            llm=get_llm()
            p=f"Ekspert za KiM pravo. Srpski. Koristi i sudsku praksu.\n{KIM_KNOWLEDGE}\n{CASE_LAW_DB}\nPITANJE:{q}\nODGOVOR:"
            try:
                r=llm.invoke([HumanMessage(content=p)]); st.markdown(r.content)
                log_action(user["id"],"law_query",q[:100])
            except Exception as e: st.error(f"{e}")


# ─── TAB: PRAVNI MOST ────────────────────────────────

def tab_bridge():
    user=st.session_state.current_user
    st.markdown('<div class="pk-card-gold"><h3>🌉 Pravni most — AL→SR</h3><p style="color:#6B7280;margin:0">Nalepite tekst → prevod + terminologija.</p></div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        al=st.text_area("🇦🇱 Albanski",height=300,placeholder="Vendim...",label_visibility="collapsed",key="br_in")
        btn=st.button("🔄 Prevedi",use_container_width=True,disabled=not al,key="br_go")
    with c2:
        st.markdown("#### 🇷🇸 Srpski")
        if btn and al:
            with st.spinner("⏳"): translated=translate_full(al,"al")
            st.markdown(translated); log_action(user["id"],"bridge",f"{len(al)}ch")
            found=[(a,s) for a,s in LEGAL_DICT.items() if a.lower() in al.lower()]
            if found:
                st.markdown("---\n#### 📖 Termini")
                for a,s in found: st.markdown(f"- **{a}** → {s}")
            word=create_word("Prevod",translated,"Ručni unos","al")
            st.download_button("📥 Word",data=word,file_name=f"Most_{date.today()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
    with st.expander("📚 Rečnik"):
        q=st.text_input("Pretraži",key="d_q")
        items=[(a,s) for a,s in LEGAL_DICT.items() if not q or q.lower() in a.lower() or q.lower() in s.lower()]
        for a,s in items[:30]: st.markdown(f"🔹 **{a}** → {s}")


# ─── TAB: DELJENJE (samo Kancelarija+) ───────────────

def tab_sharing():
    user=st.session_state.current_user
    st.markdown('<div class="pk-card-gold"><h3>🤝 Deljenje slučajeva</h3><p style="color:#6B7280;margin:0">Podelite dokumente i analize sa kolegama.</p></div>',unsafe_allow_html=True)

    # Kreiraj nov slučaj
    with st.expander("➕ Novi slučaj"):
        with st.form("new_case"):
            title=st.text_input("Naziv slučaja *",placeholder="Npr: Imovina Petrović - Peć")
            desc=st.text_area("Opis",placeholder="Kratak opis predmeta...",height=100)
            if st.form_submit_button("✅ Kreiraj"):
                if not title: st.error("Unesite naziv.")
                else:
                    try:
                        with get_db() as conn:
                            conn.execute("INSERT INTO cases(owner_id,title,description)VALUES(?,?,?)",(user["id"],title,desc))
                        st.success(f"✅ Slučaj '{title}' kreiran"); st.rerun()
                    except Exception as e: st.error(f"{e}")

    # Moji slučajevi
    st.markdown("### 📂 Moji slučajevi")
    try:
        with get_db() as conn:
            my_cases=conn.execute("SELECT * FROM cases WHERE owner_id=? ORDER BY updated_at DESC",(user["id"],)).fetchall()
    except: my_cases=[]

    if not my_cases:
        st.info("Nemate slučajeva. Kliknite ➕ da kreirate prvi.")

    for case in my_cases:
        case=dict(case)
        with st.expander(f"📂 {case['title']} — {case['created_at'][:10]}"):
            st.markdown(f"*{case.get('description','Nema opisa')}*")

            # Dodaj dokument u slučaj
            doc_file=st.file_uploader(f"Dodaj dokument u '{case['title']}'",type=["pdf","txt"],key=f"case_doc_{case['id']}")
            if doc_file:
                text,name,lang=process_file(doc_file)
                if text:
                    with get_db() as conn:
                        conn.execute("INSERT INTO case_documents(case_id,filename,text_content,language)VALUES(?,?,?,?)",
                            (case["id"],name,text[:50000],lang))
                    st.success(f"✅ {name} dodat")

            # Lista dokumenata
            try:
                with get_db() as conn:
                    case_docs=conn.execute("SELECT filename,language,created_at FROM case_documents WHERE case_id=?",(case["id"],)).fetchall()
                if case_docs:
                    st.markdown("**Dokumenti:**")
                    for cd in case_docs:
                        em={"sr":"🇷🇸","al":"🇦🇱","en":"🇬🇧"}.get(cd["language"],"🏳️")
                        st.caption(f"{em} {cd['filename']} — {cd['created_at'][:10]}")
            except: pass

            # Deljenje
            st.markdown("**Podeli sa kolegom:**")
            share_email=st.text_input("Email kolege",key=f"share_email_{case['id']}",placeholder="kolega@advokat.rs")
            if st.button("🤝 Podeli",key=f"share_btn_{case['id']}"):
                if share_email:
                    try:
                        with get_db() as conn:
                            conn.execute("INSERT INTO case_shares(case_id,shared_with_email,permission)VALUES(?,?,?)",
                                (case["id"],share_email.lower().strip(),"read"))
                        st.success(f"✅ Podeljeno sa {share_email}")
                        log_action(user["id"],"share_case",f"{case['title']} → {share_email}")
                    except: st.error("Greška.")

            # Ko ima pristup
            try:
                with get_db() as conn:
                    shares=conn.execute("SELECT shared_with_email FROM case_shares WHERE case_id=?",(case["id"],)).fetchall()
                if shares:
                    st.markdown("**Deljeno sa:**")
                    for s in shares: st.caption(f"👤 {s['shared_with_email']}")
            except: pass

    # Slučajevi podeljeni SA MNOM
    st.markdown("### 📨 Podeljeno sa mnom")
    try:
        with get_db() as conn:
            shared_with_me=conn.execute(
                "SELECT c.title,c.description,c.created_at,u.full_name as owner_name "
                "FROM case_shares cs JOIN cases c ON cs.case_id=c.id "
                "JOIN users u ON c.owner_id=u.id "
                "WHERE cs.shared_with_email=? ORDER BY c.updated_at DESC",
                (user["email"],)
            ).fetchall()
        if shared_with_me:
            for s in shared_with_me:
                with st.expander(f"📨 {s['title']} (od {s['owner_name']})"):
                    st.markdown(f"*{s.get('description','Nema opisa')}*")
                    st.caption(f"Kreirano: {s['created_at'][:10]}")
        else:
            st.info("Niko vam nije podelio slučaj.")
    except: st.info("Nema podeljenih slučajeva.")


# ═══════════════════════════════════════════════════════════════
#  15. MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS,unsafe_allow_html=True)
    st.components.v1.html('<script>if(!document.querySelector(\'link[rel="manifest"]\')){var l=document.createElement("link");l.rel="manifest";l.href="/app/static/manifest.json";document.head.appendChild(l)}if("serviceWorker" in navigator){navigator.serviceWorker.register("/app/static/sw.js").catch(()=>{})}</script>',height=0)

    init_database(); run_auto_suspension()

    if not st.session_state.logged_in: render_login(); return
    user=st.session_state.current_user
    if not user: st.session_state.logged_in=False; st.rerun(); return
    try:
        with get_db() as conn:
            fresh=conn.execute("SELECT * FROM users WHERE id=?",(user["id"],)).fetchone()
            if fresh: st.session_state.current_user=dict(fresh)
            else: do_logout(); st.rerun(); return
    except: pass
    if st.session_state.current_user["role"]=="admin": render_admin()
    else: render_user()

if __name__=="__main__": main()
