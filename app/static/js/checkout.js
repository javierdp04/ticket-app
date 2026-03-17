document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector(".purchase-form");
    if (!form) return;

    const quantityInputs = document.querySelectorAll(".quantity-input");
    const attendeesContainer = document.getElementById("attendees-container");
    const emailInput = document.getElementById("buyer_email");
    const emailConfirmInput = document.getElementById("buyer_email_confirm");
    const emailError = document.getElementById("email-error");

    function getTotalQuantity() {
        let total = 0;
        quantityInputs.forEach(function (input) {
            total += parseInt(input.value) || 0;
        });
        return total;
    }

    function updateAttendeeFields() {
        const qty = getTotalQuantity();
        attendeesContainer.innerHTML = "";

        for (let i = 1; i <= qty; i++) {
            const row = document.createElement("div");
            row.className = "form-group attendee-row";
            row.innerHTML =
                '<div class="attendee-field">' +
                    '<label for="attendee_first_name_' + i + '">Nombre del asistente ' + i + '</label>' +
                    '<input type="text" id="attendee_first_name_' + i + '" name="attendee_first_name_' + i + '" required>' +
                '</div>' +
                '<div class="attendee-field">' +
                    '<label for="attendee_last_name_' + i + '">Apellidos del asistente ' + i + '</label>' +
                    '<input type="text" id="attendee_last_name_' + i + '" name="attendee_last_name_' + i + '" required>' +
                '</div>';
            attendeesContainer.appendChild(row);
        }
    }

    updateAttendeeFields();
    quantityInputs.forEach(function (input) {
        input.addEventListener("change", updateAttendeeFields);
        input.addEventListener("input", updateAttendeeFields);
    });

    form.addEventListener("submit", function (e) {
        if (getTotalQuantity() < 1) {
            e.preventDefault();
            alert("Selecciona al menos una entrada");
            return;
        }

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
