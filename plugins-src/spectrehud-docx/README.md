# SpectreHUD DOCX Plugin

This is the first separately distributed SpectreHUD export plugin. Its source remains in the
main repository while the V1 API is being validated, but it is discovered and loaded through
the same folder boundary intended for a future standalone repository.

The runtime bundle contains `plugin.json`, the `spectrehud_docx` package, and a platform-specific
`vendor` directory containing `python-docx` and its dependencies. The main SpectreHUD package
does not depend on `python-docx`.

For development:

```bash
python -m pip install -e ./plugins-src/spectrehud-docx
python -m pytest plugins-src/spectrehud-docx/tests -q
```

Build a platform-specific folder bundle, including its dependencies:

```bash
python plugins-src/spectrehud-docx/build_bundle.py
```

Extract the resulting ZIP so the application sees one of these layouts:

```text
SpectreHUD.exe
plugins/spectrehud-docx/plugin.json

/usr/lib/spectrehud/plugins/spectrehud-docx/plugin.json
```
