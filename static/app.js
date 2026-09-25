(()=>{
"use strict";

const state={
chatId:null,
chats:[],
messages:[],
selectedFile:null,
sending:false,
controller:null
};

const $=id=>document.getElementById(id);

const el={
sidebar:$("sidebar"),
sidebarBackdrop:$("sidebarBackdrop"),
mobileMenuButton:$("mobileMenuButton"),
newChatButton:$("newChatButton"),
chatList:$("chatList"),
messages:$("messages"),
welcomeMessage:$("welcomeMessage"),
chatContainer:$("chatContainer"),
messageInput:$("messageInput"),
sendButton:$("sendButton"),
attachButton:$("attachButton"),
fileInput:$("fileInput"),
filePreview:$("filePreview"),
fileName:$("fileName"),
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
if(el.connectionStatus){
el.connectionStatus.textContent=text;
}
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

if(!window.marked){
return escapeHtml(text).replace(/\n/g,"<br>");
}

const html=window.marked.parse(text,{
breaks:true,
gfm:true
});

return window.DOMPurify
?window.DOMPurify.sanitize(html)
:html;
}

/* Normalize every possible API/SSE error shape into a string.
   Prevents JavaScript from displaying "[object Object]". */
function getErrorMessage(value,fallback="Something went wrong."){
if(value instanceof Error){
return value.message||fallback;
}

if(typeof value==="string"){
return value.trim()||fallback;
}

if(value&&typeof value==="object"){
if(typeof value.message==="string"&&value.message.trim()){
return value.message.trim();
}

if(typeof value.error==="string"&&value.error.trim()){
return value.error.trim();
}

if(value.error&&typeof value.error==="object"){
if(
typeof value.error.message==="string"&&
value.error.message.trim()
){
return value.error.message.trim();
}

if(
typeof value.error.detail==="string"&&
value.error.detail.trim()
){
return value.error.detail.trim();
}
}

if(typeof value.detail==="string"&&value.detail.trim()){
return value.detail.trim();
}

if(typeof value.data==="string"&&value.data.trim()){
return value.data.trim();
}
}

return fallback;
}

function scrollToBottom(){
requestAnimationFrame(()=>{
if(el.chatContainer){
el.chatContainer.scrollTop=
el.chatContainer.scrollHeight;
}
});
}

function updateWelcome(){
if(el.welcomeMessage){
el.welcomeMessage.style.display=
state.messages.length
?"none"
:"block";
}
}

function createMessageElement(role,content=""){
const wrapper=document.createElement("div");
wrapper.className=`message ${role}`;

const avatar=document.createElement("div");
avatar.className="message-avatar";
avatar.textContent=
role==="user"
?"YOU"
:"B";

const body=document.createElement("div");
body.className="message-content";

if(role==="user"){
body.textContent=content;
}else{
body.innerHTML=renderMarkdown(content);
}

wrapper.appendChild(avatar);
wrapper.appendChild(body);

return{wrapper,body};
}

function addMessage(role,content=""){
const message={
role,
content:String(content??"")
};

state.messages.push(message);

const rendered=
createMessageElement(
role,
message.content
);

el.messages.appendChild(
rendered.wrapper
);

updateWelcome();
scrollToBottom();

return rendered;
}

function clearMessages(){
state.messages=[];

if(!el.messages)return;

while(el.messages.firstChild){
el.messages.removeChild(
el.messages.firstChild
);
}

if(el.welcomeMessage){
el.messages.appendChild(
el.welcomeMessage
);
}

updateWelcome();
}

function renderMessages(messages){
clearMessages();

for(const message of messages||[]){

if(
message.role!=="user"&&
message.role!=="assistant"
){
continue;
}

addMessage(
message.role,
message.content
);
}

scrollToBottom();
}

function resetComposer(){
state.selectedFile=null;

if(el.fileInput){
el.fileInput.value="";
}

if(el.filePreview){
el.filePreview.style.display="none";
}

if(el.fileName){
el.fileName.textContent="";
}
}

function formatBytes(bytes){
if(!bytes)return"0 B";

const units=[
"B",
"KB",
"MB",
"GB"
];

const index=Math.min(
Math.floor(
Math.log(bytes)/Math.log(1024)
),
units.length-1
);

return`${(
bytes/Math.pow(1024,index)
).toFixed(index?1:0)} ${units[index]}`;
}

function selectFile(file){
if(!file)return;

const name=file.name||"";

const extension=name.includes(".")
?name.split(".").pop().toLowerCase()
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

if(el.fileName){
el.fileName.textContent=
`${file.name} (${formatBytes(file.size)})`;
}

if(el.filePreview){
el.filePreview.style.display="flex";
}

setStatus("File attached");
}

function setSending(value){
state.sending=Boolean(value);

if(el.sendButton){
el.sendButton.disabled=
state.sending;

el.sendButton.textContent=
state.sending
?"■"
:"↑";
}

if(el.messageInput){
el.messageInput.disabled=
state.sending;
}

if(el.attachButton){
el.attachButton.disabled=
state.sending;
}
}

function showAuthModal(mode="login"){
if(!el.authModal)return;

el.authModal.style.display="flex";

if(mode==="signup"){
showSignupForm();
}else{
showLoginForm();
}

showAuthError("");
}

function hideAuthModal(){
if(el.authModal){
el.authModal.style.display="none";
}
}

function showLoginForm(){
if(el.loginForm){
el.loginForm.style.display="flex";
}

if(el.signupForm){
el.signupForm.style.display="none";
}

if(el.authTitle){
el.authTitle.textContent=
"Welcome back";
}

if(el.authSubtitle){
el.authSubtitle.textContent=
"Sign in to continue using Brain 3.0.";
}

if(el.authSwitchButton){
el.authSwitchButton.textContent=
"Create an account";
}
}

function showSignupForm(){
if(el.loginForm){
el.loginForm.style.display="none";
}

if(el.signupForm){
el.signupForm.style.display="flex";
}

if(el.authTitle){
el.authTitle.textContent=
"Create your account";
}

if(el.authSubtitle){
el.authSubtitle.textContent=
"Create an account to start using Brain 3.0.";
}

if(el.authSwitchButton){
el.authSwitchButton.textContent=
"Already have an account? Sign in";
}
}

function showAuthError(message){
if(el.authError){
el.authError.textContent=
getErrorMessage(
message,
""
);
}
}

function getAuthUser(){
if(
window.BrainAuth&&
typeof window.BrainAuth.getUser==="function"
){
return window.BrainAuth.getUser();
}

return null;
}

function isAuthenticated(){
return Boolean(getAuthUser());
}

function updateUserUI(user=null){
if(!user){

if(el.userName){
el.userName.textContent="Guest";
}

if(el.userEmail){
el.userEmail.textContent=
"Not signed in";
}

if(el.userAvatar){
el.userAvatar.textContent="?";
}

if(el.authButton){
el.authButton.textContent="Login";
}

return;
}

const metadata=
user.user_metadata||{};

const name=
metadata.full_name||
metadata.name||
user.email?.split("@")[0]||
"User";

if(el.userName){
el.userName.textContent=name;
}

if(el.userEmail){
el.userEmail.textContent=
user.email||"";
}

if(el.userAvatar){
el.userAvatar.textContent=
name.charAt(0).toUpperCase();
}

if(el.authButton){
el.authButton.textContent="Logout";
}
}

async function apiFetch(url,options={}){
if(
window.BrainAuth&&
typeof window.BrainAuth.fetchWithAuth===
"function"
){
return window.BrainAuth.fetchWithAuth(
url,
options
);
}

return fetch(url,options);
}

async function parseJsonResponse(response){
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

const response=
await apiFetch("/api/chats");

if(!response.ok){

if(response.status===401){
handleUnauthenticated();
return;
}

const data=
await parseJsonResponse(response);

throw new Error(
getErrorMessage(
data,
`Failed to load chats (${response.status})`
)
);
}

const data=
await parseJsonResponse(response);

state.chats=
Array.isArray(data)
?data
:Array.isArray(data.chats)
?data.chats
:[];

renderChatList();

}catch(error){

console.error(
"loadChats:",
error
);

setStatus(
"Unable to load chats"
);
}
}

function renderChatList(){
if(!el.chatList)return;

el.chatList.innerHTML="";

if(!state.chats.length){

const empty=
document.createElement("div");

empty.className="chat-item";
empty.style.color="#687389";
empty.textContent=
"No conversations yet";

el.chatList.appendChild(empty);
return;
}

for(const chat of state.chats){

const item=
document.createElement("div");

item.className=
"chat-item"+
(
String(chat.id)===
String(state.chatId)
?" active"
:""
);

item.dataset.chatId=chat.id;

const title=
document.createElement("span");

title.className="chat-title";
title.textContent=
chat.title||
chat.name||
"New conversation";

const deleteButton=
document.createElement("button");

deleteButton.className=
"chat-delete";

deleteButton.type="button";
deleteButton.title="Delete chat";
deleteButton.textContent="×";

deleteButton.addEventListener(
"click",
event=>{
event.stopPropagation();
deleteChat(
chat.id
);
}
);

item.appendChild(title);
item.appendChild(deleteButton);

item.addEventListener(
"click",
()=>openChat(chat.id)
);

el.chatList.appendChild(item);
}
}

function startNewChat(){
state.chatId=null;
state.messages=[];
clearMessages();
renderChatList();
setStatus(
isAuthenticated()
?"Ready"
:"Sign in required"
);
closeMobileSidebar();
}

async function openChat(chatId){
if(!chatId)return;

if(!isAuthenticated()){
showAuthModal("login");
return;
}

try{

setStatus("Loading...");

const response=
await apiFetch(
`/api/chat/${encodeURIComponent(chatId)}`
);

const data=
await parseJsonResponse(response);

if(!response.ok){
throw new Error(
getErrorMessage(
data,
"Unable to load conversation."
)
);
}

state.chatId=
String(chatId);

const messages=
Array.isArray(data)
?data
:data.messages||[];

renderMessages(messages);
renderChatList();

setStatus("Ready");

closeMobileSidebar();

}catch(error){

console.error(
"openChat:",
error
);

setStatus(
"Unable to load chat"
);

alert(
getErrorMessage(
error,
"Unable to load chat."
)
);
}
}

async function deleteChat(chatId){
if(!chatId||!isAuthenticated()){
return;
}

const confirmed=
window.confirm(
"Delete this conversation?"
);

if(!confirmed)return;

try{

const response=
await apiFetch(
"/api/chat/delete",
{
method:"POST",
headers:{
"Content-Type":
"application/json"
},
body:JSON.stringify({
chat_id:String(chatId)
})
}
);

const data=
await parseJsonResponse(response);

if(!response.ok){
throw new Error(
getErrorMessage(
data,
"Unable to delete chat."
)
);
}

if(
String(state.chatId)===
String(chatId)
){
state.chatId=null;
clearMessages();
}

await loadChats();

setStatus("Ready");

}catch(error){

console.error(
"deleteChat:",
error
);

alert(
getErrorMessage(
error,
"Unable to delete chat."
)
);
}
}
async function sendMessage(){
if(state.sending)return;

const question=
el.messageInput?.value.trim()||
"";

if(
!question&&
!state.selectedFile
){
return;
}

if(!isAuthenticated()){
showAuthModal("login");
return;
}

setSending(true);
setStatus("Thinking...");

let assistant=null;

try{

const file=
state.selectedFile;

addMessage(
"user",
question||
(file
?`Uploaded ${file.name}`
:"")
);

el.messageInput.value="";
autoResizeTextarea();

assistant=
createMessageElement(
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

updateWelcome();
scrollToBottom();

const formData=
new FormData();

formData.append(
"question",
question
);

if(state.chatId){
formData.append(
"chat_id",
state.chatId
);
}

formData.append(
"mode",
"normal"
);

formData.append(
"client_msg_id",
crypto.randomUUID
?crypto.randomUUID()
:String(Date.now())
);

if(file){
formData.append(
"file",
file,
file.name
);
}

const controller=
new AbortController();

state.controller=controller;

const response=
await apiFetch(
"/api/chat",
{
method:"POST",
body:formData,
signal:controller.signal
}
);

if(!response.ok){

const data=
await parseJsonResponse(response);

throw new Error(
getErrorMessage(
data,
`Chat request failed (${response.status})`
)
);
}

await consumeStream(
response,
assistant.body
);

resetComposer();
setStatus("Ready");

await loadChats();

}catch(error){

if(
error.name===
"AbortError"
){
setStatus("Stopped");
return;
}

console.error(
"sendMessage:",
error
);

setStatus("Error");

const message=
getErrorMessage(
error,
"Something went wrong while processing your request."
);

if(assistant){

assistant.body.dataset.rawContent=
message;

assistant.body.style.color=
"#ff9b9b";

assistant.body.textContent=
message;

const index=
state.messages.length-1;

if(
index>=0&&
state.messages[index].role===
"assistant"
){
state.messages[index].content=
message;
}

scrollToBottom();

}else{

addErrorMessage(message);

}

}finally{

state.controller=null;
setSending(false);

}
}

async function consumeStream(
response,
assistantBody
){
if(!response.body){

const data=
await parseJsonResponse(
response
);

const message=
data.answer||
data.message||
data.error||
"";

appendAssistantText(
assistantBody,
getErrorMessage(
message,
""
)
);

return;
}

const reader=
response.body.getReader();

const decoder=
new TextDecoder("utf-8");

let buffer="";
let finished=false;

while(!finished){

const{value,done}=
await reader.read();

if(done)break;

buffer+=decoder.decode(
value,
{stream:true}
);

const parts=
buffer.split(
/\r?\n\r?\n/
);

buffer=
parts.pop()||
"";

for(const part of parts){

const event=
parseSSEEvent(part);

if(!event)continue;

if(event.event==="token"){

appendAssistantText(
assistantBody,
event.data?.text||""
);

}else if(
event.event==="chat_id"
){

if(event.data?.chat_id){

state.chatId=
String(
event.data.chat_id
);

renderChatList();

}

}else if(
event.event==="done"
){

if(event.data?.chat_id){

state.chatId=
String(
event.data.chat_id
);

}

finished=true;

}else if(
event.event==="error"
){

throw new Error(
getErrorMessage(
event.data,
"The server returned an error."
)
);

}else if(
event.event==="message"
){

appendAssistantText(
assistantBody,
event.data?.text||
event.data?.content||
""
);

}
}
}

buffer+=decoder.decode();

if(buffer.trim()){

const event=
parseSSEEvent(buffer);

if(event?.event==="token"){

appendAssistantText(
assistantBody,
event.data?.text||
""
);

}else if(
event?.event==="message"
){

appendAssistantText(
assistantBody,
event.data?.text||
event.data?.content||
""
);

}else if(
event?.event==="error"
){

throw new Error(
getErrorMessage(
event.data,
"The server returned an error."
)
);

}
}

const index=
state.messages.length-1;

if(
index>=0&&
state.messages[index].role===
"assistant"
){

state.messages[index].content=
assistantBody.dataset.rawContent||
"";
}
}

function parseSSEEvent(block){
if(!block||!block.trim()){
return null;
}

let eventName="message";
let dataText="";

for(
const line of block.split(/\r?\n/)
){

if(line.startsWith("event:")){
eventName=
line.slice(6).trim();
}else if(
line.startsWith("data:")
){

dataText+=
line.slice(5).trim();
}
}

if(!dataText){
return{
event:eventName,
data:{}
};
}

let data;

try{
data=JSON.parse(dataText);
}catch{
data={
text:dataText
};
}

return{
event:eventName,
data
};
}

function appendAssistantText(
element,
text
){
if(!element||!text)return;

const current=
element.dataset.rawContent||
"";

const updated=
current+String(text);

element.dataset.rawContent=
updated;

element.innerHTML=
renderMarkdown(updated);

const index=
state.messages.length-1;

if(
index>=0&&
state.messages[index].role===
"assistant"
){

state.messages[index].content=
updated;
}

scrollToBottom();
}

function addErrorMessage(message){
const safeMessage=
getErrorMessage(
message,
"Something went wrong."
);

const rendered=
createMessageElement(
"assistant",
""
);

rendered.body.style.color=
"#ff9b9b";

rendered.body.textContent=
safeMessage;

el.messages.appendChild(
rendered.wrapper
);

scrollToBottom();
}

function autoResizeTextarea(){
if(!el.messageInput)return;

el.messageInput.style.height=
"auto";

el.messageInput.style.height=
`${Math.min(
el.messageInput.scrollHeight,
180
)}px`;
}

function openMobileSidebar(){
if(el.sidebar){
el.sidebar.classList.add("open");
}

if(el.sidebarBackdrop){
el.sidebarBackdrop.classList.add(
"show"
);
}
}

function closeMobileSidebar(){
if(el.sidebar){
el.sidebar.classList.remove(
"open"
);
}

if(el.sidebarBackdrop){
el.sidebarBackdrop.classList.remove(
"show"
);
}
}

function handleUnauthenticated(){
state.chatId=null;
state.chats=[];
state.messages=[];

updateUserUI(null);
renderChatList();
clearMessages();

setStatus(
"Sign in required"
);
}

async function handleAuthStateChange(user){
updateUserUI(user);

if(user){

hideAuthModal();

setStatus("Ready");

await loadChats();

}else{

handleUnauthenticated();

}
}

async function handleAuthButton(){
const user=getAuthUser();

if(!user){
showAuthModal("login");
return;
}

try{

await window.BrainAuth.signOut();

handleUnauthenticated();

}catch(error){

console.error(
"signOut:",
error
);

showAuthError(
getErrorMessage(
error,
"Unable to sign out."
)
);
}
}

async function handleLogin(event){
event.preventDefault();

if(!window.BrainAuth){
showAuthError(
"Authentication is not ready."
);
return;
}

const email=
el.loginEmail.value.trim();

const password=
el.loginPassword.value;

showAuthError("");

try{

await window.BrainAuth.signIn(
email,
password
);

hideAuthModal();

}catch(error){

console.error(
"login:",
error
);

showAuthError(
getErrorMessage(
error,
"Unable to sign in."
)
);
}
}

async function handleSignup(event){
event.preventDefault();

if(!window.BrainAuth){
showAuthError(
"Authentication is not ready."
);
return;
}

const name=
el.signupName.value.trim();

const email=
el.signupEmail.value.trim();

const password=
el.signupPassword.value;

showAuthError("");

try{

const data=
await window.BrainAuth.signUp(
email,
password,
{
data:{
full_name:name,
name
}
}
);

if(data?.session){

hideAuthModal();

}else{

showAuthError(
"Account created. Check your email to confirm your account."
);

}

}catch(error){

console.error(
"signup:",
error
);

showAuthError(
getErrorMessage(
error,
"Unable to create account."
)
);
}
}

function bindEvents(){

if(el.newChatButton){

el.newChatButton.addEventListener(
"click",
startNewChat
);

}

if(el.mobileMenuButton){

el.mobileMenuButton.addEventListener(
"click",
()=>{

if(
el.sidebar?.classList.contains(
"open"
)
){
closeMobileSidebar();
}else{
openMobileSidebar();
}

}
);

}

if(el.sidebarBackdrop){

el.sidebarBackdrop.addEventListener(
"click",
closeMobileSidebar
);

}

if(el.attachButton){

el.attachButton.addEventListener(
"click",
()=>{
if(!state.sending){
el.fileInput?.click();
}
}
);

}

if(el.fileInput){

el.fileInput.addEventListener(
"change",
event=>{
selectFile(
event.target.files?.[0]
);
}
);

}

if(el.removeFileButton){

el.removeFileButton.addEventListener(
"click",
resetComposer
);

}

if(el.sendButton){

el.sendButton.addEventListener(
"click",
sendMessage
);

}

if(el.messageInput){

el.messageInput.addEventListener(
"input",
autoResizeTextarea
);

el.messageInput.addEventListener(
"keydown",
event=>{

if(
event.key==="Enter"&&
!event.shiftKey
){

event.preventDefault();

sendMessage();

}

}
);

}

if(el.authButton){

el.authButton.addEventListener(
"click",
handleAuthButton
);

}

if(el.authCloseButton){

el.authCloseButton.addEventListener(
"click",
hideAuthModal
);

}

if(el.authModal){

el.authModal.addEventListener(
"click",
event=>{

if(
event.target===
el.authModal
){
hideAuthModal();
}

}
);

}

if(el.authSwitchButton){

el.authSwitchButton.addEventListener(
"click",
()=>{

if(
el.signupForm?.style.display===
"flex"
){
showLoginForm();
}else{
showSignupForm();
}

}
);

}

if(el.loginForm){

el.loginForm.addEventListener(
"submit",
handleLogin
);

}

if(el.signupForm){

el.signupForm.addEventListener(
"submit",
handleSignup
);

}
}

let touchStartX=0;
let touchStartY=0;

function bindSwipe(){

if(!el.sidebar)return;

el.sidebar.addEventListener(
"touchstart",
event=>{

const touch=
event.changedTouches[0];

touchStartX=
touch.clientX;

touchStartY=
touch.clientY;

},
{passive:true}
);

el.sidebar.addEventListener(
"touchend",
event=>{

const touch=
event.changedTouches[0];

const dx=
touch.clientX-touchStartX;

const dy=
Math.abs(
touch.clientY-touchStartY
);

if(
dx< -60&&
dy<80
){

closeMobileSidebar();

}

},
{passive:true}
);
}

async function boot(){

bindEvents();
bindSwipe();

updateUserUI(null);
setStatus("Connecting...");

if(!window.BrainAuth){

setStatus(
"Authentication unavailable"
);

return;
}

window.BrainAuth.onAuthStateChange(
handleAuthStateChange
);

const user=
await window.BrainAuth.init();

if(user){

await handleAuthStateChange(
user
);

}else{

setStatus(
"Sign in required"
);

}
}

if(
document.readyState===
"loading"
){

document.addEventListener(
"DOMContentLoaded",
boot
);

}else{

boot();

}

})();