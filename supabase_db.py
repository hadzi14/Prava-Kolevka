"""
Supabase helper za Prava Kolevka.
"""
import re
import os
import streamlit as st
from supabase import create_client
def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)
_client = None
def get_sb():
    global _client
    if _client is None:
        url = get_secret("SUPABASE_URL")
        key = get_secret("SUPABASE_KEY")
        if not url or not key:
            raise Exception(
                "SUPABASE_URL ili SUPABASE_KEY nisu podešeni.")
        _client = create_client(url, key)
    return _client
# ═══ LAWS ═══
def sb_insert_law(data):
    """Insert zakon. data je dict sa poljima. Vraca unet red."""
    sb = get_sb()
    r = sb.table("laws").insert(data).execute()
    return r.data[0] if r.data else None
def sb_get_law(law_id):
    """Vraca zakon po ID-u."""
    sb = get_sb()
    r = sb.table("laws").select("*").eq("id", law_id).execute()
    return r.data[0] if r.data else None
def sb_get_all_laws(active_only=True):
    """Vraca sve zakone."""
    sb = get_sb()
    q = sb.table("laws").select("*")
    if active_only:
        q = q.eq("is_active", True)
    r = q.order("hierarchy_level").order("name_sr").execute()
    return r.data or []
def sb_update_law(law_id, data):
    """Azurira zakon."""
    sb = get_sb()
    r = sb.table("laws").update(data).eq("id", law_id).execute()
    return r.data[0] if r.data else None
def sb_delete_law(law_id):
    """Brise zakon i clanke (CASCADE)."""
    sb = get_sb()
    sb.table("laws").delete().eq("id", law_id).execute()
# ═══ LAW ARTICLES ═══
def sb_insert_article(data):
    """Insert clanak. data je dict."""
    sb = get_sb()
    r = sb.table("law_articles").insert(data).execute()
    return r.data[0] if r.data else None
def sb_insert_articles_bulk(articles):
    """Insert vise clanova odjednom."""
    if not articles:
        return []
    sb = get_sb()
    r = sb.table("law_articles").insert(articles).execute()
    return r.data or []
def sb_get_articles(law_id):
    """Vraca clanke zakona po law_id."""
    sb = get_sb()
    r = (sb.table("law_articles")
         .select("*")
         .eq("law_id", law_id)
         .order("order_index")
         .execute())
    return r.data or []
def sb_delete_articles(law_id):
    """Brise sve clanke zakona."""
    sb = get_sb()
    sb.table("law_articles").delete().eq("law_id", law_id).execute()
def sb_count_articles():
    """Vraca ukupan broj clanova."""
    sb = get_sb()
    r = sb.table("law_articles").select("id", count="exact").execute()
    return r.count or 0
# ═══ KOMBINOVANO ═══
def sb_save_law_with_articles(law_data, articles):
    """Sacuvaj zakon + sve clanke. Vraca (law_id, broj_clanova)."""
    law = sb_insert_law(law_data)
    if not law:
        return None, 0
    law_id = law["id"]
    bulk = []
    for i, art in enumerate(articles):
        bulk.append({
            "law_id": law_id,
            "article_number": art.get("article_number", "0"),
            "title": art.get("title", ""),
            "content": art.get("content", ""),
            "order_index": i,
        })
    if bulk:
        sb_insert_articles_bulk(bulk)
    return law_id, len(bulk)
def sb_get_law_with_articles(law_id):
    """Vraca zakon sa clancima."""
    law = sb_get_law(law_id)
    if not law:
        return None, []
    arts = sb_get_articles(law_id)
    return law, arts
def sb_get_laws_summary():
    """Vraca listu zakona sa brojem clanova."""
    sb = get_sb()
    laws = sb_get_all_laws(active_only=True)
    result = []
    for law in laws:
        arts = (sb.table("law_articles")
                .select("id", count="exact")
                .eq("law_id", law["id"])
                .execute())
        law["num_articles"] = arts.count or 0
        result.append(law)
    return result
def sb_search_articles(keyword):
    """Pretrazuje clanke po kljucnoj reci u content ili title."""
    sb = get_sb()
    r = (sb.table("law_articles")
         .select("id, law_id, article_number, title, content, order_index")
         .or_(f"content.ilike.%{keyword}%,title.ilike.%{keyword}%")
         .limit(20)
         .execute())
    return r.data or []
def sb_search_articles_by_number(art_num):
    """Pretrazuje clanke po broju clana."""
    sb = get_sb()
    r = (sb.table("law_articles")
         .select("id, law_id, article_number, title, content, order_index")
         .eq("article_number", art_num)
         .limit(20)
         .execute())
    return r.data or []
def sb_get_law_basic(law_id):
    """Vraca osnovne podatke zakona."""
    sb = get_sb()
    r = (sb.table("laws")
         .select("id, name_sr, short_name, law_number, area, hierarchy_level, gazette_info")
         .eq("id", law_id)
         .execute())
    if not r.data:
        return None
    law = r.data[0]
    law.setdefault("name_al", "")
    law.setdefault("short_name", "")
    return law
def sb_get_all_articles_with_laws():
    """Vraca sve clanke sa podacima zakona za vector store."""
    sb = get_sb()
    laws = (sb.table("laws")
            .select("id, name_sr, short_name, law_number, area, hierarchy_level")
            .eq("is_active", True)
            .execute()
            .data or [])
    if not laws:
        return []
    law_map = {l["id"]: l for l in laws}
    law_ids = list(law_map.keys())
    arts = (sb.table("law_articles")
            .select("law_id, article_number, title, content")
            .in_("law_id", law_ids)
            .order("order_index")
            .execute()
            .data or [])
    all_rows = []
    for art in arts:
        lid = art["law_id"]
        if lid not in law_map:
            continue
        law = law_map[lid]
        all_rows.append({
            "law_id": lid,
            "article_number": art["article_number"],
            "title": art.get("title", ""),
            "content": art.get("content", ""),
            "name_sr": law["name_sr"],
            "short_name": law.get("short_name", ""),
            "law_number": law.get("law_number", ""),
            "area": law.get("area", ""),
            "hierarchy_level": law.get("hierarchy_level", 3),
        })
    return all_rows
def sb_find_laws_by_name(name):
    """Trazi zakone po nazivu."""
    sb = get_sb()
    r = (sb.table("laws")
         .select("id, name_sr, short_name, law_number, area, hierarchy_level")
         .eq("is_active", True)
         .ilike("name_sr", f"%{name}%")
         .execute())
    return r.data or []
def sb_test_connection():
    """Testira konekciju i vraca status."""
    try:
        sb = get_sb()
        laws = (sb.table("laws")
                .select("id, name_sr", count="exact")
                .eq("is_active", True)
                .execute())
        arts = sb.table("law_articles").select("id", count="exact").execute()
        result = {
            "connected": True,
            "laws_count": laws.count or 0,
            "articles_count": arts.count or 0,
            "laws": [
                f"{l['id']}: {l['name_sr']}"
                for l in (laws.data or [])[:5]
            ],
        }
        test_art = (sb.table("law_articles")
                    .select("article_number, title, content")
                    .eq("law_id", 3)
                    .eq("article_number", "1")
                    .execute())
        if test_art.data:
            a = test_art.data[0]
            result["test_article"] = (
                f"Cl. {a['article_number']}: {a['content'][:100]}...")
        else:
            result["test_article"] = "Cl. 1 za law_id=3 nije pronadjen"
        return result
    except Exception as e:
        return {"connected": False, "error": str(e)}
def sb_search_articles_multi(keywords, law_ids=None):
    """Pretrazuje clanke po vise kljucnih reci."""
    if not keywords:
        return []
    sb = get_sb()
    or_parts = []
    for kw in keywords[:8]:
        kw_safe = kw.replace("%", "").replace("'", "")
        if kw_safe:
            or_parts.append(f"content.ilike.%{kw_safe}%")
            or_parts.append(f"title.ilike.%{kw_safe}%")
    if not or_parts:
        return []
    q = sb.table("law_articles").select(
        "id, law_id, article_number, title, content, order_index")
    if law_ids:
        q = q.in_("law_id", law_ids)
    r = q.or_(",".join(or_parts)).limit(50).execute()
    results = []
    for art in (r.data or []):
        content_l = (art.get("content", "") or "").lower()
        title_l = (art.get("title", "") or "").lower()
        mc = sum(
            1 for kw in keywords
            if kw.lower() in content_l or kw.lower() in title_l)
        art["_match_count"] = mc
        art["_matched_kw"] = [
            kw for kw in keywords
            if kw.lower() in content_l or kw.lower() in title_l]
        results.append(art)
    return results
def sb_get_first_articles(law_id, limit=5):
    """Vraca prvih N clanova zakona."""
    sb = get_sb()
    r = (sb.table("law_articles")
         .select("id, law_id, article_number, title, content, order_index")
         .eq("law_id", law_id)
         .order("order_index")
         .limit(limit)
         .execute())
    return r.data or []
def sb_get_law_ids_by_area(area):
    """Vraca ID-jeve zakona iz odredjene oblasti."""
    sb = get_sb()
    r = (sb.table("laws")
         .select("id")
         .eq("is_active", True)
         .eq("area", area)
         .execute())
    return [l["id"] for l in (r.data or [])]
def sb_find_parent_law(title_hint):
    """Trazi mogucni osnovni zakon po nazivu."""
    if not title_hint:
        return []
    sb = get_sb()
    hint = title_hint.strip()
    lowered = hint.lower()
    replacements = [
        "zakon o izmenama i dopunama",
        "izmene i dopune zakona",
        "na osnovu",
        "u skladu sa",
        "administrativno uputstvo o",
        "pravilnik o",
    ]
    for phrase in replacements:
        lowered = lowered.replace(phrase, "")
    cleaned_hint = lowered.strip()
    search_value = cleaned_hint if len(cleaned_hint) >= 3 else hint
    r = (sb.table("laws")
         .select("id, name_sr, short_name, law_number, area")
         .eq("is_active", True)
         .eq("document_type", "law")
         .ilike("name_sr", f"%{search_value}%")
         .limit(10)
         .execute())
    return r.data or []
# ═══════════════════════════════════════════════
#  USERS
# ═══════════════════════════════════════════════
def sb_get_user_by_email(email):
    try:
        sb = get_sb()
        r = (sb.table("users")
             .select("*")
             .eq("email", email.lower().strip())
             .execute())
        if r.data:
            return r.data[0]
        return None
    except Exception:
        return None
def sb_create_user(user_data):
    try:
        sb = get_sb()
        r = sb.table("users").insert(user_data).execute()
        if r.data:
            return r.data[0]["id"]
        return None
    except Exception:
        return None
def sb_update_user(user_id, updates):
    try:
        sb = get_sb()
        sb.table("users").update(updates).eq("id", user_id).execute()
        return True
    except Exception:
        return False
def sb_get_all_users():
    try:
        sb = get_sb()
        r = (sb.table("users")
             .select("*")
             .eq("role", "user")
             .order("full_name")
             .execute())
        return r.data or []
    except Exception:
        return []
# ═══════════════════════════════════════════════
#  CASES
# ═══════════════════════════════════════════════
def sb_create_case(owner_id, title):
    try:
        sb = get_sb()
        r = (sb.table("cases")
             .insert({"owner_id": owner_id, "title": title})
             .execute())
        if r.data:
            return r.data[0]["id"]
        return None
    except Exception:
        return None
def sb_get_user_cases(owner_id):
    try:
        sb = get_sb()
        r = (sb.table("cases")
             .select("*")
             .eq("owner_id", owner_id)
             .order("created_at", desc=True)
             .execute())
        return r.data or []
    except Exception:
        return []
def sb_delete_case(case_id, owner_id):
    try:
        sb = get_sb()
        sb.table("case_messages").delete().eq("case_id", case_id).execute()
        sb.table("case_documents").delete().eq("case_id", case_id).execute()
        sb.table("case_submissions").delete().eq("case_id", case_id).execute()
        (sb.table("cases")
         .delete()
         .eq("id", case_id)
         .eq("owner_id", owner_id)
         .execute())
        return True
    except Exception:
        return False
# ═══════════════════════════════════════════════
#  CASE MESSAGES
# ═══════════════════════════════════════════════
def sb_get_case_messages(case_id):
    try:
        sb = get_sb()
        r = (sb.table("case_messages")
             .select("*")
             .eq("case_id", case_id)
             .order("created_at")
             .execute())
        return r.data or []
    except Exception:
        return []
def sb_save_case_message(case_id, role, content,
                         sources_html="", confidence=""):
    try:
        sb = get_sb()
        sb.table("case_messages").insert({
            "case_id": case_id,
            "role": role,
            "content": content,
            "sources_html": sources_html,
            "confidence": confidence,
        }).execute()
        return True
    except Exception:
        return False
# ═══════════════════════════════════════════════
#  CASE DOCUMENTS
# ═══════════════════════════════════════════════
def sb_add_case_document(case_id, filename, text_content, language="sr"):
    try:
        sb = get_sb()
        r = sb.table("case_documents").insert({
            "case_id": case_id,
            "filename": filename,
            "text_content": text_content,
            "language": language,
        }).execute()
        if r.data:
            return r.data[0]["id"]
        return None
    except Exception:
        return None
def sb_get_case_documents(case_id):
    try:
        sb = get_sb()
        r = (sb.table("case_documents")
             .select("id, case_id, filename, language, created_at")
             .eq("case_id", case_id)
             .order("created_at")
             .execute())
        return r.data or []
    except Exception:
        return []
def sb_get_document_text(doc_id):
    try:
        sb = get_sb()
        r = (sb.table("case_documents")
             .select("text_content")
             .eq("id", doc_id)
             .execute())
        if r.data:
            return r.data[0]["text_content"]
        return ""
    except Exception:
        return ""
def sb_delete_case_document(doc_id, case_id):
    try:
        sb = get_sb()
        (sb.table("case_documents")
         .delete()
         .eq("id", doc_id)
         .eq("case_id", case_id)
         .execute())
        return True
    except Exception:
        return False
# ═══════════════════════════════════════════════
#  CASE SUBMISSIONS
# ═══════════════════════════════════════════════
def sb_save_submission(case_id, user_id, submission_type,
                       court_name, case_number, content):
    try:
        sb = get_sb()
        r = sb.table("case_submissions").insert({
            "case_id": case_id,
            "user_id": user_id,
            "submission_type": submission_type,
            "court_name": court_name,
            "case_number": case_number,
            "content": content,
            "status": "draft",
        }).execute()
        if r.data:
            return r.data[0]["id"]
        return None
    except Exception:
        return None
def sb_get_case_submissions(case_id):
    try:
        sb = get_sb()
        r = (sb.table("case_submissions")
             .select("*")
             .eq("case_id", case_id)
             .order("created_at", desc=True)
             .execute())
        return r.data or []
    except Exception:
        return []
def sb_delete_submission(sub_id, user_id):
    try:
        sb = get_sb()
        (sb.table("case_submissions")
         .delete()
         .eq("id", sub_id)
         .eq("user_id", user_id)
         .execute())
        return True
    except Exception:
        return False
# ═══════════════════════════════════════════════
#  PAYMENTS + LOGS
# ═══════════════════════════════════════════════
def sb_save_payment(user_id, amount, payment_date,
                    period_start, period_end, method, recorded_by):
    try:
        sb = get_sb()
        sb.table("payments").insert({
            "user_id": user_id,
            "amount": amount,
            "payment_date": payment_date,
            "period_start": period_start,
            "period_end": period_end,
            "method": method,
            "recorded_by": recorded_by,
            "status": "completed",
        }).execute()
        return True
    except Exception:
        return False
def sb_get_payments(month_start=None):
    try:
        sb = get_sb()
        q = sb.table("payments").select("*").eq("status", "completed")
        if month_start:
            q = q.gte("payment_date", month_start)
        r = q.execute()
        return r.data or []
    except Exception:
        return []
def sb_log_action(user_id, action, details=""):
    try:
        sb = get_sb()
        safe = re.sub(
            r'[a-zA-Z0-9._%+-]+@[^\s]+',
            '[EMAIL]',
            (details or "")[:80])
        sb.table("usage_logs").insert({
            "user_id": user_id,
            "action": action,
            "details": safe,
        }).execute()
        return True
    except Exception:
        return False
