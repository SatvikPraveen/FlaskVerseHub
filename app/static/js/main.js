/* FlaskVerseHub: progressive enhancements shared by every page. */
(function () {
  "use strict";

  // Bootstrap tooltips.
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // Auto-dismiss success flashes.
  document.querySelectorAll(".alert-success").forEach(function (el) {
    setTimeout(function () {
      var alert = bootstrap.Alert.getOrCreateInstance(el);
      alert.close();
    }, 6000);
  });

  // Confirmation prompts for destructive forms.
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  // Fetch helper that includes the CSRF token for same-origin JSON requests.
  window.FVH = window.FVH || {};
  window.FVH.fetchJSON = function (url, options) {
    options = options || {};
    options.headers = Object.assign(
      { "Content-Type": "application/json", "X-CSRFToken": window.FVH.csrfToken, Accept: "application/json" },
      options.headers || {}
    );
    if (options.body && typeof options.body !== "string") {
      options.body = JSON.stringify(options.body);
    }
    return fetch(url, options).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) {
          throw Object.assign(new Error(data.message || response.statusText), { status: response.status, data: data });
        }
        return data;
      });
    });
  };
})();
