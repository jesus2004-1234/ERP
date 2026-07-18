from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from ti import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include   

urlpatterns = [
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/admin/login/'), name='admin_logout'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='ti/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('empleados/', views.empleados_lista, name='empleados_lista'),
    path('empleados/crear/', views.empleado_crear, name='empleado_crear'),
    path('empleados/<int:pk>/editar/', views.empleado_editar, name='empleado_editar'),
    path('empleados/<int:pk>/eliminar/', views.empleado_eliminar, name='empleado_eliminar'),
    path('equipos/', views.equipos_lista, name='equipos_lista'),
    path('equipos/crear/', views.equipo_crear, name='equipo_crear'),
    path('equipos/<int:pk>/editar/', views.equipo_editar, name='equipo_editar'),
    path('equipos/<int:pk>/eliminar/', views.equipo_eliminar, name='equipo_eliminar'),
    path('asignaciones/', views.asignaciones_lista, name='asignaciones_lista'),
    path('asignaciones/crear/', views.asignacion_crear, name='asignacion_crear'),
    path('asignaciones/<int:pk>/editar/', views.asignacion_editar, name='asignacion_editar'),
    path('asignaciones/<int:pk>/eliminar/', views.asignacion_eliminar, name='asignacion_eliminar'),
    path('mantenimientos/', views.mantenimientos_lista, name='mantenimientos_lista'),
    path('mantenimientos/crear/', views.mantenimiento_crear, name='mantenimiento_crear'),
    path('mantenimientos/<int:pk>/editar/', views.mantenimiento_editar, name='mantenimiento_editar'),
    path('mantenimientos/<int:pk>/eliminar/', views.mantenimiento_eliminar, name='mantenimiento_eliminar'),
    path('correos/', views.correos_lista, name='correos_lista'),
    path('correos/crear/', views.correo_crear, name='correo_crear'),
    path('correos/<int:pk>/editar/', views.correo_editar, name='correo_editar'),
    path('correos/<int:pk>/eliminar/', views.correo_eliminar, name='correo_eliminar'),
    path('consumibles/', views.consumibles_lista, name='consumibles_lista'),
    path('consumibles/crear/', views.consumible_crear, name='consumible_crear'),
    path('consumibles/<int:pk>/editar/', views.consumible_editar, name='consumible_editar'),
    path('consumibles/<int:pk>/eliminar/', views.consumible_eliminar, name='consumible_eliminar'),
    path('tickets/', views.tickets_lista, name='tickets_lista'),

   
]
