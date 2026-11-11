# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A finished personal tool; the owner wants it kept small and simple, not grown into a product. A Python 3.9+ app that turns a constrained Markdown file into a Google Tasks list: the first `#` heading becomes the task list, each `##` heading becomes a parent task, and each `-` bullet becomes a subtask of the preceding parent. Any other content is rejected with `MarkdownFormatError`. There are two front ends over the same pipeline: `gui.py` (tkinter, packaged as the exe) and `import_project.py` (CLI). The modules sit flat at the repo root (no package), and tests import them by bare module name.

## Commands

Use the project venv (`.venv`, Python 3.14 locally):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # runtime deps + pytest + pyinstaller

.venv\Scripts\python -m pytest                                  # full suite + coverage (term + htmlcov/)
.venv\Scripts\python -m pytest tests/test_markdown_parser.py    # one file
.venv\Scripts\python -m pytest tests/test_gui.py::test_name     # one test

.venv\Scripts\python gui.py [file.md]                            # run the GUI from source
.venv\Scripts\python import_project.py test_markdown.md --dry-run  # CLI preview, no auth, no API calls
.\build.ps1                                                       # -> dist\Google Tasks Importer.exe (onefile, windowed)
```

`build.ps1` bakes `credentials.json` into the exe only if it exists in the repo root at build time.

`pyproject.toml` adds coverage flags to every pytest run and turns off the cache provider (`-p no:cacheprovider`). If you add a new top-level module, also add a matching `--cov=<module>` entry there.

## Architecture

The pipeline is strictly layered, and each module has a single job:

`markdown_parser.parse_markdown` → `models.Project`/`Section` → `execution_plan.build_execution_plan` → `ExecutionPlan` (immutable tuple of `CreateTaskListOperation` / `CreateParentTaskOperation` / `CreateSubtaskOperation`) → `execution_engine.execute_plan` → `tasks_api` (raw `service.tasklists()` / `service.tasks()` calls).

- `import_project.main` handles orchestration only: parse, plan, preview, then either exit (dry run) or authenticate → duplicate-list check → confirm → execute. It returns an exit code and never calls `sys.exit` itself.
- `execution_engine` is the only layer that turns operations into API calls. It runs operations in order and stops at the first exception, with no rollback. It reports progress to an optional callback before and after each operation (`ExecutionProgress`). `utils.print_execution_progress` is the console implementation of that callback.
- Duplicate semantics: if a task list with the same title already exists (case- and whitespace-insensitive), the whole run is aborted. Inside the newly created list, parent tasks and subtasks whose titles match one already created or found are skipped, never updated. `tasks_api._iter_tasks` pages through results and includes completed and hidden tasks.
- `models.Section`/`Project` are dataclasses that also implement `Mapping`, so the older dict-style access (`project["sections"]`) and comparisons against plain dicts still work. Keep that compatibility when you change fields.
- Adding a new operation type touches `execution_plan` (dataclass + `Operation` union + counts), `execution_engine.execute_plan` (dispatch, which otherwise raises `TypeError`), and `utils.operation_name`.
- `gui.py` uses CustomTkinter (the only UI dependency; `build.ps1` passes `--collect-data customtkinter` so its theme files get bundled). Testable logic stays free of Tk: `load_plan`, `plan_rows`, `plan_summary`, `shorten_path`, and `run_import(plan, post)`. `run_import` runs on a worker thread and reports `("status"|"progress"|"duplicate"|"done"|"error", ...)` tuples through a queue that the Tk loop polls every 100ms. Never touch widgets from the worker. The preview mirrors the resulting list: `plan_rows(plan)[i]` matches operation `i + 1`, so a progress event fills in that row's circle. Design tokens (colors, fonts, window size) are constants at the top of `gui.py`. The look is dark glass: `_apply_glass` uses pywinstyles to give the window a Windows acrylic backdrop (with a dark `GLASS_TINT`), and falls back to `FALLBACK_BACKGROUND` if that fails. With acrylic, pure `#000000` pixels become blurred glass and every other color is blended additively on top, so keep text light and never use `#000000` except for the window background. The UI font is Google Sans, bundled unmodified in `assets/fonts` (OFL; Google's trademark terms only allow the name on the original file, so don't subset or instance it). It's loaded per-process with `FontManager.load_font`, with Segoe UI Variable as the fallback, and `build.ps1` adds `assets/` to the exe. The window opens centered in a landscape layout (`centered_geometry`): controls on the left, the list preview on the right. The Tk code is in `_run_app` and is marked `# pragma: no cover`.
- `config.py` paths: `token.json` always lives in `%APPDATA%\Google Tasks Importer\` (a onefile exe's own directory is a temp folder that gets deleted). `credentials.json` is looked up in that folder first, then the PyInstaller bundle (`sys._MEIPASS`), then next to the exe or source. These values are computed at import time, so tests patch `auth.TOKEN_FILE` / `auth.CREDENTIALS_FILE` directly.

## Conventions and constraints

- A windowed exe has `sys.stdout`/`sys.stderr` set to None. `gui.main` redirects them to devnull; keep that.
- All console output must be ASCII-only so it renders in Windows PowerShell and cmd. Tests assert this with `output.encode("ascii")`. All user-facing printing goes through helpers in `utils.py`.
- `--dry-run` must never authenticate or touch the Google API.
- Tests must never reach Google. An autouse fixture in `tests/conftest.py` patches `import_project.get_service`, `gui.get_service`, `auth.Request`, `auth.InstalledAppFlow.from_client_secrets_file`, and `auth.build` so that any call raises. Tests should use the `google_service` MagicMock fixture, or patch these explicitly.
- `conftest.py` overrides `tmp_path` with a `tempfile.TemporaryDirectory` on purpose, to avoid Windows permission problems with pytest's shared temp root. Don't switch back to the built-in fixture or `tmp_path_factory`.
