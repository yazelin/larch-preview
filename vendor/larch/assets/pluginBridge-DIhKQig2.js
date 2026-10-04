import{dg as b,dh as k}from"./store-DfPU-H6m.js";const h={toast:null,addCards:"cards:write",updateCards:"cards:write",deleteCards:"cards:write",moveCards:"cards:write",setVariables:"variables:write",setSettings:null,setStorage:null,openPanel:"ui:contribute",closePanel:null,theme:"theme:write"},p=(e,r=400)=>typeof e=="string"?e.slice(0,r):"",g=e=>Array.isArray(e)?e:[],w=e=>typeof e=="string"||typeof e=="number"||typeof e=="boolean"?e:void 0,O=new Set(["id","type","pluginId","pluginCardId","pluginHtml","pluginVersion","pluginName","pluginCardName","pluginReadVars","pluginWriteVars","miniGameHtml","start"]),j=2e4;function v(e){if(!e||typeof e!="object")return null;const r={};for(const[u,s]of Object.entries(e).slice(0,40))O.has(u)||s!==void 0&&(r[u]=s);return!Object.keys(r).length||JSON.stringify(r).length>j?null:r}function I(e,r){const u=new Set(e.permissions),s=[],c=[];for(const d of g(r).slice(0,200)){const l=d||{},o=p(l.kind,40);if(!(o in h)){c.push(`不認得的動作「${o||"(空白)"}」`);continue}const m=h[o];if(m&&!u.has(m)){c.push(`「${o}」需要 ${m} 權限，這個擴充功能沒有宣告`);continue}switch(o){case"toast":{const t=p(l.message,200);t&&s.push({kind:o,message:t});break}case"addCards":{const t=g(l.cards).slice(0,100).map(n=>v(n)).filter(n=>!!n);t.length&&s.push({kind:o,cards:t,afterId:p(l.afterId,80)||void 0});break}case"updateCards":{const t=g(l.cards).slice(0,500).map(n=>{const a=n||{},i=p(a.id,80),f=v(a.patch);return i&&f?{id:i,patch:f}:null}).filter(n=>!!n);t.length&&s.push({kind:o,cards:t});break}case"deleteCards":{const t=g(l.ids).slice(0,200).map(n=>p(n,80)).filter(Boolean);t.length&&s.push({kind:o,ids:t});break}case"moveCards":{const t=g(l.positions).slice(0,500).map(n=>{const a=n||{},i=p(a.id,80),f=Number(a.x),y=Number(a.y);return i&&Number.isFinite(f)&&Number.isFinite(y)?{id:i,x:f,y}:null}).filter(n=>!!n);t.length&&s.push({kind:o,positions:t});break}case"setVariables":case"setSettings":{const t={};for(const[n,a]of Object.entries(l.values||{}).slice(0,60)){const i=w(a);i!==void 0&&(t[n.slice(0,60)]=typeof i=="string"?i.slice(0,2e3):i)}Object.keys(t).length&&s.push({kind:o,values:t});break}case"setStorage":{const t={};for(const[n,a]of Object.entries(l.values||{}).slice(0,b)){const i=n.slice(0,k);i&&(a===null?t[i]=null:(typeof a=="string"||typeof a=="number"||typeof a=="boolean")&&(t[i]=String(a)))}Object.keys(t).length&&s.push({kind:o,values:t});break}case"openPanel":{const t=p(l.panelId,60),n=e.panels?.find(a=>a.id===t);n&&n.placement!=="settings"?s.push({kind:o,panelId:t}):c.push(n?`面板「${t}」只在專案設定裡出現，不能用 openPanel 打開`:`要打開的面板「${t}」不在這個擴充功能裡`);break}case"closePanel":s.push({kind:o});break;case"theme":{const t={};for(const[n,a]of Object.entries(l.tokens||{}).slice(0,40)){const i=n.trim(),f=p(a,80).trim();!/^--[a-z0-9-]{1,60}$/i.test(i)||!/^[#a-z0-9 ,.()%+-]{1,80}$/i.test(f)||/url\s*\(|expression|javascript:|@import/i.test(f)||(t[i]=f)}Object.keys(t).length&&s.push({kind:o,tokens:t});break}}}return{effects:s,rejected:c}}function P(e){return{cards:e.cards.length,huds:e.huds?.length||0,commands:e.commands?.length||0,shortcuts:e.commands?.filter(r=>r.shortcut).length||0,panels:e.panels?.length||0,hooks:e.hooks?.length||0,theme:!!e.theme,editsProject:e.permissions.includes("cards:write"),runsOnSave:(e.hooks||[]).includes("project:save")}}const S=e=>JSON.stringify(e).replace(/</g,"\\u003c").replace(/\u2028/g,"\\u2028").replace(/\u2029/g,"\\u2029"),E=`(function(seed){
  if (window.larch && window.larch.__bridge) return;
  var own = function(object, key){ return Object.prototype.hasOwnProperty.call(object, key); };
  var post = function(message){ try { parent.postMessage(message, '*'); } catch (error) {} };
  var data = Object.create(null);
  Object.keys(seed.storage || {}).forEach(function(key){ data[key] = String(seed.storage[key]); });
  var listeners = { init: [], update: [], storage: [] };
  var emit = function(name, payload){
    (listeners[name] || []).slice().forEach(function(listener){
      try { listener(payload); } catch (error) { setTimeout(function(){ throw error; }); }
    });
  };
  var makeStorage = function(persist){
    var store = persist ? data : Object.create(null);
    var api = {};
    var define = function(name, value){ Object.defineProperty(api, name, { value: value, configurable: true, writable: true, enumerable: false }); };
    define('getItem', function(key){ key = String(key); return own(store, key) ? store[key] : null; });
    define('setItem', function(key, value){
      key = String(key); value = String(value);
      if (store[key] === value) return;
      store[key] = value;
      if (persist) post({ type: 'larch:storage:set', key: key, value: value });
    });
    define('removeItem', function(key){
      key = String(key);
      if (!own(store, key)) return;
      delete store[key];
      if (persist) post({ type: 'larch:storage:remove', key: key });
    });
    define('clear', function(){
      var keys = Object.keys(store);
      keys.forEach(function(key){ delete store[key]; });
      if (persist && keys.length) post({ type: 'larch:storage:clear' });
    });
    define('key', function(index){ var keys = Object.keys(store); return index >= 0 && index < keys.length ? keys[index] : null; });
    Object.defineProperty(api, 'length', { get: function(){ return Object.keys(store).length; }, configurable: true, enumerable: false });
    if (typeof Proxy !== 'function') return api;
    // 跟真的 localStorage 一樣，localStorage.foo、localStorage['foo'] = 'x' 也要能用。
    return new Proxy(api, {
      get: function(target, prop){
        if (prop in target) return target[prop];
        if (typeof prop === 'string' && own(store, prop)) return store[prop];
        return undefined;
      },
      set: function(target, prop, value){
        if (typeof prop !== 'string' || prop in target) return false;
        target.setItem(prop, value);
        return true;
      },
      deleteProperty: function(target, prop){ if (typeof prop === 'string') target.removeItem(prop); return true; },
      has: function(target, prop){ return prop in target || (typeof prop === 'string' && own(store, prop)); },
      ownKeys: function(){ return Object.keys(store); },
      getOwnPropertyDescriptor: function(target, prop){
        if (typeof prop === 'string' && own(store, prop)) return { value: store[prop], writable: true, enumerable: true, configurable: true };
        return undefined;
      }
    });
  };
  var local = makeStorage(true);
  var session = makeStorage(false);
  var install = function(name, value){
    try { Object.defineProperty(window, name, { configurable: true, enumerable: true, get: function(){ return value; } }); } catch (error) {}
  };
  install('localStorage', local);
  install('sessionStorage', session);
  var apply = function(key, value){
    var oldValue = own(data, key) ? data[key] : null;
    if (value === null || value === undefined) delete data[key]; else data[key] = String(value);
    var newValue = own(data, key) ? data[key] : null;
    if (oldValue === newValue) return;
    try { window.dispatchEvent(new StorageEvent('storage', { key: key, oldValue: oldValue, newValue: newValue })); } catch (error) {}
    emit('storage', { key: key, oldValue: oldValue, newValue: newValue });
  };
  var api = {
    __bridge: 1,
    plugin: seed.plugin,
    surface: seed.surface,
    view: seed.view || null,
    locale: seed.locale,
    theme: seed.theme,
    project: seed.project || null,
    settings: Object.assign({}, seed.settings || {}),
    variables: {},
    storage: {
      get: function(key){ return local.getItem(key); },
      set: function(key, value){ local.setItem(key, value); },
      remove: function(key){ local.removeItem(key); },
      clear: function(){ local.clear(); },
      keys: function(){ return Object.keys(data); },
      all: function(){ return Object.assign({}, data); },
      getJSON: function(key, fallback){
        var raw = local.getItem(key);
        if (raw === null) return fallback;
        try { return JSON.parse(raw); } catch (error) { return fallback; }
      },
      setJSON: function(key, value){ local.setItem(key, JSON.stringify(value)); }
    },
    on: function(name, listener){
      if (!listeners[name] || typeof listener !== 'function') return function(){};
      listeners[name].push(listener);
      return function(){ var list = listeners[name]; var index = list.indexOf(listener); if (index >= 0) list.splice(index, 1); };
    },
    run: function(effects){ post({ type: 'larch:effects', effects: Array.isArray(effects) ? effects : [effects] }); },
    toast: function(message){ api.run({ kind: 'toast', message: String(message) }); },
    setSettings: function(values){ api.run({ kind: 'setSettings', values: values || {} }); },
    close: function(){ post({ type: 'larch:close' }); },
    resize: function(height){ post({ type: 'larch:resize', height: Number(height) || 0 }); }
  };
  try { Object.defineProperty(window, 'larch', { value: api, configurable: true, writable: false }); } catch (error) { window.larch = api; }
  window.addEventListener('message', function(event){
    if (event.source !== parent) return;
    var message = event.data;
    if (!message || typeof message !== 'object') return;
    if (message.type === 'larch:storage:changed' && typeof message.key === 'string') { apply(message.key, message.value); return; }
    if (message.type === 'larch:storage:reset' && message.storage && typeof message.storage === 'object') {
      Object.keys(data).forEach(function(key){ if (!own(message.storage, key)) apply(key, null); });
      Object.keys(message.storage).forEach(function(key){ apply(key, message.storage[key]); });
      return;
    }
    if (message.type === 'larch:init' || message.type === 'larch:update') {
      if (message.settings && typeof message.settings === 'object') api.settings = Object.assign({}, message.settings);
      if (message.variables && typeof message.variables === 'object') api.variables = Object.assign({}, message.variables);
      if (typeof message.theme === 'string') { api.theme = message.theme; try { document.documentElement.dataset.larchTheme = message.theme; } catch (error) {} }
      if (typeof message.locale === 'string') api.locale = message.locale;
      if (message.project) api.project = message.project;
      emit(message.type === 'larch:init' ? 'init' : 'update', message);
    }
  });
  // 沙盒沒有 allow-forms：瀏覽器在送出表單前就停下來，連 submit 事件都不發。AI 寫的面板
  // 很常用 <form onsubmit> 加 preventDefault()，所以這裡把「按送出鈕」與「在欄位按 Enter」
  // 補成一個 submit 事件（不會真的送出或換頁）。當場就發，讓 submit 處理器讀到的是按下
  // 那一刻的欄位內容。Larch 的沙盒永遠不給 allow-forms，所以不會跟瀏覽器自己的送出重複。
  var implicitForm = null;
  var submit = function(form, submitter){
    if (!form || !form.isConnected) return;
    var event;
    try { event = new SubmitEvent('submit', { bubbles: true, cancelable: true, submitter: submitter || null }); }
    catch (error) { event = document.createEvent('Event'); event.initEvent('submit', true, true); }
    form.dispatchEvent(event);
  };
  var submitButtonOf = function(form){
    var controls = form.elements;
    for (var index = 0; index < controls.length; index++) {
      var control = controls[index];
      var type = (control.getAttribute('type') || (control.tagName === 'BUTTON' ? 'submit' : '')).toLowerCase();
      if ((control.tagName === 'BUTTON' || control.tagName === 'INPUT') && (type === 'submit' || type === 'image')) return control;
    }
    return null;
  };
  document.addEventListener('click', function(event){
    if (event.defaultPrevented || !event.target || !event.target.closest) return;
    var button = event.target.closest('button, input[type="submit"], input[type="image"]');
    if (!button || !button.form || button.disabled) return;
    // 在欄位按 Enter 時，瀏覽器會再替預設按鈕補一次 click：那一次已經送過了。
    if (implicitForm === button.form) return;
    var type = (button.getAttribute('type') || (button.tagName === 'BUTTON' ? 'submit' : '')).toLowerCase();
    if (type === 'submit' || type === 'image') submit(button.form, button);
  });
  var TEXT_INPUTS = ['text', 'search', 'url', 'tel', 'email', 'password', 'number', 'date', 'time', 'datetime-local', 'month', 'week'];
  document.addEventListener('keydown', function(event){
    if (event.key !== 'Enter' || event.defaultPrevented || event.isComposing || event.keyCode === 229) return;
    var input = event.target;
    if (!input || input.tagName !== 'INPUT' || !input.form || TEXT_INPUTS.indexOf((input.type || 'text').toLowerCase()) < 0) return;
    var form = input.form, button = submitButtonOf(form);
    if (button && button.disabled) return;
    var fields = 0;
    for (var index = 0; index < form.elements.length; index++) {
      var control = form.elements[index];
      if (control.tagName === 'INPUT' && TEXT_INPUTS.indexOf((control.type || 'text').toLowerCase()) >= 0) fields++;
    }
    // 跟瀏覽器的隱式送出一樣：有送出鈕，或整張表單只有一個文字欄。
    if (!button && fields !== 1) return;
    implicitForm = form;
    setTimeout(function(){ if (implicitForm === form) implicitForm = null; }, 0);
    submit(form, button);
  });
  try { document.documentElement.dataset.larchTheme = seed.theme; } catch (error) {}
  // 嵌在專案設定裡的頁面跟著內容長高，不要在設定頁裡再捲一層。
  if (seed.surface === 'settings' && typeof ResizeObserver === 'function') {
    var lastHeight = 0, measuring = false;
    var measure = function(){
      measuring = false;
      // scrollHeight 至少等於 iframe 自己的高度，只會變高不會變矮；量 <html> 的實際大小才縮得回來。
      var height = Math.ceil(document.documentElement.getBoundingClientRect().height);
      if (Math.abs(height - lastHeight) < 2) return;
      lastHeight = height;
      post({ type: 'larch:resize', height: height });
    };
    var schedule = function(){ if (!measuring) { measuring = true; requestAnimationFrame(measure); } };
    var observe = function(){ try { new ResizeObserver(schedule).observe(document.documentElement); if (document.body) new ResizeObserver(schedule).observe(document.body); } catch (error) {} schedule(); };
    if (document.body) observe(); else document.addEventListener('DOMContentLoaded', observe);
  }
  // 擴充功能沒送 larch:ready 也要拿得到 init：等它自己的腳本都跑完、監聽器掛好了再打招呼。
  var hello = function(){ post({ type: 'larch:bridge:loaded' }); };
  if (document.readyState === 'complete') setTimeout(hello, 0); else window.addEventListener('load', hello);
})`;function x(e){return`<script data-larch-bridge>${E}(${S(e)});<\/script>`}function T(e,r){const u=x(r),s=/<head(?:\s[^>]*)?>/i.exec(e);if(s)return e.slice(0,s.index+s[0].length)+u+e.slice(s.index+s[0].length);const c=/<html(?:\s[^>]*)?>/i.exec(e);if(c)return e.slice(0,c.index+c[0].length)+u+e.slice(c.index+c[0].length);const d=/<!doctype[^>]*>/i.exec(e);return d?e.slice(0,d.index+d[0].length)+u+e.slice(d.index+d[0].length):u+e}function C(e){if(!e||typeof e!="object"||Array.isArray(e))return null;const r=e;switch(r.type){case"larch:storage:set":return typeof r.key=="string"&&r.key&&typeof r.value=="string"?{type:r.type,key:r.key,value:r.value}:null;case"larch:storage:remove":return typeof r.key=="string"&&r.key?{type:r.type,key:r.key}:null;case"larch:storage:clear":case"larch:close":case"larch:bridge:loaded":case"larch:ready":return{type:r.type};case"larch:effects":return{type:r.type,effects:r.effects};case"larch:resize":return typeof r.height=="number"&&Number.isFinite(r.height)?{type:r.type,height:r.height}:null;default:return null}}export{I as f,P as p,C as r,T as w};
