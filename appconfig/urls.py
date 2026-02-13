from django.urls import path

from appconfig.views import (
    advisors_create_view,
    advisors_edit_view,
    advisors_list_view,
    careers_create_view,
    careers_edit_view,
    careers_list_view,
    jurors_create_view,
    jurors_edit_view,
    jurors_list_view,
    licenses_activate_view,
    licenses_create_view,
    licenses_edit_view,
    licenses_list_view,
    params_create_view,
    params_edit_view,
    params_list_view,
)

app_name = "appconfig"

urlpatterns = [
    path("careers/", careers_list_view, name="careers_list"),
    path("careers/new/", careers_create_view, name="careers_create"),
    path("careers/<int:career_id>/edit/", careers_edit_view, name="careers_edit"),
    path("advisors/", advisors_list_view, name="advisors_list"),
    path("advisors/new/", advisors_create_view, name="advisors_create"),
    path("advisors/<int:advisor_id>/edit/", advisors_edit_view, name="advisors_edit"),
    path("jurors/", jurors_list_view, name="jurors_list"),
    path("jurors/new/", jurors_create_view, name="jurors_create"),
    path("jurors/<int:juror_id>/edit/", jurors_edit_view, name="jurors_edit"),
    path("licenses/", licenses_list_view, name="licenses_list"),
    path("licenses/new/", licenses_create_view, name="licenses_create"),
    path("licenses/<int:license_id>/edit/", licenses_edit_view, name="licenses_edit"),
    path("licenses/<int:license_id>/activate/", licenses_activate_view, name="licenses_activate"),
    path("params/", params_list_view, name="params_list"),
    path("params/new/", params_create_view, name="params_create"),
    path("params/<int:param_id>/edit/", params_edit_view, name="params_edit"),
]
