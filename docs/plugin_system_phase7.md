# Plugin System Phase 7 - Packaged Runtime Validation

## Runtime invariant

Separately distributed plugins must behave the same through packaged SpectreHUD runtimes as
they do from source. Validation therefore executes the existing V1 Report Export capability
through the built application binary; importing the plugin with the development interpreter is
not considered sufficient.

The internal `--smoke-test-export-plugin` release switch exits before Qt or the desktop
application is imported. It discovers one supplied plugin root, validates configuration, executes
a synthetic report export, and writes a schema-versioned JSON result. This is host diagnostics,
not a new plugin capability or extension point.

## Required release cases

`scripts/smoke_test_plugin_bundle.py` runs all three cases against the packaged executable:

1. The complete platform bundle loads and produces a real DOCX artifact.
2. The same plugin without its `vendor` directory fails as `missing_dependency`.
3. The same plugin with its native `lxml` module deliberately corrupted fails as `load_failed`.

Neither failure may initialize the GUI, crash startup, or prevent another SpectreHUD invocation.
The bundle extractor also rejects paths that escape its destination.

## Platform coverage

- The Windows one-file executable and `windows-amd64` DOCX bundle pass all three cases locally.
- The release workflow repeats the checks on every Windows release build.
- The Debian job extracts the completed `.deb` and runs the same checks through
  `/opt/spectrehud/spectrehud`, using the Linux plugin bundle.
- The Debian staging tree owns `/usr/lib/spectrehud/plugins`, and its PyInstaller build now carries
  both bundled plugin manifests and their lazy loader modules just like the Windows build.

Linux runtime success remains CI-reported because a Windows host cannot execute the produced
ELF binary. A release must not be published unless that job passes.
