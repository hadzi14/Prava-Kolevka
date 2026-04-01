"""
Supabase helper za Prava Kolevka.
"""

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
                "SUPABASE_URL ili SUPABASE_KEY"
                " nisu podešeni.")
        _client = create_client(url, key)
    return _client


# ═══ LAWS ═══

def sb_insert_law(data):
    """Insert zakon. data je dict sa poljima.
    Vraća unet red."""
    sb = get_sb()
    r = sb.table("laws").insert(data).execute()
    return r.data[0] if r.data else None


def sb_get_law(law_id):
    """Vraća zakon po ID-u."""
    sb = get_sb()
    r = sb.table("laws").select("*").eq(
        "id", law_id).execute()
    return r.data[0] if r.data else None


def sb_get_all_laws(active_only=True):
    """Vraća sve zakone."""
    sb = get_sb()
    q = sb.table("laws").select("*")
    if active_only:
        q = q.eq("is_active", True)
    r = q.order("hierarchy_level").order(
        "name_sr").execute()
    return r.data or []


def sb_update_law(law_id, data):
    """Ažurira zakon."""
    sb = get_sb()
    r = sb.table("laws").update(data).eq(
        "id", law_id).execute()
    return r.data[0] if r.data else None


def sb_delete_law(law_id):
    """Briše zakon i članke (CASCADE)."""
    sb = get_sb()
    sb.table("laws").delete().eq(
        "id", law_id).execute()


# ═══ LAW ARTICLES ═══

def sb_insert_article(data):
    """Insert članak. data je dict."""
    sb = get_sb()
    r = sb.table("law_articles").insert(
        data).execute()
    return r.data[0] if r.data else None


def sb_insert_articles_bulk(articles):
    """Insert više članova odjednom."""
    if not articles:
        return []
    sb = get_sb()
    r = sb.table("law_articles").insert(
        articles).execute()
    return r.data or []


def sb_get_articles(law_id):
    """Vraća članke zakona po law_id."""
    sb = get_sb()
    r = sb.table("law_articles").select("*").eq(
        "law_id", law_id).order(
        "order_index").execute()
    return r.data or []


def sb_delete_articles(law_id):
    """Briše sve članke zakona."""
    sb = get_sb()
    sb.table("law_articles").delete().eq(
        "law_id", law_id).execute()


def sb_count_articles():
    """Vraća ukupan broj članova."""
    sb = get_sb()
    r = sb.table("law_articles").select(
        "id", count="exact").execute()
    return r.count or 0


# ═══ KOMBINOVANO ═══

def sb_save_law_with_articles(law_data, articles):
    """Sačuvaj zakon + sve članke.
    Vraća (law_id, broj_clanova)."""
    law = sb_insert_law(law_data)
    if not law:
        return None, 0
    law_id = law["id"]
    bulk = []
    for i, art in enumerate(articles):
        bulk.append({
            "law_id": law_id,
            "article_number":
                art.get("article_number", "0"),
            "title": art.get("title", ""),
            "content": art.get("content", ""),
            "order_index": i
        })
    if bulk:
        sb_insert_articles_bulk(bulk)
    return law_id, len(bulk)


def sb_get_law_with_articles(law_id):
    """Vraća zakon sa člancima."""
    law = sb_get_law(law_id)
    if not law:
        return None, []
    arts = sb_get_articles(law_id)
    return law, arts


def sb_get_laws_summary():
    """Vraća listu zakona sa brojem članova."""
    sb = get_sb()
    laws = sb_get_all_laws(active_only=True)
    result = []
    for law in laws:
        arts = sb.table("law_articles").select(
            "id", count="exact").eq(
            "law_id", law["id"]).execute()
        law["num_articles"] = arts.count or 0
        result.append(law)
    return result


def sb_search_articles(keyword):
    """Pretražuje članke po ključnoj reči
    u content ili title."""
    sb = get_sb()
    r = sb.table("law_articles").select(
        "id, law_id, article_number,"
        " title, content, order_index"
    ).or_(
        f"content.ilike.%{keyword}%,"
        f"title.ilike.%{keyword}%"
    ).limit(20).execute()
    return r.data or []


def sb_search_articles_by_number(art_num):
    """Pretražuje članke po broju člana."""
    sb = get_sb()
    r = sb.table("law_articles").select(
        "id, law_id, article_number,"
        " title, content, order_index"
    ).eq("article_number", art_num
    ).limit(20).execute()
    return r.data or []


def sb_get_law_basic(law_id):
    """Vraća osnovne podatke zakona."""
    sb = get_sb()
    r = sb.table("laws").select(
        "id, name_sr, name_al, short_name,"
        " law_number, area, hierarchy_level,"
        " gazette_info"
    ).eq("id", law_id).execute()
    return r.data[0] if r.data else None


def sb_get_all_articles_with_laws():
    """Vraća sve članke sa podacima zakona
    za vector store."""
    sb = get_sb()
    laws = sb.table("laws").select(
        "id, name_sr, short_name, law_number,"
        " area, hierarchy_level"
    ).eq("is_active", True).execute().data or []
    if not laws:
        return []
    law_map = {l["id"]: l for l in laws}
    all_rows = []
    for law_id in law_map:
        arts = sb.table("law_articles").select(
            "article_number, title, content"
        ).eq("law_id", law_id).order(
            "order_index").execute().data or []
        for art in arts:
            art["law_id"] = law_id
            art["name_sr"] = law_map[law_id]["name_sr"]
            art["short_name"] = law_map[law_id].get(
                "short_name", "")
            art["law_number"] = law_map[law_id].get(
                "law_number", "")
            art["area"] = law_map[law_id].get(
                "area", "")
            art["hierarchy_level"] = law_map[
                law_id].get("hierarchy_level", 3)
            all_rows.append(art)
    return all_rows


def sb_find_laws_by_name(name):
    """Traži zakone po nazivu ili skraćenici."""
    sb = get_sb()
    r = sb.table("laws").select(
        "id, name_sr, short_name, law_number,"
        " area, hierarchy_level"
    ).eq("is_active", True).or_(
        f"name_sr.ilike.%{name}%,"
        f"short_name.ilike.%{name}%"
    ).execute()
    return r.data or []


def sb_test_connection():
    """Testira konekciju i vraća status."""
    try:
        sb = get_sb()
        laws = sb.table("laws").select(
            "id, name_sr", count="exact"
        ).eq("is_active", True).execute()
        arts = sb.table("law_articles").select(
            "id", count="exact").execute()
        
        result = {
            "connected": True,
            "laws_count": laws.count or 0,
            "articles_count": arts.count or 0,
            "laws": [
                f"{l['id']}: {l['name_sr']}"
                for l in (laws.data or [])[:5]
            ]
        }
        
        # Test: dohvati čl. 1 za law_id=3
        test_art = sb.table("law_articles").select(
            "article_number, title, content"
        ).eq("law_id", 3).eq(
            "article_number", "1").execute()
        if test_art.data:
            a = test_art.data[0]
            result["test_article"] = (
                f"Čl. {a['article_number']}: "
                f"{a['content'][:100]}...")
        else:
            result["test_article"] = (
                "Čl. 1 za law_id=3"
                " nije pronađen")
        return result
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


def sb_search_articles_multi(keywords, law_ids=None):
    """Pretražuje članke po više ključnih reči.
    Vraća sve članke koji matchuju bar jednu reč."""
    sb = get_sb()
    all_results = {}
    for kw in keywords[:8]:
        q = sb.table("law_articles").select(
            "id, law_id, article_number,"
            " title, content, order_index")
        if law_ids:
            q = q.in_("law_id", law_ids)
        r = q.or_(
            f"content.ilike.%{kw}%,"
            f"title.ilike.%{kw}%"
        ).limit(30).execute()
        for art in (r.data or []):
            aid = art["id"]
            if aid not in all_results:
                all_results[aid] = art
                all_results[aid]["_matched_kw"] = set()
            all_results[aid]["_matched_kw"].add(kw)
    # Konvertuj set u listu za dalju obradu
    result = list(all_results.values())
    for r_item in result:
        r_item["_match_count"] = len(r_item["_matched_kw"])
        r_item["_matched_kw"] = list(r_item["_matched_kw"])
    return result


def sb_get_first_articles(law_id, limit=5):
    """Vraća prvih N članova zakona
    (za pitanja o cilju, oblasti primene itd.)."""
    sb = get_sb()
    r = sb.table("law_articles").select(
        "id, law_id, article_number,"
        " title, content, order_index"
    ).eq("law_id", law_id).order(
        "order_index").limit(limit).execute()
    return r.data or []


def sb_get_law_ids_by_area(area):
    """Vraća ID-jeve zakona iz određene oblasti."""
    sb = get_sb()
    r = sb.table("laws").select("id").eq(
        "is_active", True).eq(
        "area", area).execute()
    return [l["id"] for l in (r.data or [])]
