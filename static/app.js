"use strict";
const M=typeof window.marked!=="undefined",P=typeof window.DOMPurify!=="undefined";
if(M){try{window.marked.setOptions({breaks:!0,gfm:!0,sanitize:!1})}catch(e){console.warn("marked error",e)}}else console.warn("marked missing");
if(!P)console.error("DOMPurify missing. XSS risk!");

let userId=null,isSending=!1,selectedFile=null,lastQuestion="",controller=null,currentChatId=null,introShown=!1,authToken=null;
const $=id=>document.getElementById(id);
const API_BASE = "";
const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co"
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjcmRtd3RzZ2diZ2NvbnF2a2p6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MDAwMjAsImV4cCI6MjA5NTk3NjAyMH0.o7d6lTABfWaf_5NtPSWLR9qCUJvS_kYL9bI7Z2fSX50"
let supabase = null;

function createUUID(){if(typeof crypto!=="undefined"&&crypto.randomUUID)return crypto.randomUUID();if(typeof crypto!=="undefined"&&crypto.getRandomValues){const b=new Uint8Array(16);crypto.getRandomValues(b);b[6]=b[6]&15|64;b[8]=b[8]&63|128;return[...b].map(x=>x.toString(16).padStart(2,"0")).join("").replace(/(\w{8})(\w{4})(\w{4})(\w{4})(\w{12})/,"$1-$2-$3-$4-$5")}throw new Error("No UUID")}
function setAuthStatus(text){const el=$("authStatus");if(el)el.textContent=text}

async function getAuthToken() {
  if (!supabase) {console.error("Supabase client not initialized");return null}
  try {
    const { data, error } = await supabase.auth.getSession();
    if (error) {console.error("getSession error:", error);authToken = null;userId = null;return null}
    const session = data?.session || null;
    authToken = session?.access_token || null;
    userId = session?.user?.id || null;
    console.log("Auth session:", { authenticated:!!authToken, userId });
    return authToken;
  } catch (error) {console.error("Auth initialization failed:", error);authToken = null;userId = null;return null}
}

function getAuthHeaders(){const h={"Accept":"application/json"};if(authToken)h.Authorization=`Bearer ${authToken}`;return h}

document.addEventListener("DOMContentLoaded",initializeApp);

async function initializeApp() {
  try {
    setAuthStatus("Loading authentication...");
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";
    s.onload = async () => {
      try {
        if (!window.supabase) {throw new Error("Supabase SDK unavailable")}
        supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        console.log("Supabase initialized");

        supabase.auth.onAuthStateChange((event, session) => {
            authToken = session?.access_token || null;
            userId = session?.user?.id || null;
        });

        setAuthStatus("Checking session...");
        await getAuthToken();
        if (authToken) {console.log("Existing session found");showChatScreen()}
        else {console.log("No session found");setAuthStatus("");showAuthScreen()}
      } catch (error) {console.error("Authentication initialization failed:", error);setAuthStatus("Authentication initialization failed. Check console.")}
    };
    s.onerror = () => {console.error("Could not load Supabase SDK");setAuthStatus("Could not load authentication service.")};
    document.head.appendChild(s);
    initEvents();
    updateOverlay();
  } catch (error) {console.error("Initialization error:", error)}
}

function showAuthScreen(){$("authScreen").style.display = "flex";$("chatContainer").style.display = "none"}
function showChatScreen(){$("authScreen").style.display = "none";$("chatContainer").style.display = "flex";loadSidebar();showIntroduction()}

async function doLogin() {
  const email = $("emailInput").value.trim();
  const password = $("passwordInput").value;
  if (!email ||!password) {$("authError").textContent = "Enter email and password";return}
  if (!supabase) {$("authError").textContent = "Authentication is still loading. Please wait.";return}
  const btn = $("loginBtn");
  btn.disabled = true;btn.textContent = "Signing in...";
  $("authError").style.color = "#64748b";$("authError").textContent = "Authenticating...";
  try {
    const { data, error } = await supabase.auth.signInWithPassword({email, password});
    console.log("Supabase login result:", { hasData:!!data, hasSession:!!data?.session, hasUser:!!data?.user, error: error?.message || null });
    if (error) {$("authError").style.color = "#ef4444";$("authError").textContent = error.message;return}
    if (!data?.session?.access_token) {$("authError").style.color = "#ef4444";$("authError").textContent = "Login succeeded but Supabase returned no session.";return}
    authToken = data.session.access_token;
    userId = data.user?.id || null;
    console.log("Login successful:", userId);
    $("authError").style.color = "#22c55e";$("authError").textContent = "Login successful!";
    showChatScreen();loadSidebar();showIntroduction();
  } catch (error) {console.error("Login exception:", error);$("authError").style.color = "#ef4444";$("authError").textContent = error?.message || "Login failed";
  } finally {btn.disabled = false;btn.textContent = "Sign In"}
}

async function doSignup(){
  const email = $("emailInput").value.trim();
  const password = $("passwordInput").value.trim();
  if(!email ||!password) return alert("Enter email and password");
  if(password.length < 6) return alert("Password must be 6+ characters");
  if (!supabase) return alert("Auth loading...");
  $("authError").textContent = "Creating account...";
  const {data, error} = await supabase.auth.signUp({email, password});
  if(error){ $("authError").textContent = error.message; return }
  if(data.session){
    authToken = data.session.access_token;userId = data.user.id;
    $("authError").style.color = "#22c55e";$("authError").textContent = "Account created! Logging you in...";
    setTimeout(()=>{ showChatScreen(); loadSidebar(); showIntroduction(); }, 800);
  } else {$("authError").style.color = "#22c55e";$("authError").textContent = "Account created! Check email to confirm, then Sign In."}
}

async function doLogout(){await supabase?.auth.signOut();authToken = null;userId = null;location.reload()}

function initEvents(){
  $("uploadBtn")?.addEventListener("click",()=>$("fileInput")?.click());
  $("newChatBtn")?.addEventListener("click",newChat);
  $("hamburgerBtn")?.addEventListener("click",toggleSidebar);
  $("closeSidebarBtn")?.addEventListener("click",closeSidebar);
  $("sidebarOverlay")?.addEventListener("click",closeSidebar);
  $("fileInput")?.addEventListener("change",handleFileSelect);
  $("stopBtn")?.addEventListener("click",stopGeneration);
  $("regenBtn")?.addEventListener("click",()=>{if(lastQuestion&&!isSending)sendMessage(lastQuestion,!0)});
  $("chatForm")?.addEventListener("submit",e=>{e.preventDefault();sendMessage()});
  $("userInput")?.addEventListener("input",e=>{e.target.style.height="auto";e.target.style.height=Math.min(e.target.scrollHeight,200)+"px"});
  $("userInput")?.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendMessage()}});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")closeSidebar()});
  window.addEventListener("resize",handleResize);
  $("loginBtn")?.addEventListener("click",doLogin);
  $("signupBtn")?.addEventListener("click",doSignup);
  $("logoutBtn")?.addEventListener("click",doLogout)
}
function handleResize(){if(window.innerWidth>=769)closeSidebar();updateOverlay()}
function showIntroduction(){if(introShown)return;introShown=!0;addMessage("ai","### Welcome to Brain 3.0 by B.CORP\nI'm your AI Assistant for 2026. I can:\n- **Build**: Write full production code\n- **Decide**: Give 1 clear recommendation with why\n- **Explain**: Break complex topics into 3 steps\n- **Search**: Live web data with citations\n---\nWhat would you like to build today?")}
function toggleSidebar(){$("sidebar")?.classList.toggle("show");updateOverlay()}
function closeSidebar(){$("sidebar")?.classList.remove("show");updateOverlay()}
function updateOverlay(){const s=$("sidebar"),o=$("sidebarOverlay");if(!s||!o)return;o.classList.toggle("show",s.classList.contains("show")&&window.innerWidth<769)}

async function loadSidebar(){
  const list=$("chatList");if(!list)return;if(!authToken) return;
  try{
    const r=await fetch(`${API_BASE}/api/chats`,{method:"GET",headers:getAuthHeaders(),cache:"no-store"});
    if(r.status===401){alert("Session expired");doLogout();return}
    if(!r.ok)return;
    const chats=await r.json();
    list.innerHTML="";
    if(!Array.isArray(chats)||!chats.length){list.innerHTML='<div style="color:#64748b;font-size:13px;padding:12px;text-align:center">No recent chats</div>';return}
    chats.forEach(c=>{
      if(c==null||c.id==null)return;
      const item=document.createElement("div");
      item.className="chat-item"+(String(c.id)===String(currentChatId)?" active":"");
      const t=document.createElement("span");t.textContent=c.title||"New conversation";t.title=t.textContent;
      const d=document.createElement("button");d.type="button";d.className="chat-delete";d.textContent="✕";d.setAttribute("aria-label","Delete chat");
      t.onclick=e=>{e.stopPropagation();loadChat(c.id)};
      d.onclick=e=>{e.stopPropagation();deleteChat(c.id)};
      item.append(t,d);item.onclick=()=>loadChat(c.id);list.append(item)
    })
  }catch(e){console.error(e)}
}

async function newChat(){
  if(isSending&&controller)controller.abort();
  controller=null;isSending=!1;currentChatId=lastQuestion=null;introShown=!1;
  $("chatBox")&&($("chatBox").innerHTML="");resetAttachment();setSendingState(!1);
  showIntroduction();if(window.innerWidth<769)closeSidebar();await loadSidebar()
}

async function loadChat(id){
  if(!id||isSending)return;
  try{
    const r=await fetch(`${API_BASE}/api/chat/${encodeURIComponent(id)}`,{method:"GET",headers:getAuthHeaders(),cache:"no-store"});
    if(r.status===401){alert("Session expired");doLogout();return}
    if(r.status===403){alert("Access denied");return}
    if(!r.ok)throw new Error(r.status);
    const msgs=await r.json();
    currentChatId=id;
    const box=$("chatBox");if(!box)return;
    box.innerHTML="";introShown=!0;
    if(!Array.isArray(msgs)||!msgs.length){introShown=!1;showIntroduction()}
    else msgs.forEach(m=>{if(!m||!m.role)return;const role=m.role==="assistant"?"ai":m.role==="user"?"user":null;if(role)addMessage(role,m.content||"",m.created_at)});
    if(window.innerWidth<769)closeSidebar();await loadSidebar()
  }catch(e){console.error(e)}
}

async function deleteChat(id){
  if(!id)return;if(!confirm("Delete this chat?"))return;
  try{
    const r=await fetch(`${API_BASE}/api/chat/delete`,{method:"POST",headers:{"Content-Type":"application/json",...getAuthHeaders()},body:JSON.stringify({chat_id:id})});
    if(r.status===401){alert("Session expired");doLogout();return}
    if(r.status===403){alert("Access denied");return}
    if(!r.ok)throw new Error(r.status);
    String(currentChatId)===String(id)?await newChat():await loadSidebar()
  }catch(e){console.error(e);alert("Delete failed")}
}

function handleFileSelect(e){selectedFile=e.target.files?.[0]||null;updateAttachmentButton()}
function updateAttachmentButton(){const b=$("uploadBtn");if(!b)return;if(selectedFile){b.textContent="📎1";b.title=`Attached: ${selectedFile.name}`}else{b.textContent="📎";b.title="Attach file"}}
function resetAttachment(){selectedFile=null;const f=$("fileInput");if(f)f.value="";updateAttachmentButton()}
function antiSmash(t){if(!t)return"";return String(t).replace(/web_search\s*\{[\s\S]*?\}/gi,"").replace(/save_to_memory\s*\{[\s\S]*?\}/gi,"").replace(/\[(\d+)\]"([^"]+)"/g,'[$1] "$2"').trim()}
function escapeHTML(v){return String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;")}
function safeHttpUrl(v){try{const u=new URL(v);return u.protocol==="http:"||u.protocol==="https:"?u.href:null}catch{return null}}

// FIX 3: SAFE XSS FALLBACK
function renderAI(text){
  try{
    let clean=antiSmash(text);if(!clean)return"";
    if(!M ||!P)return`<div style="white-space:pre-wrap">${escapeHTML(clean)}</div>`; // Render plain text if deps missing

    let banner="";if(clean.includes("Here's the plan:")){clean=clean.replace("Here's the plan:","");banner='<div class="agent-banner">🧠 Agent Mode</div>'}
    let sourcesHTML="";const m=clean.match(/\*\*Sources\*\s*\n([\s\S]*)$/i);
    if(m){
      const links=[...m[1].matchAll(/\[(\d+)\]\s*\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g)];
      if(links.length){sourcesHTML='<div class="sources"><b>Sources</b>';links.forEach(x=>{const url=safeHttpUrl(x[3]);if(url)sourcesHTML+=`<div class="source-card"><a href="${url}" target="_blank" rel="noopener noreferrer nofollow">[${escapeHTML(x[1])}] ${escapeHTML(x[2])}</a></div>`});sourcesHTML+="</div>";clean=clean.replace(/\*\*Sources\*\s*\n([\s\S]*)$/i,"").trim()}
    }
    const html=window.marked.parse(clean);
    const safe=window.DOMPurify.sanitize(html,{ALLOWED_TAGS:["p","br","strong","em","del","h1","h2","h3","ul","ol","li","blockquote","pre","code","a"],ALLOWED_ATTR:["href","target","rel"],ALLOW_DATA_ATTR:!1});
    return banner+safe+sourcesHTML
  }catch(e){console.error(e);return`<div style="white-space:pre-wrap">${escapeHTML(text)}</div>`}
}

function getTime(){return new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}
function addMessage(role,text,ts=null){
  const box=$("chatBox");if(!box)return null;
  const wrap=document.createElement("div");wrap.className=`message-wrap ${role}`;
  const time=ts?new Date(ts).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}):getTime();
  if(role==="ai"){
    const a=document.createElement("div");a.className="message-avatar";a.innerHTML='<img src="/static/brain3d.png" alt="Brain">';
    const m=document.createElement("div");m.className="message ai-msg";
    const c=document.createElement("button");c.type="button";c.className="copy-btn";c.textContent="Copy";c.onclick=()=>copyText(c);
    const ct=document.createElement("div");ct.className="msg-content";ct.innerHTML=renderAI(text);
    const meta=document.createElement("div");meta.className="msg-meta";meta.textContent=time;
    m.append(c,ct,meta);wrap.append(a,m)
  }else{
    const m=document.createElement("div");m.className="message user-msg";
    const ct=document.createElement("div");ct.className="msg-content";ct.textContent=text;
    const meta=document.createElement("div");meta.className="msg-meta";meta.textContent=`${time} ✓✓`;
    m.append(ct,meta);wrap.append(m)
  }
  box.append(wrap);scrollChatToBottom();return wrap.querySelector(".message")
}

async function copyText(b){try{const t=b.closest(".message")?.querySelector(".msg-content")?.innerText||"";await navigator.clipboard.writeText(t);b.textContent="Copied!";setTimeout(()=>b.textContent="Copy",2000)}catch(e){b.textContent="Failed";setTimeout(()=>b.textContent="Copy",2000)}}
function scrollChatToBottom(){const b=$("chatBox");if(b)requestAnimationFrame(()=>b.scrollTop=b.scrollHeight)}
function stopGeneration(){if(controller){controller.abort();controller=null}setSendingState(!1)}
function setSendingState(s){const send=$("sendBtn"),stop=$("stopBtn"),regen=$("regenBtn");if(send)send.disabled=s;if(stop)stop.style.display=s?"inline-block":"none";if(regen)regen.style.display=s?"none":"inline-block"}

async function sendMessage(q=null,regen=!1){
  let ai=null;
  try{
    if(isSending)return;
    await getAuthToken();
    if(!authToken)throw new Error("Please login");
    const input=$("userInput");if(!input)throw new Error("No input");
    const question=q!==null?String(q).trim():input.value.trim();
    const file=selectedFile;
    if(!question&&!file)return;
    lastQuestion=question;
    isSending=!0;setSendingState(!0);
    if(!regen){let dt=question;if(file)dt+=`\n[Attached: ${file.name}]`;addMessage("user",dt)}
    input.value="";input.style.height="auto";
    const cid=createUUID();
    const fd=new FormData();
    fd.append("question",question);
    fd.append("client_msg_id",cid);
    fd.append("is_regen",regen?"1":"0");
    if(currentChatId!=null)fd.append("chat_id",String(currentChatId));
    if(file)fd.append("file",file,file.name);
    resetAttachment();
    ai=addMessage("ai","");
    controller=new AbortController();
    const r=await fetch(`${API_BASE}/api/chat`,{method:"POST",headers:{"Authorization":`Bearer ${authToken}`,"Accept":"text/event-stream"},body:fd,signal:controller.signal,cache:"no-store"});
    if(r.status===401){doLogout();throw new Error("Session expired. Please login again.");}
    if(r.status===403)throw new Error("Forbidden");
    if(r.status===409)throw new Error("Duplicate message");
    if(!r.ok)throw new Error(`Server ${r.status}`);
    if(!r.body)throw new Error("No stream");
    const reader=r.body.getReader(),decoder=new TextDecoder();let buf="",full="";
    function processEV(ev){
      if(!ev.trim())return;let evn="message",data=[];
      ev.split(/\r?\n/).forEach(l=>{if(!l||l[0]===":")return;if(l.startsWith("event:"))evn=l.slice(6).trim();else if(l.startsWith("data:"))data.push(l.slice(5).replace(/^ /,""))});
      if(!data.length)return;let payload;try{payload=JSON.parse(data.join("\n"))}catch{return}
      switch(evn){
        case"token":const t=payload?.text??"";if(t){full+=t;ai?.querySelector(".msg-content")&&(ai.querySelector(".msg-content").innerHTML=renderAI(full));scrollChatToBottom()}break;
        case"chat_id":if(payload?.chat_id)currentChatId=payload.chat_id;break;
        case"done":if(payload?.chat_id)currentChatId=payload.chat_id;loadSidebar();break;
        case"error":throw new Error(payload?.message||"Error")
      }
    }
    const pump=async()=>{const{value,done}=await reader.read();if(done){buf+=decoder.decode();if(buf.trim())processEV(buf);return}buf+=decoder.decode(value,{stream:!0});buf=buf.replace(/\r\n/g,"\n");const parts=buf.split("\n\n");buf=parts.pop()||"";parts.forEach(processEV);await pump()};
    await pump()
  }catch(e){
    if(e.name==="AbortError"){ai?.querySelector(".msg-content")&&(ai.querySelector(".msg-content").innerHTML="<i>*Stopped*</i>");return}
    console.error(e);ai?.querySelector(".msg-content")&&(ai.querySelector(".msg-content").innerHTML=renderAI(`**Error**\n\n${e.message}`))
  }finally{setSendingState(!1);isSending=!1;controller=null}
  }
