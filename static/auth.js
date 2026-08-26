"use strict";

window.$=id=>document.getElementById(id);

const USER_ID="00000000-0000-0000-0000-000000000001";

function showAuthScreen(){
  $("authScreen")&&( $("authScreen").style.display="none");
  $("chatContainer")&&( $("chatContainer").style.display="block");
  window.loadChats?.();
}

function showChatScreen(){
  $("authScreen")&&( $("authScreen").style.display="none");
  $("chatContainer")&&( $("chatContainer").style.display="block");
  window.loadChats?.();
}

async function initAuth(){
  showChatScreen();
}

async function getAuthToken(){
  return "";
}

function authToken(){
  return "dev-mode";
}

function getAuthHeaders(){
  return {"Accept":"application/json"};
}

async function doLogin(){showChatScreen()}
async function doSignup(){showChatScreen()}
async function doLogout(){showChatScreen()}

window.initAuth=initAuth;
window.getAuthToken=getAuthToken;
window.authToken=authToken;
window.getAuthHeaders=getAuthHeaders;
window.doLogin=doLogin;
window.doSignup=doSignup;
window.doLogout=doLogout;
window.showAuthScreen=showAuthScreen;
window.showChatScreen=showChatScreen;
window.userId=()=>USER_ID;
