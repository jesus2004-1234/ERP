import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Documento

MEDIA_TEMPORAL = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class CodigoDocumentoTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    def crear(self, nombre="doc.pdf"):
        return Documento.objects.create(
            modulo="CIT", categoria="POL", nombre=nombre,
            archivo=SimpleUploadedFile(nombre, b"x"),
        )

    def test_codigos_consecutivos(self):
        self.assertEqual(self.crear("a.pdf").codigo, "POL-CIT-001")
        self.assertEqual(self.crear("b.pdf").codigo, "POL-CIT-002")

    def test_consecutivo_sigue_despues_de_999(self):
        Documento.objects.create(
            modulo="CIT", categoria="POL", nombre="x", codigo="POL-CIT-999",
            archivo=SimpleUploadedFile("x.pdf", b"x"),
        )
        # Con MAX() sobre texto, "POL-CIT-999" > "POL-CIT-1000" y se repetia el codigo.
        self.assertEqual(self.crear("y.pdf").codigo, "POL-CIT-1000")

    def test_extension_funciona(self):
        self.assertEqual(self.crear("manual.DOCX").extension, ".docx")
