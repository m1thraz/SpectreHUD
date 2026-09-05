import re
import difflib
from typing import Dict, Any, List, Tuple, Optional


class FuzzyMatcher:
    """
    High-performance CTF & Pentester-focused fuzzy search and ranking engine.

    Weights & Scoring Hierarchy:
    1. Exact Tool Name / Command Prefix (e.g. 'nmap', 'ffuf', 'chisel', 'curl', 'nc') -> +100
    2. Acronym & Shortcode matching (e.g. 'rce' -> 'Remote Code Execution', 'lfi' -> 'Local File Inclusion') -> +85
    3. Title & Tags matching (e.g. 'privesc', 'windows', 'smb', 'ad', 'suid') -> +70 - +80
    4. Command Syntax & Flag matching (e.g. '-sC -sV', 'Invoke-Mimikatz', 'xp_cmdshell') -> +50
    5. Subsequence & Typo tolerance (e.g. 'nmp' -> 'nmap', 'whos' -> 'whois', 'chisl' -> 'chisel') -> +30 - +45
    6. Category & Description background text -> +20 - +35
    """

    @staticmethod
    def _extract_acronym(text: str) -> str:
        """Extracts leading letters from title words (e.g. 'Remote Code Execution' -> 'rce')."""
        words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(words) > 1:
            return "".join(w[0] for w in words)
        return ""

    @staticmethod
    def _is_subsequence(sub: str, full: str) -> bool:
        """Returns True if 'sub' is a contiguous or non-contiguous subsequence of 'full'."""
        if not sub or not full:
            return False
        it = iter(full)
        return all(char in it for char in sub)

    @classmethod
    def score_snippet(cls, snippet: Dict[str, Any], query: str) -> float:
        """
        Calculates a relevance score for a snippet given a search query.
        Returns 0.0 if the snippet does not match the query tokens.
        """
        q = query.strip().lower()
        if not q:
            return 1.0

        query_tokens = [t for t in re.split(r"\s+", q) if t]
        if not query_tokens:
            return 1.0

        # Extract snippet fields
        title = str(snippet.get("title", "")).lower()
        template = str(snippet.get("template", "")).lower()
        description = str(snippet.get("description", "")).lower()
        category = str(snippet.get("category", "")).lower()
        subcategory = str(snippet.get("subcategory", "")).lower()
        raw_tags = snippet.get("tags", [])
        tags = [str(t).lower() for t in raw_tags]

        # Extract primary tool / command binary name (e.g. 'nmap -sC ...' -> 'nmap')
        template_first_word = re.split(r"[\s|;&]+", template.strip())[0] if template.strip() else ""
        title_first_word = re.split(r"[\s|;&]+", title.strip())[0] if title.strip() else ""
        acronym = cls._extract_acronym(title)

        total_snippet_score = 0.0

        for token in query_tokens:
            token_score = 0.0
            t_len = len(token)

            # 1. Exact Tool Name match (+100) / Tool Prefix match (+90)
            if token == template_first_word or token == title_first_word:
                token_score = max(token_score, 100.0)
            elif template_first_word.startswith(token) or title_first_word.startswith(token):
                token_score = max(token_score, 90.0)

            # 2. Acronym match (+85)
            if acronym and (token == acronym or acronym.startswith(token)):
                token_score = max(token_score, 85.0)

            # 3. Exact tag match (+80) / Substring in tags (+55)
            if token in tags:
                token_score = max(token_score, 80.0)
            elif any(token in t for t in tags):
                token_score = max(token_score, 55.0)

            # 4. Title match
            if token == title:
                token_score = max(token_score, 95.0)
            elif token in title:
                # Word boundary match in title? (e.g. ' sql' in 'blind sql injection')
                if re.search(r"\b" + re.escape(token), title):
                    token_score = max(token_score, 75.0)
                else:
                    token_score = max(token_score, 65.0)

            # 5. Template syntax / Flag match (+50)
            if token in template:
                token_score = max(token_score, 50.0)

            # 6. Category / Subcategory match (+35)
            if token in category or token in subcategory:
                token_score = max(token_score, 35.0)

            # 7. Description match (+20)
            if token in description:
                token_score = max(token_score, 20.0)

            # 8. Fuzzy / Typo Tolerance (only for tokens of length >= 3)
            if token_score == 0.0 and t_len >= 3:
                candidates = [template_first_word, title_first_word] + tags
                token_score = cls._score_fuzzy_typo(token, t_len, candidates)

            # If any token in a multi-token query fails to match, reject snippet
            if token_score == 0.0:
                return 0.0

            total_snippet_score += token_score

        return total_snippet_score

    @classmethod
    def _score_fuzzy_typo(cls, token: str, t_len: int, candidates: List[str]) -> float:
        """Evaluates typo tolerance (Rule 8) against primary tool names and tags."""
        for w in candidates:
            if not w or len(w) < 3:
                continue
            w_len = len(w)
            # 1. Missing character in query (e.g. 'nmp' for 'nmap', 'chisl' for 'chisel', 'hydr' for 'hydra')
            if w_len == t_len + 1 and cls._is_subsequence(token, w):
                return 45.0
            # 2. Extra character in query (e.g. 'curll' for 'curl', 'nmapp' for 'nmap')
            if t_len == w_len + 1 and w_len >= 4 and cls._is_subsequence(w, token):
                return 45.0
            # 3. Single substitution/transposition typo (e.g. 'whos' for 'whois', length >= 4)
            if t_len == w_len and t_len >= 4:
                ratio = difflib.SequenceMatcher(None, token, w).ratio()
                if ratio >= 0.75:
                    return 40.0 * ratio
        return 0.0

    @classmethod
    def rank_snippets(
        cls, snippets: List[Dict[str, Any]], query: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Filters and ranks snippets by relevance to the query.
        If query is empty, returns original snippet list (optionally truncated to limit).
        """
        q = query.strip()
        if not q:
            return snippets[:limit] if limit else list(snippets)

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for s in snippets:
            score = cls.score_snippet(s, q)
            if score > 0.0:
                scored.append((score, s))

        # Sort descending by score; preserve stable order for equal scores
        scored.sort(key=lambda item: item[0], reverse=True)
        results = [item[1] for item in scored]

        if limit is not None and limit > 0:
            return results[:limit]
        return results
