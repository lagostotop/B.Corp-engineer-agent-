"use strict";

class BrainAuth {
    constructor() {
        this.user = null;
        this.session = null;
        this.initialized = false;
        this.supabase = null;
    }

    async init() {
        try {
            // Fetch config from backend
            const configRes = await fetch('/api/auth/config');
            const config = await configRes.json();
            
            if (!config.supabase_url || !config.supabase_anon_key) {
                console.warn('⚠️ Missing Supabase config - using guest mode');
                this.initialized = true;
                return null;
            }

            // Initialize Supabase
            this.supabase = window.supabase.createClient(
                config.supabase_url,
                config.supabase_anon_key
            );

            // Get current session
            const { data: { session }, error } = await this.supabase.auth.getSession();
            if (error) throw error;
            
            this.session = session;
            this.user = session?.user || null;
            this.initialized = true;

            // Set up auth state listener
            this.supabase.auth.onAuthStateChange((event, session) => {
                this.handleAuthChange(event, session);
            });

            console.log('✅ Auth initialized', this.user ? `User: ${this.user.email}` : 'Guest mode');
            return this.user;
        } catch (error) {
            console.error('Auth init error:', error);
            this.initialized = true;
            return null;
        }
    }

    handleAuthChange(event, session) {
        this.session = session;
        this.user = session?.user || null;
        
        switch(event) {
            case 'SIGNED_IN':
                this.onSignIn(this.user);
                break;
            case 'SIGNED_OUT':
                this.onSignOut();
                break;
            case 'TOKEN_REFRESHED':
                console.log('Token refreshed');
                break;
        }
    }

    async signIn(email, password) {
        const { data, error } = await this.supabase.auth.signInWithPassword({
            email,
            password
        });
        if (error) throw error;
        return data;
    }

    async signUp(email, password) {
        const { data, error } = await this.supabase.auth.signUp({
            email,
            password,
            options: {
                data: { created_at: new Date().toISOString() }
            }
        });
        if (error) throw error;
        return data;
    }

    async signOut() {
        const { error } = await this.supabase.auth.signOut();
        if (error) throw error;
        this.user = null;
        this.session = null;
        this.onSignOut();
    }

    getAuthHeader() {
        if (this.session?.access_token) {
            return `Bearer ${this.session.access_token}`;
        }
        return null;
    }

    async fetchWithAuth(url, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        const authHeader = this.getAuthHeader();
        if (authHeader) {
            headers['Authorization'] = authHeader;
        }
        
        const response = await fetch(url, {
            ...options,
            headers
        });
        
        if (response.status === 401) {
            // Try to refresh token
            const { data, error } = await this.supabase.auth.refreshSession();
            if (!error && data.session) {
                this.session = data.session;
                headers['Authorization'] = `Bearer ${data.session.access_token}`;
                return fetch(url, { ...options, headers });
            }
            throw new Error('Authentication required');
        }
        
        return response;
    }

    onSignIn(user) {
        console.log('✅ Signed in:', user.email);
        this.updateUI(user);
        this.hideLoginModal();
        if (window.loadChats) window.loadChats();
    }

    onSignOut() {
        console.log('Signed out');
        this.updateUI(null);
        this.showLoginModal();
        if (window.loadChats) window.loadChats();
    }

    updateUI(user) {
        const avatar = document.getElementById('userAvatar');
        const emailDisplay = document.getElementById('userEmailDisplay');
        const logoutBtn = document.getElementById('logoutBtn');
        const loginBtn = document.getElementById('loginBtn');
        
        if (user) {
            avatar.textContent = user.email?.charAt(0).toUpperCase() || 'U';
            emailDisplay.textContent = user.email || 'User';
            if (logoutBtn) logoutBtn.style.display = 'block';
            if (loginBtn) loginBtn.style.display = 'none';
        } else {
            avatar.textContent = 'G';
            emailDisplay.textContent = 'Guest';
            if (logoutBtn) logoutBtn.style.display = 'none';
            if (loginBtn) loginBtn.style.display = 'block';
        }
    }

    showLoginModal() {
        const modal = document.getElementById('authModal');
        if (modal) modal.style.display = 'flex';
    }

    hideLoginModal() {
        const modal = document.getElementById('authModal');
        if (modal) modal.style.display = 'none';
    }
}

// Initialize auth
const brainAuth = new BrainAuth();
window.brainAuth = brainAuth;

window.initAuth = async function() {
    await brainAuth.init();
    return brainAuth.user;
};

// Override fetch for API calls
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    if (url.startsWith('/api/') && brainAuth.session) {
        return brainAuth.fetchWithAuth(url, options);
    }
    return originalFetch(url, options);
};

// DOM ready - setup auth UI
document.addEventListener('DOMContentLoaded', function() {
    const loginBtn = document.getElementById('loginBtn');
    const signupBtn = document.getElementById('signupBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const closeModal = document.getElementById('closeAuthModal');

    if (loginBtn) {
        loginBtn.addEventListener('click', () => brainAuth.showLoginModal());
    }

    if (signupBtn) {
        signupBtn.addEventListener('click', () => {
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('signupForm').style.display = 'block';
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await brainAuth.signOut();
        });
    }

    if (closeModal) {
        closeModal.addEventListener('click', () => brainAuth.hideLoginModal());
    }

    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;
            try {
                await brainAuth.signIn(email, password);
                loginForm.reset();
            } catch (error) {
                alert('Login failed: ' + error.message);
            }
        });
    }

    // Signup form
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('signupEmail').value;
            const password = document.getElementById('signupPassword').value;
            try {
                await brainAuth.signUp(email, password);
                alert('Account created! Please check your email to confirm.');
                signupForm.reset();
                document.getElementById('loginForm').style.display = 'block';
                document.getElementById('signupForm').style.display = 'none';
            } catch (error) {
                alert('Signup failed: ' + error.message);
            }
        });
    }

    // Switch to login
    const switchLogin = document.getElementById('switchLogin');
    if (switchLogin) {
        switchLogin.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('loginForm').style.display = 'block';
            document.getElementById('signupForm').style.display = 'none';
        });
    }

    // Switch to signup
    const switchSignup = document.getElementById('switchSignup');
    if (switchSignup) {
        switchSignup.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('signupForm').style.display = 'block';
        });
    }

    // Close modal on overlay click
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) brainAuth.hideLoginModal();
        });
    }
});

console.log('✅ Brain Auth loaded');
