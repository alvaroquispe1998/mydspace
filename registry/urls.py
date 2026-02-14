from django.urls import path

from registry.views import (
    groups_create_view,
    groups_detail_view,
    groups_list_view,
    groups_submit_view,
    records_approve_view,
    records_create_view,
    records_detail_view,
    records_edit_view,
    records_list_view,
    records_mark_ready_view,
    records_observe_view,
    records_resubmit_view,
    records_submit_view,
    records_unready_view,
    records_delete_file_view,
    records_upload_file_view,
)

app_name = "registry"

urlpatterns = [
    path("", records_list_view, name="records_list"),
    path("groups/", groups_list_view, name="groups_list"),
    path("groups/new/", groups_create_view, name="groups_create"),
    path("groups/<int:group_id>/", groups_detail_view, name="groups_detail"),
    path("groups/<int:group_id>/submit/", groups_submit_view, name="groups_submit"),
    path("new/", records_create_view, name="records_create"),
    path("<int:record_id>/", records_detail_view, name="records_detail"),
    path("<int:record_id>/edit/", records_edit_view, name="records_edit"),
    path("<int:record_id>/ready/", records_mark_ready_view, name="records_mark_ready"),
    path("<int:record_id>/unready/", records_unready_view, name="records_unready"),
    path("<int:record_id>/submit/", records_submit_view, name="records_submit"),
    path("<int:record_id>/resubmit/", records_resubmit_view, name="records_resubmit"),
    path("<int:record_id>/observe/", records_observe_view, name="records_observe"),
    path("<int:record_id>/approve/", records_approve_view, name="records_approve"),
    path("<int:record_id>/files/", records_upload_file_view, name="records_upload_file"),
    path("<int:record_id>/files/<int:file_id>/delete/", records_delete_file_view, name="records_delete_file"),
]
