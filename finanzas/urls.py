from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="finanzas_dashboard"),
    path("expedientes/", views.expedientes_lista, name="expedientes_lista"),
    path("expedientes/crear/", views.expediente_crear, name="expediente_crear"),
    path("expedientes/<int:pk>/detalle/", views.expediente_detalle, name="expediente_detalle"),
    path("expedientes/<int:pk>/editar/", views.expediente_editar, name="expediente_editar"),
    path("expedientes/<int:pk>/eliminar/", views.expediente_eliminar, name="expediente_eliminar"),
    path("expedientes/<int:pk>/documentos/subir/", views.expediente_documento_subir, name="expediente_documento_subir"),
    path("expedientes/documentos/<int:pk>/eliminar/", views.expediente_documento_eliminar, name="expediente_documento_eliminar"),
    path("cxc/", views.facturas_lista, name="facturas_lista"),
    path("cxc/crear/", views.factura_crear, name="factura_crear"),
    path("cxc/<int:pk>/detalle/", views.factura_detalle, name="factura_detalle"),
    path("cxc/<int:pk>/registrar_pago/", views.registrar_pago, name="registrar_pago"),
    path("cxc/<int:pk>/editar/", views.factura_editar, name="factura_editar"),
    path("cxc/<int:pk>/cancelar/", views.factura_cancelar, name="factura_cancelar"),
    path("cxc/pagos/<int:pk>/eliminar/", views.pago_eliminar, name="pago_eliminar"),
    path("cxc/pagos/<int:pk>/editar/", views.pago_editar, name="pago_editar"),
    path("cxp/", views.facturas_proveedor_lista, name="facturas_proveedor_lista"),
    path("cxp/crear/", views.factura_proveedor_crear, name="factura_proveedor_crear"),
    path("cxp/<int:pk>/detalle/", views.factura_proveedor_detalle, name="factura_proveedor_detalle"),
    path("cxp/<int:pk>/editar/", views.factura_proveedor_editar, name="factura_proveedor_editar"),
    path("cxp/<int:pk>/cancelar/", views.factura_proveedor_cancelar, name="factura_proveedor_cancelar"),
    path("cxp/<int:pk>/registrar_pago/", views.registrar_proveedor_pago, name="registrar_proveedor_pago"),
    path("cxp/<int:pk>/pago_editar/", views.pago_proveedor_editar, name="pago_proveedor_editar"),
    path("cxp/<int:pk>/pago_eliminar/", views.pago_proveedor_eliminar, name="pago_proveedor_eliminar"),
]
