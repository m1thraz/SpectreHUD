"""
Pure Python search, categorization, and ranking engine for cheatsheet snippets.

This module is completely decoupled from Qt and UI components, enabling fast,
headless in-memory evaluation and deterministic testing.
"""

from typing import Any, Dict, List, Optional, Set
from core.fuzzy_matcher import FuzzyMatcher


def filter_by_category(
    snippets: List[Dict[str, Any]],
    category_id: Optional[str] = None,
    favorite_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filters snippets by category ID or pinned favorites status.

    Args:
        snippets: List of snippet dictionaries.
        category_id: Target category ID ('all', 'favorites', or a specific ID).
        favorite_ids: Set of pinned favorite snippet IDs.

    Returns:
        Filtered list of snippet dictionaries.
    """
    if not snippets:
        return []

    fav_set = favorite_ids or set()

    if category_id == "favorites":
        return [s for s in snippets if s.get("id") in fav_set]
    elif category_id and category_id != "all":
        return [s for s in snippets if s.get("category_id") == category_id]

    return list(snippets)


def tokenize_query(query: str) -> Dict[str, Any]:
    """
    Parses a raw search query into text tokens and specialized filter qualifiers (e.g. tag:linux).

    Returns:
        Dictionary with:
            - 'text': Remaining plain search string.
            - 'tags': Set of required tag tokens.
    """
    if not query:
        return {"text": "", "tags": set()}

    parts = query.strip().split()
    plain_parts: List[str] = []
    tags: Set[str] = set()

    for part in parts:
        if part.lower().startswith("tag:"):
            tag_val = part[4:].strip().lower()
            if tag_val:
                tags.add(tag_val)
        else:
            plain_parts.append(part)

    return {
        "text": " ".join(plain_parts),
        "tags": tags,
    }


def filter_and_rank_snippets(
    snippets: List[Dict[str, Any]],
    category_id: Optional[str] = None,
    query: str = "",
    favorite_ids: Optional[Set[str]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Filters snippets by category and tags, then ranks them using FuzzyMatcher.

    Pinned favorites matching the query receive a score boost.
    """
    if not snippets:
        return []

    fav_set = favorite_ids or set()

    # Step 1: Category Filtering
    filtered = filter_by_category(snippets, category_id=category_id, favorite_ids=fav_set)

    # Step 2: Query Parsing
    parsed = tokenize_query(query)
    required_tags = parsed["tags"]
    text_query = parsed["text"]

    # Step 3: Tag Filtering
    if required_tags:
        tag_matched = []
        for s in filtered:
            snippet_tags = {str(t).lower() for t in s.get("tags", [])}
            if required_tags.issubset(snippet_tags):
                tag_matched.append(s)
        filtered = tag_matched

    # Step 4: Text Search & Fuzzy Ranking
    if text_query and text_query.strip():
        # Score each snippet using FuzzyMatcher and apply favorite boost
        scored: List[tuple[float, Dict[str, Any]]] = []
        for s in filtered:
            score = FuzzyMatcher.score_snippet(s, text_query)
            if score > 0:
                if s.get("id") in fav_set:
                    score += 15.0
                scored.append((score, s))

        # Sort descending by score
        scored.sort(key=lambda item: item[0], reverse=True)
        results = [s for _, s in scored]
    else:
        # Sort favorites to the top while preserving stable relative order
        results = sorted(filtered, key=lambda s: 0 if s.get("id") in fav_set else 1)

    if limit is not None and limit > 0:
        return [dict(s) for s in results[:limit]]

    return [dict(s) for s in results]
