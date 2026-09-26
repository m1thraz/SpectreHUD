# SpectreHUD DOCX Plugin

This is the first separately distributed SpectreHUD export plugin. Its source remains in the
main repository as the V1 reference implementation, but it is discovered and loaded through
the same folder boundary intended for a future standalone repository.

The implementation imports only the stable
[`spectrehud_plugin_api`](../../docs/export_plugin_api_v1.md) facade. Its manifest declares API
V1, plugin version `0.1.0`, the minimum compatible host, and plugin-owned German metadata.

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

Use the bundle matching the operating system and CPU architecture. Its `vendor` directory is part
of the plugin and must be copied with it; installing `python-docx` into SpectreHUD itself is not
required.
