# WELLSPRING
A offline, privacy-first wellness sanctuary application designed to cut screen time short, protect your mental health, and return you to the physical world.

# 🌿 ABOUT WELLSPRING

A privacy-first, 100% offline personal wellbeing app that encourages digital detox and mindfulness.

WELLSPRING uses a local AI model to provide personal grounding reflections based on your journal entries—without sending a single byte of data to external servers or cloud providers. Built with the assistance of GitHub Copilot and powered locally by Google Gemma.

---

## 🏛️ Architecture & System Design

The architecture of WELLSPRING is designed around a fully offline, decoupled local ecosystem. At the presentation tier, a lightweight client interface is rendered using server-side Jinja2 templates styled with Tailwind CSS, serving as a clean local dashboard inside your browser. This communicates directly with a FastAPI backend server running locally on Python, which handles HTTP routing, business logic, and transaction management. For data persistence, the application interfaces with a lightweight local SQLite database file stored securely on the host machine to manage user moods, journal entries, and generated reflections. Simultaneously, the AI core runs completely air-gapped via Ollama hosting Google Gemma locally, allowing the backend to dispatch reflection prompts to a local endpoint without ever interacting with external cloud APIs or exposing user data to the internet.

---

## ✨ Key Features

* **100% Offline & Air-Gapped:** All data processing and AI inference happen locally on your device.
* **Zero Data Tracking:** No user accounts, cloud databases, or third-party telemetry.
* **Offline AI Core & Health Guide:** Powered by Google Gemma (via Ollama) to offer real-time mental grounding and health reflections.
* **SQLite Persistence:** Journal entries stay stored locally in a lightweight database.

---

## 🛠️ Tech Stack & Tools

* **Backend:** Python, FastAPI, Uvicorn
* **AI Model:** Google Gemma (via Ollama)
* **AI Pair Programming:** GitHub Copilot
* **Database:** SQLite
* **Frontend:** Jinja2 Templates, Tailwind CSS (via CDN)

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.9+** installed on your system.
2. **Ollama** installed and running locally.
* Download from ollama.com
* Pull the Gemma model: `ollama pull gemma`



### Installation

1. **Clone the repository:**
`git clone [https://github.com/your-username/wellspring.git](https://github.com/your-username/wellspring.git)`
`cd wellspring`
2. **Set up a virtual environment (optional but recommended):**
`python -m venv venv`
`source venv/bin/activate` (On Windows: `venv\Scripts\activate`)
3. **Install dependencies:**
`pip install fastapi uvicorn requests jinja2`

---

## 🏃 Running the Application

1. Make sure **Ollama** is running in the background:
`ollama serve`
2. Start the FastAPI server:
`uvicorn main:app --reload`
3. Open your browser and navigate to:
[http://127.0.0.1:8000](https://www.google.com/search?q=http://127.0.0.1:8000)

---

## 🔒 Privacy & Security

WELLSPRING is built from the ground up for zero-leak privacy:

* All journal logs are stored in a local SQLite database (`wellspring.db`).
* SQLite files are strictly excluded via `.gitignore` to prevent accidental uploads to version control.
* Parameterized SQL queries are used to prevent injection vulnerabilities.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

> *"Disconnect from the noise, reconnect with yourself—touch grass, not glass."*
