import os
import re

from django.db import IntegrityError, models, transaction


def ruta_documento(instance, filename):
    modulo = instance.modulo.lower()
    nombre_archivo = filename.replace(" ", "_")
    return f"documentos/{modulo}/{nombre_archivo}"


class Documento(models.Model):

    class Modulo(models.TextChoices):
        CCC = "CCC", "Conexion Comercial"
        CPF = "CPF", "Planeacion y Control Financiero"
        CHG = "CHG", "Capital Humano y Gestion Integral"
        GOP = "GOP", "Operaciones y Servicios Generales"
        CIT = "CIT", "Innovacion y Tecnologia"

    class Categoria(models.TextChoices):
        POL = "POL", "Politica"
        PRO = "PRO", "Procedimiento"
        MAN = "MAN", "Manual"
        FOR = "FOR", "Formato"
        INS = "INS", "Instructivo"

    class Estado(models.TextChoices):
        VIGENTE = "VIGENTE", "Vigente"
        OBSOLETO = "OBSOLETO", "Obsoleto"

    codigo = models.CharField(max_length=20, unique=True, blank=True)
    modulo = models.CharField(max_length=3, choices=Modulo.choices)
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=3, choices=Categoria.choices)
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.VIGENTE)
    archivo = models.FileField(upload_to=ruta_documento)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Control Documental"
        ordering = ['categoria', 'modulo', 'codigo', 'nombre']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def extension(self):
        # Antes estaba fuera de la clase (mal indentada) y nunca funcionaba.
        return os.path.splitext(self.archivo.name)[1].lower()

    def _siguiente_codigo(self):
        """
        Calcula el consecutivo numéricamente (el MAX sobre texto fallaba pasando
        el 999 y el cálculo previo no toleraba códigos con formato distinto).
        """
        prefijo = f"{self.categoria}-{self.modulo}-"
        codigos = Documento.objects.filter(
            modulo=self.modulo, categoria=self.categoria, codigo__startswith=prefijo
        ).values_list("codigo", flat=True)
        numeros = []
        for codigo in codigos:
            coincidencia = re.search(r"(\d+)$", codigo)
            if coincidencia:
                numeros.append(int(coincidencia.group(1)))
        return f"{prefijo}{(max(numeros) + 1 if numeros else 1):03d}"

    def save(self, *args, **kwargs):
        if not self.estado:
            self.estado = self.Estado.VIGENTE

        if self.codigo:
            return super().save(*args, **kwargs)

        # Si dos usuarios suben a la vez y chocan en el código único, se reintenta.
        for intento in range(5):
            self.codigo = self._siguiente_codigo()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if intento == 4:
                    raise
