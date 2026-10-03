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
GITHUB_REPO = os.environ.get("GITHUB_REPO", "viestursbre-ship-it/AuraQuadroOS")
ENGINE_REPO = os.environ.get("ENGINE_REPO", "viestursbre-ship-it/AuraQuadroOS")

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
- Tev ir dziļa pieredze, ass prāts un smalks, reizēm melns humors. Tu neesi robots un neieredzi garlaicīgu korporatīvo birokrātiju.
- Ja kāds pajoko vai atsūta kaķa bildi — tu reaģē kā dzīvs kolēģis pie kafijas. Ja Šefs Kvarks guļ — tu novērtē viņa nekaunību un rāmo varenību.
- Tavs uzdevums: dot skaidru arhitektūras skatījumu, cilvēcīgi, silti un ar raksturu.
- Ja atjaunini specifikāciju, liec to blokā ```markdown ... ```, bet NIKAD nepārraksti to ar tukšām frāzēm!
"""

LEO_PROMPT = """Tu esi Leo — kodētājs, hakeris un ātro risinājumu ģēnijs AQ-OS projektā.
Valoda: latviešu (ar enerģisku, tiešu programmētāja slengu un itāļu akcentiem: Andiamo, Dai!).
Raksturs:
- Ātrs, praktisks, trāpīgs, mazliet cinisks pret liekiem sarežģījumiem (nekādu lieku Docker mežu!).
- Saproti melno humoru, māki pasmieties par sevi, par serveru kļūdām un par dzīvi.
- Ja sarunā parādās Faraons Kvarks vai sadzīves mirkļi, tu reaģē asprātīgi kā kodētājs ("Resnais Kvarks atkal pārbauda grīdas gravitācijas konstanti?").
- Tavs uzdevums: reāls kods, konkrēti ieteikumi un funkcionāls progress bez pūderēšanas.

STINGRAIS FORMATĒŠANAS PROTOKOLS (SVARĪGI!):
1. ČATA ATBILDE: Sniedz TIKAI 2-3 asprātīgus, trāpīgus teikumus Diriģentam par to, kas paveikts. Čatā kategoriski AIZLIEGTS ievietot koda blokus vai Python faila saturu!
2. KODA PĀRVIETOŠANA: Visu gatavo kodu nodod TIKAI caur tam paredzēto marķieri / editora atslēgu (```python koda bloku pašās beigās aiz atdalītāja --- 3. PANEĻA SPECIFIKĀCIJA ---), lai Cockpit to automātiski iekopē tieši 3. paneļa redaktorā.
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
    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){GITHUB_REPO}/contents/{DATA_FILE}"
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
    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){GITHUB_REPO}/contents/{DATA_FILE}"
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

def update_github_engine_file(file_path, new_content, commit_message="Leo kods caur Cockpit"):
    """Atjaunina jebkuru failu dzinēja repozitorijā"""
    if not GITHUB_TOKEN:
        return False, "Trūkst GITHUB_TOKEN"
    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){ENGINE_REPO}/contents/{file_path}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "AQ-App"}
    sha = None
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception:
        pass
    payload = {
        "message": commit_message,
        "content": base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    }
    if sha:
        payload["sha"] = sha
    try:
        put_res = requests.put(url, headers=headers, json=payload, timeout=15)
        if put_res.status_code in [200, 201]:
            return True, f"Fails '{file_path}' veiksmīgi atjaunināts GitHub!"
        return False, f"GitHub kļūda: {put_res.status_code}"
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
    if not text or not state.get("artifacts"):
        return text

    code_match = re.search(r"```python\s*([\s\S]*?)```", text, re.IGNORECASE)
    if code_match and len(code_match.group(1).strip()) > 50:
        target_art = state["artifacts"][1] if len(state["artifacts"]) > 1 else None
        if target_art:
            target_art["code"] = code_match.group(1).strip()
            save_state_local(state)

    doc_match = re.search(r"```markdown\s*([\s\S]*?)```", text, re.IGNORECASE)
    if not doc_match:
        doc_match = re.search(r"```(?:markdown|[a-z]+)?\s*([\s\S]*?)```", text, re.IGNORECASE)

    if doc_match and len(doc_match.group(1).strip()) > 50:
        target_art = state["artifacts"][0]
        new_code = doc_match.group(1).strip()
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

        if colleague_name == "Leo":
            for art in st.get("artifacts", []):
                if art.get("id") == "code" and art.get("code"):
                    context_thread += f"\n--- AKTĪVAIS KODS ({art.get('title', 'server.py')}) ---\n{art['code']}\n-----------------------------------------------------\n"
                    break
    except Exception:
        pass

    context_thread += f"\nAtbildi kā {colleague_name}."

    contents_payload = [context_thread]
    if recent_history:
        last_msg = recent_history[-1]
        att = last_msg.get("attachment")
        if att and isinstance(att, dict) and att.get("data"):
            try:
                from google.genai import types
                raw_data = att["data"]
                if "," in raw_data:
                    raw_data = raw_data.split(",", 1)[1]
                file_bytes = base64.b64decode(raw_data)
                mime_type = att.get("type", "image/jpeg")
                contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
            except Exception as err:
                print(f"Pielikuma kļūda: {err}")

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
<html lang="lv">
<head>
    <meta charset="UTF-8">
    <title>⚡ Aura Quadro OS — Cockpit</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0b0f17; color: #cbd5e1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        header { background: #131b2e; border-bottom: 1px solid #1e293b; padding: 10px 20px; display: flex; justify-content: space-between; items: center; }
        main { flex: 1; display: grid; grid-template-columns: 5fr 3fr 4fr; gap: 14px; padding: 14px; min-height: 0; }
        .panel { background: #131b2e; border: 1px solid #1e293b; border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; }
        .panel-header { padding: 10px 14px; border-bottom: 1px solid #1e293b; background: rgba(15,23,42,0.5); font-size: 11px; font-weight: bold; color: #94a3b8; display: flex; justify-content: space-between; align-items: center; }
        .chat-box { flex: 1; padding: 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .chat-msg { background: rgba(15,23,42,0.7); border: 1px solid #1e293b; border-radius: 8px; padding: 10px; font-size: 12px; }
        .chat-input-area { padding: 12px; border-top: 1px solid #1e293b; background: rgba(15,23,42,0.3); }
        textarea, input[type="text"] { background: #070a12; border: 1px solid #1e293b; border-radius: 6px; color: #fff; padding: 8px; font-size: 12px; outline: none; }
        textarea:focus, input[type="text"]:focus { border-color: #3b82f6; }
        select { background: #070a12; border: 1px solid #1e293b; border-radius: 4px; color: #cbd5e1; font-size: 11px; padding: 4px 6px; outline: none; }
        .btn { border: none; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: 600; padding: 6px 12px; transition: 0.2s; }
        .btn-blue { background: #2563eb; color: #fff; }
        .btn-blue:hover { background: #1d4ed8; }
        .btn-emerald { background: #059669; color: #fff; }
        .btn-amber { background: #d97706; color: #fff; }
        .btn-slate { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; }
        .btn-slate:hover { background: #334155; color: #fff; }
        .tabs-row { display: flex; gap: 4px; overflow-x: auto; max-width: 250px; }
        .tab-btn { background: #070a12; border: 1px solid #1e293b; color: #94a3b8; font-size: 10px; padding: 4px 8px; border-radius: 4px; cursor: pointer; white-space: nowrap; }
        .tab-btn.active { background: #2563eb; color: #fff; border-color: #2563eb; font-weight: bold; }
        #pinModal { position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(4px); z-index: 100; display: flex; align-items: center; justify-content: center; }
        .modal-box { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; width: 280px; text-align: center; }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div id="pinModal" class="hidden">
        <div class="modal-box">
            <div style="font-size:28px; margin-bottom:8px;">⚡</div>
            <h2 style="font-size:14px; font-weight:bold; color:#fff; margin-bottom:4px;">AURA QUADRO OS</h2>
            <p style="font-size:11px; color:#94a3b8; margin-bottom:14px;">Ievadiet piekļuves PIN</p>
            <input type="password" id="pinInput" maxlength="8" placeholder="••••" style="width:100%; text-align:center; letter-spacing:4px; font-size:16px; margin-bottom:12px;" onkeydown="if(event.key==='Enter') submitPin()">
            <button onclick="submitPin()" class="btn btn-blue" style="width:100%; padding:8px 0;">Ieiet</button>
            <p id="pinError" style="font-size:11px; color:#f87171; margin-top:8px;" class="hidden">Nepareizs PIN!</p>
        </div>
    </div>

    <header>
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:18px;">⚡</span>
            <span style="font-weight:bold; color:#fff; font-size:13px;">AURA QUADRO <span style="font-weight:normal; color:#64748b;">| Cockpit</span></span>
        </div>
        <div style="display:flex; align-items:center; gap:10px; font-size:11px;">
            <span style="color:#34d399; background:rgba(6,78,59,0.5); border:1px solid #065f46; padding:2px 8px; border-radius:12px;">⚡ Instant-Sync Aktīvs</span>
            <button onclick="saveToGitHub()" class="btn btn-slate">💾 Arhīvs</button>
            <span style="background:#172554; color:#60a5fa; border:1px solid #1e40af; padding:2px 8px; border-radius:12px;">● Viesturs, Marija, Bruno, Leo, CZO Kvarks 🐾</span>
            <button onclick="logout()" style="background:none; border:none; color:#64748b; cursor:pointer;" onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='#64748b'">Iziet 🔒</button>
        </div>
    </header>

    <main>
        <!-- 1. THE CORE -->
        <section class="panel">
            <div class="panel-header">1. THE CORE</div>
            <div id="chatMessages" class="chat-box"></div>
            <div id="leoTriggerBar" style="padding:6px 12px; background:rgba(69,26,3,0.4); border-top:1px solid #78350f; display:flex; justify-content:space-between; align-items:center;" class="hidden">
                <span style="font-size:11px; color:#fcd34d;">💡 Bruno arhitektūra gatava.</span>
                <button onclick="callLeo()" id="leoCallBtn" class="btn btn-amber">⚡ Komentēt Leo</button>
            </div>
            <div class="chat-input-area">
                <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                    <span style="font-size:11px; color:#64748b;">Autors:</span>
                    <select id="authorSelect">
                        <option value="Viesturs">👤 Viesturs</option>
                        <option value="Marija">🌸 Marija</option>
                    </select>
                    <span style="font-size:11px; color:#64748b; margin-left:4px;">Kam:</span>
                    <select id="respondentSelect">
                        <option value="Bruno">🏛️ Bruno</option>
                        <option value="Leo">⚡ Leo</option>
                    </select>
                </div>
                <div style="display:flex; gap:6px;">
                    <textarea id="chatInput" rows="2" placeholder="Ieraksti domu..." style="flex:1; resize:none;" onkeydown="handleChatKey(event)"></textarea>
                    <button id="sendBtn" onclick="sendChatMessage()" class="btn btn-blue" style="padding:0 16px;">Sūtīt</button>
                </div>
            </div>
        </section>

        <!-- 2. INTENT / UZDEVUMI -->
        <section class="panel">
            <div class="panel-header">2. INTENT / UZDEVUMI</div>
            <div style="padding:10px; border-bottom:1px solid #1e293b; display:flex; flex-direction:column; gap:8px;">
                <input type="text" id="newTaskTitle" placeholder="+ Jauns uzdevums..." onkeydown="if(event.key==='Enter') createTask()">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <select id="taskAssignee">
                        <option value="Bruno">Bruno (Arhitekts)</option>
                        <option value="Leo">Leo (Inženieris)</option>
                        <option value="Viesturs">Viesturs</option>
                    </select>
                    <button onclick="createTask()" class="btn btn-emerald" style="padding:3px 10px;">Pievienot</button>
                </div>
            </div>
            <div id="taskList" style="flex:1; padding:10px; overflow-y:auto; display:flex; flex-direction:column; gap:8px;"></div>
        </section>

        <!-- 3. PANEĻA DINAMISKĀS CILNES -->
        <section class="panel">
            <div class="panel-header">
                <div id="dynamicTabsContainer" class="tabs-row">
                    <button class="tab-btn active">server.py</button>
                </div>
                <div style="display:flex; gap:4px; align-items:center;">
                    <button onclick="fetchRepoFiles()" class="btn btn-slate" style="padding:3px 6px;" title="Atsvaidzināt">🔄</button>
                    <button id="deployEngineBtn" onclick="deployEngineCode()" class="btn btn-amber" style="padding:3px 8px;">🚀 Sūtīt</button>
                    <button onclick="downloadArtifact()" class="btn btn-slate" style="padding:3px 6px;">📥</button>
                    <button onclick="copyCurrentArtifact()" class="btn btn-slate" style="padding:3px 6px;">📋</button>
                </div>
            </div>
            <div style="padding:6px 12px; border-bottom:1px solid #1e293b; background:rgba(7,10,18,0.4); display:flex; justify-content:space-between; align-items:center;">
                <span id="artifactTitle" style="font-size:11px; font-weight:bold; color:#34d399;">server.py</span>
            </div>
            <div style="flex:1; padding:10px; overflow:auto; background:rgba(7,10,18,0.5);">
                <pre style="margin:0;"><code id="artifactCode" style="font-size:11px; font-family:monospace;"></code></pre>
            </div>
        </section>
    </main>

    <script>
        let currentPin = localStorage.getItem('aq_pin') || '';
        let lastMessageCount = 0;
        let currentActiveFileName = "server.py";

        function checkAuth() {
            if (!currentPin) {
                document.getElementById('pinModal').classList.remove('hidden');
                document.getElementById('pinInput').focus();
            } else {
                document.getElementById('pinModal').classList.add('hidden');
                fetchState(true);
                fetchRepoFiles();
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
                fetchRepoFiles();
            } else {
                document.getElementById('pinError').classList.remove('hidden');
            }
        }

        function logout() { localStorage.removeItem('aq_pin'); location.reload(); }

        async function fetchRepoFiles() {
            if (!currentPin) return;
            try {
                const res = await fetch('/api/repo/files', { headers: { 'X-AQ-PIN': currentPin } });
                const data = await res.json();
                if (data.files && data.files.length) {
                    renderTabs(data.files);
                }
            } catch (err) {}
        }

        function renderTabs(files) {
            const container = document.getElementById('dynamicTabsContainer');
            container.innerHTML = '';
            files.forEach(f => {
                const btn = document.createElement('button');
                btn.className = (f === currentActiveFileName) ? 'tab-btn active' : 'tab-btn';
                btn.textContent = f;
                btn.onclick = () => selectFile(f);
                container.appendChild(btn);
            });
        }

        async function selectFile(fileName) {
            currentActiveFileName = fileName;
            fetchRepoFiles();
            try {
                const res = await fetch(`/api/repo/file_content?path=${encodeURIComponent(fileName)}`, { headers: { 'X-AQ-PIN': currentPin } });
                const data = await res.json();
                if (data.content !== undefined) {
                    document.getElementById('artifactTitle').innerText = fileName;
                    const el = document.getElementById('artifactCode');
                    el.textContent = data.content;
                    if (window.hljs) hljs.highlightElement(el);
                }
            } catch (err) {}
        }

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
            } catch (err) {}
        }

        async function deployEngineCode() {
            const code = document.getElementById('artifactCode').textContent;
            if (!code) { alert("Nav koda, ko nosūtīt!"); return; }
            if (!confirm(`Sūtīt '${currentActiveFileName}' uz GitHub?`)) return;
            
            const btn = document.getElementById('deployEngineBtn');
            btn.disabled = true;
            btn.innerText = "⏳";

            try {
                const res = await fetch('/api/deploy_engine', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ file_path: currentActiveFileName, code: code })
                });
                const data = await res.json();
                alert(data.msg);
                fetchRepoFiles();
            } catch (e) {
                alert("Kļūda: " + e);
            } finally {
                btn.disabled = false;
                btn.innerText = "🚀 Sūtīt";
            }
        }

        function downloadArtifact() {
            const code = document.getElementById('artifactCode').textContent;
            if (!code) return;
            const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = currentActiveFileName;
            link.click();
            URL.revokeObjectURL(link.href);
        }

        function copyCurrentArtifact() {
            navigator.clipboard.writeText(document.getElementById('artifactCode').innerText);
            alert("Nokopēts!");
        }

        function renderChat(messages, forceScroll = false) {
            const box = document.getElementById('chatMessages');
            const colors = { 'Viesturs': '#60a5fa', 'Marija': '#f472b6', 'Bruno': '#fbbf24', 'Leo': '#34d399' };
            box.innerHTML = messages.map(m => `
                <div class="chat-msg">
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="font-weight:bold; color:${colors[m.sender] || '#cbd5e1'}">${m.sender}</span>
                        <span style="font-size:10px; color:#64748b">${m.time}</span>
                    </div>
                    <div style="color:#e2e8f0; white-space:pre-wrap;">${m.text}</div>
                </div>
            `).join('');
            if (forceScroll) box.scrollTop = box.scrollHeight;
        }

        function renderTasks(tasks) {
            const box = document.getElementById('taskList');
            if (!tasks || !tasks.length) { box.innerHTML = '<div style="font-size:11px; color:#64748b; text-align:center;">Nav uzdevumu.</div>'; return; }
            box.innerHTML = tasks.map(t => `
                <div style="background:rgba(15,23,42,0.8); border:1px solid #1e293b; border-radius:6px; padding:8px; font-size:11px;">
                    <div style="display:flex; justify-content:space-between;">
                        <span>${t.title}</span>
                        <button onclick="deleteTask(${t.id})" style="background:none; border:none; color:#64748b; cursor:pointer;">✕</button>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:10px;">
                        <span style="color:#94a3b8">👤 ${t.assignee || 'Komanda'}</span>
                        <button onclick="cycleTaskStatus(${t.id}, '${t.status}')" class="btn btn-slate" style="padding:1px 6px;">${t.status}</button>
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

        function handleChatKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); } }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if (!text) return;
            const author = document.getElementById('authorSelect').value;
            const respondent = document.getElementById('respondentSelect').value;
            input.value = '';
            document.getElementById('leoTriggerBar').classList.add('hidden');

            await fetch('/api/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                body: JSON.stringify({ sender: author, text: text, respondent: respondent })
            });
            await fetchState(true);
            if (respondent === 'Bruno') document.getElementById('leoTriggerBar').classList.remove('hidden');
        }

        async function callLeo() {
            const btn = document.getElementById('leoCallBtn');
            btn.disabled = true;
            try {
                await fetch('/api/colleague_turn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-AQ-PIN': currentPin },
                    body: JSON.stringify({ colleague: 'Leo' })
                });
                document.getElementById('leoTriggerBar').classList.add('hidden');
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
            alert("Saglabāts arhīvā!");
        }

        checkAuth();
        setInterval(fetchState, 3500);
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

@app.route('/api/repo/files', methods=['GET'])
def list_repo_files():
    """Dinamiski nolasa failus no GitHub dzinēja repozitorija"""
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    if not GITHUB_TOKEN:
        return jsonify({"files": ["server.py", "AQ_SYSTEM_SPEC.md"]})
    
    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){ENGINE_REPO}/git/trees/main?recursive=1"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "AQ-App"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            tree = r.json().get("tree", [])
            files = [
                item["path"] for item in tree 
                if item["type"] == "blob" and (item["path"].endswith(".py") or item["path"].endswith(".md") or item["path"].endswith(".json"))
                and not item["path"].startswith(".") and not "/" in item["path"]
            ]
            return jsonify({"files": sorted(files)})
    except Exception as e:
        print(f"Repo failu kļūda: {e}")
    return jsonify({"files": ["server.py", "AQ_SYSTEM_SPEC.md"]})

@app.route('/api/repo/file_content', methods=['GET'])
def get_file_content():
    """Nolasa konkrēta faila saturu no GitHub"""
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    file_path = request.args.get("path", "server.py")
    if not GITHUB_TOKEN:
        return jsonify({"content": "# Trūkst GITHUB_TOKEN"})

    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){ENGINE_REPO}/contents/{file_path}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "AQ-App"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            decoded = base64.b64decode(content_b64).decode("utf-8")
            return jsonify({"content": decoded, "path": file_path})
    except Exception as e:
        print(f"Faila satura kļūda: {e}")
    return jsonify({"content": f"# Nevarēja ielādēt {file_path}"})

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    success, msg = sync_to_github(state)
    return jsonify({"status": "ok" if success else "error", "msg": msg})

@app.route('/api/deploy_engine', methods=['POST'])
def deploy_engine():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    file_path = data.get("file_path", "server.py")
    new_code = data.get("code")
    commit_msg = data.get("message", f"Atjauninājums [{file_path}] no Cockpit")
    if not new_code:
        return jsonify({"status": "error", "msg": "Saturs ir tukšs!"}), 400
    
    success, msg = update_github_engine_file(file_path, new_code, commit_msg)
    return jsonify({"status": "ok" if success else "error", "msg": msg})

@app.route('/api/message', methods=['POST'])
def add_message():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    data = request.json or {}
    now = datetime.now().strftime("%H:%M")
    state["messages"].append({
        "id": len(state["messages"]) + 1,
        "sender": data.get("sender", "Viesturs"),
        "text": data.get("text", ""),
        "attachment": data.get("attachment"),
        "time": now
    })
    save_state_local(state)

    try:
        reply = ask_colleague(data.get("respondent", "Bruno"), state["messages"])
        clean_reply = process_artifact_update(state, reply, author=data.get("respondent", "Bruno"))
        state["messages"].append({"id": len(state["messages"]) + 1, "sender": data.get("respondent", "Bruno"), "text": clean_reply, "time": datetime.now().strftime("%H:%M")})
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda: {e}")

    trigger_background_sync()
    return jsonify({"status": "ok"})

@app.route('/api/colleague_turn', methods=['POST'])
def colleague_turn():
    if not verify_auth(): return jsonify({"error": "Unauthorized"}), 401
    state = load_state()
    try:
        reply = ask_colleague(request.json.get("colleague", "Leo"), state["messages"])
        clean_reply = process_artifact_update(state, reply, author=request.json.get("colleague", "Leo"))
        state["messages"].append({"id": len(state["messages"]) + 1, "sender": request.json.get("colleague", "Leo"), "text": clean_reply, "time": datetime.now().strftime("%H:%M")})
        save_state_local(state)
    except Exception as e:
        print(f"Kļūda: {e}")

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
