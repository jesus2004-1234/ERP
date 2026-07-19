from django.urls import path
from . import views

urlpatterns = [
    path('documentos/', views.lista, name='documentos_lista'),
    path('documentos/cit/', views.documentos_cit, name='documentos_cit'),
]