"use strict";

window.$=id=>document.getElementById(id);

const TEST_USER_ID="00000000-0000-0000-0000-000000000001";

function showAuthScreen(){
  const a=$("authScreen"),c=$("chatContainer");
  if(a)a.style.display="none";
  if(c)c.style.display="flex";
}

function showChatScreen(){
  const a=$("authScreen"),c=$("chatContainer");
  if(a)a.style.display="none";
  if(c)c.style.display="flex";
  window.loadChats?.();
}

async function initAuth(){
  showChatScreen();
}

async function getAuthToken(){
  return null;
}

function authToken(){
  return "test-mode";
}

function getAuthHeaders(){
  return {"Accept":"application/json"};
}

async function doLogin(){
  showChatScreen();
}

async function doSignup(){
  showChatScreen();
}

async function doLogout(){
  showChatScreen();
}

window.initAuth=initAuth;
window.getAuthToken=getAuthToken;
window.authToken=authToken;
window.getAuthHeaders=getAuthHeaders;
window.doLogin=doLogin;
window.doSignup=doSignup;
window.doLogout=doLogout;
window.showAuthScreen=showAuthScreen;
window.showChatScreen=showChatScreen;
window.userId=()=>TEST_USER_ID;
