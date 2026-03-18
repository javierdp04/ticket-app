from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = app.config.get("DEBUG", False)
    # En produccion usar Gunicorn + Nginx con certificado real (Let's Encrypt)
    app.run(
        debug=debug,
        host="0.0.0.0",
        port=5000,
        ssl_context="adhoc" if debug else None,
    )
