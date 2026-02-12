from django.contrib import admin
from saf.models import SafBatch, SafBatchItem


class SafBatchItemInline(admin.TabularInline):
    model = SafBatchItem
    extra = 0
    readonly_fields = ("record", "item_folder_name", "result", "detail")


@admin.register(SafBatch)
class SafBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_code", "status", "created_by", "generated_at", "created_at")
    list_filter = ("status",)
    search_fields = ("batch_code", "created_by__username")
    inlines = [SafBatchItemInline]


@admin.register(SafBatchItem)
class SafBatchItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "record", "result", "item_folder_name")
    list_filter = ("result",)

# Register your models here.
