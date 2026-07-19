from django.urls import path
from . import views

urlpatterns = [
    path('documentos/', views.documentos_cit, name='documentos_lista'),
    path('documentos/cit/', views.documentos_cit, name='documentos_cit'),
    path('documentos/ocultar/<int:pk>/', views.ocultar_documento, name='ocultar_documento'),
    path('documentos/cambiar_estado/<int:pk>/', views.cambiar_estado_documento, name='cambiar_estado_documento'),
]