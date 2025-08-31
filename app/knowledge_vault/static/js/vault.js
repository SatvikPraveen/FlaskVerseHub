// File: app/knowledge_vault/static/js/vault.js

// Knowledge Vault JavaScript functionality

document.addEventListener("DOMContentLoaded", function () {
  initializeVaultFeatures();
});

function initializeVaultFeatures() {
  // Initialize search functionality
  initializeSearch();

  // Initialize filters
  initializeFilters();

  // Initialize lazy loading for images
  initializeLazyLoading();

  // Initialize tooltips
  initializeTooltips();

  // Initialize keyboard shortcuts
  initializeKeyboardShortcuts();
}

// Search functionality
function initializeSearch() {
  const searchInput = document.querySelector(".search-input");
  const searchForm = document.querySelector(".search-form");

  if (searchInput) {
    // Search suggestions
    let searchTimeout;

    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        showSearchSuggestions(this.value);
      }, 300);
    });

    // Clear suggestions when clicking outside
    document.addEventListener("click", function (e) {
      if (!searchInput.contains(e.target)) {
        hideSearchSuggestions();
      }
    });

    // Handle keyboard navigation in suggestions
    searchInput.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        navigateSearchSuggestions(e.key);
      } else if (e.key === "Escape") {
        hideSearchSuggestions();
        this.blur();
      }
    });
  }
}

function showSearchSuggestions(query) {
  if (query.length < 2) {
    hideSearchSuggestions();
    return;
  }

  fetch(`/knowledge_vault/search-suggestions?q=${encodeURIComponent(query)}`)
    .then((response) => response.json())
    .then((data) => {
      const suggestions = data.suggestions || [];
      displaySearchSuggestions(suggestions);
    })
    .catch((error) => {
      console.error("Error fetching search suggestions:", error);
    });
}

function displaySearchSuggestions(suggestions) {
  const searchInput = document.querySelector(".search-input");
  let suggestionsContainer = document.getElementById("searchSuggestions");

  if (!suggestionsContainer) {
    suggestionsContainer = document.createElement("div");
    suggestionsContainer.id = "searchSuggestions";
    suggestionsContainer.className = "search-suggestions";
    searchInput.parentNode.appendChild(suggestionsContainer);
  }

  if (suggestions.length === 0) {
    hideSearchSuggestions();
    return;
  }

  const suggestionsHTML = suggestions
    .map(
      (suggestion, index) => `
        <div class="suggestion-item" data-index="${index}" onclick="selectSuggestion('${suggestion.text}')">
            <span class="suggestion-text">${suggestion.text}</span>
            <span class="suggestion-type">${suggestion.type}</span>
        </div>
    `
    )
    .join("");

  suggestionsContainer.innerHTML = suggestionsHTML;
  suggestionsContainer.style.display = "block";
}

function hideSearchSuggestions() {
  const suggestionsContainer = document.getElementById("searchSuggestions");
  if (suggestionsContainer) {
    suggestionsContainer.style.display = "none";
  }
}

function selectSuggestion(text) {
  const searchInput = document.querySelector(".search-input");
  searchInput.value = text;
  hideSearchSuggestions();
  searchInput.form.submit();
}

function navigateSearchSuggestions(direction) {
  const suggestions = document.querySelectorAll(".suggestion-item");
  const current = document.querySelector(".suggestion-item.active");

  if (suggestions.length === 0) return;

  let nextIndex = 0;

  if (current) {
    current.classList.remove("active");
    const currentIndex = parseInt(current.dataset.index);

    if (direction === "ArrowDown") {
      nextIndex = currentIndex < suggestions.length - 1 ? currentIndex + 1 : 0;
    } else {
      nextIndex = currentIndex > 0 ? currentIndex - 1 : suggestions.length - 1;
    }
  }

  suggestions[nextIndex].classList.add("active");
}

// Filter functionality
function initializeFilters() {
  const categoryFilter = document.querySelector('select[name="category"]');
  const sortFilter = document.querySelector('select[name="sort"]');

  if (categoryFilter) {
    categoryFilter.addEventListener("change", function () {
      this.form.submit();
    });
  }

  if (sortFilter) {
    sortFilter.addEventListener("change", function () {
      this.form.submit();
    });
  }
}

// Lazy loading for images
function initializeLazyLoading() {
  const images = document.querySelectorAll("img[data-src]");

  if ("IntersectionObserver" in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.classList.remove("lazy");
          observer.unobserve(img);
        }
      });
    });

    images.forEach((img) => imageObserver.observe(img));
  } else {
    // Fallback for browsers without IntersectionObserver
    images.forEach((img) => {
      img.src = img.dataset.src;
      img.classList.remove("lazy");
    });
  }
}

// Tooltip initialization
function initializeTooltips() {
  const tooltipElements = document.querySelectorAll("[data-tooltip]");

  tooltipElements.forEach((element) => {
    element.addEventListener("mouseenter", showTooltip);
    element.addEventListener("mouseleave", hideTooltip);
  });
}

function showTooltip(e) {
  const tooltipText = e.target.dataset.tooltip;
  if (!tooltipText) return;

  const tooltip = document.createElement("div");
  tooltip.className = "tooltip";
  tooltip.textContent = tooltipText;
  tooltip.id = "activeTooltip";

  document.body.appendChild(tooltip);

  const rect = e.target.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();

  tooltip.style.left =
    rect.left + rect.width / 2 - tooltipRect.width / 2 + "px";
  tooltip.style.top = rect.top - tooltipRect.height - 10 + "px";

  setTimeout(() => {
    tooltip.classList.add("show");
  }, 100);
}

function hideTooltip() {
  const tooltip = document.getElementById("activeTooltip");
  if (tooltip) {
    tooltip.classList.remove("show");
    setTimeout(() => {
      tooltip.remove();
    }, 200);
  }
}

// Keyboard shortcuts
function initializeKeyboardShortcuts() {
  document.addEventListener("keydown", function (e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      const searchInput = document.querySelector(".search-input");
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }

    // Ctrl/Cmd + N for new entry (if authenticated)
    if ((e.ctrlKey || e.metaKey) && e.key === "n") {
      const newEntryLink = document.querySelector('a[href*="create"]');
      if (newEntryLink && !e.defaultPrevented) {
        e.preventDefault();
        window.location.href = newEntryLink.href;
      }
    }

    // Escape to close modals
    if (e.key === "Escape") {
      const openModal = document.querySelector('.modal[style*="flex"]');
      if (openModal) {
        openModal.style.display = "none";
      }
    }
  });
}

// Entry card interactions
function initializeEntryCards() {
  const entryCards = document.querySelectorAll(".entry-card");

  entryCards.forEach((card) => {
    // Add click handler to make entire card clickable
    card.addEventListener("click", function (e) {
      // Don't trigger if clicking on action buttons
      if (e.target.closest(".entry-actions") || e.target.closest("a")) {
        return;
      }

      const titleLink = this.querySelector(".entry-title a");
      if (titleLink) {
        window.location.href = titleLink.href;
      }
    });

    // Add hover effects
    card.addEventListener("mouseenter", function () {
      this.classList.add("hovered");
    });

    card.addEventListener("mouseleave", function () {
      this.classList.remove("hovered");
    });
  });
}

// Infinite scroll functionality
function initializeInfiniteScroll() {
  if (!document.querySelector(".pagination")) return;

  let loading = false;
  let currentPage = 1;
  const maxPage =
    parseInt(document.querySelector("[data-max-page]")?.dataset.maxPage) || 1;

  window.addEventListener("scroll", function () {
    if (loading || currentPage >= maxPage) return;

    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;

    if (scrollTop + windowHeight >= documentHeight - 1000) {
      loadMoreEntries();
    }
  });

  function loadMoreEntries() {
    loading = true;
    currentPage++;

    const params = new URLSearchParams(window.location.search);
    params.set("page", currentPage);

    fetch(`${window.location.pathname}?${params.toString()}`)
      .then((response) => response.text())
      .then((html) => {
        const parser = new DOMParser();
        const newDocument = parser.parseFromString(html, "text/html");
        const newEntries = newDocument.querySelectorAll(".entry-card");

        const entriesList = document.querySelector(".entries-list");
        newEntries.forEach((entry) => {
          entriesList.appendChild(entry.cloneNode(true));
        });

        loading = false;
        initializeEntryCards(); // Re-initialize for new cards
      })
      .catch((error) => {
        console.error("Error loading more entries:", error);
        loading = false;
      });
  }
}

// Tag management
function initializeTagManagement() {
  const tagInputs = document.querySelectorAll(".tag-input");

  tagInputs.forEach((input) => {
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        addTag(this);
      } else if (e.key === "Backspace" && this.value === "") {
        removeLastTag(this);
      }
    });

    input.addEventListener("blur", function () {
      if (this.value.trim()) {
        addTag(this);
      }
    });
  });
}

function addTag(input) {
  const value = input.value.trim();
  if (!value) return;

  const tagsContainer = input.previousElementSibling;
  if (!tagsContainer || !tagsContainer.classList.contains("tags-display"))
    return;

  // Check for duplicates
  const existingTags = Array.from(tagsContainer.querySelectorAll(".tag")).map(
    (tag) => tag.textContent
  );
  if (existingTags.includes(value)) {
    input.value = "";
    return;
  }

  const tagElement = document.createElement("span");
  tagElement.className = "tag removable";
  tagElement.innerHTML = `
        ${value}
        <button type="button" class="tag-remove" onclick="removeTag(this)">×</button>
    `;

  tagsContainer.appendChild(tagElement);
  input.value = "";

  updateTagsInput(input);
}

function removeTag(button) {
  const tag = button.parentElement;
  const tagsContainer = tag.parentElement;
  tag.remove();

  const input = tagsContainer.nextElementSibling;
  updateTagsInput(input);
}

function removeLastTag(input) {
  const tagsContainer = input.previousElementSibling;
  const tags = tagsContainer.querySelectorAll(".tag");
  if (tags.length > 0) {
    tags[tags.length - 1].remove();
    updateTagsInput(input);
  }
}

function updateTagsInput(tagInput) {
  const tagsContainer = tagInput.previousElementSibling;
  const tags = Array.from(tagsContainer.querySelectorAll(".tag")).map((tag) =>
    tag.textContent.replace("×", "").trim()
  );

  const hiddenInput = document.getElementById("tags");
  if (hiddenInput) {
    hiddenInput.value = tags.join(", ");
  }
}

// Content formatting helpers
function insertMarkdown(before, after = "") {
  const textarea = document.getElementById("contentEditor");
  if (!textarea) return;

  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selectedText = textarea.value.substring(start, end);

  const newText = before + selectedText + after;

  textarea.value =
    textarea.value.substring(0, start) +
    newText +
    textarea.value.substring(end);

  // Reset cursor position
  const newCursorPos = start + before.length + selectedText.length;
  textarea.setSelectionRange(newCursorPos, newCursorPos);
  textarea.focus();
}

// Export functions for global use
window.VaultJS = {
  insertMarkdown,
  showSearchSuggestions,
  hideSearchSuggestions,
  selectSuggestion,
  addTag,
  removeTag,
  showTooltip,
  hideTooltip,
};

// Auto-initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeVaultFeatures);
} else {
  initializeVaultFeatures();
}
