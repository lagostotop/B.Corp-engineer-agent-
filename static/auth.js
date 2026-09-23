"use strict";

class BrainAuth{
constructor(){this.user=null;this.session=null;this.supabase=null;this.initialized=false;this.listeners=new Set();}

async init(){
try{
const r=await fetch("/api/auth/config",{cache:"no-store"});
const config=await r.json();
if(!config.supabase_url||!config.supabase_anon_key){this.initialized=true;return null;}
if(!window.supabase)throw Error("Supabase client unavailable.");
this.supabase=window.supabase.createClient(config.supabase_url,config.supabase_anon_key);
const{data,error}=await this.supabase.auth.getSession();
if(error)throw error;
this.session=data.session||null;
this.user=this.session?.user||null;
this.initialized=true;
this.supabase.auth.onAuthStateChange((_,session)=>{
this.session=session||null;
this.user=session?.user||null;
this.updateUI(this.user);
for(const fn of this.listeners)Promise.resolve(fn(this.user)).catch(console.error);
});
this.updateUI(this.user);
return this.user;
}catch(error){
console.error("Auth initialization failed:",error);
this.initialized=true;
return null;
}
}

onAuthStateChange(fn){
if(typeof fn!=="function")return()=>{};
this.listeners.add(fn);
return()=>this.listeners.delete(fn);
}

getUser(){return this.user;}

async signIn(email,password){
if(!this.supabase)throw Error("Authentication is not configured.");
const{data,error}=await this.supabase.auth.signInWithPassword({email,password});
if(error)throw error;
this.session=data.session;
this.user=data.user;
this.updateUI(this.user);
return data;
}

async signUp(email,password,options={}){
if(!this.supabase)throw Error("Authentication is not configured.");
const{data,error}=await this.supabase.auth.signUp({email,password,options});
if(error)throw error;
return data;
}

async signOut(){
if(!this.supabase)return;
const{error}=await this.supabase.auth.signOut();
if(error)throw error;
this.session=null;
this.user=null;
this.updateUI(null);
}

getAuthHeader(){
const token=this.session?.access_token;
return token?"Bearer "+token:null;
}

async fetchWithAuth(url,options={}){
const makeRequest=async()=>{
const headers=new Headers(options.headers||{});
const token=this.getAuthHeader();
if(token)headers.set("Authorization",token);
return fetch(url,{...options,headers});
};

let response=await makeRequest();

if(response.status!==401||!this.supabase)return response;

const{data,error}=await this.supabase.auth.refreshSession();

if(error||!data.session){
this.session=null;
this.user=null;
this.updateUI(null);
return response;
}

this.session=data.session;
this.user=data.user;
this.updateUI(this.user);

return makeRequest();
}

updateUI(user){
const avatar=document.getElementById("userAvatar");
const name=document.getElementById("userName");
const email=document.getElementById("userEmail");
const button=document.getElementById("authButton");

if(user){
const metadata=user.user_metadata||{};
const display=metadata.full_name||metadata.name||user.email?.split("@")[0]||"User";
if(avatar)avatar.textContent=display.charAt(0).toUpperCase();
if(name)name.textContent=display;
if(email)email.textContent=user.email||"";
if(button)button.textContent="Logout";
}else{
if(avatar)avatar.textContent="?";
if(name)name.textContent="Guest";
if(email)email.textContent="Not signed in";
if(button)button.textContent="Login";
}
}
}

window.BrainAuth=new BrainAuth();