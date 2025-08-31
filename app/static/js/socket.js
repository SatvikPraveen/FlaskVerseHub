// File: FlaskVerseHub/app/static/js/sockets.js

// WebSocket client handling for real-time features
(function () {
  "use strict";

  let socket = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 2000;
  let isConnected = false;
  let messageQueue = [];

  // Initialize WebSocket connection when DOM is ready
  document.addEventListener("DOMContentLoaded", function () {
    if (typeof io !== "undefined") {
      initializeSocket();
    } else {
      console.warn("Socket.IO client library not loaded");
    }
  });

  /**
   * Initialize Socket.IO connection
   */
  function initializeSocket() {
    const socketOptions = {
      transports: ["websocket", "polling"],
      timeout: 20000,
      forceNew: true,
      reconnection: true,
      reconnectionAttempts: maxReconnectAttempts,
      reconnectionDelay: reconnectDelay,
    };

    socket = io(socketOptions);
    setupSocketEventHandlers();

    console.log("Socket.IO initialization attempted");
  }

  /**
   * Setup socket event handlers
   */
  function setupSocketEventHandlers() {
    // Connection events
    socket.on("connect", handleConnect);
    socket.on("disconnect", handleDisconnect);
    socket.on("connect_error", handleConnectError);
    socket.on("reconnect", handleReconnect);
    socket.on("reconnect_error", handleReconnectError);

    // Application events
    socket.on("notification", handleNotification);
    socket.on("dashboard_update", handleDashboardUpdate);
    socket.on("knowledge_update", handleKnowledgeUpdate);
    socket.on("user_activity", handleUserActivity);
    socket.on("system_alert", handleSystemAlert);
    socket.on("api_usage_update", handleApiUsageUpdate);

    // Chat/messaging events (if implemented)
    socket.on("message", handleMessage);
    socket.on("user_typing", handleUserTyping);
    socket.on("user_joined", handleUserJoined);
    socket.on("user_left", handleUserLeft);
  }

  /**
   * Handle successful connection
   */
  function handleConnect() {
    console.log("Socket.IO connected");
    isConnected = true;
    reconnectAttempts = 0;
    updateConnectionStatus(true);

    // Authenticate user if logged in
    if (window.FlaskVerseHub && window.FlaskVerseHub.user) {
      socket.emit("authenticate", {
        user_id: window.FlaskVerseHub.user.id,
        token: window.csrfToken,
      });
    }

    // Send queued messages
    flushMessageQueue();

    // Join user-specific room
    if (window.FlaskVerseHub && window.FlaskVerseHub.user) {
      socket.emit("join", {
        room: `user_${window.FlaskVerseHub.user.id}`,
      });
    }

    showNotification("Connected to real-time updates", "success", 3000);
  }

  /**
   * Handle disconnection
   */
  function handleDisconnect(reason) {
    console.log("Socket.IO disconnected:", reason);
    isConnected = false;
    updateConnectionStatus(false);

    if (reason === "io server disconnect") {
      // Server-initiated disconnect, reconnect manually
      socket.connect();
    }

    showNotification("Disconnected from real-time updates", "warning", 3000);
  }

  /**
   * Handle connection error
   */
  function handleConnectError(error) {
    console.error("Socket.IO connection error:", error);
    isConnected = false;
    reconnectAttempts++;
    updateConnectionStatus(false);

    if (reconnectAttempts >= maxReconnectAttempts) {
      showNotification(
        "Failed to establish real-time connection",
        "error",
        5000
      );
    }
  }

  /**
   * Handle successful reconnection
   */
  function handleReconnect(attemptNumber) {
    console.log("Socket.IO reconnected after", attemptNumber, "attempts");
    showNotification("Reconnected to real-time updates", "success", 3000);
  }

  /**
   * Handle reconnection error
   */
  function handleReconnectError(error) {
    console.error("Socket.IO reconnection error:", error);
  }

  /**
   * Handle notifications
   */
  function handleNotification(data) {
    console.log("Received notification:", data);

    // Show toast notification
    if (typeof showToast === "function") {
      showToast(data.message, data.type || "info", data.duration || 5000);
    }

    // Update notification badge
    updateNotificationBadge(data);

    // Play notification sound if enabled
    if (data.sound && isNotificationSoundEnabled()) {
      playNotificationSound();
    }

    // Show browser notification if permission granted
    if (data.browser_notification && isBrowserNotificationEnabled()) {
      showBrowserNotification(data);
    }
  }

  /**
   * Handle dashboard updates
   */
  function handleDashboardUpdate(data) {
    console.log("Dashboard update received:", data);

    // Update dashboard cards
    if (data.stats && typeof updateDashboardCards === "function") {
      updateDashboardCards(data.stats);
    }

    // Update charts
    if (data.chart_data && window.charts) {
      updateChartData(data.chart_data);
    }

    // Update activity feed
    if (data.activity && typeof updateActivityFeed === "function") {
      updateActivityFeed(data.activity);
    }
  }

  /**
   * Handle knowledge vault updates
   */
  function handleKnowledgeUpdate(data) {
    console.log("Knowledge update received:", data);

    // Update knowledge list if on the vault page
    if (window.location.pathname.includes("/knowledge")) {
      refreshKnowledgeList();
    }

    // Show update notification
    const message = `Knowledge item "${data.title}" was ${data.action}`;
    showNotification(message, "info", 4000);
  }

  /**
   * Handle user activity updates
   */
  function handleUserActivity(data) {
    console.log("User activity update:", data);

    // Update active users list
    updateActiveUsersList(data);

    // Update user presence indicators
    updateUserPresence(data);
  }

  /**
   * Handle system alerts
   */
  function handleSystemAlert(data) {
    console.log("System alert received:", data);

    // Show prominent alert
    showSystemAlert(data);

    // Log to console for debugging
    if (data.level === "critical") {
      console.error("CRITICAL SYSTEM ALERT:", data.message);
    }
  }

  /**
   * Handle API usage updates
   */
  function handleApiUsageUpdate(data) {
    console.log("API usage update:", data);

    // Update API dashboard if visible
    if (document.getElementById("apiUsageChart")) {
      updateApiUsageChart(data);
    }

    // Show rate limit warnings
    if (data.warning) {
      showNotification(data.warning, "warning", 8000);
    }
  }

  /**
   * Handle chat messages
   */
  function handleMessage(data) {
    console.log("Message received:", data);

    // Add message to chat interface
    if (typeof addMessageToChat === "function") {
      addMessageToChat(data);
    }

    // Show notification if not in chat view
    if (!window.location.pathname.includes("/chat")) {
      showNotification(`New message from ${data.username}`, "info", 5000);
    }
  }

  /**
   * Handle user typing indicators
   */
  function handleUserTyping(data) {
    if (typeof showTypingIndicator === "function") {
      showTypingIndicator(data);
    }
  }

  /**
   * Handle user joined events
   */
  function handleUserJoined(data) {
    console.log("User joined:", data);
    updateActiveUsersList(data);
    showNotification(`${data.username} joined`, "info", 3000);
  }

  /**
   * Handle user left events
   */
  function handleUserLeft(data) {
    console.log("User left:", data);
    updateActiveUsersList(data);
  }

  /**
   * Update connection status indicator
   */
  function updateConnectionStatus(connected) {
    const indicators = document.querySelectorAll(
      ".connection-status, .online-status, .live-indicator"
    );

    indicators.forEach((indicator) => {
      if (connected) {
        indicator.classList.remove("offline", "disconnected");
        indicator.classList.add("online", "connected");
        indicator.style.color = "#28a745";
      } else {
        indicator.classList.remove("online", "connected");
        indicator.classList.add("offline", "disconnected");
        indicator.style.color = "#dc3545";
      }
    });

    // Update status text
    const statusTexts = document.querySelectorAll(".status-text");
    statusTexts.forEach((text) => {
      text.textContent = connected ? "Connected" : "Disconnected";
    });
  }

  /**
   * Update notification badge
   */
  function updateNotificationBadge(data) {
    const badges = document.querySelectorAll(
      ".notification-badge, .notification-count"
    );

    badges.forEach((badge) => {
      if (data.unread_count !== undefined) {
        badge.textContent = data.unread_count;
        badge.style.display = data.unread_count > 0 ? "inline" : "none";
      } else {
        const currentCount = parseInt(badge.textContent) || 0;
        badge.textContent = currentCount + 1;
        badge.style.display = "inline";
      }
    });
  }

  /**
   * Update charts with new data
   */
  function updateChartData(chartData) {
    if (window.charts) {
      Object.keys(chartData).forEach((chartId) => {
        const chart = window.charts[chartId];
        if (chart) {
          chart.data = chartData[chartId];
          chart.update("none"); // No animation for real-time updates
        }
      });
    }
  }

  /**
   * Show system alert
   */
  function showSystemAlert(data) {
    const alert = document.createElement("div");
    alert.className = `alert alert-${
      data.level || "warning"
    } alert-dismissible system-alert`;
    alert.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div class="flex-grow-1">
                    <strong>System Alert:</strong> ${data.message}
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

    const container =
      document.querySelector(".flash-messages-container") || document.body;
    container.appendChild(alert);

    // Auto-remove after delay
    setTimeout(() => {
      if (alert.parentNode) {
        alert.parentNode.removeChild(alert);
      }
    }, data.duration || 10000);
  }

  /**
   * Update active users list
   */
  function updateActiveUsersList(data) {
    const usersList = document.getElementById("activeUsers");
    if (usersList && data.active_users) {
      usersList.innerHTML = data.active_users
        .map(
          (user) => `
                <div class="user-item">
                    <div class="user-avatar">
                        <i class="fas fa-user-circle"></i>
                    </div>
                    <div class="user-info">
                        <div class="user-name">${user.name}</div>
                        <div class="user-status online">Online</div>
                    </div>
                </div>
            `
        )
        .join("");
    }
  }

  /**
   * Update user presence indicators
   */
  function updateUserPresence(data) {
    if (data.user_id && data.status) {
      const indicators = document.querySelectorAll(
        `[data-user-id="${data.user_id}"] .presence-indicator`
      );
      indicators.forEach((indicator) => {
        indicator.className = `presence-indicator ${data.status}`;
      });
    }
  }

  /**
   * Play notification sound
   */
  function playNotificationSound() {
    try {
      const audio = new Audio("/static/sounds/notification.mp3");
      audio.volume = 0.3;
      audio
        .play()
        .catch((e) => console.log("Could not play notification sound:", e));
    } catch (error) {
      console.log("Notification sound not available");
    }
  }

  /**
   * Show browser notification
   */
  function showBrowserNotification(data) {
    if ("Notification" in window && Notification.permission === "granted") {
      const notification = new Notification(data.title || "FlaskVerseHub", {
        body: data.message,
        icon: "/static/images/logo.svg",
        tag: data.id || "general",
      });

      notification.onclick = function () {
        window.focus();
        if (data.url) {
          window.location.href = data.url;
        }
        notification.close();
      };

      // Auto-close after 5 seconds
      setTimeout(() => notification.close(), 5000);
    }
  }

  /**
   * Check if notification sound is enabled
   */
  function isNotificationSoundEnabled() {
    return localStorage.getItem("notification_sound") !== "false";
  }

  /**
   * Check if browser notifications are enabled
   */
  function isBrowserNotificationEnabled() {
    return (
      "Notification" in window &&
      Notification.permission === "granted" &&
      localStorage.getItem("browser_notifications") !== "false"
    );
  }

  /**
   * Flush queued messages
   */
  function flushMessageQueue() {
    while (messageQueue.length > 0) {
      const message = messageQueue.shift();
      socket.emit(message.event, message.data);
    }
  }

  /**
   * Public API for sending messages
   */
  window.socketEmit = function (event, data) {
    if (socket && isConnected) {
      socket.emit(event, data);
    } else {
      // Queue message for when connection is restored
      messageQueue.push({ event, data });
    }
  };

  /**
   * Join a specific room
   */
  window.joinRoom = function (roomName) {
    socketEmit("join", { room: roomName });
  };

  /**
   * Leave a specific room
   */
  window.leaveRoom = function (roomName) {
    socketEmit("leave", { room: roomName });
  };

  /**
   * Send a chat message
   */
  window.sendMessage = function (message, room) {
    socketEmit("message", {
      message: message,
      room: room,
      timestamp: new Date().toISOString(),
    });
  };

  /**
   * Request browser notification permission
   */
  window.requestNotificationPermission = function () {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then((permission) => {
        if (permission === "granted") {
          showNotification("Browser notifications enabled", "success");
        }
      });
    }
  };

  /**
   * Toggle notification sound
   */
  window.toggleNotificationSound = function () {
    const enabled = isNotificationSoundEnabled();
    localStorage.setItem("notification_sound", !enabled);
    showNotification(
      `Notification sound ${!enabled ? "enabled" : "disabled"}`,
      "info"
    );
  };

  /**
   * Get connection status
   */
  window.getSocketStatus = function () {
    return {
      connected: isConnected,
      reconnectAttempts: reconnectAttempts,
      queuedMessages: messageQueue.length,
    };
  };

  // Cleanup on page unload
  window.addEventListener("beforeunload", function () {
    if (socket) {
      socket.disconnect();
    }
  });
})();
