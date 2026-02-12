from django.urls import path

from saf.views import (
    approved_records_view,
    batches_create_view,
    batches_detail_view,
    batches_download_view,
    batches_generate_view,
    batches_list_view,
)

app_name = "saf"

urlpatterns = [
    path("batches/", batches_list_view, name="batches_list"),
    path("batches/new/", batches_create_view, name="batches_create"),
    path("batches/<int:batch_id>/", batches_detail_view, name="batches_detail"),
    path("batches/<int:batch_id>/generate/", batches_generate_view, name="batches_generate"),
    path("batches/<int:batch_id>/download/", batches_download_view, name="batches_download"),
    path("approved/", approved_records_view, name="approved_records"),
]
