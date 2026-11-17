// Small helpers: show a "working" state on slow forms and confirm destructive actions.
document.addEventListener("submit", function (e) {
  var form = e.target;
  var confirmText = form.getAttribute("data-confirm");
  if (confirmText && !window.confirm(confirmText)) { e.preventDefault(); return; }
  if (form.hasAttribute("data-busy")) {
    form.classList.add("is-busy");
    var btn = form.querySelector("button[type=submit], button:not([type])");
    if (btn) { btn.disabled = true; btn.dataset.label = btn.textContent; btn.textContent = form.getAttribute("data-busy") || "Working..."; }
  }
});
