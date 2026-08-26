import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from core.config import get_default_config_dir
from core.logger import get_logger

logger = get_logger("snippets")

class SnippetManager:
    """Manages built-in and custom user command snippets."""

    @staticmethod
    def _resolve_default_snippets_path() -> Path:
        """Resolves default_snippets.json in source repository, site-packages, or package resources."""
        # 1. Standard repo or site-packages layout (next to core/)
        candidate = Path(__file__).resolve().parent.parent / "data" / "default_snippets.json"
        if candidate.exists():
            return candidate

        # 2. Check importlib.resources if available
        try:
            import importlib.resources as pkg_resources
            if hasattr(pkg_resources, 'files'):
                traversable = pkg_resources.files('data') / 'default_snippets.json'
                res_path = Path(str(traversable))
                if res_path.exists():
                    return res_path
        except (ImportError, AttributeError, TypeError, ValueError, OSError) as e:
            logger.debug(f"Could not resolve snippets path via importlib.resources: {e}")

        return candidate

    def __init__(self, default_snippets_path: Optional[Path] = None, user_snippets_path: Optional[Path] = None):
        if default_snippets_path is None:
            default_snippets_path = self._resolve_default_snippets_path()
        if user_snippets_path is None:
            user_snippets_path = get_default_config_dir() / "user_snippets.json"

        self.default_snippets_path = Path(default_snippets_path)
        self.user_snippets_path = Path(user_snippets_path)
        self.categories: List[Dict[str, Any]] = []
        self.snippets: List[Dict[str, Any]] = []
        
        self.load_all()

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
                except (json.JSONDecodeError, RecursionError) as e:
                    logger.error(f"Corrupted user snippets JSON at {self.user_snippets_path}: {e}")
                except (OSError, UnicodeDecodeError, KeyError) as e:
                    logger.error(f"Error reading user snippets from {self.user_snippets_path}: {e}")

        if not any(c["id"] == "custom_snippets" for c in self.categories):
            self.categories.append(custom_category)
            
        self.snippets.extend(user_snippets)

    def save_user_snippets(self) -> None:
        """Persists custom user snippets to disk atomically."""
        from core.atomic_write import atomic_write_json
        try:
            custom_only = [s for s in self.snippets if s.get("is_custom", False)]
            atomic_write_json(self.user_snippets_path, custom_only, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"OS error saving user snippets to {self.user_snippets_path}: {e}", exc_info=True)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error saving user snippets: {e}")

    def add_custom_snippet(self, title: str, category: str, subcategory: str, template: str, description: str = "", tags: List[str] = None) -> Dict[str, Any]:
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
            "is_custom": True
        }
        self.snippets.append(new_snip)
        self.save_user_snippets()
        return new_snip

    def import_snippets_list(self, snippet_list: List[Dict[str, Any]]) -> int:
        """Appends a list of custom snippets and saves atomically."""
        if not snippet_list:
            return 0
        
        count = 0
        for item in snippet_list:
            if not isinstance(item, dict):
                continue
            tmpl = item.get("template") or item.get("command") or ""
            if not tmpl.strip():
                continue
            snip_id = item.get("id") or f"custom_{uuid.uuid4().hex[:8]}"
            # Avoid duplicate IDs
            if any(s.get("id") == snip_id for s in self.snippets):
                snip_id = f"custom_{uuid.uuid4().hex[:8]}"
            
            new_snip = {
                "id": snip_id,
                "title": item.get("title") or item.get("name") or "Importierter Befehl",
                "category": item.get("category") or "Custom Notes & Snippets",
                "category_id": item.get("category_id") or "custom_snippets",
                "subcategory": item.get("subcategory") or "Allgemein",
                "description": item.get("description") or "",
                "template": tmpl,
                "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
                "is_custom": True
            }
            self.snippets.append(new_snip)
            count += 1

        if count > 0:
            self.save_user_snippets()
        return count

    def import_from_file(self, file_path: Union[str, Path]) -> int:
        """Parses and imports snippets from a JSON or Markdown file."""
        from core.snippet_importer import import_snippets_from_file
        parsed = import_snippets_from_file(file_path)
        return self.import_snippets_list(parsed)

    def delete_snippet(self, snippet_id: str) -> bool:
        """Deletes a custom snippet by its ID."""
        for i, snip in enumerate(self.snippets):
            if snip.get("id") == snippet_id and snip.get("is_custom", False):
                self.snippets.pop(i)
                self.save_user_snippets()
                return True
        return False

    def search(self, query: str = "", category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Filters snippets by search query (across title, description, template, tags)
        and optionally restricts to a specific category.
        """
        results = self.snippets
        
        if category_id and category_id != "all":
            results = [s for s in results if s.get("category_id") == category_id]
            
        if not query or not query.strip():
            return results
            
        q = query.strip().lower()
        terms = q.split()
        
        filtered = []
        for s in results:
            title = s.get("title", "").lower()
            desc = s.get("description", "").lower()
            tmpl = s.get("template", "").lower()
            cat = s.get("category", "").lower()
            subcat = s.get("subcategory", "").lower()
            tags = " ".join(s.get("tags", [])).lower()
            
            combined = f"{title} {desc} {tmpl} {cat} {subcat} {tags}"
            
            # All search terms must match somewhere
            if all(term in combined for term in terms):
                filtered.append(s)
                
        return filtered

    def get_snippets(self, category_id: Optional[str] = None, search_query: str = "") -> List[Dict[str, Any]]:
        """Alias for search() to retrieve filtered snippets."""
        return self.search(query=search_query, category_id=category_id)

    def get_categories(self) -> List[Dict[str, Any]]:
        """Returns categories with accurate snippet counts."""
        cats = [{"id": "all", "name": "All Commands", "icon": "", "count": len(self.snippets)}]
        for c in self.categories:
            count = sum(1 for s in self.snippets if s.get("category_id") == c["id"])
            cats.append({
                "id": c["id"],
                "name": c["name"],
                "icon": c.get("icon", ""),
                "count": count
            })
        return cats
