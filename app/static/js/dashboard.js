/* Admin analytics charts (Chart.js). Data is embedded by the template as JSON. */
(function () {
  "use strict";
  var node = document.getElementById("metrics-data");
  if (!node || typeof Chart === "undefined") return;
  var m = JSON.parse(node.textContent);
  var palette = ["#0d6efd", "#6610f2", "#198754", "#dc3545", "#fd7e14", "#20c997", "#6f42c1", "#0dcaf0", "#ffc107", "#adb5bd"];
  var muted = getComputedStyle(document.body).getPropertyValue("--bs-secondary-color") || "#6c757d";
  Chart.defaults.color = muted.trim();
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";

  function chart(id, config) {
    var el = document.getElementById(id);
    if (el) new Chart(el, config);
  }

  chart("chart-items", {
    type: "line",
    data: { labels: m.items_per_day.map(function (d) { return d.date.slice(5); }), datasets: [{ label: "Items", data: m.items_per_day.map(function (d) { return d.count; }), borderColor: palette[0], backgroundColor: "rgba(13,110,253,.12)", fill: true, tension: 0.3, pointRadius: 2 }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
  });
  chart("chart-categories", {
    type: "doughnut",
    data: { labels: m.categories.map(function (c) { return c.name; }), datasets: [{ data: m.categories.map(function (c) { return c.count; }), backgroundColor: m.categories.map(function (c, i) { return c.color || palette[i % palette.length]; }) }] },
    options: { plugins: { legend: { position: "bottom" } } }
  });
  chart("chart-status", {
    type: "pie",
    data: { labels: Object.keys(m.status), datasets: [{ data: Object.values(m.status), backgroundColor: [palette[8], palette[2], palette[9]] }] },
    options: { plugins: { legend: { position: "bottom" } } }
  });
  chart("chart-difficulty", {
    type: "bar",
    data: { labels: Object.keys(m.difficulty), datasets: [{ label: "Items", data: Object.values(m.difficulty), backgroundColor: palette[1] }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
  });
  chart("chart-tags", {
    type: "bar",
    data: { labels: m.tags.map(function (t) { return "#" + t.name; }), datasets: [{ label: "Items", data: m.tags.map(function (t) { return t.count; }), backgroundColor: palette[5] }] },
    options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } }
  });
})();
