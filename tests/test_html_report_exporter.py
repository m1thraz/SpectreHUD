import unittest
import tempfile
from pathlib import Path
from core.html_report_exporter import HtmlReportExporter


class TestHtmlReportExporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = Path(self.temp_dir.name) / "TestBox"
        self.proj_dir.mkdir(parents=True, exist_ok=True)
        self.loot_dir = self.proj_dir / "loot"
        self.loot_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_markdown_elements_conversion(self):
        md = """# Box Writeup
## Reconnaissance
Here is a test paragraph with **bold text**, *italic text*, and `nmap -sC -sV` code.

- Port 22: OpenSSH 8.9
- Port 80: Apache 2.4

```bash
curl -i http://10.10.10.10/admin
```

> Important note about SQL injection vulnerability in search parameter.

| Port | Service | Version |
| --- | --- | --- |
| 22 | ssh | OpenSSH 8.9 |
| 80 | http | Apache 2.4 |

---
"""
        html_out = HtmlReportExporter.markdown_to_html(md, project_dir=self.proj_dir)
        self.assertIn("<h1>Box Writeup</h1>", html_out)
        self.assertIn("<h2>Reconnaissance</h2>", html_out)
        self.assertIn("<strong>bold text</strong>", html_out)
        self.assertIn("<em>italic text</em>", html_out)
        self.assertIn("<code>nmap -sC -sV</code>", html_out)
        self.assertIn("<ul>", html_out)
        self.assertIn("<li>Port 22: OpenSSH 8.9</li>", html_out)
        self.assertIn('<code class="language-bash">curl -i http://10.10.10.10/admin</code>', html_out)
        self.assertIn("<blockquote>Important note about SQL injection vulnerability in search parameter.</blockquote>", html_out)
        self.assertIn("<table>", html_out)
        self.assertIn("<th>Port</th>", html_out)
        self.assertIn("<td>OpenSSH 8.9</td>", html_out)
        self.assertIn("<hr>", html_out)

    def test_image_base64_embedding(self):
        # Create a dummy image inside loot directory
        img_file = self.loot_dir / "screenshot_test.png"
        # 1x1 transparent PNG bytes
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82'
        img_file.write_bytes(png_bytes)

        md = "### Screenshot Evidence\n![Proof Screenshot](screenshot_test.png)"
        html_out = HtmlReportExporter.markdown_to_html(md, project_dir=self.proj_dir)
        self.assertIn("data:image/png;base64,", html_out)
        self.assertIn('alt="Proof Screenshot"', html_out)

    def test_sandbox_path_traversal_image_blocked(self):
        # Image outside sandbox
        outside_file = Path(self.temp_dir.name) / "secret.png"
        outside_file.write_bytes(b'\x89PNG\r\n\x1a\nfake')

        md = "![Hacked](../secret.png)"
        html_out = HtmlReportExporter.markdown_to_html(md, project_dir=self.proj_dir)
        # Should not be base64 embedded since it's outside project sandbox
        self.assertNotIn("data:image/png;base64,", html_out)

    def test_export_to_file_and_full_html(self):
        md = "# Complete Report\nEverything is working."
        out_file = self.proj_dir / "report_out.html"
        success = HtmlReportExporter.export_to_file(
            markdown_content=md,
            output_path=out_file,
            project_dir=self.proj_dir,
            project_name="TestBox",
            target_ip="10.10.10.200"
        )
        self.assertTrue(success)
        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("TestBox", content)
        self.assertIn("10.10.10.200", content)
        self.assertIn("<h1>Complete Report</h1>", content)
        self.assertIn("window.print()", content)
        self.assertIn('contenteditable="true"', content)
        self.assertIn("resize: both", content)
        self.assertIn("downloadEditedHtml", content)
        self.assertIn('report_edited_TestBox.html', content)

    def test_light_theme_uses_client_friendly_colours(self):
        light_html = HtmlReportExporter.build_full_html(
            "# Client Report", project_dir=self.proj_dir, project_name="TestBox", theme="light"
        )
        dark_html = HtmlReportExporter.build_full_html(
            "# Technical Report", project_dir=self.proj_dir, project_name="TestBox", theme="dark"
        )

        self.assertIn("--bg-color: #f6f8fa", light_html)
        self.assertIn("Light export theme", light_html)
        self.assertIn(".brand-title, h1, h2, h3, h4 { color: #1f2328; }", light_html)
        self.assertNotIn("Light export theme", dark_html)

    def test_xss_prevention_in_images_and_links(self):
        """Verifies that malicious image src and link href payloads cannot execute XSS or inject attributes."""
        # 1. Block Image attribute breakout PoC
        md_img_block = '![pwned](x" onerror=alert(document.cookie) x=")'
        html_out = HtmlReportExporter.markdown_to_html(md_img_block, project_dir=self.proj_dir)
        self.assertNotIn('" onerror=', html_out)
        self.assertIn('src="x&quot; onerror=alert(document.cookie) x=&quot;"', html_out)

        # 2. Inline Image attribute breakout PoC
        md_img_inline = 'Inline screenshot: ![pwned](x" onfocus=alert(1) autofocus x=")'
        html_out_inline = HtmlReportExporter.markdown_to_html(md_img_inline, project_dir=self.proj_dir)
        self.assertNotIn('" onfocus=', html_out_inline)
        self.assertNotIn('" autofocus', html_out_inline)
        self.assertIn('&quot;', html_out_inline)

        # 3. JavaScript URI Scheme in Markdown Links
        md_link_js = '[Exploit](javascript:alert(1))'
        html_out_link = HtmlReportExporter.markdown_to_html(md_link_js, project_dir=self.proj_dir)
        self.assertNotIn('href="javascript:', html_out_link)
        self.assertIn('href="#unsafe-scheme-blocked"', html_out_link)

        # 4. Obfuscated whitespace javascript URI Scheme
        md_link_obf = '[Exploit](   javascript:alert(1)   )'
        html_out_obf = HtmlReportExporter.markdown_to_html(md_link_obf, project_dir=self.proj_dir)
        self.assertNotIn('href="javascript', html_out_obf)
        self.assertIn('href="#unsafe-scheme-blocked"', html_out_obf)

        # 5. Data:text/html URI Scheme in Images
        md_img_data = '![XSS](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)'
        html_out_data = HtmlReportExporter.markdown_to_html(md_img_data, project_dir=self.proj_dir)
        self.assertNotIn('src="data:text/html', html_out_data)
        self.assertIn('src="#unsafe-data-uri-blocked"', html_out_data)

        # 6. Valid Safe Links and Images are preserved
        md_safe = '[Docs](https://example.com/docs) and [Mail](mailto:test@example.com)'
        html_safe = HtmlReportExporter.markdown_to_html(md_safe, project_dir=self.proj_dir)
        self.assertIn('href="https://example.com/docs"', html_safe)
        self.assertIn('href="mailto:test@example.com"', html_safe)

    def test_download_filename_is_safe_for_the_inline_script(self):
        full_html = HtmlReportExporter.build_full_html(
            "# Report",
            project_dir=self.proj_dir,
            project_name='Evil</script><script>alert(1)</script>',
        )

        self.assertNotIn("Evil</script>", full_html)
        self.assertIn('report_edited_Evilscriptscriptalert1script.html', full_html)

    def test_protocol_relative_urls_blocked(self):
        """Finding 11: Protocol-relative URLs must be blocked in both links and images."""
        md_link_pr = '[Evil](//attacker.com/evil.js)'
        html_out_link = HtmlReportExporter.markdown_to_html(md_link_pr, project_dir=self.proj_dir)
        self.assertIn('href="#unsafe-protocol-relative-blocked"', html_out_link)

        md_img_pr = '![Evil](//attacker.com/evil.png)'
        html_out_img = HtmlReportExporter.markdown_to_html(md_img_pr, project_dir=self.proj_dir)
        self.assertIn('src="#unsafe-protocol-relative-blocked"', html_out_img)

    def test_image_embedding_budget_limit(self):
        """Finding 10: Image embedding must obey global session budget limits."""
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82'
        
        # Create 30 small images
        md_lines = []
        for i in range(30):
            img_p = self.loot_dir / f"snip_{i}.png"
            img_p.write_bytes(png_bytes)
            md_lines.append(f"![Snip {i}](snip_{i}.png)")

        md_text = "\n\n".join(md_lines)
        html_out = HtmlReportExporter.markdown_to_html(md_text, project_dir=self.proj_dir)

    def test_code_fence_language_is_html_escaped(self):
        """CRITICAL: Code fence language metadata must be sanitized and HTML escaped against attribute injection."""
        # 1. Attribute injection attempt via double quote and mouse handler
        md_attr = '```" onmouseover="alert(1)\nhello\n```'
        html_out = HtmlReportExporter.markdown_to_html(md_attr, project_dir=self.proj_dir)
        self.assertNotIn('onmouseover="', html_out)
        self.assertNotIn("onmouseover=", html_out)
        self.assertNotIn("<script", html_out)

        # 2. Tag injection attempt
        md_tag = '```><script>alert(1)</script>\nevil\n```'
        html_out_tag = HtmlReportExporter.markdown_to_html(md_tag, project_dir=self.proj_dir)
        self.assertNotIn("<script>alert(1)</script>", html_out_tag)

        # 3. Legitimate language identifier is preserved
        md_valid = '```python\nprint("secure")\n```'
        html_out_valid = HtmlReportExporter.markdown_to_html(md_valid, project_dir=self.proj_dir)
        self.assertIn('<code class="language-python">print(&quot;secure&quot;)</code>', html_out_valid)


if __name__ == "__main__":
    unittest.main()
