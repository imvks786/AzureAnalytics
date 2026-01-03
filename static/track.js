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
  // ===============================
  // SCROLL - fire once per threshold crossed
  // ===============================
  const SCROLL_THRESHOLDS = [50, 70, 90, 100];
  const sentThresholds = new Set();

  window.addEventListener("scroll", function () {
    const pos = window.scrollY + window.innerHeight;
    const height = document.documentElement.scrollHeight || 1;
    const percent = Math.min(100, Math.round((pos / height) * 100));

    // check thresholds and send for any newly crossed ones
    for (let i = 0; i < SCROLL_THRESHOLDS.length; i++) {
      const t = SCROLL_THRESHOLDS[i];
      if (percent >= t && !sentThresholds.has(t)) {
        sentThresholds.add(t);
        sendEvent("scroll", { scrollPercent: percent, scrollThreshold: t });
      }
    }
  }, { passive: true });

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
  // DYNAMIC TRACKING RULES
  // Fetch rules from server and attach listeners
  // ===============================
  (function attachRules() {
    try {
      const rulesUrl = endpoint.replace('/collect', '/rules') + '?site_id=' + encodeURIComponent(siteId);
      fetch(rulesUrl)
        .then((res) => res.json())
        .then((payload) => {
          const rules = (payload && payload.rules) || [];
          const attached = new Set();
          rules.forEach((r) => {
            const key = r.event_type + '|' + r.selector;
            if (attached.has(key)) return;
            attached.add(key);

            // Use event delegation for most events
            document.addEventListener(r.event_type, function (e) {
              const el = e.target.closest(r.selector);
              if (!el) return;
              // send rule-defined event name
              sendEvent(r.event_name, {
                selector: r.selector,
                clicked_url: el.href || null
              });
            });
          });
        })
        .catch((err) => {
          // silently ignore rules fetch errors
          console.warn('Failed to fetch tracking rules', err);
        });
    } catch (e) {
      console.warn('Error attaching rules', e);
    }
  })();

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
