from django.db import models


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
