"""
Pruebas del módulo de TI.

Correr con (usa SQLite en memoria, no necesita MySQL):

    python manage.py test ti --settings=config.settings_test
"""
import shutil
import tempfile
from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Asignacion, Consumible, Correos, Empleado, Equipo, Mantenimiento

Departamento = Empleado.Departamento

DATOS_EQUIPO = {
    'tipo': 'Computadora',
    'marca': 'Dell',
    'modelo': 'Latitude 5440',
    'numero_serie': 'SN-0001',
    'sistema_operativo': 'Windows 11',
    'estatus': 'Activo',
}

DATOS_CONSUMIBLE = {
    'nombre': 'Tóner HP 105A',
    'categoria': 'Toner',
    'descripcion': '',
    'stock_actual': '10',
    'unidad_medida': 'piezas',
}


def crear_usuario(username, departamento=None, superusuario=False):
    """Usuario de prueba; con `departamento` también crea su Empleado (lo que lee el middleware)."""
    usuario = User.objects.create_user(username, password='no-se-usa')
    if superusuario:
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.save()
    if departamento:
        Empleado.objects.create(
            usuario=usuario,
            nombre=username.capitalize(),
            apellido='Prueba',
            departamento=departamento,
        )
    return usuario


class AccesoPorDepartamentoTests(TestCase):
    """El middleware solo deja entrar a /ti/ al departamento CIT (y a los superusuarios)."""

    def test_sin_sesion_va_al_login(self):
        url = reverse('equipos_lista')
        respuesta = self.client.get(url)
        self.assertRedirects(
            respuesta, f"{reverse('login')}?next={url}", fetch_redirect_response=False,
        )

    def test_otro_departamento_no_entra(self):
        self.client.force_login(crear_usuario('contadora', Departamento.CPF))
        respuesta = self.client.get(reverse('equipos_lista'))
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)

    def test_usuario_sin_empleado_no_entra(self):
        self.client.force_login(crear_usuario('sinempleado'))
        respuesta = self.client.get(reverse('equipos_lista'))
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)

    def test_ti_si_entra(self):
        self.client.force_login(crear_usuario('tecnico', Departamento.CIT))
        respuesta = self.client.get(reverse('equipos_lista'))
        self.assertEqual(respuesta.status_code, 200)

    def test_superusuario_si_entra(self):
        self.client.force_login(crear_usuario('admin', superusuario=True))
        respuesta = self.client.get(reverse('equipos_lista'))
        self.assertEqual(respuesta.status_code, 200)

    def test_el_dashboard_de_ti_carga(self):
        self.client.force_login(crear_usuario('tecnico', Departamento.CIT))
        # Sin tocar la API externa de tickets.
        with mock.patch('ti.views._obtener_tickets', return_value=[]):
            respuesta = self.client.get(reverse('ti_dashboard'))
        self.assertEqual(respuesta.status_code, 200)


class PruebasTI(TestCase):
    """Base: usuario de TI con sesión iniciada y carpeta de archivos (media) temporal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._carpeta_media = tempfile.mkdtemp()
        cls._config_media = override_settings(MEDIA_ROOT=cls._carpeta_media)
        cls._config_media.enable()

    @classmethod
    def tearDownClass(cls):
        cls._config_media.disable()
        shutil.rmtree(cls._carpeta_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(crear_usuario('tecnico', Departamento.CIT))

    def mensajes(self, respuesta):
        return [m.message for m in get_messages(respuesta.wsgi_request)]


class EmpleadosFormularioTests(PruebasTI):

    def test_empleado_valido_se_crea(self):
        datos = {'nombre': 'Ana', 'apellido': 'López', 'departamento': 'CHG'}
        respuesta = self.client.post(reverse('empleado_crear'), datos)
        self.assertRedirects(respuesta, reverse('empleados_lista'), fetch_redirect_response=False)
        self.assertTrue(Empleado.objects.filter(nombre='Ana', departamento='CHG').exists())

    def test_departamento_invalido_se_rechaza(self):
        datos = {'nombre': 'Ana', 'apellido': 'López', 'departamento': 'XXX'}
        respuesta = self.client.post(reverse('empleado_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Empleado.objects.filter(nombre='Ana').exists())
        self.assertTrue(self.mensajes(respuesta))

    def test_campo_faltante_no_da_error_500(self):
        datos = {'nombre': 'Ana', 'departamento': 'CHG'}   # falta apellido
        respuesta = self.client.post(reverse('empleado_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Empleado.objects.filter(nombre='Ana').exists())


class EquiposFormularioTests(PruebasTI):

    def test_equipo_valido_se_crea(self):
        respuesta = self.client.post(reverse('equipo_crear'), DATOS_EQUIPO)
        self.assertRedirects(respuesta, reverse('equipos_lista'), fetch_redirect_response=False)
        self.assertEqual(Equipo.objects.count(), 1)

    def test_numero_de_serie_repetido_no_da_error_500(self):
        Equipo.objects.create(**DATOS_EQUIPO)
        respuesta = self.client.post(reverse('equipo_crear'), DATOS_EQUIPO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Equipo.objects.count(), 1)
        self.assertTrue(any('número de serie' in m.lower() for m in self.mensajes(respuesta)))

    def test_se_puede_editar_conservando_su_propio_numero_de_serie(self):
        equipo = Equipo.objects.create(**DATOS_EQUIPO)
        datos = dict(DATOS_EQUIPO, marca='HP')
        respuesta = self.client.post(reverse('equipo_editar', args=[equipo.pk]), datos)
        self.assertRedirects(respuesta, reverse('equipos_lista'), fetch_redirect_response=False)
        equipo.refresh_from_db()
        self.assertEqual(equipo.marca, 'HP')

    def test_editar_con_el_serie_de_otro_equipo_se_rechaza(self):
        Equipo.objects.create(**DATOS_EQUIPO)
        otro = Equipo.objects.create(**dict(DATOS_EQUIPO, numero_serie='SN-0002'))
        datos = dict(DATOS_EQUIPO, numero_serie='SN-0001')
        respuesta = self.client.post(reverse('equipo_editar', args=[otro.pk]), datos)
        self.assertEqual(respuesta.status_code, 200)
        otro.refresh_from_db()
        self.assertEqual(otro.numero_serie, 'SN-0002')

    def test_tipo_invalido_se_rechaza(self):
        respuesta = self.client.post(reverse('equipo_crear'), dict(DATOS_EQUIPO, tipo='Cafetera'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Equipo.objects.count(), 0)

    def test_estatus_invalido_se_rechaza(self):
        respuesta = self.client.post(reverse('equipo_crear'), dict(DATOS_EQUIPO, estatus='Perdido'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Equipo.objects.count(), 0)

    def test_campo_faltante_no_da_error_500(self):
        datos = {k: v for k, v in DATOS_EQUIPO.items() if k != 'marca'}
        respuesta = self.client.post(reverse('equipo_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Equipo.objects.count(), 0)

    def test_sistema_operativo_vacio_se_guarda_como_texto_vacio(self):
        datos = dict(DATOS_EQUIPO, sistema_operativo='')
        self.client.post(reverse('equipo_crear'), datos)
        self.assertEqual(Equipo.objects.get().sistema_operativo, '')


class ConsumiblesFormularioTests(PruebasTI):

    def test_consumible_valido_se_crea(self):
        respuesta = self.client.post(reverse('consumible_crear'), DATOS_CONSUMIBLE)
        self.assertRedirects(respuesta, reverse('consumibles_lista'), fetch_redirect_response=False)
        self.assertEqual(Consumible.objects.get().stock_actual, 10)

    def test_stock_invalido_se_rechaza(self):
        for stock in ('', '-5', 'abc', '2.5'):
            with self.subTest(stock=stock):
                datos = dict(DATOS_CONSUMIBLE, stock_actual=stock)
                respuesta = self.client.post(reverse('consumible_crear'), datos)
                self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Consumible.objects.count(), 0)

    def test_categoria_invalida_se_rechaza(self):
        datos = dict(DATOS_CONSUMIBLE, categoria='Dulces')
        respuesta = self.client.post(reverse('consumible_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Consumible.objects.count(), 0)

    def test_editar_con_stock_invalido_conserva_el_valor_anterior(self):
        consumible = Consumible.objects.create(
            nombre='Cable HDMI', categoria='Cable', stock_actual=4,
        )
        datos = dict(DATOS_CONSUMIBLE, nombre='Cable HDMI', categoria='Cable', stock_actual='-1')
        respuesta = self.client.post(reverse('consumible_editar', args=[consumible.pk]), datos)
        self.assertEqual(respuesta.status_code, 200)
        consumible.refresh_from_db()
        self.assertEqual(consumible.stock_actual, 4)


class MantenimientosFormularioTests(PruebasTI):

    def setUp(self):
        super().setUp()
        self.equipo = Equipo.objects.create(**DATOS_EQUIPO)

    def datos(self, **extra):
        datos = {
            'equipo': self.equipo.pk,
            'tipo': 'Preventivo',
            'descripcion': '',
            'ultima_fecha_mantenimiento': '',
            'proxima_fecha_mantenimiento': '2026-12-01',
            'realizado_por': '',
        }
        datos.update(extra)
        return datos

    def test_mantenimiento_valido_se_crea(self):
        respuesta = self.client.post(reverse('mantenimiento_crear'), self.datos())
        self.assertRedirects(
            respuesta, reverse('mantenimientos_lista'), fetch_redirect_response=False,
        )
        mantenimiento = Mantenimiento.objects.get()
        self.assertEqual(mantenimiento.proxima_fecha_mantenimiento, date(2026, 12, 1))
        self.assertIsNone(mantenimiento.ultima_fecha_mantenimiento)

    def test_fecha_invalida_se_rechaza(self):
        datos = self.datos(proxima_fecha_mantenimiento='31-31-2026')
        respuesta = self.client.post(reverse('mantenimiento_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Mantenimiento.objects.count(), 0)

    def test_equipo_inexistente_se_rechaza(self):
        respuesta = self.client.post(reverse('mantenimiento_crear'), self.datos(equipo=99999))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Mantenimiento.objects.count(), 0)


class CorreosFormularioTests(PruebasTI):

    def test_si_no_llega_el_tipo_se_asume_correo(self):
        datos = {
            'correo_asignado': 'ana@ejemplo.com',
            'estatus': 'Disponible',
            'empleado': '',
            'observaciones': '',
        }
        respuesta = self.client.post(reverse('correo_crear'), datos)
        self.assertRedirects(respuesta, reverse('correos_lista'), fetch_redirect_response=False)
        registro = Correos.objects.get()
        self.assertEqual(registro.tipo, 'Correo')
        self.assertIsNone(registro.empleado)

    def test_estatus_invalido_se_rechaza(self):
        datos = {'tipo': 'Correo', 'correo_asignado': 'ana@ejemplo.com', 'estatus': 'Quizá'}
        respuesta = self.client.post(reverse('correo_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Correos.objects.count(), 0)


class AsignacionesTests(PruebasTI):

    def setUp(self):
        super().setUp()
        self.equipo = Equipo.objects.create(**DATOS_EQUIPO)
        self.ana = Empleado.objects.create(
            nombre='Ana', apellido='López', departamento=Departamento.CHG,
        )
        self.beto = Empleado.objects.create(
            nombre='Beto', apellido='Ruiz', departamento=Departamento.GOP,
        )

    def datos(self, empleado=None, estatus='Asignado', **extra):
        datos = {
            'equipo': self.equipo.pk,
            'empleado': (empleado or self.ana).pk,
            'estatus': estatus,
            'entregado_por': 'TI',
            'fecha_devolucion': '',
        }
        datos.update(extra)
        return datos

    def archivo(self, nombre='acta.pdf', contenido=b'%PDF-1.4 prueba'):
        return SimpleUploadedFile(nombre, contenido)

    # -- Un equipo, un responsable ------------------------------------------------------

    def test_asignacion_valida_se_crea(self):
        respuesta = self.client.post(reverse('asignacion_crear'), self.datos())
        self.assertRedirects(
            respuesta, reverse('asignaciones_lista'), fetch_redirect_response=False,
        )
        self.assertEqual(Asignacion.objects.count(), 1)

    def test_equipo_no_se_asigna_a_dos_personas(self):
        self.client.post(reverse('asignacion_crear'), self.datos(self.ana))
        respuesta = self.client.post(reverse('asignacion_crear'), self.datos(self.beto))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Asignacion.objects.count(), 1)
        self.assertTrue(any('asignación vigente' in m for m in self.mensajes(respuesta)))

    def test_equipo_se_puede_reasignar_despues_de_devolverlo(self):
        self.client.post(reverse('asignacion_crear'), self.datos(self.ana))
        primera = Asignacion.objects.get()
        self.client.post(
            reverse('asignacion_editar', args=[primera.pk]),
            self.datos(self.ana, estatus='Devuelto'),
        )
        respuesta = self.client.post(reverse('asignacion_crear'), self.datos(self.beto))
        self.assertRedirects(
            respuesta, reverse('asignaciones_lista'), fetch_redirect_response=False,
        )
        self.assertEqual(Asignacion.objects.count(), 2)

    def test_editar_la_propia_asignacion_no_choca_consigo_misma(self):
        asignacion = Asignacion.objects.create(
            equipo=self.equipo, empleado=self.ana, estatus='Asignado',
        )
        respuesta = self.client.post(
            reverse('asignacion_editar', args=[asignacion.pk]),
            self.datos(self.ana, entregado_por='Nuevo responsable'),
        )
        self.assertRedirects(
            respuesta, reverse('asignaciones_lista'), fetch_redirect_response=False,
        )
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.entregado_por, 'Nuevo responsable')

    def test_no_se_reactiva_una_devolucion_si_el_equipo_ya_esta_asignado(self):
        vieja = Asignacion.objects.create(
            equipo=self.equipo, empleado=self.ana, estatus='Devuelto',
        )
        Asignacion.objects.create(equipo=self.equipo, empleado=self.beto, estatus='Asignado')
        respuesta = self.client.post(
            reverse('asignacion_editar', args=[vieja.pk]),
            self.datos(self.ana, estatus='Asignado'),
        )
        self.assertEqual(respuesta.status_code, 200)
        vieja.refresh_from_db()
        self.assertEqual(vieja.estatus, 'Devuelto')

    def test_varias_devoluciones_del_mismo_equipo_no_chocan(self):
        self.client.post(reverse('asignacion_crear'), self.datos(self.ana, estatus='Devuelto'))
        respuesta = self.client.post(
            reverse('asignacion_crear'), self.datos(self.beto, estatus='Devuelto'),
        )
        self.assertRedirects(
            respuesta, reverse('asignaciones_lista'), fetch_redirect_response=False,
        )
        self.assertEqual(Asignacion.objects.count(), 2)

    def test_empleado_inexistente_se_rechaza(self):
        respuesta = self.client.post(
            reverse('asignacion_crear'), self.datos(empleado=mock.Mock(pk=99999)),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Asignacion.objects.count(), 0)

    def test_editar_corrige_la_fecha_de_asignacion(self):
        asignacion = Asignacion.objects.create(
            equipo=self.equipo, empleado=self.ana, estatus='Asignado',
        )
        self.client.post(
            reverse('asignacion_editar', args=[asignacion.pk]),
            self.datos(self.ana, fecha_asignacion='2026-01-15'),
        )
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.fecha_asignacion, date(2026, 1, 15))

    # -- Archivos (actas de resguardo y devolución) ---------------------------------------

    def test_acta_pdf_valida_se_guarda(self):
        datos = self.datos(archivo_resguardo=self.archivo())
        respuesta = self.client.post(reverse('asignacion_crear'), datos)
        self.assertRedirects(
            respuesta, reverse('asignaciones_lista'), fetch_redirect_response=False,
        )
        asignacion = Asignacion.objects.get()
        self.assertTrue(asignacion.archivo_resguardo.name.endswith('.pdf'))
        self.assertTrue(default_storage.exists(asignacion.archivo_resguardo.name))

    def test_extension_no_permitida_se_rechaza(self):
        datos = self.datos(archivo_resguardo=self.archivo('acta.html', b'<script>alert(1)</script>'))
        respuesta = self.client.post(reverse('asignacion_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Asignacion.objects.count(), 0)
        self.assertTrue(any('no permitido' in m for m in self.mensajes(respuesta)))

    def test_la_extension_se_valida_tambien_en_el_acta_de_devolucion(self):
        datos = self.datos(archivo_devolucion=self.archivo('acta.exe', b'MZ'))
        respuesta = self.client.post(reverse('asignacion_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Asignacion.objects.count(), 0)

    @override_settings(MAX_UPLOAD_MB=0)
    def test_archivo_que_excede_el_tamano_maximo_se_rechaza(self):
        datos = self.datos(archivo_resguardo=self.archivo())
        respuesta = self.client.post(reverse('asignacion_crear'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Asignacion.objects.count(), 0)
        self.assertTrue(any('tamaño máximo' in m for m in self.mensajes(respuesta)))

    def test_editar_sin_subir_archivo_conserva_el_actual(self):
        self.client.post(
            reverse('asignacion_crear'), self.datos(archivo_resguardo=self.archivo()),
        )
        asignacion = Asignacion.objects.get()
        nombre = asignacion.archivo_resguardo.name
        self.client.post(
            reverse('asignacion_editar', args=[asignacion.pk]),
            self.datos(entregado_por='Otro'),
        )
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.archivo_resguardo.name, nombre)
        self.assertTrue(default_storage.exists(nombre))

    def test_marcar_eliminar_quita_el_archivo_actual_y_lo_borra_del_disco(self):
        self.client.post(
            reverse('asignacion_crear'), self.datos(archivo_resguardo=self.archivo()),
        )
        asignacion = Asignacion.objects.get()
        nombre = asignacion.archivo_resguardo.name
        respuesta = self.client.post(
            reverse('asignacion_editar', args=[asignacion.pk]),
            self.datos(eliminar_archivo_resguardo='on'),
        )
        self.assertRedirects(
            respuesta, reverse('asignaciones_lista'), fetch_redirect_response=False,
        )
        asignacion.refresh_from_db()
        self.assertFalse(asignacion.archivo_resguardo)
        self.assertFalse(default_storage.exists(nombre))
