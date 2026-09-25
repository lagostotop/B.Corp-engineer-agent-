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
function resizeTextarea(){
const input=el.messageInput;
if(!input)return;
input.style.height="auto";
input.style.height=Math.min(input.scrollHeight,190)+"px";
}

async function readSSE(stream,onEvent){
const reader=stream.getReader();
const decoder=new TextDecoder();
let buffer="";

while(true){
const{value,done}=await reader.read();
if(done)break;

buffer+=decoder.decode(value,{stream:true});

const blocks=buffer.split("\n\n");
buffer=blocks.pop()||"";

for(const block of blocks){
let event="message";
let data="";

for(const line of block.split("\n")){
if(line.startsWith("event:"))
event=line.slice(6).trim();
else if(line.startsWith("data:"))
data+=line.slice(5).trim();
}

if(!data)continue;

let parsed;
try{parsed=JSON.parse(data)}
catch{parsed={text:data}};

onEvent({event,data:parsed});
}
}

if(buffer.trim()){
let event="message";
let data="";

for(const line of buffer.split("\n")){
if(line.startsWith("event:"))event=line.slice(6).trim();
else if(line.startsWith("data:"))data+=line.slice(5).trim();
}

if(data){
let parsed;
try{parsed=JSON.parse(data)}
catch{parsed={text:data}};
onEvent({event,data:parsed});
}
}
}

async function sendMessage(){
if(state.sending)return;

const question=el.messageInput.value.trim();
const file=state.selectedFile;

if(!question&&!file)return;

if(!authenticated()){
showAuth();
return;
}

state.sending=true;
state.controller=new AbortController();

el.sendButton.disabled=true;
el.messageInput.disabled=true;
el.attachButton.disabled=true;
status("Thinking...");

const visibleText=question||(file?`Uploaded ${file.name}`:"");
addMessage("user",visibleText);

el.messageInput.value="";
resizeTextarea();

const assistant=addMessage("assistant","");
const assistantIndex=state.messages.length-1;

try{
const form=new FormData();

form.append("question",question);

if(state.chatId)
form.append("chat_id",String(state.chatId));

if(file)
form.append("file",file);

const response=await api("/api/chat",{
method:"POST",
body:form,
signal:state.controller.signal,
headers:{Accept:"text/event-stream"}
});

if(response.status===401){
handleLogout();
throw new Error("Your session expired. Please sign in again.");
}

if(!response.ok){
const data=await responseData(response);
throw new Error(errorText(data,`Request failed (${response.status})`));
}

if(!response.body)
throw new Error("Streaming is not supported by this browser.");

await readSSE(response.body,event=>{
if(event.event==="chat_id"){
if(event.data?.chat_id){
state.chatId=String(event.data.chat_id);
renderChats();
}
return;
}

if(event.event==="token"){
const text=event.data?.text||event.data?.token||"";
if(!text)return;

state.messages[assistantIndex].content+=text;
assistant.body.innerHTML=markdown(state.messages[assistantIndex].content);
scrollBottom();
return;
}

if(event.event==="message"){
const text=event.data?.text||event.data?.message||"";
if(!text)return;

state.messages[assistantIndex].content+=text;
assistant.body.innerHTML=markdown(state.messages[assistantIndex].content);
scrollBottom();
return;
}

if(event.event==="error"){
throw new Error(event.data?.message||"Brain generation failed.");
}
});

if(state.chatId)await loadChats();

status("Ready");
resetFile();

}catch(error){
if(error.name==="AbortError"){
status("Stopped");
}else{
console.error("sendMessage:",error);

if(assistant.body){
assistant.body.innerHTML=
`<p style="color:#fb7185">${escapeHtml(errorText(error,"Brain generation failed."))}</p>`;
}

status("Error");
}
}finally{
state.sending=false;
state.controller=null;

el.sendButton.disabled=false;
el.messageInput.disabled=false;
el.attachButton.disabled=false;

el.sendButton.innerHTML=`
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
<path d="M22 2 11 13"/>
<path d="m22 2-7 20-4-9-9-4Z"/>
</svg>`;

el.messageInput.focus();
}
}

function handleLogout(){
state.chatId=null;
state.chats=[];
state.messages=[];
clearMessages();
renderChats();
updateUserUI(null);
status("Signed out");
closeSidebar();
}

async function authLogin(event){
event.preventDefault();

try{
showAuthError("");
status("Signing in...");

await window.BrainAuth.signIn(
el.loginEmail.value,
el.loginPassword.value
);

hideAuth();
updateUserUI(authUser());
await loadChats();

status("Ready");
el.messageInput.focus();
}catch(error){
showAuthError(error);
status("Authentication error");
}
}

async function authSignup(event){
event.preventDefault();

try{
showAuthError("");
status("Creating account...");

const result=await window.BrainAuth.signUp(
el.signupEmail.value,
el.signupPassword.value,
{
data:{
full_name:el.signupName.value.trim()
}
}
);

if(!result.session){
showAuthError("Account created. Check your email if confirmation is required.");
return;
}

hideAuth();
updateUserUI(authUser());
await loadChats();
status("Ready");
}catch(error){
showAuthError(error);
status("Authentication error");
}
}

async function authButtonAction(){
if(authenticated()){
try{
await window.BrainAuth.signOut();
handleLogout();
}catch(error){
showAuthError(error);
}
}else{
showAuth();
}
}

function voiceInput(){
const SpeechRecognition=
window.SpeechRecognition||
window.webkitSpeechRecognition;

if(!SpeechRecognition){
status("Voice input is not supported");
return;
}

const recognition=new SpeechRecognition();
recognition.lang="en-US";
recognition.interimResults=true;

status("Listening...");

recognition.onresult=e=>{
let text="";

for(const result of e.results)
text+=result[0].transcript;

el.messageInput.value=text;
resizeTextarea();
};

recognition.onerror=()=>{
status("Voice input failed");
};

recognition.onend=()=>{
if(!state.sending)status("Ready");
};

recognition.start();
}

function filterChats(){
const query=prompt("Search conversations:");

if(query===null)return;

const q=query.trim().toLowerCase();

if(!q){
renderChats();
return;
}

const original=state.chats;

const matches=original.filter(chat=>
String(chat.title||chat.name||"")
.toLowerCase()
.includes(q)
);

el.chatList.innerHTML="";

if(!matches.length){
const empty=document.createElement("div");
empty.className="chat-empty";
empty.textContent="No matching conversations";
el.chatList.appendChild(empty);
return;
}

for(const chat of matches){
const item=document.createElement("div");
item.className="chat-item"+(String(chat.id)===String(state.chatId)?" active":"");

const icon=document.createElement("span");
icon.className="chat-icon";
icon.textContent="◦";

const title=document.createElement("span");
title.className="chat-title";
title.textContent=chat.title||"New conversation";

item.append(icon,title);
item.onclick=()=>openChat(chat.id);
el.chatList.appendChild(item);
}
}

function bind(){
el.newChatButton?.addEventListener("click",newChat);
el.newChatTopButton?.addEventListener("click",newChat);
el.clearChatButton?.addEventListener("click",newChat);

el.mobileMenuButton?.addEventListener("click",openSidebar);
el.sidebarBackdrop?.addEventListener("click",closeSidebar);

el.chatSearchButton?.addEventListener("click",filterChats);

el.authButton?.addEventListener("click",authButtonAction);
el.authCloseButton?.addEventListener("click",hideAuth);

el.authModal?.addEventListener("click",e=>{
if(e.target===el.authModal)hideAuth();
});

el.authSwitchButton?.addEventListener("click",()=>{
const signup=el.signupForm.style.display!=="none";
showAuth(signup?"login":"signup");
});

el.loginForm?.addEventListener("submit",authLogin);
el.signupForm?.addEventListener("submit",authSignup);

el.attachButton?.addEventListener("click",()=>{
el.fileInput.click();
});

el.fileInput?.addEventListener("change",()=>{
chooseFile(el.fileInput.files?.[0]);
});

el.removeFileButton?.addEventListener("click",()=>{
resetFile();
status("Ready");
});

el.voiceButton?.addEventListener("click",voiceInput);

el.messageInput?.addEventListener("input",resizeTextarea);

el.messageInput?.addEventListener("keydown",e=>{
if(e.key==="Enter"&&!e.shiftKey){
e.preventDefault();
sendMessage();
}
});

document.getElementById("composerForm")?.addEventListener("submit",e=>{
e.preventDefault();
sendMessage();
});

document.querySelectorAll("[data-prompt]").forEach(button=>{
button.addEventListener("click",()=>{
el.messageInput.value=button.dataset.prompt||"";
resizeTextarea();
el.messageInput.focus();
});
});

document.addEventListener("keydown",e=>{
if(e.key==="Escape"){
hideAuth();
closeSidebar();
}
});

let startX=0;

el.sidebar?.addEventListener("touchstart",e=>{
startX=e.touches[0].clientX;
},{passive:true});

el.sidebar?.addEventListener("touchend",e=>{
const endX=e.changedTouches[0].clientX;

if(startX-endX>70)
closeSidebar();
},{passive:true});

document.addEventListener("touchstart",e=>{
state.touchStartX=e.touches[0].clientX;
state.touchStartY=e.touches[0].clientY;
},{passive:true});

document.addEventListener("touchend",e=>{
const endX=e.changedTouches[0].clientX;
const endY=e.changedTouches[0].clientY;

const dx=endX-state.touchStartX;
const dy=Math.abs(endY-state.touchStartY);

if(dy>80)return;

if(window.innerWidth<=900){
if(dx>80&&state.touchStartX<35){
openSidebar();
}else if(dx<-80&&el.sidebar.classList.contains("open")){
closeSidebar();
}
}
},{passive:true});
}

async function init(){
bind();
resizeTextarea();

if(!window.BrainAuth){
status("Authentication unavailable");
return;
}

try{
const user=await window.BrainAuth.init();

updateUserUI(user);

window.BrainAuth.onAuthStateChange(async currentUser=>{
updateUserUI(currentUser);

if(currentUser){
await loadChats();
}else{
handleLogout();
}
});

if(user){
await loadChats();
status("Ready");
}else{
status("Sign in to chat");
}
}catch(error){
console.error(error);
status("Ready");
}
}

if(document.readyState==="loading")
document.addEventListener("DOMContentLoaded",init);
else
init();

})();