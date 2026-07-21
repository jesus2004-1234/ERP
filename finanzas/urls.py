from django.urls import path
from . import views

urlpatterns = [
    path('expedientes/', views.expedientes_lista, name='expedientes_lista'),
    path('expedientes/crear/', views.expediente_crear, name='expediente_crear'),
    path('expedientes/<int:pk>/editar/', views.expediente_editar, name='expediente_editar'),
    path('expedientes/<int:pk>/eliminar/', views.expediente_eliminar, name='expediente_eliminar'),
]