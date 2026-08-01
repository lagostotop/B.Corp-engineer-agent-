marked.setOptions({ breaks: true, gfm: true });
let supabaseClient = null;
let userId = "guest"; // GUEST MODE - NO LOGIN
let userEmail = "Guest User";
let isSending = false;
let selectedFile = null;
let lastQuestion = "";
let controller = null;
let currentChatId = null;

// v45.3 - GUEST MODE - NO AUTH
fetch('/api/config?v=45').then(res => {
    if(!res.ok) throw new Error('Config 500')
    return res.json()
}).then(config => {
    console.log("CONFIG LOADED", config.supabase_url)
    supabaseClient = supabase.createClient(config.supabase_url, config.supabase_anon_key)
    // SKIP AUTH CHECK - GO STRAIGHT TO APP
    showApp();
    loadSidebar();
}).catch(err => {
    console.error("Config Error:", err)
    // still show app even if config fails
    showApp();
    loadSidebar();
});

document.addEventListener('DOMContentLoaded', () => {
    // HIDE AUTH BUTTONS - THEY DO NOTHING NOW
    if(document.getElementById('signupBtn')) document.getElementById('signupBtn').style.display = 'none';
    if(document.getElementById('loginBtn')) document.getElementById('loginBtn').style.display = 'none';
    if(document.getElementById('logoutBtn')) document.getElementById('logoutBtn').style.display = 'none';

    document.getElementById('uploadBtn').addEventListener('click', () => document.getElementById('fileInput').click());
    document.getElementById('newChatBtn').addEventListener('click', newChat);
    document.getElementById('hamburgerBtn').addEventListener('click', toggleSidebar);
    document.getElementById('closeSidebarBtn').addEventListener('click', toggleSidebar);
    document.getElementById('fileInput').addEventListener('change', (e)=>{
        selectedFile = e.target.files[0];
        if(selectedFile) document.getElementById('uploadBtn').innerText = '📎1';
    });
    document.getElementById('stopBtn').addEventListener('click', () => { if(controller) controller.abort(); });
    document.getElementById('regenBtn').addEventListener('click', () => { if(lastQuestion) sendMessage(lastQuestion, true); });
    document.getElementById('sendBtn').addEventListener('click', () => sendMessage());
    document.getElementById('userInput').addEventListener('keypress', (e) => { if(e.key === 'Enter') sendMessage(); });
});

// REMOVED: signUp, signIn, checkAuth, logout - not needed for guest

async function loadSidebar() {
    const res = await fetch(`/api/chats?user_id=${userId}`);
    if(!res.ok) return;
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
    if(window.innerWidth < 768) toggleSidebar();
    loadSidebar();
}

async function loadChat(chatId) {
    currentChatId = chatId;
    const res = await fetch(`/api/chat/${chatId}`);
    if(!res.ok) return;
    const messages = await res.json();
    document.getElementById('chatBox').innerHTML = '';
    messages.forEach(m => addMessage(m.role, m.content, m.created_at));
    if(window.innerWidth < 768) toggleSidebar();
    loadSidebar();
}

async function deleteChat(chatId) {
    if(!confirm('Delete this chat?')) return;
    await fetch('/api/chat/delete', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({chat_id: chatId}) });
    if(currentChatId === chatId) newChat();
    loadSidebar();
}

// FIXED REGEX
function antiSmash(text) {
    if(!text) return '';
    text = text.replace(/([a-z])([A-Z])/g, '$1 $2');
    text = text.replace(/([a-z])(\d)/g, '$1 $2');
    text = text.replace(/(\d)([a-zA-Z])/g, '$1 $2');
    text = text.replace(/([a-z]),([a-zA-Z])/g, '$1, $2');
    text = text.replace(/([a-z])\.([A-Z])/g, '$1. $2');
    text = text.replace(/([a-z]):([A-Z])/g, '$1: $2');
    text = text.replace(/\s{2,}/g, '); // FIXED
    return text.trim();
}

function renderAI(text) { return marked.parse(antiSmash(text)); }
function getTime() { return new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }

function addMessage(role, text, timestamp = null) {
    const wrap = document.createElement('div');
    wrap.className = 'message-wrap ' + role;

    const time = timestamp? new Date(timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : getTime();

    if(role === 'ai') {
        wrap.innerHTML = `
            <div class="message-avatar"><img src="/static/brain3d.png"></div>
            <div class="message ai-msg">
                <button class="copy-btn" onclick="copyText(this)">Copy</button>
                <div class="msg-content">${renderAI(text)}</div>
                <div class="msg-meta">${time}</div>
            </div>
        `;
    } else {
        wrap.innerHTML = `
            <div class="message user-msg">
                <div class="msg-content">${text}</div>
                <div class="msg-meta">${time} ✓✓</div>
            </div>
        `;
    }
    document.getElementById('chatBox').appendChild(wrap);
    document.getElementById('chatBox').scrollTop = document.getElementById('chatBox').scrollHeight;
    return wrap.querySelector('.message');
}

function copyText(btn) {
    const text = btn.parentElement.querySelector('.msg-content').innerText;
    navigator.clipboard.writeText(text);
    btn.innerText = 'Copied!';
    setTimeout(() => btn.innerText = 'Copy', 2000);
}

// INTRODUCTION STAYS VISIBLE
function showWelcome() {
    document.getElementById('welcomeCard').style.display = 'block';
}

function showApp() {
    document.getElementById('authScreen').style.display = 'none';
    document.getElementById('appContainer').style.display = 'flex';
    document.getElementById('sidebar').style.display = 'block';
    document.getElementById('userEmail').innerText = userEmail; // Shows "Guest User"
    if(!currentChatId) showWelcome();
}

async function sendMessage(questionOverride = null, isRegen = false) {
    let aiMsgDiv;
    try {
        if(isSending) return;
        const input = document.getElementById('userInput');
        const question = questionOverride || input.value.trim();
        if(!question &&!selectedFile) return;

        lastQuestion = question;
        isSending = true;
        document.getElementById('sendBtn').disabled = true;
        document.getElementById('stopBtn').style.display = 'inline-block';
        document.getElementById('regenBtn').style.display = 'none';

        if(!isRegen) addMessage('user', question + (selectedFile? `\n[Attached: ${selectedFile.name}]` : ''));
        input.value = '';

        aiMsgDiv = addMessage('ai', '');
        aiMsgDiv.classList.add('typing');

        const formData = new FormData();
        formData.append('question', question);
        formData.append('user_id', userId); // ALWAYS "guest"
        if(currentChatId) formData.append('chat_id', currentChatId);
        if(selectedFile) formData.append('file', selectedFile);

        controller = new AbortController();
        const res = await fetch('/api/chat', { method: 'POST', body: formData, signal: controller.signal });
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
                    else if(data) {
                        fullText += data;
                        aiMsgDiv.querySelector('.msg-content').innerHTML = renderAI(fullText);
                        document.getElementById('chatBox').scrollTop = document.getElementById('chatBox').scrollHeight;
                    }
                }
            }
        }
        aiMsgDiv.classList.remove('typing');
        aiMsgDiv.querySelector('.msg-content').innerHTML = renderAI(fullText.trim());
        document.getElementById('regenBtn').style.display = 'inline-block';

    } catch(err) {
        console.error("SEND ERROR:", err);
        if(aiMsgDiv) {
            aiMsgDiv.classList.remove('typing');
            aiMsgDiv.querySelector('.msg-content').innerHTML = `Error: ${err.message}`;
        }
    } finally {
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('stopBtn').style.display = 'none';
        isSending = false;
        selectedFile = null;
        document.getElementById('fileInput').value = '';
        document.getElementById('uploadBtn').innerText = '📎';
    }
  }
