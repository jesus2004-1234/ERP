from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator


class Expediente(models.Model):
    class Tipo(models.TextChoices):
        CLIENTE = "Cliente", "Cliente"
        PROVEEDOR = "Proveedor", "Proveedor"
        AMBOS = "Ambos", "Cliente y Proveedor"

    class TipoContribuyente(models.TextChoices):
        FISICA = "PF", "Persona Fisica"
        MORAL = "PM", "Persona Moral"

    class Estatus(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        INACTIVO = "Inactivo", "Inactivo"

    class RegimenFiscal(models.TextChoices):
        GENERAL = "601", "601 - General de Ley Personas Morales"
        SIMPLIFICADO = "626", "626 - Régimen Simplificado de Confianza"
        SUELDOS = "605", "605 - Sueldos y Salarios"
        ARRENDAMIENTO = "606", "606 - Arrendamiento"
        ACTIVIDAD_EMPRESARIAL = "612", "612 - Personas Físicas con Actividades Empresariales"
        PROFESIONALES = "611", "611 - Ingresos por Honorarios"
        INCORPORACION = "621", "621 - Incorporación Fiscal"
        SIN_OBLIGACIONES = "616", "616 - Sin obligaciones fiscales"

    regimen_fiscal = models.CharField(max_length=3, choices=RegimenFiscal.choices, blank=True)

    # Identificación

    tipo = models.CharField(max_length=20, choices=Tipo.choices)

    tipo_contribuyente = models.CharField(
        max_length=2, choices=TipoContribuyente.choices, default=TipoContribuyente.MORAL
    )

    nombres = models.CharField(max_length=100, blank=True)

    apellido_paterno = models.CharField(max_length=100, blank=True)

    apellido_materno = models.CharField(max_length=100, blank=True)

    razon_social = models.CharField(max_length=200, blank=True)

    nombre_comercial = models.CharField(max_length=200, blank=True)

    rfc = models.CharField(max_length=13, unique=True, blank=True, null=True)

    # Contacto

    contacto_nombre = models.CharField(max_length=150, blank=True)

    contacto_telefono = models.CharField(max_length=20, blank=True)

    contacto_email = models.EmailField(blank=True)

    correo_pagos = models.EmailField(
        blank=True,
        verbose_name="Correo para envío de pagos",
        help_text="Aplica únicamente para expedientes de tipo Proveedor.",
    )

    direccion = models.TextField(blank=True)

    # Crédito

    dias_credito = models.PositiveIntegerField(default=0)

    limite_credito = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )

    # Control

    estatus = models.CharField(
        max_length=20, choices=Estatus.choices, default=Estatus.ACTIVO
    )

    fecha_alta = models.DateField(auto_now_add=True)

    observaciones = models.TextField(blank=True)

    @property
    def nombre_completo(self):

        if self.tipo_contribuyente == self.TipoContribuyente.FISICA:
            return f"{self.nombres} {self.apellido_paterno} {self.apellido_materno}".strip()

        return self.razon_social

    class Meta:
        verbose_name = "Expediente"
        verbose_name_plural = "Expedientes"
        ordering = ["tipo_contribuyente", "razon_social", "nombres"]  # noqa: RUF012

    def __str__(self):

        return f"{self.nombre_completo} ({self.get_tipo_display()})"


class ExpedienteDocumento(models.Model):
    class Categoria(models.TextChoices):
        
        ACTA_CONSTITUTIVA = ("Acta_Constitutiva", "Acta Constitutiva")
    
        SITUACION_FISCAL = ("Situacion_Fiscal", "Constancia de Situación Fiscal")

        COMPROBANTE_DOM = ("Comprobante_Domicilio", "Comprobante de Domicilio")

        INE = "INE", "INE"

        OPINION_CUMPLIMIENTO = ("Opinion_Cumplimiento", "Opinion de Cumplimiento")

        CONTRATO = "Contrato", "Contrato"

        DATOS_BANCARIOS = ("Datos_Bancarios", "Datos Bancarios")

        OTRO = "Otro", "Otro"

    expediente = models.ForeignKey(
        Expediente, on_delete=models.PROTECT, related_name="documentos"
    )

    categoria = models.CharField(max_length=30, choices=Categoria.choices)

    archivo = models.FileField(upload_to="finanzas/expedientes/%Y/%m/")

    nombre_archivo = models.CharField(max_length=255, blank=True, editable=False)

    activo = models.BooleanField(default=True)

    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento de expediente"
        verbose_name_plural = "Documentos de expediente"
        ordering = ['-fecha_subida']  # noqa: RUF012

    def save(self, *args, **kwargs):

        if self.archivo:
            self.nombre_archivo = self.archivo.name.split("/")[-1]

        super().save(*args, **kwargs)

    def __str__(self):

        return f"{self.get_categoria_display()} - {self.expediente.nombre_completo}"


class FacturaCliente(models.Model):
    class Estatus(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        PARCIAL = "Parcial", "Parcial"
        PAGADA = "Pagada", "Pagada"
        CANCELADA = "Cancelada", "Cancelada"

    class Moneda(models.TextChoices):
       MXN = "MXN", "Peso Mexicano"
       USD = "USD", "Dólar Americano"
       EUR = "EUR", "Euro"

    expediente = models.ForeignKey(
        "Expediente", on_delete=models.PROTECT, related_name="facturas_cliente"
    )
    fecha_factura = models.DateField()
    factura = models.CharField(max_length=50, unique=True)
    orden_servicio = models.CharField(max_length=100, blank=True)
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
    fecha_registro = models.DateTimeField(auto_now_add=True)

    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.MXN)
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))

    @property
    def monto_comision(self):
        total = self.total or Decimal("0.00")
        porcentaje = self.porcentaje_comision or Decimal("0.00")
        return total * porcentaje / Decimal("100")

    @property
    def total_pagado(self):
        return sum(pago.monto for pago in self.pagos.all())

    @property
    def saldo_pendiente(self):
        total = self.total or Decimal("0.00")
        return total - self.total_pagado

    @property
    def dias_vencimiento(self):
        if self.estatus == self.Estatus.PAGADA:
            return 0
        dias = (timezone.now().date() - self.fecha_vencimiento).days
        return dias if dias > 0 else 0

    @property
    def vencida(self):
        return (self.saldo_pendiente > 0 and timezone.now().date() > self.fecha_vencimiento)

    def actualizar_estatus(self):
        if self.estatus == self.Estatus.CANCELADA:
            return
        saldo = self.saldo_pendiente
        if saldo <= 0:
           nuevo = self.Estatus.PAGADA
        elif saldo < self.total:
           nuevo = self.Estatus.PARCIAL
        else:
            nuevo = self.Estatus.PENDIENTE
        if nuevo != self.estatus:
            self.estatus = nuevo
            self.save(update_fields=["estatus"])


    def __str__(self):
        return f"{self.factura} - {self.expediente.nombre_completo}"

    class Meta:
        ordering = ["-fecha_factura"]  # noqa: RUF012
        verbose_name = "Factura Cliente"
        verbose_name_plural = "Facturas Clientes"


class PagoCliente(models.Model):
    class MetodoPago(models.TextChoices):
        TRANSFERENCIA = "Transferencia", "Transferencia"
        DEPOSITO = "Deposito", "Deposito"
        CHEQUE = "Cheque", "Cheque"
        EFECTIVO = "Efectivo", "Efectivo"
        OTRO = "Otro", "Otro"

    factura = models.ForeignKey(
        "FacturaCliente", on_delete=models.CASCADE, related_name="pagos"
    )
    fecha_pago = models.DateField()
    fecha_deposito = models.DateField(blank=True, null=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(
        max_length=20, choices=MetodoPago.choices, default=MetodoPago.TRANSFERENCIA
    )
    referencia = models.CharField(max_length=100, blank=True)
    comprobante_pago = models.FileField(upload_to="finanzas/pagos/", blank=True, null=True)
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.factura.factura} - ${self.monto}"

    class Meta:
        ordering = ["fecha_pago"]  # noqa: RUF012
        verbose_name = "Pago Cliente"
        verbose_name_plural = "Pagos "

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.factura.actualizar_estatus()

class FacturaProveedor(models.Model):
    class Estatus(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        PARCIAL = "Parcial", "Parcial"
        PAGADA = "Pagada", "Pagada"
        CANCELADA = "Cancelada", "Cancelada"

    class Moneda(models.TextChoices):
        MXN = "MXN", "Peso Mexicano"
        USD = "USD", "Dólar Americano"
        EUR = "EUR", "Euro"

    expediente = models.ForeignKey(
        "Expediente",
        on_delete=models.PROTECT,
        related_name="facturas_proveedor",
    )

    fecha_factura = models.DateField()
    factura = models.CharField(max_length=50, unique=True)
    orden_compra = models.CharField(max_length=100, blank=True)

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    fecha_ingreso_proveedor = models.DateField(
        blank=True,
        null=True,
    )

    dias_credito = models.PositiveIntegerField(
        default=0,
    )

    fecha_vencimiento = models.DateField()

    estatus = models.CharField(
        max_length=20,
        choices=Estatus.choices,
        default=Estatus.PENDIENTE,
    )

    # Lo conservamos por ahora.
    cfdi_complemento_pago = models.BooleanField(
        default=False,
    )

    porcentaje_comision = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    procedencia = models.CharField(
        max_length=150,
        blank=True,
    )

    observaciones = models.TextField(
        blank=True,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    moneda = models.CharField(
        max_length=3,
        choices=Moneda.choices,
        default=Moneda.MXN,
    )

    tipo_cambio = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    @property
    def monto_comision(self):
        total = self.total or Decimal("0.00")
        porcentaje = self.porcentaje_comision or Decimal("0.00")

        return (
            total
            * porcentaje
            / Decimal("100")
        )

    @property
    def total_pagado(self):
        return sum(
            pago.monto
            for pago in self.pagos.all()
        )

    @property
    def saldo_pendiente(self):
        total = self.total or Decimal("0.00")

        return total - self.total_pagado

    @property
    def dias_vencimiento(self):
        if self.estatus == self.Estatus.PAGADA:
            return 0

        dias = (
            timezone.now().date()
            - self.fecha_vencimiento
        ).days

        return dias if dias > 0 else 0

    @property
    def vencida(self):
        return (
            self.saldo_pendiente > 0
            and timezone.now().date()
            > self.fecha_vencimiento
        )

    def actualizar_estatus(self):
        if self.estatus == self.Estatus.CANCELADA:
            return

        saldo = self.saldo_pendiente

        if saldo <= 0:
            nuevo = self.Estatus.PAGADA

        elif saldo < self.total:
            nuevo = self.Estatus.PARCIAL

        else:
            nuevo = self.Estatus.PENDIENTE

        if nuevo != self.estatus:
            self.estatus = nuevo

            self.save(
                update_fields=["estatus"]
            )

    def __str__(self):
        return (
            f"{self.factura} - "
            f"{self.expediente.nombre_completo}"
        )

    class Meta:
        ordering = ["-fecha_factura"]
        verbose_name = "Factura Proveedor"
        verbose_name_plural = "Facturas Proveedores"


class PagoProveedor(models.Model):
    class MetodoPago(models.TextChoices):
        TRANSFERENCIA = "Transferencia", "Transferencia"
        DEPOSITO = "Deposito", "Deposito"
        CHEQUE = "Cheque", "Cheque"
        EFECTIVO = "Efectivo", "Efectivo"
        OTRO = "Otro", "Otro"

    factura = models.ForeignKey(
        "FacturaProveedor",
        on_delete=models.PROTECT,
        related_name="pagos",
    )

    fecha_pago = models.DateField()

    fecha_deposito = models.DateField(
        blank=True,
        null=True,
    )

    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    metodo_pago = models.CharField(
        max_length=20,
        choices=MetodoPago.choices,
        default=MetodoPago.TRANSFERENCIA,
    )

    referencia = models.CharField(
        max_length=100,
        blank=True,
    )

    comprobante_pago = models.FileField(
        upload_to="finanzas/pagos/",
        blank=True,
        null=True,
    )

    observaciones = models.TextField(
        blank=True,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return (
            f"{self.factura.factura} - "
            f"${self.monto}"
        )

    class Meta:
        ordering = ["fecha_pago"]
        verbose_name = "Pago Proveedor"
        verbose_name_plural = "Pagos Proveedores"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.factura.actualizar_estatus()

    def delete(self, *args, **kwargs):
        factura = self.factura

        with transaction.atomic():
            super().delete(*args, **kwargs)
            factura.actualizar_estatus()

class PresupuestoAnual(models.Model):

    class Estatus(models.TextChoices):
        BORRADOR = "Borrador", "Borrador"
        ACTIVO = "Activo", "Activo"
        CERRADO = "Cerrado", "Cerrado"

    ejercicio = models.PositiveIntegerField(unique=True, verbose_name="Ejercicio")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    estatus = models.CharField(
        max_length=20,
        choices=Estatus.choices,
        default=Estatus.BORRADOR,
        verbose_name="Estatus",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creacion")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Ultima actualizacion")

    class Meta:
        verbose_name = "Presupuesto anual"
        verbose_name_plural = "Presupuestos anuales"
        ordering = ["-ejercicio"]

    def __str__(self):
        return self.nombre


class ConceptoIngreso(models.Model):
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Codigo")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripcion")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Concepto de ingreso"
        verbose_name_plural = "Conceptos de ingresos"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PartidaGasto(models.Model):
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Codigo")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripcion")
    partida_padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subpartidas",
        verbose_name="Partida padre",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Partida de gasto"
        verbose_name_plural = "Partidas de gastos"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PresupuestoIngreso(models.Model):
    presupuesto = models.ForeignKey(
        PresupuestoAnual, on_delete=models.CASCADE, related_name="ingresos", verbose_name="Presupuesto"
    )
    concepto = models.ForeignKey(
        ConceptoIngreso, on_delete=models.PROTECT, related_name="presupuesto", verbose_name="Concepto de ingresos"
    )
    monto_anual = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Monto anual")

    class Meta:
        verbose_name = "Presupuesto de ingreso"
        verbose_name_plural = "Presupuestos de ingresos"

        constraints = [
            models.UniqueConstraint(
                fields=["presupuesto", "concepto"],
                name="unique_presupuesto_concepto_ingreso"
            )
        ]

    def __str__(self):
        return f"{self.presupuesto} - {self.concepto}"


class PresupuestoGasto(models.Model):
    presupuesto = models.ForeignKey(
        PresupuestoAnual, on_delete=models.CASCADE, related_name="gastos", verbose_name="Presupuesto"
    )
    partida = models.ForeignKey(
        PartidaGasto, on_delete=models.PROTECT, related_name="presupuestos", verbose_name="Partida de gastos"
    )
    monto_anual = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Monto anual")

    class Meta:
        verbose_name = "Presupuesto de gasto"
        verbose_name_plural = "Presupuestos de gastos"

        constraints = [
            models.UniqueConstraint(
                fields=["presupuesto", "partida"],
                name="unique_presupuesto_partida_gasto"
            )
        ]

    def __str__(self):
        return f"{self.presupuesto} - {self.partida}"


class PresupuestoIngresoMensual(models.Model):
    presupuesto_ingreso = models.ForeignKey(
        PresupuestoIngreso, on_delete=models.CASCADE, related_name="mensualidades", verbose_name="Presupuesto de ingreso"
    )
    mes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Mes",
    )
    monto = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Monto")

    class Meta:
        verbose_name = "Presupuesto mensual de ingreso"
        verbose_name_plural = "Presupuestos mensuales de ingresos"

        constraints = [
            models.UniqueConstraint(
                fields=["presupuesto_ingreso", "mes"],
                name="unique_presupuesto_ingreso_mes"
            )
        ]

        ordering = ["mes"]

    def __str__(self):
        return f"{self.presupuesto_ingreso} - Mes {self.mes}: ${self.monto}"


class PresupuestoGastoMensual(models.Model):
    presupuesto_gasto = models.ForeignKey(
        PresupuestoGasto, on_delete=models.CASCADE, related_name="mensualidades", verbose_name="Presupuesto de gasto"
    )
    mes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Mes",
    )
    monto = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Monto")

    class Meta:
        verbose_name = "Presupuesto mensual de gasto"
        verbose_name_plural = "Presupuestos mensuales de gastos"

        constraints = [
            models.UniqueConstraint(
                fields=["presupuesto_gasto", "mes"],
                name="unique_presupuesto_gasto_mes"
            )
        ]

        ordering = ["mes"]

    def __str__(self):
        return f"{self.presupuesto_gasto} - Mes {self.mes}: ${self.monto}"