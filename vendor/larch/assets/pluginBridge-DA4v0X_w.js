import{dg as w,dh as O}from"./store-HQnaZO7-.js";const b={toast:null,addCards:"cards:write",updateCards:"cards:write",deleteCards:"cards:write",moveCards:"cards:write",setVariables:"variables:write",ensureVariables:"variables:write",setSettings:null,setStorage:null,openPanel:"ui:contribute",closePanel:null,theme:"theme:write"},p=(e,r=400)=>typeof e=="string"?e.slice(0,r):"",y=e=>Array.isArray(e)?e:[],h=e=>typeof e=="string"||typeof e=="number"||typeof e=="boolean"?e:void 0,j=new Set(["id","type","pluginId","pluginCardId","pluginHtml","pluginVersion","pluginName","pluginCardName","pluginReadVars","pluginWriteVars","miniGameHtml","start"]),S=2e4;function v(e){if(!e||typeof e!="object")return null;const r={};for(const[f,o]of Object.entries(e).slice(0,40))j.has(f)||o!==void 0&&(r[f]=o);return!Object.keys(r).length||JSON.stringify(r).length>S?null:r}function T(e,r){const f=new Set(e.permissions),o=[],u=[];for(const d of y(r).slice(0,200)){const c=d||{},n=p(c.kind,40);if(!(n in b)){u.push(`不認得的動作「${n||"(空白)"}」`);continue}const m=b[n];if(m&&!f.has(m)){u.push(`「${n}」需要 ${m} 權限，這個擴充功能沒有宣告`);continue}switch(n){case"toast":{const t=p(c.message,200);t&&o.push({kind:n,message:t});break}case"addCards":{const t=y(c.cards).slice(0,100).map(a=>v(a)).filter(a=>!!a);t.length&&o.push({kind:n,cards:t,afterId:p(c.afterId,80)||void 0});break}case"updateCards":{const t=y(c.cards).slice(0,500).map(a=>{const s=a||{},i=p(s.id,80),l=v(s.patch);return i&&l?{id:i,patch:l}:null}).filter(a=>!!a);t.length&&o.push({kind:n,cards:t});break}case"deleteCards":{const t=y(c.ids).slice(0,200).map(a=>p(a,80)).filter(Boolean);t.length&&o.push({kind:n,ids:t});break}case"moveCards":{const t=y(c.positions).slice(0,500).map(a=>{const s=a||{},i=p(s.id,80),l=Number(s.x),g=Number(s.y);return i&&Number.isFinite(l)&&Number.isFinite(g)?{id:i,x:l,y:g}:null}).filter(a=>!!a);t.length&&o.push({kind:n,positions:t});break}case"setVariables":case"setSettings":{const t={};for(const[a,s]of Object.entries(c.values||{}).slice(0,60)){const i=h(s);i!==void 0&&(t[a.slice(0,60)]=typeof i=="string"?i.slice(0,2e3):i)}Object.keys(t).length&&o.push({kind:n,values:t});break}case"setStorage":{const t={};for(const[a,s]of Object.entries(c.values||{}).slice(0,w)){const i=a.slice(0,O);i&&(s===null?t[i]=null:(typeof s=="string"||typeof s=="number"||typeof s=="boolean")&&(t[i]=String(s)))}Object.keys(t).length&&o.push({kind:n,values:t});break}case"ensureVariables":{const t=[];for(const a of y(c.variables).slice(0,60)){const s=a||{},i=p(s.name,60).trim();if(!E.test(i)){u.push(`變數名稱「${i||"(空白)"}」無效，只能用文字、數字與底線，且不能以數字開頭`);continue}const l=h(s.defaultValue),g=s.type==="number"||s.type==="boolean"||s.type==="string"?s.type:typeof l=="number"?"number":typeof l=="boolean"?"boolean":"string",k=g==="number"?Number.isFinite(Number(l))?Number(l):0:g==="boolean"?l===!0||l==="true":typeof l=="string"?l.slice(0,2e3):l===void 0?"":String(l);t.push({name:i,type:g,defaultValue:k,label:p(s.label,80).trim()||void 0,description:p(s.description,200).trim()||void 0,scope:s.scope==="board"?"board":"project"})}t.length&&o.push({kind:n,variables:t});break}case"openPanel":{const t=p(c.panelId,60),a=e.panels?.find(s=>s.id===t);a&&a.placement!=="settings"?o.push({kind:n,panelId:t}):u.push(a?`面板「${t}」只在專案設定裡出現，不能用 openPanel 打開`:`要打開的面板「${t}」不在這個擴充功能裡`);break}case"closePanel":o.push({kind:n});break;case"theme":{const t={};for(const[a,s]of Object.entries(c.tokens||{}).slice(0,40)){const i=a.trim(),l=p(s,80).trim();!/^--[a-z0-9-]{1,60}$/i.test(i)||!/^[#a-z0-9 ,.()%+-]{1,80}$/i.test(l)||/url\s*\(|expression|javascript:|@import/i.test(l)||(t[i]=l)}Object.keys(t).length&&o.push({kind:n,tokens:t});break}}}return{effects:o,rejected:u}}const E=/^[A-Za-z_\u3400-\u9fff][A-Za-z0-9_\u3400-\u9fff]{0,59}$/;function C(e,r,f,o){const u=n=>e.some(m=>m.name===n&&(m.scope!=="board"||m.boardId===f)),d=[...e],c=[];for(const n of r){if(u(n.name)||c.includes(n.name))continue;const m=n.scope==="board";d.push({id:o(),name:n.name,label:n.label||n.name,type:n.type,defaultValue:n.defaultValue,description:n.description,scope:m?"board":"project",boardId:m?f:void 0}),c.push(n.name)}return{variables:d,added:c}}function V(e){return{cards:e.cards.length,huds:e.huds?.length||0,commands:e.commands?.length||0,shortcuts:e.commands?.filter(r=>r.shortcut).length||0,panels:e.panels?.length||0,hooks:e.hooks?.length||0,theme:!!e.theme,editsProject:e.permissions.includes("cards:write"),runsOnSave:(e.hooks||[]).includes("project:save")}}const x=e=>JSON.stringify(e).replace(/</g,"\\u003c").replace(/\u2028/g,"\\u2028").replace(/\u2029/g,"\\u2029"),N=`(function(seed){
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
})`;function I(e){return`<script data-larch-bridge>${N}(${x(e)});<\/script>`}function _(e,r){const f=I(r),o=/<head(?:\s[^>]*)?>/i.exec(e);if(o)return e.slice(0,o.index+o[0].length)+f+e.slice(o.index+o[0].length);const u=/<html(?:\s[^>]*)?>/i.exec(e);if(u)return e.slice(0,u.index+u[0].length)+f+e.slice(u.index+u[0].length);const d=/<!doctype[^>]*>/i.exec(e);return d?e.slice(0,d.index+d[0].length)+f+e.slice(d.index+d[0].length):f+e}function A(e){if(!e||typeof e!="object"||Array.isArray(e))return null;const r=e;switch(r.type){case"larch:storage:set":return typeof r.key=="string"&&r.key&&typeof r.value=="string"?{type:r.type,key:r.key,value:r.value}:null;case"larch:storage:remove":return typeof r.key=="string"&&r.key?{type:r.type,key:r.key}:null;case"larch:storage:clear":case"larch:close":case"larch:bridge:loaded":case"larch:ready":return{type:r.type};case"larch:effects":return{type:r.type,effects:r.effects};case"larch:resize":return typeof r.height=="number"&&Number.isFinite(r.height)?{type:r.type,height:r.height}:null;default:return null}}export{T as f,C as m,V as p,A as r,_ as w};
