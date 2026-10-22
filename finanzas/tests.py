import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from finanzas.models import (
    CuentaBancaria, Expediente, ExpedienteDocumento, FacturaCliente,
    FacturaProveedor, PagoCliente, PagoProveedor,
)
from ti.models import Asignacion, Empleado, Equipo


def crear_usuario(username, departamento=None, superuser=False):
    if superuser:
        return User.objects.create_superuser(username, password="x")
    user = User.objects.create_user(username, password="x")
    if departamento:
        Empleado.objects.create(
            usuario=user, nombre=username, apellido="Prueba", departamento=departamento
        )
    return user


class BaseFinanzasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_cpf = crear_usuario("cpf", "CPF")
        cls.user_cit = crear_usuario("cit", "CIT")
        cls.user_chg = crear_usuario("chg", "CHG")
        cls.admin = crear_usuario("admin", superuser=True)

        cls.cliente = Expediente.objects.create(
            tipo="Cliente", tipo_contribuyente="PM", razon_social="Cliente SA", rfc="CLI010101AAA"
        )
        cls.proveedor = Expediente.objects.create(
            tipo="Proveedor", tipo_contribuyente="PM", razon_social="Proveedor SA", rfc="PRO010101AAA"
        )

    def factura_cliente(self, total="1000.00", numero="F-001"):
        return FacturaCliente.objects.create(
            expediente=self.cliente, fecha_factura=date.today(), factura=numero,
            subtotal=Decimal(total), total=Decimal(total),
            fecha_vencimiento=date.today() + timedelta(days=30),
        )

    def factura_proveedor(self, total="1000.00", numero="P-001"):
        return FacturaProveedor.objects.create(
            expediente=self.proveedor, fecha_factura=date.today(), factura=numero,
            subtotal=Decimal(total), total=Decimal(total),
            fecha_vencimiento=date.today() + timedelta(days=30),
        )

    def pagar_cliente(self, factura, monto):
        return PagoCliente.objects.create(factura=factura, fecha_pago=date.today(), monto=Decimal(monto))

    def post_pago(self, url_name, pk, monto):
        return self.client.post(
            reverse(url_name, args=[pk]),
            {"monto": monto, "fecha_pago": date.today().isoformat(), "metodo_pago": "Transferencia"},
        )


class ControlDeAccesoTests(BaseFinanzasTest):

    def test_anonimo_va_al_login(self):
        r = self.client.get(reverse("finanzas_dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_usuario_de_ti_no_entra_a_finanzas(self):
        self.client.login(username="cit", password="x")
        for url in (reverse("finanzas_dashboard"), reverse("facturas_lista"), reverse("expedientes_lista")):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertEqual(r["Location"], reverse("dashboard"))

    def test_usuario_de_finanzas_no_entra_a_ti(self):
        self.client.login(username="cpf", password="x")
        r = self.client.get(reverse("ti_dashboard"))
        self.assertEqual(r.status_code, 302)

    def test_usuario_de_finanzas_si_entra(self):
        self.client.login(username="cpf", password="x")
        self.assertEqual(self.client.get(reverse("finanzas_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("facturas_lista")).status_code, 200)

    def test_superusuario_entra_a_todo(self):
        self.client.login(username="admin", password="x")
        self.assertEqual(self.client.get(reverse("finanzas_dashboard")).status_code, 200)

    def test_usuario_sin_empleado_no_entra(self):
        User.objects.create_user("sinemp", password="x")
        self.client.login(username="sinemp", password="x")
        self.assertEqual(self.client.get(reverse("finanzas_dashboard")).status_code, 302)


class PagosClientesTests(BaseFinanzasTest):

    def setUp(self):
        self.client.login(username="cpf", password="x")

    def test_pago_parcial_y_total_actualizan_estatus(self):
        f = self.factura_cliente("1000.00")
        self.post_pago("registrar_pago", f.pk, "400.00")
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Parcial")
        self.post_pago("registrar_pago", f.pk, "600.00")
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pagada")
        self.assertEqual(f.total_pagado, Decimal("1000.00"))

    def test_no_permite_sobrepago(self):
        f = self.factura_cliente("1000.00")
        self.post_pago("registrar_pago", f.pk, "1000.01")
        self.assertEqual(PagoCliente.objects.count(), 0)
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pendiente")

    def test_no_permite_monto_cero_ni_texto(self):
        f = self.factura_cliente()
        self.post_pago("registrar_pago", f.pk, "0")
        self.post_pago("registrar_pago", f.pk, "abc")
        self.assertEqual(PagoCliente.objects.count(), 0)

    def test_eliminar_pago_recalcula_estatus(self):
        f = self.factura_cliente("1000.00")
        pago = self.pagar_cliente(f, "1000.00")
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pagada")
        self.client.post(reverse("pago_eliminar", args=[pago.pk]))
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pendiente")

    def test_delete_directo_del_modelo_tambien_recalcula(self):
        # Antes PagoCliente.delete() no recalculaba (solo lo hacia la vista).
        f = self.factura_cliente("1000.00")
        pago = self.pagar_cliente(f, "1000.00")
        pago.delete()
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pendiente")

    def test_editar_pago_respeta_tope(self):
        f = self.factura_cliente("1000.00")
        pago = self.pagar_cliente(f, "400.00")
        url = reverse("pago_editar", args=[pago.pk])
        base = {"fecha_pago": date.today().isoformat(), "metodo_pago": "Transferencia"}
        self.client.post(url, {**base, "monto": "1200.00"})
        pago.refresh_from_db()
        self.assertEqual(pago.monto, Decimal("400.00"))
        self.client.post(url, {**base, "monto": "1000.00"})
        pago.refresh_from_db()
        f.refresh_from_db()
        self.assertEqual(pago.monto, Decimal("1000.00"))
        self.assertEqual(f.estatus, "Pagada")

    def test_no_se_puede_pagar_factura_cancelada(self):
        f = self.factura_cliente()
        f.estatus = "Cancelada"
        f.save()
        self.post_pago("registrar_pago", f.pk, "100")
        self.assertEqual(PagoCliente.objects.count(), 0)

    def test_factura_con_pagos_no_se_puede_borrar(self):
        f = self.factura_cliente()
        self.pagar_cliente(f, "100.00")
        with self.assertRaises(ProtectedError):
            f.delete()

    def test_total_pagado_es_decimal_aunque_no_haya_pagos(self):
        f = self.factura_cliente()
        self.assertEqual(f.total_pagado, Decimal("0.00"))
        self.assertIsInstance(f.total_pagado, Decimal)


class PagosProveedoresTests(BaseFinanzasTest):

    def setUp(self):
        self.client.login(username="cpf", password="x")

    def test_no_permite_sobrepago(self):
        f = self.factura_proveedor("500.00")
        self.post_pago("registrar_proveedor_pago", f.pk, "500.01")
        self.assertEqual(PagoProveedor.objects.count(), 0)

    def test_pago_total_marca_pagada_y_borrar_revierte(self):
        f = self.factura_proveedor("500.00")
        self.post_pago("registrar_proveedor_pago", f.pk, "500.00")
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pagada")
        pago = f.pagos.get()
        self.client.post(reverse("pago_proveedor_eliminar", args=[pago.pk]))
        f.refresh_from_db()
        self.assertEqual(f.estatus, "Pendiente")


class DashboardFinanzasTests(BaseFinanzasTest):

    def test_dashboard_muestra_cifras_reales(self):
        f = self.factura_cliente("1000.00")
        self.pagar_cliente(f, "250.00")
        p = self.factura_proveedor("800.00")
        vencida = self.factura_proveedor("100.00", numero="P-002")
        vencida.fecha_vencimiento = date.today() - timedelta(days=5)
        vencida.save()
        CuentaBancaria.objects.create(
            alias="Principal", banco="Banco", numero_cuenta="123", saldo_inicial=Decimal("5000.00")
        )

        self.client.login(username="cpf", password="x")
        r = self.client.get(reverse("finanzas_dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["por_cobrar"], Decimal("750.00"))
        self.assertEqual(r.context["por_pagar"], Decimal("900.00"))
        self.assertEqual(r.context["total_ingresos"], Decimal("250.00"))
        self.assertEqual(r.context["balance_actual"], Decimal("5000.00"))
        self.assertEqual(r.context["cxp_vencidas"], 1)
        self.assertEqual(p.pagos.count(), 0)


class SubidaYMediaTests(BaseFinanzasTest):

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_rechaza_extension_peligrosa(self):
        self.client.login(username="cpf", password="x")
        archivo = SimpleUploadedFile("virus.exe", b"MZ")
        self.client.post(
            reverse("expediente_documento_subir", args=[self.cliente.pk]),
            {"categoria": "INE", "archivo": archivo},
        )
        self.assertEqual(ExpedienteDocumento.objects.count(), 0)

    def test_acepta_pdf(self):
        self.client.login(username="cpf", password="x")
        archivo = SimpleUploadedFile("ine.pdf", b"%PDF-1.4 prueba")
        self.client.post(
            reverse("expediente_documento_subir", args=[self.cliente.pk]),
            {"categoria": "INE", "archivo": archivo},
        )
        self.assertEqual(ExpedienteDocumento.objects.count(), 1)

    def _crear_archivo(self, ruta):
        import os
        destino = os.path.join(self.media, ruta)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(b"%PDF-1.4 secreto")

    def test_media_exige_login(self):
        self._crear_archivo("finanzas/expedientes/2026/07/ine.pdf")
        r = self.client.get("/media/finanzas/expedientes/2026/07/ine.pdf")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_media_de_finanzas_denegada_a_otro_departamento(self):
        self._crear_archivo("finanzas/expedientes/2026/07/ine.pdf")
        self.client.login(username="cit", password="x")
        r = self.client.get("/media/finanzas/expedientes/2026/07/ine.pdf")
        self.assertEqual(r.status_code, 403)

    def test_media_de_finanzas_permitida_a_finanzas(self):
        self._crear_archivo("finanzas/expedientes/2026/07/ine.pdf")
        self.client.login(username="cpf", password="x")
        r = self.client.get("/media/finanzas/expedientes/2026/07/ine.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 secreto")

        
    def test_documento_cpf_denegado_a_usuario_cit(self):
        self._crear_archivo("documentos/cpf/ine.pdf")
        self.client.login(username="cit", password="x")

        r = self.client.get("/media/documentos/cpf/ine.pdf")

        self.assertEqual(r.status_code, 403)

    def test_documento_cpf_permitido_a_usuario_cpf(self):
        self._crear_archivo("documentos/cpf/ine.pdf")
        self.client.login(username="cpf", password="x")

        r = self.client.get("/media/documentos/cpf/ine.pdf")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            b"".join(r.streaming_content),
            b"%PDF-1.4 secreto",
        )

    def test_documento_chg_denegado_a_usuario_cpf(self):
        self._crear_archivo("documentos/chg/contrato.pdf")
        self.client.login(username="cpf", password="x")

        r = self.client.get("/media/documentos/chg/contrato.pdf")

        self.assertEqual(r.status_code, 403)

    def test_documento_cit_denegado_a_usuario_cpf(self):
        self._crear_archivo("documentos/cit/manual.pdf")
        self.client.login(username="cpf", password="x")

        r = self.client.get("/media/documentos/cit/manual.pdf")

        self.assertEqual(r.status_code, 403)


    def test_media_bloquea_path_traversal(self):
        self.client.login(username="admin", password="x")
        r = self.client.get("/media/../config/settings.py")
        self.assertEqual(r.status_code, 404)


class TIAsignacionesTests(BaseFinanzasTest):

    def test_un_equipo_no_se_asigna_dos_veces(self):
        equipo = Equipo.objects.create(tipo="Computadora", marca="HP", modelo="X", numero_serie="SN1")
        e1 = Empleado.objects.create(nombre="A", apellido="A", departamento="CIT")
        e2 = Empleado.objects.create(nombre="B", apellido="B", departamento="CIT")
        self.client.login(username="cit", password="x")
        url = reverse("asignacion_crear")
        self.client.post(url, {"equipo": equipo.pk, "empleado": e1.pk, "estatus": "Asignado"})
        self.client.post(url, {"equipo": equipo.pk, "empleado": e2.pk, "estatus": "Asignado"})
        self.assertEqual(Asignacion.objects.filter(equipo=equipo).count(), 1)

    def test_no_se_borra_empleado_con_asignaciones(self):
        equipo = Equipo.objects.create(tipo="Mouse", marca="M", modelo="1", numero_serie="SN2")
        emp = Empleado.objects.create(nombre="A", apellido="A", departamento="CIT")
        Asignacion.objects.create(equipo=equipo, empleado=emp, estatus="Asignado")
        self.client.login(username="cit", password="x")
        self.client.post(reverse("empleado_eliminar", args=[emp.pk]))
        self.assertTrue(Empleado.objects.filter(pk=emp.pk).exists())

    def test_post_incompleto_ya_no_da_error_500(self):
        self.client.login(username="cit", password="x")
        r = self.client.post(reverse("asignacion_crear"), {})
        self.assertEqual(r.status_code, 200)
