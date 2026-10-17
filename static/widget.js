/*
 * Website assistant widget.
 *
 *   <script src="https://YOUR-HOST/widget.js" data-site="your-slug" defer></script>
 *
 * Options:
 *   data-open="true"                     start expanded (floating mode)
 *   data-mode="inline" data-target="#el" render inside an element instead of a floating bubble
 *
 * Renders inside a shadow root so the host site's CSS can't break it. Host pages
 * can theme it with CSS custom properties (they inherit through the shadow root):
 *   --assistant-font, --assistant-surface, --assistant-bg, --assistant-ink,
 *   --assistant-muted, --assistant-line
 * Exposes window.assistantAsk(question) so page buttons can ask on the visitor's behalf.
 */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || !script.dataset.site) {
    console.error("[assistant] widget.js needs a data-site attribute");
    return;
  }
  var slug = script.dataset.site;
  var apiBase = new URL(script.src).origin + "/api/" + encodeURIComponent(slug);
  var inline = script.dataset.mode === "inline";
  var startOpen = inline || script.dataset.open === "true";

  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var canSpeak = "speechSynthesis" in window;

  var ICONS = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
    speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg>',
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 19v3"/></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>'
  };

  var CSS =
    ':host{all:initial}' +
    '*{box-sizing:border-box;font-family:var(--assistant-font,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif)}' +
    '.launcher{position:fixed;right:20px;bottom:20px;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;' +
    'background:var(--accent);color:var(--on-accent);box-shadow:0 10px 30px -8px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:2147483646;transition:transform .15s}' +
    '.launcher:hover{transform:scale(1.05)}.launcher svg{width:26px;height:26px}' +
    '.panel{display:none;flex-direction:column;overflow:hidden;background:var(--assistant-surface,#fff);color:var(--assistant-ink,#1f2937)}' +
    '.panel.open{display:flex}' +
    '.floating{position:fixed;right:20px;bottom:92px;width:384px;max-width:calc(100vw - 32px);height:580px;max-height:calc(100vh - 120px);' +
    'border-radius:18px;box-shadow:0 24px 60px -16px rgba(0,0,0,.35);z-index:2147483647;border:1px solid var(--assistant-line,#e5e7eb)}' +
    '.inline{position:relative;width:100%;height:100%}' +
    '.head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--assistant-line,#e5e7eb)}' +
    '.avatar{flex:none;width:36px;height:36px;border-radius:50%;background:var(--accent);color:var(--on-accent);display:flex;align-items:center;justify-content:center;font-weight:600;font-size:15px}' +
    '.who{flex:1;min-width:0;line-height:1.25}' +
    '.who b{display:block;font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.who small{font-size:12.5px;color:var(--assistant-muted,#6b7280);display:flex;align-items:center;gap:6px}' +
    '.who small::before{content:"";width:7px;height:7px;border-radius:50%;background:#22a06b}' +
    '.icon{flex:none;background:transparent;border:1px solid var(--assistant-line,#e5e7eb);color:var(--assistant-muted,#6b7280);width:36px;height:36px;border-radius:10px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:color .15s,border-color .15s,background .15s}' +
    '.icon[hidden]{display:none}.icon:hover{color:var(--assistant-ink,#111827)}' +
    '.icon[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}' +
    '.icon svg{width:18px;height:18px}' +
    '.log{flex:1;overflow-y:auto;padding:22px 18px;display:flex;flex-direction:column;gap:14px;background:var(--assistant-bg,#f8fafc);scroll-behavior:smooth}' +
    '.msg{max-width:88%;font-size:15px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere;animation:in .25s ease both}' +
    '.instant .msg{animation:none}' +
    '@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}' +
    '.bot{align-self:flex-start;background:var(--assistant-surface,#fff);border:1px solid var(--assistant-line,#e5e7eb);padding:12px 15px;border-radius:16px 16px 16px 4px}' +
    '.bot{white-space:normal}.bot p{margin:0 0 8px}.bot p:last-child,.bot ul:last-child{margin-bottom:0}' +
    '.bot ul{margin:2px 0 8px;padding-left:18px}.bot li{margin:3px 0}.bot li::marker{color:var(--accent)}' +
    '.user{align-self:flex-end;background:var(--accent);color:var(--on-accent);padding:10px 15px;border-radius:16px 16px 4px 16px}' +
    '.err{border-color:#f3c4c4;color:#a12b2b}' +
    '.src{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;white-space:normal}' +
    '.src a{font-size:12.5px;line-height:1;padding:7px 10px;border-radius:999px;border:1px solid var(--assistant-line,#e5e7eb);color:var(--assistant-muted,#6b7280);text-decoration:none;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
    '.src a::before{content:"\\2197  "}' +
    '.src a:hover{color:var(--assistant-ink,#111827);border-color:var(--assistant-muted,#9ca3af)}' +
    '.chips{display:flex;flex-wrap:wrap;gap:8px}' +
    '.chip{border:1px solid var(--assistant-line,#e5e7eb);color:var(--assistant-ink,#1f2937);background:var(--assistant-surface,#fff);border-radius:999px;padding:8px 13px;font-size:13.5px;cursor:pointer;transition:border-color .15s,color .15s}' +
    '.chip:hover{border-color:var(--accent);color:var(--accent)}' +
    '.dots{display:inline-flex;gap:5px;padding:4px 0}.dots i{width:7px;height:7px;border-radius:50%;background:var(--assistant-muted,#9ca3af);animation:b 1.1s infinite}' +
    '.dots i:nth-child(2){animation-delay:.15s}.dots i:nth-child(3){animation-delay:.3s}' +
    '@keyframes b{0%,80%,100%{opacity:.3;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}' +
    'form{display:flex;align-items:center;gap:8px;margin:0;padding:12px;border-top:1px solid var(--assistant-line,#e5e7eb);background:var(--assistant-surface,#fff)}' +
    'input{flex:1;min-width:0;height:46px;border:1px solid var(--assistant-line,#d1d5db);border-radius:12px;padding:0 14px;font-size:15px;outline:none;color:var(--assistant-ink,#111827);background:var(--assistant-bg,#fff)}' +
    'input::placeholder{color:var(--assistant-muted,#9ca3af)}' +
    'input:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}' +
    '.send,.mic{flex:none;border:0;border-radius:12px;width:46px;height:46px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:opacity .15s}' +
    '.send{background:var(--accent);color:var(--on-accent)}.send:disabled{opacity:.45;cursor:default}' +
    '.mic{background:transparent;border:1px solid var(--assistant-line,#e5e7eb);color:var(--assistant-muted,#4b5563)}' +
    '.mic.live{border-color:#dc2626;color:#dc2626;animation:p 1.2s infinite}' +
    '@keyframes p{50%{box-shadow:0 0 0 6px rgba(220,38,38,.14)}}' +
    '.send svg,.mic svg{width:20px;height:20px}' +
    '.foot{text-align:center;font-size:11.5px;color:var(--assistant-muted,#9ca3af);padding:0 12px 10px;background:var(--assistant-surface,#fff)}' +
    'button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}' +
    '@media (max-width:480px){.floating{right:0;bottom:0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0;border:0}}' +
    '@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}';

  var mount = inline ? document.querySelector(script.dataset.target || "") : document.body;
  if (!mount) {
    console.error("[assistant] data-target not found: " + script.dataset.target);
    return;
  }
  var host = document.createElement("div");
  host.setAttribute("data-assistant", slug);
  if (inline) host.style.cssText = "display:block;width:100%;height:100%";
  mount.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  root.innerHTML =
    "<style>" + CSS + "</style>" +
    (inline ? "" : '<button class="launcher" aria-label="Open chat" aria-expanded="false">' + ICONS.chat + "</button>") +
    '<section class="panel ' + (inline ? "inline" : "floating") + '" role="region" aria-label="Chat assistant">' +
    '<div class="head"><div class="avatar" aria-hidden="true">A</div>' +
    '<div class="who"><b class="name">Assistant</b><small class="status">Online</small></div>' +
    '<button class="icon reset" title="New conversation" aria-label="Start a new conversation" hidden>' + ICONS.reset + "</button>" +
    (canSpeak ? '<button class="icon speak" aria-pressed="false" title="Read answers aloud" aria-label="Read answers aloud">' + ICONS.speaker + "</button>" : "") +
    (inline ? "" : '<button class="icon close" aria-label="Close chat">' + ICONS.close + "</button>") +
    "</div>" +
    '<div class="log" aria-live="polite"></div>' +
    "<form>" +
    '<input type="text" placeholder="Ask a question..." aria-label="Your question" maxlength="500" autocomplete="off" />' +
    (SpeechRecognition ? '<button type="button" class="mic" title="Ask by voice" aria-label="Ask by voice">' + ICONS.mic + "</button>" : "") +
    '<button type="submit" class="send" aria-label="Send">' + ICONS.send + "</button>" +
    "</form>" +
    '<div class="foot">Answers come from this website and may be incomplete.</div>' +
    "</section>";

  var $ = function (sel) { return root.querySelector(sel); };
  var panel = $(".panel"), log = $(".log"), form = $("form"), input = $("input"), send = $(".send");
  var mic = $(".mic"), speakBtn = $(".speak"), launcher = $(".launcher"), resetBtn = $(".reset");
  var history = [];
  var busy = false, speakOn = false, greeted = false, ready = false, pending = null;
  var info = { name: "Assistant", url: "", color: "#2563eb", on_color: "#ffffff", suggestions: [] };

  function setAccent(color, onColor) {
    host.style.setProperty("--accent", color);
    host.style.setProperty("--on-accent", onColor || "#ffffff");
  }
  setAccent(info.color, info.on_color);

  function scroll() { log.scrollTop = log.scrollHeight; }

  function shortTitle(title) {
    return (title || "").split(/\s[|–—-]\s/)[0].trim() || title;
  }

  // Models sometimes reply in markdown despite instructions; show it as clean text and lists.
  function renderAnswer(el, text) {
    var clean = String(text)
      .replace(/\*\*(.+?)\*\*/g, "$1").replace(/__(.+?)__/g, "$1")
      .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, "$1")
      .replace(/^#{1,6}\s*/gm, "");
    var list = null;
    clean.split(/\n/).forEach(function (line) {
      var item = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
      if (item) {
        if (!list) { list = document.createElement("ul"); el.appendChild(list); }
        var li = document.createElement("li"); li.textContent = item[1]; list.appendChild(li);
      } else if (line.trim()) {
        list = null;
        var p = document.createElement("p"); p.textContent = line.trim(); el.appendChild(p);
      }
    });
  }

  function addMessage(text, who, extraClass) {
    var el = document.createElement("div");
    el.className = "msg " + who + (extraClass ? " " + extraClass : "");
    if (who === "bot" && text) renderAnswer(el, text); else el.textContent = text;
    log.appendChild(el);
    scroll();
    return el;
  }

  // The conversation survives page navigation within the visit (sessionStorage), never across visitors.
  var storeKey = "assistant:" + slug;
  var transcript = [];
  function save() {
    try { sessionStorage.setItem(storeKey, JSON.stringify({ history: history, transcript: transcript })); } catch (e) {}
    if (resetBtn) resetBtn.hidden = transcript.length === 0;
  }
  function restore() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(storeKey) || "null");
      if (!saved || !saved.transcript || !saved.transcript.length) return false;
      history = saved.history || [];
      transcript = saved.transcript;
      log.classList.add("instant");  // restored messages appear as they were, without animating in
      transcript.forEach(function (m) {
        var el = addMessage(m.text, m.who);
        if (m.sources) addSources(el, m.sources);
      });
      if (resetBtn) resetBtn.hidden = false;
      setTimeout(function () { log.classList.remove("instant"); }, 0);
      return true;
    } catch (e) { return false; }
  }

  function addSources(el, sources) {
    if (!sources || !sources.length) return;
    var box = document.createElement("div");
    box.className = "src";
    sources.forEach(function (s) {
      var a = document.createElement("a");
      a.href = s.url; a.target = "_blank"; a.rel = "noopener";
      a.textContent = shortTitle(s.title) || s.url;
      a.title = s.title || s.url;
      box.appendChild(a);
    });
    el.appendChild(box);
  }

  function showSuggestions() {
    if (inline || !info.suggestions.length) return;
    var chips = document.createElement("div");
    chips.className = "chips";
    info.suggestions.forEach(function (q) {
      var c = document.createElement("button");
      c.type = "button"; c.className = "chip"; c.textContent = q;
      c.addEventListener("click", function () { ask(q); });
      chips.appendChild(c);
    });
    log.appendChild(chips);
    scroll();
  }

  function greet() {
    if (greeted || !ready) return;
    greeted = true;
    addMessage("Hi! I can answer questions about " + info.name + " using their website. What would you like to know?", "bot");
    if (!restore()) showSuggestions();
  }

  function reset() {
    history = []; transcript = [];
    try { sessionStorage.removeItem(storeKey); } catch (e) {}
    log.textContent = "";
    greeted = false;
    greet();
    save();
    input.focus();
  }

  function speak(text) {
    if (!speakOn || !canSpeak) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(String(text).replace(/\*\*|__|#+ |^\s*[-•]\s+/gm, "")));
  }

  function ask(question) {
    question = (question || "").trim();
    if (!question) return;
    if (!ready) { pending = question; return; }
    if (busy) return;
    if (!panel.classList.contains("open")) open();
    busy = true; send.disabled = true;
    var chips = $(".chips");
    if (chips) chips.remove();
    addMessage(question, "user");
    var typing = addMessage("", "bot");
    typing.innerHTML = '<span class="dots" role="status" aria-label="Thinking"><i></i><i></i><i></i></span>';

    var controller = "AbortController" in window ? new AbortController() : null;
    var timer = controller && setTimeout(function () { controller.abort(); }, 40000);

    fetch(apiBase + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: history }),
      signal: controller ? controller.signal : undefined
    })
      .then(function (r) {
        // A proxy error page isn't JSON; turn it into a readable message instead of a parse error.
        return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, data: d }; });
      })
      .then(function (res) {
        typing.remove();
        if (!res.ok || !res.data.answer) throw new Error(res.data.error || "Something went wrong. Please try again.");
        var el = addMessage(res.data.answer, "bot");
        addSources(el, res.data.sources);
        history.push({ role: "user", content: question }, { role: "assistant", content: res.data.answer });
        history = history.slice(-12);
        transcript.push({ who: "user", text: question }, { who: "bot", text: res.data.answer, sources: res.data.sources });
        transcript = transcript.slice(-40);
        save();
        speak(res.data.answer);
      })
      .catch(function (err) {
        typing.remove();
        var message = err && err.name === "AbortError"
          ? "That took too long. Please try again."
          : (err && err.message && !/fetch|network/i.test(err.message) ? err.message : "Couldn't reach the assistant. Check your connection and try again.");
        addMessage(message, "bot", "err");
      })
      .then(function () { if (timer) clearTimeout(timer); busy = false; send.disabled = false; });
  }
  window.assistantAsk = ask;

  function open() {
    panel.classList.add("open");
    if (launcher) launcher.setAttribute("aria-expanded", "true");
    greet();
    if (!inline) setTimeout(function () { input.focus(); }, 50);
  }
  function close() {
    panel.classList.remove("open");
    if (launcher) { launcher.setAttribute("aria-expanded", "false"); launcher.focus(); }
    if (canSpeak) window.speechSynthesis.cancel();
  }

  if (launcher) launcher.addEventListener("click", function () { panel.classList.contains("open") ? close() : open(); });
  if ($(".close")) $(".close").addEventListener("click", close);
  root.addEventListener("keydown", function (e) { if (e.key === "Escape" && !inline) close(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); var q = input.value; input.value = ""; ask(q); });

  if (resetBtn) resetBtn.addEventListener("click", reset);

  if (speakBtn) {
    speakBtn.addEventListener("click", function () {
      speakOn = !speakOn;
      speakBtn.setAttribute("aria-pressed", String(speakOn));
      if (!speakOn) window.speechSynthesis.cancel();
    });
  }

  if (mic) {
    var recognition = new SpeechRecognition();
    recognition.lang = document.documentElement.lang || "en-US";
    recognition.interimResults = true;
    var listening = false;
    recognition.onresult = function (e) {
      var text = "";
      for (var i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      input.value = text;
      if (e.results[e.results.length - 1].isFinal) { input.value = ""; ask(text); }
    };
    var stopListening = function () { listening = false; mic.classList.remove("live"); mic.setAttribute("aria-label", "Ask by voice"); };
    recognition.onend = stopListening;
    recognition.onerror = stopListening;
    mic.addEventListener("click", function () {
      if (listening) { recognition.stop(); return; }
      listening = true; mic.classList.add("live"); mic.setAttribute("aria-label", "Stop listening");
      // A spoken question gets a spoken answer.
      speakOn = true; if (speakBtn) speakBtn.setAttribute("aria-pressed", "true");
      recognition.start();
    });
  }

  fetch(apiBase + "/info")
    .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
    .then(function (d) {
      info = d;
      ready = true;
      setAccent(d.color || "#2563eb", d.on_color);
      $(".name").textContent = d.name;
      $(".avatar").textContent = (d.name || "A").trim().charAt(0).toUpperCase();
      if (d.url) $(".status").textContent = "Answers from " + d.url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
      if (startOpen) open();
      if (pending) { var q = pending; pending = null; ask(q); }
    })
    .catch(function () { console.error("[assistant] unknown site '" + slug + "'"); host.remove(); });
})();
