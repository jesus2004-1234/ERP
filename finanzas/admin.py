from django.contrib import admin
from .models import Expediente, ExpedienteDocumento

@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ('tipo','tipo_contribuyente','razon_social','estatus','fecha_alta')
    list_filter = ('tipo','tipo_contribuyente','estatus')
    search_fields = ('razon_social','nombre_comercial','rfc','contacto_nombre')

@admin.register(ExpedienteDocumento)
class ExpendienteDocumentoAdmin(admin.ModelAdmin):
    list_display = ('expediente','categoria','fecha_subida')
    list_filter = ('categoria','fecha_subida')
    search_fields = ('expediente__razon-social','expediente__rfc')
    autocomplete_fields= ('expediente',)
    ordering = ('-fecha_subida',)