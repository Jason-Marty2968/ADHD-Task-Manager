import json
import os
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext, ttk
import requests
import calendar
from datetime import date, datetime, timedelta

DATA_FILE = "adhd_data.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"


# ---------- Data Layer ----------

def load_data():
    """
    Load the JSON file or return a default structure if missing.
    Ensures all expected keys exist and normalizes task objects.
    """
    default = {
        "tasks": [],
        "reminders": [],
        "notes": []
    }

    if not os.path.exists(DATA_FILE):
        return default

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Ensure all expected keys exist.
        for key in default:
            if key not in data:
                data[key] = default[key]

        # Normalize task objects to ensure consistent structure.
        fixed_tasks = []
        for t in data["tasks"]:
            if isinstance(t, dict):
                fixed_tasks.append({
                    "title": t.get("title", ""),
                    "date": t.get("date", ""),
                    "notes": t.get("notes", ""),
                    "completed": bool(t.get("completed", False)),
                    "priority": t.get("priority", "normal"),
                })
            else:
                # Convert legacy string tasks into structured objects.
                fixed_tasks.append({
                    "title": str(t),
                    "date": "",
                    "notes": "",
                    "completed": False,
                    "priority": "normal",
                })
        data["tasks"] = fixed_tasks

        return data
    except Exception:
        return default


def save_data(data):
    """
    Write the current data structure to disk.
    """
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------- AI via Ollama ----------

def generate_ai_summary(prompt: str) -> str:
    """
    Send a prompt to the local Ollama model and return the generated text.
    This function is used by all AI summary modes.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip() or "(No response from model.)"
    except Exception as e:
        return f"(AI summary unavailable: {e})"


# ---------- Date Helpers ----------

def parse_task_date(dstr: str):
    """
    Parse a task date string (YYYY-MM-DD) into a date object.
    Returns None if the format is invalid or empty.
    """
    if not dstr:
        return None
    try:
        return datetime.strptime(dstr, "%Y-%m-%d").date()
    except ValueError:
        return None


def tasks_by_date(tasks):
    """
    Build a mapping from date -> list of tasks for that date.
    Only tasks with a valid date are included.
    """
    mapping = {}
    for t in tasks:
        d = parse_task_date(t.get("date", ""))
        if d is None:
            continue
        mapping.setdefault(d, []).append(t)
    return mapping


# ---------- AI Summary Builders ----------

def build_daily_summary_prompt(data):
    """
    Build a structured prompt for the AI to generate a daily summary.
    Includes tasks for today and tomorrow only.
    """

    today = date.today()
    tomorrow = today + timedelta(days=1)

    tasks_today = []
    tasks_tomorrow = []

    for t in data["tasks"]:
        d = parse_task_date(t.get("date", ""))
        if d is None:
            continue
        if d == today:
            tasks_today.append(t)
        elif d == tomorrow:
            tasks_tomorrow.append(t)

    def fmt(tasks):
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            status = "done" if t["completed"] else "pending"
            prio = t["priority"]
            notes = t["notes"] or ""
            line = f"- [{status}] ({prio}) {t['title']}"
            if notes:
                line += f"\n    notes: {notes}"
            lines.append(line)
        return "\n".join(lines)

    tasks_today_text = fmt(tasks_today)
    tasks_tomorrow_text = fmt(tasks_tomorrow)

    prompt = f"""
You are an ADHD-friendly assistant.

Here are my tasks for the next 24 hours:

Tasks for today ({today.isoformat()}):
{tasks_today_text}

Tasks for tomorrow ({tomorrow.isoformat()}):
{tasks_tomorrow_text}

Please:
- Give me a short, supportive summary of what I should focus on today and tomorrow.
- Highlight anything time-sensitive.
- Suggest 2–3 concrete next actions.
- Keep the tone kind and non-judgmental.
"""

    return prompt.strip()


def build_weekly_summary_prompt(data):
    """
    Build a structured prompt for the AI to generate a weekly summary.
    Includes tasks from today through next Saturday.
    """

    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    end_of_week = today + timedelta(days=days_until_saturday)

    weekly_tasks = []
    for t in data["tasks"]:
        d = parse_task_date(t.get("date", ""))
        if d is None:
            continue
        if today <= d <= end_of_week:
            weekly_tasks.append(t)

    def fmt(tasks):
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            status = "done" if t["completed"] else "pending"
            prio = t["priority"]
            date_str = t["date"] or "no date"
            notes = t["notes"] or ""
            line = f"- [{status}] ({prio}) {date_str} — {t['title']}"
            if notes:
                line += f"\n    notes: {notes}"
            lines.append(line)
        return "\n".join(lines)

    tasks_week_text = fmt(weekly_tasks)

    prompt = f"""
You are an ADHD-friendly assistant.

Here are my tasks for the rest of this week:

Week range: {today.isoformat()} → {end_of_week.isoformat()}

Tasks:
{tasks_week_text}

Please:
- Give me a weekly overview of what I have on my plate.
- Highlight anything that looks urgent or important.
- Suggest 3–5 next actions for the week.
- Keep the tone supportive and non-judgmental.
"""

    return prompt.strip()

# ---------- UI Helpers ----------

def show_list_popup(root, title, get_items, on_add=None, on_delete=None, on_edit=None, formatter=None):
    """
    Generic list popup. It receives a function (get_items) instead of a static list.
    This allows the list to refresh from the latest data after add/edit/delete.
    """
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("500x400")

    listbox = tk.Listbox(win, selectmode=tk.SINGLE)
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def render():
        # Always fetch the latest data instead of using a stale snapshot.
        items = get_items()
        listbox.delete(0, tk.END)
        for item in items:
            if formatter:
                listbox.insert(tk.END, formatter(item))
            else:
                listbox.insert(tk.END, str(item))

    render()

    btn_frame = tk.Frame(win)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    if on_add:
        tk.Button(btn_frame, text="Add", command=lambda: (on_add(win), render())).pack(side=tk.LEFT, padx=5)

    if on_edit:
        tk.Button(
            btn_frame,
            text="Edit",
            command=lambda: (
                on_edit(win, listbox.curselection()[0]) if listbox.curselection() else None,
                render()
            )
        ).pack(side=tk.LEFT, padx=5)

    if on_delete:
        tk.Button(
            btn_frame,
            text="Delete",
            command=lambda: (
                on_delete(win, listbox.curselection()[0]) if listbox.curselection() else None,
                render()
            )
        ).pack(side=tk.LEFT, padx=5)


def show_text_popup(root, title, initial_text=""):
    """
    Simple read-only text viewer for AI summaries.
    Used by both daily and weekly summary modes.
    """
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("500x400")

    text = scrolledtext.ScrolledText(win, wrap=tk.WORD)
    text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    text.insert(tk.END, initial_text)
    text.config(state=tk.DISABLED)


def show_tasks_for_date(root, tasks, target_date):
    """
    Helper to show a popup listing tasks for a specific date.
    This is used by the calendar views when a day is clicked.
    """
    win = tk.Toplevel(root)
    win.title(f"Tasks on {target_date.isoformat()}")
    win.geometry("500x400")

    listbox = tk.Listbox(win)
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    for t in tasks:
        status = "✓" if t.get("completed") else " "
        prio = t.get("priority", "normal")
        title = t.get("title", "")
        listbox.insert(tk.END, f"[{status}] ({prio}) {title}")

    if not tasks:
        listbox.insert(tk.END, "No tasks for this date.")


# ---------- Task Dialog ----------

def task_dialog(parent, task=None):
    """
    Modal dialog for creating or editing a task.
    Returns a dict with {"ok": bool, "task": {...}}.
    """
    dlg = tk.Toplevel(parent)
    dlg.title("Task" if task is None else "Edit Task")
    dlg.geometry("400x350")
    dlg.grab_set()

    title_var = tk.StringVar(value=(task["title"] if task else ""))
    date_var = tk.StringVar(value=(task["date"] if task else ""))
    notes_var = tk.StringVar(value=(task["notes"] if task else ""))
    completed_var = tk.BooleanVar(value=(task["completed"] if task else False))
    priority_var = tk.StringVar(value=(task["priority"] if task else "normal"))

    tk.Label(dlg, text="Title:").pack(anchor="w", padx=10, pady=(10, 0))
    title_entry = tk.Entry(dlg, textvariable=title_var)
    title_entry.pack(fill=tk.X, padx=10)

    tk.Label(dlg, text="Date (YYYY-MM-DD):").pack(anchor="w", padx=10, pady=(10, 0))
    date_entry = tk.Entry(dlg, textvariable=date_var)
    date_entry.pack(fill=tk.X, padx=10)

    tk.Label(dlg, text="Priority:").pack(anchor="w", padx=10, pady=(10, 0))
    priority_combo = ttk.Combobox(dlg, textvariable=priority_var, values=["low", "normal", "high"], state="readonly")
    priority_combo.pack(fill=tk.X, padx=10)
    if not task:
        priority_combo.set("normal")

    tk.Label(dlg, text="Notes:").pack(anchor="w", padx=10, pady=(10, 0))
    notes_text = scrolledtext.ScrolledText(dlg, height=5, wrap=tk.WORD)
    notes_text.pack(fill=tk.BOTH, expand=True, padx=10)
    notes_text.insert(tk.END, notes_var.get())

    completed_check = tk.Checkbutton(dlg, text="Completed", variable=completed_var)
    completed_check.pack(anchor="w", padx=10, pady=(5, 0))

    result = {"ok": False, "task": None}

    def on_ok():
        result["ok"] = True
        result["task"] = {
            "title": title_var.get().strip(),
            "date": date_var.get().strip(),
            "notes": notes_text.get("1.0", tk.END).strip(),
            "completed": completed_var.get(),
            "priority": priority_var.get()
        }
        dlg.destroy()

    def on_cancel():
        dlg.destroy()

    btn_frame = tk.Frame(dlg)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    tk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=5)
    tk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.RIGHT, padx=5)

    dlg.wait_window()
    return result

# ---------- Calendar Views ----------

class MonthGridView(tk.Frame):
    """
    Simple month grid view.
    Highlights days that have tasks and lets the user click a day to see tasks.
    """
    def __init__(self, parent, app, year, month):
        super().__init__(parent)
        self.app = app
        self.year = year
        self.month = month
        self.build()

    def build(self):
        for child in self.winfo_children():
            child.destroy()

        cal = calendar.Calendar(firstweekday=0)
        tasks_map = tasks_by_date(self.app.data["tasks"])

        # Header row with weekday names.
        header = tk.Frame(self)
        header.pack(fill=tk.X)
        for wd in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            tk.Label(header, text=wd, width=4, anchor="center").pack(side=tk.LEFT, expand=True)

        # Calendar grid.
        grid = tk.Frame(self)
        grid.pack(fill=tk.BOTH, expand=True)

        for week in calendar.monthcalendar(self.year, self.month):
            row = tk.Frame(grid)
            row.pack(fill=tk.X, expand=True)
            for day_num in week:
                if day_num == 0:
                    tk.Label(row, text="", width=4).pack(side=tk.LEFT, expand=True)
                else:
                    day_date = date(self.year, self.month, day_num)
                    has_tasks = day_date in tasks_map

                    def make_cmd(d=day_date):
                        return lambda: show_tasks_for_date(self.app.root, tasks_map.get(d, []), d)

                    btn_bg = "#d0f0d0" if has_tasks else self.cget("bg")
                    tk.Button(row, text=str(day_num), width=4, command=make_cmd(), bg=btn_bg).pack(
                        side=tk.LEFT, expand=True
                    )


class MonthSidebarView(tk.Frame):
    """
    Month grid on the left, task list for the selected day on the right.
    """
    def __init__(self, parent, app, year, month):
        super().__init__(parent)
        self.app = app
        self.year = year
        self.month = month
        self.selected_date = None
        self.tasks_map = tasks_by_date(self.app.data["tasks"])
        self.build()

    def build(self):
        for child in self.winfo_children():
            child.destroy()

        main = tk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = tk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Weekday header.
        header = tk.Frame(left)
        header.pack(fill=tk.X)
        for wd in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            tk.Label(header, text=wd, width=4, anchor="center").pack(side=tk.LEFT, expand=True)

        grid = tk.Frame(left)
        grid.pack(fill=tk.BOTH, expand=True)

        for week in calendar.monthcalendar(self.year, self.month):
            row = tk.Frame(grid)
            row.pack(fill=tk.X, expand=True)
            for day_num in week:
                if day_num == 0:
                    tk.Label(row, text="", width=4).pack(side=tk.LEFT, expand=True)
                else:
                    day_date = date(self.year, self.month, day_num)
                    has_tasks = day_date in self.tasks_map

                    def make_cmd(d=day_date):
                        return lambda: self.select_date(d)

                    btn_bg = "#d0f0d0" if has_tasks else self.cget("bg")
                    tk.Button(row, text=str(day_num), width=4, command=make_cmd(), bg=btn_bg).pack(
                        side=tk.LEFT, expand=True
                    )

        # Right side: task list for selected date.
        tk.Label(right, text="Tasks for selected day:").pack(anchor="w", padx=5, pady=(5, 0))
        self.listbox = tk.Listbox(right)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Auto-select today if it is in this month.
        today = date.today()
        if today.year == self.year and today.month == self.month:
            self.select_date(today)

    def select_date(self, d):
        self.selected_date = d
        self.listbox.delete(0, tk.END)
        tasks = self.tasks_map.get(d, [])
        if not tasks:
            self.listbox.insert(tk.END, "No tasks for this date.")
            return
        for t in tasks:
            status = "✓" if t.get("completed") else " "
            prio = t.get("priority", "normal")
            title = t.get("title", "")
            self.listbox.insert(tk.END, f"[{status}] ({prio}) {title}")


class WeekView(tk.Frame):
    """
    Simple week view.
    Shows one week at a time with tasks grouped by day.
    """
    def __init__(self, parent, app, year, month):
        super().__init__(parent)
        self.app = app
        self.year = year
        self.month = month

        # Anchor date for weekly navigation
        self.current_date = date(year, month, 1)

        self.build()

    def build(self):
        for child in self.winfo_children():
            child.destroy()

        tasks_map = tasks_by_date(self.app.data["tasks"])

        # Compute the Monday of the current week
        monday = self.current_date - timedelta(days=self.current_date.weekday())

        header = tk.Frame(self)
        header.pack(fill=tk.X)
        for i in range(7):
            d = monday + timedelta(days=i)
            tk.Label(header, text=f"{d.strftime('%a')} {d.day}", width=12, anchor="center").pack(
                side=tk.LEFT, expand=True
            )

        body = tk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)

        for i in range(7):
            d = monday + timedelta(days=i)
            col = tk.Frame(body, bd=1, relief=tk.SOLID)
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)

            tasks = tasks_map.get(d, [])
            if not tasks:
                tk.Label(col, text="No tasks", anchor="n").pack(fill=tk.X, pady=2)
            else:
                for t in tasks:
                    status = "✓" if t.get("completed") else " "
                    prio = t.get("priority", "normal")
                    title = t.get("title", "")
                    tk.Label(
                        col,
                        text=f"[{status}] ({prio}) {title}",
                        anchor="w",
                        wraplength=120,
                        justify="left"
                    ).pack(fill=tk.X, padx=2, pady=1)

    def shift_week(self, delta):
        """
        Move the weekly view forward/backward by delta weeks.
        """
        self.current_date = self.current_date + timedelta(days=7 * delta)
        self.build()


class AgendaView(tk.Frame):
    """
    Agenda view: chronological list of upcoming tasks.
    """
    def __init__(self, parent, app, year, month):
        super().__init__(parent)
        self.app = app
        self.year = year
        self.month = month
        self.build()

    def build(self):
        for child in self.winfo_children():
            child.destroy()

        tk.Label(self, text="Agenda (upcoming tasks):").pack(anchor="w", padx=10, pady=(10, 0))

        listbox = tk.Listbox(self)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        items = []
        for t in self.app.data["tasks"]:
            d = parse_task_date(t.get("date", ""))
            if d is None:
                continue
            items.append((d, t))

        items.sort(key=lambda x: (x[0], x[1].get("title", "")))

        if not items:
            listbox.insert(tk.END, "No dated tasks.")
            return

        for d, t in items:
            status = "✓" if t.get("completed") else " "
            prio = t.get("priority", "normal")
            title = t.get("title", "")
            listbox.insert(tk.END, f"{d.isoformat()}  [{status}] ({prio}) {title}")

# ---------- Main App ----------

class ADHDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ADHD Assistant (Local, Ollama)")
        self.root.geometry("340x360")

        self.data = load_data()

        tk.Label(root, text="ADHD Assistant", font=("Segoe UI", 14, "bold")).pack(pady=10)

        tk.Button(root, text="Tasks", width=22, command=self.open_tasks).pack(pady=3)
        tk.Button(root, text="Reminders", width=22, command=self.open_reminders).pack(pady=3)
        tk.Button(root, text="Notes", width=22, command=self.open_notes).pack(pady=3)
        tk.Button(root, text="Calendar", width=22, command=self.open_calendar).pack(pady=3)
        tk.Button(root, text="AI Summary", width=22, command=self.open_ai_summary_window).pack(pady=10)

        tk.Label(root, text=f"Model: {OLLAMA_MODEL}", font=("Segoe UI", 8)).pack(side=tk.BOTTOM, pady=5)

    # ---------- Tasks ----------

    def sorted_tasks(self):
        """
        Sort tasks by date, then priority, then title.
        """
        def sort_key(t):
            d = t.get("date") or "9999-12-31"
            return (d, t.get("priority") != "high", t.get("title"))
        return sorted(self.data["tasks"], key=sort_key)

    def open_tasks(self):
        """
        Open the task list window with add/edit/delete support.
        """

        def formatter(task):
            status = "✓" if task["completed"] else " "
            date_str = task["date"] or "no date"
            prio = task["priority"]
            return f"[{status}] ({prio}) {date_str} — {task['title']}"

        def add_task(win):
            res = task_dialog(win, None)
            if res["ok"] and res["task"]["title"]:
                self.data["tasks"].append(res["task"])
                self.data["tasks"] = self.sorted_tasks()
                save_data(self.data)

        def edit_task(win, index):
            tasks = self.sorted_tasks()
            if index < 0 or index >= len(tasks):
                return
            current = tasks[index]
            res = task_dialog(win, current)
            if res["ok"] and res["task"]["title"]:
                original_index = self.data["tasks"].index(current)
                self.data["tasks"][original_index] = res["task"]
                self.data["tasks"] = self.sorted_tasks()
                save_data(self.data)

        def delete_task(win, index):
            tasks = self.sorted_tasks()
            if index < 0 or index >= len(tasks):
                return
            t = tasks[index]
            if messagebox.askyesno("Delete Task", f"Delete task:\n\n{t['title']}?", parent=win):
                original_index = self.data["tasks"].index(t)
                self.data["tasks"].pop(original_index)
                save_data(self.data)

        show_list_popup(
            self.root,
            "Tasks",
            get_items=self.sorted_tasks,
            on_add=add_task,
            on_delete=delete_task,
            on_edit=edit_task,
            formatter=formatter
        )

    # ---------- Reminders ----------

    def open_reminders(self):
        def add_reminder(win):
            reminder = simpledialog.askstring("New Reminder", "Reminder:", parent=win)
            if reminder:
                self.data["reminders"].append(reminder)
                save_data(self.data)

        def delete_reminder(win, index):
            if index < 0 or index >= len(self.data["reminders"]):
                return
            r = self.data["reminders"][index]
            if messagebox.askyesno("Delete Reminder", f"Delete reminder:\n\n{r}?", parent=win):
                self.data["reminders"].pop(index)
                save_data(self.data)

        show_list_popup(
            self.root,
            "Reminders",
            get_items=lambda: self.data["reminders"],
            on_add=add_reminder,
            on_delete=delete_reminder
        )

    # ---------- Notes ----------

    def open_notes(self):
        def add_note(win):
            note = simpledialog.askstring("New Note", "Note:", parent=win)
            if note:
                self.data["notes"].append(note)
                save_data(self.data)

        def delete_note(win, index):
            if index < 0 or index >= len(self.data["notes"]):
                return
            n = self.data["notes"][index]
            if messagebox.askyesno("Delete Note", f"Delete note:\n\n{n}?", parent=win):
                self.data["notes"].pop(index)
                save_data(self.data)

        show_list_popup(
            self.root,
            "Notes",
            get_items=lambda: self.data["notes"],
            on_add=add_note,
            on_delete=delete_note
        )

    # ---------- Calendar Page ----------

    def open_calendar(self):
        win = tk.Toplevel(self.root)
        win.title("Calendar")
        win.geometry("800x500")

        today = date.today()
        state = {
            "year": today.year,
            "month": today.month,
            "view": "month_grid"
        }

        top_bar = tk.Frame(win)
        top_bar.pack(fill=tk.X, pady=5)

        content = tk.Frame(win)
        content.pack(fill=tk.BOTH, expand=True)

        bottom_bar = tk.Frame(win)
        bottom_bar.pack(fill=tk.X, pady=5)

        month_label = tk.Label(top_bar, text="", font=("Segoe UI", 11, "bold"))
        month_label.pack(side=tk.LEFT, padx=10)

        view_container = tk.Frame(content)
        view_container.pack(fill=tk.BOTH, expand=True)

        current_view = {"widget": None}

        def update_month_label():
            month_name = calendar.month_name[state["month"]]
            month_label.config(text=f"{month_name} {state['year']}")

        def build_view():
            # Only destroy the widget if switching view types
            if current_view["widget"] is not None:
                if not isinstance(current_view["widget"], WeekView) or state["view"] != "week":
                    current_view["widget"].destroy()
                    current_view["widget"] = None

            y = state["year"]
            m = state["month"]

            if state["view"] == "month_grid":
                widget = MonthGridView(view_container, self, y, m)

            elif state["view"] == "month_sidebar":
                widget = MonthSidebarView(view_container, self, y, m)

            elif state["view"] == "week":
                # Reuse existing WeekView if possible
                if isinstance(current_view["widget"], WeekView):
                    widget = current_view["widget"]
                else:
                    widget = WeekView(view_container, self, y, m)

            elif state["view"] == "agenda":
                widget = AgendaView(view_container, self, y, m)

            if widget is not current_view["widget"]:
                widget.pack(fill=tk.BOTH, expand=True)
                current_view["widget"] = widget

            update_month_label()
            rebuild_bottom_bar()

        def navigate(delta):
            if state["view"] in ("month_grid", "month_sidebar"):
                y = state["year"]
                m = state["month"] + delta
                while m < 1:
                    m += 12
                    y -= 1
                while m > 12:
                    m -= 12
                    y += 1
                state["year"], state["month"] = y, m
                build_view()

            elif state["view"] == "week":
                if isinstance(current_view["widget"], WeekView):
                    current_view["widget"].shift_week(delta)

            elif state["view"] == "agenda":
                return

        def go_today():
            t = date.today()
            state["year"], state["month"] = t.year, t.month

            if state["view"] == "week":
                if isinstance(current_view["widget"], WeekView):
                    current_view["widget"].current_date = t
                    current_view["widget"].build()
            else:
                build_view()

        def rebuild_bottom_bar():
            for child in bottom_bar.winfo_children():
                child.destroy()

            if state["view"] in ("month_grid", "month_sidebar"):
                tk.Button(bottom_bar, text="Previous Month", command=lambda: navigate(-1)).pack(side=tk.LEFT, padx=10)
                tk.Button(bottom_bar, text="Today", command=go_today).pack(side=tk.LEFT, padx=10)
                tk.Button(bottom_bar, text="Next Month", command=lambda: navigate(1)).pack(side=tk.LEFT, padx=10)

            elif state["view"] == "week":
                tk.Button(bottom_bar, text="Previous Week", command=lambda: navigate(-1)).pack(side=tk.LEFT, padx=10)
                tk.Button(bottom_bar, text="This Week", command=go_today).pack(side=tk.LEFT, padx=10)
                tk.Button(bottom_bar, text="Next Week", command=lambda: navigate(1)).pack(side=tk.LEFT, padx=10)

            elif state["view"] == "agenda":
                pass

        def set_view(view_name):
            state["view"] = view_name
            build_view()

        tk.Button(top_bar, text="Month Grid (A)", command=lambda: set_view("month_grid")).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Month + Sidebar (B)", command=lambda: set_view("month_sidebar")).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Week View (C)", command=lambda: set_view("week")).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Agenda View (D)", command=lambda: set_view("agenda")).pack(side=tk.LEFT, padx=5)

        build_view()

    # ---------- AI Summary Window ----------

    def open_ai_summary_window(self):
        """
        AI Summary window with two buttons:
        - Daily Summary
        - Weekly Summary
        """

        win = tk.Toplevel(self.root)
        win.title("AI Summaries")
        win.geometry("300x180")

        tk.Label(win, text="AI Summaries", font=("Segoe UI", 12, "bold")).pack(pady=10)

        def run_daily():
            prompt = build_daily_summary_prompt(self.data)
            self.run_ai_in_thread(prompt, "Daily Summary")

        def run_weekly():
            prompt = build_weekly_summary_prompt(self.data)
            self.run_ai_in_thread(prompt, "Weekly Summary")

        tk.Button(win, text="Daily Summary", width=20, command=run_daily).pack(pady=5)
        tk.Button(win, text="Weekly Summary", width=20, command=run_weekly).pack(pady=5)

    def run_ai_in_thread(self, prompt, title):
        """
        Run AI generation in a background thread to keep the UI responsive.
        """

        loading = tk.Toplevel(self.root)
        loading.title("Generating…")
        loading.geometry("260x80")
        tk.Label(loading, text="Generating summary…", font=("Segoe UI", 11)).pack(pady=20)
        loading.grab_set()

        def worker():
            summary = generate_ai_summary(prompt)
            try:
                loading.destroy()
            except Exception:
                pass
            show_text_popup(self.root, title, summary)

        threading.Thread(target=worker, daemon=True).start()


# ---------- Main ----------

def main():
    root = tk.Tk()
    app = ADHDApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()