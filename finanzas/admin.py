from django.contrib import admin
from django.utils.html import format_html

from .models import Expediente, ExpedienteDocumento, FacturaCliente, PagoCliente, FacturaProveedor, PagoProveedor


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "tipo_contribuyente",
        "razon_social",
        "estatus",
        "fecha_alta",
    )
    list_filter = ("tipo", "tipo_contribuyente", "estatus")
    search_fields = ("razon_social", "nombre_comercial", "rfc", "contacto_nombre")


@admin.register(ExpedienteDocumento)
class ExpedienteDocumentoAdmin(admin.ModelAdmin):
    list_display = ("expediente", "categoria", "fecha_subida")
    list_filter = ("categoria", "fecha_subida")
    search_fields = ("expediente__razon_social", "expediente__rfc")
    autocomplete_fields = ("expediente",)
    ordering = ("-fecha_subida",)


class PagoClienteInline(admin.TabularInline):
    model = PagoCliente
    extra = 0


@admin.register(FacturaCliente)
class FacturaClienteAdmin(admin.ModelAdmin):

    list_display = (
        "factura",
        "expediente",
        "fecha_factura",
        "fecha_vencimiento",
        "total",
        "total_pagado",
        "saldo_pendiente",
        "estatus_coloreado",
    )
    list_filter = ("estatus", "fecha_factura", "fecha_vencimiento")
    search_fields = (
        "factura",
        "expediente__razon_social",
        "expediente__nombres",
        "expediente__apellido_paterno",
        "expediente__rfc",
    )
    date_hierarchy = "fecha_factura"
    readonly_fields = ("monto_comision", "total_pagado", "saldo_pendiente", "fecha_registro")
    inlines = [PagoClienteInline]  # noqa: RUF012

    def get_queryset(self, request):
        # total_pagado y saldo_pendiente son @property que iteran self.pagos.all():
        # sin prefetch_related, cada fila del listado dispara una query adicional (N+1).
        return (
            super()
            .get_queryset(request)
            .select_related("expediente")
            .prefetch_related("pagos")
        )

    def estatus_coloreado(self, obj):
        colores = {
            "Pendiente": "orange",
            "Parcial": "blue",
            "Pagada": "green",
            "Cancelada": "gray",
        }
        color = colores.get(obj.estatus, "black")
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, obj.estatus)
    estatus_coloreado.short_description = "Estatus"


@admin.register(PagoCliente)
class PagoClienteAdmin(admin.ModelAdmin):
    list_select_related = ("factura", "factura__expediente",)
    list_display = ("factura", "fecha_pago", "monto", "metodo_pago")
    list_filter = ("metodo_pago", "fecha_pago")
    search_fields = (
        "factura__factura",
        "factura__expediente__razon_social",
        "factura__expediente__rfc",
        "referencia",
    )


class PagoProveedorInline(admin.TabularInline):
    model = PagoProveedor
    extra = 0
    fields = ("fecha_pago", "fecha_deposito", "monto", "metodo_pago", "referencia")
    readonly_fields = ("fecha_registro",)


@admin.register(FacturaProveedor)
class FacturaProveedorAdmin(admin.ModelAdmin):

    list_display = (
        "factura",
        "orden_compra",
        "expediente",
        "fecha_factura",
        "fecha_vencimiento",
        "total",
        "moneda",
        "estatus_coloreado",
    )
    list_filter = ("estatus", "moneda")
    search_fields = ("factura", "expediente__razon_social", "expediente__rfc", "orden_compra")
    date_hierarchy = "fecha_factura"
    readonly_fields = ("fecha_registro",)
    inlines = [PagoProveedorInline]

    def get_queryset(self, request):
        # Mismo motivo que en FacturaClienteAdmin: si en el futuro se agrega
        # total_pagado/saldo_pendiente a list_display aquí también, ya queda
        # cubierto sin necesidad de tocar esto de nuevo.
        return (
            super()
            .get_queryset(request)
            .select_related("expediente")
            .prefetch_related("pagos")
        )

    def estatus_coloreado(self, obj):
        colores = {
            "Pendiente": "orange",
            "Parcial": "blue",
            "Pagada": "green",
            "Cancelada": "gray",
        }
        color = colores.get(obj.estatus, "black")
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, obj.estatus)
    estatus_coloreado.short_description = "Estatus"


@admin.register(PagoProveedor)
class PagoProveedorAdmin(admin.ModelAdmin):
    list_display = ("factura", "fecha_pago", "monto", "metodo_pago", "referencia")
    list_filter = ("metodo_pago",)
    search_fields = ("factura__factura", "referencia", "factura__expediente__razon_social")
    date_hierarchy = "fecha_pago"
    readonly_fields = ("fecha_registro",)