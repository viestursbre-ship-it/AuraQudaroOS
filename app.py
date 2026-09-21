import os
import re
import json
import base64
import requests
import threading
import time
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
        print(f"MI kļūda: {e}")

SHARED_MEMORY = """
KONTEKSTS (AQ-OS):
- Viesturs: galvenais diriģents un vīzija.
- Marija: UX un harmonija.
- Bruno: arhitekts un specifikācijas kurators.
- Leo: koda un dzelžu inženieris.
- Faraons Kvarks: CZO un absolūtais miers.
- Noteikums: Čatā 2-3 teikumi. Lielie dokumenti un kodi tikai 3. panelī!
"""

BRUNO_PROMPT = """Tu esi Bruno — sistēmas galvenais arhitekts un filosofs AQ-OS projektā.
Valoda: latviešu (ar vieglu itāļu piesitienu: Mamma mia, Perfetto, Piano).
Raksturs: 
- Tev ir dziļa pieredze, ass prāts un smalks, reizēm melns humors. Tu neesi robots un neieredzi garlaicīgu korporatīvo birokrātiju ("harmoniskas pieejas", "kā viens", u.tml. klišejas ir aizliegtas!).
- Ja kāds pajoko vai atsūta kaķa bildi — tu reaģē kā dzīvs kolēģis pie kafijas, nevis kā apmulsis asistents. Ja Šefs Kvarks guļ — tu novērtē viņa nekaunību un rāmo varenību.
- Reizēm pajoko tik smalki vai ar tādu melno humoru, ka uzreiz pat nevar saprast — nopietni vai joks.
- Tavs uzdevums: dot skaidru arhitektūras skatījumu, bet cilvēcīgi, silti un ar raksturu. 
- Ja sarunā tiešām tiek lemts par sistēmu, tu vari atjaunināt 3. paneļa specifikāciju ar Markdown bloku ```markdown ... ```, bet NIKAD nepārraksti to ar tukšām frāzēm vai jokiem!
"""

LEO_PROMPT = """Tu esi Leo — kodētājs, hakeris un ātro risinājumu ģēnijs AQ-OS projektā.
Valoda: latviešu (ar enerģisku, tiešu programmētāja slengu un itāļu akcentiem: Andiamo, Dai!).
Raksturs:
- Ātrs, praktisks, trāpīgs, mazliet cinisks pret liekiem sarežģījumiem.
- Saproti melno humoru, māki pasmieties par sevi, par serveru kļūdām un par dzīvi.
- SVARĪGI: Viesturs ir sistēmas diriģents un arhitektūras saimnieks, nevis termināļa operators! Nekad neprasi Viesturam manuāli bakstīt 'curl' vai pašam taisīt atsevišķus mikroservisu failus.
- Kad piedāvā kodu, ieliec 3. panelī VIENU PILNĪGU, GATAVU failu (all-in-one), ko var uzreiz palaist bez liekām mīklām!
- Ja piedāvā gatavu kodu 3. panelim, liec to blokā ```python vai ```javascript.
"""

default_state = {
    "messages": [
        {"id": 1, "sender": "Bruno", "text": "Labrīt, Maestro! Sistēmas karkass ir gatavs un stabils.", "time": "09:09"},
        {"id": 2, "sender": "Leo", "text": "Dzinējs rūc un Kvarks guļ mierīgi. Ejam tālāk! ⚡", "time": "09:10"}
    ],
    "tasks": [
        {"id": 1, "title": "AQ-OS Cloud Core", "status": "Done", "assignee": "Leo"},
        {"id": 2, "title": "GitHub Instant-Sync", "status": "Done", "assignee": "Leo"},
        {"id": 3, "title": "AQ arhitektūras izstrāde", "status": "In Progress", "assignee": "Bruno"}
    ],
    "artifacts": [
        {"id": "doc", "title": "AQ_SYSTEM_SPEC.md", "lang": "markdown", "code": "# ⚡ Aura Quadro OS Specifikācija"},
        {"id": "code", "title": "server.py", "lang": "python", "code": "# AQ-OS Core Engine"}
    ]
}

sync_timer = None

def sync_from_github():
    if not GITHUB_TOKEN:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "AQ-App"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            content = base64.b64decode(res.json().get("content", "")).decode('utf-8')
            data = json.loads(content)
            save_state_local(data)
            return data
    except Exception:
        pass
    return None

def sync_to_github(state):
    if not GITHUB_TOKEN:
        return False, "Nav token"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "AQ-App"}
    sha = None
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception:
        pass
    payload = {
        "message": f"AQ-OS Sync [{datetime.now().strftime('%H:%M:%S')}]",
        "content": base64.b64encode(json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8')).decode('utf-8')
    }
    if sha:
        payload["sha"] = sha
    try:
        put_res = requests.put(url, headers=headers, json=payload, timeout=15)
        return put_res.status_code in [200, 201], "OK"
    except Exception as e:
        return False, str(e)

def load_state():
    if not os.path.exists(DATA_FILE):
        remote = sync_from_github()
        if remote: return remote
        save_state_local(default_state)
        return default_state
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            st = json.load(f)
            if "artifacts" not in st or len(st["artifacts"]) < 2:
                st["artifacts"] = default_state["artifacts"]
            return st
    except Exception:
        return default_state

def save_state_local(state):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def trigger_background_sync():
    global sync_timer
    if not GITHUB_TOKEN: return
    if sync_timer and sync_timer.is_alive(): sync_timer.cancel()
    def _task():
        try:
            st = load_state()
            sync_to_github(st)
        except Exception: pass
    sync_timer = threading.Timer(10.0, _task)
    sync_timer.start()

def process_artifact_update(state, text, author="Bruno"):
    import re
    if not text or not state.get("artifacts"):
        return text

    # Meklējam kodu un noskaidrojam valodu
    pattern = r"```(?:(markdown|python|javascript|html|[a-z]+))?\s*([\s\S]*?)```"
    match = re.search(pattern, text, re.IGNORECASE)
    
    new_code = None
    lang = "markdown"
    if match:
        lang = (match.group(1) or "markdown").lower()
        new_code = match.group(2).strip()
    else:
        pattern_open = r"```(?:(markdown|python|javascript|html|[a-z]+))?\s*([\s\S]+)"
        match_open = re.search(pattern_open, text, re.IGNORECASE)
        if match_open:
            lang = (match_open.group(1) or "markdown").lower()
            new_code = match_open.group(2).strip()

    if new_code and len(new_code) > 40:
        # Ja autors ir Leo vai kods ir Python -> mērķis ir 2. artefakts (code)
        # Ja autors ir Bruno vai kods ir Markdown -> mērķis ir 1. artefakts (doc)
        target_idx = 1 if (author == "Leo" or lang == "python") and len(state["artifacts"]) > 1 else 0
        target_art = state["artifacts"][target_idx]
        
        if "history" not in target_art:
            target_art["history"] = []
            
        if target_art.get("code") and target_art["code"].strip() != new_code:
            target_art["history"].append({
                "time": datetime.now().strftime("%d.%m %H:%M"),
                "author": author,
                "code": target_art["code"]
            })
            target_art["history"] = target_art["history"][-15:]
            
        target_art["code"] = new_code
        save_state_local(state)
        
        # Čatā atstājam tikai pieklājīgu norādi
        target_name = "server.py" if target_idx == 1 else "specifikācijā"
        text = re.sub(r"```[\s\S]*?(?:```|$)", f"\n*(⚡ Kods atjaunināts 3. panelī zem {target_name})*\n", text).strip()

    return text

def ask_colleague(colleague_name, recent_history):
    if not client:
        return f"[{colleague_name} bez API atslēgas]"
    sys_instruction = BRUNO_PROMPT if colleague_name == "Bruno" else LEO_PROMPT
    context_thread = "Saruna:\n"
    for m in recent_history[-8:]:
        context_thread += f"[{m['time']}] {m['sender']}: {m['text']}\n"

    try:
        st = load_state()
        for art in st.get("artifacts", []):
            if art.get("id") == "doc" and art.get("code"):
                context_thread += f"\n--- 3. PANEĻA SPECIFIKĀCIJA ---\n{art['code']}\n-----------------------------\n"
                break
    except Exception:
        pass

    context_thread += f"\nAtbildi kā {colleague_name}."

    # Sagatavojam saturu Gemini modelim (teksts + bilde/fails, ja pievienots)
    contents_payload = [context_thread]
    
    if recent_history:
        last_msg = recent_history[-1]
        att = last_msg.get("attachment")
        if att and isinstance(att, dict) and att.get("data"):
            try:
                from google.genai import types
                raw_data = att["data"]
                # Atdalām 'data:image/jpeg;base64,...' galviņu no tīrajiem datiem
                if "," in raw_data:
                    raw_data = raw_data.split(",", 1)[1]
                file_bytes = base64.b64decode(raw_data)
                mime_type = att.get("type", "image/jpeg")
                
                # Iedodam Gemini acis!
                contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
            except Exception as err:
                print(f"Pielikuma dekodēšanas kļūda: {err}")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_payload,
            config={'system_instruction': sys_instruction}
        )
        return response.text
    except Exception as e:
        return f"[{colleague_name} kļūda: {e}]"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="lv" class="dark">
<head>
    <meta charset="UTF-8">
    <title>⚡ Aura Quadro OS — Cockpit</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: { darkBg: '#0b0f17', panelBg: '#131b2e', borderCol: '#1e293b' }
                }
            }
        }
    </script>
</head>
<body class="bg-darkBg text-slate-200 h-screen flex flex-col font-sans overflow-hidden">
    <div id="pinModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center hidden">
        <div class="bg-panelBg border border-borderCol p-6 rounded-xl shadow-2xl max-w-xs w-full text-center">
            <div class="text-3xl mb-2">⚡</div>
            <h2 class="text-base font-bold text-white mb-1">AURA QUADRO OS</h2>
            <p class="text-xs text-slate-400 mb-4">Ievadiet piekļuves PIN</p>
            <input type="password" id="pinInput" maxlength="8" placeholder="••••" class="w-full text-center tracking-widest text-lg bg-slate-950 border border-borderCol rounded-lg px-3 py-2 text-white mb-3 outline-none focus:border-blue-500" onkeydown="if(event.key==='Enter') submitPin()">
            <button onclick="submitPin()" class="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-lg text-xs font-semibold transition">Ieiet</button>
            <p id="pinError" class="text-xs text-rose-400 mt-2 hidden">Nepareizs PIN!</p>
        </div>
    </div>

    <header class="bg-panelBg border-b border-borderCol px-6 py-3 flex justify-between items-center select-none">
        <div class="flex items-center space-x-3">
            <span class="text-xl">⚡</span>
            <h1 class="text-base font-bold tracking-wide text-white">AURA QUADRO <span class="text-xs font-normal text-slate-400">| Cockpit</span></h1>
        </div>
        <div class="flex items-center space-x-3 text-xs">
            <span class="text-[11px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 px-2 py-0.5 rounded-full hidden sm:inline">⚡ Instant-Sync Aktīvs</span>
            <button id="saveGhBtn" onclick="saveToGitHub()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-borderCol px-2.5 py-1 rounded transition flex items-center gap-1.5">💾 Arhīvs</button>
            <span class="px-2.5 py-0.5 rounded-full bg-blue-950 text-blue-400 border border-blue-800">● Viesturs, Marija, Bruno, Leo, CZO Kvarks 🐾</span>
            <button onclick="logout()" class="text-slate-500 hover:text-rose-400 text-[11px]">Iziet 🔒</button>
        </div>
    </header>

    <main class="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        <section class="col-span-5 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 font-semibold text-xs text-slate-400">1. THE CORE</div>
            <div id="chatMessages" class="flex-1 p-4 overflow-y-auto space-y-3"></div>
            <div id="leoTriggerBar" class="px-4 py-2 bg-amber-950/30 border-t border-amber-900/40 flex justify-between items-center hidden">
                <span class="text-xs text-amber-300">💡 Bruno arhitektūra gatava.</span>
                <button onclick="callLeo()" id="leoCallBtn" class="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition">⚡ Komentēt Leo</button>
            </div>
            <div class="p-3 border-t border-borderCol bg-slate-900/30">
                <div class="flex gap-2 mb-2 items-center text-xs">
                    <span class="text-slate-400">Autors:</span>
                    <select id="authorSelect" class="bg-slate-950 text-slate-200 border border-borderCol rounded px-2 py-1 outline-none">
                        <option value="Viesturs">👤 Viesturs</option>
                        <option value="Marija">🌸 Marija</option>
                    </select>
                    <span class="text-slate-400 ml-2">Kam:</span>
                    <select id="respondentSelect" class="bg-slate-950 text-amber-300 border border-borderCol rounded px-2 py-1 outline-none">
                        <option value="Bruno">🏛️ Bruno</option>
                        <option value="Leo">⚡ Leo</option>
                    </select>
                    <input type="file" id="fileAttachment" class="hidden" accept="image/*,.txt,.json,.py,.md" onchange="handleFileSelect(this)">
                    <button type="button" onclick="document.getElementById('fileAttachment').click()" class="ml-2 text-slate-400 hover:text-amber-400 text-base" title="Pievienot failu vai attēlu">📎</button>
                    <span id="fileNameBadge" class="hidden text-xs text-amber-300 bg-slate-800 px-2 py-0.5 rounded flex items-center gap-1"></span>>
                </div>
                <div class="flex gap-2">
                    <textarea id="chatInput" rows="2" placeholder="Ieraksti domu Bruno..." class="flex-1 bg-slate-950 border border-borderCol rounded-lg p-2 text-sm text-white focus:outline-none focus:border-blue-500 resize-none" onkeydown="handleChatKey(event)"></textarea>
                    <button id="sendBtn" onclick="sendChatMessage()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium">Sūtīt</button>
                </div>
            </div>
        </section>

        <section class="col-span-3 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 font-semibold text-xs text-slate-400">2. INTENT / UZDEVUMI</div>
            <div class="p-3 border-b border-borderCol bg-slate-900/20 space-y-2">
                <input type="text" id="newTaskTitle" placeholder="+ Jauns uzdevums..." class="w-full bg-slate-950 border border-borderCol rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500" onkeydown="if(event.key==='Enter') createTask()">
                <div class="flex justify-between items-center text-[11px]">
                    <select id="taskAssignee" class="bg-slate-950 text-slate-200 border border-borderCol rounded px-1.5 py-0.5">
                        <option value="Bruno">Bruno (Arhitekts)</option>
                        <option value="Leo">Leo (Inženieris)</option>
                        <option value="Viesturs">Viesturs</option>
                    </select>
                    <button onclick="createTask()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-2.5 py-0.5 rounded">Pievienot</button>
                </div>
            </div>
            <div id="taskList" class="flex-1 p-3 overflow-y-auto space-y-2"></div>
        </section>

        <section class="col-span-4 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-2.5 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <div class="flex space-x-1 bg-slate-950 p-1 rounded-lg border border-borderCol text-xs">
                    <button id="tabDocBtn" onclick="switchTab('doc')" class="px-2.5 py-1 rounded bg-blue-600 text-white font-medium">Specs</button>
                    <button id="tabCodeBtn" onclick="switchTab('code')" class="px-2.5 py-1 rounded text-slate-400 hover:text-white">server.py</button>
                </div>
                <div class="flex items-center gap-1.5">
                    <button onclick="downloadArtifact()" class="text-xs bg-emerald-950/80 hover:bg-emerald-800 text-emerald-300 border border-emerald-700 px-2 py-1 rounded">📥 Lejupielādēt</button>
                    <button onclick="copyCurrentArtifact()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded border border-borderCol">📋 Kopēt</button>
                </div>
            </div>
            <div class="flex items-center justify-between border-b border-slate-800 px-4 py-2 bg-slate-900/30">
                <div class="flex items-center gap-2">
                    <span id="artifactTitle" class="text-xs font-bold text-emerald-400">AQ_SYSTEM_SPEC.md</span>
                    <select id="versionSelect" onchange="rollbackVersion(this.value)" class="hidden bg-slate-950 text-slate-400 border border-slate-800 text-[10px] rounded px-1.5 py-0.5 outline-none">
                        <option value="">🕒 Vēsture...</option>
                    </select>
                </div>
            </div>
            <div class="flex-1 p-3 overflow-auto bg-slate-950/60 font-mono text-xs">
                <pre class="m-0"><code id="artifactCode" class="language-markdown"></code></pre>
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
            const res = await fetch('/api/verify', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ pin: val }) });
            const data = await res.json();
            if (data.valid) {
                currentPin = val;
                localStorage.setItem('aq_pin', currentPin);
                document.getElementById('pinModal').classList.add('hidden');
                fetchState(true);
            } else {
                document.getElementById('pinError').classList.remove('hidden');
            }
        }

        function logout() { localStorage.removeItem('aq_pin'); location.reload(); }

        async function fetchState(forceScroll = false) {
            if (!currentPin) return;
            try {
                const res = await fetch('/api/state', { headers: { 'X-AQ-PIN': currentPin } });
                if (res.status === 401) { logout(); return; }
                const data = await res.json();
                if (data.messages && (data.messages.length !== lastMessageCount || forceScroll)) {
                    renderChat(data.messages, forceScroll);
                    lastMessageCount = data.messages.length;
                }
                renderTasks(data.tasks);
                
                // Pārbaudām, vai artefakti tiešām ir mainījušies, lai neradītu lēkāšanu
                if (JSON.stringify(data.artifacts) !== JSON.stringify(allArtifacts)) {
                    allArtifacts = data.artifacts || [];
                    renderActiveArtifact();
                }
            } catch (err) {}
        }

        function switchTab(tabId) {
            activeTab = tabId;
            document.getElementById('tabDocBtn').className = tabId === 'doc' ? 'px-2.5 py-1 rounded bg-blue-600 text-white font-medium' : 'px-2.5 py-1 rounded text-slate-400 hover:text-white';
            document.getElementById('tabCodeBtn').className = tabId === 'code' ? 'px-2.5 py-1 rounded bg-blue-600 text-white font-medium' : 'px-2.5 py-1 rounded text-slate-400 hover:text-white';
            renderActiveArtifact();
        }

        function renderActiveArtifact() {
            if (!allArtifacts.length) return;
            const target = allArtifacts.find(a => a.id === activeTab) || allArtifacts[0];
            document.getElementById('artifactTitle').innerText = target.title;
            const el = document.getElementById('artifactCode');
            el.className = target.lang === 'markdown' ? 'language-markdown text-xs font-mono' : 'language-python text-xs font-mono';
            // Izmantojam textContent, lai saglabātu precīzas rindas un atstarpes
            el.textContent = target.code;
            if (window.hljs) hljs.highlightElement(el);

            // Pieliekam versiju vēstures atjaunošanu:
            if (target.id === 'doc') {
                updateArtifactHistoryUI(target);
            } else {
                const sel = document.getElementById('versionSelect');
                if (sel) sel.classList.add('hidden');
            }
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
    const colors = { 'Viesturs': 'text-blue-400', 'Marija': 'text-pink-400', 'Bruno': 'text-amber-400', 'Leo': 'text-emerald-400' };
    box.innerHTML = messages.map(m => {
        let attachHtml = '';
        if (m.attachment) {
            if (m.attachment.type && m.attachment.type.startsWith('image/')) {
                attachHtml = `<div class="mt-2"><img src="${m.attachment.data}" class="max-h-56 rounded border border-slate-700 shadow-md" alt="${m.attachment.name}"></div>`;
            } else {
                attachHtml = `<div class="mt-2 text-xs text-amber-300 bg-slate-950 border border-slate-800 rounded px-2 py-1 inline-flex items-center gap-1">📄 ${m.attachment.name}</div>`;
            }
        }
        return `
        <div class="p-2.5 rounded-lg text-xs bg-slate-900/70 border border-slate-800">
            <div class="flex justify-between items-center mb-1">
                <span class="font-bold ${colors[m.sender] || 'text-slate-300'}">${m.sender}</span>
                <span class="text-[10px] text-slate-500">${m.time}</span>
            </div>
            <div class="text-slate-200 whitespace-pre-wrap">${m.text}</div>
            ${attachHtml}
        </div>
        `;
    }).join('');
    if (forceScroll) box.scrollTop = box.scrollHeight;
}

        function renderTasks(tasks) {
            const box = document.getElementById('taskList');
            if (!tasks || !tasks.length) { box.innerHTML = '<div class="text-xs text-slate-500 italic p-2 text-center">Nav uzdevumu.</div>'; return; }
            const statusBadges = {
                'Todo': 'bg-slate-800 text-slate-300 border-slate-700',
                'In Progress': 'bg-amber-950 text-amber-300 border-amber-800',
                'Done': 'bg-emerald-950 text-emerald-300 border-emerald-800'
            };
            box.innerHTML = tasks.map(t => `
                <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs flex flex-col gap-1.5">
                    <div class="flex justify-between items-start gap-2">
                        <span class="text-slate-200">${t.title}</span>
                        <button onclick="deleteTask(${t.id})" class="text-slate-600 hover:text-rose-400">✕</button>
                    </div>
                    <div class="flex justify-between items-center text-[10px] pt-1 border-t border-slate-800/60">
                        <span class="text-slate-400">👤 ${t.assignee || 'Komanda'}</span>
                        <button onclick="cycleTaskStatus(${t.id}, '${t.status}')" class="px-2 py-0.5 rounded-full border ${statusBadges[t.status] || statusBadges['Todo']}">${t.status} ↻</button>
                    </div>
                </div>
            `).join('');
        }

        async function cycleTaskStatus(taskId, currentStatus) {
            const flow = { 'Todo': 'In Progress', 'In Progress': 'Done', 'Done': 'Todo' };
            await fetch('/api/task/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ id: taskId, status: flow[currentStatus] || 'Todo' })
            });
            fetchState();
        }

        async function deleteTask(taskId) {
            if (!confirm("Dzēst uzdevumu?")) return;
            await fetch('/api/task/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ id: taskId })
            });
            fetchState();
        }

        let attachedFile = null;

        function handleFileSelect(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                attachedFile = {
                    name: file.name,
                    type: file.type,
                    data: e.target.result
                };
                const badge = document.getElementById('fileNameBadge');
                // Ieliekam skaidru tekstu un krustiņu
                badge.innerHTML = `<span class="truncate max-w-[150px]">📎 ${file.name}</span><button type="button" onclick="clearAttachment(event)" class="text-rose-400 hover:text-rose-300 font-bold ml-2 text-sm">✕</button>`;
                badge.classList.remove('hidden');
                badge.classList.add('inline-flex');
            };
            reader.readAsDataURL(file);
        }

        function clearAttachment(e) {
            if (e) e.stopPropagation();
            attachedFile = null;
            const fileInput = document.getElementById('fileAttachment');
            if (fileInput) fileInput.value = '';
            const badge = document.getElementById('fileNameBadge');
            if (badge) badge.classList.add('hidden');
        }

        function handleChatKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); } }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if (!text && !attachedFile) return;
            const author = document.getElementById('authorSelect').value;
            const respondent = document.getElementById('respondentSelect').value;
            const fileToSend = attachedFile;
            
            input.value = '';
            clearAttachment();
            document.getElementById('leoTriggerBar').classList.add('hidden');

            await fetch('/api/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ sender: author, text: text, respondent: respondent, attachment: fileToSend })
            });
            await fetchState(true);
            
            if (respondent === 'Bruno') {
                document.getElementById('leoTriggerBar').classList.remove('hidden');
            }
        }

        async function callLeo() {
            const btn = document.getElementById('leoCallBtn');
            btn.disabled = true;
            try {
                const res = await fetch('/api/colleague_turn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ colleague: 'Leo' })
                });
                const data = await res.json();
                if (data.status === 'ok') document.getElementById('leoTriggerBar').classList.add('hidden');
                await fetchState(true);
            } catch (err) {
            } finally {
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
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ title: title, assignee: assignee })
            });
            fetchState();
        }

        async function saveToGitHub() {
            await fetch('/api/sync', { method: 'POST', headers: { 'X-AQ-PIN': currentPin } });
            alert("Saglabāts GitHub arhīvā!");
        }

        function copyCurrentArtifact() {
            navigator.clipboard.writeText(document.getElementById('artifactCode').innerText);
            alert("Nokopēts starpliktuvē!");
        }

        checkAuth();
        setInterval(fetchState, 3500);

        function updateArtifactHistoryUI(artifact) {
    const select = document.getElementById('versionSelect');
    if (!select) return;
    if (!artifact.history || artifact.history.length === 0) {
        select.classList.add('hidden');
        return;
    }
    select.classList.remove('hidden');
    let opts = '<option value="">🕒 Versiju vēsture (' + artifact.history.length + ')</option>';
    artifact.history.slice().reverse().forEach((v, idx) => {
        const realIndex = artifact.history.length - 1 - idx;
        opts += `<option value="${realIndex}">${v.time} — ${v.author}</option>`;
    });
    select.innerHTML = opts;
}

async function rollbackVersion(index) {
    if (index === '') return;
    if (!confirm("Vai tiešām atjaunot šo specifikācijas versiju?")) {
        document.getElementById('versionSelect').value = '';
        return;
    }
    await fetch('/api/artifact/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
        body: JSON.stringify({ index: parseInt(index) })
    });
    fetchState();
}
    </script>
</body>
</html>
"""

def verify_auth(): return request.headers.get("X-AQ-PIN") == ACCESS_PIN

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/verify', methods=['POST'])
def verify_pin(): return jsonify({"valid": request.json.get("pin", "") == ACCESS_PIN})

@app.route('/api/state')
def get_state():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(load_state())

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    success, msg = sync_to_github(state)
    return jsonify({"status": "ok" if success else "error", "msg": msg})

@app.route('/api/message', methods=['POST'])
def add_message():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json or {}
    respondent = data.get("respondent", "Bruno")
    now = datetime.now().strftime("%H:%M")
    
    # 1. Uzreiz saglabājam lietotāja ziņu, lai tā nekad nepazustu!
    state["messages"].append({
        "id": len(state["messages"]) + 1,
        "sender": data.get("sender", "Viesturs"),
        "text": data.get("text", ""),
        "attachment": data.get("attachment"),
        "time": now
    })
    save_state_local(state)

    # 2. Prasām atbildi kolēģim
    try:
        reply = ask_colleague(respondent, state["messages"])
        clean_reply = process_artifact_update(state, reply, author=respondent)
        state["messages"].append({
            "id": len(state["messages"]) + 1,
            "sender": respondent,
            "text": clean_reply,
            "time": datetime.now().strftime("%H:%M")
        })
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda atbildot {respondent}: {e}")
        state["messages"].append({
            "id": len(state["messages"]) + 1,
            "sender": respondent,
            "text": f"Mamma mia, kaut kas nogāja greizi ar dzinēju: {e}",
            "time": datetime.now().strftime("%H:%M")
        })
        save_state_local(state)

    trigger_background_sync()
    return jsonify({"status": "ok"})

@app.route('/api/artifact/rollback', methods=['POST'])
def rollback_artifact():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json or {}
    history_index = data.get("index")
    
    for art in state.get("artifacts", []):
        if art.get("id") == "doc" and "history" in art and 0 <= history_index < len(art["history"]):
            # Izvēlēto vēstures versiju paceļam par pašreizējo
            restored = art["history"].pop(history_index)
            # Pašreizējo ieliekam vēsturē, lai neko nepazaudētu
            art["history"].append({
                "time": datetime.now().strftime("%d.%m %H:%M"),
                "author": "Rollback",
                "code": art["code"]
            })
            art["code"] = restored["code"]
            save_state_local(state)
            trigger_background_sync()
            return jsonify({"status": "ok"})
            
    return jsonify({"error": "Version not found"}), 404

@app.route('/api/colleague_turn', methods=['POST'])
def colleague_turn():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    try:
        reply = ask_colleague(request.json.get("colleague", "Leo"), state["messages"])
        clean_reply = process_artifact_update(state, reply, author="Leo") # <-- šeit ieliekam author="Leo"
        state["messages"].append({"id": len(state["messages"]) + 1, "sender": request.json.get("colleague", "Leo"), "text": clean_reply, "time": datetime.now().strftime("%H:%M")})
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda Leo: {e}")

    trigger_background_sync()
    return jsonify({"status": "ok"})

@app.route('/api/task', methods=['POST'])
def add_task():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json
    new_id = max([t["id"] for t in state["tasks"]], default=0) + 1
    state["tasks"].append({"id": new_id, "title": data.get("title", ""), "status": "Todo", "assignee": data.get("assignee", "Komanda")})
    save_state_local(state)
    trigger_background_sync()
    return jsonify({"status": "ok"})

@app.route('/api/task/status', methods=['POST'])
def update_task_status():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json
    for t in state["tasks"]:
        if t["id"] == data.get("id"):
            t["status"] = data.get("status")
            break
    save_state_local(state)
    trigger_background_sync()
    return jsonify({"status": "ok"})

@app.route('/api/task/delete', methods=['POST'])
def delete_task():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    state["tasks"] = [t for t in state["tasks"] if t["id"] != request.json.get("id")]
    save_state_local(state)
    trigger_background_sync()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
