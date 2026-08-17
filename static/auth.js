"use strict";
let userId = null, authToken = null, DEBUG = true;
window.$ = id => document.getElementById(id); // ONLY PLACE $ IS DEFINED

const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjcmRtd3RzZ2diZ2NvbnF2a2p6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MDAwMjAsImV4cCI6MjA5NTk3NjAyMH0.o7d6lTABfWaf_5NtPSWLR9qCUJvS_kYL9bI7Z2fSX50";
let supabase = null;

function debug(...args){ if(DEBUG) console.log("%c[Brain3 Debug]","color:#00BFFF;font-weight:bold",...args) }
function setAuthStatus(text){ const el = window.$("authStatus"); if(el) el.textContent = text }

async function initAuth(){
    try{
        setAuthStatus("Loading authentication...");
        if(!window.supabase) throw new Error("Supabase SDK did not load. Check CDN.");
        supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {auth:{autoRefreshToken:true,persistSession:true,detectSessionInUrl:true}});
        debug("Supabase initialized");
        setAuthStatus("Checking session...");
        
        supabase.auth.onAuthStateChange((event, session)=>{
            authToken = session?.access_token || null;
            userId = session?.user?.id || null;
            debug("Auth state:", event);
            if(session && window.showChatScreen) window.showChatScreen();
            if(event==="SIGNED_OUT"){ authToken=null; userId=null; if(window.showAuthScreen) window.showAuthScreen(); }
        });
        
        const token = await getAuthToken();
        if(token){ debug("Session found"); setAuthStatus("Authenticated"); window.showChatScreen(); }
        else{ debug("No session"); setAuthStatus(""); window.showAuthScreen(); }
    }catch(error){
        console.error("AUTH INIT FAILED:", error);
        setAuthStatus("Authentication error: "+(error?.message||"Unknown"));
        if(window.showAuthScreen) window.showAuthScreen();
    }
}

async function getAuthToken(){
    if(!supabase) return null;
    const {data,error} = await supabase.auth.getSession();
    if(error) return null;
    authToken = data?.session?.access_token || null;
    userId = data?.session?.user?.id || null;
    return authToken;
}

function getAuthHeaders(){ const h={"Accept":"application/json"}; if(authToken) h.Authorization=`Bearer ${authToken}`; return h; }

async function doLogin(){
    const email=window.$("emailInput").value.trim();
    const password=window.$("passwordInput").value;
    if(!email||!password){ window.$("authError").textContent="Enter email and password"; return; }
    const btn=window.$("loginBtn"); btn.disabled=true; btn.textContent="Signing in...";
    try{
        const {data,error}=await supabase.auth.signInWithPassword({email,password});
        if(error) throw error;
        window.$("authError").style.color="#22c55e"; window.$("authError").textContent="Login successful!";
    }catch(error){
        window.$("authError").style.color="#ef4444"; window.$("authError").textContent=error.message;
    }finally{ btn.disabled=false; btn.textContent="Sign In"; }
}

async function doSignup(){ /* same as before */ }
async function doLogout(){ await supabase?.auth.signOut(); authToken=null; userId=null; location.reload(); }

window.getAuthHeaders=getAuthHeaders; window.getAuthToken=getAuthToken;
window.doLogin=doLogin; window.doSignup=doSignup; window.doLogout=doLogout;
window.userId=()=>userId; window.authToken=()=>authToken; window.initAuth=initAuth;
