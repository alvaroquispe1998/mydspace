from django.urls import path

from saf.views import (
    batches_create_from_group_view,
    batches_detail_view,
    batches_download_view,
    batches_generate_view,
    batches_list_view,
    batches_scripts_view,
    batches_upload_links_view,
)

app_name = "saf"

urlpatterns = [
    path("batches/", batches_list_view, name="batches_list"),
    path("groups/<int:group_id>/batches/new/", batches_create_from_group_view, name="batches_create_from_group"),
    path("batches/<int:batch_id>/", batches_detail_view, name="batches_detail"),
    path("batches/<int:batch_id>/generate/", batches_generate_view, name="batches_generate"),
    path("batches/<int:batch_id>/download/", batches_download_view, name="batches_download"),
    path("batches/<int:batch_id>/scripts/", batches_scripts_view, name="batches_scripts"),
    path("batches/<int:batch_id>/links/", batches_upload_links_view, name="batches_upload_links"),
]
