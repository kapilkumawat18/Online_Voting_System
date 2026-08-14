/* SecureVote V2 — Sprint 5 UX helpers */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-loading-link]").forEach(link => {
    link.addEventListener("click", () => {
      link.setAttribute("aria-busy", "true");
      link.style.pointerEvents = "none";
    });
  });
});
