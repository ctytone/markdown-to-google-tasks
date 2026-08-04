# Google Tasks Importer

Google Tasks Importer v1.0 converts a small Markdown project file into an
ordered Google Tasks list. Markdown sections become parent tasks, and bullets
become subtasks beneath the corresponding parent.

The application provides an API-free preview mode, confirmation before real
execution, duplicate protection, OAuth token caching, and ASCII-only console
output for Windows PowerShell and Command Prompt.

## Requirements

- Python 3.9 or newer
- A Google account
- A Google Cloud project with the Google Tasks API enabled

## Installation

Install the runtime packages:

```powershell
python -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

For development and automated tests:

```powershell
python -m pip install -r requirements-dev.txt
```

## Authentication

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable the **Google Tasks API**.
4. Configure the OAuth consent screen.
5. Create an OAuth client ID for a **Desktop app**.
6. Download the client configuration.
7. Rename it to `credentials.json` and place it beside
   `import_project.py`.

The first `--execute` run opens a browser for Google authorization and creates
`token.json`. Later executions reuse or refresh that token automatically.
`--dry-run` never authenticates and never calls Google.

Treat `credentials.json` and `token.json` as secrets. Do not publish them or
commit them to a public repository.

## Markdown format

Use one project heading, followed by section headings and task bullets:

```markdown
# Release Test

## Planning
- Create folder
- Open VS Code

## Development
- Write parser
- Write tests

## Deployment
- Build executable
```

Rules:

- The first `#` heading is the task-list name.
- Every `##` heading becomes a parent task.
- Every `-` bullet becomes a subtask of the preceding parent.
- Blank lines and surrounding whitespace are ignored.
- Source order is preserved.
- Files must use the `.md` extension and UTF-8 encoding.

Markdown files may be stored anywhere. A `projects/` folder inside this project
is a convenient optional convention:

```text
Google_Tasks_Importer/
|-- projects/
|   |-- release.md
|   `-- personal.md
|-- import_project.py
`-- ...
```

## Command-line usage

Exactly one mode is required:

```text
python import_project.py project_file (--dry-run | --execute) [--force] [--verbose]
```

Arguments:

- `project_file` - required Markdown project path.
- `--dry-run` - displays the complete plan, then exits without prompting,
  authenticating, or calling Google.
- `--execute` - displays the plan, checks for duplicates, asks for
  confirmation, and executes approved operations.
- `--force` - skips the confirmation prompt in execution mode.
- `--verbose` - displays additional workflow information.

View built-in help:

```powershell
python import_project.py --help
```

## Examples

Preview a project safely:

```powershell
python import_project.py projects\release.md --dry-run
```

Execute with confirmation:

```powershell
python import_project.py projects\release.md --execute
```

Execute without confirmation:

```powershell
python import_project.py projects\release.md --execute --force
```

Add workflow details:

```powershell
python import_project.py projects\release.md --execute --verbose
```

## Expected dry-run output

```text
==================================================
Google Tasks Importer
==================================================

Project       : Release Test
Markdown File : projects\release.md
Mode          : Dry Run
Confirmation  : Not required

==================================================
Execution Plan
==================================================
[1] Create Task List
    Release Test

[2] Create Parent Task
    Planning

    [3] Create Subtask
        Create folder

    [4] Create Subtask
        Open VS Code

--------------------------------------------------
Summary
--------------------------------------------------

Task Lists  : 1
Parent Tasks: 1
Subtasks    : 2
Operations  : 4

==================================================
Nothing has been created.
==================================================
```

## Safety and duplicate handling

- Dry runs perform no Google API calls.
- Execution requires confirmation unless `--force` is supplied.
- An existing task list prevents all execution.
- Existing parent tasks and subtasks are skipped, never changed.
- Duplicate matching ignores case and surrounding whitespace.
- Existing tasks and lists are never deleted.

## Automated tests and coverage

Run the complete suite:

```powershell
python -m pytest
```

The suite mocks OAuth and Google API access. A safety fixture fails any test
that attempts an unmocked Google connection. Terminal coverage is displayed
automatically, and the HTML report is written to `htmlcov/index.html`.

Pytest's persistent cache is disabled. Tests use isolated temporary directories
created and removed by the same process, avoiding stale Windows permission
problems.

## Troubleshooting

### Usage is displayed instead of importing

Supply exactly one mode:

```powershell
python import_project.py project.md --dry-run
```

or:

```powershell
python import_project.py project.md --execute
```

### `credentials.json` is missing

Download a Desktop app OAuth client from Google Cloud and place it beside
`import_project.py`. Dry-run mode does not require credentials.

### Authorization or scope errors

Confirm that the Google Tasks API is enabled and that the OAuth client is a
Desktop app. If permissions changed, move the existing `token.json` to a secure
backup location and execute again to authorize a new token.

### A task list already exists

The importer intentionally refuses to modify an existing destination list.
Rename the Markdown project heading or remove the destination manually only if
that is genuinely intended.

### Pytest reports temp-directory permission errors

Confirm that the latest `pyproject.toml` and `tests/conftest.py` are present.
The current suite does not use pytest's shared numbered temp root or persistent
cache.

## Project architecture

```text
Markdown
   |
   v
Markdown Parser
   |
   v
Project Model
   |
   v
Execution Plan
   |
   v
Execution Engine
   |
   v
Google Tasks API
```

Each layer has one responsibility: parsing, modeling, planning, execution, or
API communication. `import_project.py` is the only executable entry point.
