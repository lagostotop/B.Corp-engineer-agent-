(()=>{
"use strict";

const state={
chatId:null,
chats:[],
messages:[],
selectedFile:null,
sending:false,
controller:null,
searching:false,
touchStartX:0,
touchStartY:0
};

const $=id=>document.getElementById(id);

const el={
sidebar:$("sidebar"),
sidebarBackdrop:$("sidebarBackdrop"),
mobileMenuButton:$("mobileMenuButton"),
newChatButton:$("newChatButton"),
newChatTopButton:$("newChatTopButton"),
clearChatButton:$("clearChatButton"),
chatSearchButton:$("chatSearchButton"),
chatList:$("chatList"),
messages:$("messages"),
welcomeMessage:$("welcomeMessage"),
chatContainer:$("chatContainer"),
messageInput:$("messageInput"),
sendButton:$("sendButton"),
attachButton:$("attachButton"),
voiceButton:$("voiceButton"),
fileInput:$("fileInput"),
filePreview:$("filePreview"),
fileName:$("fileName"),
fileMeta:$("fileMeta"),
removeFileButton:$("removeFileButton"),
connectionStatus:$("connectionStatus"),
authButton:$("authButton"),
authModal:$("authModal"),
authCloseButton:$("authCloseButton"),
authSwitchButton:$("authSwitchButton"),
loginForm:$("loginForm"),
signupForm:$("signupForm"),
loginEmail:$("loginEmail"),
loginPassword:$("loginPassword"),
signupName:$("signupName"),
signupEmail:$("signupEmail"),
signupPassword:$("signupPassword"),
authTitle:$("authTitle"),
authSubtitle:$("authSubtitle"),
authError:$("authError"),
userAvatar:$("userAvatar"),
userName:$("userName"),
userEmail:$("userEmail")
};

const allowedExtensions=new Set([
"pdf","txt","md","py","js","ts","jsx","tsx",
"html","css","csv","json","png","jpg","jpeg","docx"
]);

function status(text){
if(el.connectionStatus)el.connectionStatus.textContent=text;
}

function errorText(value,fallback="Something went wrong."){
if(value instanceof Error)return value.message||fallback;
if(typeof value==="string")return value.trim()||fallback;
if(value?.message)return String(value.message);
if(typeof value?.error==="string")return value.error;
if(value?.error?.message)return String(value.error.message);
return fallback;
}

function escapeHtml(value){
return String(value??"")
.replace(/&/g,"&amp;")
.replace(/</g,"&lt;")
.replace(/>/g,"&gt;")
.replace(/"/g,"&quot;")
.replace(/'/g,"&#039;");
}

function markdown(value){
const text=String(value??"");
if(!window.marked)return escapeHtml(text).replace(/\n/g,"<br>");
const html=window.marked.parse(text,{breaks:true,gfm:true});
return window.DOMPurify?window.DOMPurify.sanitize(html):html;
}

function scrollBottom(){
requestAnimationFrame(()=>{
if(el.chatContainer)
el.chatContainer.scrollTop=el.chatContainer.scrollHeight;
});
}

function authenticated(){
return Boolean(window.BrainAuth?.getUser?.());
}

function authUser(){
return window.BrainAuth?.getUser?.()||null;
}

function api(url,options={}){
if(window.BrainAuth?.fetchWithAuth)
return window.BrainAuth.fetchWithAuth(url,options);
return fetch(url,options);
}

async function responseData(response){
const text=await response.text();
if(!text)return{};
try{return JSON.parse(text)}
catch{return{error:text}};
}

function addMessage(role,content=""){
const wrapper=document.createElement("div");
wrapper.className=`message ${role}`;

const avatar=document.createElement("div");
avatar.className="message-avatar";
avatar.textContent=role==="user"?"YOU":"B";

const body=document.createElement("div");
body.className="message-content";

if(role==="user")body.textContent=content;
else body.innerHTML=markdown(content);

wrapper.append(avatar,body);
el.messages.appendChild(wrapper);

const item={role,content:String(content??"")};
state.messages.push(item);

updateWelcome();
scrollBottom();

return{wrapper,body,item};
}

function clearMessages(){
state.messages=[];
if(!el.messages)return;
el.messages.innerHTML="";
if(el.welcomeMessage)el.messages.appendChild(el.welcomeMessage);
updateWelcome();
}

function renderMessages(messages){
clearMessages();
for(const m of messages||[]){
if(m.role==="user"||m.role==="assistant")
addMessage(m.role,m.content||"");
}
scrollBottom();
}

function updateWelcome(){
if(el.welcomeMessage)
el.welcomeMessage.style.display=state.messages.length?"none":"block";
}

function updateUserUI(user){
if(!user){
if(el.userAvatar)el.userAvatar.textContent="?";
if(el.userName)el.userName.textContent="Guest";
if(el.userEmail)el.userEmail.textContent="Not signed in";
if(el.authButton)el.authButton.textContent="Login";
return;
}

const meta=user.user_metadata||{};
const name=meta.full_name||meta.name||user.email?.split("@")[0]||"User";

if(el.userAvatar)el.userAvatar.textContent=name.charAt(0).toUpperCase();
if(el.userName)el.userName.textContent=name;
if(el.userEmail)el.userEmail.textContent=user.email||"";
if(el.authButton)el.authButton.textContent="Logout";
}

function showAuth(mode="login"){
if(!el.authModal)return;
el.authModal.style.display="flex";
if(mode==="signup"){
el.loginForm.style.display="none";
el.signupForm.style.display="flex";
el.authTitle.textContent="Create your account";
el.authSubtitle.textContent="Create an account to start using Brain 3.0.";
el.authSwitchButton.textContent="Already have an account? Sign in";
}else{
el.loginForm.style.display="flex";
el.signupForm.style.display="none";
el.authTitle.textContent="Welcome back";
el.authSubtitle.textContent="Sign in to continue using Brain 3.0.";
el.authSwitchButton.textContent="Create an account";
}
el.authError.textContent="";
}

function hideAuth(){
if(el.authModal)el.authModal.style.display="none";
}

function showAuthError(value){
if(el.authError)el.authError.textContent=errorText(value,"");
}

function openSidebar(){
el.sidebar?.classList.add("open");
el.sidebarBackdrop?.classList.add("show");
}

function closeSidebar(){
el.sidebar?.classList.remove("open");
el.sidebarBackdrop?.classList.remove("show");
}

function formatBytes(bytes){
if(!bytes)return"0 B";
const units=["B","KB","MB","GB"];
const i=Math.min(Math.floor(Math.log(bytes)/Math.log(1024)),3);
return`${(bytes/1024**i).toFixed(i?1:0)} ${units[i]}`;
}

function resetFile(){
state.selectedFile=null;
if(el.fileInput)el.fileInput.value="";
if(el.filePreview)el.filePreview.style.display="none";
if(el.fileName)el.fileName.textContent="";
if(el.fileMeta)el.fileMeta.textContent="";
}

function chooseFile(file){
if(!file)return;
const ext=file.name.split(".").pop()?.toLowerCase()||"";

if(!allowedExtensions.has(ext)){
status("Unsupported file type");
return;
}

if(file.size>10*1024*1024){
status("File exceeds 10 MB");
return;
}

state.selectedFile=file;
el.fileName.textContent=file.name;
el.fileMeta.textContent=formatBytes(file.size);
el.filePreview.style.display="flex";
status("File attached");
}

async function loadChats(){
if(!authenticated()){
state.chats=[];
renderChats();
return;
}

try{
const response=await api("/api/chats");
if(response.status===401){
handleLogout();
return;
}

const data=await responseData(response);
if(!response.ok)throw new Error(errorText(data));

state.chats=Array.isArray(data)?data:(data.chats||[]);
renderChats();
}catch(error){
console.error(error);
status("Unable to load chats");
}
}

function renderChats(){
if(!el.chatList)return;
el.chatList.innerHTML="";

if(!state.chats.length){
const empty=document.createElement("div");
empty.className="chat-empty";
empty.textContent=authenticated()?"No conversations yet":"Sign in to see your conversations";
el.chatList.appendChild(empty);
return;
}

for(const chat of state.chats){
const item=document.createElement("div");
item.className="chat-item"+(String(chat.id)===String(state.chatId)?" active":"");

const icon=document.createElement("span");
icon.className="chat-icon";
icon.textContent="◦";

const title=document.createElement("span");
title.className="chat-title";
title.textContent=chat.title||chat.name||"New conversation";

const del=document.createElement("button");
del.className="chat-delete";
del.type="button";
del.title="Delete chat";
del.textContent="×";

del.onclick=e=>{
e.stopPropagation();
deleteChat(chat.id);
};

item.append(icon,title,del);
item.onclick=()=>openChat(chat.id);
el.chatList.appendChild(item);
}
}

function newChat(){
if(!authenticated()){
showAuth();
return;
}

state.chatId=null;
state.messages=[];
if(state.controller)state.controller.abort();

clearMessages();
resetFile();
renderChats();
status("Ready");
closeSidebar();
el.messageInput?.focus();
}

async function openChat(id){
if(!authenticated()){
showAuth();
return;
}

try{
status("Loading...");
const response=await api(`/api/chat/${encodeURIComponent(id)}`);
const data=await responseData(response);

if(!response.ok)throw new Error(errorText(data,"Unable to load conversation."));

state.chatId=String(id);
renderMessages(Array.isArray(data)?data:data.messages||[]);
renderChats();
status("Ready");
closeSidebar();
}catch(error){
console.error(error);
status("Unable to load chat");
}
}

async function deleteChat(id){
if(!authenticated())return;

if(!confirm("Delete this conversation?"))return;

try{
const response=await api("/api/chat/delete",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({chat_id:String(id)})
});

const data=await responseData(response);

if(!response.ok)throw new Error(errorText(data,"Unable to delete chat."));

if(String(state.chatId)===String(id)){
state.chatId=null;
clearMessages();
}

await loadChats();
status("Ready");
}catch(error){
console.error(error);
alert(errorText(error,"Unable to delete chat."));
}
}