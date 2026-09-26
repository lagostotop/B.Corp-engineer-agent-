"use strict";

const $=id=>document.getElementById(id),qs=(s,e=document)=>e.querySelector(s),qsa=(s,e=document)=>[...e.querySelectorAll(s)];
const state={chats:[],current:null,messages:[],loading:false,controller:null,files:[],renameId:null,enterToSend:true,showActions:true};

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const md=s=>{try{return window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(String(s||""))):esc(s).replace(/\n/g,"<br>")}catch{return esc(s).replace(/\n/g,"<br>")}};
const toast=m=>{const t=$("toast");if(!t)return;t.textContent=m;t.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("show"),2200)};
const closePopups=()=>qsa(".popup").forEach(x=>x.classList.remove("show"));
const showModal=id=>$(id)?.classList.add("show");
const hideModal=id=>$(id)?.classList.remove("show");
const scrollBottom=()=>requestAnimationFrame(()=>{const c=$("chatContainer");if(c)c.scrollTop=c.scrollHeight});

async function authFetch(url,opt={}){
  if(window.BrainAuth?.fetchWithAuth)return BrainAuth.fetchWithAuth(url,opt);
  return fetch(url,{credentials:"include",...opt});
}

async function jsonFetch(url,opt={}){
  const r=await authFetch(url,{...opt,headers:{Accept:"application/json",...(opt.headers||{})}});
  let d=null;
  try{d=await r.json()}catch{}
  if(!r.ok)throw Error(d?.error?.message||d?.error||d?.message||`Request failed (${r.status})`);
  return d;
}

function setConnection(ok){
  const c=$("connection");
  if(!c)return;
  c.innerHTML=`<i></i> ${ok?"Online":"Offline"}`;
  c.classList.toggle("offline",!ok);
}

function requireAuth(){
  if(window.BrainAuth?.isAuthenticated?.())return true;
  openAuth();
  return false;
}

function openAuth(){
  const m=$("authModal");
  if(!m)return;
  m.classList.add("show");
  $("authEmail")?.focus();
}

function authError(x){
  const e=$("authError");
  if(e)e.textContent=x||"";
}

function renderWelcome(){
  if(state.messages.length)return;
  const b=$("messages");
  if(!b)return;
  b.innerHTML=`<div id="welcome" class="welcome"><h1>What can I help with?</h1><p>Ask Brain 3.0 to explain, create, analyze, code, research, or solve a problem.</p><div class="suggestions"><button class="suggestion" data-prompt="Explain a difficult concept to me simply."><b>Learn something</b><small>Understand a difficult topic</small></button><button class="suggestion" data-prompt="Help me solve a technical problem step by step."><b>Solve a problem</b><small>Work through a challenge</small></button><button class="suggestion" data-prompt="Help me write clean production-quality code."><b>Write code</b><small>Build or debug software</small></button><button class="suggestion" data-prompt="Help me brainstorm a new idea."><b>Brainstorm</b><small>Develop an idea</small></button></div></div>`;
}

function renderChats(){
  const list=$("chatList");
  if(!list)return;
  const q=($("chatSearch")?.value||"").toLowerCase().trim();
  const chats=state.chats.filter(c=>(c.title||"New Chat").toLowerCase().includes(q));
  list.innerHTML="";
  const empty=$("emptyHistory");
  if(empty)empty.style.display=chats.length?"none":"block";
  chats.forEach(c=>{
    const e=document.createElement("div");
    e.className="chat-item"+(String(c.id)===String(state.current?.id)?" active":"");
    e.innerHTML=`<span class="chat-title">${esc(c.title||"New Chat")}</span><button class="chat-more" type="button">⋯</button>`;
    e.onclick=x=>{if(!x.target.closest(".chat-more"))openChat(c.id)};
    qs(".chat-more",e).onclick=x=>{x.stopPropagation();openChatMenu(c.id,x.currentTarget)};
    list.appendChild(e);
  });
}

async function loadChats(){
  if(!window.BrainAuth?.isAuthenticated?.()){
    state.chats=[];
    renderChats();
    return;
  }
  try{
    const d=await jsonFetch("/api/chats?limit=100");
    state.chats=Array.isArray(d)?d:(d?.chats||d?.data||[]);
    renderChats();
    setConnection(true);
  }catch(e){
    console.error("Chat history:",e);
    setConnection(false);
  }
}

async function openChat(id){
  if(!requireAuth())return;
  closePopups();
  try{
    const d=await jsonFetch(`/api/chats/${encodeURIComponent(id)}`);
    const c=state.chats.find(x=>String(x.id)===String(id))||d?.chat||{};
    state.current={...c,id};
    state.messages=Array.isArray(d)?d:(d?.messages||d?.data||[]);
    renderMessages();
    renderChats();
    closeSidebar();
  }catch(e){toast(e.message||"Could not load conversation")}
}

function renderMessages(){
  const b=$("messages");
  if(!b)return;
  b.innerHTML="";
  if(!state.messages.length){renderWelcome();return}
  state.messages.forEach((m,i)=>renderMessage(m,i));
  scrollBottom();
}

function actionsHTML(i,user=false){
  if(!state.showActions)return"";
  return `<div class="message-actions">${user?`<button type="button" data-action="edit" data-index="${i}">✎ Edit</button>`:""}<button type="button" data-action="copy" data-index="${i}">⧉ Copy</button>${!user?`<button type="button" data-action="regenerate" data-index="${i}">↻ Regenerate</button>`:""}</div>`;
}

function renderMessage(m,i){
  const role=m.role==="user"?"user":"assistant";
  const text=m.content??m.message??"";
  const e=document.createElement("article");
  e.className=`message ${role}`;
  e.dataset.index=i;
  if(role==="user"){
    e.innerHTML=`<div class="message-content">${esc(text).replace(/\n/g,"<br>")}${actionsHTML(i,true)}</div><div class="message-avatar">U</div>`;
  }else{
    e.innerHTML=`<div class="message-avatar"><img src="/static/logo.png" alt=""></div><div class="message-content">${md(text)}${actionsHTML(i,false)}</div>`;
  }
  $("messages")?.appendChild(e);
}

async function copyText(text){
  try{
    await navigator.clipboard.writeText(String(text||""));
    toast("Copied");
  }catch{toast("Copy failed")}
}

function editMessage(i){
  const m=state.messages[i];
  if(!m||m.role!=="user")return;
  $("messageInput").value=m.content||"";
  state.messages=state.messages.slice(0,i);
  renderMessages();
  autoResize();
  $("messageInput")?.focus();
}

async function regenerate(i){
  if(state.loading||!requireAuth())return;
  const u=[...state.messages.slice(0,i)].reverse().find(m=>m.role==="user");
  if(!u)return;
  const text=u.content;
  state.messages=state.messages.slice(0,i);
  renderMessages();
  await sendMessage(text,true);
}

function positionPopup(p,t){
  p.classList.add("show");
  p.style.visibility="hidden";
  const r=t.getBoundingClientRect(),w=p.offsetWidth||190,h=p.offsetHeight||150;
  p.style.left=Math.min(innerWidth-w-10,Math.max(10,r.left))+"px";
  p.style.top=Math.min(innerHeight-h-10,r.bottom+5)+"px";
  p.style.visibility="";
}

function openChatMenu(id,target){
  const p=$("contextMenu");
  if(!p)return;
  state.renameId=id;
  p.innerHTML=`<button type="button" data-c="rename">✎ Rename</button><button type="button" data-c="share">↗ Share</button><button type="button" data-c="delete">🗑 Delete</button>`;
  positionPopup(p,target);
  p.querySelector("[data-c=rename]").onclick=()=>{
    closePopups();
    const c=state.chats.find(x=>String(x.id)===String(id));
    if($("renameInput"))$("renameInput").value=c?.title||"New Chat";
    showModal("renameModal");
    setTimeout(()=>$("renameInput")?.focus(),50);
  };
  p.querySelector("[data-c=share]").onclick=()=>shareChat(id);
  p.querySelector("[data-c=delete]").onclick=()=>deleteChat(id);
}

async function renameChat(){
  const id=state.renameId,title=$("renameInput")?.value.trim();
  if(!id||!title)return;
  try{
    const d=await jsonFetch(`/api/chats/${encodeURIComponent(id)}`,{
      method:"PATCH",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({title})
    });
    const c=state.chats.find(x=>String(x.id)===String(id));
    if(c)c.title=d?.chat?.title||title;
    if(state.current?.id===id)state.current.title=title;
    hideModal("renameModal");
    renderChats();
    toast("Chat renamed");
  }catch(e){toast(e.message||"Rename failed")}
}

async function deleteChat(id){
  closePopups();
  if(!confirm("Delete this conversation?"))return;
  try{
    await jsonFetch(`/api/chats/${encodeURIComponent(id)}`,{method:"DELETE"});
    state.chats=state.chats.filter(c=>String(c.id)!==String(id));
    if(String(state.current?.id)===String(id)){
      state.current=null;
      state.messages=[];
      renderMessages();
    }
    renderChats();
    toast("Chat deleted");
  }catch(e){toast(e.message||"Delete failed")}
}

async function shareChat(id=state.current?.id){
  if(!id)return toast("Open a conversation first");
  try{
    const url=location.origin+"/?chat="+encodeURIComponent(id);
    await navigator.clipboard.writeText(url);
    toast("Chat link copied");
  }catch{toast("Could not copy link")}
}

function createChat(){
  closePopups();
  state.current=null;
  state.messages=[];
  state.files=[];
  const fp=$("filePreview");
  if(fp)fp.innerHTML="";
  const input=$("messageInput");
  if(input)input.value="";
  renderMessages();
  renderChats();
  input?.focus();
}

function autoResize(){
  const x=$("messageInput");
  if(!x)return;
  x.style.height="auto";
  x.style.height=Math.min(x.scrollHeight,180)+"px";
}

async function sendMessage(text,regen=false){
  if(!requireAuth()||state.loading)return;
  text=String(text??$("messageInput")?.value||"").trim();
  if(!text)return;

  state.loading=true;
  const send=$("sendButton");
  if(send)send.textContent="■";

  if(!regen&&$("messageInput"))$("messageInput").value="";
  autoResize();

  state.messages.push({role:"user",content:text});
  renderMessages();

  const assistant={role:"assistant",content:""};
  state.messages.push(assistant);
  const index=state.messages.length-1;

  renderMessage(assistant,index);

  const messageEl=qs(`.message[data-index="${index}"]`);
  const node=qs(".message-content",messageEl);
  if(node)node.innerHTML=`<div class="generating"><i></i><i></i><i></i><span>Thinking...</span></div>`;

  scrollBottom();

  try{
    const form=new FormData();
    form.append("question",text);
    form.append("client_msg_id",crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`);
    form.append("mode","normal");
    if(state.current?.id)form.append("chat_id",state.current.id);
    if(regen)form.append("is_regen","1");
    if(state.files[0])form.append("file",state.files[0],state.files[0].name);

    state.controller=new AbortController();

    const r=await authFetch("/api/chat",{
      method:"POST",
      body:form,
      signal:state.controller.signal,
      headers:{Accept:"text/event-stream"}
    });

    if(!r.ok){
      let d={};
      try{d=await r.json()}catch{}
      throw Error(d?.error?.message||d?.error||d?.message||`Brain request failed (${r.status})`);
    }

    if(!r.body)throw Error("Brain returned no response stream.");

    await readSSE(r,node,index);
    setConnection(true);
  }catch(e){
    if(e.name==="AbortError"){
      assistant.content=assistant.content||"Generation stopped.";
      if(node)node.innerHTML=md(assistant.content)+actionsHTML(index,false);
    }else{
      console.error("Brain generation:",e);
      const message=e.message||"Brain generation failed.";
      if(node)node.innerHTML=`<div class="error-box">⚠ ${esc(message)}<br><button type="button" data-retry>Try again</button></div>`;
      node?.querySelector("[data-retry]")?.addEventListener("click",()=>{
        state.messages.splice(index,1);
        renderMessages();
        sendMessage(text,regen);
      });
      setConnection(false);
    }
  }finally{
    state.loading=false;
    state.controller=null;
    if(send)send.textContent="↑";
    scrollBottom();
    loadChats();
  }
}

/* FIXED SSE STREAM READER */
async function readSSE(response,node,index){
  const reader=response.body.getReader();
  const decoder=new TextDecoder();
  let buffer="";
  let event="";
  let data="";

  const handle=payload=>{
    if(!payload)return;
    let d;
    try{d=JSON.parse(payload)}catch{d={text:payload}};

    if(event==="token"){
      const text=d.text??d.token??d.content??"";
      state.messages[index].content+=text;
      if(node)node.innerHTML=md(state.messages[index].content)+actionsHTML(index,false);
      scrollBottom();
    }else if(event==="chat_id"){
      const id=d.chat_id||d.id;
      if(id)state.current={...(state.current||{}),id};
    }else if(event==="error"){
      throw Error(d.message||d.error||"Brain generation failed.");
    }else if(event==="done"){
      if(d.chat_id){
        state.current={...(state.current||{}),id:d.chat_id};
      }
    }
  };

  const process=chunk=>{
    buffer+=chunk;
    const lines=buffer.split(/\r?\n/);
    buffer=lines.pop()||"";

    for(const line of lines){
      if(line.startsWith("event:")){
        event=line.slice(6).trim();
      }else if(line.startsWith("data:")){
        data+=line.slice(5).trim();
      }else if(line===""){
        if(data){
          handle(data);
          data="";
        }
        event="";
      }
    }
  };

  while(true){
    const {value,done}=await reader.read();
    if(done)break;
    process(decoder.decode(value,{stream:true}));
  }

  process(decoder.decode());
  if(data)handle(data);

  if(!state.messages[index]?.content?.trim()){
    throw Error("Brain returned an empty response.");
  }

  if(node){
    node.innerHTML=md(state.messages[index].content)+actionsHTML(index,false);
  }
}

function stopGeneration(){
  state.controller?.abort();
}

function renderFiles(){
  const p=$("filePreview");
  if(!p)return;
  p.innerHTML="";
  state.files.forEach((f,i)=>{
    const e=document.createElement("div");
    e.className="file-chip";
    e.innerHTML=`${esc(f.name)} <button type="button">×</button>`;
    e.querySelector("button").onclick=()=>{
      state.files.splice(i,1);
      renderFiles();
    };
    p.appendChild(e);
  });
}

function closeSidebar(){
  $("sidebar")?.classList.remove("open");
  $("sidebarBackdrop")?.classList.remove("show");
}

function openSidebar(){
  $("sidebar")?.classList.add("open");
  $("sidebarBackdrop")?.classList.add("show");
}

function bind(id,event,fn){
  $(id)?.addEventListener(event,fn);
}

document.addEventListener("click",e=>{
  const b=e.target.closest("[data-action]");
  if(!b)return;
  const i=Number(b.dataset.index);
  const action=b.dataset.action;
  if(action==="copy")copyText(state.messages[i]?.content||"");
  else if(action==="edit")editMessage(i);
  else if(action==="regenerate")regenerate(i);
});

document.addEventListener("DOMContentLoaded",async()=>{
  try{
    if(window.BrainAuth?.init)await BrainAuth.init();
  }catch(e){console.error("Auth init:",e)}

  if(window.BrainAuth?.onAuthStateChange){
    BrainAuth.onAuthStateChange(async()=>{
      await loadChats();
    });
  }

  await loadChats();
  renderMessages();

  bind("newChat","click",createChat);
  bind("clearChat","click",createChat);

  bind("sendButton","click",()=>{
    if(state.loading)stopGeneration();
    else sendMessage();
  });

  bind("messageInput","input",autoResize);

  bind("messageInput","keydown",e=>{
    if(e.key==="Enter"&&!e.shiftKey&&state.enterToSend){
      e.preventDefault();
      sendMessage();
    }
  });

  bind("chatSearch","input",renderChats);

  bind("addButton","click",()=>{
    closePopups();
    $("toolsMenu")?.classList.toggle("show");
  });

  bind("voiceButton","click",()=>{
    if(!("webkitSpeechRecognition" in window||"SpeechRecognition" in window)){
      toast("Voice input is not supported in this browser");
      return;
    }
    const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
    const r=new Speech();
    r.lang="en-US";
    r.interimResults=false;
    r.onresult=e=>{
      const input=$("messageInput");
      if(input){
        input.value+=(input.value?" ":"")+e.results[0][0].transcript;
        autoResize();
        input.focus();
      }
    };
    r.onerror=()=>toast("Voice input failed");
    r.start();
  });

  bind("modelButton","click",()=>{
    $("modelMenu")?.classList.toggle("show");
    $("moreMenu")?.classList.remove("show");
  });

  bind("moreButton","click",()=>{
    $("moreMenu")?.classList.toggle("show");
    $("modelMenu")?.classList.remove("show");
  });

  bind("openSidebar","click",openSidebar);
  bind("closeSidebar","click",closeSidebar);
  bind("sidebarBackdrop","click",closeSidebar);

  bind("settingsBtn","click",()=>showModal("settingsModal"));

  bind("authBtn","click",async()=>{
    try{
      if(window.BrainAuth?.isAuthenticated?.()){
        await BrainAuth.signOut();
        state.current=null;
        state.messages=[];
        toast("Signed out");
        await loadChats();
        renderMessages();
      }else openAuth();
    }catch(e){toast(e.message||"Authentication failed")}
  });

  bind("saveRename","click",renameChat);

  qsa("[data-close]").forEach(b=>b.addEventListener("click",()=>hideModal(b.dataset.close)));

  qsa(".modal").forEach(m=>m.addEventListener("click",e=>{
    if(e.target===m)m.classList.remove("show");
  }));

  bind("loginSubmit","click",async()=>{
    authError("");
    try{
      await BrainAuth.signIn(
        $("authEmail")?.value.trim(),
        $("authPassword")?.value
      );
      hideModal("authModal");
      toast("Logged in");
      await loadChats();
      renderMessages();
    }catch(e){authError(e.message||"Login failed")}
  });

  bind("signupSubmit","click",async()=>{
    authError("");
    try{
      await BrainAuth.signUp(
        $("signupEmail")?.value.trim(),
        $("signupPassword")?.value
      );
      hideModal("authModal");
      toast("Account created");
      await loadChats();
    }catch(e){authError(e.message||"Signup failed")}
  });

  bind("fileInput","change",e=>{
    state.files=[...(e.target.files||[])];
    renderFiles();
  });

  bind("shareChat","click",()=>shareChat());

  document.addEventListener("click",e=>{
    if(!e.target.closest(".popup")&&!e.target.closest("#addButton")&&!e.target.closest("#modelButton")&&!e.target.closest("#moreButton")&&!e.target.closest(".chat-more")){
      closePopups();
    }
  });

  window.addEventListener("resize",()=>{
    if(innerWidth>800)closeSidebar();
  });
});