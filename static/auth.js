"use strict";

let userId = null;
let authToken = null;
let DEBUG = true;
let supabase = null;

window.$ = id => document.getElementById(id);

const SUPABASE_URL = "https://fcrdmwtsggbgconqvkjz.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "3tg-cgQ1_TH76WwrFxljQA_ygT2eyY0";

function debug(...args) {
    if (DEBUG) {
        console.log(
            "%c[Brain4.0 Auth]",
            "color:#00BFFF;font-weight:bold",
            ...args
        );
    }
}

function setAuthStatus(text) {
    const el = window.$("authStatus");
    if (el) el.textContent = text;
}

function showAuthError(message, isSuccess = false) {
    const el = window.$("authError");
    if (!el) return;

    el.style.color = isSuccess ? "#22c55e" : "#ef4444";
    el.textContent = message;
}

function showAuthScreen() {
    const authScreen = window.$("authScreen");
    const chatContainer = window.$("chatContainer");

    if (authScreen) authScreen.style.display = "flex";
    if (chatContainer) chatContainer.style.display = "none";
}

function showChatScreen() {
    const authScreen = window.$("authScreen");
    const chatContainer = window.$("chatContainer");

    if (authScreen) authScreen.style.display = "none";
    if (chatContainer) chatContainer.style.display = "block";

    debug("Chat screen displayed");

    if (typeof window.loadSidebar === "function") {
        window.loadSidebar();
    }
}

async function initAuth() {
    try {
        setAuthStatus("Loading authentication...");

        if (!window.supabase) {
            throw new Error(
                "Supabase SDK did not load. Check the CDN."
            );
        }

        supabase = window.supabase.createClient(
            SUPABASE_URL,
            SUPABASE_ANON_KEY,
            {
                auth: {
                    autoRefreshToken: true,
                    persistSession: true,
                    detectSessionInUrl: true
                }
            }
        );

        debug("Supabase initialized");

        supabase.auth.onAuthStateChange(
            (event, session) => {
                authToken = session?.access_token || null;
                userId = session?.user?.id || null;

                debug(
                    "Auth state:",
                    event,
                    userId
                );

                if (session) {
                    setAuthStatus("Authenticated");
                    showChatScreen();
                }

                if (event === "SIGNED_OUT") {
                    authToken = null;
                    userId = null;
                    showAuthScreen();
                }
            }
        );

        setAuthStatus("Checking session...");

        const token = await getAuthToken();

        if (token) {
            debug("Existing session found");
            setAuthStatus("Authenticated");
            showChatScreen();
        } else {
            debug("No active session");
            setAuthStatus("");
            showAuthScreen();
        }
    } catch (error) {
        console.error(
            "AUTH INIT FAILED:",
            error
        );

        setAuthStatus(
            "Authentication error: " +
            (error?.message || "Unknown error")
        );

        showAuthScreen();
    }
}

async function getAuthToken() {
    if (!supabase) return null;

    try {
        const {
            data,
            error
        } = await supabase.auth.getSession();

        if (error) {
            console.error(
                "getSession error:",
                error
            );
            return null;
        }

        authToken =
            data?.session?.access_token || null;

        userId =
            data?.session?.user?.id || null;

        return authToken;
    } catch (error) {
        console.error(
            "getAuthToken error:",
            error
        );

        return null;
    }
}

function getAuthHeaders() {
    const headers = {
        "Accept": "application/json"
    };

    if (authToken) {
        headers.Authorization =
            `Bearer ${authToken}`;
    }

    return headers;
}

async function doLogin() {
    const emailInput = window.$("emailInput");
    const passwordInput = window.$("passwordInput");
    const btn = window.$("loginBtn");

    if (!emailInput || !passwordInput || !btn) {
        console.error(
            "Login elements not found"
        );
        return;
    }

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        showAuthError(
            "Enter email and password."
        );
        return;
    }

    if (!supabase) {
        showAuthError(
            "Authentication is not initialized."
        );
        return;
    }

    btn.disabled = true;
    btn.textContent = "Signing in...";
    showAuthError("");

    try {
        debug("Attempting login:", email);

        const {
            data,
            error
        } = await supabase.auth.signInWithPassword({
            email,
            password
        });

        if (error) {
            throw error;
        }

        if (!data?.session) {
            throw new Error(
                "Login failed. No session returned."
            );
        }

        authToken =
            data.session.access_token;

        userId =
            data.session.user?.id || null;

        debug(
            "Login successful:",
            userId
        );

        showAuthError(
            "Login successful!",
            true
        );

        showChatScreen();
    } catch (error) {
        console.error(
            "Login error:",
            error
        );

        showAuthError(
            error?.message ||
            "Login failed."
        );
    } finally {
        btn.disabled = false;
        btn.textContent = "Sign In";
    }
}

async function doSignup() {
    const emailInput = window.$("emailInput");
    const passwordInput = window.$("passwordInput");
    const btn = window.$("signupBtn");

    if (!emailInput || !passwordInput || !btn) {
        console.error(
            "Signup elements not found"
        );
        return;
    }

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        showAuthError(
            "Enter email and password."
        );
        return;
    }

    if (password.length < 6) {
        showAuthError(
            "Password must be at least 6 characters."
        );
        return;
    }

    if (!supabase) {
        showAuthError(
            "Authentication is not initialized."
        );
        return;
    }

    btn.disabled = true;
    btn.textContent = "Creating account...";
    showAuthError("");

    try {
        debug("Creating account:", email);

        const {
            data,
            error
        } = await supabase.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo:
                    window.location.origin
            }
        });

        if (error) {
            throw error;
        }

        if (data?.user && !data?.session) {
            showAuthError(
                "Account created. Check your email to verify your account.",
                true
            );
        } else if (data?.session) {
            authToken =
                data.session.access_token;

            userId =
                data.session.user?.id || null;

            showAuthError(
                "Account created. You are now logged in.",
                true
            );

            showChatScreen();
        } else {
            showAuthError(
                "Account created. Check your email.",
                true
            );
        }
    } catch (error) {
        console.error(
            "Signup error:",
            error
        );

        showAuthError(
            error?.message ||
            "Signup failed."
        );
    } finally {
        btn.disabled = false;
        btn.textContent = "Create Account";
    }
}

async function doLogout() {
    try {
        if (supabase) {
            await supabase.auth.signOut();
        }
    } catch (error) {
        console.error(
            "Logout error:",
            error
        );
    }

    authToken = null;
    userId = null;

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

document.addEventListener(
    "DOMContentLoaded",
    () => {
        const loginBtn = window.$("loginBtn");
        const signupBtn = window.$("signupBtn");
        const logoutBtn = window.$("logoutBtn");

        if (loginBtn) {
            loginBtn.addEventListener(
                "click",
                doLogin
            );
        }

        if (signupBtn) {
            signupBtn.addEventListener(
                "click",
                doSignup
            );
        }

        if (logoutBtn) {
            logoutBtn.addEventListener(
                "click",
                doLogout
            );
        }

        const passwordInput =
            window.$("passwordInput");

        if (passwordInput) {
            passwordInput.addEventListener(
                "keydown",
                event => {
                    if (
                        event.key === "Enter"
                    ) {
                        event.preventDefault();
                        doLogin();
                    }
                }
            );
        }

        debug(
            "Auth event listeners attached"
        );

        initAuth();
    }
);
