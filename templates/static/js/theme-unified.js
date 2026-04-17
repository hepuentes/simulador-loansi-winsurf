(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var DEFAULT_THEME = "light";

  // Obtener tema guardado
  function getStoredTheme() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "light" || stored === "dark") {
        return stored;
      }
    } catch (e) {
      console.warn("localStorage no disponible");
    }

    var matches = document.cookie.match(
      new RegExp("(^| )" + STORAGE_KEY + "=([^;]+)")
    );
    if (matches && matches[2]) {
      return matches[2];
    }

    return DEFAULT_THEME;
  }

  // Guardar tema
  function saveTheme(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (e) {
      console.warn("No se pudo guardar en localStorage");
    }

    var maxAge = 365 * 24 * 60 * 60;
    document.cookie =
      STORAGE_KEY + "=" + value + ";path=/;SameSite=Lax;max-age=" + maxAge;
  }

  // Actualizar iconos
  function setIconForTheme(theme) {
    var selectors = [
      ".theme-toggle-public",
      ".theme-toggle-result",
      ".theme-toggle-login",
      "#theme-toggle",
      "#theme-toggle-nav",
      "#toggleThemeBtn",
      "#toggleTheme",
      ".theme-toggle",
      ".mobile-nav-theme-toggle",
      '[data-action="toggle-theme"]',
    ];

    var buttons = document.querySelectorAll(selectors.join(","));

    buttons.forEach(function (button) {
      if (button) {
        var icon = button.querySelector("i");
        if (
          !icon &&
          (button.tagName === "I" || button.classList.contains("bi"))
        ) {
          icon = button;
        }

        if (icon) {
          icon.classList.remove(
            "bi-sun",
            "bi-sun-fill",
            "bi-moon",
            "bi-moon-fill"
          );
          icon.classList.add(theme === "dark" ? "bi-sun-fill" : "bi-moon-fill");
        }

        if (button.tagName === "BUTTON") {
          button.setAttribute("aria-pressed", theme === "dark");
          button.setAttribute(
            "aria-label",
            theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"
          );
        }
      }
    });
  }

  // Aplicar tema
  function applyTheme(theme) {
    if (document.documentElement) {
      document.documentElement.setAttribute("data-theme", theme);
    }

    if (document.body) {
      document.body.setAttribute("data-theme", theme);

      if (theme === "dark") {
        document.body.style.backgroundColor = "#0f0f23";
        document.body.style.color = "#f7fafc";
      } else {
        document.body.style.backgroundColor = "#f8f9fa";
        document.body.style.color = "#1a202c";
      }
    }

    saveTheme(theme);
    setIconForTheme(theme);

    if (window.CustomEvent) {
      window.dispatchEvent(
        new CustomEvent("themeChanged", { detail: { theme: theme } })
      );
    }
  }

  // Obtener tema actual
  function currentTheme() {
    var htmlTheme =
      document.documentElement &&
      document.documentElement.getAttribute("data-theme");
    if (htmlTheme === "dark" || htmlTheme === "light") {
      return htmlTheme;
    }
    return getStoredTheme();
  }

  // Alternar tema
  function toggleTheme() {
    var current = currentTheme();
    var next = current === "dark" ? "light" : "dark";
    applyTheme(next);
    return next;
  }

  // ============================================
  // LOGOUT MÓVIL - VERSIÓN ULTRA RÁPIDA
  // ============================================

  var isLoggingOut = false;

  // Exponer globalmente para que otros scripts puedan verificar
  window.isLoggingOut = false;

  function forceLogout() {
    if (isLoggingOut) return;
    isLoggingOut = true;
    window.isLoggingOut = true;

    // Detener TODOS los intervalos activos (polling, etc.)
    var maxIntervalId = setInterval(function(){}, 0);
    for (var i = 1; i <= maxIntervalId; i++) {
      clearInterval(i);
    }

    // Inyectar CSS que desactiva TODAS las transiciones inmediatamente
    var style = document.createElement('style');
    style.id = 'logout-fast-style';
    style.textContent = '* { transition: none !important; animation: none !important; transition-duration: 0s !important; animation-duration: 0s !important; }';
    document.head.appendChild(style);

    // Ocultar body para evitar parpadeos
    document.body.style.opacity = '0';
    document.body.style.pointerEvents = 'none';

    // Redirect inmediato - usar replace para no agregar al historial
    window.location.replace("/logout");
  }

  // Manejar eventos
  function attachHandlers() {
    // Handler en fase de CAPTURA (true) para interceptar ANTES que cualquier otro
    document.addEventListener("click", function (e) {

      // ============================================
      // LOGOUT - MÁXIMA PRIORIDAD ABSOLUTA
      // ============================================
      var logoutLink = e.target.closest('a[href="/logout"]');
      if (logoutLink) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        forceLogout();
        return false;
      }

      // ============================================
      // TEMA
      // ============================================
      var themeButtonSelectors = [
        ".theme-toggle-public",
        ".theme-toggle-result",
        ".theme-toggle-login",
        "#theme-toggle",
        "#theme-toggle-nav",
        "#toggleThemeBtn",
        "#toggleTheme",
        ".theme-toggle",
        ".mobile-nav-theme-toggle",
        '[data-action="toggle-theme"]',
      ];

      var isThemeButton = themeButtonSelectors.some(function (selector) {
        return e.target.matches(selector) || e.target.closest(selector);
      });

      if (isThemeButton) {
        e.preventDefault();
        e.stopPropagation();
        toggleTheme();
        return;
      }

      // ============================================
      // MENÚ MÓVIL
      // ============================================
      if (
        e.target.matches(".mobile-nav-hamburger") ||
        e.target.closest(".mobile-nav-hamburger")
      ) {
        e.stopPropagation();
        var mobileMenu = document.querySelector(".mobile-nav-menu");
        if (mobileMenu) {
          var isOpen = mobileMenu.classList.toggle("show");
          var hamburger = e.target.closest(".mobile-nav-hamburger") || e.target;
          hamburger.textContent = isOpen ? "✕" : "☰";
        }
        return;
      }

      // Cerrar menú móvil al hacer clic fuera
      if (
        !e.target.closest(".mobile-nav") &&
        document.querySelector(".mobile-nav-menu.show")
      ) {
        var mobileMenu = document.querySelector(".mobile-nav-menu");
        var hamburger = document.querySelector(".mobile-nav-hamburger");
        if (mobileMenu && hamburger) {
          mobileMenu.classList.remove("show");
          hamburger.textContent = "☰";
        }
      }
    }, true); // true = fase de CAPTURA
  }

  // Aplicar tema inicial
  function applyInitialTheme() {
    var theme = getStoredTheme();

    if (document.documentElement) {
      document.documentElement.setAttribute("data-theme", theme);
    }

    if (document.body) {
      document.body.setAttribute("data-theme", theme);
      if (theme === "dark") {
        document.body.style.backgroundColor = "#0f0f23";
        document.body.style.color = "#f7fafc";
      }
    }
  }

  // Inicializar
  function initialize() {
    var theme = getStoredTheme();
    applyTheme(theme);
    attachHandlers();
    // ELIMINADO: updateMobileTitle() - El nombre del usuario ya viene de Jinja2
  }

  // Aplicar tema inicial inmediatamente
  applyInitialTheme();

  // Inicializar cuando DOM esté listo
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }

  // Exponer funciones globales
  window.toggleTheme = toggleTheme;
  window.applyTheme = applyTheme;
})();

// ============================================
// DETECCIÓN DE SESIÓN EXPIRADA EN FRONTEND
// ============================================
(function() {
  "use strict";

  function isProtectedRoute() {
    var path = window.location.pathname;
    var publicRoutes = ['/', '/calcular', '/login', '/logout'];
    return !publicRoutes.includes(path);
  }

  function checkSessionStatus() {
    // NO verificar si estamos en logout o login
    var path = window.location.pathname;
    if (path === '/logout' || path === '/login') {
      return;
    }

    if (!isProtectedRoute()) {
      return;
    }

    fetch('/api/session-status', {
      method: 'GET',
      credentials: 'same-origin'
    })
    .then(function(response) {
      if (response.status === 401 || response.status === 403) {
        console.log('⚠️ Sesión expirada detectada');
        window.location.href = '/login';
      }
    })
    .catch(function(error) {
      // Silenciar errores de red
    });
  }

  // Verificar cada 5 minutos - con delay inicial de 60 segundos
  if (isProtectedRoute()) {
    setTimeout(function() {
      setInterval(checkSessionStatus, 300000);
    }, 60000);
  }
})();