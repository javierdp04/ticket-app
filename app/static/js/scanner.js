document.addEventListener("DOMContentLoaded", function () {
    const pinForm = document.getElementById("pin-form");
    const pinInput = document.getElementById("pin-input");
    const pinSubmit = document.getElementById("pin-submit");
    const pinError = document.getElementById("pin-error");
    const scannerContainer = document.getElementById("scanner-container");
    const scanResult = document.getElementById("scan-result");

    // Autenticacion con PIN
    if (pinSubmit) {
        pinSubmit.addEventListener("click", function () {
            const pin = pinInput.value.trim();
            if (!pin) return;

            fetch("/scanner/auth", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ event_id: EVENT_ID, pin: pin }),
            })
                .then((res) => res.json())
                .then((data) => {
                    if (data.success) {
                        pinForm.style.display = "none";
                        scannerContainer.style.display = "block";
                        startScanner();
                    } else {
                        pinError.textContent = data.message || "PIN incorrecto";
                        pinError.style.display = "block";
                    }
                })
                .catch(() => {
                    pinError.textContent = "Error de conexion";
                    pinError.style.display = "block";
                });
        });
    }

    // Si ya esta autenticado, iniciar escaner directamente
    if (scannerContainer && scannerContainer.style.display !== "none") {
        startScanner();
    }

    function startScanner() {
        const html5QrCode = new Html5Qrcode("reader");
        html5QrCode.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 250, height: 250 } },
            onScanSuccess
        );
    }

    function onScanSuccess(decodedText) {
        // Extraer ticket_id de la URL del QR
        const parts = decodedText.split("/");
        const ticketId = parts[parts.length - 1];

        fetch("/scanner/validate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticket_id: ticketId, event_id: EVENT_ID }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.valid) {
                    scanResult.className = "valid";
                    scanResult.textContent = "ENTRADA VALIDA - " + data.buyer_name;
                } else {
                    scanResult.className = "invalid";
                    scanResult.textContent = "NO VALIDA - " + data.reason;
                }
            })
            .catch(() => {
                scanResult.className = "invalid";
                scanResult.textContent = "Error de conexion";
            });
    }
});
