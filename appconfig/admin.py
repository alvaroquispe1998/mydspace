from django.contrib import admin
from appconfig.models import CareerConfig, LicenseVersion, SystemConfig


@admin.register(CareerConfig)
class CareerConfigAdmin(admin.ModelAdmin):
    list_display = ("carrera_excel", "carrera_norm", "handle", "active")
    search_fields = ("carrera_excel", "carrera_norm", "handle")
    list_filter = ("active",)


@admin.register(LicenseVersion)
class LicenseVersionAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "version")


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "value")

# Register your models here.
