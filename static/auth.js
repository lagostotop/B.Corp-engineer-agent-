"use strict";
let userId = null, authToken = null, DEBUG = false;
const $ = id => document.getElementById(id);
const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjcmRtd3RzZ2diZ2NvbnF2a2p6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MDAwMjAsImV4cCI6MjA5NTk3NjAyMH0.o7d6lTABfWaf_5NtPSWLR9qCUJvS_kYL9bI7Z2fSX50";
let supabase = null;
function log(...args) { if (DEBUG) console.log("[Auth]",...args) }
function setAuthStatus(text) { const el = $("authStatus"); if (el) el.textContent = text }

async function initAuth() {
    try {
        setAuthStatus("Loading authentication...");
        if (!window.supabase) { throw new Error("Supabase SDK did not load. Check internet connection/CDN."); }
        if (typeof window.supabase.createClient!== "function") { throw new Error("Supabase SDK loaded incorrectly: createClient() missing."); }
        supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true } });
        log("Supabase initialized"); setAuthStatus("Checking session...");
        supabase.auth.onAuthStateChange((event, session) => {
            authToken = session?.access_token || null; userId = session?.user?.id || null;
            log("Auth state changed:", event);
            if (session && window.showChatScreen) { window.showChatScreen(); }
            if (event === "SIGNED_OUT") { authToken = null; userId = null; if (window.showAuthScreen) { window.showAuthScreen(); } }
        });
        const token = await getAuthToken();
        if (token) { log("Existing session found"); setAuthStatus("Authenticated"); window.showChatScreen(); }
        else { log("No session found"); setAuthStatus(""); window.showAuthScreen(); }
    } catch (error) {
        console.error("AUTH INITIALIZATION FAILED:", error); authToken = null; userId = null;
        setAuthStatus("Authentication error: " + (error?.message || "Unknown error"));
        if (window.showAuthScreen) { window.showAuthScreen(); }
    }
}
async function getAuthToken() {
    if (!supabase) { console.error("Supabase client not initialized"); return null }
    try {
        const { data, error } = await supabase.auth.getSession();
        if (error) { console.error("getSession error:", error); authToken = null; userId = null; return null }
        const session = data?.session || null; authToken = session?.access_token || null; userId = session?.user?.id || null;
        log("Auth session:", { authenticated:!!authToken, userId }); return authToken;
    } catch (error) { console.error("Auth initialization failed:", error); authToken = null; userId = null; return null }
}
function getAuthHeaders() { const h = { "Accept": "application/json" }; if (authToken) h.Authorization = `Bearer ${authToken}`; return h }
async function doLogin() {
    const email = $("emailInput").value.trim(); const password = $("passwordInput").value;
    if (!email ||!password) { $("authError").textContent = "Enter email and password"; return }
    if (!supabase) { $("authError").textContent = "Authentication is still loading. Please wait."; return }
    const btn = $("loginBtn"); btn.disabled = true; btn.textContent = "Signing in...";
    $("authError").style.color = "#64748b"; $("authError").textContent = "Authenticating...";
    try {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) { $("authError").style.color = "#ef4444"; $("authError").textContent = error.message; return }
        if (!data?.session?.access_token) { throw new Error("Supabase returned no access token.") }
        $("authError").style.color = "#22c55e"; $("authError").textContent = "Login successful!";
    } catch (error) { console.error("LOGIN EXCEPTION:", error); $("authError").style.color = "#ef4444"; $("authError").textContent = error?.message || "Login failed";
    } finally { btn.disabled = false; btn.textContent = "Sign In" }
}
async function doSignup() {
    const email = $("emailInput").value.trim(); const password = $("passwordInput").value;
    if (!email ||!password) return alert("Enter email and password");
    if (password.length < 6) return alert("Password must be 6+ characters");
    if (!supabase) return alert("Auth loading..."); $("authError").textContent = "Creating account...";
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) { $("authError").textContent = error.message; return }
    $("authError").style.color = "#22c55e"; $("authError").textContent = "Check email to confirm, then Sign In."
}
async function doLogout() { await supabase?.auth.signOut(); authToken = null; userId = null; location.reload() }
window.getAuthHeaders = getAuthHeaders; window.getAuthToken = getAuthToken; window.doLogin = doLogin;
window.doSignup = doSignup; window.doLogout = doLogout; window.userId = () => userId;
window.authToken = () => authToken; window.initAuth = initAuth;
