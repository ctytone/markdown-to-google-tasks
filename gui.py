"""Desktop window for the Google Tasks importer.

Flow: pick a Markdown file -> review the list it will create -> Import. The
preview is drawn like the resulting Google Tasks list, and each row's circle
fills in as that item is created, so the list itself shows progress.

Google sign-in and API calls run on a worker thread; the worker reports back
through a queue that the Tk main loop polls, because Tk widgets must only be
touched from the main thread.
"""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import queue
import sys
import threading
from typing import Any
import webbrowser

from auth import get_service
from config import BASE_DIR, CREDENTIALS_FILE
from execution_engine import (
    ExecutionProgress,
    execute_plan,
    has_duplicate_task_list,
)
from execution_plan import (
    CreateParentTaskOperation,
    CreateSubtaskOperation,
    ExecutionPlan,
    build_execution_plan,
)
from markdown_parser import MarkdownFormatError, parse_markdown

Event = tuple[Any, ...]
Post = Callable[[Event], None]

GOOGLE_TASKS_URL = "https://tasks.google.com/"

# Window size in unscaled pixels: a landscape window with a control column on
# the left and the list preview on the right.
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 540
MIN_WIDTH = 760
MIN_HEIGHT = 440
SIDEBAR_WIDTH = 300

# Design tokens: dark glass.
# With the Windows acrylic backdrop, pure black pixels become see-through
# blurred glass and other colors are added on top of the blur. Dark tints
# therefore read as frosted panels, and text must be light to stay legible.
GLASS = "#000000"  # Becomes the blurred backdrop. Use only for the window.
FALLBACK_BACKGROUND = "#161A21"  # Used when acrylic is unavailable.
SURFACE = "#1E222B"  # Frosted panel tint.
CONTROL = "#2A2F3A"
CONTROL_HOVER = "#363C49"
EDGE = "#566072"  # Hairline highlight around glass shapes.
INK = "#F4F6FA"
MUTED = "#AEB6C3"
ACCENT = "#1F45B5"
ACCENT_HOVER = "#2C55C8"
ACCENT_SOFT = "#8DB0FF"
DISABLED = "#2A2F3A"
ERROR = "#FF8F85"
SUCCESS = "#7FDCA6"
# Acrylic tint as 0xAABBGGRR: about 80% of #14171D, so light text and the
# accent colors stay readable even when a white window sits behind the app.
GLASS_TINT = 0xCC1D1714
# Google Sans ships in assets/fonts (SIL OFL, bundled unmodified). Segoe UI
# Variable is the fallback if it can't be loaded.
FONT_FILE = "GoogleSans[GRAD,opsz,wght].ttf"
GOOGLE_FONT = "Google Sans"
FALLBACK_FONT = "Segoe UI Variable Text"
FALLBACK_DISPLAY_FONT = "Segoe UI Variable Display"
OPEN_MARK = "○"  # white circle
DONE_MARK = "●"  # black circle


def load_plan(file_path: str | Path) -> ExecutionPlan:
    """Parse a Markdown project and build its execution plan."""
    return build_execution_plan(parse_markdown(file_path))


def plan_rows(plan: ExecutionPlan) -> list[tuple[str, str]]:
    """Return ``(kind, title)`` rows in plan order.

    ``kind`` is ``"list"``, ``"parent"`` or ``"subtask"``. Row ``i`` matches
    operation ``i + 1`` in progress events.
    """
    rows: list[tuple[str, str]] = []
    for operation in plan:
        if isinstance(operation, CreateSubtaskOperation):
            rows.append(("subtask", operation.title))
        elif isinstance(operation, CreateParentTaskOperation):
            rows.append(("parent", operation.title))
        else:
            rows.append(("list", operation.title))
    return rows


def shorten_path(path: str | Path, limit: int = 56) -> str:
    """Shorten a long path from the middle, keeping the drive and folder."""
    text = str(path)
    if len(text) <= limit:
        return text
    keep = limit - 3
    head = keep // 3
    return f"{text[:head]}...{text[-(keep - head):]}"


def plan_summary(plan: ExecutionPlan) -> str:
    """Describe the plan's size in plain words."""
    parents = plan.parent_task_count
    subtasks = plan.subtask_count
    return (
        f"{parents} {'task' if parents == 1 else 'tasks'}, "
        f"{subtasks} {'subtask' if subtasks == 1 else 'subtasks'}"
    )


def run_import(plan: ExecutionPlan, post: Post) -> None:
    """Sign in and execute a plan, reporting each step through ``post``.

    Events: ("status", text), ("progress", current, total),
    ("duplicate", list_name), ("done", ExecutionResult), ("error", text).
    """
    try:
        post(("status", "Waiting for Google sign-in in your browser..."))
        service = get_service()

        post(("status", "Checking your existing lists..."))
        if has_duplicate_task_list(service, plan):
            post(("duplicate", plan.project_name))
            return

        def on_progress(progress: ExecutionProgress) -> None:
            if progress.completed:
                post(("progress", progress.current, progress.total))

        result = execute_plan(service, plan, progress_callback=on_progress)
    except Exception as error:  # Reported to the user, not swallowed.
        post(("error", str(error) or type(error).__name__))
        return
    post(("done", result))


def _apply_glass(window: Any) -> bool:  # pragma: no cover - UI only
    """Give the window a Windows acrylic backdrop; return whether it worked."""
    if sys.platform != "win32" or sys.getwindowsversion().build < 17134:
        return False
    try:
        import pywinstyles
        from pywinstyles.py_win_style import ChangeDWMAccent, detect

        pywinstyles.apply_style(window, "acrylic")
        # Re-apply acrylic (accent state 3) with a darker tint than the
        # library's default, which is fully transparent.
        ChangeDWMAccent(detect(window), 30, 3, color=GLASS_TINT)
    except Exception:
        return False
    return True


def centered_geometry(
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
    scaling: float = 1.0,
) -> str:
    """Return a CustomTkinter geometry string that centers the window.

    ``width``/``height`` are unscaled (CustomTkinter scales them), while the
    screen size and the returned offsets are physical pixels.
    """
    x = max(0, (screen_width - round(width * scaling)) // 2)
    y = max(0, (screen_height - round(height * scaling)) // 2)
    return f"{width}x{height}+{x}+{y}"


def asset_path(*parts: str) -> Path:
    """Return a bundled asset path, inside the exe or the source tree."""
    root = getattr(sys, "_MEIPASS", None)
    return (Path(root) if root else BASE_DIR).joinpath("assets", *parts)


def _load_google_sans() -> bool:  # pragma: no cover - UI only
    """Register the bundled Google Sans for this process only."""
    import customtkinter as ctk

    font_file = asset_path("fonts", FONT_FILE)
    return font_file.is_file() and bool(
        ctk.FontManager.load_font(str(font_file))
    )


def _run_app(initial_file: str | None) -> None:  # pragma: no cover - UI only
    """Build and run the window."""
    import customtkinter as ctk
    from tkinter import filedialog, messagebox

    ctk.set_appearance_mode("dark")
    if _load_google_sans():
        body_font = display_font = GOOGLE_FONT
    else:
        body_font, display_font = FALLBACK_FONT, FALLBACK_DISPLAY_FONT

    root = ctk.CTk(fg_color=GLASS)
    root.title("Google Tasks Importer")
    root.minsize(MIN_WIDTH, MIN_HEIGHT)
    root.update_idletasks()
    root.geometry(
        centered_geometry(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            root.winfo_screenwidth(),
            root.winfo_screenheight(),
            ctk.ScalingTracker.get_window_scaling(root),
        )
    )
    # Left: controls in a fixed-width column. Right: the list preview.
    root.columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    events: queue.Queue[Event] = queue.Queue()
    state: dict[str, Any] = {"plan": None, "busy": False, "done": False}
    marks: list[Any] = []

    def font(size: int, weight: str = "normal", display: bool = False) -> Any:
        family = display_font if display else body_font
        return ctk.CTkFont(family=family, size=size, weight=weight)

    side = ctk.CTkFrame(root, fg_color="transparent", width=SIDEBAR_WIDTH)
    side.grid(row=0, column=0, sticky="nsew", padx=(28, 0), pady=(24, 24))
    side.columnconfigure(0, weight=1)
    side.rowconfigure(2, weight=1)  # Push status and Import to the bottom.

    # Header.
    header = ctk.CTkFrame(side, fg_color="transparent")
    header.grid(row=0, column=0, sticky="ew")
    ctk.CTkLabel(
        header,
        text="Google Tasks Importer",
        font=font(22, "bold", display=True),
        text_color=INK,
    ).pack(anchor="w")
    ctk.CTkLabel(
        header,
        text="Turn a Markdown outline into a task list.",
        font=font(13),
        text_color=MUTED,
        justify="left",
        wraplength=SIDEBAR_WIDTH - 20,
    ).pack(anchor="w")

    # File.
    file_box = ctk.CTkFrame(side, fg_color="transparent")
    file_box.grid(row=1, column=0, sticky="ew", pady=(28, 0))
    file_name = ctk.CTkLabel(
        file_box,
        text="No file chosen",
        font=font(14, "bold"),
        text_color=MUTED,
        anchor="w",
    )
    file_name.pack(anchor="w")
    file_folder = ctk.CTkLabel(
        file_box, text="", font=font(12), text_color=MUTED, anchor="w"
    )
    file_folder.pack(anchor="w")
    choose_button = ctk.CTkButton(
        file_box,
        text="Choose file",
        width=120,
        height=34,
        corner_radius=8,
        font=font(13),
        fg_color=CONTROL,
        hover_color=CONTROL_HOVER,
        text_color=INK,
        text_color_disabled=MUTED,
        border_width=1,
        border_color=EDGE,
    )
    choose_button.pack(anchor="w", pady=(10, 0))

    # Status and the main action, anchored to the bottom of the column.
    footer = ctk.CTkFrame(side, fg_color="transparent")
    footer.grid(row=3, column=0, sticky="ew")
    status = ctk.CTkLabel(
        footer,
        text="",
        font=font(13),
        text_color=MUTED,
        anchor="w",
        justify="left",
        wraplength=SIDEBAR_WIDTH - 20,
    )
    status.pack(anchor="w", fill="x", pady=(0, 10))
    action_button = ctk.CTkButton(
        footer,
        text="Import to Google Tasks",
        height=40,
        corner_radius=20,
        font=font(14, "bold"),
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        text_color="#FFFFFF",
        text_color_disabled=MUTED,
        state="disabled",
    )

    # The list preview: the one prominent surface in the window.
    sheet = ctk.CTkScrollableFrame(
        root,
        fg_color=SURFACE,
        corner_radius=14,
        border_width=1,
        border_color=EDGE,
        scrollbar_button_color=EDGE,
        scrollbar_button_hover_color=MUTED,
    )
    sheet.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
    action_button.pack(fill="x")

    def set_status(text: str, color: str = MUTED) -> None:
        status.configure(text=text, text_color=color)

    def clear_sheet() -> None:
        for child in sheet.winfo_children():
            child.destroy()
        marks.clear()

    def show_message(title: str, body: str, color: str = INK) -> None:
        clear_sheet()
        ctk.CTkLabel(
            sheet,
            text=title,
            font=font(15, "bold"),
            text_color=color,
            anchor="w",
        ).pack(anchor="w", padx=22, pady=(22, 4))
        ctk.CTkLabel(
            sheet,
            text=body,
            font=font(13),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=420,
        ).pack(anchor="w", padx=22)

    def show_plan(plan: ExecutionPlan) -> None:
        clear_sheet()
        for kind, title in plan_rows(plan):
            if kind == "list":
                ctk.CTkLabel(
                    sheet,
                    text=title,
                    font=font(19, "bold", display=True),
                    text_color=INK,
                    anchor="w",
                    justify="left",
                    wraplength=420,
                ).pack(anchor="w", padx=22, pady=(16, 0))
                ctk.CTkLabel(
                    sheet,
                    text=plan_summary(plan),
                    font=font(12),
                    text_color=MUTED,
                    anchor="w",
                ).pack(anchor="w", padx=22, pady=(0, 2))
                marks.append(None)  # The list has no circle.
                continue

            is_parent = kind == "parent"
            row = ctk.CTkFrame(sheet, fg_color="transparent")
            row.pack(
                fill="x",
                padx=(22 if is_parent else 48, 22),
                pady=(6 if is_parent else 0, 0),
            )
            mark = ctk.CTkLabel(
                row,
                text=OPEN_MARK,
                width=20,
                font=ctk.CTkFont(
                    family="Segoe UI Symbol", size=16 if is_parent else 13
                ),
                text_color=ACCENT_SOFT if is_parent else MUTED,
            )
            mark.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(
                row,
                text=title,
                font=font(14, "bold") if is_parent else font(13),
                text_color=INK,
                anchor="w",
                justify="left",
                wraplength=380 if is_parent else 350,
            ).pack(side="left", anchor="n")
            marks.append(mark)
        ctk.CTkFrame(sheet, fg_color="transparent", height=18).pack()

    def refresh_buttons() -> None:
        busy = state["busy"]
        choose_button.configure(state="disabled" if busy else "normal")
        if state["done"]:
            action_button.configure(text="Open Google Tasks", state="normal")
        else:
            ready = not busy and state["plan"] is not None
            action_button.configure(
                text="Importing..." if busy else "Import to Google Tasks",
                state="normal" if ready else "disabled",
            )
        enabled = action_button.cget("state") == "normal"
        action_button.configure(fg_color=ACCENT if enabled else DISABLED)

    def open_file(path: str) -> None:
        file_path = Path(path)
        file_name.configure(text=file_path.name, text_color=INK)
        file_folder.configure(text=shorten_path(file_path.parent, limit=40))
        state["done"] = False
        try:
            plan = load_plan(file_path)
        except (OSError, UnicodeError, ValueError, MarkdownFormatError) as error:
            state["plan"] = None
            show_message("This file can't be imported", str(error), ERROR)
            set_status("Fix the file, then choose it again.")
        else:
            state["plan"] = plan
            show_plan(plan)
            set_status("Check the list, then import it.")
        refresh_buttons()

    def choose_file() -> None:
        path = filedialog.askopenfilename(
            title="Choose a Markdown outline",
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
        )
        if path:
            open_file(path)

    def on_action() -> None:
        if state["done"]:
            webbrowser.open(GOOGLE_TASKS_URL)
            return
        plan = state["plan"]
        if plan is None or state["busy"]:
            return
        if not messagebox.askyesno(
            "Import to Google Tasks",
            f"Create the list \"{plan.project_name}\" with "
            f"{plan_summary(plan)}?",
        ):
            return
        state["busy"] = True
        refresh_buttons()
        threading.Thread(
            target=run_import, args=(plan, events.put), daemon=True
        ).start()

    def mark_done(row_index: int) -> None:
        if 0 <= row_index < len(marks) and marks[row_index] is not None:
            marks[row_index].configure(text=DONE_MARK, text_color=ACCENT_SOFT)

    def poll_events() -> None:
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "status":
                set_status(event[1])
            elif kind == "progress":
                current, total = event[1], event[2]
                mark_done(current - 1)
                set_status(f"Creating {current} of {total}...")
            elif kind == "duplicate":
                state["busy"] = False
                set_status(
                    f"You already have a list named \"{event[1]}\". Rename "
                    "the # heading in the file, or delete that list in "
                    "Google Tasks, then import again.",
                    ERROR,
                )
            elif kind == "done":
                result = event[1]
                state["busy"] = False
                state["done"] = True
                created = result.parent_tasks_created + result.subtasks_created
                set_status(
                    f"Done. Imported {created} items.",
                    SUCCESS,
                )
            elif kind == "error":
                state["busy"] = False
                set_status(f"Import stopped: {event[1]}", ERROR)
            refresh_buttons()
        root.after(100, poll_events)

    choose_button.configure(command=choose_file)
    action_button.configure(command=on_action)

    if CREDENTIALS_FILE.is_file():
        show_message(
            "Choose a Markdown file",
            "Use one # heading for the list name, ## headings for tasks, and "
            "- bullets for subtasks. You'll see the list here before "
            "anything is created.",
        )
    else:
        show_message(
            "Google sign-in isn't set up yet",
            "Put your credentials.json file in this folder:\n"
            f"{CREDENTIALS_FILE.parent}\n\n"
            "You can still preview files without it.",
        )
    if not _apply_glass(root):
        root.configure(fg_color=FALLBACK_BACKGROUND)
    refresh_buttons()
    if initial_file:
        open_file(initial_file)

    root.after(100, poll_events)
    root.mainloop()


def main() -> None:  # pragma: no cover - UI only
    """Launch the window, opening a file passed on the command line."""
    # A windowed executable has no console; give libraries that print
    # somewhere harmless to write.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    _run_app(sys.argv[1] if len(sys.argv) > 1 else None)


if __name__ == "__main__":  # pragma: no cover
    main()
