document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector(".purchase-form");
    if (!form) return;

    const quantityInput = document.getElementById("quantity");
    const attendeesContainer = document.getElementById("attendees-container");
    const emailInput = document.getElementById("buyer_email");
    const emailConfirmInput = document.getElementById("buyer_email_confirm");
    const emailError = document.getElementById("email-error");

    function updateAttendeeFields() {
        const qty = parseInt(quantityInput.value) || 1;
        attendeesContainer.innerHTML = "";

        if (qty > 1) {
            for (let i = 1; i <= qty; i++) {
                const div = document.createElement("div");
                div.className = "form-group";
                div.innerHTML =
                    '<label for="attendee_name_' + i + '">Nombre del asistente ' + i + '</label>' +
                    '<input type="text" id="attendee_name_' + i + '" name="attendee_name_' + i + '" required>';
                attendeesContainer.appendChild(div);
            }
        }
    }

    quantityInput.addEventListener("change", updateAttendeeFields);
    quantityInput.addEventListener("input", updateAttendeeFields);

    form.addEventListener("submit", function (e) {
        if (emailInput.value !== emailConfirmInput.value) {
            e.preventDefault();
            emailError.style.display = "block";
            emailConfirmInput.focus();
            return;
        }
        emailError.style.display = "none";

        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = "Procesando...";
    });

    emailConfirmInput.addEventListener("input", function () {
        if (emailInput.value === emailConfirmInput.value) {
            emailError.style.display = "none";
        }
    });
});
