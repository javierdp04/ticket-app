from app import create_app

app = create_app()

if __name__ == "__main__":
    # Solo para desarrollo local. En produccion usar Gunicorn:
    # gunicorn run:app --workers 4 --bind 127.0.0.1:8000
    app.run(debug=True, host="127.0.0.1", port=5000)
