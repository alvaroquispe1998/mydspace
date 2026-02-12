from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required
from accounts.forms import LoginForm, UserUpsertForm

User = get_user_model()


class UserLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    # Force redirect to our login page after logout (also avoids Django's default logged_out template).
    next_page = "accounts:login"
    http_method_names = ["get", "post", "options"]


@require_http_methods(["GET", "POST"])
def logout_view(request):
    # Always redirect to the custom login page. This avoids Django admin's logged_out template
    # being picked up when logout is accessed directly.
    auth_logout(request)
    return redirect("accounts:login")


@login_required
def dashboard_view(request):
    from registry.models import ThesisRecord

    status_counts = {s["status"]: s["count"] for s in ThesisRecord.objects.values("status").annotate(count=models.Count("id"))}
    status_label_map = {code: label for code, label in ThesisRecord.STATUS_CHOICES}
    status_rows = [
        {"status": code, "label": status_label_map.get(code, code), "count": int(status_counts.get(code, 0))}
        for code, _label in ThesisRecord.STATUS_CHOICES
    ]

    recent_records = (
        ThesisRecord.objects.select_related("career")
        .order_by("-updated_at", "-id")[:10]
    )
    pending_records = (
        ThesisRecord.objects.select_related("career")
        .filter(status=ThesisRecord.STATUS_EN_AUDITORIA)
        .order_by("nro")[:10]
    )
    context = {
        "status_rows": status_rows,
        "total_records": ThesisRecord.objects.count(),
        "pending_audit": ThesisRecord.objects.filter(status=ThesisRecord.STATUS_EN_AUDITORIA).count(),
        "recent_records": recent_records,
        "pending_records": pending_records,
    }
    return render(request, "dashboard.html", context)


@role_required(User.ROLE_AUDITOR)
def users_list_view(request):
    users = User.objects.order_by("-is_active", "username")
    return render(request, "accounts/users_list.html", {"users": users})


@role_required(User.ROLE_AUDITOR)
def users_create_view(request):
    if request.method == "POST":
        form = UserUpsertForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            if not form.cleaned_data.get("password"):
                form.add_error("password", "Debes definir contraseña para usuario nuevo.")
            else:
                user.set_password(form.cleaned_data["password"])
                user.save()
                messages.success(request, f"Usuario {user.username} creado.")
                return redirect("accounts:users_list")
    else:
        form = UserUpsertForm()
    return render(request, "accounts/user_form.html", {"form": form, "title": "Crear usuario"})


@role_required(User.ROLE_AUDITOR)
def users_edit_view(request, user_id: int):
    target = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        form = UserUpsertForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, f"Usuario {target.username} actualizado.")
            return redirect("accounts:users_list")
    else:
        form = UserUpsertForm(instance=target)
    return render(request, "accounts/user_form.html", {"form": form, "title": "Editar usuario", "target": target})

# Create your views here.
