from django.urls import path

from accounts.views import (
    UserLoginView,
    logout_view,
    users_create_view,
    users_edit_view,
    users_list_view,
)

app_name = "accounts"

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path("users/", users_list_view, name="users_list"),
    path("users/new/", users_create_view, name="users_create"),
    path("users/<int:user_id>/edit/", users_edit_view, name="users_edit"),
]
