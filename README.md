# ADHD Assistant  
A desktop productivity tool designed to help users manage tasks, reminders, notes, and AI‑generated summaries using a clean Tkinter interface and local AI via Ollama.

---

## 📌 Overview
The ADHD Assistant is a lightweight, local-first productivity app built with Python and Tkinter. It provides:

- Task management (title, date, notes, priority, completion)
- Reminders
- Notes
- Calendar view
- AI Summary generation using a local Ollama model (gemma3:4b)
- JSON-based persistent storage
- Automated internal tests using pytest

The app is designed to be simple, fast, and distraction‑free.

---

## 🛠️ Installation

### 1. Install Python 3.13+
Download from the Microsoft Store or python.org.

### 2. Ensure pip is installed
```bash
python -m ensurepip --default-pip
```

### 3. Install required Python packages
```bash
pip install pillow requests pytest
```

> Tkinter is included with most Python installations.

### 4. Install Ollama (for AI summaries)
Download from:
https://ollama.com/download

After installation, pull the required model:
```bash
ollama pull gemma3:4b
```

---

## 📁 Project Structure

```
ADHD/
│── adhd.py                # Main application
│── automation_test.py     # Automated internal test suite
│── data.json              # Persistent storage
│── INSTRUCTIONS.txt       # Setup & usage instructions
│── README.md              # Project documentation
```

---

## 🚀 Running the Application

Start the ADHD Assistant with:

```bash
python adhd.py
```

The main window includes:

- Tasks  
- Reminders  
- Notes  
- Calendar  
- AI Summary  

All data is saved automatically into `data.json`.

---

## 🤖 AI Summary (Local Ollama)

To use the AI Summary feature:

1. Start the Ollama server:
   ```bash
   ollama serve
   ```

2. In the app, click **AI Summary**  
   The app sends your tasks/notes to the local model (`gemma3:4b`) and displays a generated summary.

---

## 🧪 Running Automated Tests

The automated tests run **internally** (no mouse automation) using pytest.

Run all tests with:

```bash
pytest -s
```

You should see:

```
3 passed in X.XXs
```

Tests include:

- Adding a task  
- Deleting a task  
- Opening the AI summary popup  

---

## 🔄 Resetting the App

To reset all data:

1. Delete `data.json`
2. Run the app again  
   A fresh file will be created automatically.

---

## 🛠️ Troubleshooting

### Pytest not recognized
Use the full path:

```
"C:\Users\<yourname>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\pytest.exe" -s
```

### Ollama model missing
Check installed models:
```bash
ollama list
```

If missing:
```bash
ollama pull gemma3:4b
```

### App crashes on load
Delete `data.json` and restart.

---

## 📄 License
This project is for educational and personal use.

---

## 🙌 Author
Created by Jason.

"# ADHD-Task-Manager" 
