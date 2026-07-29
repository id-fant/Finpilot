import React from "react";
import ReactDOM from "react-dom/client";

// The dashboard predates modules and its panels share a small window-level
// contract. Expose React first, then load the existing files in dependency
// order. This gives us a production Vite build without a risky panel rewrite;
// each panel can migrate to explicit imports incrementally.
window.React = React;
window.ReactDOM = ReactDOM;

function showBootFailure(error) {
  const root = document.getElementById("root");
  if (!root) return;
  root.innerHTML = "";
  const main = document.createElement("main");
  main.className = "fatal-screen";
  main.setAttribute("role", "alert");
  const panel = document.createElement("div");
  panel.className = "fatal-panel";
  const code = document.createElement("div");
  code.className = "fatal-code";
  code.textContent = "STARTUP / RECOVERY";
  const title = document.createElement("h1");
  title.textContent = "FinPilot could not load";
  const message = document.createElement("p");
  message.textContent = "The browser received mismatched or incomplete frontend files. Reload after the development servers are ready.";
  const detail = document.createElement("code");
  detail.textContent = error?.message || "Unknown startup error";
  const reload = document.createElement("button");
  reload.className = "btn-primary";
  reload.textContent = "Reload dashboard";
  reload.addEventListener("click", () => location.reload());
  panel.append(code, title, message, detail, reload);
  main.append(panel);
  root.append(main);
}

try {
  // A production service worker left on the dev origin can mix cached HTML
  // with freshly-built modules. Remove it before loading the dashboard.
  if ("serviceWorker" in navigator && import.meta.env.DEV) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map(registration => registration.unregister()));
    if ("caches" in window) {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter(key => key.startsWith("finpilot-shell-"))
          .map(key => caches.delete(key))
      );
    }
  }

  await import("../data.jsx");
  await import("../components.jsx");
  await import("../views.jsx");
  await import("../explainer.jsx");
  await import("../mc_panel.jsx");
  await import("../journal_panel.jsx");
  await import("../system_panel.jsx");
  await import("../quant_panel.jsx");
  await import("../stock_panel.jsx");
  await import("../news_panel.jsx");
  await import("../app.jsx");

  if ("serviceWorker" in navigator && import.meta.env.PROD) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
  }
} catch (error) {
  console.error("FinPilot startup failed", error);
  showBootFailure(error);
}
