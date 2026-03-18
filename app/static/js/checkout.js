document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector(".purchase-form");
    if (!form) return;

    const quantityInputs = document.querySelectorAll(".quantity-input");
    const attendeesContainer = document.getElementById("attendees-container");
    const reusableCodesContainer = document.getElementById("reusable-codes-container");
    const emailInput = document.getElementById("buyer_email");
    const emailConfirmInput = document.getElementById("buyer_email_confirm");
    const emailError = document.getElementById("email-error");
    const checkoutError = document.getElementById("checkout-error");

    function getTotalQuantity() {
        let total = 0;
        quantityInputs.forEach(function (input) {
            total += parseInt(input.value) || 0;
        });
        return total;
    }

    function updateDynamicFields() {
        attendeesContainer.innerHTML = "";
        reusableCodesContainer.innerHTML = "";
        if (checkoutError) checkoutError.style.display = "none";

        let attendeeIdx = 1;

        quantityInputs.forEach(function (input) {
            var typeQty = parseInt(input.value) || 0;
            if (typeQty < 1) return;

            var typeId = input.getAttribute("data-requires-code");
            var isReusable = input.getAttribute("data-code-reusable") === "true";
            var typeName = input.closest(".ticket-type-select").querySelector("strong").textContent;

            // Reusable code: single field above buyer name
            if (typeId && isReusable) {
                var codeDiv = document.createElement("div");
                codeDiv.className = "form-group";
                codeDiv.innerHTML =
                    '<label>Codigo de acceso — ' + typeName + '</label>' +
                    '<input type="text" name="access_code_' + typeId + '" placeholder="Introduce tu codigo" required>';
                reusableCodesContainer.appendChild(codeDiv);
            }

            for (var j = 0; j < typeQty; j++) {
                var row = document.createElement("div");
                row.className = "form-group attendee-row";

                var html =
                    '<div class="attendee-field">' +
                        '<label for="attendee_first_name_' + attendeeIdx + '">Nombre del asistente ' + attendeeIdx + '</label>' +
                        '<input type="text" id="attendee_first_name_' + attendeeIdx + '" name="attendee_first_name_' + attendeeIdx + '" required>' +
                    '</div>' +
                    '<div class="attendee-field">' +
                        '<label for="attendee_last_name_' + attendeeIdx + '">Apellidos del asistente ' + attendeeIdx + '</label>' +
                        '<input type="text" id="attendee_last_name_' + attendeeIdx + '" name="attendee_last_name_' + attendeeIdx + '" required>' +
                    '</div>';

                // Non-reusable code: one field per attendee of this type
                if (typeId && !isReusable) {
                    html +=
                        '<div class="attendee-field">' +
                            '<label>Codigo de acceso</label>' +
                            '<input type="text" name="access_code_' + typeId + '[]" placeholder="Tu codigo" required>' +
                        '</div>';
                }

                row.innerHTML = html;
                attendeesContainer.appendChild(row);
                attendeeIdx++;
            }
        });
    }

    updateDynamicFields();
    quantityInputs.forEach(function (input) {
        input.addEventListener("change", updateDynamicFields);
        input.addEventListener("input", updateDynamicFields);
    });

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (checkoutError) checkoutError.style.display = "none";

        if (getTotalQuantity() < 1) {
            alert("Selecciona al menos una entrada");
            return;
        }

        if (emailInput.value !== emailConfirmInput.value) {
            emailError.style.display = "block";
            emailConfirmInput.focus();
            return;
        }
        emailError.style.display = "none";

        var btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = "Procesando...";

        var formData = new FormData(form);

        fetch(form.action, {
            method: "POST",
            body: formData,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then(function (response) {
            var ct = response.headers.get("content-type") || "";
            if (ct.indexOf("application/json") !== -1) {
                return response.json().then(function (data) {
                    if (!response.ok) throw new Error(data.error || "Error desconocido");
                    return data;
                });
            }
            return response.text().then(function (text) {
                if (!response.ok) throw new Error(text || "Error desconocido");
                return {};
            });
        })
        .then(function (data) {
            if (data.redirect) {
                window.location.href = data.redirect;
            }
        })
        .catch(function (err) {
            if (checkoutError) {
                checkoutError.textContent = err.message;
                checkoutError.style.display = "block";
            }
            btn.disabled = false;
            btn.textContent = "Comprar";
        });
    });

    emailConfirmInput.addEventListener("input", function () {
        if (emailInput.value === emailConfirmInput.value) {
            emailError.style.display = "none";
        }
    });
});
