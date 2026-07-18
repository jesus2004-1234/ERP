from django.urls import path
from . import views

urlpatterns = [
    path('documentos/', views.lista, name='documentos_lista'),
    path('documentos/ti/', views.documentos_ti, name='documentos_ti'),
]