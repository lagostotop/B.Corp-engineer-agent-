"use strict";

let userId = "00000000-0000-0000-0000-000000000001";

window.$ = id => document.getElementById(id);

function debug(...args) {
    console.log("%c[Brain 3.0]", "color:#00BFFF;font-weight:bold", ...args);
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
    const auth = $("authScreen");
    const chat = $("chatContainer");

    if (auth) auth.style.display = "none";
    if (chat) chat.style.display = "block";

    setAuthStatus("Brain 3.0 online");
}

function showChatScreen() {
    const auth = $("authScreen");
    const chat = $("chatContainer");

    if (auth) auth.style.display = "none";
    if (chat) chat.style.display = "block";

    debug("Chat screen displayed");

    if (typeof window.loadSidebar === "function") {
        window.loadSidebar();
    }
}

async function initAuth() {
    debug("Authentication disabled - test mode");

    setAuthStatus("Brain 3.0 online");
    showChatScreen();
}

async function getAuthToken() {
    return null;
}

function getAuthHeaders() {
    return {
        "Accept": "application/json"
    };
}

async function doLogin() {
    showChatScreen();
}

async function doSignup() {
    showChatScreen();
}

async function doLogout() {
    showChatScreen();
}

window.getAuthHeaders = getAuthHeaders;
window.getAuthToken = getAuthToken;
window.doLogin = doLogin;
window.doSignup = doSignup;
window.doLogout = doLogout;
window.showAuthScreen = showAuthScreen;
window.showChatScreen = showChatScreen;
window.userId = () => userId;
window.authToken = () => null;
window.initAuth = initAuth;

document.addEventListener("DOMContentLoaded", () => {
    debug("Authentication bypass enabled");
    initAuth();
});
