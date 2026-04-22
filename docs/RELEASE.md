# Release process

## Windows installer

The real Windows installer is produced on `windows-latest` by `.github/workflows/release-windows.yml` when a `v*.*.*` tag is pushed. The workflow installs `autoshelf[all]`, runs `python packaging/build.py --target windows`, and uploads:

- `dist/autoshelf-2.1.0-win-x64-setup.exe`
- `dist/autoshelf-2.1.0-win-x64-setup.exe.sha256`
- `dist/build-metadata.json`

The installer is an Inno Setup build over a PyInstaller one-dir output. It creates GUI and CLI shortcuts, registers `.autoshelf-plan`, optionally adds the CLI directory to PATH, and preserves `%LOCALAPPDATA%\autoshelf` unless the uninstall checkbox for local data removal is selected.

## Linux development dry run

This repository can validate the Windows package shape on Linux without producing a PE executable:

```bash
python packaging/build.py --target windows-dry-run
```

That command renders the Inno Setup template, generates the app icon if needed, audits the files that would be packaged, writes `dist/build-metadata.json`, and emits a placeholder SHA-256 file. If Wine and `iscc.exe` are installed, `--target windows --cross-from-linux` can be used; otherwise the command fails with a clear tooling error.

## Signing

If `AUTOSHELF_SIGNING_CERT` and `AUTOSHELF_SIGNING_PASS` are set on the Windows builder, `packaging/build.py` signs the installer with `signtool.exe`. Without those variables, the build succeeds unsigned and prints a warning.
