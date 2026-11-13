"""
Formularios del módulo de TI.

Antes las vistas leían request.POST directamente y creaban los registros sin validar:
un número de serie repetido, un stock inválido o un campo faltante terminaban en
error 500, y las listas de opciones (tipo, estatus, departamento...) aceptaban
cualquier texto. Estos formularios validan todo antes de tocar la base de datos.

Los nombres de los campos son los mismos que envían los templates actuales, por lo
que los templates no cambian.
"""
import logging

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from config.uploads import validar_archivo_subido

from .models import Asignacion, Consumible, Correos, Empleado, Equipo, Mantenimiento

logger = logging.getLogger(__name__)

# <input type="date"> envía AAAA-MM-DD; se acepta también DD/MM/AAAA por si se captura a mano.
FORMATOS_FECHA = ['%Y-%m-%d', '%d/%m/%Y']


class FormularioTI(forms.ModelForm):
    """
    Base de los formularios de TI.

    - Fija los formatos de fecha aceptados.
    - Guarda los textos vacíos como '' (no NULL), igual que hacían las vistas, para que
      los templates que muestran el valor tal cual no impriman "None".
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo, forms.DateField):
                campo.input_formats = FORMATOS_FECHA
            elif isinstance(campo, forms.CharField):
                campo.empty_value = ''


class EmpleadoForm(FormularioTI):
    class Meta:
        model = Empleado
        fields = ['nombre', 'apellido', 'departamento']


class EquipoForm(FormularioTI):
    class Meta:
        model = Equipo
        fields = ['tipo', 'marca', 'modelo', 'numero_serie', 'sistema_operativo', 'estatus']
        labels = {
            'numero_serie': 'Número de serie',
            'sistema_operativo': 'Sistema operativo',
        }
        error_messages = {
            'numero_serie': {'unique': 'Ya existe un equipo con ese número de serie.'},
        }


class MantenimientoForm(FormularioTI):
    class Meta:
        model = Mantenimiento
        fields = [
            'equipo', 'tipo', 'descripcion',
            'ultima_fecha_mantenimiento', 'proxima_fecha_mantenimiento',
            'realizado_por',
        ]
        labels = {
            'descripcion': 'Descripción',
            'ultima_fecha_mantenimiento': 'Última fecha de mantenimiento',
            'proxima_fecha_mantenimiento': 'Próxima fecha de mantenimiento',
            'realizado_por': 'Realizado por',
        }


class CorreoForm(FormularioTI):
    class Meta:
        model = Correos
        fields = ['tipo', 'empleado', 'correo_asignado', 'estatus', 'observaciones']
        labels = {'correo_asignado': 'Correo o línea asignada'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si no llega el tipo se asume 'Correo' (comportamiento anterior de la vista).
        self.fields['tipo'].required = False

    def clean_tipo(self):
        return self.cleaned_data.get('tipo') or Correos.Tipo.CORREO


class ConsumibleForm(FormularioTI):
    class Meta:
        model = Consumible
        fields = ['nombre', 'categoria', 'descripcion', 'stock_actual', 'unidad_medida']
        labels = {
            'categoria': 'Categoría',
            'descripcion': 'Descripción',
            'stock_actual': 'Stock actual',
            'unidad_medida': 'Unidad de medida',
        }


class AsignacionForm(FormularioTI):
    """
    Alta y edición de asignaciones de equipo.

    Los archivos y la fecha de asignación se declaran aparte (no son campos editables del
    modelo para ModelForm: `fecha_asignacion` es auto_now_add y los archivos tienen su
    propio manejo de "eliminar archivo actual"), y se aplican en `guardar()`.
    """

    fecha_asignacion = forms.DateField(required=False, label='Fecha de asignación')
    archivo_resguardo = forms.FileField(
        required=False, widget=forms.FileInput, label='Carta responsiva de asignación',
    )
    archivo_devolucion = forms.FileField(
        required=False, widget=forms.FileInput, label='Carta responsiva de devolución',
    )
    eliminar_archivo_resguardo = forms.BooleanField(required=False)
    eliminar_archivo_devolucion = forms.BooleanField(required=False)

    class Meta:
        model = Asignacion
        fields = ['equipo', 'empleado', 'fecha_devolucion', 'estatus', 'entregado_por']
        labels = {
            'fecha_devolucion': 'Fecha de devolución',
            'entregado_por': 'Entregado por',
        }

    # -- Archivos: misma validación (extensión y tamaño) que usan finanzas y control documental.
    def _validar_archivo(self, campo):
        archivo = self.cleaned_data.get(campo)
        if archivo:
            valido, mensaje = validar_archivo_subido(archivo)
            if not valido:
                raise ValidationError(mensaje)
        return archivo

    def clean_archivo_resguardo(self):
        return self._validar_archivo('archivo_resguardo')

    def clean_archivo_devolucion(self):
        return self._validar_archivo('archivo_devolucion')

    def guardar(self):
        """
        Guarda la asignación y devuelve el objeto. Lanza ValidationError si el equipo ya
        tiene una asignación vigente.

        La revisión y el guardado van en una sola transacción que bloquea la fila del
        equipo (SELECT ... FOR UPDATE). Así, dos personas que asignan el mismo equipo al
        mismo tiempo ya no pueden pasar la revisión las dos: la segunda espera, ve la
        asignación de la primera y es rechazada.
        """
        por_borrar = []

        with transaction.atomic():
            equipo = Equipo.objects.select_for_update().get(pk=self.cleaned_data['equipo'].pk)

            if self.cleaned_data['estatus'] == Asignacion.EstatusAsignacion.ASIGNADO:
                vigentes = Asignacion.objects.filter(
                    equipo=equipo, estatus=Asignacion.EstatusAsignacion.ASIGNADO,
                )
                if self.instance.pk:
                    vigentes = vigentes.exclude(pk=self.instance.pk)
                if vigentes.exists():
                    raise ValidationError(
                        'Ese equipo ya tiene una asignación vigente. '
                        'Registra primero su devolución.'
                    )

            asignacion = super().save(commit=False)

            # La fecha de asignación solo se corrige al editar (al crear la fija el modelo).
            fecha = self.cleaned_data.get('fecha_asignacion')
            if fecha and asignacion.pk:
                asignacion.fecha_asignacion = fecha

            # Cada archivo es independiente: si no se sube uno nuevo se conserva el que
            # ya estaba; si se marca "eliminar", se quita sin necesidad de subir otro.
            for campo in ('archivo_resguardo', 'archivo_devolucion'):
                nuevo = self.cleaned_data.get(campo)
                if nuevo:
                    setattr(asignacion, campo, nuevo)
                elif self.cleaned_data.get(f'eliminar_{campo}'):
                    actual = getattr(asignacion, campo)
                    if actual:
                        por_borrar.append((actual.storage, actual.name))
                    setattr(asignacion, campo, None)

            asignacion.save()

        # El archivo físico se borra hasta que la transacción ya se confirmó.
        for almacenamiento, nombre in por_borrar:
            try:
                almacenamiento.delete(nombre)
            except OSError:
                logger.warning('No se pudo borrar el archivo %s', nombre, exc_info=True)

        return asignacion
