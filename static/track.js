(function () {
  const s = document.currentScript;
  const siteId = s && s.getAttribute("data-site-id");
  if (!siteId) return;

  const endpoint = "https://analytics-imvks.azurewebsites.net/collect";

  // ===============================
  // VISITOR ID (persistent)
  // ===============================
  let vid = localStorage.getItem("_va_vid");
  if (!vid) {
    vid = crypto.randomUUID();
    localStorage.setItem("_va_vid", vid);
  }

  // ===============================
  // FIRST VISIT
  // ===============================
  const isFirstVisit = !localStorage.getItem("_va_first_visit");
  if (isFirstVisit) {
    localStorage.setItem("_va_first_visit", "1");
  }

  // ===============================
  // SESSION MANAGEMENT
  // ===============================
  const SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes
  const now = Date.now();

  let sessionId = localStorage.getItem("_va_session_id");
  let lastActivity = localStorage.getItem("_va_last_activity");

  let isNewSession = false;

  if (!sessionId || !lastActivity || now - lastActivity > SESSION_TIMEOUT) {
    sessionId = crypto.randomUUID();
    localStorage.setItem("_va_session_id", sessionId);
    isNewSession = true;
  }

  localStorage.setItem("_va_last_activity", now);

  // ===============================
  // SEND EVENT
  // ===============================
  function sendEvent(type, extra = {}) {
    navigator.sendBeacon(
      endpoint,
      JSON.stringify({
        siteId,
        visitorId: vid,
        sessionId,
        eventType: type,
        pageUrl: location.href,
        pageTitle: window.document.title,
        referrer: document.referrer,
        userAgent: navigator.userAgent,
        language: navigator.language,
        platform: navigator.platform,
        screenSize: screen.width + "x" + screen.height,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        ...extra
      })
    );
  }

  // ===============================
  // SESSION START
  // ===============================
  if (isNewSession) {
    sendEvent("session_start");
  }

  // ===============================
  // FIRST VISIT EVENT
  // ===============================
  if (isFirstVisit) {
    sendEvent("first_visit");
  }

  // ===============================
  // PAGE VIEW
  // ===============================
  sendEvent("page_view");

  // ===============================
  // USER ENGAGEMENT (10s)
  // ===============================
  let engaged = false;

  setTimeout(() => {
    if (!engaged) {
      engaged = true;
      sendEvent("user_engagement", { engagement_time_sec: 10 });
    }
  }, 10000);

  // ===============================
  // SCROLL (100% once)
  // ===============================
  let scrollSent = false;

  window.addEventListener("scroll", function () {
    if (scrollSent) return;

    const pos = window.scrollY + window.innerHeight;
    const height = document.documentElement.scrollHeight;

    if (pos >= height - 5) {
      scrollSent = true;
      sendEvent("scroll");
    }
  });

  // ===============================
  // LINK CLICK
  // ===============================
  document.addEventListener("click", function (e) {
    const link = e.target.closest("a[href]");
    if (!link) return;

    sendEvent("click", {
      clicked_url: link.href,
      is_external: link.host !== location.host
    });
  });

  // ===============================
  // FORM START
  // ===============================
  let formStarted = false;

  document.addEventListener("focusin", function (e) {
    if (formStarted) return;

    const el = e.target;
    if (
      el.tagName === "INPUT" ||
      el.tagName === "TEXTAREA" ||
      el.tagName === "SELECT"
    ) {
      formStarted = true;
      sendEvent("form_start", {
        field_name: el.name || el.id || "unknown"
      });
    }
  });

})();
