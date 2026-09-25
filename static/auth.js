"use strict";

class BrainAuth{
constructor(){
this.user=null;
this.session=null;
this.supabase=null;
this.initialized=false;
this.listeners=new Set();
}

async init(){
try{
const response=await fetch("/api/auth/config",{cache:"no-store"});

if(!response.ok){
throw new Error(`Authentication configuration failed (${response.status})`);
}

const config=await response.json();

const url=config.supabase_url||"";
const key=config.supabase_publishable_key||config.supabase_anon_key||"";

if(!url||!key){
throw new Error("Authentication is not configured.");
}

if(!window.supabase){
throw new Error("Supabase client unavailable.");
}

this.supabase=window.supabase.createClient(url,key);

const{data,error}=await this.supabase.auth.getSession();

if(error)throw error;

this.session=data.session||null;
this.user=this.session?.user||null;
this.initialized=true;

this.supabase.auth.onAuthStateChange((event,session)=>{
this.session=session||null;
this.user=session?.user||null;

this.updateUI(this.user);

for(const listener of this.listeners){
Promise.resolve(listener(this.user,event)).catch(console.error);
}
});

this.updateUI(this.user);

return this.user;
}catch(error){
console.error("Auth initialization failed:",error);

this.initialized=true;
this.supabase=null;
this.session=null;
this.user=null;

this.updateUI(null);

return null;
}
}

onAuthStateChange(fn){
if(typeof fn!=="function")return()=>{};

this.listeners.add(fn);

return()=>this.listeners.delete(fn);
}

getUser(){
return this.user;
}

isAuthenticated(){
return Boolean(this.user&&this.session);
}

async signIn(email,password){
if(!this.supabase){
throw new Error("Authentication is not configured.");
}

const{data,error}=await this.supabase.auth.signInWithPassword({
email:String(email).trim(),
password
});

if(error)throw error;

this.session=data.session||null;
this.user=data.user||null;

this.updateUI(this.user);

return data;
}

async signUp(email,password,options={}){
if(!this.supabase){
throw new Error("Authentication is not configured.");
}

const{data,error}=await this.supabase.auth.signUp({
email:String(email).trim(),
password,
options
});

if(error)throw error;

this.session=data.session||null;
this.user=data.user||null;

this.updateUI(this.user);

return data;
}

async signOut(){
if(!this.supabase){
this.session=null;
this.user=null;
this.updateUI(null);
return;
}

const{error}=await this.supabase.auth.signOut();

if(error)throw error;

this.session=null;
this.user=null;

this.updateUI(null);
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
headers.set("Authorization",`Bearer ${token}`);
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

try{
const{data,error}=await this.supabase.auth.refreshSession();

if(error||!data.session){
this.session=null;
this.user=null;
this.updateUI(null);
return response;
}

this.session=data.session;
this.user=data.user||null;

this.updateUI(this.user);

response=await makeRequest();

return response;
}catch(error){
console.error("Session refresh failed:",error);

this.session=null;
this.user=null;

this.updateUI(null);

return response;
}
}

updateUI(user){
const avatar=document.getElementById("userAvatar");
const name=document.getElementById("userName");
const email=document.getElementById("userEmail");
const button=document.getElementById("authButton");

if(!user){
if(avatar)avatar.textContent="?";
if(name)name.textContent="Guest";
if(email)email.textContent="Not signed in";
if(button)button.textContent="Login";
return;
}

const metadata=user.user_metadata||{};

const display=
metadata.full_name||
metadata.name||
user.email?.split("@")[0]||
"User";

if(avatar){
avatar.textContent=
display.charAt(0).toUpperCase();
}

if(name){
name.textContent=display;
}

if(email){
email.textContent=user.email||"";
}

if(button){
button.textContent="Logout";
}
}
}

window.BrainAuth=new BrainAuth();