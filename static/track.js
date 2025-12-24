(function () {
  const s = document.currentScript;
  const siteId = s && s.getAttribute("data-site-id");
  if (!siteId) return;

  // ---- Visitor ID ----
  let vid = localStorage.getItem("_va_vid");
  if (!vid) {
    vid = crypto.randomUUID();
    localStorage.setItem("_va_vid", vid);
  }

  const endpoint = "https://analytics-imvks.azurewebsites.net/collect";

  function sendEvent(type, extra = {}) {
    navigator.sendBeacon(
      endpoint,
      JSON.stringify({
        siteId,
        visitorId: vid,
        eventType: type,
        pageUrl: location.href,
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
  // 1️⃣ PAGE VIEW (once)
  // ===============================
  sendEvent("page_view");

  // ===============================
  // 2️⃣ SCROLL (100% once)
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
  // 3️⃣ LINK CLICK (auto)
  // ===============================
  document.addEventListener("click", function (e) {
    const link = e.target.closest("a[href]");
    if (!link) return;

    sendEvent("click", {
      clicked_url: link.href,
      is_external: link.host !== location.host
    });
  });

})();
