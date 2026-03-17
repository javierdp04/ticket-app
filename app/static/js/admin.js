document.addEventListener("DOMContentLoaded", function () {
    // Confirmacion antes de cambiar estado de evento
    const statusForms = document.querySelectorAll('form[action*="/status"]');
    statusForms.forEach(function (form) {
        form.addEventListener("submit", function (e) {
            const status = form.querySelector('input[name="status"]').value;
            if (status === "finished") {
                if (!confirm("Estas seguro de que quieres finalizar este evento?")) {
                    e.preventDefault();
                }
            }
        });
    });
});
