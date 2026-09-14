"""
Report Scope & Methodology model.

Provides the ScopeTargetItem, ScopeExclusionItem, and ReportScopeMethodology
dataclasses with Markdown parsing and rendering of the scope, methodology,
in-scope/out-of-scope targets, and rules of engagement.
"""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ScopeTargetItem:
    """An authorized testing target within the assessment scope."""

    target: str = ""
    target_type: str = "network"  # "network", "host", "webapp", "api", "cloud", "other"
    environment: str = "production"  # "production", "staging", "development", "other"
    description: str = ""


@dataclass
class ScopeExclusionItem:
    """An explicitly excluded asset, system, or limitation."""

    target: str = ""
    reason: str = ""


def normalize_target_type(val: str) -> str:
    v = (val or "").strip().lower()
    if "web" in v or "app" in v:
        return "webapp"
    if "api" in v or "service" in v:
        return "api"
    if "net" in v or "sub" in v or "cidr" in v:
        return "network"
    if "host" in v or "server" in v or "ip" in v:
        return "host"
    if "cloud" in v or "aws" in v or "azure" in v or "gcp" in v:
        return "cloud"
    return "other" if v else "network"


def normalize_environment(val: str) -> str:
    v = (val or "").strip().lower()
    if "prod" in v:
        return "production"
    if "stag" in v or "test" in v or "qa" in v:
        return "staging"
    if "dev" in v or "entw" in v:
        return "development"
    return "other" if v else "production"


@dataclass
class ReportScopeMethodology:
    """Structured representation of the Scope & Methodology section."""

    title: str = "Scope & Methodik"
    approach: str = "greybox"  # "blackbox", "greybox", "whitebox"
    approach_details: str = ""
    in_scope_targets: List[ScopeTargetItem] = field(default_factory=list)
    out_of_scope_targets: List[ScopeExclusionItem] = field(default_factory=list)
    restrictions: List[str] = field(default_factory=lambda: ["no_dos", "no_social_engineering", "no_data_destruction"])
    custom_rules: str = ""

    @classmethod
    def from_markdown(cls, markdown: str, language: str = "de") -> "ReportScopeMethodology":
        default_title = "Scope & Methodik" if language == "de" else "Scope & Methodology"
        if not markdown:
            return cls(title=default_title)

        title = default_title
        h2 = re.search(r"^##\s+(.*?)$", markdown, re.MULTILINE)
        if h2:
            title = h2.group(1).strip()

        # Parse approach
        approach = "greybox"
        approach_details = ""
        m_appr = re.search(
            r"^[ \t]*[-*]\s*[*_]*(?:Ansatz|Approach|Testmethodik|Methodology)[:*_ \t]*\s*(.*)$",
            markdown,
            re.IGNORECASE | re.MULTILINE,
        )
        if m_appr:
            raw_appr = m_appr.group(1).lower()
            if "black" in raw_appr:
                approach = "blackbox"
            elif "white" in raw_appr:
                approach = "whitebox"
            elif "grey" in raw_appr or "gray" in raw_appr:
                approach = "greybox"

        in_targets: List[ScopeTargetItem] = []
        out_targets: List[ScopeExclusionItem] = []
        restrictions: List[str] = []
        custom_rules_lines: List[str] = []

        # Check for subsections or full text
        has_subsections = bool(re.search(r"^###\s+", markdown, re.MULTILINE))

        if has_subsections:
            sections = re.split(r"^###\s+", markdown, flags=re.MULTILINE)
            for sec in sections[1:]:
                sec_lines = sec.strip().splitlines()
                if not sec_lines:
                    continue
                sec_header = sec_lines[0].lower()

                if any(k in sec_header for k in ("ansatz", "approach", "methodik", "methodology")):
                    for line in sec_lines[1:]:
                        cl = line.strip()
                        if not cl:
                            continue
                        m_det = re.search(r"^[ \t]*[-*]\s*[*_]*(?:Details|Beschreibung)[:*_ \t]*\s*(.*)$", cl, re.IGNORECASE)
                        if m_det:
                            approach_details = m_det.group(1).strip()
                        elif not cl.startswith(("-", "*", "|")) and not approach_details:
                            approach_details = cl

                elif "in-scope" in sec_header or "in scope" in sec_header or "ziel" in sec_header or "target" in sec_header:
                    for line in sec_lines[1:]:
                        cl = line.strip()
                        if not cl.startswith("|") or cl.startswith("|---"):
                            continue
                        cols = [c.strip() for c in cl.split("|")[1:-1]]
                        if len(cols) >= 2:
                            raw_tgt = cols[0].strip().strip("`").strip()
                            low_tgt = raw_tgt.lower()
                            if not raw_tgt or low_tgt in ("ziel", "target", "keine ziele definiert", "no targets defined") or low_tgt.startswith(("ziel /", "target /")):
                                continue
                            t_type = normalize_target_type(cols[1]) if len(cols) > 1 else "network"
                            t_env = normalize_environment(cols[2]) if len(cols) > 2 else "production"
                            t_desc = cols[3] if len(cols) > 3 else ""
                            in_targets.append(ScopeTargetItem(target=raw_tgt, target_type=t_type, environment=t_env, description=t_desc))

                elif "out-of-scope" in sec_header or "out of scope" in sec_header or "ausschluss" in sec_header or "exclusion" in sec_header:
                    for line in sec_lines[1:]:
                        cl = line.strip()
                        if not cl.startswith("|") or cl.startswith("|---"):
                            continue
                        cols = [c.strip() for c in cl.split("|")[1:-1]]
                        if len(cols) >= 1:
                            raw_tgt = cols[0].strip().strip("`").strip()
                            low_tgt = raw_tgt.lower()
                            if not raw_tgt or low_tgt in ("ausgeschlossen", "excluded", "keine ausschlüsse definiert", "no exclusions defined") or low_tgt.startswith(("ausgeschlossenes", "excluded target")):
                                continue
                            reason = cols[1] if len(cols) > 1 else ""
                            out_targets.append(ScopeExclusionItem(target=raw_tgt, reason=reason))

                elif any(k in sec_header for k in ("einschränkung", "limitation", "rule", "engagement")):
                    for line in sec_lines[1:]:
                        cl = line.strip()
                        if not cl or cl.startswith("|"):
                            continue
                        m_bullet = re.search(r"^[-*]\s+(.*)$", cl)
                        item_text = m_bullet.group(1).strip() if m_bullet else cl
                        low = item_text.lower()
                        matched_std = False
                        if "dos" in low or "denial-of-service" in low or "verfügbarkeit" in low:
                            if "no_dos" not in restrictions:
                                restrictions.append("no_dos")
                            matched_std = True
                        if "social engineering" in low or "phishing" in low:
                            if "no_social_engineering" not in restrictions:
                                restrictions.append("no_social_engineering")
                            matched_std = True
                        if "zerstörung" in low or "alteration" in low or "veränderung" in low or "löschung" in low:
                            if "no_data_destruction" not in restrictions:
                                restrictions.append("no_data_destruction")
                            matched_std = True
                        if "testfenster" in low or "business hours" in low or "zeitfenster" in low:
                            if "business_hours_only" not in restrictions:
                                restrictions.append("business_hours_only")
                            matched_std = True
                        if not matched_std and not any(ign in low for ign in ("keine besonderen", "no specific")):
                            custom_rules_lines.append(item_text)

        # Legacy fallback if no tables were parsed
        if not in_targets:
            m_in = re.search(r"^[ \t]*[-*]\s*[*_]*In[ -]?Scope[:*_ \t]*\s*(.*)$", markdown, re.IGNORECASE | re.MULTILINE)
            if m_in:
                val = m_in.group(1).strip()
                if val:
                    for t_part in re.split(r"[,;\n]+", val):
                        clean_t = t_part.strip().strip("*_`").strip()
                        if clean_t:
                            in_targets.append(ScopeTargetItem(target=clean_t, target_type="network", environment="production"))

        if not out_targets:
            m_out = re.search(r"^[ \t]*[-*]\s*[*_]*Out[ -]?of[ -]?Scope[:*_ \t]*\s*(.*)$", markdown, re.IGNORECASE | re.MULTILINE)
            if m_out:
                val = m_out.group(1).strip()
                if val:
                    for o_part in re.split(r"[,;\n]+", val):
                        clean_o = o_part.strip().strip("*_`").strip()
                        if clean_o:
                            out_targets.append(ScopeExclusionItem(target=clean_o, reason="Out of Scope"))

        if not restrictions and not custom_rules_lines:
            m_lim = re.search(r"^[ \t]*[-*]\s*[*_]*(?:Einschränkungen|Limitations)[:*_ \t]*\s*(.*)$", markdown, re.IGNORECASE | re.MULTILINE)
            if m_lim:
                lim_text = m_lim.group(1).strip()
                low_lim = lim_text.lower()
                if "dos" in low_lim or "denial-of-service" in low_lim:
                    restrictions.append("no_dos")
                if "social engineering" in low_lim or "phishing" in low_lim:
                    restrictions.append("no_social_engineering")
                if "zerstörung" in low_lim or "alteration" in low_lim or "veränderung" in low_lim or "löschung" in low_lim:
                    restrictions.append("no_data_destruction")
                if "testfenster" in low_lim or "business hours" in low_lim:
                    restrictions.append("business_hours_only")
            else:
                restrictions = ["no_dos", "no_social_engineering", "no_data_destruction"]

        return cls(
            title=title,
            approach=approach,
            approach_details=approach_details,
            in_scope_targets=in_targets,
            out_of_scope_targets=out_targets,
            restrictions=restrictions,
            custom_rules="\n".join(custom_rules_lines),
        )

    def to_markdown(self, language: str = "de") -> str:
        sec_title = self.title or ("Scope & Methodik" if language == "de" else "Scope & Methodology")
        lines: List[str] = [f"## {sec_title}", ""]

        # Approach subsection
        appr_title = "### Pentest-Ansatz & Methodik" if language == "de" else "### Pentest Approach & Methodology"
        lines.append(appr_title)
        lines.append("")

        appr_names_de = {
            "blackbox": "Blackbox (Keine Vorkenntnisse / externer Angreifer)",
            "greybox": "Greybox (Teilweise Vorkenntnisse / Standard-Nutzerperspektive)",
            "whitebox": "Whitebox (Vollständige Kenntnisse / Quellcode & Architektur)",
        }
        appr_names_en = {
            "blackbox": "Blackbox (No prior knowledge / external attacker)",
            "greybox": "Greybox (Partial knowledge / authenticated user perspective)",
            "whitebox": "Whitebox (Full knowledge / architecture & source code audit)",
        }
        appr_map = appr_names_de if language == "de" else appr_names_en
        appr_label = appr_map.get(self.approach.lower(), self.approach.capitalize())
        lbl_appr = "Ansatz" if language == "de" else "Approach"
        lines.append(f"- **{lbl_appr}:** {appr_label}")
        if self.approach_details.strip():
            lines.append(f"  {self.approach_details.strip()}")
        lines.append("")

        # In-Scope Table
        in_title = "### In-Scope Ziele & Netzwerke" if language == "de" else "### In-Scope Targets & Networks"
        lines.append(in_title)
        lines.append("")
        if language == "de":
            lines.append("| Ziel / Host / Subnetz | Typ | Umgebung | Beschreibung |")
            lines.append("|---|---|---|---|")
        else:
            lines.append("| Target / Host / Subnet | Type | Environment | Description |")
            lines.append("|---|---|---|---|")

        type_map_de = {
            "network": "Netzwerk / Subnetz",
            "host": "Host / Server",
            "webapp": "Web-Anwendung",
            "api": "API / Web-Service",
            "cloud": "Cloud-Ressource",
            "other": "Sonstige",
        }
        env_map_de = {
            "production": "Produktion",
            "staging": "Staging",
            "development": "Entwicklung",
            "other": "Sonstige",
        }

        if self.in_scope_targets:
            for item in self.in_scope_targets:
                tgt = (item.target or "–").replace("|", "\\|").replace("\n", " ")
                t_lbl = type_map_de.get(item.target_type, item.target_type.capitalize()) if language == "de" else item.target_type.capitalize()
                e_lbl = env_map_de.get(item.environment, item.environment.capitalize()) if language == "de" else item.environment.capitalize()
                desc = (item.description or "–").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{tgt}` | {t_lbl} | {e_lbl} | {desc} |")
        else:
            empty_msg = "*Keine Ziele definiert*" if language == "de" else "*No targets defined*"
            lines.append(f"| {empty_msg} | | | |")
        lines.append("")

        # Out-of-Scope Table
        out_title = "### Out-of-Scope & Ausschlusskriterien" if language == "de" else "### Out-of-Scope & Exclusions"
        lines.append(out_title)
        lines.append("")
        if language == "de":
            lines.append("| Ausgeschlossenes Ziel / Komponente | Grund / Kriterium |")
            lines.append("|---|---|")
        else:
            lines.append("| Excluded Target / Component | Reason / Constraint |")
            lines.append("|---|---|")

        if self.out_of_scope_targets:
            for ex_item in self.out_of_scope_targets:
                tgt = (ex_item.target or "–").replace("|", "\\|").replace("\n", " ")
                reason = (ex_item.reason or "–").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{tgt}` | {reason} |")
        else:
            empty_msg = "*Keine Ausschlüsse definiert*" if language == "de" else "*No exclusions defined*"
            lines.append(f"| {empty_msg} | |")
        lines.append("")

        # Rules of Engagement / Restrictions
        roe_title = "### Testeinschränkungen & Rules of Engagement" if language == "de" else "### Limitations & Rules of Engagement"
        lines.append(roe_title)
        lines.append("")

        roe_labels_de = {
            "no_dos": "Keine Denial-of-Service-Angriffe (DoS/DDoS) oder Beeinträchtigung der Systemverfügbarkeit",
            "no_social_engineering": "Kein Social Engineering / Phishing gegen Mitarbeiter oder Dritte",
            "no_data_destruction": "Keine dauerhafte Veränderung oder Zerstörung von Geschäfts- und Produktivdaten",
            "business_hours_only": "Prüfaktivitäten ausschließlich innerhalb vereinbarter Testfenster",
        }
        roe_labels_en = {
            "no_dos": "No Denial-of-Service attacks (DoS/DDoS) or service disruption",
            "no_social_engineering": "No social engineering or phishing targeting personnel or third parties",
            "no_data_destruction": "No destructive exploitation or permanent data alteration/deletion",
            "business_hours_only": "Testing activities restricted to agreed service windows",
        }
        labels = roe_labels_de if language == "de" else roe_labels_en

        for r_key in self.restrictions:
            text = labels.get(r_key, r_key)
            lines.append(f"- {text}")

        if self.custom_rules.strip():
            for c_line in self.custom_rules.strip().splitlines():
                cl = c_line.strip()
                if not cl:
                    continue
                if cl.startswith(("-", "*")):
                    lines.append(cl)
                else:
                    lines.append(f"- {cl}")

        if not self.restrictions and not self.custom_rules.strip():
            no_roe = "*Keine besonderen Einschränkungen vereinbart.*" if language == "de" else "*No specific restrictions agreed.*"
            lines.append(no_roe)

        lines.append("")
        return "\n".join(lines).strip()
