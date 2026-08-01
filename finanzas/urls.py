from django.urls import path

from . import views

urlpatterns = [
    path("expedientes/", views.expedientes_lista, name="expedientes_lista"),
    path("expedientes/crear/", views.expediente_crear, name="expediente_crear"),
    path(
        "expedientes/<int:pk>/detalle/",
        views.expediente_detalle,
        name="expediente_detalle",
    ),
    path(
        "expedientes/<int:pk>/editar/",
        views.expediente_editar,
        name="expediente_editar",
    ),
    path(
        "expedientes/<int:pk>/eliminar/",
        views.expediente_eliminar,
        name="expediente_eliminar",
    ),
    path(
        "expedientes/<int:pk>/documentos/subir/",
        views.expediente_documento_subir,
        name="expediente_documento_subir",
    ),
    path(
        "expedientes/documentos/<int:pk>/eliminar/",
        views.expediente_documento_eliminar,
        name="expediente_documento_eliminar",
    ),
    path("cxc/", views.facturas_lista, name="facturas_lista"),
]
