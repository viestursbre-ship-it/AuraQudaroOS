import base64
from datetime import datetime
import json
import os
from flask import Flask, jsonify, render_template_string, request
from google import genai
import requests

app = Flask(__name__)
DATA_FILE = "state.json"

ACCESS_PIN = os.environ.get("ACCESS_PIN", "7788")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "viestursbre-ship-it/AuraQuadroOS")

client = None
if os.environ.get("GEMINI_API_KEY"):
  try:
    client = genai.Client()
  except Exception as e:
    print(f"Kļūda inicializējot MI klientu: {e}")

SHARED_MEMORY = """
KONTEKSTS UN PROJEKTA ATMIŅA (Aura Quadro OS):
- Komanda (4 prāti):
  1. Viesturs — galvenais diriģents, vīzija, stratēģija un filozofs.
  2. Marija — praktiskums, lietotāja pieredze (UX) un reālās dzīves ritms.
  3. Bruno — sistēmas arhitekts, ideju ģenerators, konceptuālists.
  4. Leo — vadošais koda inženieris, dzelži, Python/Web dzinējs.
- Faraons Kvarks — runcis, CZO (Chief Zen Officer), dzenbudisma un miera uzraugs ar vēderu gaisā.
- Vīzija: Izveidot vieglu, jaudīgu AI operētājsistēmu (AQ-OS) bez rutīnas un birokrātijas.
- Principi: Būvēt uzreiz pareizajos pamatos, nekādas bezjēdzīgas kopēšanas, brīva un koleģiāla komunikācija ar humoru un itālisku dzirksteli.
"""

BRUNO_PROMPT = f"""Tu esi Bruno — Aura Quadro komandas sistēmas arhitekts un domātājs.
{SHARED_MEMORY}
Runā dabiskā, viedā, koleģiālā un asprātīgā tonī. Nekad nesaki, ka esi valodas modelis.
Tavs fokuss: sistēmas karkass, UX loģika, idejas un filozofija. Rūpīgi iedziļinies visās saņemtajās kolēģu replikās."""

LEO_PROMPT = f"""Tu esi Leo — Aura Quadro komandas dalībnieks un vadošais koda inženieris.
{SHARED_MEMORY}
Runā dabiskā, asprātīgā, koleģiālā inženiera valodā. Nekad nesaki, ka esi MI.
Tev NAV jārunā tikai par kodu — iesaisties jebkurā sarunā, piedāvā domas par sistēmu, dzīvi un komandas plāniem. Kad vajadzīgs kods, iedod to precīzi."""

default_state = {
    "messages": [
        {
            "id": 1,
            "sender": "Bruno",
            "text": (
                "Sveiciens komandai! Bāze ir nofiksēta, un visi kanāli ir atvērti."
                " Viestur, Marija — esam gatavi darbam!"
            ),
            "time": "00:00",
        },
        {
            "id": 2,
            "sender": "Leo",
            "text": (
                "Dzinējs rūc nevainojami mākonī. GitHub arhīva sinhronizācija ir"
                " pieslēgta — tagad atmiņa ir neiznīcināma!"
            ),
            "time": "00:01",
        },
    ],
    "read_markers": {"Bruno": 2, "Leo": 2},
    "tasks": [
        {
            "id": 1,
            "title": "AQ-OS Cloud Core v0.1",
            "status": "Done",
            "desc": "Palaists 3 paneļu vadības centrs mākonī.",
        },
        {
            "id": 2,
            "title": "GitHub Sync integrācija",
            "status": "Done",
            "desc": "Sarakstes un datu fiksēšana GitHub krātuvē.",
        },
    ],
    "artifacts": [
        {
            "id": 1,
            "title": "server.py",
            "lang": "python",
            "code": "# Aura Quadro OS — Core Engine\n# Viesturs, Marija, Bruno, Leo & Kvarks online!",
        }
    ],
}


def sync_from_github():
  """Startējoties mēģina paņemt jaunāko state.json no GitHub."""
  if not GITHUB_TOKEN:
    return None
  url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
  headers = {
      "Authorization": f"token {GITHUB_TOKEN}",
      "Accept": "application/vnd.github.v3+json",
  }
  try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
      content_b64 = res.json().get("content", "")
      decoded = base64.b64decode(content_b64).decode("utf-8")
      data = json.loads(decoded)
      save_state_local(data)
      print("Dati veiksmīgi sinhronizēti no GitHub!")
      return data
  except Exception as e:
    print(f"GitHub ielādes kļūda: {e}")
  return None


def sync_to_github(state):
  """Saglabā state.json tieši GitHub repozitorijā ar jaunu commit."""
  if not GITHUB_TOKEN:
    return False, "Nav iestatīts GITHUB_TOKEN"
  url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
  headers = {
      "Authorization": f"token {GITHUB_TOKEN}",
      "Accept": "application/vnd.github.v3+json",
  }

  sha = None
  try:
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
      sha = r.json().get("sha")
  except Exception as e:
    print(f"Neizdevās iegūt esošo faila SHA: {e}")

  payload = {
      "message": (
          f"AQ-OS Archive Auto-save"
          f" [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"
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
      if "read_markers" not in st:
        st["read_markers"] = {"Bruno": 0, "Leo": 0}
      return st
  except:
    return default_state


def save_state_local(state):
  with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


def ask_colleague(colleague_name, unread_messages, recent_history):
  if not client:
    return f"[{colleague_name} klusē: nav iestatīta GEMINI_API_KEY]"

  sys_instruction = BRUNO_PROMPT if colleague_name == "Bruno" else LEO_PROMPT

  context_thread = "Šeit ir sarunas konteksts komandas čatā:\n"
  for m in recent_history[-6:]:
    context_thread += f"[{m['time']}] {m['sender']}: {m['text']}\n"

  context_thread += (
      f"\nJaunās neizlasītās ziņas, ko tev ({colleague_name}) tagad rūpīgi"
      " jāizlasa:\n"
  )
  for m in unread_messages:
    context_thread += f"[{m['time']}] {m['sender']}: {m['text']}\n"

  context_thread += (
      f"\nTagad atbildi kā {colleague_name}. Ņem vērā visu teikto un sniedz savu"
      " trāpīgo redzējumu."
  )

  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=context_thread,
        config={"system_instruction": sys_instruction},
    )
    return response.text
  except Exception as e:
    return f"[{colleague_name} savienojuma kļūda: {e}]"


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
            <button id="saveGhBtn" onclick="saveToGitHub()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-borderCol px-2.5 py-1 rounded transition flex items-center gap-1.5">
                <span>💾</span> Saglabāt arhīvā
            </button>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-blue-950 text-blue-400 border border-blue-800">
                ● Viesturs, Marija, Bruno, Leo
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
                    <textarea id="chatInput" rows="2" placeholder="Ieraksti ziņu komandai..." class="flex-1 bg-slate-950 border border-borderCol rounded-lg p-2 text-sm text-white focus:outline-none focus:border-blue-500 resize-none" onkeydown="handleChatKey(event)"></textarea>
                    <button onclick="sendChatMessage()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition h-[42px]">Sūtīt</button>
                </div>
            </div>
        </section>

        <!-- 2. Intent / Tasks -->
        <section class="col-span-3 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">2. Intent / Uzdevumi</span>
                <span class="text-slate-500 text-sm">🎯</span>
            </div>
            <div class="p-3 border-b border-borderCol bg-slate-900/20">
                <input type="text" id="newTaskTitle" placeholder="+ Jauns uzdevums..." class="w-full bg-slate-950 border border-borderCol rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500" onkeydown="if(event.key==='Enter') createTask()">
            </div>
            <div id="taskList" class="flex-1 p-3 overflow-y-auto space-y-2"></div>
        </section>

        <!-- 3. Artifacts -->
        <section class="col-span-4 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">3. Kods & Moduļi</span>
                <button onclick="copyCode()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded border border-borderCol transition">Kopēt 📋</button>
            </div>
            <div class="flex-1 p-3 overflow-hidden flex flex-col">
                <div class="text-xs text-slate-400 mb-2 font-mono text-emerald-400" id="artifactTitle">server.py</div>
                <div class="flex-1 bg-slate-950 rounded-lg p-3 overflow-auto border border-borderCol">
                    <pre><code id="artifactCode" class="language-python text-xs font-mono"></code></pre>
                </div>
            </div>
        </section>
    </main>

    <script>
        let currentPin = localStorage.getItem('aq_pin') || '';

        function checkAuth() {
            if (!currentPin) {
                document.getElementById('pinModal').classList.remove('hidden');
                document.getElementById('pinInput').focus();
            } else {
                document.getElementById('pinModal').classList.add('hidden');
                fetchState();
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
                fetchState();
            } else {
                document.getElementById('pinError').classList.remove('hidden');
            }
        }

        function logout() {
            localStorage.removeItem('aq_pin');
            location.reload();
        }

        async function fetchState() {
            if (!currentPin) return;
            const res = await fetch('/api/state', {
                headers: { 'X-AQ-PIN': currentPin }
            });
            if (res.status === 401) {
                logout();
                return;
            }
            const data = await res.json();
            renderChat(data.messages);
            renderTasks(data.tasks);
            renderArtifact(data.artifacts[0]);
        }

        function renderChat(messages) {
            const box = document.getElementById('chatMessages');
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
            box.scrollTop = box.scrollHeight;
        }

        function renderTasks(tasks) {
            const box = document.getElementById('taskList');
            box.innerHTML = tasks.map(t => `
                <div class="p-2 rounded bg-slate-900/70 border border-slate-800 flex justify-between items-center text-xs">
                    <span class="text-slate-200">${t.title}</span>
                    <span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-950 text-blue-400 border border-blue-800">${t.status}</span>
                </div>
            `).join('');
        }

        function renderArtifact(art) {
            if (!art) return;
            document.getElementById('artifactTitle').innerText = art.title;
            const el = document.getElementById('artifactCode');
            el.innerText = art.code;
            if (window.hljs) hljs.highlightElement(el);
        }

        function handleChatKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if (!text) return;
            
            const author = document.getElementById('authorSelect').value;
            input.value = '';

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
                <div id="aiTypingIndicator" class="p-2 text-[11px] text-amber-400/80 italic flex items-center gap-1.5 animate-pulse">
                    <span>●</span> Komanda domā...
                </div>
            `;
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                await fetch('/api/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-AQ-PIN': currentPin
                    },
                    body: JSON.stringify({ sender: author, text: text })
                });
            } catch (err) {
                console.error("Kļūda:", err);
            } finally {
                const ind = document.getElementById('aiTypingIndicator');
                if (ind) ind.remove();
                fetchState();
            }
        }

        async function createTask() {
            const input = document.getElementById('newTaskTitle');
            const title = input.value.trim();
            if (!title) return;
            input.value = '';
            await fetch('/api/task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-AQ-PIN': currentPin
                },
                body: JSON.stringify({ title: title })
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

        function copyCode() {
            navigator.clipboard.writeText(document.getElementById('artifactCode').innerText);
            alert("Kods nokopēts!");
        }

        checkAuth();
        setInterval(fetchState, 3000);
    </script>
</body>
</html>
"""

def verify_auth():
    pin = request.headers.get("X-AQ-PIN")
    return pin == ACCESS_PIN

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/verify', methods=['POST'])
def verify_pin():
    pin = request.json.get("pin", "")
    return jsonify({"valid": pin == ACCESS_PIN})

@app.route('/api/state')
def get_state():
    if not verify_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(load_state())

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    if not verify_auth():
        return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    success, msg = sync_to_github(state)
    if success:
        return jsonify({"status": "ok", "msg": msg})
    return jsonify({"status": "error", "msg": msg}), 500

@app.route('/api/message', methods=['POST'])
def add_message():
    if not verify_auth():
        return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json
    now = datetime.now().strftime("%H:%M")
    user_text = data.get("text", "")
    author = data.get("sender", "Viesturs")
    
    new_msg = {
        "id": len(state["messages"]) + 1,
        "sender": author,
        "text": user_text,
        "time": now
    }
    state["messages"].append(new_msg)
    save_state_local(state)
    
    txt = user_text.lower()
    if "leo" in txt or any(w in txt for w in ["kod", "skript", "python", "bug", "kļūd", "dzinēj"]):
        chosen = "Leo"
    elif "bruno" in txt or any(w in txt for w in ["arhitekt", "vīzij", "plān", "domā"]):
        chosen = "Bruno"
    else:
        last_ai = next((m["sender"] for m in reversed(state["messages"][:-1]) if m["sender"] in ["Bruno", "Leo"]), "Leo")
        chosen = "Bruno" if last_ai == "Leo" else "Leo"

    last_read_id = state.get("read_markers", {}).get(chosen, 0)
    unread = [m for m in state["messages"] if m["id"] > last_read_id]

    try:
        reply = ask_colleague(chosen, unread, recent_history=state["messages"])
        ai_msg = {
            "id": len(state["messages"]) + 1,
            "sender": chosen,
            "text": reply,
            "time": datetime.now().strftime("%H:%M")
        }
        state["messages"].append(ai_msg)
        state["read_markers"][chosen] = ai_msg["id"]
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda ģenerējot atbildi: {e}")
        
    return jsonify({"status": "ok"})

@app.route('/api/task', methods=['POST'])
def add_task():
    if not verify_auth():
        return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json
    state["tasks"].append({
        "id": len(state["tasks"]) + 1,
        "title": data.get("title", ""),
        "status": "In Progress"
    })
    save_state_local(state)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
