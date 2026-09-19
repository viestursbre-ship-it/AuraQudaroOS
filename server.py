import json
import os
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
DATA_FILE = "state.json"

# Noklusējuma stāvoklis, ja fails vēl neeksistē
default_state = {
    "messages": [
        {
            "id": 1,
            "sender": "Architect",
            "role": "ai_arch",
            "text": "AQ-OS vadības panelis v0.1 inicializēts. Trīs paneļu karkass gatavs darbam!",
            "time": "00:00",
        }
    ],
    "tasks": [
        {
            "id": 1,
            "title": "Izveidot AQ-OS v0.1 karkasu",
            "status": "In Progress",
            "desc": "Palaist trīs paneļu vadības kabīni ar lokālo atmiņu.",
        }
    ],
    "artifacts": [
        {
            "id": 1,
            "title": "server.py (Core Backend)",
            "lang": "python",
            "code": "# Python Flask backend for AQ-OS Cockpit\nprint('Aura Quadro OS Running')",
        }
    ],
}


def load_state():
  if not os.path.exists(DATA_FILE):
    save_state(default_state)
    return default_state
  try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except:
    return default_state


def save_state(state):
  with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="lv" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Aura Quadro OS — Cockpit v0.1</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Highlight.js sintakses izcelšanai -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darkBg: '#0b0f17',
                        panelBg: '#131b2e',
                        borderCol: '#1e293b'
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-darkBg text-slate-200 h-screen flex flex-col font-sans overflow-hidden">

    <!-- Top Header -->
    <header class="bg-panelBg border-b border-borderCol px-6 py-3 flex justify-between items-center select-none">
        <div class="flex items-center space-x-3">
            <span class="text-xl">⚡</span>
            <h1 class="text-base font-bold tracking-wide text-white">AURA QUADRO OS <span class="text-xs font-normal text-slate-400">| Cockpit v0.1</span></h1>
        </div>
        <div class="flex items-center space-x-4 text-xs">
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-blue-950 text-blue-400 border border-blue-800">
                ● 4 Minds Active
            </span>
            <span class="text-slate-400">Memory: <span class="text-emerald-400 font-mono">state.json</span></span>
        </div>
    </header>

    <!-- Main Workspace: 3 Columns -->
    <main class="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        
        <!-- PANEL 1: The Core (Chat) - Col 4 -->
        <section class="col-span-4 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">1. The Core (Kopējā Plūsma)</span>
                <span class="text-slate-500 text-sm">💬</span>
            </div>
            
            <div id="chatMessages" class="flex-1 p-4 overflow-y-auto space-y-3">
                <!-- Messages load dynamically -->
            </div>

            <div class="p-3 border-t border-borderCol bg-slate-900/30">
                <div class="flex gap-2 mb-2">
                    <select id="authorSelect" class="bg-slate-950 text-xs text-slate-300 border border-borderCol rounded px-2 py-1 outline-none">
                        <option value="Viesturs">👤 Viesturs</option>
                        <option value="Marija">🌸 Marija</option>
                        <option value="Architect">🏛️ Architect MI</option>
                        <option value="Coder">⚡ Coder MI</option>
                    </select>
                </div>
                <div class="flex gap-2">
                    <input type="text" id="chatInput" placeholder="Ieraksti domu vai ideju..." class="flex-1 bg-slate-950 border border-borderCol rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" onkeydown="if(event.key==='Enter') sendChatMessage()">
                    <button onclick="sendChatMessage()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition">Sūtīt</button>
                </div>
            </div>
        </section>

        <!-- PANEL 2: Intent / Task Queue - Col 3 -->
        <section class="col-span-3 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">2. Intent / Tasks</span>
                <span class="text-slate-500 text-sm">🎯</span>
            </div>
            
            <div class="p-3 border-b border-borderCol bg-slate-900/20">
                <input type="text" id="newTaskTitle" placeholder="+ Jauns uzdevums koderim..." class="w-full bg-slate-950 border border-borderCol rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500 mb-2" onkeydown="if(event.key==='Enter') createTask()">
            </div>

            <div id="taskList" class="flex-1 p-3 overflow-y-auto space-y-2">
                <!-- Tasks load dynamically -->
            </div>
        </section>

        <!-- PANEL 3: Live Output & Code Artifacts - Col 5 -->
        <section class="col-span-5 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">3. Live Output & Artifacts</span>
                <button onclick="copyCode()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded border border-borderCol transition">Kopēt kodu 📋</button>
            </div>
            
            <div class="flex-1 p-3 overflow-hidden flex flex-col">
                <div class="text-xs text-slate-400 mb-2 flex justify-between items-center">
                    <span id="artifactTitle" class="font-mono text-emerald-400">server.py</span>
                    <span class="text-[10px] text-slate-500 uppercase">Gatavs lietošanai</span>
                </div>
                <div class="flex-1 bg-slate-950 rounded-lg p-3 overflow-auto border border-borderCol">
                    <pre><code id="artifactCode" class="language-python text-xs font-mono"></code></pre>
                </div>
            </div>
        </section>

    </main>

    <script>
        async function fetchState() {
            const res = await fetch('/api/state');
            const data = await res.json();
            renderChat(data.messages);
            renderTasks(data.tasks);
            renderArtifact(data.artifacts[0]);
        }

        function renderChat(messages) {
            const box = document.getElementById('chatMessages');
            box.innerHTML = messages.map(m => `
                <div class="p-2.5 rounded-lg text-xs bg-slate-900/70 border border-slate-800">
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-bold text-blue-400">${m.sender}</span>
                        <span class="text-[10px] text-slate-500">${m.time}</span>
                    </div>
                    <div class="text-slate-200">${m.text}</div>
                </div>
            `).join('');
            box.scrollTop = box.scrollHeight;
        }

        function renderTasks(tasks) {
            const box = document.getElementById('taskList');
            const statusColors = {
                'Drafted': 'bg-amber-950 text-amber-400 border-amber-800',
                'In Progress': 'bg-blue-950 text-blue-400 border-blue-800',
                'Done': 'bg-emerald-950 text-emerald-400 border-emerald-800'
            };
            box.innerHTML = tasks.map(t => `
                <div class="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800 flex justify-between items-center">
                    <div>
                        <div class="text-xs font-medium text-slate-200">${t.title}</div>
                    </div>
                    <span class="text-[10px] px-2 py-0.5 rounded-full border ${statusColors[t.status] || 'bg-slate-800 text-slate-300'}">
                        ${t.status}
                    </span>
                </div>
            `).join('');
        }

        function renderArtifact(art) {
            if(!art) return;
            document.getElementById('artifactTitle').innerText = art.title;
            const codeEl = document.getElementById('artifactCode');
            codeEl.innerText = art.code;
            codeEl.className = 'language-' + (art.lang || 'python');
            hljs.highlightElement(codeEl);
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const author = document.getElementById('authorSelect').value;
            const text = input.value.trim();
            if(!text) return;
            
            await fetch('/api/message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ sender: author, text: text })
            });
            input.value = '';
            fetchState();
        }

        async function createTask() {
            const input = document.getElementById('newTaskTitle');
            const title = input.value.trim();
            if(!title) return;

            await fetch('/api/task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ title: title })
            });
            input.value = '';
            fetchState();
        }

        function copyCode() {
            const code = document.getElementById('artifactCode').innerText;
            navigator.clipboard.writeText(code);
            alert("Kods nokopēts starpliktuvē!");
        }

        fetchState();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/state')
def get_state():
    return jsonify(load_state())

@app.route('/api/message', methods=['POST'])
def add_message():
    state = load_state()
    data = request.json
    now = datetime.now().strftime("%H:%M")
    new_msg = {
        "id": len(state["messages"]) + 1,
        "sender": data.get("sender", "Viesturs"),
        "text": data.get("text", ""),
        "time": now
    }
    state["messages"].append(new_msg)
    save_state(state)
    return jsonify({"status": "ok"})

@app.route('/api/task', methods=['POST'])
def add_task():
    state = load_state()
    data = request.json
    new_task = {
        "id": len(state["tasks"]) + 1,
        "title": data.get("title", ""),
        "status": "In Progress",
        "desc": ""
    }
    state["tasks"].append(new_task)
    save_state(state)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("⚡ Aura Quadro OS Cockpit v0.1 griežas uz http://localhost:5000")
    app.run(port=5000, debug=True)
