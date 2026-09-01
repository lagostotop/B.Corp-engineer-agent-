"use strict";

const $=id=>document.getElementById(id),API="";
let sending=false,file=null,controller=null,currentChatId=null,lastQuestion="";

document.addEventListener("DOMContentLoaded",async()=>{
  events();
  await window.initAuth?.();
});

function events(){
  $("uploadBtn")?.addEventListener("click",()=>$("fileInput")?.click());

  $("fileInput")?.addEventListener("change",e=>{
    file=e.target.files?.[0]||null;
    $("filePreview").style.display=file?"flex":"none";
    $("fileName").textContent=file?.name||"";
  });

  $("removeFileBtn")?.addEventListener("click",clearFile);
  $("newChatBtn")?.addEventListener("click",newChat);

  $("hamburgerBtn")?.addEventListener("click",()=>side(true));
  $("closeSidebarBtn")?.addEventListener("click",()=>side(false));
  $("sidebarOverlay")?.addEventListener("click",()=>side(false));

  $("stopBtn")?.addEventListener("click",stop);
  $("regenBtn")?.addEventListener("click",()=>{
    if(lastQuestion&&!sending)send(lastQuestion,true);
  });

  $("chatForm")?.addEventListener("submit",e=>{
    e.preventDefault();
    send();
  });

  $("userInput")?.addEventListener("input",grow);

  $("userInput")?.addEventListener("keydown",e=>{
    if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){
      e.preventDefault();
      send();
    }
  });

  window.addEventListener("resize",()=>{
    if(innerWidth>1100)side(false);
  });
}

function side(show){
  $("sidebar")?.classList.toggle("show",show);
  $("sidebarOverlay")?.classList.toggle("show",show&&innerWidth<=1100);
}

function grow(){
  const x=$("userInput");
  if(!x)return;
  x.style.height="auto";
  x.style.height=Math.min(x.scrollHeight,180)+"px";
}

function clearFile(){
  file=null;
  if($("fileInput"))$("fileInput").value="";
  if($("filePreview"))$("filePreview").style.display="none";
  if($("fileName"))$("fileName").textContent="";
}

function uuid(){
  return crypto.randomUUID?.()||
  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g,c=>{
    const r=Math.random()*16|0;
    return (c==="x"?r:r&3|8).toString(16);
  });
}

async function loadChats(){
  try{
    const r=await fetch(`${API}/api/chats`,{cache:"no-store"});
    if(r.status===401){
      window.brainAuth?.showLoginModal();
      return;
    }
    if(!r.ok)return;

    const chats=await r.json(),list=$("chatList");
    if(!list)return;

    list.innerHTML=chats?.length?"":
      '<div class="empty-chats">No conversations yet</div>';

    chats?.forEach(c=>{
      if(!c?.id)return;

      const item=document.createElement("div");
      item.className="chat-item"+
        (String(c.id)===String(currentChatId)?" active":"");

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

      list.append(item);
    });
  }catch(e){
    console.error("Chats:",e);
  }
}

async function loadChat(id){
  if(!id||sending)return;

  try{
    const r=await fetch(
      `${API}/api/chat/${encodeURIComponent(id)}`,
      {cache:"no-store"}
    );

    if(r.status===401){
      window.brainAuth?.showLoginModal();
      return;
    }

    if(!r.ok)throw Error(`Server ${r.status}`);

    const msgs=await r.json();
    currentChatId=id;

    $("chatBox").innerHTML="";

    msgs?.forEach(m=>{
      if(m?.role==="user")add("user",m.content);
      if(m?.role==="assistant")add("ai",m.content);
    });

    await loadChats();

    if(innerWidth<=1100)side(false);
  }catch(e){
    console.error("Chat:",e);
  }
}

async function newChat(){
  stop();
  currentChatId=null;
  lastQuestion="";
  clearFile();

  $("chatBox").innerHTML="";
  await loadChats();

  if(innerWidth<=1100)side(false);
}

async function deleteChat(id){
  if(!id||!confirm("Delete this conversation?"))return;

  try{
    const r=await fetch(`${API}/api/chat/delete`,{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({chat_id:id})
    });

    if(r.status===401){
      window.brainAuth?.showLoginModal();
      return;
    }

    if(!r.ok)throw Error();

    if(String(currentChatId)===String(id))
      await newChat();
    else
      await loadChats();

  }catch{
    alert("Could not delete conversation");
  }
}

function render(text){
  if(!text)return"";

  const x=String(text)
    .replace(/Agent Research Results:/gi,"")
    .trim();

  if(!window.marked||!window.DOMPurify){
    const d=document.createElement("div");
    d.textContent=x;
    return d.innerHTML.replace(/\n/g,"<br>");
  }

  return DOMPurify.sanitize(marked.parse(x),{
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

function add(role,text){
  const box=$("chatBox");
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

    msg.append(content);
    row.append(avatar,msg);

    const tools=document.createElement("div");
    tools.className="copy-row";

    const copy=document.createElement("button");
    copy.className="copy-btn";
    copy.type="button";
    copy.textContent="Copy";

    copy.onclick=async()=>{
      try{
        await navigator.clipboard.writeText(content.innerText||"");
        copy.textContent="Copied";
        setTimeout(()=>copy.textContent="Copy",1500);
      }catch{
        copy.textContent="Failed";
      }
    };

    tools.append(copy);
    wrap.append(row,tools);
    box.append(wrap);
    bottom();

    return content;
  }

  const msg=document.createElement("div");
  msg.className="message user-msg";
  msg.textContent=text;

  row.append(msg);
  wrap.append(row);
  box.append(wrap);
  bottom();

  return msg;
}

function bottom(){
  const x=$("chatBox");
  if(x)requestAnimationFrame(()=>x.scrollTop=x.scrollHeight);
}

function state(v){
  sending=v;

  $("sendBtn").disabled=v;
  $("stopBtn").style.display=v?"inline-flex":"none";
  $("regenBtn").style.display=!v&&lastQuestion?"inline-flex":"none";
}

function stop(){
  controller?.abort();
  controller=null;
  state(false);
}

async function send(question=null,regen=false){
  if(sending)return;

  const input=$("userInput");
  const q=question!==null?
    String(question).trim():
    input.value.trim();

  const attached=file;

  if(!q&&!attached)return;

  lastQuestion=q;
  state(true);

  if(!regen){
    let display=q;

    if(attached)
      display+=(display?"\n":"")+`📎 ${attached.name}`;

    add("user",display);
  }

  input.value="";
  input.style.height="auto";

  const form=new FormData();

  form.append("question",q);
  form.append("client_msg_id",uuid());
  form.append("is_regen",regen?"1":"0");

  if(currentChatId!=null)
    form.append("chat_id",String(currentChatId));

  if(attached)
    form.append("file",attached,attached.name);

  clearFile();

  const ai=add("ai","");
  controller=new AbortController();

  try{
    const r=await fetch(`${API}/api/chat`,{
      method:"POST",
      headers:{Accept:"text/event-stream"},
      body:form,
      signal:controller.signal,
      cache:"no-store"
    });

    if(r.status===401){
      window.brainAuth?.showLoginModal();
      throw new Error("Please login to continue");
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

      else if(type==="chat_id"){
        if(p.chat_id)currentChatId=p.chat_id;
      }

      else if(type==="done"){
        if(p.chat_id)currentChatId=p.chat_id;
        loadChats();
      }

      else if(type==="error"){
        throw Error(p.message||"AI error");
      }
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

window.loadChats=loadChats;
window.loadSidebar=loadChats;
