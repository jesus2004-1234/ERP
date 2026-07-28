from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Empleado(models.Model):

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="empleado"
    )
    class Departamento(models.TextChoices):
        DGE = 'DGE', 'Dirección General'
        GAF = 'GAF', 'Gerencia de Administración y Finanzas'
        CCC = 'CCC', 'Conexión Comercial'
        CPF = 'CPF', 'Planeación y Control Financiero'
        CHG = 'CHG', 'Capital Humano y Gestión Integral'
        GOP = 'GOP', 'Operaciones y Servicios Generales'
        CIT = 'CIT', 'Innovación y Tecnología'

    nombre             = models.CharField(max_length=100)
    apellido           = models.CharField(max_length=100)
    departamento       = models.CharField(max_length=100, choices=Departamento.choices)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ['apellido', 'nombre']

    @property
    def tiene_computadora(self):
        return self.asignaciones.filter(
            equipo__tipo__in=['Computadora', 'Laptop'],
            estatus='Asignado'
        ).exists()

    @property
    def tiene_telefono(self):
        return self.asignaciones.filter(
            equipo__tipo='Teléfono',
            estatus='Asignado'
        ).exists()

    @property
    def tiene_linea_telefonica(self):
        return self.correos.filter(
            tipo='Linea',
            estatus='Ocupado'
        ).exists()


class Equipo(models.Model):

    class TipoEquipo(models.TextChoices):
        COMPUTADORA = 'Computadora', 'Computadora'
        IMPRESORA   = 'Impresora',   'Impresora'
        PROYECTOR   = 'Proyector',   'Proyector'
        TELEFONO    = 'Teléfono',    'Teléfono'
        TECLADO     = 'Teclado',     'Teclado'
        MOUSE       = 'Mouse',       'Mouse'

    class EstatusEquipo(models.TextChoices):
        ACTIVO        = 'Activo',        'Activo'
        INACTIVO      = 'Inactivo',      'Inactivo'
        EN_REPARACION = 'En reparación', 'En reparación'
        BAJA          = 'Baja',          'Baja'

    tipo              = models.CharField(max_length=20, choices=TipoEquipo.choices)
    marca             = models.CharField(max_length=100)
    modelo            = models.CharField(max_length=100)
    numero_serie      = models.CharField(max_length=100, unique=True)
    sistema_operativo = models.CharField(max_length=100, blank=True, null=True)
    estatus           = models.CharField(max_length=20, choices=EstatusEquipo.choices, default=EstatusEquipo.ACTIVO)

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ['tipo', 'marca', 'modelo']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.marca} {self.modelo} (S/N: {self.numero_serie})"


class Asignacion(models.Model):

    class EstatusAsignacion(models.TextChoices):
        ASIGNADO = 'Asignado', 'Asignado'
        DEVUELTO = 'Devuelto', 'Devuelto'

    equipo           = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    empleado         = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='asignaciones')
    fecha_asignacion = models.DateField(auto_now_add=True)
    fecha_devolucion = models.DateField(blank=True, null=True)
    estatus          = models.CharField(max_length=20, choices=EstatusAsignacion.choices, default=EstatusAsignacion.ASIGNADO)
    entregado_por    = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Asignación"
        verbose_name_plural = "Asignaciones"
        ordering = ['-fecha_asignacion']

    def __str__(self):
        return f"{self.equipo} asignado a {self.empleado} el {self.fecha_asignacion}"


class Mantenimiento(models.Model):

    class TipoMantenimiento(models.TextChoices):
        PREVENTIVO = 'Preventivo', 'Preventivo'
        CORRECTIVO = 'Correctivo', 'Correctivo'

    equipo                      = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    descripcion                 = models.TextField(blank=True, null=True)
    tipo                        = models.CharField(max_length=20, choices=TipoMantenimiento.choices)
    ultima_fecha_mantenimiento  = models.DateField(blank=True, null=True)
    proxima_fecha_mantenimiento = models.DateField(blank=True, null=True)
    realizado_por               = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Mantenimiento"
        verbose_name_plural = "Mantenimientos"
        ordering = ['-proxima_fecha_mantenimiento']

    def __str__(self):
        return f"Mantenimiento {self.get_tipo_display()} para {self.equipo} - {self.estatus}"

    @property
    def estatus(self):
        if not self.proxima_fecha_mantenimiento:
            return 'Pendiente'
        hoy = timezone.now().date()
        dias_restantes = (self.proxima_fecha_mantenimiento - hoy).days
        if dias_restantes < 0:
            return 'Vencido'
        elif dias_restantes <= 30:
            return 'Pendiente'
        return 'Al dia'

    @property
    def color_estatus(self):
        if self.estatus == 'Vencido':
            return 'danger'
        elif self.estatus == 'Pendiente':
            return 'warning text-dark'
        return 'success'


class Correos(models.Model):

    class Tipo(models.TextChoices):
        CORREO = 'Correo', 'Correo electrónico'
        LINEA  = 'Linea',  'Línea telefónica'

    class EstatusCorreo(models.TextChoices):
        DISPONIBLE = 'Disponible', 'Disponible'
        OCUPADO    = 'Ocupado',    'Ocupado'

    tipo             = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CORREO)
    empleado         = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True, related_name='correos')
    correo_asignado  = models.CharField(max_length=200)
    fecha_asignacion = models.DateField(auto_now_add=True)
    estatus          = models.CharField(max_length=20, choices=EstatusCorreo.choices, default=EstatusCorreo.DISPONIBLE)
    observaciones    = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Correo / Línea"
        verbose_name_plural = "Correos y Líneas"
        ordering = ['-fecha_asignacion']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.correo_asignado} ({self.get_estatus_display()})"


class Consumible(models.Model):

    class Categoria(models.TextChoices):
        PAPELERIA = 'Papelería', 'Papelería'
        TONER     = 'Tóner',    'Tóner'
        CABLE     = 'Cable',    'Cable'
        ACCESORIO = 'Accesorio','Accesorio'
        OTRO      = 'Otro',     'Otro'

    nombre        = models.CharField(max_length=200)
    categoria     = models.CharField(max_length=20, choices=Categoria.choices)
    descripcion   = models.TextField(blank=True, null=True)
    stock_actual  = models.PositiveIntegerField(default=0)
    unidad_medida = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = 'Consumible'
        verbose_name_plural = 'Consumibles'
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.stock_actual} disponibles)"

    @property
    def stock_bajo(self):
        return self.stock_actual < 5