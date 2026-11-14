(function () {
  "use strict";

  var CONFIG = Object.assign(
    { apiBase: "", scanEndpoint: "/api/scan", mode: "live", timeoutMs: 4000 },
    window.DETECT_FIRST_CONFIG || {}
  );
  var STORAGE_KEY = "detect-first-demo-v1";

  // Evidence-rule observations, separate from the machine-learning prediction.
  var CATEGORIES = {
    unsolicited_job_offer: "Unsolicited job offer",
    upfront_payment_request: "Upfront payment request",
    unrealistic_earnings: "Unrealistic earnings",
    vague_job_details: "Vague job details",
    urgency_pressure: "Urgency / pressure",
    unverified_employer: "Unverified employer identity"
  };
  var CATEGORY_ALIASES = {
    unsolicited_offer: "unsolicited_job_offer",
    unsolicited: "unsolicited_job_offer",
    vague_details: "vague_job_details",
    urgency: "urgency_pressure",
    pressure: "urgency_pressure",
    unverified_employer_identity: "unverified_employer",
    unverified_identity: "unverified_employer"
  };

  // Demo conversations. `saved: true` contacts are never scanned.
  var CHATS = [
    { id: "mom", name: "Mom", saved: true,
      messages: [{ dir: "in", text: "How are you?", time: "9:41 AM" }] },
    { id: "u1", name: "124-5135-2355", saved: false,
      messages: [{ dir: "in", text: "Hi, we met yesterday.", time: "8:15 AM" }] },
    { id: "u2", name: "732-882-1944", saved: false,
      messages: [{ dir: "in", text: "Hello! We are hiring students for remote work. Deposit $60 in the next 24 hours to secure your position and start earning up to $300 per day. Reply now for onboarding details.", time: "7:52 AM" }] }
  ];

  var ICONS = {
    person: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4.500 4.500 0 1 0 0-9 4.500 4.500 0 0 0 0 9Zm0 2c-4.400 0-8 2.200-8 5v2h16v-2c0-2.800-3.600-5-8-5Z"/></svg>',
    warn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 1.500 21h21L12 3Zm1 14.500h-2v-2h2v2Zm0-3.500h-2V9.500h2V14Z"/></svg>',
    block: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20ZM4 12a8 8 0 0 1 12.900-6.300L5.700 16.900A8 8 0 0 1 4 12Zm8 8a8 8 0 0 1-4.900-1.700L18.300 7.100A8 8 0 0 1 12 20Z"/></svg>',
    shield: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.400 9.400 8 11 4.600-1.600 8-6 8-11V5l-8-3Zm-1.200 14.200-3.500-3.500 1.400-1.400 2.100 2.100 4.500-4.500 1.400 1.400-5.900 5.900Z"/></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20.500v-7l9-1.500-9-1.500v-7L22 12 3 20.500Z"/></svg>',
    ticks: '<svg viewBox="0 0 18 12" aria-hidden="true"><path d="m1 6.500 3.500 3.500L11 2.500M7.500 9l1 1L15.500 2.500" fill="none" stroke="currentColor" stroke-width="1.500" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };

  // ---------- state ----------

  // Persisted: what the user did in the demo.
  var saved = loadSaved();
  // In memory only: scan results, re-requested on every load and reset.
  var scans = {};      // chatId -> { status: "scanning" | "done" | "error", flagged, reasons, source }
  var panelOpen = {};  // chatId -> true when an accepted chat's warning was reopened
  var openChatId = null;
  var navigatedInApp = false;
  var scanRun = 0;

  function emptySaved() { return { decisions: {}, read: {}, sent: {} }; }

  function loadSaved() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (raw && typeof raw === "object") return Object.assign(emptySaved(), raw);
    } catch (e) { /* storage unavailable or corrupt: start fresh */ }
    return emptySaved();
  }

  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); } catch (e) { /* ignore */ }
  }

  // ---------- scanning (the only part that talks to the backend) ----------

  function normalizeCategory(value) {
    var key = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    key = CATEGORY_ALIASES[key] || key;
    return { key: key, label: CATEGORIES[key] || String(value) };
  }

  function normalizeResult(raw) {
    if (!raw || typeof raw.is_scam !== "boolean" || !Array.isArray(raw.reasons) ||
        typeof raw.scanned !== "boolean" || typeof raw.evidence_flagged !== "boolean" ||
        (raw.scanned ? typeof raw.model_flagged !== "boolean" : raw.model_flagged !== null) ||
        ["none", "model", "evidence", "both"].indexOf(raw.warning_source) === -1) {
      throw new Error("Invalid scan response");
    }
    var seen = {};
    var reasons = [];
    (Array.isArray(raw.reasons) ? raw.reasons : []).forEach(function (r) {
      var isObj = r && typeof r === "object";
      var name = isObj ? (r.category || r.id || r.label) : r;
      if (!name) return;
      var cat = normalizeCategory(name);
      if (seen[cat.key]) return;
      seen[cat.key] = true;
      reasons.push({ key: cat.key, label: cat.label, evidence: isObj && r.evidence ? String(r.evidence) : "" });
    });
    return { flagged: raw.is_scam, reasons: reasons, modelFlagged: raw.model_flagged,
      warningSource: raw.warning_source, scanned: raw.scanned, skippedReason: raw.skipped_reason };
  }

  function fetchLiveScan(chat, message) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, CONFIG.timeoutMs);
    return fetch(CONFIG.apiBase + CONFIG.scanEndpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message.text,
        sender: chat.name,
        is_saved_contact: chat.saved,
        is_first_message: true
      }),
      signal: controller.signal
    }).then(function (res) {
      if (!res.ok) throw new Error("Scan endpoint returned " + res.status);
      return res.json();
    }).finally(function () { clearTimeout(timer); });
  }

  function scanMessage(chat, message) {
    return fetchLiveScan(chat, message).then(function (raw) {
      return Object.assign({ source: "live" }, normalizeResult(raw));
    });
  }

  // Scan the first incoming message of every unsaved sender. Saved contacts are skipped.
  function runScans() {
    var run = ++scanRun;
    scans = {};
    CHATS.forEach(function (chat) {
      if (chat.saved) return;
      var first = chat.messages.filter(function (m) { return m.dir === "in"; })[0];
      if (!first) return;
      scans[chat.id] = { status: "scanning" };
      scanMessage(chat, first).then(function (result) {
        if (run !== scanRun) return;
        scans[chat.id] = Object.assign({ status: "done" }, result);
        render();
      }, function () {
        if (run !== scanRun) return;
        scans[chat.id] = { status: "error" };
        render();
      });
    });
    render();
  }

  // ---------- derived state ----------

  function chatById(id) { return CHATS.filter(function (c) { return c.id === id; })[0] || null; }
  function isFlagged(chat) { var s = scans[chat.id]; return Boolean(s && s.status === "done" && s.flagged); }
  function decisionFor(chat) { return saved.decisions[chat.id] || null; }
  function allMessages(chat) { return chat.messages.concat(saved.sent[chat.id] || []); }

  function warningVisible(chat) {
    if (!isFlagged(chat)) return false;
    var decision = decisionFor(chat);
    if (decision === "blocked") return false;
    return decision === "accepted" ? Boolean(panelOpen[chat.id]) : true;
  }

  // ---------- DOM helpers ----------

  function el(tag, props) {
    var node = document.createElement(tag);
    if (props) Object.keys(props).forEach(function (key) {
      if (key === "class") node.className = props[key];
      else if (key === "html") node.innerHTML = props[key];   // static icon markup only
      else if (key === "text") node.textContent = props[key];
      else if (key.slice(0, 2) === "on") node.addEventListener(key.slice(2), props[key]);
      else node.setAttribute(key, props[key]);
    });
    for (var i = 2; i < arguments.length; i++) {
      var child = arguments[i];
      if (child === null || child === undefined || child === false) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  function icon(name, cls) { return el("span", { class: "ico " + (cls || ""), html: ICONS[name] }); }

  function avatarInto(node, chat) {
    node.className = node.className.replace(/\s*avatar-(saved|unknown)/g, "") +
      (chat.saved ? " avatar-saved" : " avatar-unknown");
    node.textContent = "";
    if (chat.saved) node.textContent = chat.name.charAt(0).toUpperCase();
    else node.innerHTML = ICONS.person;
  }

  var $ = function (id) { return document.getElementById(id); };

  // ---------- rendering ----------

  function render() {
    renderList();
    renderChat();
    renderStatus();
  }

  function renderList() {
    var list = $("chat-list");
    list.textContent = "";
    CHATS.forEach(function (chat) {
      var messages = allMessages(chat);
      var last = messages[messages.length - 1];
      var decision = decisionFor(chat);
      var blocked = decision === "blocked";
      var flagged = isFlagged(chat) && !blocked;
      var unread = !saved.read[chat.id] && !blocked;

      var avatar = el("div", { class: "avatar" });
      avatarInto(avatar, chat);

      var preview = el("div", { class: "row-preview" + (blocked ? " is-blocked" : "") });
      if (blocked) {
        preview.appendChild(icon("block", "ico-muted"));
        preview.appendChild(el("span", { class: "row-preview-text", text: "You blocked this contact" }));
      } else {
        if (flagged) preview.appendChild(icon("warn", decision === "accepted" ? "ico-muted" : "ico-warn"));
        if (last.dir === "out") preview.appendChild(icon("ticks", "ico-ticks"));
        preview.appendChild(el("span", { class: "row-preview-text", text: last.text }));
      }

      var label = chat.name + (chat.saved ? "" : ", not in your contacts") +
        (blocked ? ", blocked" : flagged ? ", possible job scam" : "") +
        (unread ? ", 1 unread message" : "");

      list.appendChild(
        el("button", {
          class: "row" + (unread ? " is-unread" : ""), type: "button", role: "listitem",
          "data-chat": chat.id, "aria-label": label,
          onclick: function () { openChat(chat.id); }
        },
          avatar,
          el("div", { class: "row-main" },
            el("div", { class: "row-top" },
              el("span", { class: "row-name", text: chat.name }),
              el("span", { class: "row-time", text: last.time })),
            el("div", { class: "row-bottom" },
              preview,
              unread ? el("span", { class: "badge", text: "1" }) : null)))
      );
    });
  }

  function renderChat() {
    var chat = chatById(openChatId);
    if (!chat) return;
    var scan = scans[chat.id];
    var decision = decisionFor(chat);
    var flagged = isFlagged(chat);

    avatarInto($("chat-avatar"), chat);
    $("chat-name").textContent = chat.name;
    $("chat-sub").textContent = decision === "blocked" ? "Blocked"
      : chat.saved ? "Saved contact" : "Not in your contacts";

    var thread = $("thread");
    thread.textContent = "";
    thread.appendChild(el("div", { class: "chip chip-date", text: "TODAY" }));
    if (chat.saved) {
      thread.appendChild(el("div", { class: "chip chip-note", text: "Saved contact · not scanned" }));
    }
    if (!chat.saved) {
      thread.appendChild(el("div", { class: "chip chip-note", text: "This sender is not in your contacts." }));
    }

    var firstIncomingDone = false;
    allMessages(chat).forEach(function (m) {
      var isFirstIncoming = m.dir === "in" && !firstIncomingDone;
      if (isFirstIncoming) firstIncomingDone = true;
      var marked = isFirstIncoming && flagged;

      var bubble = el("div", { class: "bubble bubble-" + m.dir + (marked ? " is-flagged" : "") },
        el("span", { class: "bubble-text", text: m.text }),
        el("span", { class: "bubble-meta" },
          el("span", { text: m.time }),
          m.dir === "out" ? icon("ticks", "ico-ticks") : null));

      if (marked) {
        bubble.appendChild(el("button", {
          class: "flag-tag", type: "button", "data-action": "show-warning",
          onclick: function () {
            if (decisionFor(chat) === "accepted") { panelOpen[chat.id] = !panelOpen[chat.id]; render(); }
          }
        }, icon("warn", "ico-warn"), el("span", { text: "Flagged as a possible job scam" })));
      }
      thread.appendChild(bubble);

      if (isFirstIncoming && !chat.saved && scan) {
        if (scan.status === "scanning") {
          thread.appendChild(el("div", { class: "chip chip-scan", "data-scan": "scanning" },
            el("span", { class: "spinner" }), el("span", { text: "Checking first message…" })));
        } else if (scan.status === "error") {
          thread.appendChild(el("div", { class: "chip chip-scan", "data-scan": "error" },
            el("span", { text: "Connection error. Couldn’t check this message. " }),
            el("button", { class: "link-btn", type: "button", text: "Try again", onclick: runScans })));
        } else if (!scan.scanned) {
          thread.appendChild(el("div", { class: "chip chip-scan", "data-scan": "skipped",
            text: "Not scanned · only the first message from an unknown sender is checked." }));
        } else if (!scan.flagged) {
          thread.appendChild(el("div", { class: "chip chip-scan", "data-scan": "clean" },
            icon("shield", "ico-ok"),
            el("span", { text: "First message checked · no warning triggered. This does not prove it is safe." })));
        }
      }
    });

    if (decision === "blocked") {
      thread.appendChild(el("div", { class: "chip chip-note", "data-state": "blocked", text: "You blocked this contact." }));
    } else if (decision === "accepted" && flagged) {
      thread.appendChild(el("div", { class: "chip chip-note", "data-state": "accepted",
        text: "You chose to keep this chat. Never pay money to get a job." }));
    }

    renderDock(chat, scan, decision);
    thread.scrollTop = thread.scrollHeight;
  }

  function renderDock(chat, scan, decision) {
    var dock = $("dock");
    var previousInput = dock.querySelector(".composer-input");
    var draft = previousInput ? previousInput.value : "";
    var hadFocus = previousInput && document.activeElement === previousInput;
    dock.textContent = "";

    if (decision === "blocked") {
      dock.appendChild(el("div", { class: "blocked-bar" },
        icon("block", "ico-muted"),
        el("span", { text: "You can’t message a contact you blocked." })));
      return;
    }

    if (warningVisible(chat)) {
      dock.appendChild(buildWarning(chat, scan, decision));
      return;
    }

    var input = el("input", {
      class: "composer-input", type: "text", placeholder: "Type a message",
      "aria-label": "Type a message", autocomplete: "off", maxlength: "500"
    });
    input.value = draft;
    var form = el("form", {
      class: "composer",
      onsubmit: function (event) {
        event.preventDefault();
        var text = input.value.trim();
        if (!text) return;
        input.value = "";
        sendMessage(chat, text);
      }
    }, input, el("button", { class: "send-btn", type: "submit", "aria-label": "Send", html: ICONS.send }));
    dock.appendChild(form);
    if (hadFocus) input.focus();
  }

  // Screen 3: the warning panel.
  function buildWarning(chat, scan, decision) {
    var reasons = el("ul", { class: "warning-reasons" });
    scan.reasons.forEach(function (r) {
      reasons.appendChild(el("li", { "data-reason": r.key },
        icon("warn", "ico-warn"),
        el("div", null,
          el("div", { class: "reason-label", text: r.label }),
          r.evidence ? el("div", { class: "reason-evidence", text: r.evidence }) : null)));
    });

    var accepted = decision === "accepted";
    return el("section", { class: "warning", role: "region", "aria-labelledby": "warning-title" },
      el("div", { class: "warning-head" },
        el("span", { class: "warning-icon", html: ICONS.warn }),
        el("div", null,
          el("h2", { id: "warning-title", text: "Potential job scam detected" }),
          el("p", { text: scan.warningSource === "evidence"
            ? "Evidence-based warning. The ML classifier did not flag this message."
            : scan.warningSource === "both"
              ? "The ML classifier and separate evidence rules both flagged this message."
              : "The ML classifier flagged this message based on wording learned from job postings." }))),
      scan.reasons.length ? reasons : null,
      el("p", { class: "warning-source", text: "Reasons above are evidence-rule observations, not model explanations. A warning is not proof of fraud." }),
      el("div", { class: "warning-actions" },
        el("button", { class: "btn btn-danger", type: "button", "data-action": "block", text: "Block",
          onclick: function () { decide(chat, "blocked"); } }),
        accepted
          ? el("button", { class: "btn btn-ghost", type: "button", "data-action": "close-warning", text: "Keep chatting",
              onclick: function () { panelOpen[chat.id] = false; render(); } })
          : el("button", { class: "btn btn-ghost", type: "button", "data-action": "accept", text: "Accept Anyway",
              onclick: function () { decide(chat, "accepted"); } })));
  }

  function renderStatus() {
    var node = $("scan-status");
    var states = Object.keys(scans).map(function (id) { return scans[id]; });
    var text = "";
    var kind = "";
    if (states.some(function (s) { return s.status === "scanning"; })) {
      text = "Checking messages…";
    } else if (states.some(function (s) { return s.status === "error"; })) {
      text = "Classifier unreachable. Messages could not be checked."; kind = "error";
    } else if (states.length) {
      text = "Connected to the Detect First classifier."; kind = "live";
    }
    node.textContent = text;
    node.setAttribute("data-kind", kind);
  }

  // ---------- actions ----------

  function decide(chat, decision) {
    saved.decisions[chat.id] = decision;
    panelOpen[chat.id] = false;
    persist();
    render();
    toast(decision === "blocked" ? chat.name + " blocked" : "Chat accepted");
  }

  function sendMessage(chat, text) {
    var time = new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    (saved.sent[chat.id] = saved.sent[chat.id] || []).push({ dir: "out", text: text, time: time });
    persist();
    render();
    var input = $("dock").querySelector(".composer-input");
    if (input) input.focus();
  }

  var resetting = false;
  function resetDemo() {
    if (resetting) return;
    resetting = true;
    ++scanRun;
    closeMenu();
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, CONFIG.timeoutMs);
    fetch(CONFIG.apiBase + "/api/reset", { method: "POST", credentials: "same-origin", signal: controller.signal })
      .then(function (response) {
        if (!response.ok) throw new Error("Reset failed");
        return response.json();
      }).then(function (data) {
        if (data.reset !== true) throw new Error("Invalid reset response");
        finishReset();
      }).catch(function () {
        Object.keys(scans).forEach(function (id) { scans[id] = { status: "error" }; });
        render();
        toast("Reset failed. Check the server and retry.");
      }).finally(function () { clearTimeout(timer); resetting = false; });
  }

  function finishReset() {
    saved = emptySaved();
    panelOpen = {};
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
    closeMenu();
    if (openChatId) goHome();
    runScans();
    toast("Demo reset");
  }

  var toastTimer;
  function toast(text) {
    var node = $("toast");
    node.textContent = text;
    node.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.classList.remove("is-visible"); }, 1800);
  }

  // ---------- navigation (hash based, so the browser/phone back button works) ----------

  function openChat(id) {
    navigatedInApp = true;
    location.hash = "#/chat/" + id;
  }

  function goHome() {
    if (navigatedInApp) history.back();
    else history.replaceState(null, "", location.pathname + location.search);
    if (!navigatedInApp) applyRoute();
  }

  function applyRoute() {
    var match = /^#\/chat\/([\w-]+)$/.exec(location.hash);
    var chat = match ? chatById(match[1]) : null;
    var home = $("screen-home");
    var screen = $("screen-chat");

    if (chat) {
      openChatId = chat.id;
      if (!saved.read[chat.id]) { saved.read[chat.id] = true; persist(); }
      render();
      screen.removeAttribute("inert");
      home.setAttribute("inert", "");
      $("phone").classList.add("chat-open");
    } else {
      // Keep the conversation rendered while it slides away.
      openChatId = null;
      navigatedInApp = false;
      home.removeAttribute("inert");
      screen.setAttribute("inert", "");
      $("phone").classList.remove("chat-open");
      renderList();
    }
  }

  // ---------- menu ----------

  function closeMenu() {
    $("menu").hidden = true;
    $("menu-btn").setAttribute("aria-expanded", "false");
  }

  $("menu-btn").addEventListener("click", function (event) {
    event.stopPropagation();
    var menu = $("menu");
    menu.hidden = !menu.hidden;
    this.setAttribute("aria-expanded", String(!menu.hidden));
  });
  document.addEventListener("click", closeMenu);
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") closeMenu(); });

  Array.prototype.forEach.call(document.querySelectorAll('[data-action="reset"]'), function (button) {
    button.addEventListener("click", resetDemo);
  });
  $("back-btn").addEventListener("click", goHome);
  window.addEventListener("hashchange", applyRoute);

  // ---------- start ----------

  runScans();
  applyRoute();
})();
