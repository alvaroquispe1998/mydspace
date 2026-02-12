from django.contrib import admin
from registry.models import AuditEvent, ThesisFile, ThesisRecord


class ThesisFileInline(admin.TabularInline):
    model = ThesisFile
    extra = 0


@admin.register(ThesisRecord)
class ThesisRecordAdmin(admin.ModelAdmin):
    list_display = ("nro", "titulo", "career", "status", "created_at")
    list_filter = ("status", "career")
    search_fields = ("titulo", "autor1_nombre", "autor2_nombre", "autor3_nombre")
    inlines = [ThesisFileInline]


@admin.register(ThesisFile)
class ThesisFileAdmin(admin.ModelAdmin):
    list_display = ("record", "file_type", "original_name", "size_bytes", "created_at")
    list_filter = ("file_type",)
    search_fields = ("original_name", "record__titulo")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("record", "action", "user", "created_at")
    list_filter = ("action",)
    search_fields = ("record__titulo", "comment", "user__username")

# Register your models here.
