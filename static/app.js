"use strict";

const $=id=>document.getElementById(id);
const q=(s,e=document)=>e.querySelector(s);
const qa=(s,e=document)=>[...e.querySelectorAll(s)];

const S={messages:[],chats:[],current:null,loading:false,controller:null,enter:true,actions:true};

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const md=s=>{
try{return window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(String(s||""))):esc(s).replace(/\n/g,"<br>")}
catch{return esc(s).replace(/\n/g,"<br>")}
};

function toast(text){
const x=$("toast");if(!x)return;
x.textContent=text;x.classList.add("show");
clearTimeout(window.__toast);window.__toast=setTimeout(()=>x.classList.remove("show"),2200)
}

function modal(id,on=true){$(id)?.classList.toggle("show",on)}

function auth(){return window.BrainAuth?.isAuthenticated?.()===true}

function needAuth(){
if(auth())return true;
modal("authModal",true);
return false
}

async function api(url,opt={}){
const r=await BrainAuth.fetchWithAuth(url,{credentials:"include",...opt});
let d={};try{d=await r.json()}catch{}
if(!r.ok)throw Error(d?.error||d?.message||`Request failed (${r.status})`);
return d
}

function connection(ok=true){
const x=$("connection");
if(x){x.innerHTML=`<i></i>${ok?"Online":"Offline"}`;x.classList.toggle("offline",!ok)}
}

function resize(){
const x=$("messageInput");
if(x){x.style.height="auto";x.style.height=Math.min(x.scrollHeight,180)+"px"}
}

function scrollBottom(){
requestAnimationFrame(()=>{
const x=$("chatContainer");if(x)x.scrollTop=x.scrollHeight
})
}

function welcome(){
const b=$("messages");if(!b)return;
b.innerHTML=`<div id="welcome" class="welcome">
<div class="welcome-logo"><img src="/static/logo.png" alt="B"></div>
<h1>What can I help with?</h1>
<p>Ask Brain 3.0 to explain, create, analyze, code, research, or solve a problem.</p>
<div class="suggestions">
<button class="suggestion" data-prompt="Explain a difficult concept to me simply." type="button"><b>Learn something</b><small>Understand a difficult topic</small></button>
<button class="suggestion" data-prompt="Help me solve a technical problem step by step." type="button"><b>Solve a problem</b><small>Work through a challenge</small></button>
<button class="suggestion" data-prompt="Help me write clean production-quality code." type="button"><b>Write code</b><small>Build or debug software</small></button>
<button class="suggestion" data-prompt="Help me brainstorm a new idea." type="button"><b>Brainstorm</b><small>Develop an idea</small></button>
</div></div>`
}

function render(){
const b=$("messages");if(!b)return;
b.innerHTML="";
if(!S.messages.length){welcome();return}
S.messages.forEach((m,i)=>{
const e=document.createElement("article"),user=m.role==="user";
e.className=`message ${user?"user":"assistant"}`;
e.dataset.index=i;
e.innerHTML=user?
`<div class="message-content">${esc(m.content).replace(/\n/g,"<br>")}${S.actions?`<div class="message-actions"><button data-action="edit" data-index="${i}" type="button">✎ Edit</button><button data-action="copy" data-index="${i}" type="button">⧉ Copy</button></div>`:""}</div><div class="message-avatar">U</div>`:
`<div class="message-avatar"><img src="/static/logo.png" alt=""></div><div class="message-content">${md(m.content)}${S.actions?`<div class="message-actions"><button data-action="copy" data-index="${i}" type="button">⧉ Copy</button><button data-action="regenerate" data-index="${i}" type="button">↻ Regenerate</button></div>`:""}</div>`
});
scrollBottom()
}

async function loadChats(){
if(!auth()){S.chats=[];renderChats();return}
try{
const d=await api("/api/chats?limit=100");
S.chats=Array.isArray(d)?d:(d.chats||d.data||[]);
renderChats();connection(true)
}catch(e){console.error(e);connection(false)}
}

function renderChats(){
const list=$("chatList");if(!list)return;
list.innerHTML="";
const search=($("chatSearch")?.value||"").toLowerCase();
const chats=S.chats.filter(c=>(c.title||"New Chat").toLowerCase().includes(search));
$("emptyHistory")&&($("emptyHistory").style.display=chats.length?"none":"block");
chats.forEach(c=>{
const e=document.createElement("div");
e.className="chat-item"+(String(c.id)===String(S.current?.id)?" active":"");
e.innerHTML=`<span class="chat-title">${esc(c.title||"New Chat")}</span><button class="chat-more" type="button">⋯</button>`;
e.onclick=x=>{if(!x.target.closest(".chat-more"))openChat(c.id)};
q(".chat-more",e).onclick=x=>{x.stopPropagation();openContext(c.id,x.currentTarget)};
list.appendChild(e)
})
}

async function openChat(id){
if(!needAuth())return;
try{
const d=await api(`/api/chats/${encodeURIComponent(id)}`);
S.current={...(S.chats.find(c=>String(c.id)===String(id))||{}),id};
S.messages=Array.isArray(d)?d:(d.messages||d.data||[]);
render();renderChats()
}catch(e){toast(e.message)}
}

function newChat(){
S.current=null;S.messages=[];$("messageInput").value="";resize();render();renderChats();$("messageInput").focus()
}

function openContext(id,target){
const p=$("contextMenu");if(!p)return;
p.innerHTML=`<button data-c="rename" type="button">✎ Rename</button><button data-c="delete" type="button">🗑 Delete</button>`;
p.classList.add("show");
const r=target.getBoundingClientRect();
p.style.left=Math.max(8,Math.min(innerWidth-170,r.left-130))+"px";
p.style.top=Math.min(innerHeight-100,r.bottom+5)+"px";
p.querySelector("[data-c=rename]").onclick=()=>{
p.classList.remove("show");
$("renameInput").value=S.chats.find(c=>String(c.id)===String(id))?.title||"New Chat";
S.renameId=id;modal("renameModal",true)
};
p.querySelector("[data-c=delete]").onclick=async()=>{
p.classList.remove("show");
if(!confirm("Delete this conversation?"))return;
try{
await api(`/api/chats/${encodeURIComponent(id)}`,{method:"DELETE"});
S.chats=S.chats.filter(c=>String(c.id)!==String(id));
if(String(S.current?.id)===String(id))newChat();
renderChats();toast("Chat deleted")
}catch(e){toast(e.message)}
}
}

async function renameChat(){
const id=S.renameId,title=$("renameInput")?.value.trim();
if(!id||!title)return;
try{
await api(`/api/chats/${encodeURIComponent(id)}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({title})});
const c=S.chats.find(x=>String(x.id)===String(id));if(c)c.title=title;
modal("renameModal",false);renderChats();toast("Chat renamed")
}catch(e){toast(e.message)}
}

async function send(){
if(!needAuth()||S.loading)return;
const input=$("messageInput"),text=input.value.trim();
if(!text)return;

S.loading=true;
$("sendButton").textContent="■";
input.value="";resize();

S.messages.push({role:"user",content:text});
const ai={role:"assistant",content:""};
S.messages.push(ai);
render();

const index=S.messages.length-1;
const node=q(`.message[data-index="${index}"] .message-content`);
if(node)node.innerHTML=`<div class="generating"><i></i><i></i><i></i><span>Thinking...</span></div>`;

try{
S.controller=new AbortController();

const body=new FormData();
body.append("question",text);
body.append("mode","normal");
if(S.current?.id)body.append("chat_id",S.current.id);

const r=await BrainAuth.fetchWithAuth("/api/chat",{
method:"POST",
body,
signal:S.controller.signal,
headers:{Accept:"text/event-stream"}
});

if(!r.ok){
let d={};try{d=await r.json()}catch{}
throw Error(d?.error||d?.message||`Brain generation failed (${r.status})`)
}

if(!r.body)throw Error("Brain returned no stream.");

await readStream(r,node,index);
connection(true);
}catch(e){
if(e.name==="AbortError"){
ai.content="Generation stopped.";
if(node)node.innerHTML=md(ai.content)
}else{
console.error(e);
ai.content="";
if(node)node.innerHTML=`<div class="error-box">⚠ ${esc(e.message||"Brain generation failed.")}<br><button data-retry type="button">Try again</button></div>`;
node?.querySelector("[data-retry]")?.addEventListener("click",()=>sendAgain(text))
}
}finally{
S.loading=false;S.controller=null;$("sendButton").textContent="↑";scrollBottom()
}
}

async function sendAgain(text){
if(S.loading)return;
S.messages.pop();S.messages.pop();render();
$("messageInput").value=text;
await send()
}

async function readStream(response,node,index){
const reader=response.body.getReader(),decoder=new TextDecoder();
let buffer="",event="",data="";

function process(raw){
if(!raw)return;
let d;
try{d=JSON.parse(raw)}catch{d={text:raw}};

if(event==="error")throw Error(d.message||d.error||"Brain generation failed.");

if(event==="token"||event==="message"||event==="content"){
S.messages[index].content+=d.text??d.token??d.content??"";
node.innerHTML=md(S.messages[index].content)+actionHtml(index,false);
scrollBottom()
}

if(event==="chat_id"){
const id=d.chat_id||d.id;
if(id)S.current={...(S.current||{}),id}
}
}

while(true){
const{value,done}=await reader.read();
if(done)break;
buffer+=decoder.decode(value,{stream:true});
const lines=buffer.split(/\r?\n/);
buffer=lines.pop()||"";

for(const line of lines){
if(line.startsWith("event:"))event=line.slice(6).trim();
else if(line.startsWith("data:"))data+=line.slice(5).trim();
else if(!line){
if(data){process(data);data=""}
event=""
}
}
}

if(data)process(data);
if(!S.messages[index].content.trim())throw Error("Brain returned an empty response.");
node.innerHTML=md(S.messages[index].content)+actionHtml(index,false)
}

function actionHtml(i,user){
if(!S.actions)return"";
return`<div class="message-actions">${user?`<button data-action="edit" data-index="${i}" type="button">✎ Edit</button>`:""}<button data-action="copy" data-index="${i}" type="button">⧉ Copy</button>${user?"":`<button data-action="regenerate" data-index="${i}" type="button">↻ Regenerate</button>`}</div>`
}

async function copyMessage(i){
try{await navigator.clipboard.writeText(S.messages[i]?.content||"");toast("Copied")}catch{toast("Copy failed")}
}

function editMessage(i){
const m=S.messages[i];if(!m)return;
$("messageInput").value=m.content||"";
S.messages=S.messages.slice(0,i);
render();resize();$("messageInput").focus()
}

async function regenerate(i){
const user=[...S.messages.slice(0,i)].reverse().find(x=>x.role==="user");
if(!user)return;
S.messages=S.messages.slice(0,i);
render();
$("messageInput").value=user.content;
await send()
}

function stop(){S.controller?.abort()}

function closeMenus(){qa(".popup").forEach(x=>x.classList.remove("show"))}

function bind(){
console.log("Brain 3.0 frontend booted");

$("newChat")?.addEventListener("click",newChat);
$("clearChat")?.addEventListener("click",newChat);

$("sendButton")?.addEventListener("click",()=>S.loading?stop():send());

$("messageInput")?.addEventListener("input",resize);
$("messageInput")?.addEventListener("keydown",e=>{
if(e.key==="Enter"&&!e.shiftKey&&S.enter){e.preventDefault();send()}
});

$("addButton")?.addEventListener("click",e=>{
e.stopPropagation();closeMenus();$("toolsMenu")?.classList.toggle("show")
});

$("modelButton")?.addEventListener("click",e=>{
e.stopPropagation();closeMenus();$("modelMenu")?.classList.toggle("show")
});

$("moreButton")?.addEventListener("click",e=>{
e.stopPropagation();closeMenus();$("moreMenu")?.classList.toggle("show")
});

$("settingsBtn")?.addEventListener("click",()=>modal("settingsModal",true));

$("chatSearch")?.addEventListener("input",renderChats);

$("saveRename")?.addEventListener("click",renameChat);

$("enterToggle")?.addEventListener("change",e=>S.enter=e.target.checked);

$("actionsToggle")?.addEventListener("change",e=>{
S.actions=e.target.checked;render()
});

$("openSidebar")?.addEventListener("click",()=>{
$("sidebar")?.classList.add("open");$("sidebarBackdrop")?.classList.add("show")
});

$("sidebarBackdrop")?.addEventListener("click",()=>{
$("sidebar")?.classList.remove("open");$("sidebarBackdrop")?.classList.remove("show")
});

$("authBtn")?.addEventListener("click",async()=>{
if(auth()){
try{await BrainAuth.signOut();S.messages=[];S.current=null;render();renderChats();toast("Signed out")}
catch(e){toast(e.message)}
}else modal("authModal",true)
});

$("loginSubmit")?.addEventListener("click",async()=>{
try{
await BrainAuth.signIn($("authEmail").value,$("authPassword").value);
modal("authModal",false);await loadChats();toast("Logged in")
}catch(e){$("authError").textContent=e.message}
});

$("signupSubmit")?.addEventListener("click",async()=>{
try{
await BrainAuth.signUp($("authEmail").value,$("authPassword").value);
modal("authModal",false);await loadChats();toast("Account created")
}catch(e){$("authError").textContent=e.message}
});

qa("[data-close]").forEach(x=>x.addEventListener("click",()=>modal(x.dataset.close,false)));

qa(".modal").forEach(x=>x.addEventListener("click",e=>{
if(e.target===x)x.classList.remove("show")
}));

document.addEventListener("click",e=>{
const action=e.target.closest("[data-action]");
if(action){
const i=Number(action.dataset.index);
if(action.dataset.action==="copy")copyMessage(i);
if(action.dataset.action==="edit")editMessage(i);
if(action.dataset.action==="regenerate")regenerate(i);
return
}

const prompt=e.target.closest("[data-prompt]");
if(prompt){
$("messageInput").value=prompt.dataset.prompt;
resize();$("messageInput").focus();return
}

const tool=e.target.closest("[data-tool]");
if(tool){
closeMenus();
if(tool.dataset.tool==="file"){$("fileInput").click();return}
if(tool.dataset.tool==="image"){$("fileInput").accept="image/*";$("fileInput").click();return}
toast("Code mode coming soon");return
}

if(!e.target.closest(".popup")&&!e.target.closest("#addButton")&&!e.target.closest("#modelButton")&&!e.target.closest("#moreButton"))closeMenus()
});
}

async function boot(){
try{
bind();
connection(true);
welcome();
resize();

if(!window.BrainAuth){
console.error("BrainAuth missing");
toast("Authentication script did not load.");
return
}

await BrainAuth.init();
await loadChats();

}catch(e){
console.error("Brain 3.0 boot error:",e);
toast("Frontend error: "+e.message)
}
}

if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);
else boot();