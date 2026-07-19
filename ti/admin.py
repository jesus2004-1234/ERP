from django.contrib import admin
from .models import Empleado, Equipo, Asignacion, Mantenimiento, Correos, Consumible


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'apellido', 'departamento')
    list_filter   = ('departamento',)
    search_fields = ('nombre', 'apellido')


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display  = ('tipo', 'marca', 'modelo', 'numero_serie', 'estatus',)
    list_filter   = ('tipo', 'estatus',)
    search_fields = ('marca', 'modelo', 'numero_serie')


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display  = ('equipo', 'empleado', 'fecha_asignacion', 'fecha_devolucion', 'estatus')
    list_filter   = ('estatus',)
    search_fields = ('equipo__marca', 'equipo__modelo', 'empleado__nombre', 'empleado__apellido')


@admin.register(Mantenimiento)
class MantenimientoAdmin(admin.ModelAdmin):
    list_display  = ('equipo', 'tipo', 'proxima_fecha_mantenimiento', 'realizado_por')
    list_filter   = ('tipo',)
    search_fields = ('equipo__marca', 'equipo__modelo')


@admin.register(Correos)
class CorreosAdmin(admin.ModelAdmin):
    list_display  = ('correo_asignado', 'empleado', 'fecha_asignacion', 'estatus')
    list_filter   = ('estatus',)
    search_fields = ('correo_asignado', 'empleado__nombre', 'empleado__apellido')


@admin.register(Consumible)
class ConsumibleAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'categoria', 'stock_actual', 'unidad_medida')
    list_filter   = ('categoria',)
    search_fields = ('nombre', 'descripcion')

