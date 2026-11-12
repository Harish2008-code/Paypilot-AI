(function () {
  "use strict";
  const app = window.PayPilotApp;
  if (!app) return;
  const button = document.getElementById("refresh-analytics");
  if (!button) return;
  button.addEventListener("click", async function () {
    app.setLoading(button, true);
    try {
      const response = await app.api("/api/analytics/refresh/", { method: "POST", body: JSON.stringify({}) });
      const brief = response.brief;
      const forecast = response.forecast;
      const set = function (id, value) { const target = document.getElementById(id); if (target) target.textContent = value; };
      set("analytics-gross", response.metrics.gross);
      set("forecast-next-week", forecast.next_week);
      set("forecast-daily-average", forecast.daily_average);
      set("forecast-change", forecast.change_percent);
      set("analyst-headline", brief.headline);
      set("analyst-next", brief.next_step);
      set("analyst-mode", brief.mode);
      app.toast("Payment intelligence refreshed.", "success");
    } catch (error) { app.toast(error.message, "error"); }
    finally { app.setLoading(button, false); }
  });
}());
