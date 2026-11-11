# Google Tasks Importer

> **A small personal tool.** This is one of the little programs I made to make
> my own life a bit easier. It does one thing, it does it well enough for me,
> and it's finished. It isn't a product, isn't supported, and probably won't get
> new features. You're welcome to use or fork it, but you'll need your own
> Google Cloud credentials (see below).

Write a project outline in Markdown, pick the file, click **Import**, and it
shows up in Google Tasks as a list with parent tasks and subtasks.

```markdown
# Release Test          <- becomes the task list

## Planning             <- parent task
- Create folder         <- subtask
- Open VS Code

## Development
- Write parser
- Write tests
```

Rules: one `#` heading (the list name), `##` headings for parent tasks, `-`
bullets for subtasks. Blank lines are ignored, order is kept, and anything else
is rejected so nothing gets imported by accident. Files must be UTF-8 `.md`.

## Using it

1. Open **Google Tasks Importer.exe** (or drag a `.md` file onto it).
2. Click **Choose file** and pick your Markdown file. The preview shows
   the list exactly as it will appear, and each circle fills in as that task
   is created.
3. Click **Import to Google Tasks** and confirm.
4. The first time, a browser opens for Google sign-in. After that it remembers
   you.

If a list with the same name already exists, nothing is created. Rename the
`#` heading or delete the old list, then try again. The tool never edits or
deletes anything in Google Tasks.

## One-time Google setup

The app signs in through your own Google Cloud project:

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a
   project and enable the **Google Tasks API**.
2. Configure the OAuth consent screen (External), and add your own Google
   account as a test user.
3. Create an OAuth client ID of type **Desktop app** and download the JSON.
4. Rename it to `credentials.json` and put it in
   `%APPDATA%\Google Tasks Importer\`, or in the project folder before building
   to bake it into the exe.

**Weekly sign-in:** while the consent screen is in *Testing*, Google expires
the sign-in after 7 days, so the browser will open again about once a week. To
stop that, click **Publish app** on the consent screen. For a personal app you
don't need Google's verification; you'll just click through an "unverified app"
warning once when you sign in.

The saved sign-in lives at `%APPDATA%\Google Tasks Importer\token.json`. Delete
it to sign in fresh. Keep `credentials.json` and `token.json` private; both are
gitignored.

## Building the exe

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.\build.ps1
```

The result is `dist\Google Tasks Importer.exe`, a single file you can move
anywhere. Windows SmartScreen may warn about an unsigned app the first time; click
**More info -> Run anyway**.

## Command line and tests

The original command-line version still works:

```powershell
python import_project.py project.md --dry-run            # preview only, no Google access
python import_project.py project.md --execute [--force]  # import (confirms unless --force)
```

```powershell
.venv\Scripts\python -m pytest
```

The tests mock all Google access, and a safety fixture fails any test that
tries to reach a real account.

## Credits

The interface uses [Google Sans](https://github.com/googlefonts/googlesans),
included unmodified under the SIL Open Font License (`assets/fonts/OFL.txt`).
The frosted-glass window uses Windows acrylic via
[pywinstyles](https://github.com/Akascape/py-window-styles).

## How it fits together

Markdown parser -> project model -> execution plan -> execution engine ->
Google Tasks API. `gui.py` (the exe) and `import_project.py` (the CLI) are thin
front ends over the same pipeline.
