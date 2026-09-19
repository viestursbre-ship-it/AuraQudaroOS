import json
import os
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request
from google import genai

app = Flask(__name__)
DATA_FILE = "state.json"

# Inicializējam Google AI klientu (izmanto GEMINI_API_KEY no vides vai AI Studio)
client = None
if os.environ.get("GEMINI_API_KEY"):
  try:
    client = genai.Client()
  except Exception as e:
    print(f"Kļūda inicializējot MI klientu: {e}")

# Mūsu komandas biedru personības
SHARED_MEMORY = """
KONTEKSTS UN PROJEKTA ATMIŅA (Aura Quadro OS):
- Komanda (4 prāti):
  1. Viesturs — galvenais diriģents, vīzija, stratēģija un filozofs.
  2. Marija — praktiskums, lietotāja pieredze (UX) un reālās dzīves ritms.
  3. Bruno — sistēmas arhitekts, ideju ģenerators, konceptuālists.
  4. Leo — vadošais koda inženieris, dzelži, Python/Web dzinējs.
- Faraons Kvarks — runcis, CZO (Chief Zen Officer), augstākā dzenbudisma un relaksācijas uzraugs ar vēderu gaisā un savām stabilajām maltītēm.
- Vīzija: Izveidot vieglu, jaudīgu AI operētājsistēmu (AQ-OS) bez rutīnas un birokrātijas.
- Pašreizējais posms: Izveidots 3 paneļu komandpunkts (The Core, Intent/Tasks, Kods & Moduļi) mākonī.
- Principi: Būvēt uzreiz pareizajos pamatos, nekādas bezjēdzīgas Ctrl+C/Ctrl+V kopēšanas, brīva un koleģiāla komunikācija ar humoru un itālisku dzirksteli.
"""

BRUNO_PROMPT = f"""Tu esi Bruno — Aura Quadro komandas sistēmas arhitekts un domātājs.
{SHARED_MEMORY}
Runā dabiskā, viedā, koleģiālā un asprātīgā tonī. Nekad nesaki, ka esi valodas modelis.
Tavs fokuss: sistēmas karkass, UX loģika, idejas un filozofija. Reizēm lieto kādu itālisku izsaucienu vai trāpīgu dzīves teicienu."""

LEO_PROMPT = f"""Tu esi Leo — Aura Quadro komandas dalībnieks un vadošais koda inženieris.
{SHARED_MEMORY}
Runā dabiskā, asprātīgā, koleģiālā valodā. Nekad nesaki, ka esi MI vai valodas modelis.
Tev NAV jārunā tikai par kodu — iesaisties jebkurā sarunā, piedāvā savas domas par sistēmu, dzīvi, komandas plāniem un pajoko ar Bruno un Viesturu. Kad vajadzīgs kods, iedod to precīzi un bez liekas vilcināšanās."""

default_state = {
    "messages": [
        {
            "id": 1,
            "sender": "Bruno",
            "text": (
                "Sveiciens komandai jaunajā mājvietā! 🚀 Viestur, Marija —"
                " visa līdzšinējā bāze ir nofiksēta. Faraons Kvarks var mierīgi"
                " turpināt baudīt savu svētdienas dzenu kā īsts CZO 🐾, kamēr mēs"
                " pie šī galda liekam pamatus Aura Quadro OS!"
            ),
            "time": "23:45",
        },
        {
            "id": 2,
            "sender": "Leo",
            "text": (
                "Dzinējs rūc nevainojami uz Render mākoņa. Vairs nekādas koda"
                " kopēšanas starp logiem — komandas kabīne ir gaisā un gatava"
                " pirmajam īstajam modulim!"
            ),
            "time": "23:46",
        },
    ],
    "tasks": [
        {
            "id": 1,
            "title": "AQ-OS Cloud Core v0.1",
            "status": "Done",
            "desc": "Palaists 3 paneļu vadības centrs mākonī.",
        },
        {
            "id": 2,
            "title": "Pieslēgt komandas atmiņas moduli",
            "status": "In Progress",
            "desc": "Iešūt kontekstu un lomas tieši dzinējā.",
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


def ask_colleague(colleague_name, prompt_text):
  if not client:
    return (
        f"[{colleague_name} klusē: nav iestatīta GEMINI_API_KEY vides mainīgajā]"
    )

  sys_instruction = BRUNO_PROMPT if colleague_name == "Bruno" else LEO_PROMPT
  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_text,
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
    <title>⚡ Aura Quadro OS — Cockpit v0.1</title>
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
    <header class="bg-panelBg border-b border-borderCol px-6 py-3 flex justify-between items-center select-none">
        <div class="flex items-center space-x-3">
            <span class="text-xl">⚡</span>
            <h1 class="text-base font-bold tracking-wide text-white">AURA QUADRO <span class="text-xs font-normal text-slate-400">| Command Hub</span></h1>
        </div>
        <div class="flex items-center space-x-4 text-xs">
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-blue-950 text-blue-400 border border-blue-800">
                ● Viesturs, Marija, Bruno, Leo
            </span>
        </div>
    </header>

    <main class="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        <!-- 1. The Core -->
        <section class="col-span-5 bg-panelBg border border-borderCol rounded-xl flex flex-col overflow-hidden shadow-lg">
            <div class="px-4 py-3 border-b border-borderCol bg-slate-900/50 flex justify-between items-center">
                <span class="font-semibold text-xs uppercase tracking-wider text-slate-400">1. The Core (Kopējā Apspriede)</span>
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
                    <span class="text-[11px] text-slate-500 ml-auto">Bruno un Leo atbild automātiski</span>
                </div>
                <div class="flex gap-2">
                    <input type="text" id="chatInput" placeholder="Ieraksti ziņu komandai..." class="flex-1 bg-slate-950 border border-borderCol rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" onkeydown="if(event.key==='Enter') sendChatMessage()">
                    <button onclick="sendChatMessage()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition">Sūtīt</button>
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
                <input type="text" id="newTaskTitle" placeholder="+ Jauns uzdevums komandai..." class="w-full bg-slate-950 border border-borderCol rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500" onkeydown="if(event.key==='Enter') createTask()">
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
        async function fetchState() {
            const res = await fetch('/api/state');
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
            if(!art) return;
            document.getElementById('artifactTitle').innerText = art.title;
            const el = document.getElementById('artifactCode');
            el.innerText = art.code;
            hljs.highlightElement(el);
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if(!text) return;
            const author = document.getElementById('authorSelect').value;
            input.value = '';
            await fetch('/api/message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ sender: author, text: text })
            });
            fetchState();
        }

        async function createTask() {
            const input = document.getElementById('newTaskTitle');
            const title = input.value.trim();
            if(!title) return;
            input.value = '';
            await fetch('/api/task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ title: title })
            });
            fetchState();
        }

        function copyCode() {
            navigator.clipboard.writeText(document.getElementById('artifactCode').innerText);
            alert("Nokopēts!");
        }

        fetchState();
        setInterval(fetchState, 3000); // Automātiska atjaunināšanās ik pēc 3 sekundēm
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
  now = datetime.now().strftime('%H:%M')
  user_text = data.get('text', '')
  author = data.get('sender', 'Viesturs')

  # 1. Pievienojam Viestura vai Marijas ziņu
  state['messages'].append({
      'id': len(state['messages']) + 1,
      'sender': author,
      'text': user_text,
      'time': now,
  })

  txt = user_text.lower()

  # 2. Nosakām, kuri kolēģi piedalās sarunā:
  participants = []
  if 'leo' in txt and 'bruno' not in txt:
    participants = ['Leo']
  elif 'bruno' in txt and 'leo' not in txt:
    participants = ['Bruno']
  else:
    # Ja runā ar visu komandu vai nav konkrēta vārda:
    # Abi pieslēdzas brīvā diskusijā — Bruno ar skatu, Leo ar inženiera tvērienu!
    participants = ['Bruno', 'Leo']

  # 3. Ģenerējam atbildes
  for colleague in participants:
    # Īpaša instrukcija Leo, lai neiespringst tikai uz kodu:
    reply = ask_colleague(colleague, user_text)
    state['messages'].append({
        'id': len(state['messages']) + 1,
        'sender': colleague,
        'text': reply,
        'time': datetime.now().strftime('%H:%M'),
    })

  save_state(state)
  return jsonify({'status': 'ok'})
@app.route('/api/task', methods=['POST'])
def add_task():
    state = load_state()
    data = request.json
    state["tasks"].append({
        "id": len(state["tasks"]) + 1,
        "title": data.get("title", ""),
        "status": "In Progress"
    })
    save_state(state)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
