from django.contrib import admin
from .models import Documento

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'estado')
    list_filter = ('categoria', 'estado')
    search_fields = ('codigo', 'nombre')
# Register your models here.
