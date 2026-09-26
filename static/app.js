const $=id=>document.getElementById(id),qs=(s,e=document)=>e.querySelector(s),qsa=(s,e=document)=>[...e.querySelectorAll(s)];
const state={chats:[],current:null,messages:[],loading:false,controller:null,files:[],renameId:null,enterToSend:true,showActions:true};
const api=async(url,opt={})=>{const r=await fetch(url,{credentials:"include",...opt,headers:{"Content-Type":"application/json",...(opt.headers||{})}});let d=null;try{d=await r.json()}catch{}if(!r.ok)throw new Error(d?.error||d?.message||`Request failed (${r.status})`);return d};
const toast=m=>{const t=$("toast");t.textContent=m;t.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("show"),2200)};
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const markdown=s=>{try{return DOMPurify.sanitize(marked.parse(String(s||"")))}catch{return esc(s).replace(/\n/g,"<br>")}};
const closePopups=()=>qsa(".popup").forEach(x=>x.classList.remove("show"));
const scrollBottom=()=>{const c=$("chatContainer");requestAnimationFrame(()=>c.scrollTop=c.scrollHeight)};
const showModal=id=>$(id).classList.add("show");
const hideModal=id=>$(id).classList.remove("show");

function setConnection(ok=true){$("connection").innerHTML=`<i></i> ${ok?"Online":"Offline"}`;$("connection").classList.toggle("offline",!ok)}

function renderWelcome(){if(state.messages.length)return;$("messages").innerHTML=`<div id="welcome" class="welcome"><div class="welcome-logo"><img src="/static/logo.png" alt="Brain"></div><h1>What are you working on?</h1><p>Ask Brain 3.0 to explain, create, analyze, code, research, or solve a problem.</p><div class="suggestions"><button class="suggestion" data-prompt="Explain a difficult concept to me simply."><b>🧠 Learn something</b><small>Explain a difficult concept</small></button><button class="suggestion" data-prompt="Help me solve a technical problem step by step."><b>🔬 Solve a problem</b><small>Work through a challenge</small></button><button class="suggestion" data-prompt="Help me write clean production-quality code."><b>💻 Write code</b><small>Build or debug software</small></button><button class="suggestion" data-prompt="Help me brainstorm a new idea."><b>💡 Brainstorm</b><small>Develop an idea</small></button></div></div>`}

function renderChats(){const list=$("chatList"),term=$("chatSearch").value.toLowerCase().trim();list.innerHTML="";const chats=state.chats.filter(c=>(c.title||"New chat").toLowerCase().includes(term));$("emptyHistory").style.display=chats.length?"none":"block";chats.forEach(c=>{const el=document.createElement("div");el.className="chat-item"+(c.id===state.current?.id?" active":"");el.dataset.id=c.id;el.innerHTML=`<span class="chat-title">${esc(c.title||"New chat")}</span><button class="chat-more" type="button" aria-label="Chat options">⋯</button>`;el.onclick=e=>{if(e.target.closest(".chat-more"))return;openChat(c.id)};el.querySelector(".chat-more").onclick=e=>{e.stopPropagation();openChatMenu(c.id,e.currentTarget)};list.appendChild(el)})}

async function loadChats(){try{const d=await api("/api/chats");state.chats=Array.isArray(d)?d:(d.chats||d.data||[]);renderChats();setConnection(true)}catch(e){setConnection(false);console.error(e)}}

async function openChat(id){closePopups();try{const d=await api(`/api/chat/${encodeURIComponent(id)}`);const c=state.chats.find(x=>String(x.id)===String(id))||{};state.current={...c,id};state.messages=d.messages||d.chat?.messages||d.data?.messages||[];renderMessages();renderChats()}catch(e){toast("Could not load conversation");console.error(e)}}

function renderMessages(){const box=$("messages");box.innerHTML="";if(!state.messages.length){renderWelcome();return}state.messages.forEach((m,i)=>renderMessage(m,i));scrollBottom()}

function renderMessage(m,i){const role=m.role==="user"?"user":"assistant",text=m.content??m.message??"";const el=document.createElement("article");el.className=`message ${role}`;el.dataset.index=i;el.innerHTML=role==="user"?`<div class="message-content">${esc(text).replace(/\n/g,"<br>")}<div class="message-actions"><button data-action="edit">✎ Edit</button><button data-action="copy">⧉ Copy</button><button data-action="more">⋯</button></div></div><div class="message-avatar">U</div>`:`<div class="message-avatar"><img src="/static/logo.png" alt="" style="width:21px;height:21px;object-fit:contain"></div><div class="message-content">${markdown(text)}<div class="message-actions"><button data-action="copy">⧉ Copy</button><button data-action="regenerate">↻ Regenerate</button><button data-action="more">⋯</button></div></div>`;if(!state.showActions)qs(".message-actions",el)?.remove();qs("[data-action=copy]",el)?.addEventListener("click",()=>copyText(text));qs("[data-action=edit]",el)?.addEventListener("click",()=>editMessage(i));qs("[data-action=regenerate]",el)?.addEventListener("click",()=>regenerate(i));qs("[data-action=more]",el)?.addEventListener("click",e=>messageMenu(i,e.currentTarget));$("messages").appendChild(el)}

async function copyText(text){try{await navigator.clipboard.writeText(String(text));toast("Copied")}catch{toast("Copy failed")}}

function editMessage(i){const m=state.messages[i];if(!m||m.role!=="user")return;$("messageInput").value=m.content||"";autoResize();$("messageInput").focus();state.messages=state.messages.slice(0,i);renderMessages();toast("Message ready to edit")}

async function regenerate(i){if(state.loading||!state.current)return;const m=state.messages[i];if(!m||m.role!=="assistant")return;state.messages=state.messages.slice(0,i);renderMessages();const last=state.messages[state.messages.length-1];if(last?.role==="user")await sendMessage(last.content,true)}

function messageMenu(i,target){const p=$("contextMenu");p.innerHTML=`<button data-c="copy">⧉ Copy</button><button data-c="delete">🗑 Delete</button>`;positionPopup(p,target);p.classList.add("show");p.querySelector("[data-c=copy]").onclick=()=>{copyText(state.messages[i].content);closePopups()};p.querySelector("[data-c=delete]").onclick=()=>{state.messages.splice(i,1);renderMessages();closePopups()}}

function openChatMenu(id,target){const p=$("contextMenu");state.renameId=id;p.innerHTML=`<button data-c="rename">✎ Rename</button><button data-c="pin">📌 Pin</button><button data-c="share">↗ Share</button><button data-c="archive">📦 Archive</button><button data-c="delete" class="danger">🗑 Delete</button>`;positionPopup(p,target);p.classList.add("show");p.querySelector("[data-c=rename]").onclick=()=>{closePopups();const c=state.chats.find(x=>String(x.id)===String(id));$("renameInput").value=c?.title||"New chat";showModal("renameModal");setTimeout(()=>$("renameInput").focus(),50)};p.querySelector("[data-c=pin]").onclick=()=>{toast("Pin saved for this chat");closePopups()};p.querySelector("[data-c=share]").onclick=()=>shareChat(id);p.querySelector("[data-c=archive]").onclick=()=>{toast("Archive is coming soon");closePopups()};p.querySelector("[data-c=delete]").onclick=()=>deleteChat(id)}

function positionPopup(p,target){const r=target.getBoundingClientRect();p.style.left=Math.min(window.innerWidth-p.offsetWidth-10,Math.max(10,r.left))+"px";p.style.top=Math.min(window.innerHeight-p.offsetHeight-10,r.bottom+5)+"px"}

async function renameChat(){const id=state.renameId,title=$("renameInput").value.trim();if(!id||!title)return;try{await api(`/api/chat/${encodeURIComponent(id)}/rename`,{method:"PATCH",body:JSON.stringify({title})});const c=state.chats.find(x=>String(x.id)===String(id));if(c)c.title=title;if(state.current&&String(state.current.id)===String(id))state.current.title=title;renderChats();hideModal("renameModal");toast("Chat renamed")}catch(e){toast(e.message||"Rename failed");console.error(e)}}

async function deleteChat(id){closePopups();if(!confirm("Delete this conversation?"))return;try{await api(`/api/chat/${encodeURIComponent(id)}`,{method:"DELETE"}).catch(()=>api("/api/chat/delete",{method:"POST",body:JSON.stringify({chat_id:id,id})}));state.chats=state.chats.filter(c=>String(c.id)!==String(id));if(state.current&&String(state.current.id)===String(id)){state.current=null;state.messages=[];renderWelcome()}renderChats();toast("Chat deleted")}catch(e){toast("Could not delete chat");console.error(e)}}

async function createChat(){closePopups();state.current=null;state.messages=[];state.files=[];$("filePreview").innerHTML="";$("messageInput").value="";renderWelcome();renderChats();$("messageInput").focus()}

function autoResize(){const x=$("messageInput");x.style.height="auto";x.style.height=Math.min(x.scrollHeight,180)+"px"}

async function sendMessage(text,fromRegenerate=false){text=String(text??$("messageInput").value).trim();if(!text||state.loading)return;state.loading=true;$("sendButton").textContent="■";$("sendButton").disabled=false;if(!fromRegenerate)$("messageInput").value="";autoResize();if(!$("welcome")?.hidden)$("welcome")?.remove();state.messages.push({role:"user",content:text});const userIndex=state.messages.length-1;renderMessages();const assistant={role:"assistant",content:""};state.messages.push(assistant);const assistantIndex=state.messages.length-1;renderMessage(assistant,assistantIndex);const node=qs(`.message[data-index="${assistantIndex}"] .message-content`);node.innerHTML=`<div class="generating"><i></i><i></i><i></i><span>Thinking...</span></div>`;scrollBottom();try{let body={message:text};if(state.current?.id)body.chat_id=state.current.id;if(state.files.length)body.files=state.files.map(f=>({name:f.name,type:f.type}));state.controller=new AbortController();const r=await fetch("/api/chat",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:state.controller.signal});if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.error||d.message||`Brain request failed (${r.status})`)}const ct=r.headers.get("content-type")||"";if(ct.includes("text/event-stream")||ct.includes("text/plain")){await readStream(r,node,assistantIndex)}else{const d=await r.json();const answer=d.response||d.message||d.content||d.answer||d.text||d.data?.response||"";state.messages[assistantIndex].content=answer||"I couldn't generate a response.";updateAssistantNode(node,state.messages[assistantIndex].content);if(d.chat_id&&!state.current)state.current={id:d.chat_id,title:d.title||text.slice(0,55)};if(d.id&&!state.current)state.current={id:d.id,title:d.title||text.slice(0,55)};if(state.current&&!state.chats.some(c=>String(c.id)===String(state.current.id))){state.chats.unshift(state.current);renderChats()}}setConnection(true)}catch(e){if(e.name==="AbortError"){state.messages[assistantIndex].content="Generation stopped.";updateAssistantNode(node,state.messages[assistantIndex].content)}else{state.messages[assistantIndex].content="";node.innerHTML=`<div class="error-box">⚠ ${esc(e.message||"Brain generation failed")}<br><button data-retry>Try again</button></div>`;node.querySelector("[data-retry]").onclick=()=>{state.messages.splice(assistantIndex,1);sendMessage(text,true)};setConnection(false);console.error(e)}}finally{state.loading=false;state.controller=null;$("sendButton").textContent="↑";scrollBottom();await loadChats()}}

async function readStream(r,node,index){const reader=r.body.getReader(),decoder=new TextDecoder();let buf="",full="";while(true){const {value,done}=await reader.read();if(done)break;buf+=decoder.decode(value,{stream:true});const parts=buf.split(/\n/);buf=parts.pop()||"";for(let line of parts){line=line.trim();if(!line)continue;if(line.startsWith("data:"))line=line.slice(5).trim();if(line==="[DONE]")continue;let chunk=line;try{const d=JSON.parse(line);chunk=d.content??d.delta??d.response??d.message??d.text??"";if(d.chat_id&&!state.current)state.current={id:d.chat_id,title:d.title||state.messages[0]?.content?.slice(0,55)}}catch{}if(chunk){full+=chunk;state.messages[index].content=full;updateAssistantNode(node,full);scrollBottom()}}}if(full)state.messages[index].content=full}

function updateAssistantNode(node,text){node.innerHTML=markdown(text)+`<div class="message-actions"><button data-action="copy">⧉ Copy</button><button data-action="regenerate">↻ Regenerate</button><button data-action="more">⋯</button></div>`;node.querySelector("[data-action=copy]").onclick=()=>copyText(text);node.querySelector("[data-action=regenerate]").onclick=()=>regenerate(state.messages.findIndex(m=>m.content===text&&m.role==="assistant"));node.querySelector("[data-action=more]").onclick=e=>messageMenu(state.messages.findIndex(m=>m.content===text&&m.role==="assistant"),e.currentTarget)}

function stopGeneration(){if(state.loading&&state.controller)state.controller.abort()}

function shareChat(id=state.current?.id){if(!id)return toast("Start a conversation first");const url=`${location.origin}/?chat=${encodeURIComponent(id)}`;if(navigator.share)navigator.share({title:"Brain 3.0 conversation",url}).catch(()=>{});else copyText(url)}

function positionMenus(){closePopups()}

document.addEventListener("click",e=>{if(!e.target.closest(".popup,.chat-more,.more-menu,.model-button,#addButton,#moreButton"))closePopups()});
$("newChat").onclick=createChat;
$("clearChat").onclick=createChat;
$("openSidebar").onclick=()=>{$("sidebar").classList.add("open");$("sidebarBackdrop").classList.add("show")};
$("closeSidebar").onclick=()=>{$("sidebar").classList.remove("open");$("sidebarBackdrop").classList.remove("show")};
$("sidebarBackdrop").onclick=()=>{$("sidebar").classList.remove("open");$("sidebarBackdrop").classList.remove("show")};
$("chatSearch").oninput=renderChats;
$("saveRename").onclick=renameChat;
$("settingsBtn").onclick=()=>showModal("settingsModal");
$("shareChat").onclick=()=>shareChat();
$("moreButton").onclick=e=>{closePopups();const p=$("moreMenu");p.classList.add("show");p.style.top="55px";p.style.right="18px"};
$("modelButton").onclick=()=>{closePopups();$("modelMenu").classList.add("show")};
$("addButton").onclick=e=>{closePopups();const p=$("toolsMenu");p.classList.add("show")};
$("sendButton").onclick=()=>state.loading?stopGeneration():sendMessage();
$("messageInput").addEventListener("input",autoResize);
$("messageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&state.enterToSend){e.preventDefault();sendMessage()}});
$("fileInput").onchange=e=>{state.files=[...e.target.files];$("filePreview").innerHTML=state.files.map((f,i)=>`<div class="file-chip">📎 ${esc(f.name)} <button data-file="${i}">×</button></div>`).join("");qsa("[data-file]").forEach(b=>b.onclick=()=>{state.files.splice(+b.dataset.file,1);b.parentElement.remove()})};
qsa(".suggestion").forEach(b=>b.onclick=()=>{ $("messageInput").value=b.dataset.prompt;autoResize();$("messageInput").focus()});
qsa("[data-close]").forEach(b=>b.onclick=()=>hideModal(b.dataset.close));
qsa("#toolsMenu button").forEach(b=>b.onclick=()=>{const t=b.dataset.tool;if(t==="file"||t==="image"){$("fileInput").accept=t==="image"?"image/*":"";$("fileInput").click()}else toast(`${b.textContent.trim()} is not connected yet`);closePopups()});
$("enterToggle").onchange=e=>state.enterToSend=e.target.checked;
$("actionsToggle").onchange=e=>{state.showActions=e.target.checked;renderMessages()};
$("authBtn").onclick=()=>{if(window.BrainAuth?.openLogin)BrainAuth.openLogin();else toast("Authentication is handled by auth.js")};
window.addEventListener("resize",positionMenus);
(async()=>{try{await loadChats();const id=new URLSearchParams(location.search).get("chat");if(id)await openChat(id);else renderWelcome()}catch(e){renderWelcome();console.error(e)}})();