"use strict";
const M = typeof window.marked!== "undefined", P = typeof window.DOMPurify!== "undefined";
if (M) {
    try { window.marked.setOptions({ breaks: true, gfm: true, sanitize: false }) }
    catch (e) { console.warn("marked error", e) }
} else {
    console.warn("marked missing")
}
if (!P) console.error("DOMPurify missing. XSS risk!");

let isSending = false, selectedFile = null, lastQuestion = "", controller = null, currentChatId = null, introShown = false;
const API_BASE = ""; // Use window.$ from auth.js
const DEBUG = true;

function debug(...args){ if(DEBUG) console.log("%c[Brain4.0 App]","color:#00BFFF;font-weight:bold",...args) }

function createUUID() {
    if (typeof crypto!== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    if (typeof crypto!== "undefined" && crypto.getRandomValues) {
        const b = new Uint8Array(16);
        crypto.getRandomValues(b);
        b[6] = b[6] & 15 | 64;
        b[8] = b[8] & 63 | 128;
        return [...b].map(x => x.toString(16).padStart(2, "0")).join("").replace(/(\w{8})(\w{4})(\w{4})(\w{4})(\w{12})/, "$1-$2-$3-$4-$5")
    }
    throw new Error("No UUID")
}

document.addEventListener("DOMContentLoaded", initializeApp);

async function initializeApp() {
    try {
        debug("initializeApp started");
        initEvents();
        if (window.initAuth) { await window.initAuth(); }
    } catch (error) { console.error("App initialization failed:", error) }
}

function showAuthScreen() { window.$("authScreen").style.display = "flex"; window.$("chatContainer").style.display = "none" }
function showChatScreen() { window.$("authScreen").style.display = "none"; window.$("chatContainer").style.display = "flex"; loadSidebar(); showIntroduction() }
window.showAuthScreen = showAuthScreen;
window.showChatScreen = showChatScreen;

function initEvents() {
    window.$("uploadBtn")?.addEventListener("click", () => window.$("fileInput")?.click());
    window.$("newChatBtn")?.addEventListener("click", newChat);
    window.$("hamburgerBtn")?.addEventListener("click", toggleSidebar);
    window.$("closeSidebarBtn")?.addEventListener("click", closeSidebar);
    window.$("sidebarOverlay")?.addEventListener("click", closeSidebar);
    window.$("fileInput")?.addEventListener("change", handleFileSelect);
    window.$("stopBtn")?.addEventListener("click", stopGeneration);
    window.$("regenBtn")?.addEventListener("click", () => { if (lastQuestion &&!isSending) sendMessage(lastQuestion, true) });
    window.$("chatForm")?.addEventListener("submit", e => { e.preventDefault(); sendMessage() });
    window.$("userInput")?.addEventListener("input", e => { e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px" });
    window.$("userInput")?.addEventListener("keydown", e => { if (e.key === "Enter" &&!e.shiftKey &&!e.isComposing) { e.preventDefault(); sendMessage() } });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeSidebar() });
    window.addEventListener("resize", handleResize);
    window.$("loginBtn")?.addEventListener("click", window.doLogin);
    window.$("signupBtn")?.addEventListener("click", window.doSignup);
    window.$("logoutBtn")?.addEventListener("click", window.doLogout)
}

function handleResize() { if (window.innerWidth >= 769) closeSidebar(); updateOverlay() }
function showIntroduction() {
    if (introShown) return;
    introShown = true;
    addMessage("ai", "### Welcome to Brain 4.0 by B.CORP\nI'm your AI OS for 2026. I use autonomous agents + 4-tier routing:\n\n- **⚡ Fast**: Hi/Thanks → Llama 8B Instant\n- **🎯 General**: Normal chat → Llama 3.3 70B\n- **🧠 Reasoning**: Coding/Strategy → GPT-OSS 120B\n- **👁️ Vision**: Images/PDFs → Llama 4 Scout\n\nI can also: Research, Remember things, Search your docs.\n---\nWhat would you like to build today?")
}
function toggleSidebar() { window.$("sidebar")?.classList.toggle("show"); updateOverlay() }
function closeSidebar() { window.$("sidebar")?.classList.remove("show"); updateOverlay() }
function updateOverlay() { const s = window.$("sidebar"), o = window.$("sidebarOverlay"); if (!s ||!o) return; o.classList.toggle("show", s.classList.contains("show") && window.innerWidth < 769) }

async function loadSidebar() {
    const list = window.$("chatList"); if (!list) return; if (!window.authToken()) return;
    debug("Loading sidebar");
    try {
        const r = await fetch(`${API_BASE}/api/chats`, { method: "GET", headers: window.getAuthHeaders(), cache: "no-store" });
        if (r.status === 401) { alert("Session expired"); window.doLogout(); return }
        if (!r.ok) return;
        const chats = await r.json();
        list.innerHTML = "";
        if (!Array.isArray(chats) ||!chats.length) { list.innerHTML = '<div style="color:#64748b;font-size:13px;padding:12px;text-align:center">No recent chats</div>'; return }
        chats.forEach(c => {
            if (c == null || c.id == null) return;
            const item = document.createElement("div");
            item.className = `chat-item${String(c.id) === String(currentChatId)? " active" : ""}`;
            const t = document.createElement("span"); t.textContent = c.title || "New conversation"; t.title = t.textContent;
            const d = document.createElement("button"); d.type = "button"; d.className = "chat-delete"; d.textContent = "✕"; d.setAttribute("aria-label", "Delete chat");
            t.onclick = e => { e.stopPropagation(); loadChat(c.id) };
            d.onclick = e => { e.stopPropagation(); deleteChat(c.id) };
            item.append(t, d); item.onclick = () => loadChat(c.id); list.append(item)
        })
    } catch (e) { console.error(e) }
}

async function newChat() {
    debug("New chat");
    if (isSending && controller) controller.abort();
    controller = null; isSending = false; currentChatId = lastQuestion = null; introShown = false;
    window.$("chatBox") && (window.$("chatBox").innerHTML = ""); resetAttachment(); setSendingState(false);
    showIntroduction(); if (window.innerWidth < 769) closeSidebar(); await loadSidebar()
}

async function loadChat(id) {
    if (!id || isSending) return;
    debug("Loading chat:", id);
    try {
        const r = await fetch(`${API_BASE}/api/chat/${encodeURIComponent(id)}`, { method: "GET", headers: window.getAuthHeaders(), cache: "no-store" });
        if (r.status === 401) { alert("Session expired"); window.doLogout(); return }
        if (r.status === 403) { alert("Access denied"); return }
        if (!r.ok) throw new Error(`Server ${r.status}`);
        const msgs = await r.json();
        currentChatId = id;
        const box = window.$("chatBox"); if (!box) return;
        box.innerHTML = ""; introShown = true;
        if (!Array.isArray(msgs) ||!msgs.length) { introShown = false; showIntroduction() }
        else msgs.forEach(m => { if (!m ||!m.role) return; const role = m.role === "assistant"? "ai" : m.role === "user"? "user" : null; if (role) addMessage(role, m.content || "", m.created_at) });
        if (window.innerWidth < 769) closeSidebar(); await loadSidebar()
    } catch (e) { console.error(e) }
}

async function deleteChat(id) {
    if (!id) return; if (!confirm("Delete this chat?")) return;
    debug("Deleting chat:", id);
    try {
        const r = await fetch(`${API_BASE}/api/chat/delete`, { method: "POST", headers: { "Content-Type": "application/json",...window.getAuthHeaders() }, body: JSON.stringify({ chat_id: id }) });
        if (r.status === 401) { alert("Session expired"); window.doLogout(); return }
        if (r.status === 403) { alert("Access denied"); return }
        if (!r.ok) throw new Error(`Server ${r.status}`);
        String(currentChatId) === String(id)? await newChat() : await loadSidebar()
    } catch (e) { console.error(e); alert("Delete failed") }
}

function handleFileSelect(e) { selectedFile = e.target.files?.[0] || null; updateAttachmentButton() }
function updateAttachmentButton() { const b = window.$("uploadBtn"); if (!b) return; if (selectedFile) { b.textContent = "📎1"; b.title = `Attached: ${selectedFile.name}` } else { b.textContent = "📎"; b.title = "Attach file" } }
function resetAttachment() { selectedFile = null; const f = window.$("fileInput"); if (f) f.value = ""; updateAttachmentButton() }
function antiSmash(t) { if (!t) return ""; return String(t).replace(/web_search\s*\{[\s\S]*?\}/gi, "").replace(/save_to_memory\s*\{[\s\S]*?\}/gi, "").replace(/Agent Research Results:[\s\S]*?User Query:/gi, "").trim() }
function escapeHTML(v) { return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
function safeHttpUrl(v) { try { const u = new URL(v); return u.protocol === "http:" || u.protocol === "https:"? u.href : null } catch { return null } }

function renderAI(text) {
    try {
        let clean = antiSmash(text); if (!clean) return "";
        if (!M ||!P) return `<div style="white-space:pre-wrap">${escapeHTML(clean)}</div>`;

        let banner = "";
        if (clean.includes("Agent Research Results:")) {
            banner = '<div class="agent-banner">🧠 Agent Mode: Research + Tools Used</div>';
            clean = clean.replace("Agent Research Results:", "")
        }

        // FIX: Corrected regex for Sources
        let sourcesHTML = "";
        const m = clean.match(/\*\*Sources\*\*\s*\n([\s\S]*)$/i);
        if (m) {
            const links = [...m[1].matchAll(/\[(\d+)\]\s*\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g)];
            if (links.length) {
                sourcesHTML = '<div class="sources"><b>Sources</b>';
                links.forEach(x => {
                    const url = safeHttpUrl(x[3]);
                    if (url) sourcesHTML += `<div class="source-card"><a href="${url}" target="_blank" rel="noopener noreferrer nofollow">[${escapeHTML(x[1])}] ${escapeHTML(x[2])}</a></div>`
                });
                sourcesHTML += "</div>";
                clean = clean.replace(/\*\*Sources\*\*\s*\n([\s\S]*)$/i, "").trim()
            }
        }
        const html = window.marked.parse(clean);
        const safe = window.DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ["p", "br", "strong", "em", "del", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "pre", "code", "a", "table", "thead", "tbody", "tr", "th", "td"],
            ALLOWED_ATTR: ["href", "target", "rel"],
            ALLOW_DATA_ATTR: false
        });
        return banner + safe + sourcesHTML
    } catch (e) { console.error(e); return `<div style="white-space:pre-wrap">${escapeHTML(text)}</div>` }
}

function getTime() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }

function addMessage(role, text, ts = null) {
    const box = window.$("chatBox"); if (!box) return null;
    const wrap = document.createElement("div"); wrap.className = `message-wrap ${role}`;
    const time = ts? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : getTime();
    if (role === "ai") {
        const a = document.createElement("div"); a.className = "message-avatar"; a.innerHTML = '<img src="/static/brain3d.png" alt="Brain">';
        const m = document.createElement("div"); m.className = "message ai-msg";
        const c = document.createElement("button"); c.type = "button"; c.className = "copy-btn"; c.textContent = "Copy"; c.onclick = () => copyText(c);
        const ct = document.createElement("div"); ct.className = "msg-content"; ct.innerHTML = renderAI(text);
        const meta = document.createElement("div"); meta.className = "msg-meta"; meta.textContent = time;
        m.append(c, ct, meta); wrap.append(a, m)
    } else {
        const m = document.createElement("div"); m.className = "message user-msg";
        const ct = document.createElement("div"); ct.className = "msg-content"; ct.textContent = text;
        const meta = document.createElement("div"); meta.className = "msg-meta"; meta.textContent = `${time} ✓✓`;
        m.append(ct, meta); wrap.append(m)
    }
    box.append(wrap); scrollChatToBottom(); return wrap.querySelector(".message")
}

async function copyText(b) {
    try {
        const t = b.closest(".message")?.querySelector(".msg-content")?.innerText || "";
        await navigator.clipboard.writeText(t);
        b.textContent = "Copied!";
        setTimeout(() => b.textContent = "Copy", 2000)
    } catch (e) {
        b.textContent = "Failed";
        setTimeout(() => b.textContent = "Copy", 2000)
    }
}

function scrollChatToBottom() { const b = window.$("chatBox"); if (b) requestAnimationFrame(() => b.scrollTop = b.scrollHeight) }
function stopGeneration() { if (controller) { controller.abort(); controller = null } setSendingState(false) }
function setSendingState(s) { const send = window.$("sendBtn"), stop = window.$("stopBtn"), regen = window.$("regenBtn"); if (send) send.disabled = s; if (stop) stop.style.display = s? "inline-block" : "none"; if (regen) regen.style.display = s? "none" : "inline-block" }

async function sendMessage(q = null, regen = false) {
    let ai = null;
    try {
        if (isSending) return;
        await window.getAuthToken();
        if (!window.authToken()) throw new Error("Please login");
        const input = window.$("userInput"); if (!input) throw new Error("No input");
        const question = q!== null? String(q).trim() : input.value.trim();
        const file = selectedFile;
        if (!question &&!file) return;
        lastQuestion = question;
        isSending = true; setSendingState(true);
        if (!regen) { let dt = question; if (file) dt += `\n[Attached: ${file.name}]`; addMessage("user", dt) }
        input.value = ""; input.style.height = "auto";
        const cid = createUUID();
        const fd = new FormData();
        fd.append("question", question);
        fd.append("client_msg_id", cid);
        fd.append("is_regen", regen? "1" : "0");
        if (currentChatId!= null) fd.append("chat_id", String(currentChatId));
        if (file) fd.append("file", file, file.name);
        resetAttachment();
        ai = addMessage("ai", ""); // Start with empty for streaming
        controller = new AbortController();

        debug("Sending request:", {cid, hasFile:!!file, regen});
        const r = await fetch(`${API_BASE}/api/chat`, { method: "POST", headers: { "Authorization": `Bearer ${window.authToken()}`, "Accept": "text/event-stream" }, body: fd, signal: controller.signal, cache: "no-store" });

        debug("Response:", r.status, r.headers.get("X-Request-ID"));
        if (r.status === 401) { window.doLogout(); throw new Error("Session expired. Please login again."); }
        if (r.status === 403) throw new Error("Forbidden");
        if (r.status === 409) throw new Error("Duplicate message");
        if (!r.ok) throw new Error(`Server ${r.status}`);
        if (!r.body) throw new Error("No stream");

        const reader = r.body.getReader(), decoder = new TextDecoder(); let buf = "", full = "";

        function processEV(ev) {
            if (!ev.trim()) return; let evn = "message", data = [];
            ev.split(/\r?\n/).forEach(l => { if (!l || l[0] === ":") return; if (l.startsWith("event:")) evn = l.slice(6).trim(); else if (l.startsWith("data:")) data.push(l.slice(5).replace(/^ /, "")) });
            if (!data.length) return; let payload; try { payload = JSON.parse(data.join("\n")) } catch { return }
            switch (evn) {
                case "token":
                    const t = payload?.text?? "";
                    if (t) {
                        full += t;
                        ai?.querySelector(".msg-content") && (ai.querySelector(".msg-content").innerHTML = renderAI(full));
                        scrollChatToBottom()
                    }
                    break;
                case "chat_id":
                    if (payload?.chat_id) { currentChatId = payload.chat_id }
                    break;
                case "done":
                    if (payload?.chat_id) currentChatId = payload.chat_id;
                    loadSidebar();
                    break;
                case "error":
                    throw new Error(payload?.message || "Error")
            }
        }

        while (true) {
            const { value, done } = await reader.read();
            if (done) { buf += decoder.decode(); if (buf.trim()) processEV(buf); break }
            buf += decoder.decode(value, { stream: true }); buf = buf.replace(/\r\n/g, "\n"); const parts = buf.split("\n\n"); buf = parts.pop() || ""; parts.forEach(processEV);
        }
    } catch (e) {
        if (e.name === "AbortError") { ai?.querySelector(".msg-content") && (ai.querySelector(".msg-content").innerHTML = "<i>*Stopped*</i>"); return }
        console.error(e); ai?.querySelector(".msg-content") && (ai.querySelector(".msg-content").innerHTML = renderAI(`**Error**\n\n${e.message}`))
    } finally { setSendingState(false); isSending = false; controller = null }
}
