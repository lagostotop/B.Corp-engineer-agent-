"use strict";
let userId = null, authToken = null, DEBUG = true;
window.$ = id => document.getElementById(id); // ONLY PLACE $ IS DEFINED

const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjcmRtd3RzZ2diZ2NvbnF2a2p6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MDAwMjAsImV4cCI6MjA5NTk3NjAyMH0.o7d6lTABfWaf_5NtPSWLR9qCUJvS_kYL9bI7Z2fSX50";
let supabase = null;

function debug(...args){ if(DEBUG) console.log("%c[Brain4.0 Auth]","color:#00BFFF;font-weight:bold",...args) }
function setAuthStatus(text){ const el = window.$("authStatus"); if(el) el.textContent = text }
function showAuthError(msg, isSuccess = false){
    const el = window.$("authError");
    if(!el) return;
    el.style.color = isSuccess ? "#22c55e" : "#ef4444";
    el.textContent = msg;
}

async function initAuth(){
    try{
        setAuthStatus("Loading authentication...");
        if(!window.supabase) throw new Error("Supabase SDK did not load. Check CDN.");
        
        supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
            auth:{ autoRefreshToken:true, persistSession:true, detectSessionInUrl:true }
        });
        debug("Supabase initialized");
        setAuthStatus("Checking session...");
        
        supabase.auth.onAuthStateChange((event, session)=>{
            authToken = session?.access_token || null;
            userId = session?.user?.id || null;
            debug("Auth state:", event, userId);
            if(session && window.showChatScreen) window.showChatScreen();
            if(event==="SIGNED_OUT"){ 
                authToken=null; 
                userId=null; 
                if(window.showAuthScreen) window.showAuthScreen(); 
            }
        });
        
        const token = await getAuthToken();
        if(token){ 
            debug("Session found"); 
            setAuthStatus("Authenticated"); 
            window.showChatScreen(); 
        }
        else{ 
            debug("No session"); 
            setAuthStatus(""); 
            window.showAuthScreen(); 
        }
    }catch(error){
        console.error("AUTH INIT FAILED:", error);
        setAuthStatus("Authentication error: "+(error?.message||"Unknown"));
        if(window.showAuthScreen) window.showAuthScreen();
    }
}

async function getAuthToken(){
    if(!supabase) return null;
    const {data,error} = await supabase.auth.getSession();
    if(error) {
        console.error("getSession error", error);
        return null;
    }
    authToken = data?.session?.access_token || null;
    userId = data?.session?.user?.id || null;
    return authToken;
}

function getAuthHeaders(){ 
    const h={"Accept":"application/json"}; 
    if(authToken) h.Authorization=`Bearer ${authToken}`; 
    return h; 
}

async function doLogin(){
    const email=window.$("emailInput").value.trim();
    const password=window.$("passwordInput").value;
    if(!email||!password){ showAuthError("Enter email and password"); return; }
    
    const btn=window.$("loginBtn"); 
    btn.disabled=true; 
    btn.textContent="Signing in...";
    showAuthError("");
    
    try{
        const {data,error}=await supabase.auth.signInWithPassword({email,password});
        if(error) throw error;
        if(!data.session) throw new Error("Login failed. Check email/password.");
        
        showAuthError("Login successful! Loading...", true);
    }catch(error){
        console.error("Login error", error);
        showAuthError(error.message || "Login failed");
    }finally{ 
        btn.disabled=false; 
        btn.textContent="Sign In"; 
    }
}

async function doSignup(){
    const email=window.$("emailInput").value.trim();
    const password=window.$("passwordInput").value;
    if(!email||!password){ showAuthError("Enter email and password"); return; }
    if(password.length < 6){ showAuthError("Password must be at least 6 characters"); return; }
    
    const btn=window.$("signupBtn"); 
    btn.disabled=true; 
    btn.textContent="Creating account...";
    showAuthError("");
    
    try{
        const {data,error}=await supabase.auth.signUp({
            email,password,
            options: {
                emailRedirectTo: window.location.origin
            }
        });
        if(error) throw error;
        
        if(data.user && !data.session){
            showAuthError("Account created! Check your email to verify.", true);
        } else {
            showAuthError("Account created! You are now logged in.", true);
        }
    }catch(error){
        console.error("Signup error", error);
        showAuthError(error.message || "Signup failed");
    }finally{ 
        btn.disabled=false; 
        btn.textContent="Sign Up"; 
    }
}

async function doLogout(){ 
    try{
        await supabase?.auth.signOut(); 
        authToken=null; 
        userId=null; 
        location.reload(); 
    }catch(e){
        console.error("Logout error", e);
        location.reload();
    }
}

// Export to window
window.getAuthHeaders=getAuthHeaders; 
window.getAuthToken=getAuthToken;
window.doLogin=doLogin; 
window.doSignup=doSignup; 
window.doLogout=doLogout;
window.userId=()=>userId; 
window.authToken=()=>authToken; 
window.initAuth=initAuth;
