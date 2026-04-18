import json
import os
import pytest
import tkinter as tk

# Import your app
from adhd import ADHDApp, DATA_FILE, save_data, load_data


@pytest.fixture
def app_instance():
    """Create a fresh instance of the app for each test."""
    root = tk.Tk()
    root.withdraw()  # Hide UI during tests
    app = ADHDApp(root)
    return app


def test_add_task(app_instance):
    """Test adding a task internally without GUI clicks."""
    app = app_instance

    # Create a task internally
    new_task = {
        "title": "Automated Task",
        "date": "2026-04-20",
        "notes": "This is an automated test task.",
        "completed": False,
        "priority": "normal"
    }

    # Add task to data
    app.data["tasks"].append(new_task)
    save_data(app.data)

    # Validate JSON
    data = load_data()
    assert any(t["title"] == "Automated Task" for t in data["tasks"])


def test_delete_task(app_instance):
    """Test deleting a task internally."""
    app = app_instance

    # Ensure task exists
    app.data["tasks"].append({"title": "Automated Task"})
    save_data(app.data)

    # Delete task internally
    app.data["tasks"] = [
        t for t in app.data["tasks"] if t["title"] != "Automated Task"
    ]
    save_data(app.data)

    # Validate JSON
    data = load_data()
    assert not any(t["title"] == "Automated Task" for t in data["tasks"])


def test_ai_summary_popup(app_instance):
    """Test that AI summary function creates a popup window."""
    app = app_instance
    root = app.root

    # Call the AI summary function internally
    app.open_ai_summary()

    # Check if a Toplevel window was created
    popups = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(popups) > 0
