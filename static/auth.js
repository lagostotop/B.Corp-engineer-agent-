"use strict";
let userId = null, authToken = null, DEBUG = false;
const $ = id => document.getElementById(id);

const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjcmRtd3RzZ2diZ2NvbnF2a2p6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MDAwMjAsImV4cCI6MjA5NTk3NjAyMH0.o7d6lTABfWaf_5NtPSWLR9qCUJvS_kYL9bI7Z2fSX50";
let supabase = null;

function log(...args) { if (DEBUG) console.log("[Auth]",...args) }

function setAuthStatus(text) { const el = $("authStatus"); if (el) el.textContent = text }

async function initAuth() {
    if (!window.supabase) { throw new Error("Supabase SDK unavailable. Did you add script tag to index.html?") }
    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    log("Supabase initialized");

    supabase.auth.onAuthStateChange((event, session) => {
        authToken = session?.access_token || null;
        userId = session?.user?.id || null;
        log("Auth state changed:", event)
        if (session && window.showChatScreen) { window.showChatScreen() }
    });

    await getAuthToken();
    if (authToken && window.showChatScreen) { log("Existing session found"); window.showChatScreen() }
    else if (window.showAuthScreen) { log("No session found"); setAuthStatus(""); window.showAuthScreen() }
}

async function getAuthToken() {
    if (!supabase) { console.error("Supabase client not initialized"); return null }
    try {
        const { data, error } = await supabase.auth.getSession();
        if (error) { console.error("getSession error:", error); authToken = null; userId = null; return null }
        const session = data?.session || null;
        authToken = session?.access_token || null;
        userId = session?.user?.id || null;
        log("Auth session:", { authenticated:!!authToken, userId });
        return authToken;
    } catch (error) { console.error("Auth initialization failed:", error); authToken = null; userId = null; return null }
}

function getAuthHeaders() { const h = { "Accept": "application/json" }; if (authToken) h.Authorization = `Bearer ${authToken}`; return h }

async function doLogin() {
    const email = $("emailInput").value.trim();
    const password = $("passwordInput").value;
    if (!email ||!password) { $("authError").textContent = "Enter email and password"; return }
    if (!supabase) { $("authError").textContent = "Authentication is still loading. Please wait."; return }
    const btn = $("loginBtn");
    btn.disabled = true; btn.textContent = "Signing in...";
    $("authError").style.color = "#64748b"; $("authError").textContent = "Authenticating...";
    try {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (DEBUG) { console.log("LOGIN DATA:", data); console.log("LOGIN ERROR:", error); }
        if (error) { $("authError").style.color = "#ef4444"; $("authError").textContent = error.message; return }
        if (!data?.session?.access_token) { throw new Error("Supabase returned no access token.") }
        authToken = data.session.access_token;
        userId = data.user?.id || null;
        if (DEBUG) console.log("LOGIN SUCCESS", "USER:", data.user, "TOKEN EXISTS:",!!authToken);
        $("authError").style.color = "#22c55e"; $("authError").textContent = "Login successful!";
        window.showChatScreen();
    } catch (error) { console.error("LOGIN EXCEPTION:", error); $("authError").style.color = "#ef4444"; $("authError").textContent = error?.message || "Login failed";
    } finally { btn.disabled = false; btn.textContent = "Sign In" }
}

async function doSignup() {
    const email = $("emailInput").value.trim();
    const password = $("passwordInput").value;
    if (!email ||!password) return alert("Enter email and password");
    if (password.length < 6) return alert("Password must be 6+ characters");
    if (!supabase) return alert("Auth loading...");
    $("authError").textContent = "Creating account...";
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) { $("authError").textContent = error.message; return }
    if (data.session) {
        authToken = data.session.access_token; userId = data.user.id;
        $("authError").style.color = "#22c55e"; $("authError").textContent = "Account created! Logging you in...";
        setTimeout(() => { window.showChatScreen() }, 800);
    } else { $("authError").style.color = "#22c55e"; $("authError").textContent = "Account created! Check email to confirm, then Sign In." }
}

async function doLogout() { await supabase?.auth.signOut(); authToken = null; userId = null; location.reload() }

// Expose to window so app.js can use them
window.getAuthHeaders = getAuthHeaders;
window.getAuthToken = getAuthToken;
window.doLogin = doLogin;
window.doSignup = doSignup;
window.doLogout = doLogout;
window.userId = () => userId;
window.authToken = () => authToken;

// Auto-start auth when file loads
document.addEventListener("DOMContentLoaded", initAuth);
