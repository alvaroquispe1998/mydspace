from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*allowed_roles: str):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "No tienes permisos para realizar esta acción.")
            return redirect("dashboard")

        return _wrapped

    return decorator
