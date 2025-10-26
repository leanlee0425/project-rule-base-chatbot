// frontend/website/chat/chat.js
(function () {
  const API_BASE = (window.API_BASE || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const CHAT_URL = API_BASE + "/chat";

  // Persist context across pages (so navigation doesn’t lose the chat)
  let ctx = {};
  try {
    const saved = sessionStorage.getItem("rb_ctx");
    if (saved) ctx = JSON.parse(saved);
  } catch {}

  function saveCtx() {
    try { sessionStorage.setItem("rb_ctx", JSON.stringify(ctx || {})); } catch {}
  }

  // Build DOM
  const root = document.createElement("div");
  root.id = "rb-chat";
  root.innerHTML = `
     <div class="rb-panel" role="dialog" aria-label="Chat panel">
    <header>
      <span class="rb-title">Lean's Shopper Chatbot</span>
       <button class="rb-close" aria-label="Close chat" title="Close">×</button>
     </header>
      <div class="rb-typing">Bot is typing…</div>
      <div class="rb-messages" aria-live="polite"></div>
      <form class="rb-inputbar">
        <textarea placeholder="Type a message… (Shift+Enter for newline)"></textarea>
        <button type="submit" class="rb-send">Send</button>
      </form>
    </div>
    <button class="rb-toggle" aria-expanded="false">💬 Need Help?</button>
  `;
  document.body.appendChild(root);

  const panel = root.querySelector(".rb-panel");
  const msgs = root.querySelector(".rb-messages");
  const typing = root.querySelector(".rb-typing");
  const form = root.querySelector("form");
  const input = root.querySelector("textarea");
  const send = root.querySelector(".rb-send");
  const toggle = root.querySelector(".rb-toggle");

  function addMsg(who, text) {
    const wrap = document.createElement("div");
    wrap.className = `rb-msg ${who}`;
    const av = document.createElement("div");
    av.className = `rb-avatar ${who}`;
    av.textContent = who === "you" ? "YOU" : "BOT";
    const b = document.createElement("div");
    b.className = "rb-bubble";
    b.textContent = text;
    wrap.appendChild(av);
    wrap.appendChild(b);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function setTyping(on) {
    root.classList.toggle("typing", !!on);
  }

  function openPanel() {
    root.classList.add("open");
    toggle.setAttribute("aria-expanded", "true");
    input.focus();
  }

  const closeBtn = root.querySelector(".rb-close");

closeBtn.addEventListener("click", () => {
  closePanel();
  // (optional) remember minimized state for this tab
  try { sessionStorage.setItem("rb_open", "0"); } catch {}
});


  function closePanel() {
    root.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  }

  toggle.addEventListener("click", () => {
    if (root.classList.contains("open")) closePanel();
    else openPanel();
  });

  // Optional greeting (only once per session)
//   if (!sessionStorage.getItem("rb_greeted")) {
//     sessionStorage.setItem("rb_greeted", "1");
//     addMsg("bot", "Hello! How can I assist you today?");
//   }

  addMsg("bot", "Hello! How can I assist you today?");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    addMsg("you", message);
    input.value = "";
    send.disabled = true;
    setTyping(true);

    try {
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, context: ctx }),
      });
      const data = await res.json();
      setTyping(false);

      // keep / persist context
      ctx = data.context || {};
      saveCtx();

      addMsg("bot", data.reply || "(No reply)");

      // end_session UX: lock input
      if (ctx.end_session) {
        input.disabled = true;
        send.disabled = true;
        input.placeholder = "Session ended. Refresh or reopen to start a new chat.";
      } else {
        send.disabled = false;
        input.focus();
      }
    } catch (err) {
      setTyping(false);
      addMsg("bot", "Network error. Is the API up at: " + CHAT_URL + " ?");
      console.error(err);
      send.disabled = false;
    }
  });

  // Enter to send; Shift+Enter = newline
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
})();
