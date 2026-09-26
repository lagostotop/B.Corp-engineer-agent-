"use strict";

const $=id=>document.getElementById(id);
const qs=(s,e=document)=>e.querySelector(s);
const qsa=(s,e=document)=>[...e.querySelectorAll(s)];

const S={
chats:[],current:null,messages:[],loading:false,controller:null,
files:[],renameId:null,enter:true,actions:true
};

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const md=s=>{
try{return window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(String(s||""))):esc(s).replace(/\n/g,"<br>")}
catch{return esc(s).replace(/\n/g,"<br>")}
};

function toast(m){
const t=$("toast");if(!t)return;
t.textContent=m;t.classList.add("show");
clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("show"),2200);
}

function closePop(){qsa(".popup").forEach(x=>x.classList.remove("show"))}
function modal(id,on=true){$(id)?.classList.toggle("show",on)}
function auth(){return window.BrainAuth?.isAuthenticated?.()===true}
function needAuth(){if(auth())return true;modal("authModal",true);return false}

async function af(url,o={}){
if(window.BrainAuth?.fetchWithAuth)return BrainAuth.fetchWithAuth(url,o);
return fetch(url,{credentials:"include",...o});
}

async function jf(url,o={}){
const r=await af(url,{...o,headers:{Accept:"application/json",...(o.headers||{})}});
let d={};try{d=await r.json()}catch{}
if(!r.ok)throw Error(d?.error?.message||d?.error||d?.message||`Request failed (${r.status})`);
return d;
}

function connection(ok){
const x=$("connection");
if(x){x.innerHTML=`<i></i>${ok?"Online":"Offline"}`;x.classList.toggle("offline",!ok)}
}

function resize(){
const x=$("messageInput");
if(x){x.style.height="auto";x.style.height=Math.min(x.scrollHeight,180)+"px"}
}

function scroll(){
requestAnimationFrame(()=>{
const x=$("chatContainer");
if(x)x.scrollTop=x.scrollHeight;
});
}

function welcome(){
if(S.messages.length)return;
const b=$("messages");
if(b)b.innerHTML=`<div id="welcome" class="welcome"><div class="welcome-logo"><img src="/static/logo.png" alt="B"></div><h1>What can I help with?</h1><p>Ask Brain 3.0 to explain, create, analyze, code, research, or solve a problem.</p><div class="suggestions"><button class="suggestion" data-prompt="Explain a difficult concept to me simply." type="button"><b>Learn something</b><small>Understand a difficult topic</small></button><button class="suggestion" data-prompt="Help me solve a technical problem step by step." type="button"><b>Solve a problem</b><small>Work through a challenge</small></button><button class="suggestion" data-prompt="Help me write clean production-quality code." type="button"><b>Write code</b><small>Build or debug software</small></button><button class="suggestion" data-prompt="Help me brainstorm a new idea." type="button"><b>Brainstorm</b><small>Develop an idea</small></button></div></div>`;
}

function actions(i,u){
if(!S.actions)return"";
return`<div class="message-actions">${u?`<button type="button" data-action="edit" data-index="${i}">✎ Edit</button>`:""}<button type="button" data-action="copy" data-index="${i}">⧉ Copy</button>${u?"":`<button type="button" data-action="regenerate" data-index="${i}">↻ Regenerate</button>`}</div>`;
}

function addMessage(m,i){
const e=document.createElement("article"),u=m.role==="user",t=m.content??m.message??"";
e.className=`message ${u?"user":"assistant"}`;
e.dataset.index=i;
e.innerHTML=u?
`<div class="message-content">${esc(t).replace(/\n/g,"<br>")}${actions(i,true)}</div><div class="message-avatar">U</div>`:
`<div class="message-avatar"><img src="/static/logo.png" alt=""></div><div class="message-content">${md(t)}${actions(i,false)}</div>`;
$("messages")?.appendChild(e);
}

function render(){
const b=$("messages");if(!b)return;
b.innerHTML="";
if(!S.messages.length){welcome();return}
S.messages.forEach(addMessage);
scroll();
}

function renderChats(){
const l=$("chatList");if(!l)return;
const term=($("chatSearch")?.value||"").toLowerCase();
const a=S.chats.filter(c=>(c.title||"New Chat").toLowerCase().includes(term));
l.innerHTML="";
if($("emptyHistory"))$("emptyHistory").style.display=a.length?"none":"block";
a.forEach(c=>{
const e=document.createElement("div");
e.className="chat-item"+(String(c.id)===String(S.current?.id)?" active":"");
e.innerHTML=`<span class="chat-title">${esc(c.title||"New Chat")}</span><button class="chat-more" type="button">⋯</button>`;
e.onclick=x=>{if(!x.target.closest(".chat-more"))openChat(c.id)};
qs(".chat-more",e).onclick=x=>{x.stopPropagation();chatMenu(c.id,x.currentTarget)};
l.appendChild(e);
});
}

async function loadChats(){
if(!auth()){S.chats=[];renderChats();return}
try{
const d=await jf("/api/chats?limit=100");
S.chats=Array.isArray(d)?d:(d.chats||d.data||[]);
renderChats();connection(true);
}catch(e){console.error(e);connection(false)}
}

async function openChat(id){
if(!needAuth())return;
closePop();
try{
const d=await jf(`/api/chats/${encodeURIComponent(id)}`);
S.current={...(S.chats.find(c=>String(c.id)===String(id))||{}),id};
S.messages=Array.isArray(d)?d:(d.messages||d.data||[]);
render();renderChats();closeSidebar();
}catch(e){toast(e.message||"Could not load chat")}
}

function newChat(){
closePop();
S.current=null;S.messages=[];S.files=[];
renderFiles();
$("messageInput").value="";
resize();render();renderChats();
$("messageInput")?.focus();
}

function renderFiles(){
const p=$("filePreview");if(!p)return;
p.innerHTML="";
S.files.forEach((f,i)=>{
const e=document.createElement("div");
e.className="file-chip";
e.innerHTML=`${esc(f.name)}<button type="button">×</button>`;
e.querySelector("button").onclick=()=>{
S.files.splice(i,1);renderFiles();
};
p.appendChild(e);
});
}

async function copy(t){
try{await navigator.clipboard.writeText(String(t||""));toast("Copied")}
catch{toast("Copy failed")}
}

function edit(i){
const m=S.messages[i];
if(!m||m.role!=="user")return;
$("messageInput").value=m.content||"";
S.messages=S.messages.slice(0,i);
render();resize();$("messageInput")?.focus();
}

async function regenerate(i){
if(S.loading)return;
const u=[...S.messages.slice(0,i)].reverse().find(x=>x.role==="user");
if(!u)return;
S.messages=S.messages.slice(0,i);
render();
await send(u.content,true);
}

function chatMenu(id,t){
const p=$("contextMenu");if(!p)return;
S.renameId=id;
p.innerHTML=`<button data-c="rename" type="button">✎ Rename</button><button data-c="share" type="button">↗ Share</button><button data-c="delete" type="button">🗑 Delete</button>`;
p.classList.add("show");
const r=t.getBoundingClientRect();
p.style.left=Math.min(innerWidth-(p.offsetWidth||160)-10,r.left)+"px";
p.style.top=Math.min(innerHeight-(p.offsetHeight||100)-10,r.bottom+5)+"px";

p.querySelector("[data-c=rename]").onclick=()=>{
closePop();
$("renameInput").value=S.chats.find(c=>String(c.id)===String(id))?.title||"New Chat";
modal("renameModal",true);
};

p.querySelector("[data-c=share]").onclick=()=>share(id);
p.querySelector("[data-c=delete]").onclick=()=>delChat(id);
}

async function rename(){
const id=S.renameId,title=$("renameInput")?.value.trim();
if(!id||!title)return;
try{
await jf(`/api/chats/${encodeURIComponent(id)}`,{
method:"PATCH",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({title})
});
const c=S.chats.find(x=>String(x.id)===String(id));
if(c)c.title=title;
modal("renameModal",false);renderChats();toast("Chat renamed");
}catch(e){toast(e.message)}
}

async function delChat(id){
closePop();
if(!confirm("Delete this conversation?"))return;
try{
await jf(`/api/chats/${encodeURIComponent(id)}`,{method:"DELETE"});
S.chats=S.chats.filter(c=>String(c.id)!==String(id));
if(String(S.current?.id)===String(id)){
S.current=null;S.messages=[];render();
}
renderChats();toast("Chat deleted");
}catch(e){toast(e.message)}
}

async function share(id=S.current?.id){
if(!id)return toast("Open a conversation first");
try{
await navigator.clipboard.writeText(`${location.origin}/?chat=${encodeURIComponent(id)}`);
toast("Chat link copied");
}catch{toast("Could not copy link")}
}

async function send(text,regen=false){
if(!needAuth()||S.loading)return;
text=String(text??$("messageInput")?.value||"").trim();
if(!text)return;

S.loading=true;
const sb=$("sendButton");
if(sb)sb.textContent="■";
if(!regen&&$("messageInput"))$("messageInput").value="";
resize();

S.messages.push({role:"user",content:text});
const a={role:"assistant",content:""};
S.messages.push(a);
render();

const i=S.messages.length-1;
const el=qs(`.message[data-index="${i}"] .message-content`);
if(el)el.innerHTML=`<div class="generating"><i></i><i></i><i></i><span>Thinking...</span></div>`;

try{
const f=new FormData();
f.append("question",text);
f.append("client_msg_id",crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`);
f.append("mode","normal");
if(S.current?.id)f.append("chat_id",S.current.id);
if(regen)f.append("is_regen","1");
if(S.files[0])f.append("file",S.files[0],S.files[0].name);

S.controller=new AbortController();

const r=await af("/api/chat",{
method:"POST",
body:f,
signal:S.controller.signal,
headers:{Accept:"text/event-stream"}
});

if(!r.ok){
let d={};try{d=await r.json()}catch{}
throw Error(d?.error?.message||d?.error||d?.message||`Brain request failed (${r.status})`);
}

if(!r.body)throw Error("Brain returned no response stream.");
await stream(r,el,i);
connection(true);

}catch(e){
if(e.name==="AbortError"){
a.content=a.content||"Generation stopped.";
if(el)el.innerHTML=md(a.content)+actions(i,false);
}else{
console.error(e);
if(el)el.innerHTML=`<div class="error-box">⚠ ${esc(e.message||"Brain generation failed.")}<br><button data-retry type="button">Try again</button></div>`;
el?.querySelector("[data-retry]")?.addEventListener("click",()=>{
S.messages.splice(i,1);render();send(text,regen);
});
connection(false);
}
}finally{
S.loading=false;
S.controller=null;
if(sb)sb.textContent="↑";
scroll();
loadChats();
}
}

async function stream(r,node,i){
const rd=r.body.getReader(),dec=new TextDecoder();
let buf="",event="",data="";

const handle=x=>{
if(!x)return;
let d;
try{d=JSON.parse(x)}catch{d={text:x}};

if(event==="token"||event==="message"||event==="content"){
S.messages[i].content+=d.text??d.token??d.content??"";
if(node)node.innerHTML=md(S.messages[i].content)+actions(i,false);
scroll();
}else if(event==="chat_id"){
const id=d.chat_id||d.id;
if(id)S.current={...(S.current||{}),id};
}else if(event==="error"){
throw Error(d.message||d.error||"Brain generation failed.");
}else if(event==="done"&&d.chat_id){
S.current={...(S.current||{}),id:d.chat_id};
}
};

while(true){
const{value,done}=await rd.read();
if(done)break;
buf+=dec.decode(value,{stream:true});
const lines=buf.split(/\r?\n/);
buf=lines.pop()||"";
for(const line of lines){
if(line.startsWith("event:"))event=line.slice(6).trim();
else if(line.startsWith("data:"))data+=line.slice(5).trim();
else if(!line){
if(data){handle(data);data=""}
event="";
}
}
}

buf+=dec.decode();
if(data)handle(data);
if(!S.messages[i]?.content?.trim())throw Error("Brain returned an empty response.");
if(node)node.innerHTML=md(S.messages[i].content)+actions(i,false);
}

function stop(){S.controller?.abort()}

function closeSidebar(){
$("sidebar")?.classList.remove("open");
$("sidebarBackdrop")?.classList.remove("show");
}

function openSidebar(){
$("sidebar")?.classList.add("open");
$("sidebarBackdrop")?.classList.add("show");
}

document.addEventListener("click",e=>{
const a=e.target.closest("[data-action]");
if(a){
const i=+a.dataset.index;
if(a.dataset.action==="copy")copy(S.messages[i]?.content);
else if(a.dataset.action==="edit")edit(i);
else if(a.dataset.action==="regenerate")regenerate(i);
return;
}

const s=e.target.closest("[data-prompt]");
if(s){
$("messageInput").value=s.dataset.prompt;
resize();$("messageInput").focus();
return;
}

const tool=e.target.closest("[data-tool]");
if(tool){
closePop();
if(tool.dataset.tool==="file")$("fileInput")?.click();
else if(tool.dataset.tool==="image"){
const f=$("fileInput");
if(f){
f.accept="image/*";
f.click();
setTimeout(()=>f.accept="",100);
}
}else toast("Code mode is coming soon");
}
});

async function boot(){
console.log("Brain 3.0 frontend booting...");
console.log("BrainAuth:",window.BrainAuth);
console.log("BrainAuth.init:",typeof window.BrainAuth?.init);

try{
if(!window.BrainAuth||typeof BrainAuth.init!=="function")throw Error("Authentication module did not load correctly.");
await BrainAuth.init();
BrainAuth.onAuthStateChange(()=>loadChats());
}catch(e){
console.error("Authentication startup error:",e);
toast("Authentication error: "+e.message);
}

render();
await loadChats();
resize();

$("newChat")?.addEventListener("click",newChat);
$("clearChat")?.addEventListener("click",newChat);

$("sendButton")?.addEventListener("click",()=>S.loading?stop():send());

$("messageInput")?.addEventListener("input",resize);
$("messageInput")?.addEventListener("keydown",e=>{
if(e.key==="Enter"&&!e.shiftKey&&S.enter){
e.preventDefault();
send();
}
});

$("chatSearch")?.addEventListener("input",renderChats);

$("addButton")?.addEventListener("click",e=>{
e.stopPropagation();
$("toolsMenu")?.classList.toggle("show");
$("modelMenu")?.classList.remove("show");
$("moreMenu")?.classList.remove("show");
});

$("modelButton")?.addEventListener("click",()=>{
$("modelMenu")?.classList.toggle("show");
$("toolsMenu")?.classList.remove("show");
$("moreMenu")?.classList.remove("show");
});

$("moreButton")?.addEventListener("click",()=>{
$("moreMenu")?.classList.toggle("show");
$("modelMenu")?.classList.remove("show");
$("toolsMenu")?.classList.remove("show");
});

$("openSidebar")?.addEventListener("click",openSidebar);
$("closeSidebar")?.addEventListener("click",closeSidebar);
$("sidebarBackdrop")?.addEventListener("click",closeSidebar);

$("settingsBtn")?.addEventListener("click",()=>modal("settingsModal",true));
$("saveRename")?.addEventListener("click",rename);
$("shareChat")?.addEventListener("click",()=>share());

$("fileInput")?.addEventListener("change",e=>{
S.files=[...(e.target.files||[])];
renderFiles();
});

$("enterToggle")?.addEventListener("change",e=>S.enter=e.target.checked);

$("actionsToggle")?.addEventListener("change",e=>{
S.actions=e.target.checked;
render();
});

$("authBtn")?.addEventListener("click",async()=>{
if(auth()){
try{
await BrainAuth.signOut();
S.current=null;S.messages=[];
render();await loadChats();toast("Signed out");
}catch(e){toast(e.message)}
}else modal("authModal",true);
});

$("loginSubmit")?.addEventListener("click",async()=>{
try{
await BrainAuth.signIn($("authEmail").value,$("authPassword").value);
modal("authModal",false);
await loadChats();
render();
toast("Logged in");
}catch(e){
$("authError").textContent=e.message;
}
});

$("signupSubmit")?.addEventListener("click",async()=>{
try{
await BrainAuth.signUp($("authEmail").value,$("authPassword").value);
modal("authModal",false);
await loadChats();
render();
toast("Account created");
}catch(e){
$("authError").textContent=e.message;
}
});

qsa("[data-close]").forEach(x=>x.addEventListener("click",()=>modal(x.dataset.close,false)));

qsa(".modal").forEach(x=>x.addEventListener("click",e=>{
if(e.target===x)x.classList.remove("show");
}));

console.log("Brain 3.0 frontend ready.");
}

if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);
else boot();