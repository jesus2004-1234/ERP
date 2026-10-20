from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from . import views

urlpatterns = [
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/admin/login/'), name='admin_logout'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('control_documental/', include('control_documental.urls')),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('finanzas/', include('finanzas.urls')),
    path('ti/', include('ti.urls')),
    # Archivos subidos: siempre con login y permiso por módulo (también en desarrollo).
    re_path(r'^media/(?P<ruta>.+)$', views.media_protegida, name='media_protegida'),
]
