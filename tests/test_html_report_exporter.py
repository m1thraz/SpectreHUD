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


if __name__ == "__main__":
    unittest.main()
