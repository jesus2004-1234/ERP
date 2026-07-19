from django.db import models
import os
from django.db.models import Max

def ruta_documento(instance, filename):
   modulo = instance.modulo.lower()
   nombre_archivo = filename.replace(" ", "_")
   return f"documentos/{modulo}/{nombre_archivo}"

class Documento(models.Model):
    def save(self, *args, **kwargs):
        if not self.codigo:
            ultimo_codigo = Documento.objects.filter(modulo=self.modulo, categoria=self.categoria).aggregate(Max('codigo'))['codigo__max']
            if ultimo_codigo:
                next_codigo = str(int(ultimo_codigo.split('-')[-1]) + 1)
            else:
                next_codigo = '1'
            self.codigo = f"{self.categoria}-{self.modulo}-{next_codigo:03d}"
        super().save(*args, **kwargs)
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
    
    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Control Documental"
        ordering = ['categoria', 'modulo', 'codigo', 'nombre']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"