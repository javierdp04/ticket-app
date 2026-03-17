document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector(".purchase-form");
    if (!form) return;

    form.addEventListener("submit", function () {
        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = "Procesando...";
    });
});
