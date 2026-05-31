(function () {
  var STORAGE_KEY = "sql-sp-harness-theme";
  var THEMES = ["dark", "light"];

  function preferredTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (THEMES.indexOf(stored) !== -1) {
      return stored;
    }
    if (window.matchMedia("(prefers-color-scheme: light)").matches) {
      return "light";
    }
    return "dark";
  }

  function syncThemeToggle(theme) {
    var toggle = document.getElementById("theme-toggle");
    if (!toggle) {
      return;
    }
    var isLight = theme === "light";
    toggle.setAttribute("aria-pressed", isLight ? "true" : "false");
    toggle.setAttribute(
      "aria-label",
      isLight ? "Switch to dark theme" : "Switch to light theme"
    );
    toggle.setAttribute(
      "title",
      isLight ? "Switch to dark theme" : "Switch to light theme"
    );
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
    syncThemeToggle(theme);
  }

  function initTheme() {
    var toggle = document.getElementById("theme-toggle");
    if (!toggle) {
      return;
    }
    var theme = document.documentElement.getAttribute("data-theme") || preferredTheme();
    if (!document.documentElement.getAttribute("data-theme")) {
      applyTheme(theme);
    } else {
      syncThemeToggle(theme);
    }
    toggle.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") || "dark";
      applyTheme(current === "dark" ? "light" : "dark");
    });
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", function (event) {
        if (localStorage.getItem(STORAGE_KEY)) {
          return;
        }
        applyTheme(event.matches ? "dark" : "light");
      });
  }

  function initSidebar() {
    var toggle = document.getElementById("menu-toggle");
    var backdrop = document.getElementById("sidebar-backdrop");
    if (!toggle) {
      return;
    }

    function setOpen(open) {
      document.body.classList.toggle("sidebar-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (backdrop) {
        backdrop.setAttribute("aria-hidden", open ? "false" : "true");
      }
    }

    toggle.addEventListener("click", function () {
      setOpen(!document.body.classList.contains("sidebar-open"));
    });

    if (backdrop) {
      backdrop.addEventListener("click", function () {
        setOpen(false);
      });
    }

    document.querySelectorAll(".sidebar-nav a[href^='#']").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia("(max-width: 900px)").matches) {
          setOpen(false);
        }
      });
    });
  }

  function initCodeTabs() {
    var root = document.querySelector("[data-code-tabs]");
    if (!root) {
      return;
    }
    var tabs = root.querySelectorAll('[role="tab"]');
    var panels = root.querySelectorAll("[data-tab-panel]");

    function activate(tabId) {
      tabs.forEach(function (tab) {
        var selected = tab.getAttribute("data-tab") === tabId;
        tab.setAttribute("aria-selected", selected ? "true" : "false");
        tab.tabIndex = selected ? 0 : -1;
      });
      panels.forEach(function (panel) {
        var active = panel.getAttribute("data-tab-panel") === tabId;
        panel.toggleAttribute("hidden", !active);
        panel.setAttribute("data-active", active ? "true" : "false");
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        activate(tab.getAttribute("data-tab"));
      });
      tab.addEventListener("keydown", function (event) {
        var ids = ["macos", "windows"];
        var current = tab.getAttribute("data-tab");
        var index = ids.indexOf(current);
        if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
          event.preventDefault();
          var next =
            event.key === "ArrowRight"
              ? ids[(index + 1) % ids.length]
              : ids[(index - 1 + ids.length) % ids.length];
          activate(next);
          root.querySelector('[data-tab="' + next + '"]').focus();
        }
      });
    });

    var ua = navigator.userAgent || "";
    if (/Win/i.test(ua) || /Windows/i.test(ua)) {
      activate("windows");
    }
  }

  function initPackageVersion() {
    var root = document.getElementById("package-version");
    if (!root) {
      return;
    }
    var valueEl = root.querySelector(".sidebar-version__value");
    if (!valueEl) {
      return;
    }
    fetch("./version.json")
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        if (data && data.version) {
          valueEl.textContent = "Version: " + data.version;
        }
      })
      .catch(function () {
        /* keep HTML fallback */
      });
  }

  function initCopySnippets() {
    document.querySelectorAll(".snippet-block").forEach(function (block) {
      var button = block.querySelector(".snippet-block__copy");
      var code = block.querySelector("pre code");
      if (!button || !code) {
        return;
      }

      function copyText() {
        var text = code.textContent || "";
        if (!text) {
          return;
        }
        var done = function () {
          button.textContent = "Copied";
          button.setAttribute("data-copied", "true");
          window.setTimeout(function () {
            button.textContent = "Copy";
            button.removeAttribute("data-copied");
          }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () {
            fallbackCopy(text, done);
          });
        } else {
          fallbackCopy(text, done);
        }
      }

      function fallbackCopy(text, onSuccess) {
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.left = "-9999px";
        document.body.appendChild(area);
        area.select();
        try {
          if (document.execCommand("copy")) {
            onSuccess();
          }
        } finally {
          document.body.removeChild(area);
        }
      }

      button.addEventListener("click", function (event) {
        event.preventDefault();
        copyText();
      });
    });
  }

  function boot() {
    initTheme();
    initSidebar();
    initCodeTabs();
    initPackageVersion();
    initCopySnippets();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
