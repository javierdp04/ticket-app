from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

from app.services import event_service, ticket_service

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == current_app.config["ADMIN_PASSWORD"]:
            session["admin_authenticated"] = True
            return redirect(url_for("admin.dashboard"))
        return render_template("admin/login.html", error="Contrasena incorrecta")
    return render_template("admin/login.html")


@admin_bp.route("/admin/logout")
def logout():
    session.pop("admin_authenticated", None)
    return redirect(url_for("main.index"))


@admin_bp.route("/admin")
@admin_required
def dashboard():
    events = event_service.get_all_events()
    return render_template("admin/dashboard.html", events=events)


@admin_bp.route("/admin/event/new")
@admin_required
def new_event():
    return render_template("admin/event_form.html", event=None)


@admin_bp.route("/admin/event/create", methods=["POST"])
@admin_required
def create_event():
    data = {
        "name": request.form.get("name"),
        "description": request.form.get("description", ""),
        "date": request.form.get("date"),
        "venue": request.form.get("venue"),
        "price": request.form.get("price"),
        "currency": request.form.get("currency", "eur"),
        "max_tickets": request.form.get("max_tickets"),
    }
    event_service.create_event(data)
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/admin/event/<event_id>")
@admin_required
def event_detail(event_id):
    event = event_service.get_event(event_id)
    if not event:
        return "Evento no encontrado", 404
    stats = ticket_service.get_event_stats(event_id)
    recent = ticket_service.get_recent_purchases(event_id)
    available = event_service.get_available_tickets(event_id)
    return render_template(
        "admin/event_detail.html",
        event=event,
        stats=stats,
        recent=recent,
        available=available,
    )


@admin_bp.route("/admin/event/<event_id>/edit")
@admin_required
def edit_event(event_id):
    event = event_service.get_event(event_id)
    if not event:
        return "Evento no encontrado", 404
    return render_template("admin/event_form.html", event=event)


@admin_bp.route("/admin/event/<event_id>/update", methods=["POST"])
@admin_required
def update_event(event_id):
    data = {
        "name": request.form.get("name"),
        "description": request.form.get("description", ""),
        "date": request.form.get("date"),
        "venue": request.form.get("venue"),
        "price": request.form.get("price"),
        "currency": request.form.get("currency", "eur"),
        "max_tickets": request.form.get("max_tickets"),
    }
    event_service.update_event(event_id, data)
    return redirect(url_for("admin.event_detail", event_id=event_id))


@admin_bp.route("/admin/event/<event_id>/status", methods=["POST"])
@admin_required
def change_status(event_id):
    new_status = request.form.get("status")
    event_service.change_status(event_id, new_status)
    return redirect(url_for("admin.dashboard"))
