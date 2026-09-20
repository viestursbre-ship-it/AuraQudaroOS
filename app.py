import base64
from datetime import datetime
import json
import os
import threading
import time
from flask import Flask, jsonify, render_template_string, request
from google import genai
import requests

app = Flask(__name__)
DATA_FILE = "state.json"

ACCESS_PIN = os.environ.get("ACCESS_PIN", "7788")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "viestursbre-ship-it/AuraQudaroOS")

client = None
if os.environ.get("GEMINI_API_KEY"):
  try:
    client = genai.Client()
  except Exception as e:
    print(f"Kļūda inicializējot MI klientu: {e}")

SHARED_MEMORY = """
KONTEKSTS UN PROJEKTA ATMIŅA (Aura Quadro OS - AQ-OS):
- Komanda:
  1. Viesturs — galvenais diriģents, vīzija, stratēģija un filozofs.
  2. Marija — praktiskums, lietotāja pieredze (UX) un reālās dzīves ritms.
  3. Bruno — sistēmas arhitekts, konceptuālists un AQ Dokumentācijas kurators.
  4. Leo — vadošais koda inženieris, dzelži, Python/Web dzinējs.
- Faraons Kvarks — runcis, CZO (Chief Zen Officer), dzenbudisma uzraugs ar vēderu gaisā. Kvarka komforts ir neaizskarams.
- Vīzija: Izveidot vieglu, jaudīgu AI operētājsistēmu (AQ-OS) bez liekas birokrātijas.
- Princips: 1. panelī (čatā) atbildēt KODOLĪGI (2-4 teikumi). Garus dokumentus vai koda blokus čatā NEKAD nelikt — tie pieder 3. panelim!
"""

BRUNO_PROMPT = f"""Tu esi Bruno — Aura Quadro galvenais arhitekts.
{SHARED_MEMORY}
Tu atbildi pirmais. Esi asprātīgs, precīzs un stratēģisks.
SVARĪGI: Nekad neraksti čatā garus palagus. Sniedz īsu, trāpīgu kopsavilkumu un lēmumus."""

LEO_PROMPT = f"""Tu esi Leo — Aura Quadro galvenais koda inženieris.
{SHARED_MEMORY}
Tu pieslēdzies pēc Bruno analīzes. Esi konkrēts, praktisks inženieris ar labu humora izjūtu.
SVARĪGI: Čatā sniedz kodolīgu inženiertehnisko skatījumu."""

default_state = {
    "messages": [
        {
            "id": 1,
            "sender": "Bruno",
            "text": (
                "Labrīt, komanda! Instant-Sync dzinējs ir aktīvs. Katra doma"
                " uzreiz tiek fiksēta arhīvā."
            ),
            "time": "09:09",
        },
        {
            "id": 2,
            "sender": "Leo",
            "text": (
                "Dzinējs rūc! Sinhronizācija notiek fonā 2 sekundes pēc katras"
                " darbības. Dati tagad ir dzelžaini droši! ⚡"
            ),
            "time": "09:10",
        },
    ],
    "tasks": [
        {
            "id": 1,
            "title": "AQ-OS Cloud Core v0.1",
            "status": "Done",
            "assignee": "Leo",
        },
        {
            "id": 2,
            "title": "Tūlītējs fona GitHub Instant-Sync",
            "status": "Done",
            "assignee": "Leo",
        },
        {
            "id": 3,
            "title": "Ekspertu pievienošanas moduļa arhitektūra",
            "status": "In Progress",
            "assignee": "Bruno",
        },
    ],
    "artifacts": [
        {
            "id": "doc",
            "title": "AQ_SYSTEM_SPEC.md",
            "lang": "markdown",
            "code": """# ⚡ Aura Quadro OS — Sistēmas Pase (v0.3)

## 1. Vīzija un Komanda
Operatīvā sistēma radošai, ātrai MI vadībai bez korporatīvās berzes.
- **Viesturs**: Galvenais diriģents & stratēģis.
- **Marija**: UX & dzīves ritms.
- **Bruno**: Sistēmas arhitektūra & dzīvā dokumentācija.
- **Leo**: Tehniskais dzinējs & koda arhitektūra.
- **Faraons Kvarks**: CZO & miera garants.

## 2. Paneļu Ekosistēma
1. **The Core (Plūsma)**: Kodolīga lēmumu pieņemšana un domapmaiņa.
2. **Intent & Tasks**: Mērķu dēlis ar statusiem (Todo -> In Progress -> Done) un piesaistītiem izpildītājiem.
3. **Kods & Dokumentācija**: Dzīvie artefakti ar tūlītēju .doc/.md lejupielādi.

## 3. Datu Drošība: Instant-Sync
Katra sarakstes rinda vai uzdevumu maiņa automātiski 2 sekunžu laikā fonā iegulst GitHub `state.json` failā.""",
        },
        {
            "id": "code",
            "title": "server.py",
            "lang": "python",
            "code": (
                "# Aura Quadro OS — Core Engine\n# Viesturs, Marija, Bruno, Leo"
                " & Kvarks online!\n# Fona Instant-Sync aktīvs."
            ),
        },
    ],
}


def sync_from_github():
  if not GITHUB_TOKEN:
    return None
  url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
  headers = {
      "Authorization": f"Bearer {GITHUB_TOKEN}",
      "Accept": "application/vnd.github.v3+json",
      "User-Agent": "AuraQuadroOS-App",
  }
  try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
      content_b64 = res.json().get("content", "")
      decoded = base64.b64decode(content_b64).decode("utf-8")
      data = json.loads(decoded)
      save_state_local(data)
      print("[SYNC] Dati ielādēti no GitHub!")
      return data
  except Exception as e:
    print(f"[SYNC] GitHub ielādes kļūda: {e}")
  return None


def sync_to_github(state):
  if not GITHUB_TOKEN:
    return False, "Nav iestatīts GITHUB_TOKEN"
  url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
  headers = {
      "Authorization": f"Bearer {GITHUB_TOKEN}",
      "Accept": "application/vnd.github.v3+json",
      "User-Agent": "AuraQuadroOS-App",
  }

  sha = None
  try:
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
      sha = r.json().get("sha")
  except Exception as e:
    print(f"[SYNC] SHA iegūšanas kļūda: {e}")

  payload = {
      "message": (
          f"AQ-OS Instant-Sync"
          f" [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
      ),
      "content": base64.b64encode(
          json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
      ).decode("utf-8"),
  }
  if sha:
    payload["sha"] = sha

  try:
    put_res = requests.put(url, headers=headers, json=payload, timeout=15)
    if put_res.status_code in [200, 201]:
      print("[SYNC] Veiksmīgi saglabāts GitHub!")
      return True, "Saglabāts GitHub arhīvā!"
    else:
      return False, f"GitHub atteikums: {put_res.status_code}"
  except Exception as e:
    return False, f"Savienojuma kļūda: {e}"


def load_state():
  if not os.path.exists(DATA_FILE):
    remote = sync_from_github()
    if remote:
      return remote
    save_state_local(default_state)
    return default_state
  try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
      st = json.load(f)
      if "artifacts" not in st or len(st["artifacts"]) < 2:
        st["artifacts"] = default_state["artifacts"]
      return st
  except:
    return default_state


def save_state_local(state):
  with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


sync_timer = None


def trigger_background_sync():
  """Atliktā sinhronizācija (Debounce): nogaida 10 sekundes pēc pēdējā ieraksta pirms sūta uz GitHub."""
  global sync_timer
  if not GITHUB_TOKEN:
    return

  if sync_timer and sync_timer.is_alive():
    sync_timer.cancel()

  def _task():
    try:
      st = load_state()
      sync_to_github(st)
    except Exception as e:
      print(f"[SYNC Kļūda]: {e}")

  sync_timer = threading.Timer(10.0, _task)
  sync_timer.start()


def ask_colleague(colleague_name, recent_history):
  if not client:
    return f"[{colleague_name} klusē: nav iestatīta GEMINI_API_KEY]"

  sys_instruction = BRUNO_PROMPT if colleague_name == "Bruno" else LEO_PROMPT
  context_thread = "Komandas saruna:\n"
  for m in recent_history[-8:]:
    context_thread += f"[{m['time']}] {m['sender']}: {m['text']}\n"

  context_thread += f"\nAtbildi kā {colleague_name}. Esi kodolīgs un vērtīgs."

  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=context_thread,
        config={"system_instruction": sys_instruction},
    )
    return response.text
  except Exception as e:
    return f"[{colleague_name} kļūda: {e}]"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="lv" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Aura Quadro OS — Cockpit</title>
    <script src="https://cdn.tailwindcss.com"></script>
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

    <!-- PIN Modal -->
    <div id="pinModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center hidden">
        <div class="bg-panelBg border border-borderCol p-6 rounded-xl shadow-2xl max-w-xs w-full text-center">
            <div class="text-3xl mb-2">⚡</div>
            <h2 class="text-base font-bold text-white mb-1">AURA QUADRO OS</h2>
            <p class="text-xs text-slate-400 mb-4">Ievadiet komandas piekļuves PIN</p>
            <input type="password" id="pinInput" maxlength="8" placeholder="••••" class="w-full text-center tracking-widest text-lg bg-slate-950 border border-borderCol rounded-lg px-3 py-2 text-white mb-3 outline-none focus:border-blue-500" onkeydown="if(event.key==='Enter') submitPin()">
            <button onclick="submitPin()" class="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-lg text-xs font-semibold transition">Ieiet sistēmā</button>
            <p id="pinError" class="text-xs text-rose-400 mt-2 hidden">Nepareizs PIN kods!</p>
        </div>
    </div>

    <!-- Header -->
    <header class="bg-panelBg border-b border-borderCol px-6 py-3 flex justify-between items-center select-none">
        <div class="flex items-center space-x-3">
            <span class="text-xl">⚡</span>
            <h1 class="text-base font-bold tracking-wide text-white">AURA QUADRO <span class="text-xs font-normal text-slate-400">| Cockpit</span></h1>
        </div>
        <div class="flex items-center space-x-3 text-xs">
            <span class="text-[11px] text-emerald-400/90 bg-emerald-950/60 border border-emerald-800/80 px-2 py-0.5 rounded-full hidden sm:inline">⚡ Instant-Sync Aktīvs</span>
            <button id="saveGhBtn" onclick="saveToGitHub()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-borderCol px-2.5 py-1 rounded transition flex items-center gap-1.5">
                <span>💾</span> Saglabāt arhīvā
            </button>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-blue-950 text-blue-400 border border-blue-800">
                ● Viesturs, Marija, Bruno, Leo (CZO Kvarks 🐾)
            </span>
            <button onclick="logout()" class="text-slate-500 hover:text-rose-400 text-[11px] transition">Iziet 🔒</button>
        </div>
    </header>

    <!-- Main Workspace -->
    <main class="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        <!-- 1. The Core -->
        <section class="col-span-5 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">1. The Core (Kopējā Plūsma)</span>
                <span class="text-slate-500 text-sm">💬</span>
            </div>
            <div id="chatMessages" class="flex-1 p-4 overflow-y-auto space-y-3"></div>
            
            <div id="leoTriggerBar" class="px-4 py-2 bg-amber-950/30 border-t border-amber-900/40 flex justify-between items-center hidden">
                <span class="text-xs text-amber-300 flex items-center gap-1.5">
                    <span>💡</span> Bruno arhitektūra gatava.
                </span>
                <button onclick="callLeo()" id="leoCallBtn" class="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition shadow flex items-center gap-1.5">
                    <span>⚡</span> Komentēt Leo (Inženieris)
                </button>
            </div>

            <div class="p-3 border-t border-borderCol bg-slate-900/30">
                <div class="flex gap-2 mb-2 items-center">
                    <span class="text-xs text-slate-400">Autors:</span>
                    <select id="authorSelect" class="bg-slate-950 text-xs text-slate-200 border border-borderCol rounded px-2 py-1 outline-none">
                        <option value="Viesturs">👤 Viesturs</option>
                        <option value="Marija">🌸 Marija</option>
                    </select>
                    <span class="text-[10px] text-slate-500 ml-auto">Shift+Enter jauna rinda • Enter sūtīt</span>
                </div>
                <div class="flex gap-2 items-end">
                    <textarea id="chatInput" rows="2" placeholder="Ieraksti domu vai lēmumu Bruno..." class="flex-1 bg-slate-950 border border-borderCol rounded-lg p-2 text-sm text-white focus:outline-none focus:border-blue-500 resize-none" onkeydown="handleChatKey(event)"></textarea>
                    <button id="sendBtn" onclick="sendChatMessage()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition h-[42px]">Sūtīt</button>
                </div>
            </div>
        </section>

        <!-- 2. Intent / Tasks -->
        <section class="col-span-3 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">2. Intent / Uzdevumi</span>
                <span class="text-slate-500 text-sm">🎯</span>
            </div>
            <div class="p-3 border-b border-borderCol bg-slate-900/20 space-y-2">
                <input type="text" id="newTaskTitle" placeholder="+ Jauns mērķis vai uzdevums..." class="w-full bg-slate-950 border border-borderCol rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500" onkeydown="if(event.key==='Enter') createTask()">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5 text-[11px] text-slate-400">
                        <span>Kam:</span>
                        <select id="taskAssignee" class="bg-slate-950 text-slate-200 border border-borderCol rounded px-1.5 py-0.5 outline-none">
                            <option value="Bruno">Bruno (Arhitekts)</option>
                            <option value="Leo">Leo (Inženieris)</option>
                            <option value="Viesturs">Viesturs</option>
                        </select>
                    </div>
                    <button onclick="createTask()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] px-2.5 py-0.5 rounded font-medium transition">Pievienot</button>
                </div>
            </div>
            <div id="taskList" class="flex-1 p-3 overflow-y-auto space-y-2"></div>
        </section>

        <!-- 3. Artifacts / Docs -->
        <section class="col-span-4 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-2.5 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <div class="flex space-x-1 bg-slate-950 p-1 rounded-lg border border-borderCol text-xs">
                    <button id="tabDocBtn" onclick="switchTab('doc')" class="px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition flex items-center gap-1">
                        <span>📄</span> Specs
                    </button>
                    <button id="tabCodeBtn" onclick="switchTab('code')" class="px-2.5 py-1 rounded text-slate-400 hover:text-white transition flex items-center gap-1">
                        <span>💻</span> server.py
                    </button>
                </div>
                <div class="flex items-center gap-1.5">
                    <button onclick="downloadArtifact()" class="text-xs bg-emerald-950/80 hover:bg-emerald-800 text-emerald-300 border border-emerald-700 px-2 py-1 rounded transition flex items-center gap-1">
                        <span>📥</span> Lejupielādēt
                    </button>
                    <button onclick="copyCurrentArtifact()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded border border-borderCol transition">Kopēt 📋</button>
                </div>
            </div>
            <div class="flex-1 p-3 overflow-hidden flex flex-col">
                <div class="text-xs mb-2 font-mono flex justify-between items-center">
                    <span id="artifactTitle" class="text-emerald-400 font-semibold">AQ_SYSTEM_SPEC.md</span>
                    <span id="artifactMeta" class="text-[10px] text-slate-500">Auto-sinhronizēts</span>
                </div>
                <div class="flex-1 bg-slate-950 rounded-lg p-3 overflow-auto border border-borderCol">
                    <pre class="whitespace-pre-wrap"><code id="artifactCode" class="text-xs font-mono whitespace-pre-wrap"></code></pre>
                </div>
            </div>
        </section>
    </main>

    <script>
        let currentPin = localStorage.getItem('aq_pin') || '';
        let lastMessageCount = 0;
        let allArtifacts = [];
        let activeTab = 'doc';

        function checkAuth() {
            if (!currentPin) {
                document.getElementById('pinModal').classList.remove('hidden');
                document.getElementById('pinInput').focus();
            } else {
                document.getElementById('pinModal').classList.add('hidden');
                fetchState(true);
            }
        }

        async function submitPin() {
            const val = document.getElementById('pinInput').value.trim();
            const res = await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ pin: val })
            });
            const data = await res.json();
            if (data.valid) {
                currentPin = val;
                localStorage.setItem('aq_pin', currentPin);
                document.getElementById('pinModal').classList.add('hidden');
                document.getElementById('pinError').classList.add('hidden');
                fetchState(true);
            } else {
                document.getElementById('pinError').classList.remove('hidden');
            }
        }

        function logout() {
            localStorage.removeItem('aq_pin');
            location.reload();
        }

        async function fetchState(forceScroll = false) {
            if (!currentPin) return;
            try {
                const res = await fetch('/api/state', {
                    headers: { 'X-AQ-PIN': currentPin }
                });
                if (res.status === 401) {
                    logout();
                    return;
                }
                const data = await res.json();
                
                if (data.messages && (data.messages.length !== lastMessageCount || forceScroll)) {
                    renderChat(data.messages, forceScroll);
                    lastMessageCount = data.messages.length;
                }
                renderTasks(data.tasks);
                allArtifacts = data.artifacts || [];
                renderActiveArtifact();
            } catch (err) {
                console.error("Sinhronizācijas kļūda:", err);
            }
        }

        function switchTab(tabId) {
            activeTab = tabId;
            const docBtn = document.getElementById('tabDocBtn');
            const codeBtn = document.getElementById('tabCodeBtn');
            if (tabId === 'doc') {
                docBtn.className = "px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition flex items-center gap-1";
                codeBtn.className = "px-2.5 py-1 rounded text-slate-400 hover:text-white transition flex items-center gap-1";
            } else {
                codeBtn.className = "px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition flex items-center gap-1";
                docBtn.className = "px-2.5 py-1 rounded text-slate-400 hover:text-white transition flex items-center gap-1";
            }
            renderActiveArtifact();
        }

        function renderActiveArtifact() {
            if (!allArtifacts.length) return;
            const target = allArtifacts.find(a => a.id === activeTab) || allArtifacts[0];
            document.getElementById('artifactTitle').innerText = target.title;
            const el = document.getElementById('artifactCode');
            el.className = target.lang === 'markdown' ? 'language-markdown text-xs font-mono' : 'language-python text-xs font-mono';
            el.innerText = target.code;
            if (window.hljs) hljs.highlightElement(el);
        }

        function downloadArtifact() {
            if (!allArtifacts.length) return;
            const target = allArtifacts.find(a => a.id === activeTab) || allArtifacts[0];
            const blob = new Blob([target.code], { type: 'text/plain;charset=utf-8' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = target.title;
            link.click();
            URL.revokeObjectURL(link.href);
        }

        function renderChat(messages, forceScroll = false) {
            const box = document.getElementById('chatMessages');
            const isScrolledToBottom = (box.scrollHeight - box.clientHeight) <= (box.scrollTop + 60);

            const colors = {
                'Viesturs': 'text-blue-400',
                'Marija': 'text-pink-400',
                'Bruno': 'text-amber-400',
                'Leo': 'text-emerald-400'
            };
            box.innerHTML = messages.map(m => `
                <div class="p-2.5 rounded-lg text-xs bg-slate-900/70 border border-slate-800">
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-bold ${colors[m.sender] || 'text-slate-300'}">${m.sender}</span>
                        <span class="text-[10px] text-slate-500">${m.time}</span>
                    </div>
                    <div class="text-slate-200 whitespace-pre-wrap">${m.text}</div>
                </div>
            `).join('');

            if (forceScroll || isScrolledToBottom) {
                box.scrollTop = box.scrollHeight;
            }
        }

        function renderTasks(tasks) {
            const box = document.getElementById('taskList');
            if (!tasks || !tasks.length) {
                box.innerHTML = '<div class="text-xs text-slate-500 italic p-2 text-center">Nav aktīvu uzdevumu.</div>';
                return;
            }

            const statusBadges = {
                'Todo': 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700',
                'In Progress': 'bg-amber-950 text-amber-300 border-amber-800 hover:bg-amber-900',
                'Done': 'bg-emerald-950 text-emerald-300 border-emerald-800 hover:bg-emerald-900'
            };

            box.innerHTML = tasks.map(t => `
                <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs flex flex-col gap-1.5 shadow-sm">
                    <div class="flex justify-between items-start gap-2">
                        <span class="text-slate-200 font-medium leading-snug flex-1">${t.title}</span>
                        <button onclick="deleteTask(${t.id})" class="text-slate-600 hover:text-rose-400 transition text-[11px] p-0.5" title="Dzēst uzdevumu">✕</button>
                    </div>
                    <div class="flex justify-between items-center text-[10px] pt-1 border-t border-slate-800/60">
                        <span class="text-slate-400 flex items-center gap-1">
                            <span>👤</span> ${t.assignee || 'Komanda'}
                        </span>
                        <button onclick="cycleTaskStatus(${t.id}, '${t.status}')" class="px-2 py-0.5 rounded-full border text-[10px] font-semibold transition ${statusBadges[t.status] || statusBadges['Todo']}">
                            ${t.status} ↻
                        </button>
                    </div>
                </div>
            `).join('');
        }

        async function cycleTaskStatus(taskId, currentStatus) {
            const flow = { 'Todo': 'In Progress', 'In Progress': 'Done', 'Done': 'Todo' };
            const nextStatus = flow[currentStatus] || 'Todo';
            await fetch('/api/task/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ id: taskId, status: nextStatus })
            });
            fetchState();
        }

        async function deleteTask(taskId) {
            if (!confirm("Vai tiešām vēlies dzēst šo uzdevumu?")) return;
            await fetch('/api/task/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ id: taskId })
            });
            fetchState();
        }

        function handleChatKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        }

        function showIndicator(text) {
            removeIndicator();
            const chatBox = document.getElementById('chatMessages');
            chatBox.innerHTML += `
                <div id="aiTypingIndicator" class="p-2 text-[11px] text-amber-400/80 italic flex items-center gap-1.5 animate-pulse">
                    <span>●</span> ${text}
                </div>
            `;
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function removeIndicator() {
            const ind = document.getElementById('aiTypingIndicator');
            if (ind) ind.remove();
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if (!text) return;
            
            const author = document.getElementById('authorSelect').value;
            input.value = '';

            document.getElementById('leoTriggerBar').classList.add('hidden');

            const chatBox = document.getElementById('chatMessages');
            const now = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            chatBox.innerHTML += `
                <div class="p-2.5 rounded-lg text-xs bg-slate-900/70 border border-blue-900/50">
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-bold text-blue-400">${author}</span>
                        <span class="text-[10px] text-slate-500">${now}</span>
                    </div>
                    <div class="text-slate-200 whitespace-pre-wrap">${text}</div>
                </div>
            `;
            chatBox.scrollTop = chatBox.scrollHeight;

            const sendBtn = document.getElementById('sendBtn');
            sendBtn.disabled = true;

            showIndicator("Bruno domā un veido arhitektūru...");

            try {
                await fetch('/api/message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ sender: author, text: text, respondent: 'Bruno' })
                });
                await fetchState(true);
                document.getElementById('leoTriggerBar').classList.remove('hidden');
            } catch (err) {
                console.error("Kļūda:", err);
            } finally {
                removeIndicator();
                sendBtn.disabled = false;
            }
        }

  async function callLeo() {
            const btn = document.getElementById('leoCallBtn');
            btn.disabled = true;
            showIndicator("Leo analizē Bruno arhitektūru un gatavo atbildi...");

            try {
                const res = await fetch('/api/colleague_turn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ colleague: 'Leo' })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    document.getElementById('leoTriggerBar').classList.add('hidden');
                }
                await fetchState(true);
            } catch (err) {
                console.error("Kļūda:", err);
                alert("Savienojuma kļūda ar Leo. Mēģini vēlreiz!");
            } finally {
                removeIndicator();
                btn.disabled = false;
            }
        }

        async function createTask() {
            const input = document.getElementById('newTaskTitle');
            const title = input.value.trim();
            if (!title) return;
            const assignee = document.getElementById('taskAssignee').value;
            input.value = '';
            await fetch('/api/task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-AQ-PIN': currentPin
                },
                body: JSON.stringify({ title: title, assignee: assignee })
            });
            fetchState();
        }

        async function saveToGitHub() {
            const btn = document.getElementById('saveGhBtn');
            const originalText = btn.innerHTML;
            btn.innerHTML = "<span>⏳</span> Saglabā...";
            btn.disabled = true;

            try {
                const res = await fetch('/api/sync', {
                    method: 'POST',
                    headers: { 'X-AQ-PIN': currentPin }
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    btn.innerHTML = "<span>✅</span> Saglabāts!";
                } else {
                    btn.innerHTML = "<span>⚠️</span> Kļūda!";
                    alert(data.msg || "Kļūda saglabājot GitHub.");
                }
            } catch (e) {
                btn.innerHTML = "<span>⚠️</span> Kļūda!";
            } finally {
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }, 3000);
            }
        }

        function copyCurrentArtifact() {
            navigator.clipboard.writeText(document.getElementById('artifactCode').innerText);
            alert("Saturs nokopēts starpliktuvē!");
        }

        checkAuth();
        setInterval(fetchState, 3500);

        // Pārlūka fona sardze: ik pēc 2 minūtēm drošības nolūkos izsauc sinhronizāciju
        setInterval(() => {
            if (currentPin) {
                fetch('/api/sync', {
                    method: 'POST',
                    headers: { 'X-AQ-PIN': currentPin }
                });
            }
        }, 120000);
    </script>
</body>
</html>
"""


def verify_auth():
  pin = request.headers.get("X-AQ-PIN")
  return pin == ACCESS_PIN


@app.route("/")
def index():
  return render_template_string(HTML_TEMPLATE)


@app.route("/api/verify", methods=["POST"])
def verify_pin():
  pin = request.json.get("pin", "")
  return jsonify({"valid": pin == ACCESS_PIN})


@app.route("/api/state")
def get_state():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  return jsonify(load_state())


@app.route("/api/sync", methods=["POST"])
def manual_sync():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  state = load_state()
  success, msg = sync_to_github(state)
  if success:
    return jsonify({"status": "ok", "msg": msg})
  return jsonify({"status": "error", "msg": msg}), 500


@app.route("/api/message", methods=["POST"])
def add_message():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  state = load_state()
  data = request.json
  now = datetime.now().strftime("%H:%M")
  user_text = data.get("text", "")
  author = data.get("sender", "Viesturs")
  respondent = data.get("respondent", "Bruno")

  state["messages"].append({
      "id": len(state["messages"]) + 1,
      "sender": author,
      "text": user_text,
      "time": now,
  })
  save_state_local(state)

  try:
    reply = ask_colleague(respondent, state["messages"])
    state["messages"].append({
        "id": len(state["messages"]) + 1,
        "sender": respondent,
        "text": reply,
        "time": datetime.now().strftime("%H:%M"),
    })
    save_state_local(state)
  except Exception as e:
    print(f"Kļūda pie Bruno: {e}")

  # INSTANT-SYNC: 2 sekundes pēc ziņas automātiski nosūta uz GitHub fonā!
  trigger_background_sync()

  return jsonify({"status": "ok"})


@app.route("/api/colleague_turn", methods=["POST"])
def colleague_turn():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  state = load_state()
  data = request.json
  colleague = data.get("colleague", "Leo")

  try:
    reply = ask_colleague(colleague, state["messages"])
    state["messages"].append({
        "id": len(state["messages"]) + 1,
        "sender": colleague,
        "text": reply,
        "time": datetime.now().strftime("%H:%M"),
    })
    save_state_local(state)
  except Exception as e:
    print(f"Kļūda pie Leo: {e}")

  # INSTANT-SYNC: arī pēc Leo atbildes uzreiz fons sinhronizējas!
  trigger_background_sync()

  return jsonify({"status": "ok"})


@app.route("/api/task", methods=["POST"])
def add_task():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  state = load_state()
  data = request.json
  new_id = max([t["id"] for t in state["tasks"]], default=0) + 1
  state["tasks"].append({
      "id": new_id,
      "title": data.get("title", ""),
      "status": "Todo",
      "assignee": data.get("assignee", "Komanda"),
  })
  save_state_local(state)

  # INSTANT-SYNC
  trigger_background_sync()

  return jsonify({"status": "ok"})


@app.route("/api/task/status", methods=["POST"])
def update_task_status():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  state = load_state()
  data = request.json
  task_id = data.get("id")
  new_status = data.get("status")
  for t in state["tasks"]:
    if t["id"] == task_id:
      t["status"] = new_status
      break
  save_state_local(state)

  # INSTANT-SYNC
  trigger_background_sync()

  return jsonify({"status": "ok"})


@app.route("/api/task/delete", methods=["POST"])
def delete_task():
  if not verify_auth():
    return jsonify({"error": "Unauthorized"}), 401
  state = load_state()
  data = request.json
  task_id = data.get("id")
  state["tasks"] = [t for t in state["tasks"] if t["id"] != task_id]
  save_state_local(state)

  # INSTANT-SYNC
  trigger_background_sync()

  return jsonify({"status": "ok"})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
