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
