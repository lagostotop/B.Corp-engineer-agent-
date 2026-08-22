"use strict";

let userId = null, authToken = null, supabase = null;
const DEBUG = true;

window.$ = id => document.getElementById(id);

const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "3tg-cgQ1_TH76WwrFxljQA_ygT2eyY0";

function debug(...args) {
    if (DEBUG) console.log("%c[Brain 3.0 Auth]", "color:#00BFFF;font-weight:bold", ...args);
}

function setAuthStatus(text) {
    const el = $("authStatus");
    if (el) el.textContent = text || "";
}

function showAuthError(message, success = false) {
    const el = $("authError");
    if (!el) return;
    el.textContent = message || "";
    el.style.color = success ? "#22c55e" : "#ef4444";
}

function showAuthScreen() {
    const auth = $("authScreen"), chat = $("chatContainer");
    if (auth) auth.style.display = "flex";
    if (chat) chat.style.display = "none";
}

function showChatScreen() {
    const auth = $("authScreen"), chat = $("chatContainer");
    if (auth) auth.style.display = "none";
    if (chat) chat.style.display = "block";
    debug("Chat screen displayed");
    if (typeof window.loadSidebar === "function") window.loadSidebar();
}

async function initAuth() {
    try {
        setAuthStatus("Loading authentication...");

        if (!window.supabase?.createClient) {
            throw new Error("Supabase SDK did not load. Check the CDN.");
        }

        supabase = window.supabase.createClient(
            SUPABASE_URL,
            SUPABASE_PUBLISHABLE_KEY,
            {
                auth: {
                    autoRefreshToken: true,
                    persistSession: true,
                    detectSessionInUrl: true
                }
            }
        );

        debug("Supabase initialized");

        supabase.auth.onAuthStateChange((event, session) => {
            authToken = session?.access_token || null;
            userId = session?.user?.id || null;

            debug("Auth state:", event, userId);

            if (session) {
                setAuthStatus("Authenticated");
                showChatScreen();
            } else if (event === "SIGNED_OUT") {
                authToken = null;
                userId = null;
                setAuthStatus("");
                showAuthScreen();
            }
        });

        const token = await getAuthToken();

        if (token) {
            setAuthStatus("Authenticated");
            showChatScreen();
        } else {
            setAuthStatus("");
            showAuthScreen();
        }
    } catch (error) {
        console.error("AUTH INIT FAILED:", error);
        setAuthStatus("Authentication error");
        showAuthError(error?.message || "Authentication failed.");
        showAuthScreen();
    }
}

async function getAuthToken() {
    if (!supabase) return null;

    try {
        const { data, error } = await supabase.auth.getSession();

        if (error) throw error;

        const session = data?.session;

        authToken = session?.access_token || null;
        userId = session?.user?.id || null;

        return authToken;
    } catch (error) {
        console.error("getAuthToken:", error);
        authToken = null;
        userId = null;
        return null;
    }
}

function getAuthHeaders() {
    const headers = { Accept: "application/json" };
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    return headers;
}

async function doLogin() {
    const email = $("emailInput")?.value.trim();
    const password = $("passwordInput")?.value;
    const btn = $("loginBtn");

    if (!email || !password) {
        showAuthError("Enter email and password.");
        return;
    }

    if (!supabase) {
        showAuthError("Authentication is not initialized.");
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = "Signing in...";
    }

    showAuthError("");

    try {
        const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password
        });

        if (error) throw error;
        if (!data?.session) throw new Error("Login failed. No session returned.");

        authToken = data.session.access_token;
        userId = data.session.user?.id || null;

        debug("Login successful:", userId);
        showAuthError("Login successful!", true);
        showChatScreen();
    } catch (error) {
        console.error("Login error:", error);
        showAuthError(error?.message || "Login failed.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Sign In";
        }
    }
}

async function doSignup() {
    const email = $("emailInput")?.value.trim();
    const password = $("passwordInput")?.value;
    const btn = $("signupBtn");

    if (!email || !password) {
        showAuthError("Enter email and password.");
        return;
    }

    if (password.length < 6) {
        showAuthError("Password must be at least 6 characters.");
        return;
    }

    if (!supabase) {
        showAuthError("Authentication is not initialized.");
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = "Creating account...";
    }

    showAuthError("");

    try {
        const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo: window.location.origin
            }
        });

        if (error) throw error;

        if (data?.session) {
            authToken = data.session.access_token;
            userId = data.session.user?.id || null;
            showAuthError("Account created. You are now logged in.", true);
            showChatScreen();
        } else {
            showAuthError(
                "Account created. Check your email to verify your account.",
                true
            );
        }
    } catch (error) {
        console.error("Signup error:", error);
        showAuthError(error?.message || "Signup failed.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Create Account";
        }
    }
}

async function doLogout() {
    try {
        if (supabase) await supabase.auth.signOut();
    } catch (error) {
        console.error("Logout error:", error);
    }

    authToken = null;
    userId = null;
    setAuthStatus("");
    showAuthScreen();
}

window.getAuthHeaders = getAuthHeaders;
window.getAuthToken = getAuthToken;
window.doLogin = doLogin;
window.doSignup = doSignup;
window.doLogout = doLogout;
window.showAuthScreen = showAuthScreen;
window.showChatScreen = showChatScreen;
window.userId = () => userId;
window.authToken = () => authToken;
window.initAuth = initAuth;

document.addEventListener("DOMContentLoaded", () => {
    $("loginBtn")?.addEventListener("click", doLogin);
    $("signupBtn")?.addEventListener("click", doSignup);
    $("logoutBtn")?.addEventListener("click", doLogout);

    $("passwordInput")?.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            doLogin();
        }
    });

    debug("Auth initialized");
    initAuth();
});
