/* =========================================================
   BRAIN 3.0 BY B.CORP
   Frontend Controller v5.4.0
   JWT Auth + Production Debugged
   ========================================================= */

"use strict";

const MARKED_AVAILABLE = typeof window.marked!== "undefined";
if (MARKED_AVAILABLE) {
    try { window.marked.setOptions({ breaks: true, gfm: true }); }
    catch (error) { console.warn("Brain 3.0: Could not configure marked.js.", error); }
} else { console.warn("Brain 3.0: marked.js was not loaded."); }

let userId = null; // NOW COMES FROM SUPABASE
let isSending = false;
let selectedFile = null;
let lastQuestion = "";
let controller = null;
let currentChatId = null;
let introShown = false;
let authToken = null; // NEW: Store Supabase JWT

function $(id) { return document.getElementById(id); }

// NEW: Get auth token from Supabase or fallback to guest
async function getAuthToken() {
    // TODO: Replace with real supabase.auth.getSession()
    // For now: check localStorage or use guest
    authToken = localStorage.getItem("brain30_access_token");
    userId = localStorage.getItem("brain30_user_id");
    
    if (!authToken) {
        // GUEST MODE FOR TESTING - REMOVE IN PROD
        if (!userId) {
            userId = crypto.randomUUID();
            localStorage.setItem("brain30_user_id", userId);
        }
        authToken = `guest-${userId}`; // Backend will reject this in prod
        console.warn("Brain 3.0: Running in GUEST MODE. Add Supabase Auth for production.");
    }
    return authToken;
}

function getAuthHeaders() {
    const headers = { "Accept": "application/json" };
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    return headers;
}

document.addEventListener("DOMContentLoaded", initializeApp);

async function initializeApp() {
    await getAuthToken(); // LOAD TOKEN FIRST
    initEvents();
    updateOverlay();
    loadSidebar();
    showIntroduction();
}

function initEvents() {
    $("uploadBtn")?.addEventListener("click", () => { $("fileInput")?.click(); });
    $("newChatBtn")?.addEventListener("click", newChat);
    $("hamburgerBtn")?.addEventListener("click", toggleSidebar);
    $("closeSidebarBtn")?.addEventListener("click", closeSidebar);
    $("sidebarOverlay")?.addEventListener("click", closeSidebar);
    $("fileInput")?.addEventListener("change", handleFileSelect);
    $("stopBtn")?.addEventListener("click", stopGeneration);
    $("regenBtn")?.addEventListener("click", () => { if (lastQuestion &&!isSending) { sendMessage(lastQuestion, true); } });

    $("chatForm")?.addEventListener("submit", event => {
        event.preventDefault();
        sendMessage();
    });

    $("userInput")?.addEventListener("keydown", event => {
        if (event.key === "Enter" &&!event.shiftKey &&!event.isComposing) {
            event.preventDefault();
            sendMessage();
        }
    });
    document.addEventListener("keydown", event => { if (event.key === "Escape") { closeSidebar(); } });
    window.addEventListener("resize", handleResize);
}

function handleResize() {
    if (window.innerWidth >= 769) { closeSidebar(); }
    updateOverlay();
}

function showIntroduction() {
    if (introShown) { return; }
    introShown = true;
    const introText = `### Welcome to Brain 3.0 by B.CORP
I'm your AI Assistant for 2026. I can:
- **Build**: Write full production code
- **Decide**: Give 1 clear recommendation with why
- **Explain**: Break complex topics into 3 steps
- **Search**: Live web data with citations
---
**User ID**: \`${userId?.slice(0, 8)}...\`
What would you like to build today?`;
    addMessage("ai", introText);
}

function toggleSidebar() {
    const sidebar = $("sidebar");
    if (!sidebar) { return; }
    sidebar.classList.toggle("show");
    updateOverlay();
}

function closeSidebar() {
    const sidebar = $("sidebar");
    if (!sidebar) { return; }
    sidebar.classList.remove("show");
    updateOverlay();
}

function updateOverlay() {
    const sidebar = $("sidebar");
    const overlay = $("sidebarOverlay");
    if (!sidebar ||!overlay) { return; }
    const visible = sidebar.classList.contains("show") && window.innerWidth < 769;
    overlay.classList.toggle("show", visible);
}

async function loadSidebar() {
    const list = $("chatList");
    if (!list) { console.warn("Brain 3.0: #chatList was not found in index.html."); return; }
    try {
        // FIX: NO user_id in URL. Auth via header
        const response = await fetch(`/api/chats`, { 
            method: "GET", 
            headers: getAuthHeaders(), 
            cache: "no-store" 
        });
        if (response.status === 401) { alert("Session expired. Please login."); return; }
        if (!response.ok) { console.warn("Sidebar request failed:", response.status); return; }
        const chats = await response.json();
        list.innerHTML = "";
        if (!Array.isArray(chats) || chats.length === 0) {
            const empty = document.createElement("div");
            empty.style.cssText = "color:#64748b;font-size:13px;padding:12px;text-align:center;";
            empty.textContent = "No recent chats";
            list.appendChild(empty);
            return;
        }
        chats.forEach(chat => {
            if (!chat || chat.id === undefined || chat.id === null) { return; }
            const item = document.createElement("div");
            item.className = "chat-item" + (String(chat.id) === String(currentChatId)? " active" : "");
            const title = document.createElement("span");
            title.textContent = chat.title || "New conversation";
            title.title = title.textContent;
            const deleteButton = document.createElement("span");
            deleteButton.className = "chat-delete";
            deleteButton.textContent = "✕";
            deleteButton.title = "Delete chat";
            deleteButton.setAttribute("role", "button");
            deleteButton.setAttribute("tabindex", "0");
            deleteButton.setAttribute("aria-label", "Delete chat");
            title.addEventListener("click", event => { event.stopPropagation(); loadChat(chat.id); });
            deleteButton.addEventListener("click", event => { event.stopPropagation(); deleteChat(chat.id); });
            deleteButton.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); deleteChat(chat.id); } });
            item.appendChild(title);
            item.appendChild(deleteButton);
            item.addEventListener("click", () => loadChat(chat.id));
            list.appendChild(item);
        });
    } catch (error) { console.error("Load sidebar error:", error); }
}

async function newChat() {
    if (isSending && controller) { controller.abort(); }
    controller = null; isSending = false; currentChatId = null; lastQuestion = ""; introShown = false;
    const chatBox = $("chatBox"); if (chatBox) { chatBox.innerHTML = ""; }
    resetAttachment(); setSendingState(false); showIntroduction();
    if (window.innerWidth < 769) { closeSidebar(); }
    await loadSidebar();
}

async function loadChat(chatId) {
    if (!chatId || isSending) { return; }
    try {
        const response = await fetch(`/api/chat/${encodeURIComponent(chatId)}`, { 
            method: "GET", 
            headers: getAuthHeaders(), // FIX: AUTH HEADER
            cache: "no-store" 
        });
        if (response.status === 401) { alert("Session expired. Please login."); return; }
        if (response.status === 403) { alert("You don't have access to this chat."); return; }
        if (!response.ok) { throw new Error(`Unable to load chat (${response.status})`); }
        const messages = await response.json();
        currentChatId = chatId;
        const chatBox = $("chatBox"); if (!chatBox) { return; }
        chatBox.innerHTML = ""; introShown = true;
        if (!Array.isArray(messages) || messages.length === 0) { introShown = false; showIntroduction(); }
        else {
            messages.forEach(message => {
                if (!message ||!message.role) { return; }
                const role = message.role === "assistant"? "ai" : message.role === "user"? "user" : null;
                if (!role) { return; }
                addMessage(role, message.content || "", message.created_at);
            });
        }
        if (window.innerWidth < 769) { closeSidebar(); }
        await loadSidebar();
    } catch (error) { console.error("Load chat error:", error); }
}

async function deleteChat(chatId) {
    if (!chatId) { return; }
    const confirmed = window.confirm("Delete this chat? This cannot be undone.");
    if (!confirmed) { return; }
    try {
        // FIX: NO user_id in body
        const response = await fetch("/api/chat/delete", { 
            method: "POST", 
            headers: { "Content-Type": "application/json", ...getAuthHeaders() }, 
            body: JSON.stringify({ chat_id: chatId }) 
        });
        if (response.status === 401) { alert("Session expired. Please login."); return; }
        if (response.status === 403) { alert("You don't have access to this chat."); return; }
        if (!response.ok) { throw new Error(`Delete failed (${response.status})`); }
        if (String(currentChatId) === String(chatId)) { await newChat(); } else { await loadSidebar(); }
    } catch (error) { console.error("Delete chat error:", error); alert("Unable to delete this chat."); }
}

function handleFileSelect(event) {
    const file = event.target.files?.[0] || null;
    selectedFile = file;
    updateAttachmentButton();
}

function updateAttachmentButton() {
    const button = $("uploadBtn");
    if (!button) { return; }
    if (selectedFile) {
        button.textContent = "📎1";
        button.title = `Attached: ${selectedFile.name}`;
        button.setAttribute("aria-label", `Attached: ${selectedFile.name}`);
    } else {
        button.textContent = "📎";
        button.title = "Attach file";
        button.setAttribute("aria-label", "Attach file");
    }
}

function resetAttachment() {
    selectedFile = null;
    const fileInput = $("fileInput");
    if (fileInput) { fileInput.value = ""; }
    updateAttachmentButton();
}

function antiSmash(text) {
    if (!text) { return ""; }
    let clean = String(text);
    clean = clean.replace(/web_search\s*\{[\s\S]*?\}/gi, "");
    clean = clean.replace(/save_to_memory\s*\{[\s\S]*?\}/gi, "");
    clean = clean.replace(/\[(\d+)\]"([^"]+)"/g, "[$1] \"$2\"");
    return clean.trim();
}

function escapeHTML(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }

function renderAI(text) {
    try {
        let clean = antiSmash(text);
        if (!clean) { return ""; }
        if (typeof window.marked === "undefined") { return `<div style="white-space:pre-wrap">${escapeHTML(clean)}</div>`; }
        if (clean.includes("Here's the plan:")) {
            clean = clean.replace("Here's the plan:", '<div class="agent-banner">🧠 Agent Mode</div>\n### Here\'s the plan:');
        }
        const sourceRegex = /\*\*Sources\*\s*\n([\s\S]*)$/i;
        const sourceMatch = clean.match(sourceRegex);
        if (sourceMatch) {
            const sourceText = sourceMatch[1];
            const linkRegex = /\[(\d+)\]\s*\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g;
            const links = [...sourceText.matchAll(linkRegex)];
            if (links.length > 0) {
                let sourcesHTML = '<div class="sources"><b>Sources</b>';
                links.forEach(match => {
                    const number = escapeHTML(match[1]);
                    const title = escapeHTML(match[2]);
                    const url = escapeHTML(match[3]);
                    sourcesHTML += `<div class="source-card"><a href="${url}" target="_blank" rel="noopener noreferrer">[${number}] ${title}</a></div>`;
                });
                sourcesHTML += "</div>";
                clean = clean.replace(sourceRegex, "");
                return (window.marked.parse(clean) + sourcesHTML);
            }
        }
        return window.marked.parse(clean);
    } catch (error) {
        console.error("Render error:", error);
        return `<div style="white-space:pre-wrap">${escapeHTML(text)}</div>`;
    }
}

function getTime() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

function addMessage(role, text, timestamp = null) {
    const chatBox = $("chatBox"); if (!chatBox) return null;
    const wrap = document.createElement("div"); wrap.className = `message-wrap ${role}`;
    const time = timestamp? new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : getTime();
    if (role === "ai") {
        const avatar = document.createElement("div"); avatar.className = "message-avatar";
        const image = document.createElement("img"); image.src = "/static/brain3d.png"; image.alt = "Brain"; avatar.appendChild(image);
        const message = document.createElement("div"); message.className = "message ai-msg";
        const copyButton = document.createElement("button"); copyButton.type = "button"; copyButton.className = "copy-btn"; copyButton.textContent = "Copy";
        copyButton.addEventListener("click", () => copyText(copyButton));
        const content = document.createElement("div"); content.className = "msg-content"; content.innerHTML = renderAI(text);
        const meta = document.createElement("div"); meta.className = "msg-meta"; meta.textContent = time;
        message.appendChild(copyButton); message.appendChild(content); message.appendChild(meta);
        wrap.appendChild(avatar); wrap.appendChild(message);
    } else {
        const message = document.createElement("div"); message.className = "message user-msg";
        const content = document.createElement("div"); content.className = "msg-content"; content.innerHTML = escapeHTML(text).replace(/\n/g, "<br>");
        const meta = document.createElement("div"); meta.className = "msg-meta"; meta.textContent = `${time} ✓✓`;
        message.appendChild(content); message.appendChild(meta); wrap.appendChild(message);
    }
    chatBox.appendChild(wrap); scrollChatToBottom(); return wrap.querySelector(".message");
}

async function copyText(button) {
    try {
        const message = button.closest(".message"); const content = message?.querySelector(".msg-content");
        if (!content) return; const text = content.innerText || "";
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied!"; setTimeout(() => { button.textContent = "Copy"; }, 2000);
    } catch (error) { console.error("Copy failed:", error); button.textContent = "Failed"; setTimeout(() => { button.textContent = "Copy"; }, 2000); }
}

function scrollChatToBottom() {
    const chatBox = $("chatBox"); if (!chatBox) return;
    requestAnimationFrame(() => { chatBox.scrollTop = chatBox.scrollHeight; });
}

function stopGeneration() {
    if (controller) { controller.abort(); controller = null; }
    setSendingState(false);
}

function setSendingState(sending) {
    const sendButton = $("sendBtn");
    const stopButton = $("stopBtn");
    const regenButton = $("regenBtn");
    if (sendButton) { sendButton.disabled = sending; }
    if (stopButton) { stopButton.style.display = sending? "inline-block" : "none"; }
    if (regenButton) { regenButton.style.display = sending? "none" : "inline-block"; }
}

async function sendMessage(questionOverride = null, isRegen = false) {
    let aiMsgDiv;
    try {
        if (isSending) return;
        await getAuthToken(); // REFRESH TOKEN
        const input = $("userInput");
        const question = questionOverride || input.value.trim();
        if (!question &&!selectedFile) return;

        lastQuestion = question;
        isSending = true;
        setSendingState(true);

        if (!isRegen) { addMessage('user', question + (selectedFile? `\n[Attached: ${selectedFile.name}]` : '')); }
        input.value = '';
        resetAttachment();

        aiMsgDiv = addMessage('ai', '');

        const formData = new FormData();
        formData.append('question', question);
        // REMOVED: formData.append('user_id', userId);
        if (currentChatId) formData.append('chat_id', currentChatId);
        if (selectedFile) formData.append('file', selectedFile);

        controller = new AbortController();
        const res = await fetch('/api/chat', { 
            method: 'POST', 
            headers: { "Authorization": `Bearer ${authToken}` }, // FIX: AUTH HEADER
            body: formData, 
            signal: controller.signal 
        });
        if (res.status === 401) throw new Error('Unauthorized. Please login.');
        if (!res.ok) throw new Error('Server Error: ' + res.status);

        // FIX 2: ROBUST SSE BUFFER
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let fullText = '';
        let streamDone = false;

        while (!streamDone) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = line.substring(6).trim();

                if (data.startsWith('[CHAT_ID]')) {
                    currentChatId = data.replace('[CHAT_ID]', '').replace('[/CHAT_ID]', '');
                    loadSidebar();
                } else if (data === '[DONE]') {
                    streamDone = true;
                    break;
                } else if (data) {
                    fullText += data;
                    aiMsgDiv.querySelector('.msg-content').innerHTML = renderAI(fullText);
                    scrollChatToBottom();
                }
            }
        }
    } catch (err) {
        if (err.name === "AbortError") {
            if (aiMsgDiv) aiMsgDiv.querySelector('.msg-content').innerHTML = `<i>*Generation stopped*</i>`;
        } else {
            console.error("SEND ERROR:", err);
            if (aiMsgDiv) {
                aiMsgDiv.querySelector('.msg-content').innerHTML = `**Brain 3.0 Error**<br>${escapeHTML(err.message)}<br><small>Try regenerating.</small>`;
            }
        }
    } finally {
        setSendingState(false);
        isSending = false;
        controller = null;
    }
                  }
