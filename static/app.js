"use strict";

class BrainAuth{
  constructor(){
    this.user=null;
    this.session=null;
    this.supabase=null;
    this.initialized=false;
  }

  async init(){
    try{
      const r=await fetch("/api/auth/config",{cache:"no-store"});
      const config=await r.json();

      if(!config.supabase_url||!config.supabase_anon_key){
        this.initialized=true;
        return null;
      }

      if(!window.supabase){
        console.error("Supabase client unavailable");
        this.initialized=true;
        return null;
      }

      this.supabase=window.supabase.createClient(
        config.supabase_url,
        config.supabase_anon_key
      );

      const {data,error}=await this.supabase.auth.getSession();

      if(error)throw error;

      this.session=data.session||null;
      this.user=this.session?.user||null;
      this.initialized=true;

      this.supabase.auth.onAuthStateChange(
        (_,session)=>{
          this.session=session||null;
          this.user=session?.user||null;
          this.updateUI(this.user);

          if(this.user){
            this.hideLoginModal();
            window.loadChats?.();
          }else{
            this.showLoginModal();
          }
        }
      );

      this.updateUI(this.user);

      if(this.user){
        window.loadChats?.();
      }else{
        this.showLoginModal();
      }

      return this.user;

    }catch(error){
      console.error("Auth initialization failed:",error);
      this.initialized=true;
      return null;
    }
  }

  async signIn(email,password){
    if(!this.supabase)throw Error("Authentication is not configured.");

    const {data,error}=await this.supabase.auth.signInWithPassword({
      email,
      password
    });

    if(error)throw error;

    this.session=data.session;
    this.user=data.user;

    this.updateUI(this.user);
    this.hideLoginModal();

    return data;
  }

  async signUp(email,password){
    if(!this.supabase)throw Error("Authentication is not configured.");

    const {data,error}=await this.supabase.auth.signUp({
      email,
      password
    });

    if(error)throw error;

    return data;
  }

  async signOut(){
    if(!this.supabase)return;

    const {error}=await this.supabase.auth.signOut();

    if(error)throw error;

    this.session=null;
    this.user=null;

    this.updateUI(null);
    this.showLoginModal();
  }

  getAuthHeader(){
    const token=this.session?.access_token;
    return token?`Bearer ${token}`:null;
  }

  async fetchWithAuth(url,options={}){
    const makeRequest=async()=>{
      const headers=new Headers(options.headers||{});

      const token=this.getAuthHeader();

      if(token){
        headers.set("Authorization",token);
      }

      return fetch(url,{
        ...options,
        headers
      });
    };

    let response=await makeRequest();

    if(response.status!==401||!this.supabase){
      return response;
    }

    const {data,error}=await this.supabase.auth.refreshSession();

    if(error||!data.session){
      this.session=null;
      this.user=null;
      this.updateUI(null);
      this.showLoginModal();
      return response;
    }

    this.session=data.session;
    this.user=data.user;

    return makeRequest();
  }

  updateUI(user){
    const avatar=document.getElementById("userAvatar");
    const email=document.getElementById("userEmailDisplay");
    const login=document.getElementById("loginBtn");
    const logout=document.getElementById("logoutBtn");

    if(user){
      if(avatar)avatar.textContent=
        (user.email||"U").charAt(0).toUpperCase();

      if(email)email.textContent=user.email||"User";
      if(login)login.style.display="none";
      if(logout)logout.style.display="block";
    }else{
      if(avatar)avatar.textContent="G";
      if(email)email.textContent="Guest";
      if(login)login.style.display="block";
      if(logout)logout.style.display="none";
    }
  }

  showLoginModal(){
    const modal=document.getElementById("authModal");
    if(modal)modal.style.display="flex";
  }

  hideLoginModal(){
    const modal=document.getElementById("authModal");
    if(modal)modal.style.display="none";
  }
}

const brainAuth=new BrainAuth();

window.brainAuth=brainAuth;

window.initAuth=()=>brainAuth.init();

document.addEventListener("DOMContentLoaded",()=>{
  const loginBtn=document.getElementById("loginBtn");
  const signupBtn=document.getElementById("signupBtn");
  const logoutBtn=document.getElementById("logoutBtn");
  const close=document.getElementById("closeAuthModal");

  loginBtn?.addEventListener("click",()=>{
    brainAuth.showLoginModal();
  });

  logoutBtn?.addEventListener("click",async()=>{
    try{
      await brainAuth.signOut();
    }catch(error){
      alert(error.message||"Sign out failed.");
    }
  });

  close?.addEventListener("click",()=>{
    brainAuth.hideLoginModal();
  });

  const loginForm=document.querySelector("#loginForm form");
  const signupForm=document.querySelector("#signupForm form");

  const loginContainer=document.getElementById("loginForm");
  const signupContainer=document.getElementById("signupForm");

  loginContainer?.addEventListener("submit",async e=>{
    e.preventDefault();

    const email=document.getElementById("loginEmail")?.value.trim();
    const password=document.getElementById("loginPassword")?.value;

    try{
      await brainAuth.signIn(email,password);
      e.target.reset?.();
    }catch(error){
      alert(error.message||"Login failed.");
    }
  });

  signupContainer?.addEventListener("submit",async e=>{
    e.preventDefault();

    const email=document.getElementById("signupEmail")?.value.trim();
    const password=document.getElementById("signupPassword")?.value;

    try{
      await brainAuth.signUp(email,password);
      alert("Account created. Check your email if confirmation is required.");

      signupContainer.style.display="none";
      loginContainer.style.display="block";
    }catch(error){
      alert(error.message||"Signup failed.");
    }
  });

  document.getElementById("switchSignup")?.addEventListener("click",()=>{
    loginContainer.style.display="none";
    signupContainer.style.display="block";
  });

  document.getElementById("switchLogin")?.addEventListener("click",()=>{
    signupContainer.style.display="none";
    loginContainer.style.display="block";
  });

  document.getElementById("authModal")?.addEventListener("click",e=>{
    if(e.target===e.currentTarget){
      brainAuth.hideLoginModal();
    }
  });
});