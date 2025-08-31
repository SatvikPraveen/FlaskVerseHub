// File: FlaskVerseHub/app/static/js/main.js

// Global FlaskVerseHub JavaScript functionality
(function () {
  "use strict";

  // Initialize when DOM is ready
  document.addEventListener("DOMContentLoaded", function () {
    initializeApp();
  });

  /**
   * Main application initialization
   */
  function initializeApp() {
    initializeCSRF();
    initializeNavbar();
    initializeTooltips();
    initializeModals();
    initializeFormValidation();
    initializeFileUploads();
    initializePasswordToggles();
    initializeLoadingStates();
    initializeConfirmDialogs();

    console.log("FlaskVerseHub initialized successfully");
  }

  /**
   * CSRF Token Management
   */
  function initializeCSRF() {
    const csrfToken = document
      .querySelector("meta[name=csrf-token]")
      ?.getAttribute("content");

    if (csrfToken) {
      // Set CSRF token for all AJAX requests
      window.csrfToken = csrfToken;

      // Configure jQuery AJAX if available
      if (typeof $ !== "undefined") {
        $.ajaxSetup({
          beforeSend: function (xhr, settings) {
            if (
              !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
              !this.crossDomain
            ) {
              xhr.setRequestHeader("X-CSRFToken", csrfToken);
            }
          },
        });
      }
    }
  }

  /**
   * Navbar functionality
   */
  function initializeNavbar() {
    // Mobile menu toggle
    const navbarToggler = document.querySelector(".navbar-toggler");
    const navbarCollapse = document.querySelector(".navbar-collapse");

    if (navbarToggler && navbarCollapse) {
      navbarToggler.addEventListener("click", function () {
        navbarCollapse.classList.toggle("show");
      });
    }

    // Close dropdowns when clicking outside
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".dropdown")) {
        const openDropdowns = document.querySelectorAll(".dropdown-menu.show");
        openDropdowns.forEach((menu) => menu.classList.remove("show"));
      }
    });
  }

  /**
   * Initialize tooltips (if Bootstrap tooltips are available)
   */
  function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll(
      '[data-bs-toggle="tooltip"]'
    );
    if (tooltipTriggerList.length > 0 && typeof bootstrap !== "undefined") {
      tooltipTriggerList.forEach((tooltipTriggerEl) => {
        new bootstrap.Tooltip(tooltipTriggerEl);
      });
    }
  }

  /**
   * Modal functionality
   */
  function initializeModals() {
    // Auto-focus first input in modals
    const modals = document.querySelectorAll(".modal");
    modals.forEach((modal) => {
      modal.addEventListener("shown.bs.modal", function () {
        const firstInput = this.querySelector("input, select, textarea");
        if (firstInput) {
          firstInput.focus();
        }
      });
    });

    // Confirmation modals
    const confirmButtons = document.querySelectorAll("[data-confirm]");
    confirmButtons.forEach((button) => {
      button.addEventListener("click", function (e) {
        e.preventDefault();
        const message = this.getAttribute("data-confirm") || "Are you sure?";
        if (confirm(message)) {
          // If it's a form button, submit the form
          const form = this.closest("form");
          if (form) {
            form.submit();
          } else if (this.href) {
            window.location.href = this.href;
          }
        }
      });
    });
  }

  /**
   * Form validation
   */
  function initializeFormValidation() {
    const forms = document.querySelectorAll("form.needs-validation");
    forms.forEach((form) => {
      form.addEventListener("submit", function (e) {
        if (!form.checkValidity()) {
          e.preventDefault();
          e.stopPropagation();
          showValidationErrors(form);
        }
        form.classList.add("was-validated");
      });

      // Real-time validation
      const inputs = form.querySelectorAll("input, select, textarea");
      inputs.forEach((input) => {
        input.addEventListener("blur", function () {
          validateInput(this);
        });
      });
    });
  }

  /**
   * Validate individual input
   */
  function validateInput(input) {
    const isValid = input.checkValidity();
    const feedback = input.parentNode.querySelector(".invalid-feedback");

    if (!isValid) {
      input.classList.add("is-invalid");
      input.classList.remove("is-valid");
      if (feedback) {
        feedback.textContent = input.validationMessage;
      }
    } else {
      input.classList.remove("is-invalid");
      input.classList.add("is-valid");
    }
  }

  /**
   * Show validation errors
   */
  function showValidationErrors(form) {
    const firstInvalidInput = form.querySelector(":invalid");
    if (firstInvalidInput) {
      firstInvalidInput.focus();
      firstInvalidInput.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  /**
   * File upload functionality
   */
  function initializeFileUploads() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach((input) => {
      const dropZone = input.closest(".drop-zone");

      if (dropZone) {
        initializeDropZone(input, dropZone);
      }

      input.addEventListener("change", function () {
        handleFileSelection(this);
      });
    });
  }

  /**
   * Initialize drag and drop zones
   */
  function initializeDropZone(input, dropZone) {
    dropZone.addEventListener("dragover", function (e) {
      e.preventDefault();
      this.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", function (e) {
      e.preventDefault();
      this.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", function (e) {
      e.preventDefault();
      this.classList.remove("dragover");
      input.files = e.dataTransfer.files;
      handleFileSelection(input);
    });

    dropZone.addEventListener("click", function () {
      input.click();
    });
  }

  /**
   * Handle file selection
   */
  function handleFileSelection(input) {
    const files = Array.from(input.files);
    const preview = input.parentNode.querySelector(".file-preview");

    if (preview && files.length > 0) {
      displayFilePreview(files, preview);
    }
  }

  /**
   * Display file preview
   */
  function displayFilePreview(files, preview) {
    preview.innerHTML = "";
    preview.classList.remove("d-none");

    files.forEach((file, index) => {
      const fileItem = document.createElement("div");
      fileItem.className =
        "file-item d-flex align-items-center justify-content-between p-2 border rounded mb-2";
      fileItem.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="fas fa-file text-primary me-2"></i>
                    <div>
                        <div class="file-name fw-medium">${file.name}</div>
                        <small class="file-size text-muted">${formatFileSize(
                          file.size
                        )}</small>
                    </div>
                </div>
                <button type="button" class="btn btn-sm btn-outline-danger file-remove" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            `;
      preview.appendChild(fileItem);
    });

    // Add remove functionality
    const removeButtons = preview.querySelectorAll(".file-remove");
    removeButtons.forEach((button) => {
      button.addEventListener("click", function () {
        this.closest(".file-item").remove();
        // Note: Cannot directly remove from FileList, would need custom implementation
      });
    });
  }

  /**
   * Format file size
   */
  function formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  /**
   * Password toggle functionality
   */
  function initializePasswordToggles() {
    window.togglePassword = function (inputId) {
      const input = document.getElementById(inputId);
      const icon = document.getElementById(inputId + "-toggle-icon");

      if (input && icon) {
        if (input.type === "password") {
          input.type = "text";
          icon.classList.remove("fa-eye");
          icon.classList.add("fa-eye-slash");
        } else {
          input.type = "password";
          icon.classList.remove("fa-eye-slash");
          icon.classList.add("fa-eye");
        }
      }
    };
  }

  /**
   * Loading states
   */
  function initializeLoadingStates() {
    window.showLoading = function (message = "Loading...") {
      const spinner = document.getElementById("loading-spinner");
      if (spinner) {
        const messageEl = spinner.querySelector("p");
        if (messageEl) messageEl.textContent = message;
        spinner.classList.remove("d-none");
      }
    };

    window.hideLoading = function () {
      const spinner = document.getElementById("loading-spinner");
      if (spinner) {
        spinner.classList.add("d-none");
      }
    };

    // Show loading on form submissions
    const forms = document.querySelectorAll("form");
    forms.forEach((form) => {
      form.addEventListener("submit", function () {
        if (this.checkValidity()) {
          showLoading("Submitting...");
        }
      });
    });
  }

  /**
   * Confirmation dialogs
   */
  function initializeConfirmDialogs() {
    window.showConfirmDialog = function (message, onConfirm, onCancel) {
      const confirmed = confirm(message);
      if (confirmed && typeof onConfirm === "function") {
        onConfirm();
      } else if (!confirmed && typeof onCancel === "function") {
        onCancel();
      }
      return confirmed;
    };
  }

  /**
   * AJAX utilities
   */
  window.FlaskVerseHubAPI = {
    request: function (url, options = {}) {
      const defaults = {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": window.csrfToken || "",
        },
      };

      const config = Object.assign({}, defaults, options);

      if (
        config.method !== "GET" &&
        config.body &&
        typeof config.body === "object"
      ) {
        config.body = JSON.stringify(config.body);
      }

      return fetch(url, config)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const contentType = response.headers.get("Content-Type");
          if (contentType && contentType.includes("application/json")) {
            return response.json();
          }
          return response.text();
        })
        .catch((error) => {
          console.error("API request failed:", error);
          if (typeof showToast === "function") {
            showToast("Request failed: " + error.message, "error");
          }
          throw error;
        });
    },

    get: function (url, params = {}) {
      const urlParams = new URLSearchParams(params);
      const fullUrl = urlParams.toString() ? `${url}?${urlParams}` : url;
      return this.request(fullUrl);
    },

    post: function (url, data = {}) {
      return this.request(url, {
        method: "POST",
        body: data,
      });
    },

    put: function (url, data = {}) {
      return this.request(url, {
        method: "PUT",
        body: data,
      });
    },

    delete: function (url) {
      return this.request(url, {
        method: "DELETE",
      });
    },
  };

  /**
   * Notification utilities
   */
  window.showNotification = function (message, type = "info", duration = 5000) {
    if (typeof showToast === "function") {
      showToast(message, type, duration);
    } else {
      // Fallback to console
      console.log(`${type.toUpperCase()}: ${message}`);
    }
  };

  /**
   * Utility functions
   */
  window.FlaskVerseHubUtils = {
    debounce: function (func, wait, immediate) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          timeout = null;
          if (!immediate) func.apply(this, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(this, args);
      };
    },

    throttle: function (func, limit) {
      let inThrottle;
      return function (...args) {
        if (!inThrottle) {
          func.apply(this, args);
          inThrottle = true;
          setTimeout(() => (inThrottle = false), limit);
        }
      };
    },

    formatDate: function (date, options = {}) {
      const defaults = {
        year: "numeric",
        month: "short",
        day: "numeric",
      };
      return new Date(date).toLocaleDateString(
        "en-US",
        Object.assign(defaults, options)
      );
    },

    formatTime: function (date, options = {}) {
      const defaults = {
        hour: "2-digit",
        minute: "2-digit",
      };
      return new Date(date).toLocaleTimeString(
        "en-US",
        Object.assign(defaults, options)
      );
    },

    escapeHtml: function (text) {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    },

    scrollToTop: function (smooth = true) {
      window.scrollTo({
        top: 0,
        behavior: smooth ? "smooth" : "auto",
      });
    },

    copyToClipboard: function (text) {
      if (navigator.clipboard) {
        return navigator.clipboard.writeText(text).then(() => {
          if (typeof showToast === "function") {
            showToast("Copied to clipboard!", "success", 2000);
          }
        });
      } else {
        // Fallback for older browsers
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const success = document.execCommand("copy");
        document.body.removeChild(textArea);

        if (success && typeof showToast === "function") {
          showToast("Copied to clipboard!", "success", 2000);
        }

        return Promise.resolve(success);
      }
    },

    generateId: function () {
      return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },

    isEmpty: function (value) {
      return (
        value === null ||
        value === undefined ||
        value === "" ||
        (Array.isArray(value) && value.length === 0) ||
        (typeof value === "object" && Object.keys(value).length === 0)
      );
    },
  };

  /**
   * Global event handlers
   */

  // Handle file drag and drop globally
  window.handleFileDrop = function (event, fieldId) {
    event.preventDefault();
    const input = document.getElementById(fieldId);
    if (input) {
      input.files = event.dataTransfer.files;
      handleFileSelection(input);
    }
    event.target.closest(".drop-zone").classList.remove("dragover");
  };

  window.handleDragOver = function (event) {
    event.preventDefault();
    event.target.closest(".drop-zone").classList.add("dragover");
  };

  window.handleDragLeave = function (event) {
    event.preventDefault();
    event.target.closest(".drop-zone").classList.remove("dragover");
  };

  window.handleFileSelect = function (event) {
    handleFileSelection(event.target);
  };

  // Keyboard shortcuts
  document.addEventListener("keydown", function (e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      const searchInput = document.querySelector('input[name="q"]');
      if (searchInput) {
        searchInput.focus();
      }
    }

    // Escape to close modals
    if (e.key === "Escape") {
      const openModals = document.querySelectorAll(".modal.show");
      openModals.forEach((modal) => {
        const modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) {
          modalInstance.hide();
        }
      });
    }
  });
})();
