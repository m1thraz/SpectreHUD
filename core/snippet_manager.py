import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_default_config_dir
from core.logger import get_logger
from core.storage import PersistenceError

logger = get_logger("snippets")

class SnippetManager:
    """Manages built-in and custom user command snippets."""

    @staticmethod
    def _resolve_default_snippets_path(language: str = "en") -> Path:
        """Resolves default_snippets JSON for language ('en' or 'de') in source repository, site-packages, package resources, or PyInstaller bundle."""
        import sys

        is_en = str(language).lower().startswith("en")
        filename = "default_snippets - EN.json" if is_en else "default_snippets.json"

        # 0. Check PyInstaller frozen bundle
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            bundle_candidate = Path(sys._MEIPASS) / "data" / filename
            if bundle_candidate.exists():
                return bundle_candidate
            fallback = Path(sys._MEIPASS) / "data" / "default_snippets.json"
            if fallback.exists():
                return fallback

        # 1. Standard repo or site-packages layout (next to core/)
        data_dir = Path(__file__).resolve().parent.parent / "data"
        candidate = data_dir / filename
        if candidate.exists():
            return candidate

        fallback_candidate = data_dir / "default_snippets.json"
        if fallback_candidate.exists():
            return fallback_candidate

        # 2. Check importlib.resources if available
        try:
            import importlib.resources as pkg_resources
            if hasattr(pkg_resources, 'files'):
                traversable = pkg_resources.files('data') / filename
                res_path = Path(str(traversable))
                if res_path.exists():
                    return res_path
        except (ImportError, AttributeError, TypeError, ValueError, OSError) as e:
            logger.debug(f"Could not resolve snippets path via importlib.resources: {e}")

        return candidate

    def __init__(
        self,
        default_snippets_path: Optional[Path] = None,
        user_snippets_path: Optional[Path] = None,
        favorites_path: Optional[Path] = None,
        language: str = "en",
        event_bus: Optional[Any] = None
    ):
        self.language = "en" if str(language).lower().startswith("en") else "de"
        self._custom_default_snippets_path = default_snippets_path is not None
        if default_snippets_path is None:
            default_snippets_path = self._resolve_default_snippets_path(self.language)
        if user_snippets_path is None:
            user_snippets_path = get_default_config_dir() / "user_snippets.json"
        if favorites_path is None:
            favorites_path = get_default_config_dir() / "user_favorites.json"

        self.event_bus = event_bus
        self.default_snippets_path = Path(default_snippets_path)
        self.user_snippets_path = Path(user_snippets_path)
        self.favorites_path = Path(favorites_path)
        self.favorite_ids: set = set()
        self.categories: List[Dict[str, Any]] = []
        self.snippets: List[Dict[str, Any]] = []
        
        self.load_favorites()
        self.load_all()

    def set_language(self, language: str) -> None:
        """Switches snippet database to match the given language ('en' or 'de') and reloads."""
        new_lang = "en" if str(language).lower().startswith("en") else "de"
        if self.language == new_lang and self.default_snippets_path.exists() and not self._custom_default_snippets_path:
            return
        self.language = new_lang
        if not self._custom_default_snippets_path:
            self.default_snippets_path = self._resolve_default_snippets_path(new_lang)
        self.load_all()

    def load_favorites(self) -> None:
        """Loads list of pinned snippet IDs from disk."""
        from core.validators import is_file_size_valid, MAX_CONFIG_FILE_SIZE
        self.favorite_ids = set()
        if self.favorites_path.exists() and is_file_size_valid(self.favorites_path, MAX_CONFIG_FILE_SIZE):
            try:
                with open(self.favorites_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.favorite_ids = set(str(item) for item in data if isinstance(item, (str, int)))
            except (json.JSONDecodeError, RecursionError) as e:
                logger.error(f"Corrupted favorites JSON at {self.favorites_path}: {e}")
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error reading favorites from {self.favorites_path}: {e}")

    def save_favorites(self) -> None:
        """Persists pinned snippet IDs to disk atomically."""
        from core.atomic_write import atomic_write_json
        try:
            atomic_write_json(self.favorites_path, sorted(list(self.favorite_ids)), indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving favorites to {self.favorites_path}: {e}", exc_info=True)
            raise PersistenceError(f"Could not persist favorites: {e}") from e

    def toggle_favorite(self, snippet_id: str) -> bool:
        """Toggles favorite state for a given snippet ID. Returns True if now favorite, False otherwise."""
        if not snippet_id:
            return False
        if snippet_id in self.favorite_ids:
            self.favorite_ids.remove(snippet_id)
            state = False
        else:
            self.favorite_ids.add(snippet_id)
            state = True
        
        # Update in-memory snippets
        for s in self.snippets:
            if s.get("id") == snippet_id:
                s["is_favorite"] = state
                break

        self.save_favorites()
        return state

    def is_favorite(self, snippet_id: str) -> bool:
        """Returns True if the snippet ID is pinned as a favorite."""
        return snippet_id in self.favorite_ids

    def load_all(self) -> None:
        """Loads both default bundled snippets and user-added custom snippets."""
        self.categories = []
        self.snippets = []
        
        # 1. Load default snippets
        from core.validators import is_file_size_valid, MAX_SNIPPETS_FILE_SIZE
        if self.default_snippets_path.exists() and is_file_size_valid(self.default_snippets_path, MAX_SNIPPETS_FILE_SIZE):
            try:
                with open(self.default_snippets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        logger.warning(f"Expected dict in snippets JSON at {self.default_snippets_path}, got {type(data).__name__}.")
                        data = {}
                    for cat in data.get("categories", []):
                        if not isinstance(cat, dict):
                            continue
                        cat_info = {
                            "id": cat.get("id", cat.get("name")),
                            "name": cat.get("name"),
                            "icon": cat.get("icon", "")
                        }
                        self.categories.append(cat_info)
                        for snip in cat.get("snippets", []):
                            if not isinstance(snip, dict):
                                continue
                            snip["is_custom"] = False
                            snip["category_id"] = cat_info["id"]
                            snip["is_favorite"] = snip.get("id") in self.favorite_ids
                            if "category" not in snip:
                                snip["category"] = cat_info["name"]
                            self.snippets.append(snip)
            except (json.JSONDecodeError, RecursionError) as e:
                logger.error(f"Corrupted default snippets JSON at {self.default_snippets_path}: {e}")
            except (OSError, UnicodeDecodeError, KeyError, AttributeError) as e:
                logger.error(f"Error reading default snippets from {self.default_snippets_path}: {e}")

        # 2. Load user custom snippets
        custom_category = {
            "id": "custom_snippets",
            "name": "Custom Notes & Snippets",
            "icon": ""
        }
        
        user_snippets = []
        if self.user_snippets_path.exists():
            if not is_file_size_valid(self.user_snippets_path, MAX_SNIPPETS_FILE_SIZE):
                logger.error(f"User snippets file {self.user_snippets_path} exceeds maximum size limit of {MAX_SNIPPETS_FILE_SIZE} bytes. Rejecting oversized file.")
            else:
                from core.validators import validate_user_snippets
                try:
                    with open(self.user_snippets_path, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                        user_snippets = validate_user_snippets(user_data)
                        for s in user_snippets:
                            s["is_favorite"] = s.get("id") in self.favorite_ids
                except (json.JSONDecodeError, RecursionError) as e:
                    logger.error(f"Corrupted user snippets JSON at {self.user_snippets_path}: {e}")
                except (OSError, UnicodeDecodeError, KeyError) as e:
                    logger.error(f"Error reading user snippets from {self.user_snippets_path}: {e}")

        if not any(c["id"] == "custom_snippets" for c in self.categories):
            self.categories.append(custom_category)
            
        self.snippets.extend(user_snippets)

        # Prune any orphaned favorite IDs that do not match loaded snippets
        valid_ids = {s.get("id") for s in self.snippets if s.get("id")}
        self.favorite_ids = {fid for fid in self.favorite_ids if fid in valid_ids}

    def save_user_snippets(self) -> None:
        """Persists custom user snippets to disk atomically."""
        from core.atomic_write import atomic_write_json
        custom_only = [s for s in self.snippets if s.get("is_custom", False)]
        try:
            atomic_write_json(self.user_snippets_path, custom_only, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user snippets to {self.user_snippets_path}: {e}", exc_info=True)
            raise PersistenceError(f"Could not persist user snippets: {e}") from e

    def add_custom_snippet(self, title: str, category: str = "Custom Notes & Snippets", subcategory: str = "Allgemein", template: str = "", description: str = "", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Creates and stores a new custom snippet."""
        if tags is None:
            tags = []
        new_snip = {
            "id": f"custom_{uuid.uuid4().hex[:8]}",
            "title": title,
            "category": category or "Custom Notes & Snippets",
            "category_id": "custom_snippets",
            "subcategory": subcategory or "Allgemein",
            "description": description,
            "template": template,
            "tags": tags,
            "is_custom": True,
            "is_favorite": False
        }
        from core.atomic_write import atomic_write_json
        custom_only = [s for s in self.snippets if s.get("is_custom", False)] + [new_snip]
        try:
            atomic_write_json(self.user_snippets_path, custom_only, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user snippets: {e}", exc_info=True)
            raise PersistenceError(f"Could not persist custom snippet: {e}") from e

        self.snippets.append(new_snip)
        return new_snip

    def import_from_file(self, file_path: Any) -> int:
        """
        Imports snippets from a JSON or Markdown file, adds them to user snippets,
        and persists them to user_snippets.json in a single atomic batch write.
        Returns the number of snippets imported.
        """
        from core.snippet_importer import import_snippets_from_file
        parsed = import_snippets_from_file(file_path)
        if not parsed:
            return 0

        new_items = []
        for snip in parsed:
            new_snip = {
                "id": f"custom_{uuid.uuid4().hex[:8]}",
                "title": snip.get("title", "Imported Snippet"),
                "category": snip.get("category", "Custom Notes & Snippets"),
                "category_id": "custom_snippets",
                "subcategory": snip.get("subcategory", "Allgemein"),
                "template": snip.get("template", ""),
                "description": snip.get("description", ""),
                "tags": snip.get("tags", []) if isinstance(snip.get("tags"), list) else [],
                "is_custom": True,
                "is_favorite": False
            }
            new_items.append(new_snip)

        if new_items:
            from core.atomic_write import atomic_write_json
            custom_only = [s for s in self.snippets if s.get("is_custom", False)] + new_items
            try:
                atomic_write_json(self.user_snippets_path, custom_only, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error persisting imported snippets: {e}", exc_info=True)
                raise PersistenceError(f"Could not persist imported snippets: {e}") from e

            self.snippets.extend(new_items)

        return len(new_items)

    def delete_snippet(self, snippet_id: str) -> bool:
        """Deletes a custom snippet by its ID."""
        target_idx = None
        for i, snip in enumerate(self.snippets):
            if snip.get("id") == snippet_id and snip.get("is_custom", False):
                target_idx = i
                break
        
        if target_idx is None:
            return False

        from core.atomic_write import atomic_write_json
        custom_only = [s for s in self.snippets if s.get("is_custom", False) and s.get("id") != snippet_id]
        try:
            atomic_write_json(self.user_snippets_path, custom_only, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error persisting snippets after deletion: {e}", exc_info=True)
            raise PersistenceError(f"Could not persist deletion of snippet {snippet_id}: {e}") from e

        self.snippets.pop(target_idx)
        if snippet_id in self.favorite_ids:
            self.favorite_ids.remove(snippet_id)
            from core.atomic_write import atomic_write_json
            try:
                atomic_write_json(self.favorites_path, sorted(list(self.favorite_ids)), indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Could not persist favorites during snippet deletion: {e}")
        return True

    def search(self, query: str = "", category_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Filters snippets by category and ranks them using FuzzyMatcher.
        Supports fuzzy typo tolerance, tool prefix prioritization, acronyms, and tag/syntax matching.
        """
        results = self.snippets
        
        if category_id == "favorites":
            results = [s for s in results if s.get("id") in self.favorite_ids]
        elif category_id and category_id != "all":
            results = [s for s in results if s.get("category_id") == category_id]
            
        if query and query.strip():
            from core.fuzzy_matcher import FuzzyMatcher
            results = FuzzyMatcher.rank_snippets(results, query)
            # Boost pinned favorites if they match
            def score_with_fav(s: Dict[str, Any]) -> float:
                base = FuzzyMatcher.score_snippet(s, query)
                if s.get("id") in self.favorite_ids:
                    return base + 15.0
                return base
            results.sort(key=score_with_fav, reverse=True)
        else:
            # Sort favorites to the top while preserving stable relative order
            results = sorted(results, key=lambda s: 0 if s.get("id") in self.favorite_ids else 1)

        if limit is not None and limit > 0:
            return [dict(s) for s in results[:limit]]
        return [dict(s) for s in results]

    def get_all_snippets(self) -> List[Dict[str, Any]]:
        """Returns defensive copies of all snippets."""
        return [dict(s) for s in self.snippets]

    def get_snippets(self, category_id: Optional[str] = None, search_query: str = "", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Alias for search() to retrieve filtered & ranked snippets."""
        return self.search(query=search_query, category_id=category_id, limit=limit)

    def get_categories(self) -> List[Dict[str, Any]]:
        """Returns defensive copies of categories with accurate snippet counts, including 'all' and 'favorites'."""
        fav_count = sum(1 for s in self.snippets if s.get("id") in self.favorite_ids)
        cats = [
            {"id": "all", "name": "All Commands", "icon": "", "count": len(self.snippets)},
            {"id": "favorites", "name": "Favoriten", "icon": "★", "count": fav_count}
        ]
        for c in self.categories:
            count = sum(1 for s in self.snippets if s.get("category_id") == c["id"])
            cats.append({
                "id": c["id"],
                "name": c["name"],
                "icon": c.get("icon", ""),
                "count": count
            })
        return [dict(c) for c in cats]
