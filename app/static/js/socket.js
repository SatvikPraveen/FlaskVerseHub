/* Real-time client: presence, notifications and the live item feed. */
(function () {
  "use strict";
  if (typeof io === "undefined") return;
  var socket = io({ transports: ["websocket", "polling"] });
  var status = document.getElementById("live-status");
  var dot = document.getElementById("live-dot");
  var feed = document.getElementById("live-feed");
  var unread = document.getElementById("unread-count");
  var badge = document.getElementById("nav-unread");

  function setStatus(text, online) {
    if (status) status.textContent = text;
    if (dot) dot.className = "status-dot " + (online ? "status-online" : "status-offline") + " me-1";
  }
  function addFeed(icon, html) {
    if (!feed) return;
    var empty = document.getElementById("live-feed-empty");
    if (empty) empty.remove();
    var li = document.createElement("li");
    li.className = "list-group-item small";
    li.innerHTML = '<i class="fa-solid ' + icon + ' me-2 text-primary"></i>' + html + ' <span class="text-muted">· just now</span>';
    feed.prepend(li);
    while (feed.children.length > 12) feed.removeChild(feed.lastChild);
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function bump(delta) {
    [unread, badge].forEach(function (el) {
      if (!el) return;
      var n = Math.max(0, (parseInt(el.textContent, 10) || 0) + delta);
      el.textContent = n;
      if (badge === el) el.classList.toggle("d-none", n === 0);
    });
  }

  socket.on("connect", function () { setStatus("Live updates connected", true); });
  socket.on("disconnect", function () { setStatus("Live updates disconnected — reconnecting…", false); });
  socket.on("presence", function (p) { setStatus("Live · " + p.connected + " online", true); });
  socket.on("item:created", function (e) { addFeed("fa-plus", escapeHtml(e.author) + ' published <a href="/knowledge/' + encodeURIComponent(e.slug) + '">' + escapeHtml(e.title) + "</a>"); });
  socket.on("item:updated", function (e) { addFeed("fa-pen", escapeHtml(e.actor || e.author) + ' updated <a href="/knowledge/' + encodeURIComponent(e.slug) + '">' + escapeHtml(e.title) + "</a> (v" + e.version + ")"); });
  socket.on("item:deleted", function (e) { addFeed("fa-trash", escapeHtml(e.title) + " was deleted"); });
  socket.on("notification", function (n) {
    bump(1);
    addFeed("fa-bell", escapeHtml(n.title));
    var list = document.getElementById("notification-list");
    if (list) {
      var li = document.createElement("li");
      li.className = "list-group-item fw-semibold small";
      li.innerHTML = '<a class="text-decoration-none" href="' + (n.link || "/dashboard/notifications") + '">' + escapeHtml(n.title) + '</a><div class="text-muted">just now</div>';
      list.prepend(li);
    }
  });

  window.FVH = window.FVH || {};
  window.FVH.socket = socket;
  window.FVH.markRead = function (id, href) {
    window.FVH.fetchJSON("/dashboard/notifications/" + id + "/read", { method: "POST" })
      .then(function () { bump(-1); window.location.href = href; })
      .catch(function () { window.location.href = href; });
  };
  var slugNode = document.querySelector("[data-item-slug]");
  if (slugNode) socket.emit("subscribe", { item: slugNode.getAttribute("data-item-slug") });
})();
