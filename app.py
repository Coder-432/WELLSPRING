from contextlib import contextmanager
from datetime import datetime
import json
import sqlite3
import urllib.request
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="WELLSPRING — Personal Wellness Sanctuary")

DATABASE_NAME = "wellspring.db"


@contextmanager
def get_db_connection():
  connection = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
  connection.row_factory = sqlite3.Row
  try:
    yield connection
  finally:
    connection.close()


def initialize_database():
  with get_db_connection() as connection:
    db = connection.cursor()

    db.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                duration INTEGER NOT NULL,
                location TEXT DEFAULT 'General',
                mood INTEGER NOT NULL,
                energy INTEGER NOT NULL,
                notes TEXT
            )
        """)

    db.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                intervention TEXT NOT NULL,
                duration_days INTEGER NOT NULL,
                baseline_avg REAL NOT NULL,
                status TEXT NOT NULL,
                start_date TEXT NOT NULL
            )
        """)
    connection.commit()


initialize_database()


@app.get("/api/data")
def get_dashboard_data():
  try:
    with get_db_connection() as connection:
      db = connection.cursor()

      db.execute("SELECT * FROM activities ORDER BY date DESC, id DESC")
      activities = [dict(row) for row in db.fetchall()]

      db.execute("SELECT * FROM experiments")
      experiments = [dict(row) for row in db.fetchall()]

      total_logs = len(activities)
      total_minutes = sum(a["duration"] for a in activities)

      avg_mood = (
          round(sum(a["mood"] for a in activities) / total_logs, 1)
          if total_logs > 0
          else 0
      )
      avg_energy = (
          round(sum(a["energy"] for a in activities) / total_logs, 1)
          if total_logs > 0
          else 0
      )

      categories = {}
      for a in activities:
        cat = a["category"]
        categories[cat] = categories.get(cat, 0) + a["duration"]

    return {
        "stats": {
            "total_logs": total_logs,
            "total_minutes": total_minutes,
            "avg_mood": avg_mood,
            "avg_energy": avg_energy,
        },
        "activities": activities,
        "experiments": experiments,
        "categories": categories,
    }
  except Exception:
    return {
        "stats": {
            "total_logs": 0,
            "total_minutes": 0,
            "avg_mood": 0,
            "avg_energy": 0,
        },
        "activities": [],
        "experiments": [],
        "categories": {},
    }


@app.post("/api/activities")
def add_activity(
    name: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    duration: int = Form(...),
    mood: int = Form(...),
    energy: int = Form(...),
    notes: str = Form(""),
):
  with get_db_connection() as connection:
    db = connection.cursor()
    db.execute(
        """
            INSERT INTO activities (name, category, date, duration, location, mood, energy, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, category, date, duration, "General", mood, energy, notes),
    )
    connection.commit()
  return {"status": "success"}


@app.post("/api/ai-query")
def ai_query(question: str = Form(...)):
  with get_db_connection() as connection:
    db = connection.cursor()
    db.execute(
        "SELECT name, category, date, duration, energy, mood, notes FROM"
        " activities ORDER BY date DESC LIMIT 15"
    )
    rows = db.fetchall()

    if not rows:
      return {
          "response": (
              "Your sanctuary journal is currently pristine and empty. Record"
              " your first moment in the Activity Journal to begin your"
              " reflection."
          ),
          "evidence_count": 0,
      }

    logs_summary = " | ".join([
        f"{r['date']}: {r['name']} ({r['category']}, {r['duration']}m, Energy:"
        f" {r['energy']}/5, Mood: {r['mood']}/5)"
        for r in rows
    ])

  prompt = (
      f"You are WELLSPRING's reflection companion. User Question:"
      f" {question}\nJournal History: {logs_summary}\nProvide a calm, concise,"
      " supportive reflection based strictly on these moments."
  )
  try:
    payload = json.dumps(
        {"model": "gemma", "prompt": prompt, "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as response:
      res_data = json.loads(response.read().decode("utf-8"))
      answer = res_data.get("response")
      if answer:
        return {"response": answer, "evidence_count": len(rows)}
  except Exception:
    pass

  total_entries = len(rows)
  avg_eng = sum(r["energy"] for r in rows) / total_entries
  avg_mood = sum(r["mood"] for r in rows) / total_entries

  fallback_answer = (
      f"Reflecting across your {total_entries} recent entries: Your average"
      f" energy score rests at {avg_eng:.1f}/5.0 and your mood average is"
      f" {avg_mood:.1f}/5.0. Your journey shows steady self-attunement."
  )

  return {"response": fallback_answer, "evidence_count": total_entries}


@app.get("/", response_class=HTMLResponse)
def serve_ui():
  return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WELLSPRING — Personal Wellness Sanctuary</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        warm: {
                            bg: '#FAF8F5',
                            card: '#FFFFFF',
                            sidebar: '#F3EFEA',
                            border: '#E3DDD5',
                            pistachio: '#D4E0D2',
                            peach: '#FCECDD',
                            lilac: '#E8DEF3',
                            rose: '#F2D6CD',
                            gold: '#FDF0D5',
                            text: '#2D283E',
                            muted: '#80758A',
                            accent: '#C8B6E2',
                            accentDark: '#4A3E56'
                        }
                    },
                    fontFamily: { sans: ['Plus Jakarta Sans', 'sans-serif'] }
                }
            }
        }
    </script>
</head>
<body class="bg-warm-bg text-warm-text font-sans antialiased min-h-screen flex flex-row selection:bg-warm-peach selection:text-warm-accentDark">

    <!-- Sidebar Navigation -->
    <aside class="w-64 bg-warm-sidebar border-r border-warm-border flex flex-col justify-between p-6 fixed h-full z-20 shadow-xs">
        <div>
            <!-- COLORFUL WELLSPRING LOGO HEADER -->
            <div class="mb-10 px-2">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-warm-accent via-warm-pistachio to-warm-peach p-0.5 shadow-md hover:rotate-6 transition duration-300 flex items-center justify-center">
                        <div class="w-full h-full bg-white rounded-[14px] flex items-center justify-center">
                            <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none">
                                <defs>
                                    <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                                        <stop offset="0%" stop-color="#C8B6E2"/>
                                        <stop offset="50%" stop-color="#8BBF9F"/>
                                        <stop offset="100%" stop-color="#F7A072"/>
                                    </linearGradient>
                                </defs>
                                <path stroke="url(#logoGrad)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                            </svg>
                        </div>
                    </div>
                    <div>
                        <h1 class="text-xl font-extrabold tracking-tight bg-gradient-to-r from-warm-accentDark via-[#6E5B82] to-[#B37285] bg-clip-text text-transparent">
                            WELLSPRING
                        </h1>
                        <p class="text-[10px] text-warm-muted font-semibold tracking-wider uppercase">Sanctuary</p>
                    </div>
                </div>
            </div>

            <nav class="space-y-2">
                <button onclick="switchTab('dashboard')" id="nav-dashboard" class="w-full text-left px-4 py-3 rounded-2xl text-sm font-semibold bg-warm-accent text-warm-accentDark transition flex items-center gap-3 shadow-xs">
                    <svg class="w-4 h-4 opacity-85" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
                    Dashboard
                </button>
                <button onclick="switchTab('tracker')" id="nav-tracker" class="w-full text-left px-4 py-3 rounded-2xl text-sm font-medium text-warm-text hover:bg-warm-card transition flex items-center gap-3">
                    <svg class="w-4 h-4 text-warm-muted" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                    Activity Journal
                </button>
                <button onclick="switchTab('analytics')" id="nav-analytics" class="w-full text-left px-4 py-3 rounded-2xl text-sm font-medium text-warm-text hover:bg-warm-card transition flex items-center gap-3">
                    <svg class="w-4 h-4 text-warm-muted" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    Reflection Analytics
                </button>
                <button onclick="switchTab('experiment')" id="nav-experiment" class="w-full text-left px-4 py-3 rounded-2xl text-sm font-medium text-warm-text hover:bg-warm-card transition flex items-center gap-3">
                    <svg class="w-4 h-4 text-warm-muted" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                    Habit Lab
                </button>
                <button onclick="switchTab('tips')" id="nav-tips" class="w-full text-left px-4 py-3 rounded-2xl text-sm font-medium text-warm-text hover:bg-warm-card transition flex items-center gap-3">
                    <svg class="w-4 h-4 text-warm-muted" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 01-2 2h-0a2 2 0 01-2-2v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                    Health Tips
                </button>
                <button onclick="switchTab('assistant')" id="nav-assistant" class="w-full text-left px-4 py-3 rounded-2xl text-sm font-medium text-warm-text hover:bg-warm-card transition flex items-center gap-3">
                    <svg class="w-4 h-4 text-warm-muted" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                    Sanctuary Guide
                </button>
            </nav>
        </div>
        <div class="text-xs text-warm-muted border-t border-warm-border pt-4 px-2">
            <p class="font-semibold text-warm-accentDark flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5 text-warm-accentDark" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                Private & Secure
            </p>
            <p class="mt-0.5 opacity-80">Stored locally on device.</p>
        </div>
    </aside>

    <!-- Main Content Area -->
    <main class="ml-64 flex-1 p-10 max-w-7xl">

        <!-- 1. DASHBOARD TAB -->
        <div id="tab-dashboard" class="space-y-8">
            <div class="bg-gradient-to-r from-warm-peach via-warm-pistachio to-warm-lilac text-warm-accentDark p-8 rounded-3xl shadow-xs relative overflow-hidden flex justify-between items-center border border-white">
                <div class="z-10 space-y-1">
                    <span class="bg-white/60 text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1.5 w-max">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path></svg>
                        Your Inner Space
                    </span>
                    <h2 class="text-3xl font-bold tracking-tight">Welcome to Your Sanctuary</h2>
                    <p class="text-sm font-medium opacity-90" id="current-date"></p>
                </div>
                <div class="text-7xl opacity-20 select-none z-0">🌿</div>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-3 gap-5">
                <div class="bg-warm-card p-6 rounded-3xl border border-warm-border shadow-xs hover:border-warm-accent transition">
                    <p class="text-xs font-bold text-warm-muted uppercase tracking-wider flex items-center gap-1.5"><svg class="w-4 h-4 text-warm-accentDark" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>Journal Entries</p>
                    <p class="text-3xl font-bold text-warm-accentDark mt-2" id="stat-logs">0</p>
                    <span class="text-xs text-warm-muted font-semibold mt-3 inline-block">Saved moments</span>
                </div>
                <div class="bg-warm-card p-6 rounded-3xl border border-warm-border shadow-xs hover:border-warm-accent transition">
                    <p class="text-xs font-bold text-warm-muted uppercase tracking-wider flex items-center gap-1.5"><svg class="w-4 h-4 text-warm-accentDark" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>Active Time</p>
                    <p class="text-3xl font-bold text-warm-accentDark mt-2" id="stat-minutes">0m</p>
                    <span class="text-xs text-warm-muted font-semibold mt-3 inline-block">Total duration</span>
                </div>
                <div class="bg-warm-card p-6 rounded-3xl border border-warm-border shadow-xs hover:border-warm-accent transition">
                    <p class="text-xs font-bold text-warm-muted uppercase tracking-wider flex items-center gap-1.5"><svg class="w-4 h-4 text-warm-accentDark" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>Mood / Energy</p>
                    <p class="text-3xl font-bold text-warm-accentDark mt-2" id="stat-ratings">0 / 0</p>
                    <span class="text-xs text-warm-muted font-semibold mt-3 inline-block">Average out of 5</span>
                </div>
            </div>

            <!-- Charts -->
            <div class="grid grid-cols-2 gap-6">
                <div class="bg-warm-card p-7 rounded-3xl border border-warm-border shadow-xs">
                    <h3 class="font-bold text-warm-accentDark text-base mb-1">Activity Distribution</h3>
                    <p class="text-xs text-warm-muted mb-6">Minutes spent per category</p>
                    <canvas id="weeklyChart" height="150"></canvas>
                </div>
                <div class="bg-warm-card p-7 rounded-3xl border border-warm-border shadow-xs">
                    <h3 class="font-bold text-warm-accentDark text-base mb-1">Proportional Breakdown</h3>
                    <p class="text-xs text-warm-muted mb-6">Visual spread of your habits</p>
                    <canvas id="categoryChart" height="150"></canvas>
                </div>
            </div>

            <!-- Bottom Image Gallery -->
            <div class="grid grid-cols-3 gap-5 mt-10 pt-6 border-t border-warm-border">
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-pistachio">
                    <img src="https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=600&q=80" alt="Forest canopy" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-peach">
                    <img src="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80" alt="Serene coastline" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-lilac">
                    <img src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80" alt="Mountain valley" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
            </div>
        </div>

        <!-- 2. ACTIVITY TRACKER TAB -->
        <div id="tab-tracker" class="hidden space-y-8">
            <div class="bg-gradient-to-r from-warm-peach via-warm-rose to-warm-pistachio text-warm-accentDark p-8 rounded-3xl shadow-xs flex justify-between items-center border border-white">
                <div class="space-y-1">
                    <span class="bg-white/60 text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1.5 w-max">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                        Journaling
                    </span>
                    <h2 class="text-3xl font-bold tracking-tight">Activity Journal</h2>
                    <p class="text-sm font-medium opacity-90">Record moments of movement, rest, and reflection.</p>
                </div>
                <div class="text-7xl opacity-25 select-none">🍃</div>
            </div>

            <div class="bg-warm-card p-8 rounded-3xl border border-warm-border shadow-xs">
                <h3 class="font-bold text-warm-accentDark text-lg mb-6 flex items-center gap-2">🌿 Record New Moment</h3>
                <form id="activityForm" onsubmit="submitActivity(event)" class="grid grid-cols-2 gap-5">
                    <div>
                        <label class="block text-xs font-bold text-warm-muted uppercase tracking-wider mb-2">Activity Name</label>
                        <input type="text" name="name" required placeholder="e.g., Quiet forest walk at sunrise" class="w-full border border-warm-border rounded-2xl p-3.5 text-sm focus:outline-none focus:border-warm-accent bg-warm-bg">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-warm-muted uppercase tracking-wider mb-2">Category</label>
                        <select name="category" class="w-full border border-warm-border rounded-2xl p-3.5 text-sm bg-warm-bg focus:outline-none focus:border-warm-accent">
                            <option>Walking Outdoors</option>
                            <option>Exercising</option>
                            <option>Resting</option>
                            <option>Recreation</option>
                            <option>Social Interaction</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-warm-muted uppercase tracking-wider mb-2">Date</label>
                        <input type="date" id="todayDate" name="date" required class="w-full border border-warm-border rounded-2xl p-3.5 text-sm focus:outline-none focus:border-warm-accent bg-warm-bg">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-warm-muted uppercase tracking-wider mb-2">Duration (minutes)</label>
                        <input type="number" name="duration" value="30" min="1" max="360" required class="w-full border border-warm-border rounded-2xl p-3.5 text-sm focus:outline-none focus:border-warm-accent bg-warm-bg">
                    </div>
                    <div class="col-span-2">
                        <label class="block text-xs font-bold text-warm-muted uppercase tracking-wider mb-2">Mood & Energy (Scale 1-5)</label>
                        <div class="flex gap-3">
                            <input type="number" name="mood" min="1" max="5" value="4" class="w-1/2 border border-warm-border rounded-2xl p-3.5 text-sm bg-warm-bg" placeholder="Mood">
                            <input type="number" name="energy" min="1" max="5" value="4" class="w-1/2 border border-warm-border rounded-2xl p-3.5 text-sm bg-warm-bg" placeholder="Energy">
                        </div>
                    </div>
                    <div class="col-span-2">
                        <label class="block text-xs font-bold text-warm-muted uppercase tracking-wider mb-2">Reflections / Notes</label>
                        <textarea name="notes" rows="2" placeholder="How did this moment feel?" class="w-full border border-warm-border rounded-2xl p-3.5 text-sm focus:outline-none focus:border-warm-accent bg-warm-bg"></textarea>
                    </div>
                    <div class="col-span-2 pt-2">
                        <button type="submit" class="bg-warm-accent text-warm-accentDark font-semibold text-sm py-3.5 px-7 rounded-2xl hover:bg-opacity-90 transition cursor-pointer shadow-xs">Save to Journal 🌿</button>
                    </div>
                </form>
            </div>

            <!-- LOGS TABLE -->
            <div class="bg-warm-card p-8 rounded-3xl border border-warm-border shadow-xs">
                <h3 class="font-bold text-warm-accentDark text-lg mb-4 flex items-center gap-2">📚 Saved Journal Entries</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-warm-text border-collapse">
                        <thead>
                            <tr class="bg-warm-sidebar text-warm-accentDark font-bold border-b border-warm-border">
                                <th class="p-4">Date</th>
                                <th class="p-4">Name</th>
                                <th class="p-4">Category</th>
                                <th class="p-4">Duration</th>
                                <th class="p-4">Mood</th>
                                <th class="p-4">Energy</th>
                                <th class="p-4">Notes</th>
                            </tr>
                        </thead>
                        <tbody id="logs-table-body"></tbody>
                    </table>
                </div>
            </div>

            <!-- Bottom Image Gallery -->
            <div class="grid grid-cols-3 gap-5 mt-10 pt-6 border-t border-warm-border">
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-rose">
                    <img src="https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=600&q=80" alt="Natural forest landscape" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-pistachio">
                    <img src="https://images.unsplash.com/photo-1473448912268-2022ce9509d8?auto=format&fit=crop&w=600&q=80" alt="Green path" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-peach">
                    <img src="https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=600&q=80" alt="Serene valley landscape" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
            </div>
        </div>

        <!-- 3. REFLECTION ANALYTICS TAB -->
        <div id="tab-analytics" class="hidden space-y-8">
            <div class="bg-gradient-to-r from-warm-pistachio via-warm-lilac to-warm-peach text-warm-accentDark p-8 rounded-3xl shadow-xs flex justify-between items-center border border-white">
                <div class="space-y-1">
                    <span class="bg-white/60 text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1.5 w-max">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                        Insights
                    </span>
                    <h2 class="text-3xl font-bold tracking-tight">Reflection Analytics</h2>
                    <p class="text-sm font-medium opacity-90">Gentle patterns discovered from your personal records.</p>
                </div>
                <div class="text-7xl opacity-25 select-none">🌊</div>
            </div>
            <div class="bg-warm-card p-8 rounded-3xl border border-warm-border shadow-xs space-y-4">
                <h3 class="font-bold text-warm-accentDark text-lg flex items-center gap-2">🔍 Pattern Investigator</h3>
                <p id="analytics-live-content" class="text-sm text-warm-text leading-relaxed">Loading records...</p>
            </div>

            <!-- Bottom Image Gallery -->
            <div class="grid grid-cols-3 gap-5 mt-10 pt-6 border-t border-warm-border">
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-lilac">
                    <img src="https://images.unsplash.com/photo-1470246973918-29a93221c455?auto=format&fit=crop&w=600&q=80" alt="Calm stream" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-peach">
                    <img src="https://images.unsplash.com/photo-1518495973542-4542c06a5843?auto=format&fit=crop&w=600&q=80" alt="Sunlit leaves" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-pistachio">
                    <img src="https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=600&q=80" alt="Reflection lake" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
            </div>
        </div>

        <!-- 4. HABIT LAB TAB -->
        <div id="tab-experiment" class="hidden space-y-8">
            <div class="bg-gradient-to-r from-warm-lilac via-warm-rose to-warm-peach text-warm-accentDark p-8 rounded-3xl shadow-xs flex justify-between items-center border border-white">
                <div class="space-y-1">
                    <span class="bg-white/60 text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1.5 w-max">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                        Experimentation
                    </span>
                    <h2 class="text-3xl font-bold tracking-tight">Habit Lab 🔬</h2>
                    <p class="text-sm font-medium opacity-90">Test small, deliberate shifts in your daily flow.</p>
                </div>
                <div class="text-7xl opacity-25 select-none">🔬</div>
            </div>

            <!-- Multiple Experiments Grid -->
            <div class="grid grid-cols-3 gap-6">
                <div class="bg-warm-card p-6 rounded-3xl border border-warm-border shadow-xs space-y-3 flex flex-col justify-between">
                    <div>
                        <span class="bg-warm-pistachio text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full">🌱 Active Test</span>
                        <h3 class="text-lg font-bold text-warm-accentDark mt-3">15-Min Morning Outdoor Stroll</h3>
                        <p class="text-xs text-warm-muted mt-1 leading-relaxed"><b>Goal:</b> Elevate energy levels and afternoon mental clarity before starting work.</p>
                    </div>
                    <div class="text-xs text-warm-accentDark border-t border-warm-border pt-3 font-semibold">
                        Nurtures daily vitality.
                    </div>
                </div>

                <div class="bg-warm-card p-6 rounded-3xl border border-warm-border shadow-xs space-y-3 flex flex-col justify-between">
                    <div>
                        <span class="bg-warm-lilac text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full">🌙 Evening Test</span>
                        <h3 class="text-lg font-bold text-warm-accentDark mt-3">Digital Sunset (Screen-Free)</h3>
                        <p class="text-xs text-warm-muted mt-1 leading-relaxed"><b>Goal:</b> Disconnect from screens 1 hour before sleep to improve evening calm.</p>
                    </div>
                    <div class="text-xs text-warm-accentDark border-t border-warm-border pt-3 font-semibold">
                        Cultivates restful peace.
                    </div>
                </div>

                <div class="bg-warm-card p-6 rounded-3xl border border-warm-border shadow-xs space-y-3 flex flex-col justify-between">
                    <div>
                        <span class="bg-warm-peach text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full">💧 Hydration Ritual</span>
                        <h3 class="text-lg font-bold text-warm-accentDark mt-3">500ml Water Upon Waking</h3>
                        <p class="text-xs text-warm-muted mt-1 leading-relaxed"><b>Goal:</b> Kickstart metabolic hydration and morning alertness instantly.</p>
                    </div>
                    <div class="text-xs text-warm-accentDark border-t border-warm-border pt-3 font-semibold">
                        Awakens inner flow.
                    </div>
                </div>
            </div>

            <!-- Bottom Image Gallery -->
            <div class="grid grid-cols-3 gap-5 mt-10 pt-6 border-t border-warm-border">
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-peach">
                    <img src="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=80" alt="Morning meadow" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-pistachio">
                    <img src="https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=600&q=80" alt="Pine forest" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-rose">
                    <img src="https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=600&q=80" alt="Wandering trail" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
            </div>
        </div>

        <!-- 5. HEALTH TIPS TAB -->
        <div id="tab-tips" class="hidden space-y-8">
            <div class="bg-gradient-to-r from-warm-gold via-warm-peach to-warm-lilac text-warm-accentDark p-8 rounded-3xl shadow-xs flex justify-between items-center border border-white">
                <div class="space-y-1">
                    <span class="bg-white/60 text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1.5 w-max">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 01-2 2h-0a2 2 0 01-2-2v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                        Wellness Guidance
                    </span>
                    <h2 class="text-3xl font-bold tracking-tight">Health & Reflection Tips</h2>
                    <p class="text-sm font-medium opacity-90">Gentle, restorative principles to support your daily rhythm.</p>
                </div>
                <div class="text-7xl opacity-25 select-none">💡</div>
            </div>

            <!-- Health Tips Cards Grid -->
            <div class="grid grid-cols-2 gap-6">
                <div class="bg-warm-card p-7 rounded-3xl border border-warm-border shadow-xs space-y-3">
                    <div class="flex items-center gap-2 text-warm-accentDark font-bold text-base">
                        <span class="p-2 bg-warm-pistachio rounded-xl text-xs">☀️</span> Morning Natural Light
                    </div>
                    <p class="text-xs text-warm-muted leading-relaxed">
                        Step outside into morning sunlight within 30 minutes of waking. Natural photons regulate your circadian cortisol rise, boosting daytime alertness and evening sleep readiness.
                    </p>
                </div>

                <div class="bg-warm-card p-7 rounded-3xl border border-warm-border shadow-xs space-y-3">
                    <div class="flex items-center gap-2 text-warm-accentDark font-bold text-base">
                        <span class="p-2 bg-warm-peach rounded-xl text-xs">🚶</span> Mindful Micro-Walks
                    </div>
                    <p class="text-xs text-warm-muted leading-relaxed">
                        Even a brief 10-to-15-minute gentle outdoor stroll lowers blood pressure and clears cognitive fatigue. Moving in open space shifts your brain into expansive visual processing.
                    </p>
                </div>

                <div class="bg-warm-card p-7 rounded-3xl border border-warm-border shadow-xs space-y-3">
                    <div class="flex items-center gap-2 text-warm-accentDark font-bold text-base">
                        <span class="p-2 bg-warm-lilac rounded-xl text-xs">🧘</span> Conscious Pauses
                    </div>
                    <p class="text-xs text-warm-muted leading-relaxed">
                        Integrate two-minute breathing breaks between daily transitions. Inhaling deeply through the nose and exhaling slowly activates your parasympathetic nervous system to dissolve tension.
                    </p>
                </div>

                <div class="bg-warm-card p-7 rounded-3xl border border-warm-border shadow-xs space-y-3">
                    <div class="flex items-center gap-2 text-warm-accentDark font-bold text-base">
                        <span class="p-2 bg-warm-rose rounded-xl text-xs">🍵 Hydration Rhythm</span>
                    </div>
                    <p class="text-xs text-warm-muted leading-relaxed">
                        Sip room-temperature water steadily throughout the day rather than chugging large amounts at once. Consistent cellular hydration prevents subtle afternoon fatigue and headaches.
                    </p>
                </div>
            </div>

            <!-- Bottom Image Gallery -->
            <div class="grid grid-cols-3 gap-5 mt-10 pt-6 border-t border-warm-border">
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-gold">
                    <img src="https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=600&q=80" alt="Mindful pause" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-lilac">
                    <img src="https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=600&q=80" alt="Tranquil scene" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-pistachio">
                    <img src="https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?auto=format&fit=crop&w=600&q=80" alt="Green retreat" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
            </div>
        </div>

        <!-- 6. SANCTUARY GUIDE TAB -->
        <div id="tab-assistant" class="hidden space-y-8">
            <div class="bg-gradient-to-r from-warm-rose via-warm-peach to-warm-pistachio text-warm-accentDark p-8 rounded-3xl shadow-xs flex justify-between items-center border border-white">
                <div class="space-y-1">
                    <span class="bg-white/60 text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1.5 w-max">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                        Intelligence
                    </span>
                    <h2 class="text-3xl font-bold tracking-tight">Sanctuary Guide</h2>
                    <p class="text-sm font-medium opacity-90">Reflect on your personal journal records securely.</p>
                </div>
                <div class="text-7xl opacity-25 select-none">💬</div>
            </div>
            <div class="bg-warm-card p-8 rounded-3xl border border-warm-border shadow-xs space-y-5">
                <div class="flex gap-3">
                    <input type="text" id="aiQueryInput" placeholder="Ask about your logged entries or energy trends..." class="flex-1 border border-warm-border rounded-2xl p-4 text-sm focus:outline-none focus:border-warm-accent bg-warm-bg">
                    <button onclick="sendAIQuery()" class="bg-warm-accent text-warm-accentDark font-semibold text-sm px-7 py-4 rounded-2xl hover:bg-opacity-90 transition cursor-pointer shadow-xs">Reflect ✨</button>
                </div>
                <div id="aiResponseBox" class="hidden p-6 bg-warm-sidebar border border-warm-border rounded-3xl text-sm text-warm-text space-y-3">
                    <h4 class="font-bold text-warm-accentDark flex items-center gap-2">🌿 Sanctuary Reflection</h4>
                    <p id="aiResponseText"></p>
                    <div class="flex gap-2 pt-2">
                        <span id="evidenceBadge" class="bg-white text-warm-accentDark text-xs font-bold px-3 py-1 rounded-full border border-warm-border">✨ Reflection Complete</span>
                    </div>
                </div>
            </div>

            <!-- Bottom Image Gallery -->
            <div class="grid grid-cols-3 gap-5 mt-10 pt-6 border-t border-warm-border">
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-lilac">
                    <img src="https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80" alt="Quiet study" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-peach">
                    <img src="https://images.unsplash.com/photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=600&q=80" alt="Writing desk" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
                <div class="overflow-hidden rounded-3xl shadow-xs border border-warm-border aspect-[4/3] bg-warm-pistachio">
                    <img src="https://images.unsplash.com/photo-1517842645767-c639042777db?auto=format&fit=crop&w=600&q=80" alt="Peaceful corner" class="w-full h-full object-cover hover:scale-105 transition duration-500">
                </div>
            </div>
        </div>

    </main>

    <script>
        let barChartInstance = null;
        let pieChartInstance = null;

        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        document.getElementById('current-date').innerHTML = `Today is <b>${new Date().toLocaleDateString('en-US', options)}</b>.`;
        document.getElementById('todayDate').valueAsDate = new Date();

        function switchTab(tabId) {
            ['dashboard', 'tracker', 'analytics', 'experiment', 'tips', 'assistant'].forEach(t => {
                const tabEl = document.getElementById(`tab-${t}`);
                const navEl = document.getElementById(`nav-${t}`);
                if(tabEl) tabEl.classList.add('hidden');
                if(navEl) navEl.className = "w-full text-left px-4 py-3 rounded-2xl text-sm font-medium text-warm-text hover:bg-warm-card transition flex items-center gap-3";
            });
            const activeTab = document.getElementById(`tab-${tabId}`);
            const activeNav = document.getElementById(`nav-${tabId}`);
            if(activeTab) activeTab.classList.remove('hidden');
            if(activeNav) activeNav.className = "w-full text-left px-4 py-3 rounded-2xl text-sm font-semibold bg-warm-accent text-warm-accentDark transition flex items-center gap-3 shadow-xs";
            
            fetchAndRenderData();
        }

        async function fetchAndRenderData() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();

                document.getElementById('stat-logs').innerText = data.stats.total_logs;
                document.getElementById('stat-minutes').innerText = `${data.stats.total_minutes}m`;
                document.getElementById('stat-ratings').innerText = `${data.stats.avg_mood} / ${data.stats.avg_energy}`;

                const tbody = document.getElementById('logs-table-body');
                tbody.innerHTML = '';
                if(data.activities.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" class="p-8 text-center text-warm-muted italic">Your journal is currently pristine and empty. Record your first moment above!</td></tr>';
                } else {
                    data.activities.forEach(act => {
                        const tr = document.createElement('tr');
                        tr.className = "border-b border-warm-border hover:bg-warm-sidebar transition";
                        tr.innerHTML = `
                            <td class="p-4 font-medium">${act.date}</td>
                            <td class="p-4 font-semibold text-warm-accentDark">${act.name}</td>
                            <td class="p-4"><span class="bg-warm-sidebar text-warm-text px-3 py-1 rounded-xl text-xs font-medium">${act.category}</span></td>
                            <td class="p-4">${act.duration} mins</td>
                            <td class="p-4">${act.mood}/5</td>
                            <td class="p-4">${act.energy}/5</td>
                            <td class="p-4 text-xs text-warm-muted">${act.notes || '-'}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }

                const analyticsEl = document.getElementById('analytics-live-content');
                if(data.stats.total_logs > 0) {
                    analyticsEl.innerHTML = `<b>Reflective Summary:</b> You have recorded <b>${data.stats.total_logs} moments</b> totaling <b>${data.stats.total_minutes} active minutes</b>. Average self-reported energy score: <b>${data.stats.avg_energy}/5.0</b>.`;
                } else {
                    analyticsEl.innerText = "No journal entries recorded yet. Add moments in the Activity Journal to generate reflection patterns.";
                }

                const catLabels = Object.keys(data.categories);
                const catValues = Object.values(data.categories);

                const ctxBar = document.getElementById('weeklyChart').getContext('2d');
                if(barChartInstance) barChartInstance.destroy();
                barChartInstance = new Chart(ctxBar, {
                    type: 'bar',
                    data: {
                        labels: catLabels.length > 0 ? catLabels : ['No Entries Yet'],
                        datasets: [{
                            label: 'Minutes Spent',
                            data: catValues.length > 0 ? catValues : [0],
                            backgroundColor: '#C8B6E2',
                            borderRadius: 10
                        }]
                    },
                    options: { responsive: true, plugins: { legend: { display: false } } }
                });

                const ctxPie = document.getElementById('categoryChart').getContext('2d');
                if(pieChartInstance) pieChartInstance.destroy();
                pieChartInstance = new Chart(ctxPie, {
                    type: 'doughnut',
                    data: {
                        labels: catLabels.length > 0 ? catLabels : ['No Entries Yet'],
                        datasets: [{
                            data: catValues.length > 0 ? catValues : [1],
                            backgroundColor: ['#C8B6E2', '#D4E0D2', '#FCECDD', '#E8DEF3', '#F2D6CD']
                        }]
                    },
                    options: { responsive: true }
                });

            } catch (err) {
                console.error("Error loading data:", err);
            }
        }

        async function submitActivity(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            try {
                const response = await fetch('/api/activities', { method: 'POST', body: formData });
                if (response.ok) {
                    alert('Moment securely saved to your journal!');
                    e.target.reset();
                    document.getElementById('todayDate').valueAsDate = new Date();
                    switchTab('tracker');
                } else {
                    alert('Error saving moment.');
                }
            } catch (err) {
                alert('Connection error: ' + err);
            }
        }

        async function sendAIQuery() {
            const question = document.getElementById('aiQueryInput').value;
            if (!question) return;
            
            document.getElementById('aiResponseText').innerText = "Reflecting on your journal records...";
            document.getElementById('aiResponseBox').classList.remove('hidden');

            try {
                const formData = new URLSearchParams();
                formData.append('question', question);
                
                const res = await fetch('/api/ai-query', { method: 'POST', body: formData });
                const data = await res.json();
                
                document.getElementById('aiResponseText').innerText = data.response;
                document.getElementById('evidenceBadge').innerText = `✨ Reflection Complete: ${data.evidence_count} Entries`;
            } catch (err) {
                document.getElementById('aiResponseText').innerText = "Error reflecting on records.";
            }
        }

        window.addEventListener('DOMContentLoaded', fetchAndRenderData);
    </script>
</body>
</html>
"""


if __name__ == "__main__":
  uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
