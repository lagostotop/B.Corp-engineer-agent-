"use strict";
const $=id=>document.getElementById(id),qs=(s,e=document)=>e.querySelector(s),qsa=(s,e=document)=>[...e.querySelectorAll(s)];
const state={chats:[],current:null,messages:[],loading:false,controller:null,files:[],renameId:null,enterToSend:true,showActions:true};

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const markdown=s=>{try{return window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(String(s||""))):esc(s).replace(/\n/g,"<br>")}catch{return esc(s).replace(/\n/g,"<br>")}};
const toast=m=>{const t=$("toast");if(!t)return;t.textContent=m;t.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("show"),2200)};
const closePopups=()=>qsa(".popup").forEach(x=>x.classList.remove("show"));
const showModal=id=>$(id)?.classList.add("show"),hideModal=id=>$(id)?.classList.remove("show");
const scrollBottom=()=>requestAnimationFrame(()=>{const c=$("chatContainer");if(c)c.scrollTop=c.scrollHeight});

async function authFetch(url,opt={}){if(window.BrainAuth?.fetchWithAuth)return BrainAuth.fetchWithAuth(url,opt);return fetch(url,{credentials:"include",...opt})}
async function jsonFetch(url,opt={}){const r=await authFetch(url,{...opt,headers:{Accept:"application/json",...(opt.headers||{})}});let d=null;try{d=await r.json()}catch{}if(!r.ok)throw Error(d?.error?.message||d?.error||d?.message||`Request failed (${r.status})`);return d}
function setConnection(ok){const c=$("connection");if(!c)return;c.innerHTML=`<i></i> ${ok?"Online":"Offline"}`;c.classList.toggle("offline",!ok)}

function requireAuth(){if(BrainAuth?.isAuthenticated())return true;openAuth();return false}

function openAuth(){const m=$("authModal");if(!m)return;m.classList.add("show");$("authEmail")?.focus()}
function authError(x){const e=$("authError");if(e)e.textContent=x||""}

function renderWelcome(){if(state.messages.length)return;const b=$("messages");if(!b)return;b.innerHTML=`<div id="welcome" class="welcome"><h1>What can I help with?</h1><p>Ask Brain 3.0 to explain, create, analyze, code, research, or solve a problem.</p><div class="suggestions"><button class="suggestion" data-prompt="Explain a difficult concept to me simply."><b>Learn something</b><small>Understand a difficult topic</small></button><button class="suggestion" data-prompt="Help me solve a technical problem step by step."><b>Solve a problem</b><small>Work through a challenge</small></button><button class="suggestion" data-prompt="Help me write clean production-quality code."><b>Write code</b><small>Build or debug software</small></button><button class="suggestion" data-prompt="Help me brainstorm a new idea."><b>Brainstorm</b><small>Develop an idea</small></button></div></div>`;qsa(".suggestion").forEach(x=>x.onclick=()=>{$("messageInput").value=x.dataset.prompt;autoResize();$("messageInput").focus()})}

function renderChats(){const list=$("chatList");if(!list)return;const q=($("chatSearch")?.value||"").toLowerCase().trim();list.innerHTML="";const chats=state.chats.filter(c=>(c.title||"New Chat").toLowerCase().includes(q));$("emptyHistory").style.display=chats.length?"none":"block";chats.forEach(c=>{const e=document.createElement("div");e.className="chat-item"+(String(c.id)===String(state.current?.id)?" active":"");e.innerHTML=`<span class="chat-title">${esc(c.title||"New Chat")}</span><button class="chat-more">⋯</button>`;e.onclick=x=>{if(!x.target.closest(".chat-more"))openChat(c.id)};qs(".chat-more",e).onclick=x=>{x.stopPropagation();openChatMenu(c.id,x.currentTarget)};list.appendChild(e)})}

async function loadChats(){if(!BrainAuth?.isAuthenticated()){state.chats=[];renderChats();return}try{const d=await jsonFetch("/api/chats?limit=100");state.chats=Array.isArray(d)?d:(d?.chats||d?.data||[]);renderChats();setConnection(true)}catch(e){console.error("Chat list",e);setConnection(false)}}

async function openChat(id){if(!requireAuth())return;closePopups();try{const d=await jsonFetch(`/api/chats/${encodeURIComponent(id)}`);const c=state.chats.find(x=>String(x.id)===String(id))||d?.chat||{};state.current={...c,id};state.messages=Array.isArray(d)?d:(d?.messages||[]);renderMessages();renderChats();closeSidebar()}catch(e){toast(e.message||"Could not load conversation")}}

function renderMessages(){const b=$("messages");if(!b)return;b.innerHTML="";if(!state.messages.length){renderWelcome();return}state.messages.forEach((m,i)=>renderMessage(m,i));scrollBottom()}

function renderMessage(m,i){const role=m.role==="user"?"user":"assistant",text=m.content??m.message??"",e=document.createElement("article");e.className=`message ${role}`;e.dataset.index=i;if(role==="user")e.innerHTML=`<div class="message-content">${esc(text).replace(/\n/g,"<br>")}${state.showActions?`<div class="message-actions"><button data-a="edit">✎ Edit</button><button data-a="copy">⧉ Copy</button></div>`:""}</div><div class="message-avatar">U</div>`;else e.innerHTML=`<div class="message-avatar"><img src="/static/logo.png" alt=""></div><div class="message-content">${markdown(text)}${state.showActions?`<div class="message-actions"><button data-a="copy">⧉ Copy</button><button data-a="regenerate">↻ Regenerate</button></div>`:""}</div>`;$(`[data-a="copy"]`,e)?.addEventListener("click",()=>copyText(text));$(`[data-a="edit"]`,e)?.addEventListener("click",()=>editMessage(i));$(`[data-a="regenerate"]`,e)?.addEventListener("click",()=>regenerate(i));$("messages").appendChild(e)}

async function copyText(x){try{await navigator.clipboard.writeText(String(x));toast("Copied")}catch{toast("Copy failed")}}

function editMessage(i){const m=state.messages[i];if(!m||m.role!=="user")return;$("messageInput").value=m.content||"";state.messages=state.messages.slice(0,i);renderMessages();autoResize();$("messageInput").focus()}

async function regenerate(i){if(state.loading||!requireAuth())return;const u=[...state.messages.slice(0,i)].reverse().find(m=>m.role==="user");if(!u)return;state.messages=state.messages.slice(0,i);renderMessages();await sendMessage(u.content,true)}

function positionPopup(p,t){p.classList.add("show");p.style.visibility="hidden";const r=t.getBoundingClientRect(),w=p.offsetWidth||190,h=p.offsetHeight||150;p.style.left=Math.min(innerWidth-w-10,Math.max(10,r.left))+"px";p.style.top=Math.min(innerHeight-h-10,r.bottom+5)+"px";p.style.visibility=""}

function openChatMenu(id,target){const p=$("contextMenu");if(!p)return;state.renameId=id;p.innerHTML=`<button data-c="rename">✎ Rename</button><button data-c="share">↗ Share</button><button data-c="delete">🗑 Delete</button>`;positionPopup(p,target);p.querySelector("[data-c=rename]").onclick=()=>{closePopups();const c=state.chats.find(x=>String(x.id)===String(id));$("renameInput").value=c?.title||"New Chat";showModal("renameModal");setTimeout(()=>$("renameInput")?.focus(),50)};p.querySelector("[data-c=share]").onclick=()=>shareChat(id);p.querySelector("[data-c=delete]").onclick=()=>deleteChat(id)}

async function renameChat(){const id=state.renameId,title=$("renameInput").value.trim();if(!id||!title)return;try{const d=await jsonFetch(`/api/chats/${encodeURIComponent(id)}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({title})});const c=state.chats.find(x=>String(x.id)===String(id));if(c)c.title=d?.chat?.title||title;if(state.current?.id===id)state.current.title=title;hideModal("renameModal");renderChats();toast("Chat renamed")}catch(e){toast(e.message||"Rename failed")}}

async function deleteChat(id){closePopups();if(!confirm("Delete this conversation?"))return;try{await jsonFetch(`/api/chats/${encodeURIComponent(id)}`,{method:"DELETE"});state.chats=state.chats.filter(c=>String(c.id)!==String(id));if(String(state.current?.id)===String(id)){state.current=null;state.messages=[];renderWelcome()}renderChats();toast("Chat deleted")}catch(e){toast(e.message||"Delete failed")}}

async function shareChat(){if(!state.current)return toast("Open a conversation first");try{await navigator.clipboard.writeText(location.origin+"/?chat="+encodeURIComponent(state.current.id));toast("Chat link copied")}catch{toast("Could not copy link")}}

function createChat(){closePopups();state.current=null;state.messages=[];state.files=[];$("filePreview").innerHTML="";$("messageInput").value="";renderWelcome();renderChats();$("messageInput").focus()}

function autoResize(){const x=$("messageInput");if(!x)return;x.style.height="auto";x.style.height=Math.min(x.scrollHeight,180)+"px"}

async function sendMessage(text,regen=false){if(!requireAuth()||state.loading)return;text=String(text??$("messageInput").value).trim();if(!text)return;state.loading=true;$("sendButton").textContent="■";if(!regen)$("messageInput").value="";autoResize();state.messages.push({role:"user",content:text});renderMessages();const a={role:"assistant",content:""};state.messages.push(a);const i=state.messages.length-1;renderMessage(a,i);const node=qs(`.message[data-index="${i}"] .message-content`);if(node)node.innerHTML=`<div class="generating"><i></i><i></i><i></i><span>Thinking...</span></div>`;scrollBottom();try{const f=new FormData();f.append("question",text);f.append("client_msg_id",crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`);f.append("mode","normal");if(state.current?.id)f.append("chat_id",state.current.id);if(regen)f.append("is_regen","1");if(state.files[0])f.append("file",state.files[0],state.files[0].name);state.controller=new AbortController();const r=await authFetch("/api/chat",{method:"POST",body:f,signal:state.controller.signal,headers:{Accept:"text/event-stream"}});if(!r.ok){let d={};try{d=await r.json()}catch{}throw Error(d?.error?.message||d?.error||d?.message||`Brain request failed (${r.status})`)}await readSSE(r,node,i);setConnection(true)}catch(e){if(e.name==="AbortError"){a.content="Generation stopped.";if(node)node.innerHTML="Generation stopped."}else{console.error(e);if(node)node.innerHTML=`<div class="error-box">⚠ ${esc(e.message||"Brain generation failed")}<br><button data-retry>Try again</button></div>`;node?.querySelector("[data-retry]")?.addEventListener("click",()=>{state.messages.splice(i,1);renderMessages();sendMessage(text,regen)});setConnection(false)}}finally{state.loading=false;state.controller=null;$("sendButton").textContent="↑";scrollBottom();await loadChats()}}

async function readSSE(response,node,index){const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="",event="",data="";const process=async()=>{const lines=buffer.split(/\r?\n/);buffer=lines.pop()||"";for(const line of lines){if(line.startsWith("event:"))event=line.slice(6).trim();else if(line.startsWith("data:"))data+=line.slice(5).trim();else if(line===""){if(data){let d={};try{d=JSON.parse(data)}catch{}if(event==="token"){state.messages[index].content+=d.text||"";if(node)node.innerHTML=markdown(state.messages[index].content)+actionsHTML(index,false)}else if(event==="error")throw Error(d.message||"Brain generation failed.");else if(event==="chat_id"){if(d.chat_id&&!state.current)state.current={id:d.chat_id};if(d.chat_id)state.current={...(state.current||{}),id:d.chat_id}}}event="";data=""}}};while(true){const{x,done}=await reader.read();if(done)break;buffer+=decoder.decode(x,{stream:true});await process()}buffer+="\n";await process();if(!state.messages[index].content)throw Error("Brain returned an empty response.")}
function actionsHTML(i,user){return state.showActions?`<div class="message-actions"><button data-action-copy="${i}">⧉ Copy</button>${!user?`<button data-action-regenerate="${i}">↻ Regenerate</button>`:""}</div>`:""}

function attachDynamicActions(){qsa("[data-action-copy]").forEach(b=>b.onclick=()=>copyText(state.messages[+b.dataset.actionCopy]?.content||""));qsa("[data-action-regenerate]").forEach(b=>b.onclick=()=>regenerate(+b.dataset.actionRegenerate))}

function stopGeneration(){state.controller?.abort()}

function renderFiles(){const p=$("filePreview");p.innerHTML="";state.files.forEach((f,i)=>{const e=document.createElement("div");e.className="file-chip";e.innerHTML=`${esc(f.name)} <button>×</button>`;e.querySelector("button").onclick=()=>{state.files.splice(i,1);renderFiles()};p.appendChild(e)})}

function closeSidebar(){$("sidebar").classList.remove("open");$("sidebarBackdrop").classList.remove("show")}
function openSidebar(){$("sidebar").classList.add("open");$("sidebarBackdrop").classList.add("show")}

document.addEventListener("DOMContentLoaded",async()=>{await BrainAuth.init();BrainAuth.onAuthStateChange(async()=>{await loadChats()});await loadChats();renderWelcome();

$("newChat").onclick=createChat;$("clearChat").onclick=createChat;$("sendButton").onclick=()=>state.loading?stopGeneration():sendMessage();$("messageInput").addEventListener("input",autoResize);$("messageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&state.enterToSend){e.preventDefault();sendMessage()}});$("chatSearch").addEventListener("input",renderChats);$("addButton").onclick=()=>{closePopups();$("toolsMenu").classList.toggle("show")};$("voiceButton").onclick=()=>toast("Voice input coming soon");$("modelButton").onclick=()=>{$("modelMenu").classList.toggle("show");$("moreMenu").classList.remove("show")};$("moreButton").onclick=()=>{$("moreMenu").classList.toggle("show");$("modelMenu").classList.remove("show")};$("openSidebar").onclick=openSidebar;$("closeSidebar").onclick=closeSidebar;$("sidebarBackdrop").onclick=closeSidebar;$("settingsBtn").onclick=()=>showModal("settingsModal");$("authBtn").onclick=async()=>{if(BrainAuth.isAuthenticated()){await BrainAuth.signOut();toast("Signed out");await loadChats()}else openAuth()};$("saveRename").onclick=renameChat;

qsa("[data-close]").forEach(b=>b.onclick=()=>hideModal(b.dataset.close));qsa(".modal").forEach(m=>m.addEventListener("click",e=>{if(e.target===m)m.classList.remove("show")}));

$("loginSubmit").onclick=async()=>{authError("");try{await BrainAuth.signIn($("authEmail").value,$("authPassword").value);hideModal("authModal");toast("Logged in");await loadChats()}catch(e){authError(e.message||"Login failed")}};
$("signupSubmit").onclick=async()=>{authError("");try{const d=await BrainAuth.signUp($("authEmail").value,$("authPassword").value);if(!d.session)authError("Account created. Check your email to confirm your account.");else{hideModal("authModal");toast("Account created");await loadChats()}}catch(e){authError(e.message||"Signup failed")}};

$("enterToggle").onchange=e=>state.enterToSend=e.target.checked;$("actionsToggle").onchange=e=>{state.showActions=e.target.checked;renderMessages()};

qsa("#toolsMenu button").forEach(b=>b.onclick=()=>{const t=b.dataset.tool;if(t==="file"||t==="image")$("fileInput").click();else toast(`${b.textContent.trim()} coming soon`);closePopups()});
$("fileInput").onchange=e=>{state.files=[...(e.target.files||[])];renderFiles();e.target.value=""};

document.addEventListener("click",e=>{if(!e.target.closest(".popup")&&!e.target.closest("#addButton")&&!e.target.closest("#modelButton")&&!e.target.closest("#moreButton"))closePopups()});
});

const _renderMessage=renderMessage;
const oldRenderMessages=renderMessages;
renderMessages=function(){oldRenderMessages();attachDynamicActions()};