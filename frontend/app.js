(function () {
  "use strict";

  // All backend requests and response parsing live in api.js.
  var Api = window.DetectFirstApi;
  var STORAGE_KEY = "detect-first-demo-v1";

  // The starter conversations remain local; generated conversations come from server history.
  var DEMO_CHATS = [
    { id: "mom", name: "Mom", saved: true,
      messages: [{ dir: "in", text: "How are you?", time: "9:41 AM" }] },
    { id: "u1", name: "124-5135-2355", saved: false,
      messages: [{ dir: "in", text: "Hi, we met yesterday.", time: "8:15 AM" }] },
    { id: "u2", name: "732-882-1944", saved: false,
      messages: [{ dir: "in", text: "Hello! We are hiring students for remote work. Deposit $60 in the next 24 hours to secure your position and start earning up to $300 per day. Reply now for onboarding details.", time: "7:52 AM" }] }
  ];
  var AVATAR_COLORS = ["#6b8fb5", "#7e9a6c", "#b5846b", "#8a78b0", "#5f9ea0", "#b07891"];

  var ICONS = {
    person: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4.500 4.500 0 1 0 0-9 4.500 4.500 0 0 0 0 9Zm0 2c-4.400 0-8 2.200-8 5v2h16v-2c0-2.800-3.600-5-8-5Z"/></svg>',
    warn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 1.500 21h21L12 3Zm1 14.500h-2v-2h2v2Zm0-3.500h-2V9.500h2V14Z"/></svg>',
    block: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20ZM4 12a8 8 0 0 1 12.900-6.300L5.700 16.900A8 8 0 0 1 4 12Zm8 8a8 8 0 0 1-4.900-1.700L18.300 7.100A8 8 0 0 1 12 20Z"/></svg>',
    shield: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.400 9.400 8 11 4.600-1.600 8-6 8-11V5l-8-3Zm-1.200 14.200-3.500-3.500 1.400-1.400 2.100 2.100 4.500-4.500 1.400 1.400-5.900 5.900Z"/></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20.500v-7l9-1.500-9-1.500v-7L22 12 3 20.500Z"/></svg>',
    ticks: '<svg viewBox="0 0 18 12" aria-hidden="true"><path d="m1 6.500 3.500 3.500L11 2.500M7.500 9l1 1L15.500 2.500" fill="none" stroke="currentColor" stroke-width="1.500" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };

  // ---------- state ----------

  // Only local presentation state is persisted. Scans, generated chats and decisions
  // are always hydrated from the server.
  var saved = loadSaved();
  var scans = {};      // chatId -> { status: "scanning" | "done" | "error", flagged, reasons, spans, ... }
  var generated = [];
  var serverDecisions = {};
  var serverIncoming = {};
  var panelOpen = {};  // chatId -> true when an accepted chat's warning was reopened
  var openChatId = null;
  var navigatedInApp = false;
  var scanRun = 0;
  var analysisRun = 0;
  var analysisController = null;
  // Incoming-message simulation.
  var scenario = "random";
  var receiving = false;
  var receiveRun = 0;
  var receiveError = "";
  var historyRun = 0;
  var historyReady = false;
  var historyLoading = false;
  var arrival = null;  // { id, at } for the chat that just received a message

  function emptySaved() { return { read: {}, sent: {}, order: {} }; }

  function validMessage(message, dir) {
    return Boolean(message) && typeof message === "object" &&
      (dir ? message.dir === dir : message.dir === "in" || message.dir === "out") &&
      typeof message.text === "string" && message.text.length > 0 && message.text.length <= 5000 &&
      typeof message.time === "string" && message.time.length <= 20;
  }

  function loadSaved() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (raw && typeof raw === "object" && !Array.isArray(raw)) {
        var restored = emptySaved();
        var ids = {};
        DEMO_CHATS.forEach(function (chat) { ids[chat.id] = true; });
        ["read", "sent", "order"].forEach(function (key) {
          Object.keys(raw[key] || {}).forEach(function (id) {
            if (/^[\w-]{1,128}$/.test(id)) ids[id] = true;
          });
        });
        Object.keys(ids).forEach(function (id) {
          var read = raw.read && raw.read[id];
          if (read === true) restored.read[id] = 1;
          else if (Number.isInteger(read) && read > 0) restored.read[id] = read;
          var sent = raw.sent && raw.sent[id];
          if (Array.isArray(sent)) restored.sent[id] = sent.filter(function (m) { return validMessage(m); })
            .map(function (m) { return { dir: m.dir, text: m.text, time: m.time }; });
          var order = raw.order && raw.order[id];
          if (Number.isInteger(order) && order > 0) restored.order[id] = order;
        });
        return restored;
      }
    } catch (e) { /* storage unavailable or corrupt: start fresh */ }
    return emptySaved();
  }

  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); } catch (e) { /* ignore */ }
  }

  // ---------- derived state ----------

  function allChats() { return DEMO_CHATS.concat(generated); }
  function chatById(id) { return allChats().filter(function (c) { return c.id === id; })[0] || null; }
  function isFlagged(chat) { var s = scans[chat.id]; return Boolean(s && s.status === "done" && s.flagged); }
  function decisionFor(chat) { return serverDecisions[chat.id] || chat.decision || null; }
  function allMessages(chat) {
    return chat.messages.concat(serverIncoming[chat.id] || [], saved.sent[chat.id] || []);
  }
  function incomingCount(chat) {
    return allMessages(chat).filter(function (m) { return m.dir === "in"; }).length;
  }
  function unreadCount(chat) {
    if (decisionFor(chat) === "blocked") return 0;
    return Math.max(0, incomingCount(chat) - (saved.read[chat.id] || 0));
  }

  // Most recent activity first. Demo chats keep their original order until something arrives.
  function sortedChats() {
    var base = {};
    DEMO_CHATS.forEach(function (chat, index) { base[chat.id] = -index; });
    function rank(chat) { return saved.order[chat.id] || base[chat.id] || 0; }
    return allChats().sort(function (a, b) { return rank(b) - rank(a); });
  }

  function nextOrder() {
    return Object.keys(saved.order).reduce(function (max, id) { return Math.max(max, saved.order[id]); }, 0) + 1;
  }

  function warningVisible(chat) {
    if (!isFlagged(chat)) return false;
    var decision = decisionFor(chat);
    if (decision === "blocked") return false;
    return decision === "accepted" ? Boolean(panelOpen[chat.id]) : true;
  }

  function nowTime() {
    return new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }

  // ---------- scanning ----------

  // Scan a chat's first incoming message. Saved contacts are never sent to the API.
  function scanChat(chat) {
    if (chat.saved || chat.serverBacked) return;
    var first = chat.messages.filter(function (m) { return m.dir === "in"; })[0];
    if (!first) return;
    var run = scanRun;
    scans[chat.id] = { status: "scanning" };
    Api.scan(chat, first.text).then(function (result) {
      if (run !== scanRun) return;
      scans[chat.id] = Object.assign({ status: "done" }, result);
      render();
    }, function () {
      if (run !== scanRun) return;
      scans[chat.id] = { status: "error" };
      render();
    });
  }

  function runScans() {
    ++scanRun;
    scans = {};
    allChats().forEach(function (chat) {
      if (chat.serverBacked && chat.analysis) {
        scans[chat.id] = Object.assign({ status: "done" }, chat.analysis);
      } else {
        scanChat(chat);
      }
    });
    render();
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
    node.style.background = "";
    if (!chat.saved) { node.innerHTML = ICONS.person; return; }
    node.textContent = chat.name.trim().charAt(0).toUpperCase();
    if (chat.id.indexOf("g-") === 0) {
      var hash = 0;
      for (var i = 0; i < chat.name.length; i++) hash = (hash * 31 + chat.name.charCodeAt(i)) % 997;
      node.style.background = AVATAR_COLORS[hash % AVATAR_COLORS.length];
    }
  }

  var $ = function (id) { return document.getElementById(id); };

  // ---------- rendering ----------

  function render() {
    renderList();
    renderChat();
    renderStatus();
  }

  function renderTestResult(result) {
    var output = $("test-result");
    output.textContent = "";
    var reasons = el("ul", { class: "test-evidence-list" });
    result.reasons.forEach(function (reason) {
      reasons.appendChild(el("li", { "data-evidence": reason.key },
        el("div", { class: "test-evidence-title", text: reason.label }),
        reason.snippet
          ? el("blockquote", { class: "test-snippet", text: "“" + reason.snippet + "”" })
          : null,
        el("p", { class: "test-explanation", text: reason.evidence })));
    });

    output.appendChild(el("section", { class: "analysis-card", "aria-labelledby": "test-verdict" },
      el("h2", { id: "test-verdict", text: result.flagged
        ? "Combined warning triggered"
        : "No major warning signals detected" }),
      el("section", { class: "analysis-part", "aria-labelledby": "test-model-title" },
        el("h3", { id: "test-model-title", text: "Model classification" }),
        el("p", { "data-model-result": result.modelFlagged ? "flagged" : "not-flagged",
          text: result.modelFlagged
            ? "The trained model flagged this message based on wording learned from job postings."
            : "The trained model did not flag this message." }),
        el("p", { class: "test-method-note",
          text: "This is a binary prediction, not a probability or an explanation of the model." })),
      el("section", { class: "analysis-part", "aria-labelledby": "test-evidence-title" },
        el("h3", { id: "test-evidence-title", text: "Evidence-based warning categories" }),
        el("p", { class: "test-method-note",
          text: result.evidenceFlagged
            ? "At least two separate rule categories matched; this is separate from the model prediction."
            : "Fewer than two rule categories matched, so the evidence rules did not trigger a warning." }),
        result.reasons.length ? reasons
          : el("p", { class: "test-no-evidence", text: "No evidence categories matched this message." })),
      !result.flagged
        ? el("p", { class: "test-caution",
          text: "No major warning signals were detected. This does not prove the message is safe." })
        : el("p", { class: "test-caution",
          text: "A warning is not proof of fraud. The rules are limited observations and do not verify employers." })));
  }

  function analyzeTestMessage(event) {
    event.preventDefault();
    var message = $("test-message").value.trim();
    if (!message) {
      $("test-status").textContent = "Enter a message to analyze.";
      $("test-message").focus();
      return;
    }

    var run = ++analysisRun;
    if (analysisController) analysisController.abort();
    analysisController = new AbortController();
    $("analyze-btn").disabled = true;
    $("test-status").textContent = "Analyzing with the local model…";
    $("test-result").textContent = "";

    Api.analyze(message, analysisController).then(function (result) {
      if (run !== analysisRun) return;
      renderTestResult(result);
      $("test-status").textContent = "Analysis complete.";
    }).catch(function () {
      if (run !== analysisRun) return;
      $("test-result").textContent = "";
      $("test-status").textContent = "Analysis failed. No sample result was used. Check the local server and try again.";
    }).finally(function () {
      if (run === analysisRun) {
        $("analyze-btn").disabled = false;
        analysisController = null;
      }
    });
  }

  function resetTestMessage() {
    ++analysisRun;
    if (analysisController) analysisController.abort();
    analysisController = null;
    $("test-form").reset();
    $("test-result").textContent = "";
    $("test-status").textContent = "";
    $("analyze-btn").disabled = false;
    $("test-message").focus();
  }

  function renderList() {
    var list = $("chat-list");
    list.textContent = "";
    sortedChats().forEach(function (chat) {
      var messages = allMessages(chat);
      var last = messages[messages.length - 1];
      var decision = decisionFor(chat);
      var blocked = decision === "blocked";
      var flagged = isFlagged(chat) && !blocked;
      var unread = unreadCount(chat);

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
        (unread ? ", " + unread + " unread message" + (unread > 1 ? "s" : "") : "");

      var row = el("button", {
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
            unread ? el("span", { class: "badge", text: String(unread) }) : null)));

      // A just-arrived chat eases in once; re-renders continue the animation rather than restart it.
      if (arrival && arrival.id === chat.id) {
        var elapsed = Date.now() - arrival.at;
        if (elapsed < 1400) {
          row.classList.add("is-new");
          row.style.animationDelay = -elapsed + "ms";
        }
      }
      list.appendChild(row);
    });
  }

  // Message text with backend-supplied evidence spans marked. Spans are sorted and non-overlapping.
  function bubbleText(text, spans) {
    var node = el("span", { class: "bubble-text" });
    var cursor = 0;
    (spans || []).forEach(function (span) {
      if (span.start > cursor) node.appendChild(document.createTextNode(text.slice(cursor, span.start)));
      var mark = el("mark", {
        class: "hl", role: "button", tabindex: "0", "aria-haspopup": "dialog",
        "data-category": span.key, text: text.slice(span.start, span.end)
      });
      mark.addEventListener("click", function () {
        // Let people select highlighted text without the popup getting in the way.
        var selection = window.getSelection && window.getSelection();
        if (selection && !selection.isCollapsed) return;
        toggleEvidence(mark, span);
      });
      mark.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggleEvidence(mark, span); }
      });
      node.appendChild(mark);
      cursor = span.end;
    });
    if (cursor < text.length) node.appendChild(document.createTextNode(text.slice(cursor)));
    return node;
  }

  function renderChat() {
    var chat = chatById(openChatId);
    if (!chat) return;
    closeEvidence();
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
        bubbleText(m.text, marked ? scan.spans : null),
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

  // The warning panel. The model's prediction and the evidence-rule findings are reported separately.
  function buildWarning(chat, scan, decision) {
    var reasons = el("ul", { class: "warning-reasons", tabindex: "0", "aria-label": "Message evidence; scroll for all reasons" });
    scan.reasons.forEach(function (r) {
      reasons.appendChild(el("li", { "data-reason": r.key },
        icon("warn", "ico-warn"),
        el("div", null,
          el("div", { class: "reason-label", text: r.label }),
          r.evidence ? el("div", { class: "reason-evidence", text: r.evidence }) : null)));
    });

    var count = scan.reasons.length;
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
      el("dl", { class: "warning-split" },
        el("div", { "data-model": scan.modelFlagged ? "flagged" : "not-flagged" },
          el("dt", { text: "Model prediction" }),
          el("dd", { text: scan.modelFlagged ? "Flagged" : "Not flagged" })),
        el("div", { "data-evidence-count": String(count) },
          el("dt", { text: "Evidence rules" }),
          el("dd", { text: count === 0 ? "No findings" : count === 1 ? "1 finding" : count + " findings" }))),
      count ? reasons : null,
      el("p", { class: "warning-source", text: (scan.spans.length ? "Tap highlighted text in the message for details. " : "") +
        "Rule observations, not model explanations. A warning is not proof of fraud." }),
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
      text = "Live classifier connected."; kind = "live";
    }
    node.textContent = text;
    node.setAttribute("data-kind", kind);
  }

  // ---------- evidence explanation popup ----------

  var activeMark = null;

  function toggleEvidence(mark, span) {
    if (activeMark === mark) { closeEvidence(true); return; }
    closeEvidence();
    activeMark = mark;
    mark.classList.add("is-active");

    var pop = $("evidence-pop");
    $("evidence-pop-category").textContent = span.label;
    $("evidence-pop-phrase").textContent = "“" + span.phrase + "”";
    $("evidence-pop-text").textContent = span.explanation || "The analyzer did not supply an explanation for this match.";
    pop.hidden = false;

    // Place the popup just below the phrase, or above it when there is no room.
    var screen = $("screen-chat").getBoundingClientRect();
    var header = $("screen-chat").querySelector(".appbar").getBoundingClientRect();
    var rect = mark.getBoundingClientRect();
    var height = pop.offsetHeight;
    var top = rect.bottom - screen.top + 8;
    if (top + height > screen.height - 8) top = rect.top - screen.top - height - 8;
    top = Math.max(header.bottom - screen.top + 6, Math.min(top, screen.height - height - 8));
    pop.style.top = top + "px";
    $("evidence-pop-close").focus({ preventScroll: true });
  }

  function closeEvidence(restoreFocus) {
    var pop = $("evidence-pop");
    if (pop.hidden) return;
    pop.hidden = true;
    if (activeMark) {
      activeMark.classList.remove("is-active");
      if (restoreFocus && activeMark.isConnected) activeMark.focus({ preventScroll: true });
    }
    activeMark = null;
  }

  // ---------- incoming-message simulation ----------

  function scenarioById(id) {
    return Api.SCENARIOS.filter(function (s) { return s.id === id; })[0] || Api.SCENARIOS[0];
  }

  function renderReceive() {
    var button = $("receive-btn");
    button.disabled = receiving || historyLoading || resetting;
    button.classList.toggle("is-busy", receiving);
    $("receive-label").textContent = historyLoading ? "Loading history…"
      : receiving ? "Receiving…"
      : scenario === "random" ? "Receive random message"
      : "Receive: " + scenarioById(scenario).short;

    $("receive-error").hidden = !receiveError;
    $("receive-error-text").textContent = receiveError;

    var options = $("scenario-options");
    options.textContent = "";
    Api.SCENARIOS.forEach(function (item) {
      options.appendChild(el("button", {
        type: "button", role: "menuitemradio", "data-scenario": item.id,
        "aria-checked": String(item.id === scenario), text: item.label,
        onclick: function () {
          scenario = item.id;
          closeScenarioMenu();
          renderReceive();
          $("receive-btn").focus();
        }
      }));
    });
  }

  // Ask the backend for one simulated message. Only this button does that:
  // opening or reopening a chat never generates anything.
  function receiveMessage() {
    if (receiving || resetting) return;
    if (!historyReady) {
      if (!historyLoading) loadHistory();
      return;
    }
    var run = ++receiveRun;
    receiving = true;
    receiveError = "";
    closeScenarioMenu();
    renderReceive();
    Api.receiveMessage(scenario).then(function (incoming) {
      if (run === receiveRun) deliver(incoming);
    }, function (error) {
      if (run === receiveRun) receiveError = Api.describeError(error, "receive a message");
    }).finally(function () {
      if (run !== receiveRun) return;
      receiving = false;
      renderReceive();
    });
  }

  function deliver(response) {
    var incoming = response.conversation;
    var chat = chatById(incoming.id);
    if (DEMO_CHATS.some(function (item) { return item.id === incoming.id; })) {
      serverIncoming[incoming.id] = incoming.messages;
    } else if (chat) {
      chat.messages = incoming.messages;
      chat.analysis = incoming.analysis;
      chat.decision = incoming.decision;
    } else {
      generated.push(incoming);
      chat = incoming;
    }
    if (incoming.decision) serverDecisions[incoming.id] = incoming.decision;
    if (incoming.analysis) scans[incoming.id] = Object.assign({ status: "done" }, incoming.analysis);
    saved.order[chat.id] = nextOrder();
    if (openChatId === chat.id) saved.read[chat.id] = incomingCount(chat);
    persist();
    arrival = { id: chat.id, at: Date.now() };
    render();
    document.querySelector(".home-body").scrollTop = 0;
    toast("New message from " + chat.name);
  }

  function hydrateHistory(history) {
    generated = [];
    serverIncoming = {};
    serverDecisions = Object.assign({}, history.decisions);
    history.conversations.forEach(function (conversation) {
      var isStarter = DEMO_CHATS.some(function (chat) { return chat.id === conversation.id; });
      if (conversation.decision) serverDecisions[conversation.id] = conversation.decision;
      if (isStarter) {
        serverIncoming[conversation.id] = conversation.messages;
        return;
      }
      generated.push(conversation);
      if (!saved.order[conversation.id]) saved.order[conversation.id] = nextOrder();
    });
    historyReady = true;
    persist();
    runScans();
    applyRoute();
  }

  function loadHistory() {
    if (historyLoading) return;
    historyLoading = true;
    receiveError = "";
    var run = ++historyRun;
    renderReceive();
    Api.history().then(function (history) {
      if (run === historyRun) hydrateHistory(history);
    }).catch(function (error) {
      if (run !== historyRun) return;
      historyReady = false;
      receiveError = Api.describeError(error, "load conversation history");
      runScans();
      applyRoute();
    }).finally(function () {
      if (run !== historyRun) return;
      historyLoading = false;
      renderReceive();
    });
  }

  function closeScenarioMenu() {
    $("scenario-menu").hidden = true;
    $("scenario-btn").setAttribute("aria-expanded", "false");
  }

  // ---------- actions ----------

  var decisionRuns = {};
  function decide(chat, decision) {
    var run = decisionRuns[chat.id] = (decisionRuns[chat.id] || 0) + 1;
    Api.decide(chat.id, decision === "blocked" ? "block" : "accept").then(function (updated) {
      if (decisionRuns[chat.id] !== run) return;
      serverDecisions[chat.id] = updated.decision;
      panelOpen[chat.id] = false;
      render();
      toast(decision === "blocked" ? chat.name + " blocked" : "Chat accepted");
    }).catch(function (error) {
      if (decisionRuns[chat.id] !== run) return;
      toast(Api.describeError(error, "save this decision"));
    });
  }

  function sendMessage(chat, text) {
    (saved.sent[chat.id] = saved.sent[chat.id] || []).push({ dir: "out", text: text, time: nowTime() });
    persist();
    render();
    var input = $("dock").querySelector(".composer-input");
    if (input) input.focus();
  }

  var resetting = false;
  function resetDemo() {
    if (resetting) return;
    resetting = true;
    ++historyRun;
    historyLoading = false;
    ++scanRun;
    closeMenu();
    renderReceive();
    Api.reset().then(finishReset, function () {
      Object.keys(scans).forEach(function (id) { scans[id] = { status: "error" }; });
      receiveError = "Reset failed. Check the server and retry.";
      render();
      toast(receiveError);
    }).finally(function () { resetting = false; renderReceive(); });
  }

  function finishReset() {
    saved = emptySaved();
    generated = [];
    serverDecisions = {};
    serverIncoming = {};
    historyReady = true;
    panelOpen = {};
    ++receiveRun;
    receiving = false;
    receiveError = "";
    arrival = null;
    scenario = "random";
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
    closeMenu();
    closeScenarioMenu();
    renderReceive();
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

  function openTestMessage() {
    navigatedInApp = true;
    closeMenu();
    location.hash = "#/test";
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
    var chatScreen = $("screen-chat");
    var testScreen = $("screen-test");
    var testOpen = !chat && location.hash === "#/test";
    closeEvidence();
    closeScenarioMenu();

    if (chat) {
      openChatId = chat.id;
      var seen = incomingCount(chat);
      if (saved.read[chat.id] !== seen) { saved.read[chat.id] = seen; persist(); }
      render();
      chatScreen.removeAttribute("inert");
      testScreen.setAttribute("inert", "");
      home.setAttribute("inert", "");
      $("phone").classList.add("chat-open");
      $("phone").classList.remove("test-open");
    } else if (testOpen) {
      openChatId = null;
      chatScreen.setAttribute("inert", "");
      testScreen.removeAttribute("inert");
      home.setAttribute("inert", "");
      $("phone").classList.remove("chat-open");
      $("phone").classList.add("test-open");
      $("test-message").focus();
    } else {
      // Keep the conversation rendered while it slides away.
      openChatId = null;
      navigatedInApp = false;
      home.removeAttribute("inert");
      chatScreen.setAttribute("inert", "");
      testScreen.setAttribute("inert", "");
      $("phone").classList.remove("chat-open");
      $("phone").classList.remove("test-open");
      renderList();
    }
  }

  // ---------- menus and global dismissal ----------

  function closeMenu() {
    $("menu").hidden = true;
    $("menu-btn").setAttribute("aria-expanded", "false");
  }

  $("menu-btn").addEventListener("click", function (event) {
    event.stopPropagation();
    closeScenarioMenu();
    var menu = $("menu");
    menu.hidden = !menu.hidden;
    this.setAttribute("aria-expanded", String(!menu.hidden));
  });

  $("scenario-btn").addEventListener("click", function (event) {
    event.stopPropagation();
    closeMenu();
    var menu = $("scenario-menu");
    menu.hidden = !menu.hidden;
    this.setAttribute("aria-expanded", String(!menu.hidden));
    if (!menu.hidden) menu.querySelector('[aria-checked="true"]').focus();
  });

  document.addEventListener("click", function (event) {
    closeMenu();
    if (!event.target.closest("#scenario-menu")) closeScenarioMenu();
    if (!event.target.closest(".hl, #evidence-pop")) closeEvidence();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    closeMenu();
    if (!$("scenario-menu").hidden) { closeScenarioMenu(); $("scenario-btn").focus(); }
    closeEvidence(true);
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-action="reset"]'), function (button) {
    button.addEventListener("click", resetDemo);
  });
  document.querySelector('[data-action="test-message"]').addEventListener("click", openTestMessage);
  $("test-form").addEventListener("submit", analyzeTestMessage);
  $("reset-test-btn").addEventListener("click", resetTestMessage);
  $("back-btn").addEventListener("click", goHome);
  $("test-back-btn").addEventListener("click", goHome);
  $("receive-btn").addEventListener("click", receiveMessage);
  $("receive-error-dismiss").addEventListener("click", function () { receiveError = ""; renderReceive(); });
  $("evidence-pop-close").addEventListener("click", function () { closeEvidence(true); });
  // The popup is anchored to a phrase, so it goes away when that phrase moves.
  $("thread").addEventListener("scroll", function () { closeEvidence(); }, { passive: true });
  window.addEventListener("resize", function () { closeEvidence(); });
  window.addEventListener("hashchange", applyRoute);

  // ---------- start ----------

  renderReceive();
  loadHistory();
})();
