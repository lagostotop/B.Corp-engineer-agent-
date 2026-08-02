marked.setOptions({ breaks: true, gfm: true });
let userId = "00000-0000-0000-0000-000001";
let isSending = false;
let selectedFile = null;
let lastQuestion = "";
let controller = null;
let currentChatId = null;
let introShown = false;

document.addEventListener('DOMContentLoaded', () => {
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
    document.getElementById('userInput').addEventListener('keypress', (e) => { if(e.key === 'Enter' &&!e.shiftKey) sendMessage(); });
    document.addEventListener('click', (e) => {
        const sidebar = document.getElementById('sidebar');
        const hamburger = document.getElementById('hamburgerBtn');
        if(window.innerWidth < 768 && sidebar.classList.contains('show')) {
            if(!sidebar.contains(e.target) &&!hamburger.contains(e.target)) {
                toggleSidebar();
            }
        }
    });
    loadSidebar();
    showIntroduction();
});

function showIntroduction() {
    if(introShown) return;
    introShown = true;
    const introText = `### Introduction
I'm your AI Assistant for 2026. I can:

- **Build**: Write full production code
- **Decide**: Give 1 clear recommendation with "why"
- **Explain**: Break complex topics into 3 steps
- **Search**: Live web data for news, prices, latest info

---
What would you like to build today?`;
    addMessage('ai', introText);
}

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('show'); }

async function loadSidebar() {
    try {
        const res = await fetch(`/api/chats?user_id=${userId}`);
        if(!res.ok) return;
        const chats = await res.json();
        const list = document.getElementById('chatList');
        list.innerHTML = '';
        chats.forEach(chat => {
            const div = document.createElement('div');
            div.className = 'chat-item';
            if(chat.id === currentChatId) div.classList.add('active');
            div.innerHTML = `<span onclick="loadChat('${chat.id}')">${chat.title}</span><span class="chat-delete" onclick="event.stopPropagation(); deleteChat('${chat.id}')">✕</span>`;
            list.appendChild(div);
        });
    } catch(e) { console.error("Load sidebar error:", e) }
}

async function newChat() {
    currentChatId = null;
    document.getElementById('chatBox').innerHTML = '';
    introShown = false;
    showIntroduction();
    if(window.innerWidth < 768) toggleSidebar();
    loadSidebar();
}

async function loadChat(chatId) {
    currentChatId = chatId;
    const res = await fetch(`/api/chat/${chatId}`);
    if(!res.ok) return;
    const messages = await res.json();
    document.getElementById('chatBox').innerHTML = '';
    if(messages.length === 0) showIntroduction();
    messages.forEach(m => addMessage(m.role, m.content, m.created_at));
    if(window.innerWidth < 768) toggleSidebar();
    loadSidebar();
}

async function deleteChat(chatId) {
    if(!confirm('Delete this chat? This cannot be undone.')) return;
    await fetch('/api/chat/delete', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({chat_id: chatId}) });
    if(currentChatId === chatId) newChat();
    loadSidebar();
}

function antiSmash(text) {
    if(!text) return '';
    text = text.replace(/([a-z])([A-Z])/g, '$1 $2');
    text = text.replace(/([a-z])(\d)/g, '$1 $2');
    text = text.replace(/(\d)([a-zA-Z])/g, '$1 $2');
    text = text.replace(/\s{2,}/g, ' ');
    return text.trim();
}

function renderAI(text) { return marked.parse(antiSmash(text)); }
function getTime() { return new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }

function addMessage(role, text, timestamp = null) {
    const wrap = document.createElement('div');
    wrap.className = 'message-wrap ' + role;
    const time = timestamp? new Date(timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : getTime();
    if(role === 'ai') {
        wrap.innerHTML = `<div class="message-avatar"><img src="/static/brain3d.png"></div><div class="message ai-msg"><button class="copy-btn" onclick="copyText(this)">Copy</button><div class="msg-content">${renderAI(text)}</div><div class="msg-meta">${time}</div></div>`;
    } else {
        wrap.innerHTML = `<div class="message user-msg"><div class="msg-content">${text}</div><div class="msg-meta">${time} ✓✓</div></div>`;
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
        formData.append('user_id', userId);
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
        document.getElementById('regenBtn').style.display = 'inline-block';
    } catch(err) {
        console.error("SEND ERROR:", err);
        if(aiMsgDiv) {
            aiMsgDiv.classList.remove('typing');
            aiMsgDiv.querySelector('.msg-content').innerHTML = `**Error: Server Error**<br>${err.message}`;
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
