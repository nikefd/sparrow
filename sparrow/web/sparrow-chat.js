/*!
 * sparrow-chat.js — the official floating chat dock for sparrow agents.
 *
 * Zero dependencies, self-injecting CSS, framework-free. Drop it on any page
 * that talks to a sparrow Harness over SSE and you get a consistent chat UI:
 * a floating action button, a resizable slide-out dock, a conversation drawer,
 * streaming replies, tool-step chips, and citations.
 *
 *   <script src="/sparrow-chat.js"></script>
 *   <script>
 *     SparrowChat.mount({
 *       endpoint: '/api/agent/chat',
 *       conversationsApi: '/api/agent/conversations',
 *       title: 'AI Assistant',
 *       hint: 'Ask me anything…',
 *       accent: '#7c3aed',
 *     });
 *   </script>
 *
 * Markdown rendering is used if a global `marked` is present, else plain text.
 */
(function (global) {
  'use strict';

  var DEFAULTS = {
    endpoint: '/api/agent/chat',                  // POST {message, conversation_id} -> SSE
    conversationsApi: '/api/agent/conversations', // GET list / GET :id / DELETE :id
    title: 'AI Assistant',
    hint: '',
    accent: '#7c3aed',
    storageKey: 'sparrow_conv_id',
    fabIcon: '💬',
    // All user-facing strings default to English; override via `i18n` to
    // localize. Time units that follow a number use a leading space if needed.
    i18n: {
      send: 'Send',
      placeholder: 'Type a message…',
      history: 'History',
      newChat: 'New chat',
      resize: 'Resize',
      close: 'Close',
      back: 'Back',
      thinking: 'Thinking',
      emptyNew: 'Start a new chat, or open 🕘 for history.',
      newStarted: 'New chat started ✨',
      loading: 'Loading…',
      noConversations: 'No conversations yet.',
      loadFailed: 'Failed to load.',
      emptyConversation: 'No messages in this conversation yet.',
      sources: 'Sources',
      messages: 'msgs',
      untitled: 'New chat',
      del: 'Delete',
      justNow: 'just now',
      minAgo: 'm ago',
      hourAgo: 'h ago',
      dayAgo: 'd ago',
    },
  };

  function h(html) {
    var t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }

  function esc(s) {
    return (s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function md(text) {
    if (global.marked && typeof global.marked.parse === 'function') {
      try { return global.marked.parse(text || ''); } catch (e) { /* fall through */ }
    }
    return esc(text || '').replace(/\n/g, '<br>');
  }

  function relTime(ts, t) {
    if (!ts) return '';
    var ms = new Date(ts).getTime();
    if (isNaN(ms)) return '';
    var min = Math.floor(Math.max(0, Date.now() - ms) / 60000);
    if (min < 1) return t.justNow;
    if (min < 60) return min + t.minAgo;
    var hr = Math.floor(min / 60);
    if (hr < 24) return hr + t.hourAgo;
    var day = Math.floor(hr / 24);
    if (day < 7) return day + t.dayAgo;
    return new Date(ms).toISOString().slice(0, 10);
  }

  function injectStyle(accent) {
    if (document.getElementById('sparrow-chat-style')) return;
    var css = [
      '.sp-chat{--sp-accent:' + accent + ';',
      '--sp-bg:#fff;--sp-bg2:#f7f8fb;--sp-border:#e6e8ef;--sp-text:#0f172a;--sp-dim:#64748b;--sp-faint:#94a3b8}',
      // FAB
      '.sp-fab{position:fixed;right:24px;bottom:24px;z-index:9000;width:56px;height:56px;',
      'border:none;border-radius:50%;cursor:pointer;background:var(--sp-accent);color:#fff;',
      'font-size:24px;box-shadow:0 8px 24px rgba(0,0,0,.22);transition:transform .15s,box-shadow .15s}',
      '.sp-fab:hover{transform:translateY(-2px) scale(1.04);box-shadow:0 12px 28px rgba(0,0,0,.28)}',
      // dock — three sizes via data-size
      '.sp-dock{position:fixed;z-index:9000;display:flex;flex-direction:column;background:var(--sp-bg);',
      'border:1px solid var(--sp-border);border-radius:16px;box-shadow:0 16px 50px rgba(15,23,42,.22);',
      'overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;',
      'font-size:14px;color:var(--sp-text);transition:width .18s ease,height .18s ease}',
      '.sp-dock[data-size="normal"]{right:24px;bottom:96px;width:440px;height:640px;max-height:calc(100vh - 130px)}',
      '.sp-dock[data-size="large"]{right:24px;bottom:96px;width:720px;height:calc(100vh - 130px)}',
      '.sp-dock[data-size="full"]{right:0;left:0;top:0;bottom:0;width:auto;height:auto;border-radius:0;margin:auto;max-width:980px}',
      '.sp-dock.sp-hidden{display:none}',
      // header
      '.sp-head{display:flex;align-items:center;justify-content:space-between;gap:8px;',
      'padding:13px 16px;border-bottom:1px solid var(--sp-border);background:var(--sp-bg2)}',
      '.sp-title{font-weight:600;font-size:14.5px;display:flex;align-items:center;gap:7px}',
      '.sp-head-actions{display:flex;gap:4px;align-items:center}',
      '.sp-ico{background:none;border:none;border-radius:8px;cursor:pointer;color:var(--sp-dim);',
      'font-size:15px;width:30px;height:30px;display:flex;align-items:center;justify-content:center;',
      'transition:background .12s,color .12s}',
      '.sp-ico:hover{background:var(--sp-border);color:var(--sp-text)}',
      // hint
      '.sp-hint{margin:12px 16px 0;padding:10px 13px;background:var(--sp-bg2);border:1px solid var(--sp-border);',
      'border-radius:10px;font-size:12.5px;line-height:1.5;color:var(--sp-dim)}',
      // messages
      '.sp-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px}',
      '.sp-msg{padding:11px 15px;border-radius:13px;max-width:82%;font-size:14px;line-height:1.6;',
      'word-wrap:break-word;overflow-wrap:anywhere}',
      '.sp-msg.user{background:var(--sp-accent);color:#fff;align-self:flex-end;border-bottom-right-radius:3px}',
      '.sp-msg.bot{background:var(--sp-bg2);color:var(--sp-text);border:1px solid var(--sp-border);',
      'align-self:flex-start;border-bottom-left-radius:3px}',
      '.sp-msg.bot>*:first-child{margin-top:0}.sp-msg.bot>*:last-child{margin-bottom:0}',
      '.sp-msg.bot p{margin:.4em 0}.sp-msg.bot ul,.sp-msg.bot ol{margin:.4em 0;padding-left:1.3em}',
      '.sp-msg.bot pre{background:#0f172a;color:#e2e8f0;padding:11px 13px;border-radius:9px;overflow:auto;font-size:12.5px}',
      '.sp-msg.bot code{background:rgba(15,23,42,.06);padding:1px 5px;border-radius:5px;font-size:.92em}',
      '.sp-msg.bot pre code{background:none;padding:0}',
      '.sp-msg.bot table{border-collapse:collapse;width:100%;margin:.5em 0;font-size:13px}',
      '.sp-msg.bot th,.sp-msg.bot td{border:1px solid var(--sp-border);padding:5px 9px;text-align:left}',
      '.sp-msg.bot th{background:var(--sp-bg2)}',
      // tool chips
      '.sp-steps{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:9px}.sp-steps:empty{display:none}',
      '.sp-chip{font-size:11.5px;padding:3px 10px;border-radius:999px;background:var(--sp-bg);',
      'border:1px solid var(--sp-border);color:var(--sp-faint);white-space:nowrap}',
      '.sp-chip.running{border-color:var(--sp-accent);color:var(--sp-accent)}',
      '.sp-chip.running::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;',
      'background:var(--sp-accent);margin-right:5px;animation:sp-pulse 1s infinite}',
      '@keyframes sp-pulse{0%,100%{opacity:.3}50%{opacity:1}}',
      '.sp-chip em{font-style:normal;opacity:.65}',
      '.sp-cites{margin-top:9px;font-size:11.5px;color:var(--sp-faint);border-top:1px dashed var(--sp-border);padding-top:7px}',
      '.sp-thinking{color:var(--sp-faint)}',
      '.sp-thinking::after{content:"…";animation:sp-dots 1.2s steps(4) infinite;display:inline-block;width:1em;text-align:left;overflow:hidden;vertical-align:bottom}',
      '@keyframes sp-dots{0%{width:0}100%{width:1em}}',
      // input
      '.sp-input{display:flex;gap:9px;padding:13px 16px;border-top:1px solid var(--sp-border);background:var(--sp-bg2)}',
      '.sp-input textarea{flex:1;resize:none;border:1px solid var(--sp-border);border-radius:10px;padding:9px 12px;',
      'font-family:inherit;font-size:14px;max-height:140px;color:var(--sp-text);background:var(--sp-bg);line-height:1.5}',
      '.sp-input textarea:focus{outline:none;border-color:var(--sp-accent);box-shadow:0 0 0 3px ' + accent + '22}',
      '.sp-send{border:none;border-radius:10px;background:var(--sp-accent);color:#fff;cursor:pointer;',
      'padding:0 18px;font-size:14px;font-weight:500}',
      '.sp-send:hover{filter:brightness(.95)}.sp-send:disabled{opacity:.5;cursor:default}',
      // drawer (conversation history) — slides over, WITH a back button
      '.sp-drawer{position:absolute;inset:0;background:var(--sp-bg);z-index:5;display:flex;flex-direction:column}',
      '.sp-drawer.sp-hidden{display:none}',
      '.sp-drawer-head{display:flex;align-items:center;gap:8px;padding:13px 16px;border-bottom:1px solid var(--sp-border);background:var(--sp-bg2)}',
      '.sp-drawer-title{font-weight:600;font-size:14px;flex:1}',
      '.sp-drawer-list{flex:1;overflow-y:auto}',
      '.sp-conv{display:flex;align-items:center;gap:8px;padding:12px 16px;border-bottom:1px solid var(--sp-border);cursor:pointer}',
      '.sp-conv:hover{background:var(--sp-bg2)}.sp-conv.active{background:' + accent + '14}',
      '.sp-conv-main{flex:1;min-width:0}',
      '.sp-conv-title{font-size:13.5px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.sp-conv-meta{font-size:11.5px;color:var(--sp-faint);margin-top:2px}',
      '.sp-conv-del{background:none;border:none;color:var(--sp-faint);cursor:pointer;font-size:15px;',
      'padding:4px 7px;border-radius:7px;opacity:0;transition:opacity .15s}',
      '.sp-conv:hover .sp-conv-del{opacity:1}.sp-conv-del:hover{background:var(--sp-border);color:var(--sp-text)}',
      '.sp-empty{padding:40px 16px;text-align:center;color:var(--sp-faint);font-size:13px}',
      // mobile
      '@media(max-width:560px){.sp-dock[data-size]{right:8px!important;left:8px!important;bottom:80px!important;',
      'top:auto!important;width:auto!important;height:70vh!important;border-radius:16px!important;margin:0!important}',
      '.sp-fab{right:16px;bottom:16px}}',
    ].join('');
    var style = document.createElement('style');
    style.id = 'sparrow-chat-style';
    style.textContent = css;
    document.head.appendChild(style);
  }

  var SIZES = ['normal', 'large', 'full'];

  function SparrowChat(opts) {
    this.cfg = Object.assign({}, DEFAULTS, opts || {});
    // merge i18n so callers can override just a few strings
    this.t = Object.assign({}, DEFAULTS.i18n, (opts && opts.i18n) || {});
    this.convId = localStorage.getItem(this.cfg.storageKey) || '';
    this.size = localStorage.getItem(this.cfg.storageKey + '_size') || 'normal';
    this.busy = false;
    this.opened = false;
    this._build();
  }

  SparrowChat.prototype._build = function () {
    injectStyle(this.cfg.accent);
    var c = this.cfg, t = this.t;
    this.root = h('<div class="sp-chat"></div>');
    this.fab = h('<button class="sp-fab" title="' + esc(c.title) + '">' + c.fabIcon + '</button>');
    this.dock = h(
      '<div class="sp-dock sp-hidden" data-size="' + this.size + '">' +
      '<div class="sp-head">' +
      '<span class="sp-title">' + esc(c.title) + '</span>' +
      '<div class="sp-head-actions">' +
      '<button class="sp-ico" data-act="convs" title="' + esc(t.history) + '">🕘</button>' +
      '<button class="sp-ico" data-act="new" title="' + esc(t.newChat) + '">＋</button>' +
      '<button class="sp-ico" data-act="resize" title="' + esc(t.resize) + '">⤢</button>' +
      '<button class="sp-ico" data-act="close" title="' + esc(t.close) + '">✕</button>' +
      '</div></div>' +
      (c.hint ? '<div class="sp-hint">' + esc(c.hint) + '</div>' : '') +
      '<div class="sp-msgs"></div>' +
      '<div class="sp-input"><textarea rows="1" placeholder="' + esc(t.placeholder) + '"></textarea>' +
      '<button class="sp-send">' + esc(t.send) + '</button></div>' +
      '<div class="sp-drawer sp-hidden">' +
      '<div class="sp-drawer-head"><button class="sp-ico" data-act="back" title="' + esc(t.back) + '">‹</button>' +
      '<span class="sp-drawer-title">' + esc(t.history) + '</span></div>' +
      '<div class="sp-drawer-list"></div></div>' +
      '</div>'
    );
    this.root.appendChild(this.fab);
    this.root.appendChild(this.dock);
    document.body.appendChild(this.root);

    this.msgs = this.dock.querySelector('.sp-msgs');
    this.input = this.dock.querySelector('textarea');
    this.sendBtn = this.dock.querySelector('.sp-send');
    this.drawer = this.dock.querySelector('.sp-drawer');
    this.drawerList = this.dock.querySelector('.sp-drawer-list');

    var self = this;
    this.fab.addEventListener('click', function () { self.toggle(); });
    this.dock.querySelector('[data-act="close"]').addEventListener('click', function () { self.toggle(false); });
    this.dock.querySelector('[data-act="new"]').addEventListener('click', function () { self.newConversation(); });
    this.dock.querySelector('[data-act="convs"]').addEventListener('click', function () { self.openDrawer(); });
    this.dock.querySelector('[data-act="back"]').addEventListener('click', function () { self.closeDrawer(); });
    this.dock.querySelector('[data-act="resize"]').addEventListener('click', function () { self.cycleSize(); });
    this.sendBtn.addEventListener('click', function () { self.send(); });
    this.input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); self.send(); }
    });
    this.input.addEventListener('input', function () {
      self.input.style.height = 'auto';
      self.input.style.height = Math.min(self.input.scrollHeight, 140) + 'px';
    });
  };

  SparrowChat.prototype.cycleSize = function () {
    var i = (SIZES.indexOf(this.size) + 1) % SIZES.length;
    this.size = SIZES[i];
    this.dock.setAttribute('data-size', this.size);
    localStorage.setItem(this.cfg.storageKey + '_size', this.size);
  };

  SparrowChat.prototype.toggle = function (force) {
    var open = force !== undefined ? force : this.dock.classList.contains('sp-hidden');
    this.dock.classList.toggle('sp-hidden', !open);
    if (open && !this.opened) { this.init(); this.opened = true; }
    if (open) this.input.focus();
  };

  SparrowChat.prototype.init = function () {
    if (this.convId) this.loadMessages(this.convId);
    else this.msgs.innerHTML = '<div class="sp-empty">' + esc(this.t.emptyNew) + '</div>';
  };

  SparrowChat.prototype.newConversation = function () {
    this.convId = 'c_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    localStorage.setItem(this.cfg.storageKey, this.convId);
    this.msgs.innerHTML = '<div class="sp-empty">' + esc(this.t.newStarted) + '</div>';
    this.closeDrawer();
  };

  SparrowChat.prototype.openDrawer = function () {
    this.loadConversations();
    this.drawer.classList.remove('sp-hidden');
  };
  SparrowChat.prototype.closeDrawer = function () {
    this.drawer.classList.add('sp-hidden');
  };

  SparrowChat.prototype.loadConversations = function () {
    var self = this, t = this.t;
    this.drawerList.innerHTML = '<div class="sp-empty">' + esc(t.loading) + '</div>';
    fetch(this.cfg.conversationsApi).then(function (r) { return r.json(); }).then(function (data) {
      var convs = Array.isArray(data) ? data : (data.conversations || []);
      if (!convs.length) { self.drawerList.innerHTML = '<div class="sp-empty">' + esc(t.noConversations) + '</div>'; return; }
      self.drawerList.innerHTML = '';
      convs.forEach(function (cv) {
        var row = h(
          '<div class="sp-conv' + (cv.id === self.convId ? ' active' : '') + '" data-id="' + esc(cv.id) + '">' +
          '<div class="sp-conv-main"><div class="sp-conv-title">' + esc(cv.title || t.untitled) + '</div>' +
          '<div class="sp-conv-meta">' + (cv.msg_count || 0) + ' ' + esc(t.messages) + ' · ' + relTime(cv.updated_at, t) + '</div></div>' +
          '<button class="sp-conv-del" title="' + esc(t.del) + '">🗑</button></div>'
        );
        row.querySelector('.sp-conv-main').addEventListener('click', function () {
          self.convId = cv.id;
          localStorage.setItem(self.cfg.storageKey, cv.id);
          self.closeDrawer();
          self.loadMessages(cv.id);
        });
        row.querySelector('.sp-conv-del').addEventListener('click', function (e) {
          e.stopPropagation();
          fetch(self.cfg.conversationsApi + '/' + encodeURIComponent(cv.id), { method: 'DELETE' })
            .then(function () { self.loadConversations(); });
        });
        self.drawerList.appendChild(row);
      });
    }).catch(function () { self.drawerList.innerHTML = '<div class="sp-empty">' + esc(t.loadFailed) + '</div>'; });
  };

  SparrowChat.prototype.loadMessages = function (convId) {
    var self = this;
    fetch(this.cfg.conversationsApi + '/' + encodeURIComponent(convId))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var list = data.messages || [];
        self.msgs.innerHTML = '';
        if (!list.length) { self.msgs.innerHTML = '<div class="sp-empty">' + esc(self.t.emptyConversation) + '</div>'; return; }
        list.forEach(function (m) {
          if (m.role === 'user') self.addUser(m.content);
          else self.addBotFull(m);
        });
        self.scrollDown();
      }).catch(function () { /* ignore */ });
  };

  SparrowChat.prototype.addUser = function (text) {
    this.msgs.appendChild(h('<div class="sp-msg user">' + esc(text) + '</div>'));
  };

  SparrowChat.prototype.addBotFull = function (m) {
    var steps = (m.tool_steps || []).map(function (s) {
      return '<span class="sp-chip">' + esc(s.label) + ': ' + esc(s.summary) + '</span>';
    }).join('');
    var cites = (m.citations || []).length
      ? '<div class="sp-cites">' + esc(this.t.sources) + ': ' + m.citations.map(esc).join(' · ') + '</div>' : '';
    this.msgs.appendChild(h('<div class="sp-msg bot">' +
      (steps ? '<div class="sp-steps">' + steps + '</div>' : '') + md(m.content) + cites + '</div>'));
  };

  SparrowChat.prototype.scrollDown = function () { this.msgs.scrollTop = this.msgs.scrollHeight; };

  SparrowChat.prototype.send = function () {
    if (this.busy) return;
    var text = this.input.value.trim();
    if (!text) return;
    this.input.value = '';
    this.input.style.height = 'auto';
    if (!this.convId) this.newConversation();
    var empty = this.msgs.querySelector('.sp-empty');
    if (empty) this.msgs.innerHTML = '';

    this.addUser(text);
    var bot = h('<div class="sp-msg bot"><div class="sp-steps"></div>' +
      '<div class="sp-body"><span class="sp-thinking">' + esc(self.t.thinking) + '</span></div></div>');
    this.msgs.appendChild(bot);
    var ui = { steps: bot.querySelector('.sp-steps'), body: bot.querySelector('.sp-body') };
    this.scrollDown();

    this.busy = true;
    this.sendBtn.disabled = true;
    var self = this;
    fetch(this.cfg.endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ message: text, conversation_id: this.convId }),
    }).then(function (resp) {
      if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status);
      return self._consume(resp.body, ui);
    }).catch(function (e) {
      ui.body.innerHTML = '❌ ' + esc(e.message);
    }).then(function () {
      self.busy = false;
      self.sendBtn.disabled = false;
    });
  };

  SparrowChat.prototype._consume = function (body, ui) {
    var self = this;
    var reader = body.getReader();
    var decoder = new TextDecoder();
    var buf = '';
    function pump() {
      return reader.read().then(function (res) {
        if (res.done) return;
        buf += decoder.decode(res.value, { stream: true });
        var parts = buf.split('\n\n');
        buf = parts.pop();
        parts.forEach(function (part) {
          var line = part.split('\n').filter(function (l) { return l.indexOf('data:') === 0; })[0];
          if (!line) return;
          var ev;
          try { ev = JSON.parse(line.slice(5).trim()); } catch (e) { return; }
          self._event(ev, ui);
        });
        self.scrollDown();
        return pump();
      });
    }
    return pump();
  };

  SparrowChat.prototype._event = function (ev, ui) {
    if (ev.type === 'tool_call') {
      var args = Object.keys(ev.arguments || {}).map(function (k) { return k + '=' + ev.arguments[k]; }).join(' ');
      ui.steps.appendChild(h('<span class="sp-chip running" data-tool="' + esc(ev.name) + '">' +
        esc(ev.label || ev.name) + (args ? ' <em>' + esc(args) + '</em>' : '') + '</span>'));
    } else if (ev.type === 'tool_result') {
      var chips = ui.steps.querySelectorAll('.sp-chip.running[data-tool="' + ev.name + '"]');
      var chip = chips[chips.length - 1];
      if (chip) {
        chip.classList.remove('running');
        chip.innerHTML = '✅ ' + esc(ev.label || ev.name) + ': ' + esc(ev.summary || '');
      }
    } else if (ev.type === 'final') {
      var cites = (ev.citations || []).length
        ? '<div class="sp-cites">' + esc(this.t.sources) + ': ' + ev.citations.map(esc).join(' · ') + '</div>' : '';
      ui.body.innerHTML = md(ev.content) + cites;
    } else if (ev.type === 'error') {
      ui.body.innerHTML = '❌ ' + esc(ev.message || 'error');
    }
  };

  // Public API
  global.SparrowChat = {
    mount: function (opts) { return new SparrowChat(opts); },
  };
})(typeof window !== 'undefined' ? window : this);
