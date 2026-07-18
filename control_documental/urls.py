from django.urls import path
from . import views

urlpatterns = [
    path('documentos/', views.lista, name='documentos_lista'),
]