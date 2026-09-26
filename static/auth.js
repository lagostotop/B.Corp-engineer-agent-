"use strict";

class BrainAuthClass{
constructor(){this.user=null;this.session=null;this.supabase=null;this.listeners=new Set();this.initialized=false}

async init(){
if(this.initialized)return this.user;
try{
const r=await fetch("/api/auth/config",{cache:"no-store"});
if(!r.ok)throw Error(`Authentication configuration failed (${r.status})`);
const c=await r.json(),url=c.supabase_url,key=c.supabase_publishable_key||c.supabase_anon_key;
if(!url||!key)throw Error("Authentication configuration is incomplete.");
if(!window.supabase)throw Error("Supabase client library did not load.");
this.supabase=window.supabase.createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});
const g=await this.supabase.auth.getSession();
if(g.error)throw g.error;
this.session=g.data?.session||null;
this.user=this.session?.user||null;
this.supabase.auth.onAuthStateChange((event,session)=>{
this.session=session||null;
this.user=session?.user||null;
this.updateUI(this.user);
for(const fn of this.listeners)Promise.resolve(fn(this.user,event)).catch(console.error);
});
this.initialized=true;
this.updateUI(this.user);
return this.user;
}catch(e){
console.error("Auth initialization failed:",e);
this.updateUI(null);
return null;
}
}

onAuthStateChange(fn){
if(typeof fn!=="function")return()=>{};
this.listeners.add(fn);
return()=>this.listeners.delete(fn);
}

getUser(){return this.user}
isAuthenticated(){return!!(this.user&&this.session?.access_token)}
getAuthHeader(){return this.session?.access_token?`Bearer ${this.session.access_token}`:null}

async signIn(email,password){
if(!this.initialized)await this.init();
if(!this.supabase)throw Error("Authentication is not configured.");
const r=await this.supabase.auth.signInWithPassword({email:String(email).trim(),password});
if(r.error)throw r.error;
this.session=r.data?.session||null;
this.user=r.data?.user||null;
this.updateUI(this.user);
return r.data;
}

async signUp(email,password){
if(!this.initialized)await this.init();
if(!this.supabase)throw Error("Authentication is not configured.");
const r=await this.supabase.auth.signUp({email:String(email).trim(),password});
if(r.error)throw r.error;
this.session=r.data?.session||null;
this.user=r.data?.user||null;
this.updateUI(this.user);
return r.data;
}

async signOut(){
if(this.supabase){
const r=await this.supabase.auth.signOut();
if(r.error)throw r.error;
}
this.session=null;
this.user=null;
this.updateUI(null);
}

async refresh(){
if(!this.supabase)return null;
const r=await this.supabase.auth.refreshSession();
if(r.error)throw r.error;
this.session=r.data?.session||null;
this.user=r.data?.user||null;
this.updateUI(this.user);
return this.session;
}

async fetchWithAuth(url,options={}){
if(!this.initialized)await this.init();
const run=async()=>{
const h=new Headers(options.headers||{});
const token=this.getAuthHeader();
if(token)h.set("Authorization",token);
return fetch(url,{...options,credentials:"include",headers:h});
};
let r=await run();
if(r.status!==401||!this.supabase)return r;
try{
const s=await this.refresh();
if(!s)return r;
return await run();
}catch(e){
console.error("Session refresh failed:",e);
return r;
}
}

updateUI(u){
const a=document.getElementById("userAvatar");
const n=document.getElementById("userName");
const em=document.getElementById("userEmail");
const b=document.getElementById("authBtn");
if(!u){
if(a)a.textContent="?";
if(n)n.textContent="Guest";
if(em)em.textContent="Not signed in";
if(b)b.textContent="Login";
return;
}
const m=u.user_metadata||{};
const name=m.full_name||m.name||u.email?.split("@")[0]||"User";
if(a)a.textContent=name.charAt(0).toUpperCase();
if(n)n.textContent=name;
if(em)em.textContent=u.email||"";
if(b)b.textContent="Logout";
}
}

window.BrainAuth=new BrainAuthClass();

window.BrainAuth.init=window.BrainAuth.init.bind(window.BrainAuth);
window.BrainAuth.signIn=window.BrainAuth.signIn.bind(window.BrainAuth);
window.BrainAuth.signUp=window.BrainAuth.signUp.bind(window.BrainAuth);
window.BrainAuth.signOut=window.BrainAuth.signOut.bind(window.BrainAuth);
window.BrainAuth.fetchWithAuth=window.BrainAuth.fetchWithAuth.bind(window.BrainAuth);

console.log("BrainAuth loaded:",typeof window.BrainAuth.init);