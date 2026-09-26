"use strict";

const $=id=>document.getElementById(id);
const qs=(s,e=document)=>e.querySelector(s);
const qsa=(s,e=document)=>[...e.querySelectorAll(s)];

const state={
  chats:[],current:null,messages:[],loading:false,controller:null,
  files:[],renameId:null,enterToSend:true,showActions:true
};

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));

const toast=m=>{
  const t=$("toast");
  if(!t)return;
  t.textContent=m;
  t.classList.add("show");
  clearTimeout(toast.t);
  toast.t=setTimeout(()=>t.classList.remove("show"),2200);
};

const markdown=s=>{
  try{return window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(String(s||""))):esc(s).replace(/\n/g,"<br>")}
  catch{return esc(s).replace(/\n/g,"<br>")}
};

const closePopups=()=>qsa(".popup").forEach(x=>x.classList.remove("show"));

const scrollBottom=()=>{
  const c=$("chatContainer");
  if(c)requestAnimationFrame(()=>c.scrollTop=c.scrollHeight);
};

const showModal=id=>$(id)?.classList.add("show");
const hideModal=id=>$(id)?.classList.remove("show");

async function authFetch(url,options={}){
  if(window.BrainAuth?.fetchWithAuth)return BrainAuth.fetchWithAuth(url,options);
  return fetch(url,{credentials:"include",...options});
}

async function jsonFetch(url,options={}){
  const r=await authFetch(url,{
    ...options,
    headers:{
      Accept:"application/json",
      ...(options.headers||{})
    }
  });
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

function renderWelcome(){
  if(state.messages.length)return;
  const box=$("messages");
  if(!box)return;
  box.innerHTML=`
    <div id="welcome" class="welcome">
      <div class="welcome-logo"><img src="/static/logo.png" alt="B.Corp"></div>
      <h1>What are you working on?</h1>
      <p>Ask Brain 3.0 to explain, create, analyze, code, research, or solve a problem.</p>
      <div class="suggestions">
        <button class="suggestion" data-prompt="Explain a difficult concept to me simply."><b>🧠 Learn</b><small>Understand something difficult</small></button>
        <button class="suggestion" data-prompt="Help me solve a technical problem step by step."><b>🔬 Solve</b><small>Work through a challenge</small></button>
        <button class="suggestion" data-prompt="Help me write clean production-quality code."><b>💻 Code</b><small>Build or debug software</small></button>
        <button class="suggestion" data-prompt="Help me brainstorm a new idea."><b>💡 Create</b><small>Develop an idea</small></button>
      </div>
    </div>`;
  qsa(".suggestion").forEach(b=>b.onclick=()=>{
    $("messageInput").value=b.dataset.prompt;
    autoResize();
    $("messageInput").focus();
  });
}

function renderChats(){
  const list=$("chatList");
  if(!list)return;
  const search=($("chatSearch")?.value||"").toLowerCase().trim();
  list.innerHTML="";
  const chats=state.chats.filter(c=>(c.title||"New Chat").toLowerCase().includes(search));
  if($("emptyHistory"))$("emptyHistory").style.display=chats.length?"none":"block";

  chats.forEach(c=>{
    const el=document.createElement("div");
    el.className="chat-item"+(String(c.id)===String(state.current?.id)?" active":"");
    el.dataset.id=c.id;
    el.innerHTML=`
      <span class="chat-title">${esc(c.title||"New Chat")}</span>
      <button class="chat-more" type="button" aria-label="Chat options">⋯</button>`;
    el.onclick=e=>{
      if(e.target.closest(".chat-more"))return;
      openChat(c.id);
    };
    qs(".chat-more",el).onclick=e=>{
      e.stopPropagation();
      openChatMenu(c.id,e.currentTarget);
    };
    list.appendChild(el);
  });
}

async function loadChats(){
  try{
    const d=await jsonFetch("/api/chats");
    state.chats=Array.isArray(d)?d:(d?.chats||d?.data||[]);
    renderChats();
    setConnection(true);
  }catch(e){
    console.error("Chat list:",e);
    setConnection(false);
  }
}

async function openChat(id){
  closePopups();
  try{
    const d=await jsonFetch(`/api/chat/${encodeURIComponent(id)}`);
    const c=state.chats.find(x=>String(x.id)===String(id))||{};
    state.current={...c,id};
    state.messages=Array.isArray(d)?d:(d?.messages||[]);
    renderMessages();
    renderChats();
  }catch(e){
    console.error(e);
    toast(e.message||"Could not load conversation");
  }
}

function renderMessages(){
  const box=$("messages");
  if(!box)return;
  box.innerHTML="";
  if(!state.messages.length){
    renderWelcome();
    return;
  }
  state.messages.forEach((m,i)=>renderMessage(m,i));
  scrollBottom();
}

function renderMessage(m,i){
  const role=m.role==="user"?"user":"assistant";
  const text=m.content??m.message??"";
  const el=document.createElement("article");
  el.className=`message ${role}`;
  el.dataset.index=i;

  if(role==="user"){
    el.innerHTML=`
      <div class="message-content">
        ${esc(text).replace(/\n/g,"<br>")}
        ${state.showActions?`<div class="message-actions">
          <button data-action="edit">✎ Edit</button>
          <button data-action="copy">⧉ Copy</button>
        </div>`:""}
      </div>
      <div class="message-avatar">U</div>`;
  }else{
    el.innerHTML=`
      <div class="message-avatar"><img src="/static/logo.png" alt=""></div>
      <div class="message-content">
        ${markdown(text)}
        ${state.showActions?`<div class="message-actions">
          <button data-action="copy">⧉ Copy</button>
          <button data-action="regenerate">↻ Regenerate</button>
          <button data-action="more">⋯</button>
        </div>`:""}
      </div>`;
  }

  qs("[data-action=copy]",el)?.addEventListener("click",()=>copyText(text));
  qs("[data-action=edit]",el)?.addEventListener("click",()=>editMessage(i));
  qs("[data-action=regenerate]",el)?.addEventListener("click",()=>regenerate(i));
  qs("[data-action=more]",el)?.addEventListener("click",e=>messageMenu(i,e.currentTarget));

  $("messages").appendChild(el);
}

async function copyText(text){
  try{
    await navigator.clipboard.writeText(String(text));
    toast("Copied");
  }catch{
    toast("Copy failed");
  }
}

function editMessage(i){
  const m=state.messages[i];
  if(!m||m.role!=="user")return;
  $("messageInput").value=m.content||"";
  state.messages=state.messages.slice(0,i);
  renderMessages();
  autoResize();
  $("messageInput").focus();
}

async function regenerate(i){
  if(state.loading)return;
  const lastUser=[...state.messages.slice(0,i)].reverse().find(m=>m.role==="user");
  if(!lastUser)return;
  state.messages=state.messages.slice(0,i);
  renderMessages();
  await sendMessage(lastUser.content,true);
}

function messageMenu(i,target){
  const p=$("contextMenu");
  if(!p)return;
  p.innerHTML=`
    <button data-c="copy">⧉ Copy</button>
    <button data-c="delete">🗑 Delete locally</button>`;
  positionPopup(p,target);
  p.classList.add("show");
  p.querySelector("[data-c=copy]").onclick=()=>{
    copyText(state.messages[i]?.content||"");
    closePopups();
  };
  p.querySelector("[data-c=delete]").onclick=()=>{
    state.messages.splice(i,1);
    renderMessages();
    closePopups();
  };
}

function openChatMenu(id,target){
  const p=$("contextMenu");
  if(!p)return;
  state.renameId=id;
  p.innerHTML=`
    <button data-c="rename">✎ Rename</button>
    <button data-c="share">↗ Share</button>
    <button data-c="delete" class="danger">🗑 Delete</button>`;
  positionPopup(p,target);
  p.classList.add("show");

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

function positionPopup(p,target){
  p.style.visibility="hidden";
  p.classList.add("show");
  const r=target.getBoundingClientRect();
  const w=p.offsetWidth||190;
  const h=p.offsetHeight||150;
  p.style.left=Math.min(innerWidth-w-10,Math.max(10,r.left))+"px";
  p.style.top=Math.min(innerHeight-h-10,r.bottom+5)+"px";
  p.style.visibility="";
}

async function renameChat(){
  const id=state.renameId;
  const title=$("renameInput")?.value.trim();
  if(!id||!title)return;

  try{
    const d=await jsonFetch(`/api/chats/${encodeURIComponent(id)}`,{
      method:"PATCH",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({title})
    });

    const c=state.chats.find(x=>String(x.id)===String(id));
    if(c)c.title=d?.chat?.title||title;
    if(state.current&&String(state.current.id)===String(id))state.current.title=d?.chat?.title||title;

    hideModal("renameModal");
    renderChats();
    toast("Chat renamed");
  }catch(e){
    console.error(e);
    toast(e.message||"Rename failed");
  }
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
      renderWelcome();
    }

    renderChats();
    toast("Chat deleted");
  }catch(e){
    console.error(e);
    toast(e.message||"Could not delete chat");
  }
}

function createChat(){
  closePopups();
  state.current=null;
  state.messages=[];
  state.files=[];
  if($("filePreview"))$("filePreview").innerHTML="";
  if($("messageInput"))$("messageInput").value="";
  renderWelcome();
  renderChats();
  $("messageInput")?.focus();
}

function autoResize(){
  const x=$("messageInput");
  if(!x)return;
  x.style.height="auto";
  x.style.height=Math.min(x.scrollHeight,180)+"px";
}

async function sendMessage(text,regen=false){
  text=String(text??$("messageInput").value).trim();
  if(!text||state.loading)return;

  state.loading=true;
  $("sendButton").textContent="■";
  $("sendButton").classList.add("stop");

  if(!regen)$("messageInput").value="";
  autoResize();

  state.messages.push({role:"user",content:text});
  renderMessages();

  const assistant={role:"assistant",content:""};
  state.messages.push(assistant);
  const index=state.messages.length-1;
  renderMessage(assistant,index);

  const node=qs(`.message[data-index="${index}"] .message-content`);
  if(node)node.innerHTML=`<div class="generating"><i></i><i></i><i></i><span>Thinking...</span></div>`;

  scrollBottom();

  try{
    const form=new FormData();
    form.append("question",text);
    form.append("client_msg_id",crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`);
    form.append("mode","normal");

    if(state.current?.id)form.append("chat_id",state.current.id);
    if(regen)form.append("is_regen","1");

    if(state.files.length){
      state.files.forEach(f=>form.append("file",f,f.name));
    }

    state.controller=new AbortController();

    const response=await authFetch("/api/chat",{
      method:"POST",
      body:form,
      signal:state.controller.signal,
      headers:{Accept:"text/event-stream"}
    });

    if(!response.ok){
      let d={};
      try{d=await response.json()}catch{}
      throw Error(d?.error?.message||d?.error||d?.message||`Brain request failed (${response.status})`);
    }

    await readSSE(response,node,index);
    setConnection(true);

  }catch(e){
    if(e.name==="AbortError"){
      state.messages[index].content="Generation stopped.";
      updateAssistantNode(node,"Generation stopped.",false);
    }else{
      console.error("Brain generation:",e);
      state.messages[index].content="";
      if(node){
        node.innerHTML=`
          <div class="error-box">
            ⚠ ${esc(e.message||"Brain generation failed")}
            <br><button data-retry>Try again</button>
          </div>`;
        node.querySelector("[data-retry]").onclick=()=>{
          state.messages.splice(index,1);
          renderMessages();
          sendMessage(text,regen);
        };
      }
      setConnection(false);
    }
  }finally{
    state.loading=false;
    state.controller=null;
    $("sendButton").textContent="↑";
    $("sendButton").classList.remove("stop");
    scrollBottom();
    await loadChats();
  }
}

async function readSSE(response,node,index){
  const reader=response.body.getReader();
  const decoder=new TextDecoder();
  let buffer="";
  let full="";
  let eventName="";

  while(true){
    const {value,done}=await reader.read();
    if(done)break;

    buffer+=decoder.decode(value,{stream:true});
    const events=buffer.split(/\r?\n\r?\n/);
    buffer=events.pop()||"";

    for(const block of events){
      let dataLines=[];
      eventName="message";

      for(const line of block.split(/\r?\n/)){
        if(line.startsWith("event:"))eventName=line.slice(6).trim();
        else if(line.startsWith("data:"))dataLines.push(line.slice(5).trim());
      }

      if(!dataLines.length)continue;

      const raw=dataLines.join("\n");
      let data={};

      try{data=JSON.parse(raw)}catch{data={text:raw}};

      if(eventName==="chat_id"){
        if(data.chat_id){
          const id=data.chat_id;
          state.current=state.current||{id,title:state.messages.find(m=>m.role==="user")?.content?.slice(0,60)||"New Chat"};
          state.current.id=id;
        }
        continue;
      }

      if(eventName==="token"){
        const text=data.text||"";
        if(text){
          full+=text;
          state.messages[index].content=full;
          updateAssistantNode(node,full,true);
          scrollBottom();
        }
        continue;
      }

      if(eventName==="error"){
        throw Error(data.message||"Brain generation failed");
      }

      if(eventName==="done"){
        if(data.chat_id&&!state.current){
          state.current={id:data.chat_id,title:full.slice(0,60)||"New Chat"};
        }
      }
    }
  }

  if(!full){
    updateAssistantNode(node,"I couldn't generate a response.",false);
    state.messages[index].content="I couldn't generate a response.";
  }
}

function updateAssistantNode(node,text,streaming=true){
  if(!node)return;
  node.innerHTML=markdown(text)+`
    ${state.showActions?`<div class="message-actions">
      <button data-action="copy">⧉ Copy</button>
      ${streaming?`<button data-action="regenerate">↻ Regenerate</button>`:""}
      <button data-action="more">⋯</button>
    </div>`:""}`;

  node.querySelector("[data-action=copy]")?.addEventListener("click",()=>copyText(text));

  node.querySelector("[data-action=regenerate]")?.addEventListener("click",()=>{
    const i=state.messages.findIndex(m=>m.role==="assistant"&&m.content===text);
    if(i>=0)regenerate(i);
  });

  node.querySelector("[data-action=more]")?.addEventListener("click",e=>{
    const i=state.messages.findIndex(m=>m.role==="assistant"&&m.content===text);
    if(i>=0)messageMenu(i,e.currentTarget);
  });
}

function stopGeneration(){
  if(state.loading&&state.controller)state.controller.abort();
}

function shareChat(id=state.current?.id){
  if(!id){
    toast("Start a conversation first");
    return;
  }

  const url=`${location.origin}/?chat=${encodeURIComponent(id)}`;

  if(navigator.share){
    navigator.share({title:"B.Corp Brain 3.0",url}).catch(()=>{});
  }else{
    copyText(url);
  }
}

function bind(id,event,fn){
  const el=$(id);
  if(el)el.addEventListener(event,fn);
}

document.addEventListener("click",e=>{
  if(!e.target.closest(".popup,.chat-more,.more-menu,#addButton,#moreButton,#modelButton"))closePopups();
});

bind("newChat","click",createChat);
bind("clearChat","click",createChat);

bind("openSidebar","click",()=>{
  $("sidebar")?.classList.add("open");
  $("sidebarBackdrop")?.classList.add("show");
});

bind("closeSidebar","click",()=>{
  $("sidebar")?.classList.remove("open");
  $("sidebarBackdrop")?.classList.remove("show");
});

bind("sidebarBackdrop","click",()=>{
  $("sidebar")?.classList.remove("open");
  $("sidebarBackdrop")?.classList.remove("show");
});

bind("chatSearch","input",renderChats);
bind("saveRename","click",renameChat);

bind("settingsBtn","click",()=>showModal("settingsModal"));
bind("shareChat","click",()=>shareChat());

bind("moreButton","click",()=>{
  closePopups();
  const p=$("moreMenu");
  if(p){
    p.classList.add("show");
    p.style.top="55px";
    p.style.right="18px";
  }
});

bind("modelButton","click",()=>{
  closePopups();
  $("modelMenu")?.classList.add("show");
});

bind("addButton","click",()=>{
  closePopups();
  $("toolsMenu")?.classList.add("show");
});

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

bind("fileInput","change",e=>{
  state.files=[...e.target.files];
  const p=$("filePreview");
  if(!p)return;

  p.innerHTML=state.files.map((f,i)=>`
    <div class="file-chip">
      📎 ${esc(f.name)}
      <button data-file="${i}">×</button>
    </div>`).join("");

  qsa("[data-file]",p).forEach(b=>b.onclick=()=>{
    state.files.splice(+b.dataset.file,1);
    b.parentElement.remove();
  });
});

qsa("[data-close]").forEach(b=>b.onclick=()=>hideModal(b.dataset.close));

bind("enterToggle","change",e=>state.enterToSend=e.target.checked);

bind("actionsToggle","change",e=>{
  state.showActions=e.target.checked;
  renderMessages();
});

bind("authButton","click",async()=>{
  if(!window.BrainAuth){
    toast("Authentication unavailable");
    return;
  }

  if(BrainAuth.isAuthenticated()){
    try{
      await BrainAuth.signOut();
      state.chats=[];
      state.current=null;
      state.messages=[];
      renderChats();
      renderWelcome();
      toast("Signed out");
    }catch(e){
      toast(e.message||"Sign out failed");
    }
  }else if(BrainAuth.openLogin){
    BrainAuth.openLogin();
  }else{
    toast("Please sign in");
  }
});

async function init(){
  try{
    if(window.BrainAuth)await BrainAuth.init();
    await loadChats();

    const id=new URLSearchParams(location.search).get("chat");

    if(id)await openChat(id);
    else renderWelcome();

    if(window.BrainAuth){
      BrainAuth.onAuthStateChange(async()=>{
        await loadChats();
        if(!state.messages.length)renderWelcome();
      });
    }
  }catch(e){
    console.error("App initialization:",e);
    renderWelcome();
  }
}

init();