// File: FlaskVerseHub/app/static/js/dashboard.js

// Dashboard-specific JavaScript functionality
(function () {
  "use strict";

  let charts = {};
  let dashboardData = {};
  let refreshInterval = null;

  // Initialize dashboard when DOM is ready
  document.addEventListener("DOMContentLoaded", function () {
    initializeDashboard();
  });

  /**
   * Main dashboard initialization
   */
  function initializeDashboard() {
    initializeSidebar();
    initializeCharts();
    initializeRealTimeUpdates();
    initializeDashboardCards();
    initializeDataTables();
    initializeFilters();

    console.log("Dashboard initialized successfully");
  }

  /**
   * Sidebar functionality
   */
  function initializeSidebar() {
    const sidebarToggle = document.querySelector('[data-bs-toggle="sidebar"]');
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.querySelector(".sidebar-overlay");

    // Mobile sidebar toggle
    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", function () {
        sidebar.classList.toggle("show");
        overlay.classList.toggle("show");
      });
    }

    // Close sidebar when overlay is clicked
    if (overlay) {
      overlay.addEventListener("click", function () {
        sidebar.classList.remove("show");
        overlay.classList.remove("show");
      });
    }

    // Collapse/expand sidebar sections
    const sectionToggles = document.querySelectorAll(".nav-section-toggle");
    sectionToggles.forEach((toggle) => {
      toggle.addEventListener("click", function () {
        const section = this.closest(".nav-section");
        const menu = section.querySelector(".nav-menu");

        section.classList.toggle("collapsed");
        if (menu) {
          menu.style.display = section.classList.contains("collapsed")
            ? "none"
            : "block";
        }
      });
    });
  }

  /**
   * Initialize dashboard charts
   */
  function initializeCharts() {
    // Analytics chart
    const analyticsChart = document.getElementById("analyticsChart");
    if (analyticsChart && typeof Chart !== "undefined") {
      charts.analytics = createAnalyticsChart(analyticsChart);
    }

    // Usage chart
    const usageChart = document.getElementById("usageChart");
    if (usageChart && typeof Chart !== "undefined") {
      charts.usage = createUsageChart(usageChart);
    }

    // Activity chart
    const activityChart = document.getElementById("activityChart");
    if (activityChart && typeof Chart !== "undefined") {
      charts.activity = createActivityChart(activityChart);
    }
  }

  /**
   * Create analytics chart
   */
  function createAnalyticsChart(canvas) {
    const ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        datasets: [
          {
            label: "Knowledge Items",
            data: [12, 19, 23, 25, 32, 45],
            borderColor: "#007bff",
            backgroundColor: "rgba(0, 123, 255, 0.1)",
            tension: 0.4,
          },
          {
            label: "API Calls",
            data: [8, 15, 18, 22, 28, 38],
            borderColor: "#28a745",
            backgroundColor: "rgba(40, 167, 69, 0.1)",
            tension: 0.4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
          },
        },
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    });
  }

  /**
   * Create usage chart
   */
  function createUsageChart(canvas) {
    const ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Knowledge Vault", "API Calls", "Dashboard Views", "Other"],
        datasets: [
          {
            data: [35, 25, 20, 20],
            backgroundColor: ["#007bff", "#28a745", "#ffc107", "#6c757d"],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
          },
        },
      },
    });
  }

  /**
   * Create activity chart
   */
  function createActivityChart(canvas) {
    const ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        datasets: [
          {
            label: "Activities",
            data: [12, 15, 18, 22, 25, 8, 5],
            backgroundColor: "#007bff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    });
  }

  /**
   * Initialize real-time updates
   */
  function initializeRealTimeUpdates() {
    // Start periodic data refresh
    startDataRefresh();

    // Add refresh button functionality
    const refreshButton = document.getElementById("refreshDashboard");
    if (refreshButton) {
      refreshButton.addEventListener("click", function () {
        refreshDashboardData();
        this.classList.add("rotating");
        setTimeout(() => this.classList.remove("rotating"), 1000);
      });
    }

    // Auto-refresh toggle
    const autoRefreshToggle = document.getElementById("autoRefresh");
    if (autoRefreshToggle) {
      autoRefreshToggle.addEventListener("change", function () {
        if (this.checked) {
          startDataRefresh();
        } else {
          stopDataRefresh();
        }
      });
    }
  }

  /**
   * Start data refresh interval
   */
  function startDataRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }

    refreshInterval = setInterval(() => {
      refreshDashboardData();
    }, 30000); // Refresh every 30 seconds
  }

  /**
   * Stop data refresh interval
   */
  function stopDataRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  }

  /**
   * Refresh dashboard data
   */
  function refreshDashboardData() {
    const API = window.FlaskVerseHubAPI;

    Promise.all([
      API.get("/api/dashboard/stats"),
      API.get("/api/dashboard/activity"),
      API.get("/api/dashboard/notifications"),
    ])
      .then(([stats, activity, notifications]) => {
        updateDashboardCards(stats);
        updateActivityFeed(activity);
        updateNotifications(notifications);
      })
      .catch((error) => {
        console.error("Failed to refresh dashboard data:", error);
        showNotification("Failed to refresh dashboard data", "error");
      });
  }

  /**
   * Initialize dashboard cards
   */
  function initializeDashboardCards() {
    const cards = document.querySelectorAll(".dashboard-card");

    cards.forEach((card) => {
      // Add hover effects
      card.addEventListener("mouseenter", function () {
        this.style.transform = "translateY(-2px)";
      });

      card.addEventListener("mouseleave", function () {
        this.style.transform = "translateY(0)";
      });

      // Click handlers for navigation
      const link = card.getAttribute("data-link");
      if (link) {
        card.style.cursor = "pointer";
        card.addEventListener("click", function () {
          window.location.href = link;
        });
      }
    });
  }

  /**
   * Update dashboard cards with new data
   */
  function updateDashboardCards(data) {
    if (!data) return;

    Object.keys(data).forEach((key) => {
      const card = document.querySelector(`[data-stat="${key}"]`);
      if (card) {
        const valueEl = card.querySelector(".card-value");
        const changeEl = card.querySelector(".card-change");

        if (valueEl) {
          animateValue(
            valueEl,
            parseInt(valueEl.textContent) || 0,
            data[key].value
          );
        }

        if (changeEl && data[key].change !== undefined) {
          const change = data[key].change;
          changeEl.textContent = `${change > 0 ? "+" : ""}${change}%`;
          changeEl.className = `card-change ${
            change >= 0 ? "positive" : "negative"
          }`;
        }

        // Add update animation
        card.classList.add("live-update");
        setTimeout(() => card.classList.remove("live-update"), 2000);
      }
    });
  }

  /**
   * Animate value changes
   */
  function animateValue(element, start, end, duration = 1000) {
    const startTimestamp = performance.now();

    function step(timestamp) {
      const elapsed = timestamp - startTimestamp;
      const progress = Math.min(elapsed / duration, 1);

      const current = Math.floor(start + (end - start) * progress);
      element.textContent = current.toLocaleString();

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    }

    requestAnimationFrame(step);
  }

  /**
   * Initialize data tables
   */
  function initializeDataTables() {
    const tables = document.querySelectorAll(".data-table");

    tables.forEach((table) => {
      // Add sorting functionality
      const headers = table.querySelectorAll("th[data-sort]");
      headers.forEach((header) => {
        header.style.cursor = "pointer";
        header.addEventListener("click", function () {
          sortTable(table, this.getAttribute("data-sort"));
        });
      });

      // Add row selection
      const checkboxes = table.querySelectorAll('input[type="checkbox"]');
      const selectAllCheckbox = table.querySelector(
        'thead input[type="checkbox"]'
      );

      if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener("change", function () {
          checkboxes.forEach((cb) => {
            if (cb !== this) cb.checked = this.checked;
          });
          updateBulkActions();
        });
      }

      checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", updateBulkActions);
      });
    });
  }

  /**
   * Sort table by column
   */
  function sortTable(table, column) {
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const header = table.querySelector(`th[data-sort="${column}"]`);

    const isAscending = !header.classList.contains("sort-asc");

    // Remove existing sort classes
    table.querySelectorAll("th").forEach((th) => {
      th.classList.remove("sort-asc", "sort-desc");
    });

    // Add new sort class
    header.classList.add(isAscending ? "sort-asc" : "sort-desc");

    rows.sort((a, b) => {
      const aVal =
        a.querySelector(`td[data-sort="${column}"]`)?.textContent.trim() || "";
      const bVal =
        b.querySelector(`td[data-sort="${column}"]`)?.textContent.trim() || "";

      const comparison = aVal.localeCompare(bVal, undefined, { numeric: true });
      return isAscending ? comparison : -comparison;
    });

    // Reappend sorted rows
    rows.forEach((row) => tbody.appendChild(row));
  }

  /**
   * Update bulk actions based on selection
   */
  function updateBulkActions() {
    const selectedCheckboxes = document.querySelectorAll(
      '.data-table tbody input[type="checkbox"]:checked'
    );
    const bulkActions = document.querySelector(".bulk-actions");

    if (bulkActions) {
      const count = selectedCheckboxes.length;
      if (count > 0) {
        bulkActions.style.display = "block";
        const countEl = bulkActions.querySelector(".selection-count");
        if (countEl) {
          countEl.textContent = `${count} item${count > 1 ? "s" : ""} selected`;
        }
      } else {
        bulkActions.style.display = "none";
      }
    }
  }

  /**
   * Initialize filters
   */
  function initializeFilters() {
    const filterForm = document.getElementById("dashboardFilters");
    if (!filterForm) return;

    const filterInputs = filterForm.querySelectorAll("input, select");

    filterInputs.forEach((input) => {
      input.addEventListener(
        "change",
        FlaskVerseHubUtils.debounce(applyFilters, 300)
      );
    });

    // Clear filters button
    const clearButton = filterForm.querySelector(".clear-filters");
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        filterInputs.forEach((input) => {
          if (input.type === "checkbox" || input.type === "radio") {
            input.checked = false;
          } else {
            input.value = "";
          }
        });
        applyFilters();
      });
    }
  }

  /**
   * Apply dashboard filters
   */
  function applyFilters() {
    const filterForm = document.getElementById("dashboardFilters");
    if (!filterForm) return;

    const formData = new FormData(filterForm);
    const params = new URLSearchParams(formData);

    showLoading("Applying filters...");

    window.FlaskVerseHubAPI.get(
      "/api/dashboard/filtered-data",
      Object.fromEntries(params)
    )
      .then((data) => {
        updateDashboardContent(data);
        hideLoading();
      })
      .catch((error) => {
        console.error("Filter application failed:", error);
        showNotification("Failed to apply filters", "error");
        hideLoading();
      });
  }

  /**
   * Update dashboard content with filtered data
   */
  function updateDashboardContent(data) {
    // Update charts
    if (data.chartData && charts.analytics) {
      charts.analytics.data = data.chartData.analytics;
      charts.analytics.update();
    }

    // Update tables
    if (data.tableData) {
      updateDataTables(data.tableData);
    }

    // Update cards
    if (data.stats) {
      updateDashboardCards(data.stats);
    }
  }

  /**
   * Update data tables with new data
   */
  function updateDataTables(data) {
    Object.keys(data).forEach((tableId) => {
      const table = document.getElementById(tableId);
      if (table) {
        const tbody = table.querySelector("tbody");
        if (tbody) {
          tbody.innerHTML = data[tableId];
        }
      }
    });
  }

  /**
   * Update activity feed
   */
  function updateActivityFeed(activities) {
    const feed = document.getElementById("activityFeed");
    if (!feed || !activities) return;

    const items = activities
      .map(
        (activity) => `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">
                    <i class="fas ${getActivityIcon(activity.type)}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${activity.title}</div>
                    <div class="activity-description">${
                      activity.description
                    }</div>
                    <div class="activity-time">${FlaskVerseHubUtils.formatTime(
                      activity.timestamp
                    )}</div>
                </div>
            </div>
        `
      )
      .join("");

    feed.innerHTML = items;
  }

  /**
   * Get activity icon based on type
   */
  function getActivityIcon(type) {
    const icons = {
      create: "fa-plus",
      edit: "fa-edit",
      delete: "fa-trash",
      login: "fa-sign-in-alt",
      logout: "fa-sign-out-alt",
      api: "fa-plug",
      default: "fa-info",
    };
    return icons[type] || icons.default;
  }

  /**
   * Update notifications
   */
  function updateNotifications(notifications) {
    const badge = document.querySelector(".notification-badge");
    const dropdown = document.querySelector(".notifications-dropdown");

    if (badge && notifications) {
      badge.textContent = notifications.unread_count;
      badge.style.display = notifications.unread_count > 0 ? "inline" : "none";
    }

    if (dropdown && notifications && notifications.items) {
      const items = notifications.items
        .map(
          (notification) => `
                <li><a class="dropdown-item notification-item ${
                  notification.read ? "" : "unread"
                }" href="${notification.url || "#"}">
                    <div class="notification-content">
                        <strong>${notification.title}</strong>
                        <small class="text-muted d-block">${FlaskVerseHubUtils.formatTime(
                          notification.created_at
                        )}</small>
                        <span class="notification-text">${
                          notification.message
                        }</span>
                    </div>
                </a></li>
            `
        )
        .join("");

      dropdown.innerHTML = `
                <li class="dropdown-header">
                    <i class="fas fa-bell"></i>
                    Notifications
                </li>
                <li><hr class="dropdown-divider"></li>
                ${items}
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item text-center" href="/dashboard/notifications">
                    View all notifications
                </a></li>
            `;
    }
  }

  /**
   * Export dashboard data
   */
  window.exportDashboardData = function (format = "csv") {
    showLoading("Preparing export...");

    window.FlaskVerseHubAPI.get(`/api/dashboard/export?format=${format}`)
      .then((response) => {
        const blob = new Blob([response], { type: "text/csv" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `dashboard-data-${
          new Date().toISOString().split("T")[0]
        }.${format}`;
        a.click();
        window.URL.revokeObjectURL(url);
        hideLoading();
        showNotification("Dashboard data exported successfully", "success");
      })
      .catch((error) => {
        console.error("Export failed:", error);
        showNotification("Export failed", "error");
        hideLoading();
      });
  };

  // Cleanup on page unload
  window.addEventListener("beforeunload", function () {
    stopDataRefresh();
  });
})();
