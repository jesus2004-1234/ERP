from django.db import models
from django.utils import timezone


class Expediente(models.Model):

    class Tipo(models.TextChoices):
        CLIENTE = 'Cliente', 'Cliente'
        PROVEEDOR = 'Proveedor', 'Proveedor'
        AMBOS = 'Ambos', 'Cliente y Proveedor'


    class TipoContribuyente(models.TextChoices):
        FISICA = 'PF', 'Persona fisica'
        MORAL = 'PM', 'Persona Moral'


    class Estatus(models.TextChoices):
        ACTIVO = 'Activo', 'Activo'
        INACTIVO = 'Inactivo', 'Inactivo'


    # Identificación

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices
    )

    tipo_contribuyente = models.CharField(
        max_length=2,
        choices=TipoContribuyente.choices,
        default=TipoContribuyente.MORAL
    )


    nombres = models.CharField(
        max_length=100,
        blank=True
    )

    apellido_paterno = models.CharField(
        max_length=100,
        blank=True
    )

    apellido_materno = models.CharField(
        max_length=100,
        blank=True
    )

    razon_social = models.CharField(
        max_length=200,
        blank=True
    )

    nombre_comercial = models.CharField(
        max_length=200,
        blank=True
    )


    rfc = models.CharField(
        max_length=13,
        unique=True,
        blank=True,
        null=True
    )


    # Contacto

    contacto_nombre = models.CharField(
        max_length=150,
        blank=True
    )

    contacto_telefono = models.CharField(
        max_length=20,
        blank=True
    )

    contacto_email = models.EmailField(
        blank=True
    )

    direccion = models.TextField(
        blank=True
    )


    # Crédito

    dias_credito = models.PositiveIntegerField(
        default=0
    )

    limite_credito = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )


    # Control

    estatus = models.CharField(
        max_length=20,
        choices=Estatus.choices,
        default=Estatus.ACTIVO
    )

    fecha_alta = models.DateField(
        auto_now_add=True
    )

    observaciones = models.TextField(
        blank=True
    )


    @property
    def nombre_completo(self):

        if self.tipo_contribuyente == self.TipoContribuyente.FISICA:

            return f"{self.nombres} {self.apellido_paterno} {self.apellido_materno}".strip()

        return self.razon_social



    class Meta:
        verbose_name = "Expediente"
        verbose_name_plural = "Expedientes"
        ordering = [
            'tipo_contribuyente',
            'razon_social',
            'nombres'
        ]



    def __str__(self):

        return f"{self.nombre_completo} ({self.get_tipo_display()})"


class ExpedienteDocumento(models.Model):

    class Categoria(models.TextChoices):

        RFC = 'RFC', 'Constancia de RFC'

        SITUACION_FISCAL = (
            'Situacion_Fiscal',
            'Constancia de Situación Fiscal'
        )

        COMPROBANTE_DOM = (
            'Comprobante_Domicilio',
            'Comprobante de Domicilio'
        )

        ACTA_CONSTITUTIVA = (
            'Acta_Constitutiva',
            'Acta Constitutiva'
        )

        CONTRATO = 'Contrato', 'Contrato'

        OTRO = 'Otro', 'Otro'


    expediente = models.ForeignKey(
        Expediente,
        on_delete=models.CASCADE,
        related_name='documentos'
    )


    categoria = models.CharField(
        max_length=30,
        choices=Categoria.choices
    )


    archivo = models.FileField(
        upload_to='finanzas/expedientes/%Y/%m/'
    )


    nombre_archivo = models.CharField(
        max_length=255,
        blank=True,
        editable=False
    )


    activo = models.BooleanField(
        default=True
    )


    fecha_subida = models.DateTimeField(
        auto_now_add=True
    )



    class Meta:
        verbose_name = "Documento de expediente"
        verbose_name_plural = "Documentos de expediente"
        ordering = ['-fecha_subida']



    def save(self, *args, **kwargs):

        if self.archivo:
            self.nombre_archivo = self.archivo.name.split('/')[-1]

        super().save(*args, **kwargs)



    def __str__(self):

        return f"{self.get_categoria_display()} - {self.expediente.nombre_completo}"

class FacturaCliente(models.Model):

    class Estatus(models.TextChoices):
        PENDIENTE = 'Pendiente', 'Pendiente'
        PARCIAL = 'Parcial', 'Parcial'
        PAGADA = 'Pagada', 'Pagada'
        CANCELADA = 'Cancelada', 'Cancelada'

    expediente = models.ForeignKey('Expediente', on_delete=models.PROTECT, related_name='facturas_cliente')
    fecha_factura = models.DateField()
    factura = models.CharField(max_length=50, unique=True)
    orden_compra = models.CharField(max_length=100, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    fecha_ingreso_cliente = models.DateField(blank=True, null=True)
    dias_credito = models.PositiveIntegerField(default=0)
    fecha_vencimiento = models.DateField()
    estatus = models.CharField(max_length=20, choices=Estatus.choices, default=Estatus.PENDIENTE)
    cfdi_complemento_pago = models.BooleanField(default=False)
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    procedencia = models.CharField(max_length=150, blank=True)
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=False)

    @property
    def monto_comision(self):
        return(self.total * self.porcentaje_comision / Decimal("100"))
    @property
    def total_pagado(self):
        return sum(pago.monto for pago in self.pagos.all())
    @property
    def saldo_pendiente(self):
        return self.total - self.total_pagado
    @property
    def dias_vencimiento(self):
        if self.estatus == self.Estatus.PAGADA:
            return 0
        return(timezone.now().date() - self.fecha_vencimiento).days

    def __str__(self):
        return f"{self.factura} - {self.expediente.nombre_completo}"

    class Meta:
        ordering = ["-fecha_factura"]
        verbose_name = "Factura Cliente"
        verbose_name_plural = "Facturas Clientes"


class PagoCliente(models.Model):

    class MetodoPago(models.TextChoices):
        TRANSFERENCIA = "Transferencia", "Transferencia"
        DEPOSITO = "Deposito", "Deposito"
        CHEQUE = "Cheque", "Cheque"
        EFECTIVO = "Efectivo", "Efectivo"
        OTRO = "Otro", "Otro"

    factura = models.ForeignKey('FacturaCliente', on_delete=models.CASCADE, related_name='pagos')
    fecha_pago = models.DateField()
    fecha_deposito = models.DateField( blank=True, null=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago.choices, default=MetodoPago.TRANSFERENCIA)
    referencia = models.CharField(max_length=100, blank=True)
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return(
            f"{self.factura.factura} - " 
            f"${self.monto}"
        )
    class Meta:
        ordering = ['fecha_pago']
        verbose_name = "Pago Cliente"
        verbose_name_plural = "Pagos "