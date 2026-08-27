import unittest
from core.fuzzy_matcher import FuzzyMatcher


class TestFuzzyMatcher(unittest.TestCase):

    def setUp(self):
        self.sample_snippets = [
            {
                "id": "1",
                "title": "Nmap Standard Fast Scan",
                "template": "nmap -sC -sV -oN nmap.txt {{TARGET_IP}}",
                "description": "Scans top 1000 ports with default safe scripts and version detection",
                "category": "Network & Recon",
                "tags": ["recon", "nmap", "portscan", "network"]
            },
            {
                "id": "2",
                "title": "SQLMap Automated SQLi Dump",
                "template": "sqlmap -u {{TARGET_URL}} --dump --batch",
                "description": "Automated SQL injection tool to dump database tables",
                "category": "Web Exploitation",
                "tags": ["web", "sql", "sqli", "injection"]
            },
            {
                "id": "3",
                "title": "Remote Code Execution via Web Shell",
                "template": "curl http://{{TARGET_IP}}/shell.php?cmd={{COMMAND}}",
                "description": "Execute arbitrary bash commands via PHP web shell backdoor",
                "category": "Web Exploitation",
                "tags": ["web", "rce", "webshell", "exploit"]
            },
            {
                "id": "4",
                "title": "Local File Inclusion Wordlist Fuzzing",
                "template": "ffuf -u http://{{TARGET_IP}}/page.php?file=FUZZ -w {{WORDLIST}}",
                "description": "Fuzzing parameter for directory traversal and LFI vulnerabilities",
                "category": "Web Exploitation",
                "tags": ["web", "lfi", "traversal", "ffuf"]
            },
            {
                "id": "5",
                "title": "Windows Privilege Escalation via WinPEAS",
                "template": "winpeas.exe quiet cmd fast",
                "description": "Automated Windows local privilege escalation enumeration binary",
                "category": "Windows & Active Directory",
                "tags": ["windows", "privesc", "winpeas", "ad"]
            },
            {
                "id": "6",
                "title": "Linux SUID Binary Search",
                "template": "find / -perm -u=s -type f 2>/dev/null",
                "description": "Find binaries with SUID bit set for Linux privilege escalation",
                "category": "Linux & Shells",
                "tags": ["linux", "privesc", "suid", "enum"]
            },
            {
                "id": "7",
                "title": "Chisel Reverse Pivot Tunnel",
                "template": "chisel client {{LOCAL_HOST}}:8000 R:socks",
                "description": "Fast TCP/UDP tunnel over HTTP with SSH-like port forwarding",
                "category": "Network & Pivoting",
                "tags": ["pivoting", "chisel", "tunnel", "network"]
            }
        ]

    def test_exact_tool_name_prioritization(self):
        ranked = FuzzyMatcher.rank_snippets(self.sample_snippets, "nmap")
        self.assertEqual(ranked[0]["id"], "1")
        self.assertEqual(ranked[0]["title"], "Nmap Standard Fast Scan")

    def test_tool_prefix_match(self):
        ranked = FuzzyMatcher.rank_snippets(self.sample_snippets, "nma")
        self.assertEqual(ranked[0]["id"], "1")

        ranked_sql = FuzzyMatcher.rank_snippets(self.sample_snippets, "sqlm")
        self.assertEqual(ranked_sql[0]["id"], "2")

    def test_acronym_matching(self):
        # 'rce' matches 'Remote Code Execution'
        ranked_rce = FuzzyMatcher.rank_snippets(self.sample_snippets, "rce")
        self.assertTrue(any(s["id"] == "3" for s in ranked_rce))
        self.assertEqual(ranked_rce[0]["id"], "3")

        # 'lfi' matches 'Local File Inclusion'
        ranked_lfi = FuzzyMatcher.rank_snippets(self.sample_snippets, "lfi")
        self.assertEqual(ranked_lfi[0]["id"], "4")

    def test_typo_tolerance(self):
        # 'nmp' should match 'nmap'
        ranked_nmp = FuzzyMatcher.rank_snippets(self.sample_snippets, "nmp")
        self.assertGreaterEqual(len(ranked_nmp), 1)
        self.assertEqual(ranked_nmp[0]["id"], "1")

        # 'chisl' should match 'chisel'
        ranked_chisl = FuzzyMatcher.rank_snippets(self.sample_snippets, "chisl")
        self.assertGreaterEqual(len(ranked_chisl), 1)
        self.assertEqual(ranked_chisl[0]["id"], "7")

    def test_multi_token_and_filtering(self):
        # 'windows privesc' must match Windows Privilege Escalation (id: 5), NOT Linux (id: 6)
        ranked_win = FuzzyMatcher.rank_snippets(self.sample_snippets, "windows privesc")
        self.assertEqual(len(ranked_win), 1)
        self.assertEqual(ranked_win[0]["id"], "5")

        # 'linux privesc' must match Linux SUID Binary Search (id: 6)
        ranked_lin = FuzzyMatcher.rank_snippets(self.sample_snippets, "linux privesc")
        self.assertEqual(len(ranked_lin), 1)
        self.assertEqual(ranked_lin[0]["id"], "6")

    def test_tag_match_weights(self):
        ranked_suid = FuzzyMatcher.rank_snippets(self.sample_snippets, "suid")
        self.assertEqual(ranked_suid[0]["id"], "6")

    def test_empty_query_returns_original(self):
        ranked_empty = FuzzyMatcher.rank_snippets(self.sample_snippets, "")
        self.assertEqual(len(ranked_empty), len(self.sample_snippets))

        ranked_whitespace = FuzzyMatcher.rank_snippets(self.sample_snippets, "   ")
        self.assertEqual(len(ranked_whitespace), len(self.sample_snippets))

    def test_result_limit(self):
        ranked_limited = FuzzyMatcher.rank_snippets(self.sample_snippets, "", limit=3)
        self.assertEqual(len(ranked_limited), 3)


if __name__ == "__main__":
    unittest.main()
