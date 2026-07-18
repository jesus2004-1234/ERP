from django.db import models
import os

def ruta_documento(instance, filename):
   extension = os.path.splitext(filename)[1]
   modulo = instance.__class__.__name__.lower()
   nombre_archivo = instance.modulo.lower().replace(" ", "_")
   return f"documentos/{modulo}/{nombre_archivo}{extension}"

class Documento(models.Model):
    def save(self, *args, **kwargs):
        if not self.codigo:
            consecutivo = Documento.objects.filter(modulo=self.modulo, categoria=self.categoria).count() + 1
            self.codigo = f"{self.categoria}-{self.modulo}-{consecutivo:03d}"
        super().save(*args, **kwargs)
    class Modulo:
        CCC = "CCC" "Conexion Comercial"
        CPF = "CPF" "Planeacion y Control Financiero"
        CHG = "CHG" "Capital Humano y Gestion Integral"
        GOP = "GOP" "Operaciones y Servicios Generales"
        CIT = "CIT" "Innovacion y Tecnologia"

    class Categoria:
        POL = "POL" "Politica"
        PRO = "PRO" "Procedimiento"
        MAN = "MAN" "Manual"
        FOR = "FOR" "Formato"
        INS = "INS" "Instructivo"

    class Estado:
        Vigente = "Vigente"
        Obsoleto = "Obsoleto"

    codigo = models.CharField(max_length=20, unique=True, blank=True)
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=3, choices=Categoria.choices)
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.Vigente)
    archivo = models.FileField(upload_to=ruta_documento)
    
    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Control Documental"
        ordering = ['categoria', 'modulo', 'codigo', 'nombre']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"