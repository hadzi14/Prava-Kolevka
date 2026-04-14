"""
═══════════════════════════════════════════════════════════════
UI KOMPONENTE — Prava Kolevka
Izdvojene UI funkcije iz app.py
═══════════════════════════════════════════════════════════════
"""
import streamlit as st
from datetime import datetime


def render_footer():
    """Prikaz footer-a aplikacije"""
    st.markdown("""
    <div style='text-align: center; margin-top: 3rem; padding: 1rem; 
                border-top: 1px solid #ddd; color: #666; font-size: 0.85rem;'>
        <p><strong>Prava Kolevka v6.2</strong> | Pravni AI za Kosovo ⚖️</p>
        <p>Razvijeno uz podršku modernih AI tehnologija</p>
    </div>
    """, unsafe_allow_html=True)


def render_sources_html(results):
    """HTML prikaz izvora/pravnih članova"""
    if not results:
        return "<p>Nema dostupnih izvora.</p>"
    
    html = "<div class='sources-container' style='margin-top: 1.5rem;'>"
    html += "<h4 style='color: #2c3e50; margin-bottom: 1rem;'>📚 Pravni izvori:</h4>"
    
    for i, res in enumerate(results, 1):
        law_name = res.get('law_name', 'Nepoznat zakon')
        article_num = res.get('article_number', '')
        score = res.get('score', 0)
        text_snippet = res.get('text', '')[:200]
        
        html += f"""
        <div style='background: #f8f9fa; border-left: 4px solid #3498db; 
                    padding: 0.75rem; margin-bottom: 0.75rem; border-radius: 4px;'>
            <strong>Izvor {i}:</strong> {law_name}
            {f' - Član {article_num}' if article_num else ''}
            <div style='font-size: 0.85rem; color: #666; margin-top: 0.5rem;'>
                {text_snippet}...
            </div>
            <div style='font-size: 0.75rem; color: #999; margin-top: 0.25rem;'>
                Relevance score: {score:.2f}
            </div>
        </div>
        """
    
    html += "</div>"
    return html


def render_login():
    """Login interfejs"""
    st.markdown("""
    <div style='text-align: center; padding: 2rem;'>
        <h1 style='color: #2c3e50;'>⚖️ Prava Kolevka</h1>
        <p style='color: #7f8c8d; font-size: 1.1rem;'>Pravni AI asistent za Kosovo</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("Email adresa", placeholder="korisnik@primer.com")
            password = st.password_input("Lozinka", placeholder="••••••••")
            submit = st.form_submit_button("Uloguj se", use_container_width=True)
            
            if submit:
                from supabase_db import sb_get_user_by_email
                from app import authenticate_user, init_ss
                
                user = sb_get_user_by_email(email)
                if user and authenticate_user(email, password):
                    init_ss()
                    st.session_state.user = user
                    st.session_state.authenticated = True
                    st.session_state.login_time = datetime.now()
                    st.rerun()
                else:
                    st.error("Neispravan email ili lozinka.")
        
        st.markdown("---")
        st.info("🔐 Sigurna platforma za pravne profesionalce")


def render_admin():
    """Admin panel interfejs"""
    st.title("🛡️ Admin Panel")
    
    menu = st.sidebar.selectbox(
        "Navigacija",
        ["Dashboard", "Zakoni", "Korisnici", "Plaćanja", "Podešavanja"]
    )
    
    if menu == "Dashboard":
        from app import admin_dashboard
        admin_dashboard()
    elif menu == "Zakoni":
        from app import admin_laws
        admin_laws()
    elif menu == "Korisnici":
        from app import admin_users
        admin_users()
    elif menu == "Plaćanja":
        from app import admin_payments
        admin_payments()
    elif menu == "Podešavanja":
        from app import admin_settings
        admin_settings()


def render_user():
    """Korisnički interfejs sa tabovima"""
    user = st.session_state.get('user')
    if not user:
        st.warning("Niste ulogovani.")
        return
    
    st.markdown(f"""
    <div style='display: flex; justify-content: space-between; align-items: center; 
                padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 8px; color: white; margin-bottom: 2rem;'>
        <div>
            <h2 style='margin: 0;'>Dobrodošli, {user.get('full_name', 'Korisnik')}!</h2>
            <p style='margin: 0.5rem 0 0; opacity: 0.9; font-size: 0.9rem;'>
                {user.get('email', '')} | {user.get('role', 'korisnik')}
            </p>
        </div>
        <div style='text-align: right;'>
            <p style='margin: 0; font-size: 0.85rem; opacity: 0.8;'>
                Pretplata: <strong>{user.get('subscription_status', 'free').upper()}</strong>
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Tabovi
    tabs = st.tabs([
        "📁 Moji predmeti",
        "🔍 Pretraga zakona", 
        "🌐 Prevodilac",
        "📝 Podnesci",
        "🏛️ Sudska nadležnost",
        "💳 Pretplata"
    ])
    
    with tabs[0]:
        from app import tab_cases
        tab_cases()
    
    with tabs[1]:
        from app import tab_search
        tab_search()
    
    with tabs[2]:
        from app import tab_translate
        tab_translate()
    
    with tabs[3]:
        from app import tab_submissions
        # Potrebno je proslediti case_id i user - ovo će biti rešeno u app.py
        st.info("Odaberite predmet za kreiranje podnesaka")
    
    with tabs[4]:
        from app import tab_bridge
        tab_bridge()
    
    with tabs[5]:
        from app import tab_subscription
        tab_subscription()


# ============================================================================
# TAB FUNKCIJE - Izdvajamo ih u poseban fajl kasnije
# ============================================================================

def tab_cases():
    """Tab: Moji predmeti"""
    st.header("📁 Moji predmeti")
    
    # Uvozimo funkcije iz app.py dok ne prebacimo svu logiku
    from app import create_case, get_user_cases, delete_case
    
    user = st.session_state.get('user')
    if not user:
        st.warning("Morate biti ulogovani.")
        return
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_case_title = st.text_input("Naziv novog predmeta", placeholder="npr. Parnica br. 123/2024")
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button("➕ Kreiraj predmet", use_container_width=True):
            if new_case_title.strip():
                create_case(user['id'], new_case_title.strip())
                st.success("Predmet kreiran!")
                st.rerun()
    
    cases = get_user_cases(user['id'])
    if not cases:
        st.info("Nemate kreiranih predmeta.")
    else:
        for case in cases:
            with st.expander(f"📂 {case['title']} (ID: {case['id'][:8]}...)"):
                st.write(f"**Kreiran:** {case['created_at']}")
                st.write(f"**Status:** {case.get('status', 'Aktivan')}")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("Otvori", key=f"open_{case['id']}"):
                        st.session_state.current_case = case
                with col_b:
                    if st.button("Obriši", key=f"del_{case['id']}", type="secondary"):
                        delete_case(case['id'], user['id'])
                        st.rerun()
                with col_c:
                    st.write("")


def tab_search():
    """Tab: Pretraga zakona"""
    st.header("🔍 Pretraga zakona i članova")
    
    query = st.text_input("Unesite pojam za pretragu", 
                         placeholder="npr. naknada štete, radni odnos, zakup...")
    
    if query:
        from app import search_laws, format_results
        
        with st.spinner("Pretražujem bazu zakona..."):
            results = search_laws(query, max_results=10)
        
        if results:
            st.success(f"Pronađeno {len(results)} rezultata")
            st.markdown(format_results(results), unsafe_allow_html=True)
        else:
            st.warning("Nema pronađenih rezultata.")


def tab_translate():
    """Tab: Prevodilac"""
    st.header("🌐 Prevodilac (SR ↔ AL)")
    
    col1, col2 = st.columns(2)
    with col1:
        source_text = st.text_area("Tekst za prevod", height=200, 
                                  placeholder="Unesite tekst na srpskom ili albanskom...")
        lang = st.selectbox("Jezik izvornog teksta", ["srpski", "albanski"])
    
    with col2:
        st.write("**Prevod:**")
        if source_text and st.button("Prevedi"):
            from app import translate_full
            target_lang = "al" if lang == "srpski" else "sr"
            with st.spinner("Prevodim..."):
                translation = translate_full(source_text, target_lang)
                st.text_area("", value=translation, height=200)


def tab_submissions(case_id=None, user=None):
    """Tab: Podnesci"""
    if not case_id:
        # Ako nije odabran predmet, prikaži listu
        st.subheader("Odaberite predmet za kreiranje podneska")
        from app import get_user_cases
        user = st.session_state.get('user')
        cases = get_user_cases(user['id']) if user else []
        
        if cases:
            case_options = {f"{c['title']}": c['id'] for c in cases}
            selected = st.selectbox("Predmet", list(case_options.keys()))
            if st.button("Odaberi"):
                st.session_state.current_case = next(c for c in cases if c['id'] == case_options[selected])
                st.rerun()
        return
    
    st.header("📝 Kreiranje podneska")
    st.info(f"Predmet: {case_id}")
    # Logika za kreiranje podneska ostaje u app.py


def tab_bridge():
    """Tab: Sudska nadležnost"""
    st.header("🏛️ Određivanje sudske nadležnosti")
    
    case_desc = st.text_area("Opis slučaja", 
                            placeholder="Opišite slučaj da bismo odredili nadležni sud...",
                            height=150)
    
    submission_type = st.selectbox("Vrsta podneska", 
                                  ["Tužba", "Zahtev", "Molba", "Žalba", "Drugo"])
    
    if st.button("Utvrди nadležnost"):
        from app import detect_court
        if case_desc.strip():
            with st.spinner("Analiziram..."):
                court = detect_court(case_desc, submission_type)
                st.success(f"Nadležni sud: **{court}**")
        else:
            st.warning("Unesite opis slučaja.")


def tab_subscription():
    """Tab: Pretplata"""
    st.header("💳 Upravljajte pretplatom")
    
    user = st.session_state.get('user')
    if not user:
        return
    
    current_plan = user.get('subscription_status', 'free')
    st.write(f"Trenutni plan: **{current_plan.upper()}**")
    
    st.markdown("""
    ### Dostupni planovi:
    - **Free**: Osnovne funkcije
    - **Basic**: Napredna pretraga, 50 upita/mesečno
    - **Pro**: Neograničeni upiti, AI podnesci, prioritetna podrška
    """)
    
    if current_plan == 'free':
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Nadogradi na Basic", use_container_width=True):
                from app import create_stripe_checkout
                create_stripe_checkout('basic', user['email'])
        with col2:
            if st.button("Nadogradi na Pro", use_container_width=True):
                from app import create_stripe_checkout
                create_stripe_checkout('pro', user['email'])
