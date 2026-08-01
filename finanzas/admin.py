from django.contrib import admin

from .models import Expediente, ExpedienteDocumento, FacturaCliente, PagoCliente


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
class ExpendienteDocumentoAdmin(admin.ModelAdmin):
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
    list_select_related = ("expediente",)

    list_display = (
        "factura",
        "expediente",
        "fecha_factura",
        "fecha_vencimiento",
        "total",
        "total_pagado",
        "saldo_pendiente",
        "estatus",
    )
    list_filter = ("estatus", "fecha_factura", "fecha_vencimiento")
    search_fields = (
        "factura",
        "expediente__razon_social",
        "expediente__nombres",
        "expediente__apellido_paterno",
        "expediente__rfc",
    )
    readonly_fields = ("monto_comision", "total_pagado", "saldo_pendiente")
    inlines = [PagoClienteInline]  # noqa: RUF012


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
