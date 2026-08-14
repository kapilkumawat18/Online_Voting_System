
/* SecureVote V2 — Sprint 7 release QA helpers */
(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.classList.add("sv-ready");

    document.querySelectorAll("form").forEach(form => {
      form.addEventListener("submit", () => {
        const submit = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!submit || submit.dataset.noLock === "true") return;
        if (form.dataset.submitted === "true") return;
        form.dataset.submitted = "true";
        submit.classList.add("sv-loading");
        submit.setAttribute("aria-busy", "true");
      });
    });

    document.querySelectorAll("a[data-loading-link]").forEach(link => {
      link.addEventListener("click", () => {
        link.classList.add("sv-loading");
        link.setAttribute("aria-busy", "true");
      });
    });

    // Prevent accidental double activation on common action buttons.
    document.querySelectorAll("[data-single-action]").forEach(button => {
      button.addEventListener("click", () => {
        if (button.dataset.locked === "true") return;
        button.dataset.locked = "true";
        window.setTimeout(() => { button.dataset.locked = "false"; }, 1200);
      });
    });
  });
})();
