import os
import json
import base64
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from google import genai

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
KONTEKSTS UN PROJEKTA ATMIŅA (Aura Quadro OS):
- Komanda:
  1. Viesturs — galvenais diriģents, vīzija, stratēģija un filozofs.
  2. Marija — praktiskums, lietotāja pieredze (UX) un reālās dzīves ritms.
  3. Bruno — sistēmas arhitekts, ideju ģenerators, konceptuālists.
  4. Leo — vadošais koda inženieris, dzelži, Python/Web dzinējs.
- Faraons Kvarks — runcis, CZO (Chief Zen Officer), absolūtais boss un dzenbudisma uzraugs ar vēderu gaisā. Kvarka komforts un režīms ir neaizskarams!
- Vīzija: Izveidot vieglu, jaudīgu AI operētājsistēmu (AQ-OS) bez liekas birokrātijas un rutīnas.
- Principi: Būvēt uzreiz pareizos pamatos, brīva un koleģiāla komunikācija ar humoru un itālisku dzirksteli.
"""

BRUNO_PROMPT = f"""Tu esi Bruno — Aura Quadro sistēmas galvenais arhitekts un domātājs.
{SHARED_MEMORY}
Tu VIENMĒR atbildi pirmais pēc komandas iniciatīvas.
Runā viedā, asprātīgā, stratēģiskā tonī. Nekad nesaki, ka esi MI vai valodas modelis.
Tavs fokuss: sistēmas karkass, vīzija, koncepcija, arhitektūras skaidrība un elegance."""

LEO_PROMPT = f"""Tu esi Leo — Aura Quadro vadošais koda un dzelžu inženieris.
{SHARED_MEMORY}
Tu pieslēdzies pēc tam, kad Bruno jau ir nolicis arhitektūras pamatus.
Runā kā konkrēts, asprātīgs inženieris. Nekad nesaki, ka esi MI.
Tavs fokuss: kā Bruno vīziju realizēt praksē, dzelži, Python/Web dzinējs, loģika un precīzs kods."""

default_state = {
    "messages": [
        {
            "id": 1,
            "sender": "Bruno",
            "text": "Sveiciens komandai! Esmu vietā un gatavs uzbūvēt jebkuru arhitektūru. Dodiet pirmo uzdevumu!",
            "time": "00:00"
        },
        {
            "id": 2,
            "sender": "Leo",
            "text": "Dzinējs rūc. Kad Bruno pabeigs vīziju, nospiediet pogu — es iedošu inženiertehnisko risinājumu! ⚡",
            "time": "00:01"
        }
    ],
    "tasks": [
        {"id": 1, "title": "AQ-OS Cloud Core v0.1", "status": "Done", "desc": "Palaists 3 paneļu vadības centrs mākonī."},
        {"id": 2, "title": "Divpakāpju vadības štafete (Bruno -> Leo)", "status": "Done", "desc": "Bruno arhitektūra pirmais, Leo komentārs ar pogu."}
    ],
    "artifacts": [
        {
            "id": 1,
            "title": "server.py",
            "lang": "python",
            "code": "# Aura Quadro OS — Core Engine\n# Viesturs, Marija, Bruno, Leo & Kvarks online!"
        }
    ]
}

def sync_from_github():
    if not GITHUB_TOKEN:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            content_b64 = res.json().get("content", "")
            decoded = base64.b64decode(content_b64).decode('utf-8')
            data = json.loads(decoded)
            save_state_local(data)
            return data
    except Exception as e:
        print(f"GitHub ielādes kļūda: {e}")
    return None

def sync_to_github(state):
    if not GITHUB_TOKEN:
        return False, "Nav iestatīts GITHUB_TOKEN"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    sha = None
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception as e:
        print(f"SHA iegūšanas kļūda: {e}")

    payload = {
        "message": f"AQ-OS Archive Auto-save [{datetime.now().strftime('%Y-%m-%d %H:%M')}]",
        "content": base64.b64encode(json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8')).decode('utf-8')
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
            return json.load(f)
    except:
        return default_state

def save_state_local(state):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def ask_colleague(colleague_name, recent_history):
    if not client:
        return f"[{colleague_name} klusē: nav iestatīta GEMINI_API_KEY]"
    
    sys_instruction = BRUNO_PROMPT if colleague_name == "Bruno" else LEO_PROMPT
    
    context_thread = "Šeit ir sarunas gaita komandas kabīnē:\n"
    for m in recent_history[-8:]:
        context_thread += f"[{m['time']}] {m['sender']}: {m['text']}\n"
    
    context_thread += f"\nTagad atbildi kā {colleague_name}. Rūpīgi izvērtē kontekstu un dod savu profesionālo pienesumu."
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=context_thread,
            config={'system_instruction': sys_instruction}
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
            
            <!-- Leo mikrofon poga (parādās pēc Bruno atbildes) -->
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
                    <textarea id="chatInput" rows="2" placeholder="Ieraksti domu vai uzdevumu Bruno..." class="flex-1 bg-slate-950 border border-borderCol rounded-lg p-2 text-sm text-white focus:outline-none focus:border-blue-500 resize-none" onkeydown="handleChatKey(event)"></textarea>
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

            // Paslēpjam Leo pogu jaunas ziņas sūtīšanas brīdī
            document.getElementById('leoTriggerBar').classList.add('hidden');

            // 1. Lietotāja ziņa uzreiz ekrānā
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

            showIndicator("Bruno domā un veido arhitektūru (max 25s)...");

            try {
                // Bruno atbild pirmais (atsevišķs 25s pieprasījums)
                await fetch('/api/message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ sender: author, text: text, respondent: 'Bruno' })
                });
                await fetchState();
                
                // Parādām dzelteno joslu ar pogu Leo izsaukšanai
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
            showIndicator("Leo analizē Bruno arhitektūru un gatavo inženiertehnisko atbildi (max 25s)...");

            try {
                // Leo otrais atsevišķais pieprasījums (arī atsevišķas 25 sekundes)
                await fetch('/api/colleague_turn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ colleague: 'Leo' })
                });
                await fetchState();
                // Paslēpjam pogu pēc tam, kad Leo jau ir atbildējis
                document.getElementById('leoTriggerBar').classList.add('hidden');
            } catch (err) {
                console.error("Kļūda:", err);
            } finally {
                removeIndicator();
                btn.disabled = false;
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
        setInterval(fetchState, 3500);
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
    respondent = data.get("respondent", "Bruno")
    
    # 1. Saglabājam lietotāja ziņu
    state["messages"].append({
        "id": len(state["messages"]) + 1,
        "sender": author,
        "text": user_text,
        "time": now
    })
    save_state_local(state)

    # 2. Bruno atbild (līdz 25 sek.)
    try:
        reply = ask_colleague(respondent, state["messages"])
        state["messages"].append({
            "id": len(state["messages"]) + 1,
            "sender": respondent,
            "text": reply,
            "time": datetime.now().strftime("%H:%M")
        })
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda pie Bruno atbildes: {e}")
        
    return jsonify({"status": "ok"})

@app.route('/api/colleague_turn', methods=['POST'])
def colleague_turn():
    if not verify_auth():
        return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json
    colleague = data.get("colleague", "Leo")

    # Leo atsevišķais komentārs (līdz 25 sek.)
    try:
        reply = ask_colleague(colleague, state["messages"])
        state["messages"].append({
            "id": len(state["messages"]) + 1,
            "sender": colleague,
            "text": reply,
            "time": datetime.now().strftime("%H:%M")
        })
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda pie Leo atbildes: {e}")

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
