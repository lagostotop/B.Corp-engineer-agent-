"use strict";

const $=id=>document.getElementById(id);
const API="";
const M=!!window.marked,P=!!window.DOMPurify;

let sending=false,file=null,controller=null,currentChatId=null,lastQuestion="";

document.addEventListener("DOMContentLoaded",async()=>{
  events();
  try{await window.initAuth?.()}catch(e){console.error(e)}
});

function auth(){return window.authToken?.()||""}
function headers(json=false){
  return {...(json?{"Content-Type":"application/json"}:{}),...window.getAuthHeaders?.()};
}

function showAuthScreen(){
  $("authScreen").style.display="flex";
  $("chatContainer").style.display="none";
}

function showChatScreen(){
  $("authScreen").style.display="none";
  $("chatContainer").style.display="flex";
  loadChats();
}

window.showAuthScreen=showAuthScreen;
window.showChatScreen=showChatScreen;

function events(){
  $("uploadBtn")?.addEventListener("click",()=>$("fileInput")?.click());
  $("fileInput")?.addEventListener("change",e=>{
    file=e.target.files?.[0]||null;
    $("filePreview").style.display=file?"flex":"none";
    $("fileName").textContent=file?.name||"";
  });

  $("removeFileBtn")?.addEventListener("click",clearFile);
  $("newChatBtn")?.addEventListener("click",newChat);
  $("logoutBtn")?.addEventListener("click",window.doLogout);
  $("loginBtn")?.addEventListener("click",window.doLogin);
  $("signupBtn")?.addEventListener("click",window.doSignup);

  $("hamburgerBtn")?.addEventListener("click",()=>toggleSide(true));
  $("closeSidebarBtn")?.addEventListener("click",()=>toggleSide(false));
  $("sidebarOverlay")?.addEventListener("click",()=>toggleSide(false));

  $("stopBtn")?.addEventListener("click",stop);
  $("regenBtn")?.addEventListener("click",()=>lastQuestion&&!sending&&send(lastQuestion,true));

  $("chatForm")?.addEventListener("submit",e=>{
    e.preventDefault();
    send();
  });

  $("userInput")?.addEventListener("input",autoGrow);
  $("userInput")?.addEventListener("keydown",e=>{
    if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){
      e.preventDefault();
      send();
    }
  });

  // REMOVED: welcome-chip click handler because we removed welcome UI

  window.addEventListener("resize",()=>{
    if(innerWidth>=769) toggleSide(false);
  });
}

function toggleSide(show){
  $("sidebar")?.classList.toggle("show",show);
  $("sidebarOverlay")?.classList.toggle("show",show&&innerWidth<769);
}

function autoGrow(){
  const x=$("userInput");
  x.style.height="auto";
  x.style.height=Math.min(x.scrollHeight,180)+"px";
}

function clearFile(){
  file=null;
  if($("fileInput"))$("fileInput").value="";
  $("filePreview").style.display="none";
  $("fileName").textContent="";
}

function uuid(){
  if(crypto.randomUUID)return crypto.randomUUID();
  return"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g,c=>{
    const r=Math.random()*16|0,v=c==="x"?r:r&3|8;
    return v.toString(16);
  });
}

async function loadChats(){
  if(!auth())return;
  try{
    const r=await fetch(`${API}/api/chats`,{
      headers:headers(),cache:"no-store"
    });
    if(r.status===401)return window.doLogout?.();
    if(!r.ok)return;

    const chats=await r.json();
    const list=$("chatList");
    list.innerHTML="";

    if(!chats.length){
      list.innerHTML='<div style="padding:12px;color:#64748b;font-size:12px">No conversations yet</div>';
      return;
    }

    chats.forEach(c=>{
      if(!c?.id)return;

      const item=document.createElement("div");
      item.className="chat-item"+(String(c.id)===String(currentChatId)?" active":"");

      const title=document.createElement("span");
      title.className="chat-item-title";
      title.textContent=c.title||"New conversation";

      const del=document.createElement("button");
      del.className="chat-delete";
      del.type="button";
      del.textContent="×";

      item.append(title,del);
      item.onclick=()=>loadChat(c.id);
      del.onclick=e=>{
        e.stopPropagation();
        deleteChat(c.id);
      };

      list.appendChild(item);
    });
  }catch(e){console.error("Chats:",e)}
}

async function loadChat(id){
  if(!id||sending)return;

  try{
    const r=await fetch(`${API}/api/chat/${encodeURIComponent(id)}`,{
      headers:headers(),cache:"no-store"
    });

    if(r.status===401)return window.doLogout?.();
    if(!r.ok)throw Error(`Server ${r.status}`);

    const msgs=await r.json();
    currentChatId=id;

    const box=$("chatBox");
    box.innerHTML=""; // CLEAN START - NO WELCOME

    msgs.forEach(m=>{
      if(m?.role==="user")addMessage("user",m.content);
      if(m?.role==="assistant")addMessage("ai",m.content);
    });

    // REMOVED: if(!msgs.length)welcome(); 
    await loadChats();

    if(innerWidth<769)toggleSide(false);
  }catch(e){console.error("Load chat:",e)}
}

async function newChat(){
  stop();
  currentChatId=null;
  lastQuestion="";
  clearFile();

  $("chatBox").innerHTML=""; // CLEAN START - NO WELCOME
  await loadChats();

  if(innerWidth<769)toggleSide(false);
}

async function deleteChat(id){
  if(!id||!confirm("Delete this conversation?"))return;

  try{
    const r=await fetch(`${API}/api/chat/delete`,{
      method:"POST",
      headers:headers(true),
      body:JSON.stringify({chat_id:id})
    });

    if(r.status===401)return window.doLogout?.();
    if(!r.ok)throw Error();

    if(String(currentChatId)===String(id))await newChat();
    else await loadChats();
  }catch(e){alert("Could not delete conversation")}
}

// REMOVED: welcome() function completely. No more big brain

function addMessage(role,text){
  // REMOVED: $("welcomeScreen")?.remove();

  const wrap=document.createElement("div");
  wrap.className=`message-wrap ${role}`;

  const row=document.createElement("div");
  row.className="message-row";

  if(role==="ai"){
    const avatar=document.createElement("div");
    avatar.className="message-avatar ai-avatar";
    avatar.innerHTML='<img src="/static/brain3d.png" alt="Brain">';

    const msg=document.createElement("div");
    msg.className="message ai-msg";

    const content=document.createElement("div");
    content.className="msg-content";
    content.innerHTML=render(text);

    msg.appendChild(content);
    row.append(avatar,msg);

    const copy=document.createElement("button");
    copy.className="copy-btn";
    copy.type="button";
    copy.textContent="Copy";
    copy.onclick=()=>copyMessage(content,copy);

    const tools=document.createElement("div");
    tools.className="copy-row";
    tools.appendChild(copy);

    wrap.append(row,tools);
    $("chatBox").appendChild(wrap);
    bottom();

    return content;
  }

  const msg=document.createElement("div");
  msg.className="message user-msg";
  msg.textContent=text;

  row.appendChild(msg);
  wrap.appendChild(row);
  $("chatBox").appendChild(wrap);
  bottom();

  return msg;
}

function render(text){
  if(!text)return"";

  let clean=String(text)
   .replace(/Agent Research Results:/gi,"")
   .trim();

  if(!M||!P){
    const d=document.createElement("div");
    d.textContent=clean;
    return d.innerHTML.replace(/\n/g,"<br>");
  }

  const html=marked.parse(clean);

  return DOMPurify.sanitize(html,{
    ALLOWED_TAGS:[
      "p","br","strong","em","del",
      "h1","h2","h3","h4",
      "ul","ol","li","blockquote",
      "pre","code","a",
      "table","thead","tbody","tr","th","td"
    ],
    ALLOWED_ATTR:["href","target","rel"]
  });
}

async function copyMessage(content,btn){
  try{
    await navigator.clipboard.writeText(content.innerText||"");
    btn.textContent="Copied";
    setTimeout(()=>btn.textContent="Copy",1500);
  }catch{
    btn.textContent="Failed";
  }
}

function bottom(){
  const box=$("chatBox");
  requestAnimationFrame(()=>box.scrollTop=box.scrollHeight);
}

function state(on){
  sending=on;

  $("sendBtn").disabled=on;
  $("stopBtn").style.display=on?"inline-flex":"none";
  $("regenBtn").style.display=!on&&lastQuestion?"inline-flex":"none";
}

function stop(){
  controller?.abort();
  controller=null;
  state(false);
}

async function send(question=null,regen=false){
  if(sending)return;

  const input=$("userInput");
  const q=question!==null?String(question).trim():input.value.trim();
  const attached=file;

  if(!q&&!attached)return;
  if(!auth())return window.showAuthScreen?.();

  lastQuestion=q;
  state(true);

  if(!regen){
    let display=q;
    if(attached)display+=(display?"\n":"")+`📎 ${attached.name}`;
    addMessage("user",display);
  }

  input.value="";
  input.style.height="auto";

  const cid=uuid();
  const form=new FormData();

  form.append("question",q);
  form.append("client_msg_id",cid);
  form.append("is_regen",regen?"1":"0");

  if(currentChatId!=null)
    form.append("chat_id",String(currentChatId));

  if(attached)
    form.append("file",attached,attached.name);

  clearFile();

  const ai=addMessage("ai","");
  controller=new AbortController();

  try{
    const r=await fetch(`${API}/api/chat`,{
      method:"POST",
      headers:{
        Authorization:`Bearer ${auth()}`,
        Accept:"text/event-stream"
      },
      body:form,
      signal:controller.signal,
      cache:"no-store"
    });

    if(r.status===401){
      window.doLogout?.();
      throw Error("Session expired");
    }

    if(r.status===403)throw Error("Access denied");
    if(r.status===409)throw Error("Duplicate message");
    if(!r.ok)throw Error(`Server ${r.status}`);
    if(!r.body)throw Error("Streaming unavailable");

    const reader=r.body.getReader();
    const decoder=new TextDecoder();

    let buffer="",full="";

    const event=raw=>{
      if(!raw.trim())return;

      let type="message",data="";

      raw.split("\n").forEach(line=>{
        if(line.startsWith("event:"))
          type=line.slice(6).trim();

        if(line.startsWith("data:"))
          data+=line.slice(5).trim();
      });

      if(!data)return;

      let p;
      try{p=JSON.parse(data)}catch{return}

      if(type==="token"){
        full+=p.text||"";
        ai.innerHTML=render(full);
        bottom();
      }

      if(type==="chat_id"&&p.chat_id)
        currentChatId=p.chat_id;

      if(type==="done"){
        if(p.chat_id)currentChatId=p.chat_id;
        loadChats();
      }

      if(type==="error")
        throw Error(p.message||"AI error");
    };

    while(true){
      const {value,done}=await reader.read();

      if(done){
        buffer+=decoder.decode();
        if(buffer)event(buffer);
        break;
      }

      buffer+=decoder.decode(value,{stream:true});
      buffer=buffer.replace(/\r\n/g,"\n");

      const parts=buffer.split("\n\n");
      buffer=parts.pop()||"";
      parts.forEach(event);
    }

  }catch(e){
    if(e.name==="AbortError"){
      ai.innerHTML="<em>Generation stopped.</em>";
    }else{
      console.error(e);
      ai.innerHTML=render(`**Error**\n\n${e.message}`);
    }
  }finally{
    controller=null;
    state(false);
  }
}
