(()=>{
"use strict";

const state={
chatId:null,
chats:[],
messages:[],
selectedFile:null,
sending:false,
controller:null,
authReady:false
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

function setStatus(text){
if(el.connectionStatus)
el.connectionStatus.textContent=text;
}

function errorText(value,fallback="Something went wrong."){
if(value instanceof Error)
return value.message||fallback;

if(typeof value==="string")
return value.trim()||fallback;

if(value&&typeof value==="object"){
if(typeof value.message==="string"&&value.message.trim())
return value.message.trim();

if(typeof value.error==="string"&&value.error.trim())
return value.error.trim();

if(value.error&&typeof value.error==="object"){
if(typeof value.error.message==="string")
return value.error.message;

if(typeof value.error.detail==="string")
return value.error.detail;
}

if(typeof value.detail==="string")
return value.detail;
}

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

function renderMarkdown(value){
const text=String(value??"");

if(!window.marked)
return escapeHtml(text).replace(/\n/g,"<br>");

const html=window.marked.parse(text,{
breaks:true,
gfm:true
});

return window.DOMPurify
?window.DOMPurify.sanitize(html)
:html;
}

function scrollToBottom(){
requestAnimationFrame(()=>{
if(el.chatContainer)
el.chatContainer.scrollTop=el.chatContainer.scrollHeight;
});
}

function updateWelcome(){
if(el.welcomeMessage)
el.welcomeMessage.style.display=
state.messages.length?"none":"block";
}

function createMessageElement(role,content=""){
const wrapper=document.createElement("div");
wrapper.className=`message ${role}`;

const avatar=document.createElement("div");
avatar.className="message-avatar";
avatar.textContent=role==="user"?"YOU":"B";

const body=document.createElement("div");
body.className="message-content";

if(role==="user")
body.textContent=content;
else
body.innerHTML=renderMarkdown(content);

wrapper.append(avatar,body);

return{wrapper,body};
}

function addMessage(role,content=""){
const message={
role,
content:String(content??"")
};

state.messages.push(message);

const rendered=createMessageElement(
role,
message.content
);

el.messages.appendChild(rendered.wrapper);

updateWelcome();
scrollToBottom();

return rendered;
}

function clearMessages(){
state.messages=[];

if(!el.messages)return;

el.messages.innerHTML="";

if(el.welcomeMessage)
el.messages.appendChild(el.welcomeMessage);

updateWelcome();
}

function renderMessages(messages){
clearMessages();

for(const message of messages||[]){
if(message.role!=="user"&&message.role!=="assistant")
continue;

addMessage(
message.role,
message.content
);
}

scrollToBottom();
}

function formatBytes(bytes){
if(!bytes)return"0 B";

const units=["B","KB","MB","GB"];
const index=Math.min(
Math.floor(Math.log(bytes)/Math.log(1024)),
units.length-1
);

return`${(bytes/Math.pow(1024,index)).toFixed(index?1:0)} ${units[index]}`;
}

function resetComposer(){
state.selectedFile=null;

if(el.fileInput)
el.fileInput.value="";

if(el.filePreview)
el.filePreview.style.display="none";

if(el.fileName)
el.fileName.textContent="";

if(el.fileMeta)
el.fileMeta.textContent="";
}

function selectFile(file){
if(!file)return;

const extension=file.name.includes(".")
?file.name.split(".").pop().toLowerCase()
:"";

if(!allowedExtensions.has(extension)){
setStatus("Unsupported file type");
return;
}

if(file.size>10*1024*1024){
setStatus("File exceeds 10 MB");
return;
}

state.selectedFile=file;

if(el.fileName)
el.fileName.textContent=file.name;

if(el.fileMeta)
el.fileMeta.textContent=formatBytes(file.size);

if(el.filePreview)
el.filePreview.style.display="flex";

setStatus("File attached");
}

function getAuthUser(){
return window.BrainAuth&&
typeof window.BrainAuth.getUser==="function"
?window.BrainAuth.getUser()
:null;
}

function isAuthenticated(){
return Boolean(getAuthUser());
}

function updateUserUI(user=null){
if(!user){
if(el.userName)el.userName.textContent="Guest";
if(el.userEmail)el.userEmail.textContent="Not signed in";
if(el.userAvatar)el.userAvatar.textContent="?";
if(el.authButton)el.authButton.textContent="Login";
return;
}

const metadata=user.user_metadata||{};

const name=
metadata.full_name||
metadata.name||
user.email?.split("@")[0]||
"User";

if(el.userName)
el.userName.textContent=name;

if(el.userEmail)
el.userEmail.textContent=user.email||"";

if(el.userAvatar)
el.userAvatar.textContent=name.charAt(0).toUpperCase();

if(el.authButton)
el.authButton.textContent="Logout";
}

function showAuthError(message){
if(el.authError)
el.authError.textContent=errorText(message,"");
}

function showLoginForm(){
if(el.loginForm)el.loginForm.style.display="flex";
if(el.signupForm)el.signupForm.style.display="none";

if(el.authTitle)
el.authTitle.textContent="Welcome back";

if(el.authSubtitle)
el.authSubtitle.textContent=
"Sign in to continue using Brain 3.0.";

if(el.authSwitchButton)
el.authSwitchButton.textContent="Create an account";
}

function showSignupForm(){
if(el.loginForm)el.loginForm.style.display="none";
if(el.signupForm)el.signupForm.style.display="flex";

if(el.authTitle)
el.authTitle.textContent="Create your account";

if(el.authSubtitle)
el.authSubtitle.textContent=
"Create an account to start using Brain 3.0.";

if(el.authSwitchButton)
el.authSwitchButton.textContent=
"Already have an account? Sign in";
}

function showAuthModal(mode="login"){
if(!el.authModal)return;

el.authModal.style.display="flex";

if(mode==="signup")
showSignupForm();
else
showLoginForm();

showAuthError("");
}

function hideAuthModal(){
if(el.authModal)
el.authModal.style.display="none";
}

async function apiFetch(url,options={}){
if(window.BrainAuth&&
typeof window.BrainAuth.fetchWithAuth==="function")
return window.BrainAuth.fetchWithAuth(url,options);

return fetch(url,options);
}

async function parseResponse(response){
const text=await response.text();

if(!text)return{};

try{
return JSON.parse(text);
}catch{
return{error:text};
}
}

async function loadChats(){
if(!isAuthenticated()){
state.chats=[];
renderChatList();
return;
}

try{
const response=await apiFetch("/api/chats");

if(response.status===401){
handleUnauthenticated();
return;
}

const data=await parseResponse(response);

if(!response.ok)
throw new Error(
errorText(data,`Failed to load chats (${response.status})`)
);

state.chats=Array.isArray(data)
?data
:Array.isArray(data.chats)
?data.chats
:[];

renderChatList();

}catch(error){
console.error("loadChats:",error);
setStatus("Unable to load chats");
}
}

function renderChatList(){
if(!el.chatList)return;

el.chatList.innerHTML="";

if(!state.chats.length){
const empty=document.createElement("div");
empty.className="chat-empty";
empty.textContent=
isAuthenticated()
?"No conversations yet"
:"Sign in to see your conversations";
el.chatList.appendChild(empty);
return;
}

for(const chat of state.chats){
const item=document.createElement("div");

item.className=
"chat-item"+
(String(chat.id)===String(state.chatId)
?" active":"");

item.dataset.chatId=chat.id;

const icon=document.createElement("span");
icon.className="chat-icon";
icon.textContent="◦";

const title=document.createElement("span");
title.className="chat-title";
title.textContent=
chat.title||
chat.name||
"New conversation";

const deleteButton=document.createElement("button");
deleteButton.className="chat-delete";
deleteButton.type="button";
deleteButton.title="Delete chat";
deleteButton.textContent="×";

deleteButton.addEventListener("click",event=>{
event.stopPropagation();
deleteChat(chat.id);
});

item.append(icon,title,deleteButton);

item.addEventListener("click",()=>{
openChat(chat.id);
});

el.chatList.appendChild(item);
}
}

function startNewChat(){
if(!isAuthenticated()){
showAuthModal("login");
return;
}

if(state.controller){
state.controller.abort();
state.controller=null;
}

state.chatId=null;
state.messages=[];

clearMessages();
resetComposer();
renderChatList();

setStatus("Ready");
closeMobileSidebar();

el.messageInput?.focus();
}

async function openChat(chatId){
if(!chatId)return;

if(!isAuthenticated()){
showAuthModal("login");
return;
}

try{
setStatus("Loading...");

const response=await apiFetch(
`/api/chat/${encodeURIComponent(chatId)}`
);

const data=await parseResponse(response);

if(!response.ok)
throw new Error(
errorText(data,"Unable to load conversation.")
);

state.chatId=String(chatId);

renderMessages(
Array.isArray(data)
?data
:data.messages||[]
);

renderChatList();

setStatus("Ready");
closeMobileSidebar();

}catch(error){
console.error("openChat:",error);
setStatus("Unable to load chat");
}
}

async function deleteChat(chatId){
if(!chatId||!isAuthenticated())
return;

if(!window.confirm("Delete this conversation?"))
return;

try{
const response=await apiFetch(
"/api/chat/delete",
{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({
chat_id:String(chatId)
})
}
);

const data=await parseResponse(response);

if(!response.ok)
throw new Error(
errorText(data,"Unable to delete chat.")
);

if(String(state.chatId)===String(chatId)){
state.chatId=null;
clearMessages();
}

await loadChats();

setStatus("Ready");

}catch(error){
console.error("deleteChat:",error);
alert(errorText(error,"Unable to delete chat."));
}
}
async function sendMessage(){
if(state.sending)return;

const question=
el.messageInput?.value.trim()||"";

if(!question&&!state.selectedFile)
return;

if(!isAuthenticated()){
showAuthModal("login");
return;
}

state.sending=true;
state.controller=new AbortController();

if(el.sendButton){
el.sendButton.disabled=true;
el.sendButton.innerHTML="■";
}

if(el.messageInput)
el.messageInput.disabled=true;

if(el.attachButton)
el.attachButton.disabled=true;

setStatus("Thinking...");

let assistant=null;
let assistantIndex=-1;

try{
const file=state.selectedFile;

addMessage(
"user",
question||
(file?`Uploaded ${file.name}`:"")
);

el.messageInput.value="";
autoResizeTextarea();

assistant=createMessageElement(
"assistant",
""
);

el.messages.appendChild(
assistant.wrapper
);

state.messages.push({
role:"assistant",
content:""
});

assistantIndex=state.messages.length-1;

updateWelcome();
scrollToBottom();

const formData=new FormData();

formData.append("question",question);

if(state.chatId)
formData.append("chat_id",state.chatId);

if(file)
formData.append("file",file);

const response=await apiFetch(
"/api/chat",
{
method:"POST",
body:formData,
signal:state.controller.signal,
headers:{
"Accept":"text/event-stream"
}
}
);

if(!response.ok){
const data=await parseResponse(response);

throw new Error(
errorText(
data,
`Request failed (${response.status})`
)
);
}

if(!response.body)
throw new Error("Streaming is not supported by this browser.");

await readSSE(
response.body,
event=>{
if(event.event==="chat_id"){
if(event.data?.chat_id){
state.chatId=String(event.data.chat_id);
renderChatList();
}
return;
}

if(event.event==="token"){
const text=
event.data?.text||
event.data?.token||
"";

if(!text)return;

state.messages[assistantIndex].content+=text;

assistant.body.innerHTML=
renderMarkdown(
state.messages[assistantIndex].content
);

scrollToBottom();
return;
}

if(event.event==="message"){
const text=
event.data?.text||
event.data?.message||
"";

if(text){
state.messages[assistantIndex].content+=text;
assistant.body.innerHTML=
renderMarkdown(
state.messages[assistantIndex].content
);
}

return;
}

if(event.event==="error"){
throw new Error(
errorText(
event.data,
"Brain generation failed."
)
);
}

if(event.event==="done"){
setStatus("Ready");
}
});

if(!state.messages[assistantIndex].content){
assistant.body.innerHTML=
"<span class=\"empty-response\">No response received.</span>";
}

await loadChats();

}catch(error){
if(error.name==="AbortError"){
setStatus("Stopped");
}else{
console.error("sendMessage:",error);

if(assistant){
assistant.body.innerHTML=
`<div class="response-error">${escapeHtml(
errorText(error,"Brain generation failed.")
)}</div>`;
}

setStatus("Error");
}

}finally{
state.sending=false;
state.controller=null;

if(el.sendButton){
el.sendButton.disabled=false;

el.sendButton.innerHTML=`
<svg viewBox="0 0 24 24" fill="none"
stroke="currentColor" stroke-width="2.3">
<path d="M22 2 11 13"/>
<path d="m22 2-7 20-4-9Z"/>
</svg>`;
}

if(el.messageInput)
el.messageInput.disabled=false;

if(el.attachButton)
el.attachButton.disabled=false;

resetComposer();

if(isAuthenticated())
setStatus("Ready");

el.messageInput?.focus();
}
}

async function readSSE(stream,onEvent){
const reader=stream.getReader();
const decoder=new TextDecoder();
let buffer="";

while(true){
const{value,done}=await reader.read();

if(done)break;

buffer+=decoder.decode(value,{
stream:true
});

const blocks=buffer.split("\n\n");

buffer=blocks.pop()||"";

for(const block of blocks){
const event=parseSSEBlock(block);

if(event)
onEvent(event);
}
}

if(buffer.trim()){
const event=parseSSEBlock(buffer);

if(event)
onEvent(event);
}
}

function parseSSEBlock(block){
const lines=block.split(/\r?\n/);

let event="message";
let data="";

for(const line of lines){
if(line.startsWith("event:"))
event=line.slice(6).trim();

else if(line.startsWith("data:"))
data+=line.slice(5).trim();
}

if(!data)return null;

let parsed=data;

try{
parsed=JSON.parse(data);
}catch{}

return{
event,
data:parsed
};
}

function autoResizeTextarea(){
const input=el.messageInput;

if(!input)return;

input.style.height="auto";

input.style.height=
Math.min(input.scrollHeight,180)+"px";
}

function closeMobileSidebar(){
el.sidebar?.classList.remove("open");
el.sidebarBackdrop?.classList.remove("show");
document.body.classList.remove("sidebar-open");
}

function openMobileSidebar(){
el.sidebar?.classList.add("open");
el.sidebarBackdrop?.classList.add("show");
document.body.classList.add("sidebar-open");
}

function toggleMobileSidebar(){
if(el.sidebar?.classList.contains("open"))
closeMobileSidebar();
else
openMobileSidebar();
}

function handleUnauthenticated(){
state.chatId=null;
state.chats=[];
state.messages=[];

clearMessages();
renderChatList();
updateUserUI(null);

setStatus("Sign in required");
}

async function handleAuthButton(){
const user=getAuthUser();

if(user){
try{
await window.BrainAuth.signOut();
handleUnauthenticated();
}catch(error){
alert(errorText(error,"Unable to sign out."));
}
return;
}

showAuthModal("login");
}

async function handleLogin(event){
event.preventDefault();

showAuthError("");

const email=el.loginEmail?.value.trim();
const password=el.loginPassword?.value||"";

if(!email||!password){
showAuthError("Enter your email and password.");
return;
}

try{
const button=el.loginForm.querySelector(".auth-submit");

if(button){
button.disabled=true;
button.textContent="Signing in...";
}

await window.BrainAuth.signIn(
email,
password
);

hideAuthModal();

updateUserUI(getAuthUser());

await loadChats();

setStatus("Ready");

}catch(error){
showAuthError(error);
}finally{
const button=el.loginForm.querySelector(".auth-submit");

if(button){
button.disabled=false;
button.textContent="Sign in";
}
}
}

async function handleSignup(event){
event.preventDefault();

showAuthError("");

const name=el.signupName?.value.trim();
const email=el.signupEmail?.value.trim();
const password=el.signupPassword?.value||"";

if(!email||!password){
showAuthError("Enter an email and password.");
return;
}

if(password.length<6){
showAuthError("Password must contain at least 6 characters.");
return;
}

try{
const button=el.signupForm.querySelector(".auth-submit");

if(button){
button.disabled=true;
button.textContent="Creating...";
}

await window.BrainAuth.signUp(
email,
password,
{
data:{
full_name:name
}
}
);

const user=getAuthUser();

if(user){
hideAuthModal();
await loadChats();
setStatus("Ready");
}else{
showAuthError(
"Account created. Check your email to confirm your account."
);
}
}catch(error){
showAuthError(error);
}finally{
const button=el.signupForm.querySelector(".auth-submit");

if(button){
button.disabled=false;
button.textContent="Create account";
}
}
}

function setupSuggestions(){
document.querySelectorAll(".suggestion").forEach(button=>{
button.addEventListener("click",()=>{
if(!isAuthenticated()){
showAuthModal("login");
return;
}

const prompt=button.dataset.prompt||"";

el.messageInput.value=prompt;
autoResizeTextarea();
el.messageInput.focus();
});
});
}

function setupSwipeSidebar(){
let startX=0;
let startY=0;

document.addEventListener("touchstart",event=>{
if(!event.touches[0])return;

startX=event.touches[0].clientX;
startY=event.touches[0].clientY;
},{
passive:true
});

document.addEventListener("touchend",event=>{
if(!event.changedTouches[0])return;

const endX=event.changedTouches[0].clientX;
const endY=event.changedTouches[0].clientY;

const dx=endX-startX;
const dy=endY-startY;

if(Math.abs(dx)<60||Math.abs(dx)<Math.abs(dy))
return;

if(dx<0&&el.sidebar?.classList.contains("open"))
closeMobileSidebar();

if(dx>0&&startX<40)
openMobileSidebar();
},{
passive:true
});
}

function setupEvents(){
el.mobileMenuButton?.addEventListener(
"click",
toggleMobileSidebar
);

el.sidebarBackdrop?.addEventListener(
"click",
closeMobileSidebar
);

el.newChatButton?.addEventListener(
"click",
startNewChat
);

el.newChatTopButton?.addEventListener(
"click",
startNewChat
);

el.clearChatButton?.addEventListener(
"click",
()=>{
if(state.messages.length&&
window.confirm("Clear this conversation?")){
clearMessages();
state.chatId=null;
renderChatList();
}
}
);

el.authButton?.addEventListener(
"click",
handleAuthButton
);

el.authCloseButton?.addEventListener(
"click",
hideAuthModal
);

el.authModal?.addEventListener(
"click",
event=>{
if(event.target===el.authModal)
hideAuthModal();
}
);

el.authSwitchButton?.addEventListener(
"click",()=>{
showAuthError("");

if(el.loginForm?.style.display!=="none")
showSignupForm();
else
showLoginForm();
}
);

el.loginForm?.addEventListener(
"submit",
handleLogin
);

el.signupForm?.addEventListener(
"submit",
handleSignup
);

el.attachButton?.addEventListener(
"click",
()=>{
if(!state.sending)
el.fileInput?.click();
}
);

el.fileInput?.addEventListener(
"change",
event=>{
const file=event.target.files?.[0];

if(file)
selectFile(file);
}
);

el.removeFileButton?.addEventListener(
"click",
resetComposer
);

el.sendButton?.addEventListener(
"click",
sendMessage
);

el.messageInput?.addEventListener(
"input",
autoResizeTextarea
);

el.messageInput?.addEventListener(
"keydown",
event=>{
if(event.key==="Enter"&&!event.shiftKey){
event.preventDefault();

if(!state.sending)
sendMessage();
}
}
);

el.messageInput?.addEventListener(
"paste",
()=>{
setTimeout(autoResizeTextarea,0);
}
);

document.addEventListener(
"keydown",
event=>{
if((event.ctrlKey||event.metaKey)&&event.key==="k"){
event.preventDefault();
el.messageInput?.focus();
}
if(event.key==="Escape"){
closeMobileSidebar();
hideAuthModal();
}
}
);

setupSuggestions();
setupSwipeSidebar();
}

async function init(){
setupEvents();

if(window.BrainAuth){
window.BrainAuth.onAuthStateChange(
async user=>{
state.authReady=true;

updateUserUI(user);

if(user){
setStatus("Ready");
await loadChats();
}else{
handleUnauthenticated();
}
}
);

await window.BrainAuth.init();

state.authReady=true;

const user=getAuthUser();

updateUserUI(user);

if(user)
await loadChats();
else
handleUnauthenticated();

}else{
state.authReady=true;
handleUnauthenticated();
}
}

if(document.readyState==="loading"){
document.addEventListener("DOMContentLoaded",init);
}else{
init();
}

})();