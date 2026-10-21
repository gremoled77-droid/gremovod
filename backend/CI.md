# Backend suite — offline run

The backend suite runs on a temporary SQLite database and never calls a paid provider.
This note is the local counterpart of `.github/workflows/studio-offline-ci.yml`.

## What the CI runs

| Job | Command | Blocking |
|---|---|---|
| `backend-unit` | `python -X utf8 -m unittest <every backend/test_*.py except the media group>` | yes |
| `backend-media` | `python -X utf8 -m unittest backend.test_media_qc backend.test_n35_freeze` | no, informational |

The media group needs FFmpeg/FFprobe and compares exact media properties, so it runs
in its own job with FFmpeg installed. It is informational until one green run on the
Linux runner proves the same expectations there.

## Running it locally

```powershell
$py = "C:\Users\BLOWKA\Documents\Minimax\.venv-audit\Scripts\python.exe"
cd C:\Users\BLOWKA\Documents\Minimax\gremovod
$env:STUDIO_DATA_DIR = Join-Path $env:TEMP "gremovod-ci-db"
& $py -X utf8 -m unittest discover -s backend -p "test_*.py"
```

`STUDIO_DATA_DIR` points the Studio database at a temporary directory. The tests also
create their own temporary database in `setUp`, so the variable is a second line of
defence: nothing may be written into the working tree.

## What the suite does not cover

- No paid provider is called. Provider paths are mocked.
- No Studio server on port 8000 or 5173 is contacted.
- No production SQLite, media or credentials are touched.
- A release master, its QC and the owner decision are not verified here. That is a
  separate task.

## Adding a test

A new `backend/test_*.py` module is picked up automatically: the CI computes the
module list at run time rather than from a hardcoded list. Keep the media group
(`test_media_qc.py`, `test_n35_freeze.py`) out of the unit job — it belongs to the
media job with FFmpeg installed.
