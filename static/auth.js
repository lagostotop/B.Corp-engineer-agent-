"use strict";

const SUPABASE_URL="https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjcmRtd3RzZ2diZ2NvbnF2a2p6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MDAwMjAsImV4cCI6MjA5NTk3NjAyMH0.o7d6lTABfWaf_5NtPSWLR9qCUJvS_kYL9bI7Z2fSX50";

window.$=id=>document.getElementById(id);

let sb=null,user=null;

function status(t){
  const x=$("authStatus");
  if(x)x.textContent=t||"";
}

function error(t,ok=false){
  const x=$("authError");
  if(!x)return;
  x.textContent=t||"";
  x.style.color=ok?"#22c55e":"#ef4444";
}

function showAuthScreen(){
  $("authScreen").style.display="flex";
  $("chatContainer").style.display="none";
}

function showChatScreen(){
  $("authScreen").style.display="none";
  $("chatContainer").style.display="block";
  $("userEmailDisplay")&&( $("userEmailDisplay").textContent=user?.email||"");
  $("userAvatar")&&( $("userAvatar").textContent=(user?.email||"U")[0].toUpperCase() );
  window.loadChats?.();
}

async function initAuth(){
  if(!window.supabase)throw Error("Supabase library missing");

  sb=window.supabase.createClient(SUPABASE_URL,SUPABASE_KEY);
  window.supabaseClient=sb;

  const {data}=await sb.auth.getSession();
  user=data?.session?.user||null;

  if(user)showChatScreen();
  else showAuthScreen();

  sb.auth.onAuthStateChange((_e,s)=>{
    user=s?.user||null;
    if(user)showChatScreen();
    else showAuthScreen();
  });

  status(user?"Brain 3.0 online":"Sign in to continue");
}

async function getAuthToken(){
  if(!sb)return null;
  const {data}=await sb.auth.getSession();
  return data?.session?.access_token||null;
}

function authToken(){
  return window._brainToken||null;
}

async function refreshToken(){
  const token=await getAuthToken();
  window._brainToken=token;
  return token;
}

function getAuthHeaders(){
  const token=window._brainToken;
  return token
    ? {Authorization:`Bearer ${token}`,Accept:"application/json"}
    : {Accept:"application/json"};
}

async function doLogin(){
  error("");
  const email=$("emailInput")?.value.trim();
  const password=$("passwordInput")?.value;

  if(!email||!password)return error("Enter your email and password.");

  try{
    status("Signing in...");
    const {data,error:e}=await sb.auth.signInWithPassword({email,password});
    if(e)throw e;

    user=data.user;
    await refreshToken();
    status("Brain 3.0 online");
    showChatScreen();
  }catch(e){
    console.error(e);
    error(e.message||"Sign in failed.");
  }
}

async function doSignup(){
  error("");
  const email=$("emailInput")?.value.trim();
  const password=$("passwordInput")?.value;

  if(!email||!password)return error("Enter an email and password.");
  if(password.length<6)return error("Password must be at least 6 characters.");

  try{
    status("Creating account...");
    const {data,error:e}=await sb.auth.signUp({email,password});
    if(e)throw e;

    if(data.session){
      user=data.user;
      await refreshToken();
      showChatScreen();
    }else{
      error("Account created. Check your email to verify your account.",true);
    }
  }catch(e){
    console.error(e);
    error(e.message||"Account creation failed.");
  }
}

async function doLogout(){
  try{await sb?.auth.signOut()}catch(e){console.error(e)}
  window._brainToken=null;
  user=null;
  showAuthScreen();
}

window.initAuth=initAuth;
window.getAuthToken=getAuthToken;
window.refreshToken=refreshToken;
window.authToken=authToken;
window.getAuthHeaders=getAuthHeaders;
window.doLogin=doLogin;
window.doSignup=doSignup;
window.doLogout=doLogout;
window.showAuthScreen=showAuthScreen;
window.showChatScreen=showChatScreen;
window.currentUser=()=>user;
