import json
import os
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext, ttk
import requests

DATA_FILE = "adhd_data.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"


# ---------- Data Layer ----------

def load_data():
    default = {
        "tasks": [],        # list of {title, date, notes, completed, priority}
        "reminders": [],
        "notes": []
    }

    if not os.path.exists(DATA_FILE):
        return default

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Auto-repair missing keys
        for key in default:
            if key not in data:
                data[key] = default[key]

        # Ensure tasks are objects with expected fields
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
                # old string-based task, convert
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
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------- AI via Ollama (gemma3:4b) ----------

def generate_ai_summary(prompt: str) -> str:
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


# ---------- UI Helpers ----------

def show_list_popup(root, title, items, on_add=None, on_delete=None, on_edit=None, formatter=None):
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("500x400")

    listbox = tk.Listbox(win, selectmode=tk.SINGLE)
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def render():
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
        add_btn = tk.Button(btn_frame, text="Add", command=lambda: (on_add(win), render()))
        add_btn.pack(side=tk.LEFT, padx=5)

    if on_edit:
        edit_btn = tk.Button(
            btn_frame,
            text="Edit",
            command=lambda: (on_edit(win, listbox.curselection()[0]) if listbox.curselection() else None, render())
        )
        edit_btn.pack(side=tk.LEFT, padx=5)

    if on_delete:
        del_btn = tk.Button(
            btn_frame,
            text="Delete",
            command=lambda: (on_delete(win, listbox.curselection()[0]) if listbox.curselection() else None, render())
        )
        del_btn.pack(side=tk.LEFT, padx=5)


def show_text_popup(root, title, initial_text=""):
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("500x400")

    text = scrolledtext.ScrolledText(win, wrap=tk.WORD)
    text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    text.insert(tk.END, initial_text)
    text.config(state=tk.DISABLED)


# ---------- Task Dialog ----------

def task_dialog(parent, task=None):
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


# ---------- Main App ----------

class ADHDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ADHD Assistant (Local, Ollama)")
        self.root.geometry("320x280")

        self.data = load_data()

        tk.Label(root, text="ADHD Assistant", font=("Segoe UI", 14, "bold")).pack(pady=10)

        tk.Button(root, text="Tasks", width=22, command=self.open_tasks).pack(pady=5)
        tk.Button(root, text="Reminders", width=22, command=self.open_reminders).pack(pady=5)
        tk.Button(root, text="Notes", width=22, command=self.open_notes).pack(pady=5)
        tk.Button(root, text="AI Summary", width=22, command=self.open_ai_summary).pack(pady=15)

        tk.Label(root, text=f"Model: {OLLAMA_MODEL}", font=("Segoe UI", 8)).pack(side=tk.BOTTOM, pady=5)

    # ----- Tasks (structured) -----

    def open_tasks(self):
        def formatter(task):
            status = "✓" if task["completed"] else " "
            date = task["date"] or "no date"
            prio = task["priority"]
            return f"[{status}] ({prio}) {date} — {task['title']}"

        def add_task(win):
            res = task_dialog(win, None)
            if res["ok"] and res["task"]["title"]:
                self.data["tasks"].append(res["task"])
                self.data["tasks"] = self.sorted_tasks()
                save_data(self.data)

        def edit_task(win, index):
            if index is None or index < 0 or index >= len(self.data["tasks"]):
                return
            current = self.data["tasks"][index]
            res = task_dialog(win, current)
            if res["ok"] and res["task"]["title"]:
                self.data["tasks"][index] = res["task"]
                self.data["tasks"] = self.sorted_tasks()
                save_data(self.data)

        def delete_task(win, index):
            if index is None or index < 0 or index >= len(self.data["tasks"]):
                return
            t = self.data["tasks"][index]
            if messagebox.askyesno("Delete Task", f"Delete task:\n\n{t['title']}?", parent=win):
                self.data["tasks"].pop(index)
                save_data(self.data)

        show_list_popup(
            self.root,
            "Tasks",
            self.sorted_tasks(),
            on_add=add_task,
            on_delete=delete_task,
            on_edit=edit_task,
            formatter=formatter
        )

    def sorted_tasks(self):
        def sort_key(t):
            d = t.get("date") or "9999-12-31"
            return (d, t.get("priority") != "high", t.get("title"))
        return sorted(self.data["tasks"], key=sort_key)

    # ----- Reminders -----

    def open_reminders(self):
        def add_reminder(win):
            reminder = simpledialog.askstring("New Reminder", "Reminder:", parent=win)
            if reminder:
                self.data["reminders"].append(reminder)
                save_data(self.data)

        def delete_reminder(win, index):
            if index is None or index < 0 or index >= len(self.data["reminders"]):
                return
            r = self.data["reminders"][index]
            if messagebox.askyesno("Delete Reminder", f"Delete reminder:\n\n{r}?", parent=win):
                self.data["reminders"].pop(index)
                save_data(self.data)

        show_list_popup(
            self.root,
            "Reminders",
            self.data["reminders"],
            on_add=add_reminder,
            on_delete=delete_reminder
        )

    # ----- Notes -----

    def open_notes(self):
        def add_note(win):
            note = simpledialog.askstring("New Note", "Note:", parent=win)
            if note:
                self.data["notes"].append(note)
                save_data(self.data)

        def delete_note(win, index):
            if index is None or index < 0 or index >= len(self.data["notes"]):
                return
            n = self.data["notes"][index]
            if messagebox.askyesno("Delete Note", f"Delete note:\n\n{n}?", parent=win):
                self.data["notes"].pop(index)
                save_data(self.data)

        show_list_popup(
            self.root,
            "Notes",
            self.data["notes"],
            on_add=add_note,
            on_delete=delete_note
        )

    # ----- AI Summary (with Generating window) -----

    def open_ai_summary(self):
        # Build structured task text
        if self.data["tasks"]:
            task_lines = []
            for t in self.sorted_tasks():
                status = "done" if t["completed"] else "pending"
                date = t["date"] or "no date"
                prio = t["priority"]
                notes = t["notes"] or ""
                line = f"- [{status}] ({prio}) {date} — {t['title']}"
                if notes:
                    line += f"\n    notes: {notes}"
                task_lines.append(line)
            tasks_text = "\n".join(task_lines)
        else:
            tasks_text = "No tasks."

        reminders = "\n".join(f"- {r}" for r in self.data["reminders"]) or "No reminders."
        notes = "\n".join(f"- {n}" for n in self.data["notes"]) or "No notes."

        prompt = f"""
You are an ADHD-friendly assistant.

Here are my current items:

Tasks:
{tasks_text}

Reminders:
{reminders}

Notes:
{notes}

Please:
- Give me a short, kind summary of what I have on my plate.
- Highlight anything that seems time-sensitive or important.
- Suggest 3 concrete next actions.
- Keep it supportive and non-judgmental.
"""

        loading = tk.Toplevel(self.root)
        loading.title("Generating…")
        loading.geometry("260x80")
        tk.Label(loading, text="Generating summary…", font=("Segoe UI", 11)).pack(pady=20)
        loading.grab_set()

        def run_ai():
            summary = generate_ai_summary(prompt)
            try:
                loading.destroy()
            except Exception:
                pass
            show_text_popup(self.root, "AI Summary", summary)

        threading.Thread(target=run_ai, daemon=True).start()


# ---------- Main ----------

def main():
    root = tk.Tk()
    app = ADHDApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
