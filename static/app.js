marked.setOptions({ breaks: true, gfm: true });
let supabaseClient = null; let userId = null; let userEmail = null; let isSending = false; let selectedFile = null; let lastQuestion = ""; let controller = null; let currentChatId = null;

fetch('/config?v=43').then(res => {
    if(!res.ok) throw new Error('Config 500')
    return res.json()
}).then(config => {
    console.log("CONFIG LOADED", config.supabase_url)
    supabaseClient = supabase.createClient(config.supabase_url, config.supabase_key)
    checkAuth();
}).catch(err => {
    console.error("Config Error:", err)
    document.getElementById('authError').innerText = "Server Error: Refresh page"
});

async function checkAuth() { 
    if(!supabaseClient) return;
    const { data: { session }, error } = await supabaseClient.auth.getSession();
    if(error) console.error("SESSION ERROR:", error);
    if(session) { 
        userId = session.user.id; 
        userEmail = session.user.email; 
        showApp(); 
        loadSidebar(); 
    } else {
        document.getElementById('sidebar').style.display = 'none';
        console.log("No session found");
    }
}

document.getElementById('signupBtn').addEventListener('click', signUp);
document.getElementById('loginBtn').addEventListener('click', signIn);
document.getElementById('logoutBtn').addEventListener('click', logout);
document.getElementById('uploadBtn').addEventListener('click', () => document.getElementById('fileInput').click());
document.getElementById('newChatBtn').addEventListener('click', newChat);
document.getElementById('hamburgerBtn').addEventListener('click', toggleSidebar);
document.getElementById('closeSidebarBtn').addEventListener('click', toggleSidebar);

async function signUp() { 
    const email=document.getElementById('email').value; 
    const password=document.getElementById('password').value; 
    document.getElementById('authError').innerText = "Creating account...";
    const {error}=await supabaseClient.auth.signUp({email,password}); 
    if(error) document.getElementById('authError').innerText=error.message; 
    else {document.getElementById('authError').style.color = '#22c55e'; document.getElementById('authError').innerText='Check email to confirm';} 
}

async function signIn() { 
    const email=document.getElementById('email').value; 
    const password=document.getElementById('password').value; 
    document.getElementById('authError').innerText = "Logging in...";
    loginBtn.disabled = true;
    const {data, error}=await supabaseClient.auth.signInWithPassword({email,password});
    loginBtn.disabled = false;
    if(error) {
        document.getElementById('authError').innerText=error.message; 
        console.error("LOGIN ERROR:", error);
    } else { 
        document.getElementById('authError').innerText = "";
        userId = data.user.id; 
        userEmail = data.user.email; 
        showApp(); 
        loadSidebar(); 
    } 
}

async function logout() { await supabaseClient.auth.signOut(); location.reload(); }

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('show'); }

async function loadSidebar() {
    const res = await fetch(`/chats?user_id=${userId}`);
    const chats = await res.json();
    const list = document.getElementById('chatList');
    list.innerHTML = '';
    chats.forEach(chat => {
        const div = document.createElement('div');
        div.className = 'chat-item';
        if(chat.id === currentChatId) div.classList.add('active');
        div.innerHTML = `<span onclick="loadChat('${chat.id}')">${chat.title}</span><span class="chat-delete" onclick="deleteChat('${chat.id}')">✕</span>`;
        list.appendChild(div);
    });
}

async function newChat() {
    currentChatId = null;
    document.getElementById('chatBox').innerHTML = '';
    showWelcome();
    toggleSidebar();
    loadSidebar();
}

async function loadChat(chatId) {
    currentChatId = chatId;
    const res = await fetch(`/chat/${chatId}`);
    const messages = await res.json();
    document.getElementById('chatBox').innerHTML = '';
    messages.forEach(m => addMessage(m.role, m.content));
    toggleSidebar();
    loadSidebar();
}

async function deleteChat(chatId) {
    if(!confirm('Delete this chat?')) return;
    await fetch('/chat/delete', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({chat_id: chatId}) });
    if(currentChatId === chatId) newChat();
    loadSidebar();
}

// FIX 1: Don't break ### headers or markdown
function antiSmash(text) {
    if(!text) return '';
    // Only fix joined words, don't touch markdown
    text = text.replace(/([a-z])([A-Z])/g, '$1 $2');
    text = text.replace(/([a-z])(\d)/g, '$1 $2');
    text = text.replace(/(\d)([a-zA-Z])/g, '$1 $2');
    text = text.replace(/([a-z]),([a-zA-Z])/g, '$1, $2');
    text = text.replace(/([a-z])\.([A-Z])/g, '$1. $2');
    text = text.replace(/([a-z]):([A-Z])/g, '$1: $2');
    text = text.replace(/\s{2,}/g, ' ); // collapse multiple spaces only
    return text.trim();
}

function renderAI(text) { return marked.parse(antiSmash(text)); }

function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'message ' + (role === 'user'? 'user-msg' : 'ai-msg');
    if(role === 'ai') {
        div.innerHTML = `<button class="copy-btn" onclick="copyText(this)">Copy</button>` + renderAI(text);
    } else {
        div.textContent = text;
    }
    document.getElementById('chatBox').appendChild(div);
    document.getElementById('chatBox').scrollTop = document.getElementById('chatBox').scrollHeight;
    return div;
}

function copyText(btn) {
    const text = btn.parentElement.innerText.replace('Copy', '');
    navigator.clipboard.writeText(text);
    btn.innerText = 'Copied!';
    setTimeout(() => btn.innerText = 'Copy', 2000);
}

// FIX 2: Meta AI style welcome
function showWelcome() {
    addMessage('ai', `### Hey! Welcome to Brain 3.0 😊
I'm your AI engineer built by **B.CORP**.

### Here's what I can do
- **Build**: Apps, websites, and automation
- **Decide**: Give you direct, no-fluff answers
- **Explain**: Break down complex topics into simple steps

What should we build today?`);
}

function showApp() {
    document.getElementById('authScreen').style.display = 'none';
    document.getElementById('appContainer').style.display = 'flex';
    document.getElementById('sidebar').style.display = 'block';
    document.getElementById('userEmail').innerText = userEmail;
    if(!currentChatId) showWelcome();
}

document.getElementById('fileInput').addEventListener('change', (e)=>{ selectedFile = e.target.files[0]; });
document.getElementById('stopBtn').addEventListener('click', () => { if(controller) controller.abort(); });
document.getElementById('regenBtn').addEventListener('click', () => { if(lastQuestion) sendMessage(lastQuestion, true); });
document.getElementById('sendBtn').addEventListener('click', () => sendMessage());
document.getElementById('userInput').addEventListener('keypress', (e) => { if(e.key === 'Enter') sendMessage(); });

// FIX 3: Better streaming to prevent joined words
async function sendMessage(questionOverride = null, isRegen = false) {
    let aiMsgDiv;
    try {
        if(isSending) return;
        const input = document.getElementById('userInput');
        const question = questionOverride || input.value.trim();
        if(!question &&!selectedFile) return;

        if(!isRegen) currentChatId = null;

        lastQuestion = question;
        isSending = true;
        document.getElementById('sendBtn').disabled = true;
        document.getElementById('stopBtn').style.display = 'block';

        if(!isRegen) addMessage('user', question);
        input.value = '';

        aiMsgDiv = addMessage('ai', '');
        aiMsgDiv.classList.add('typing');

        const formData = new FormData();
        formData.append('question', question);
        formData.append('user_id', userId);
        if(currentChatId) formData.append('chat_id', currentChatId);
        if(selectedFile) formData.append('file', selectedFile);

        controller = new AbortController();
        const res = await fetch('/ask', { method: 'POST', body: formData, signal: controller.signal });
        if(!res.ok) throw new Error('Server Error: ' + res.status);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        while(true) {
            const {value, done} = await reader.read();
            if(done) break;
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for(const line of lines) {
                if(line.startsWith('data: ')) {
                    const data = line.substring(6);
                    if(data.startsWith('[CHAT_ID]')) {
                        currentChatId = data.replace('[CHAT_ID]','').replace('[/CHAT_ID]','');
                        loadSidebar();
                    }
                    else if(data === '[DONE]') break;
                    else {
                        fullText += data + ' '; // ADDED SPACE to prevent joining
                        aiMsgDiv.innerHTML = `<button class="copy-btn" onclick="copyText(this)">Copy</button>` + renderAI(fullText);
                        document.getElementById('chatBox').scrollTop = document.getElementById('chatBox').scrollHeight;
                    }
                }
            }
        }
        aiMsgDiv.classList.remove('typing');
        aiMsgDiv.innerHTML = `<button class="copy-btn" onclick="copyText(this)">Copy</button>` + renderAI(fullText.trim());
        document.getElementById('regenBtn').style.display = 'block';
        if(window.innerWidth < 768) toggleSidebar();

    } catch(err) {
        console.error("SEND ERROR:", err);
        if(aiMsgDiv) {
            aiMsgDiv.classList.remove('typing');
            aiMsgDiv.innerHTML = `<button class="copy-btn" onclick="copyText(this)">Copy</button>Error: ${err.message}`;
        }
    } finally {
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('stopBtn').style.display = 'none';
        isSending = false;
        selectedFile = null;
        document.getElementById('fileInput').value = '';
    }
  } 
