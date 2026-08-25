import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

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
        if self.default_snippets_path.exists():
            try:
                with open(self.default_snippets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for cat in data.get("categories", []):
                        cat_info = {
                            "id": cat.get("id", cat.get("name")),
                            "name": cat.get("name"),
                            "icon": cat.get("icon", "📁")
                        }
                        self.categories.append(cat_info)
                        for snip in cat.get("snippets", []):
                            snip["is_custom"] = False
                            snip["category_id"] = cat_info["id"]
                            if "category" not in snip:
                                snip["category"] = cat_info["name"]
                            self.snippets.append(snip)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted default snippets JSON at {self.default_snippets_path}: {e}")
            except (OSError, UnicodeDecodeError, KeyError) as e:
                logger.error(f"Error reading default snippets from {self.default_snippets_path}: {e}")

        # 2. Load user custom snippets
        custom_category = {
            "id": "custom_snippets",
            "name": "⭐ Eigene Notizen & Custom",
            "icon": "⭐"
        }
        
        user_snippets = []
        if self.user_snippets_path.exists():
            try:
                with open(self.user_snippets_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    for snip in user_data:
                        snip["is_custom"] = True
                        snip["category_id"] = snip.get("category_id", "custom_snippets")
                        user_snippets.append(snip)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted user snippets JSON at {self.user_snippets_path}: {e}")
            except (OSError, UnicodeDecodeError, KeyError) as e:
                logger.error(f"Error reading user snippets from {self.user_snippets_path}: {e}")

        if not any(c["id"] == "custom_snippets" for c in self.categories):
            self.categories.append(custom_category)
            
        self.snippets.extend(user_snippets)

    def save_user_snippets(self) -> None:
        """Persists custom user snippets to disk."""
        try:
            self.user_snippets_path.parent.mkdir(parents=True, exist_ok=True)
            custom_only = [s for s in self.snippets if s.get("is_custom", False)]
            with open(self.user_snippets_path, "w", encoding="utf-8") as f:
                json.dump(custom_only, f, indent=2, ensure_ascii=False)
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
            "category": category or "⭐ Eigene Notizen & Custom",
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
        cats = [{"id": "all", "name": "✨ Alle Befehle", "icon": "⚡", "count": len(self.snippets)}]
        for c in self.categories:
            count = sum(1 for s in self.snippets if s.get("category_id") == c["id"])
            cats.append({
                "id": c["id"],
                "name": c["name"],
                "icon": c.get("icon", "📁"),
                "count": count
            })
        return cats
