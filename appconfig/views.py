from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import User
from appconfig.forms import CareerConfigForm, LicenseVersionForm, SystemConfigForm
from appconfig.models import CareerConfig, LicenseVersion, SystemConfig


@role_required(User.ROLE_AUDITOR)
def careers_list_view(request):
    careers = CareerConfig.objects.order_by("carrera_excel")
    return render(request, "config/careers_list.html", {"careers": careers})


@role_required(User.ROLE_AUDITOR)
def careers_create_view(request):
    if request.method == "POST":
        form = CareerConfigForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Carrera creada.")
            return redirect("appconfig:careers_list")
    else:
        form = CareerConfigForm()
    return render(request, "config/career_form.html", {"form": form, "title": "Nueva carrera"})


@role_required(User.ROLE_AUDITOR)
def careers_edit_view(request, career_id: int):
    career = get_object_or_404(CareerConfig, pk=career_id)
    if request.method == "POST":
        form = CareerConfigForm(request.POST, instance=career)
        if form.is_valid():
            form.save()
            messages.success(request, "Carrera actualizada.")
            return redirect("appconfig:careers_list")
    else:
        form = CareerConfigForm(instance=career)
    return render(request, "config/career_form.html", {"form": form, "title": "Editar carrera", "career": career})


@role_required(User.ROLE_AUDITOR)
def licenses_list_view(request):
    licenses = LicenseVersion.objects.order_by("-is_active", "-created_at")
    return render(request, "config/licenses_list.html", {"licenses": licenses})


@role_required(User.ROLE_AUDITOR)
def licenses_create_view(request):
    if request.method == "POST":
        form = LicenseVersionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Licencia guardada.")
            return redirect("appconfig:licenses_list")
    else:
        form = LicenseVersionForm()
    return render(request, "config/license_form.html", {"form": form, "title": "Nueva licencia"})


@role_required(User.ROLE_AUDITOR)
def licenses_edit_view(request, license_id: int):
    target = get_object_or_404(LicenseVersion, pk=license_id)
    if request.method == "POST":
        form = LicenseVersionForm(request.POST, instance=target)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.created_by_id:
                obj.created_by = request.user
            obj.save()
            messages.success(request, "Licencia actualizada.")
            return redirect("appconfig:licenses_list")
    else:
        form = LicenseVersionForm(instance=target)
    return render(request, "config/license_form.html", {"form": form, "title": "Editar licencia", "license_obj": target})


@role_required(User.ROLE_AUDITOR)
def licenses_activate_view(request, license_id: int):
    target = get_object_or_404(LicenseVersion, pk=license_id)
    target.is_active = True
    target.save()
    messages.success(request, f"Licencia activa: {target.name} v{target.version}")
    return redirect("appconfig:licenses_list")


@role_required(User.ROLE_AUDITOR)
def params_list_view(request):
    params = SystemConfig.objects.order_by("key")
    return render(request, "config/params_list.html", {"params": params})


@role_required(User.ROLE_AUDITOR)
def params_create_view(request):
    if request.method == "POST":
        form = SystemConfigForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Parámetro creado.")
            return redirect("appconfig:params_list")
    else:
        form = SystemConfigForm()
    return render(request, "config/param_form.html", {"form": form, "title": "Nuevo parámetro"})


@role_required(User.ROLE_AUDITOR)
def params_edit_view(request, param_id: int):
    target = get_object_or_404(SystemConfig, pk=param_id)
    if request.method == "POST":
        form = SystemConfigForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, "Parámetro actualizado.")
            return redirect("appconfig:params_list")
    else:
        form = SystemConfigForm(instance=target)
    return render(request, "config/param_form.html", {"form": form, "title": "Editar parámetro"})

# Create your views here.
