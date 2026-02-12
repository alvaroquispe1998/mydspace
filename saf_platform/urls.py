from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from accounts.views import dashboard_view
from accounts import views as account_views

urlpatterns = [
    path("admin/users/", account_views.users_list_view, name="admin_users_list"),
    path("admin/users/new/", account_views.users_create_view, name="admin_users_create"),
    path("admin/users/<int:user_id>/edit/", account_views.users_edit_view, name="admin_users_edit"),
    # Ensure admin logout redirects to our custom login instead of showing Django admin "logged out" page.
    path("admin/logout/", account_views.logout_view, name="admin_logout"),
    path('admin/', admin.site.urls),
    path("", dashboard_view, name="dashboard"),
    path("auth/", include("accounts.urls")),
    path("records/", include("registry.urls")),
    path("config/", include("appconfig.urls")),
    path("saf/", include("saf.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
