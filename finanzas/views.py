from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect


from .models import Expediente, ExpedienteDocumento, FacturaCliente, PagoCliente, FacturaProveedor, PagoProveedor, PresupuestoAnual, PresupuestoIngreso, ConceptoIngreso, PresupuestoGasto, PartidaGasto, PresupuestoIngresoMensual, PresupuestoGastoMensual, CategoriaMovimiento, ProgramaPago, MovimientoPrograma,CuentaBancaria, MovimientoBancario
from .validators import validar_rfc


@never_cache
@login_required
def dashboard(request):
    """
    Dashboard principal del módulo de Finanzas.
    """

    context = {
        "total_ingresos": "$0.00",
        "total_egresos": "$0.00",
        "balance_actual": "$0.00",
        "alertas_financieras": 0,
    }

    return render(
        request,
        "finanzas/finanzas_dashboard.html",
        context,
    )


# =====================================================
# HELPERS
# =====================================================

def _dias_credito_desde_post(post):
    """Castea dias_credito a int de forma segura. Devuelve 0 si no es válido."""
    try:
        return int(post.get('dias_credito') or 0)
    except (TypeError, ValueError):
        return 0


def _limite_credito_desde_post(post):
    """Castea limite_credito a Decimal de forma segura. Devuelve None si no es válido."""
    valor = post.get('limite_credito')
    if not valor:
        return None
    try:
        return Decimal(valor)
    except InvalidOperation:
        return None


def _datos_expediente_desde_post(post, tipo_contribuyente, rfc):
    """
    Arma el diccionario de campos comunes entre crear y editar expediente,
    evitando duplicar la misma lista larga de request.POST.get(...) dos veces.
    """
    tipo = post.get('tipo')

    return {
        'tipo': tipo,
        'tipo_contribuyente': tipo_contribuyente,
        'nombre_comercial': post.get('nombre_comercial', ''),
        'rfc': rfc or None,
        'regimen_fiscal': post.get('regimen_fiscal', ''),
        'contacto_nombre': post.get('contacto_nombre', ''),
        'contacto_telefono': post.get('contacto_telefono', ''),
        'contacto_email': post.get('contacto_email', ''),
        'correo_pagos': post.get('correo_pagos', '') if tipo == Expediente.Tipo.PROVEEDOR else '',
        'direccion': post.get('direccion', ''),
        'dias_credito': _dias_credito_desde_post(post),
        'limite_credito': _limite_credito_desde_post(post),
        'estatus': post.get('estatus', Expediente.Estatus.ACTIVO),
        'observaciones': post.get('observaciones', ''),
    }


# =====================================================
# LISTADO DE EXPEDIENTES
# =====================================================

@never_cache
@login_required
def expedientes_lista(request):

    busqueda = request.GET.get('q', '')
    tipo = request.GET.get('tipo', '')
    estatus = request.GET.get('estatus', '')

    expedientes = Expediente.objects.all()

    if busqueda:
        expedientes = expedientes.filter(
            Q(razon_social__icontains=busqueda) |
            Q(nombre_comercial__icontains=busqueda) |
            Q(rfc__icontains=busqueda)
        )

    if tipo:
        expedientes = expedientes.filter(tipo=tipo)

    if estatus:
        expedientes = expedientes.filter(estatus=estatus)

    paginator = Paginator(expedientes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'finanzas/expedientes/lista.html',
        {
            'expedientes': page_obj,
            'page_obj': page_obj,
            'busqueda': busqueda,
            'tipo_actual': tipo,
            'estatus_actual': estatus,
            'tipos': Expediente.Tipo.choices,
            'estatuses': Expediente.Estatus.choices,
        }
    )


# =====================================================
# CREAR EXPEDIENTE
# =====================================================

@never_cache
@login_required
def expediente_crear(request):

    if request.method == 'POST':

        tipo_contribuyente = request.POST.get('tipo_contribuyente')
        rfc = (request.POST.get('rfc') or "").strip().upper()

        valido, mensaje = validar_rfc(tipo_contribuyente, rfc)

        if not valido:
            messages.error(request, mensaje)
            return render(
                request,
                'finanzas/expedientes/crear.html',
                {
                    'tipos': Expediente.Tipo.choices,
                    'estatuses': Expediente.Estatus.choices,
                    'tipos_contribuyente': Expediente.TipoContribuyente.choices,
                    'regimenes': Expediente.RegimenFiscal.choices,
                    'estatus_default': Expediente.Estatus.ACTIVO,
                }
            )

        datos = _datos_expediente_desde_post(request.POST, tipo_contribuyente, rfc)

        # Persona Física: razon_social se arma a partir del nombre
        # Persona Moral: razon_social viene directo del formulario
        if tipo_contribuyente == Expediente.TipoContribuyente.FISICA:
            nombres = request.POST.get('nombres', '')
            apellido_paterno = request.POST.get('apellido_paterno', '')
            apellido_materno = request.POST.get('apellido_materno', '')
            datos.update({
                'nombres': nombres,
                'apellido_paterno': apellido_paterno,
                'apellido_materno': apellido_materno,
                'razon_social': f"{nombres} {apellido_paterno} {apellido_materno}".strip(),
            })
        else:
            datos.update({
                'nombres': '',
                'apellido_paterno': '',
                'apellido_materno': '',
                'razon_social': request.POST.get('razon_social', ''),
            })

        Expediente.objects.create(**datos)

        messages.success(request, 'Expediente creado correctamente.')

        return redirect('expedientes_lista')

    return render(
        request,
        'finanzas/expedientes/crear.html',
        {
            'tipos': Expediente.Tipo.choices,
            'estatuses': Expediente.Estatus.choices,
            'tipos_contribuyente': Expediente.TipoContribuyente.choices,
            'regimenes': Expediente.RegimenFiscal.choices,
            'estatus_default': Expediente.Estatus.ACTIVO,
        }
    )


# =====================================================
# EDITAR EXPEDIENTE
# =====================================================

@never_cache
@login_required
def expediente_editar(request, pk):

    expediente = get_object_or_404(Expediente, pk=pk)

    if request.method == 'POST':

        tipo_contribuyente = request.POST.get('tipo_contribuyente')
        rfc = (request.POST.get('rfc') or "").strip().upper()

        valido, mensaje = validar_rfc(tipo_contribuyente, rfc, expediente_id=pk)

        if not valido:
            messages.error(request, mensaje)
            return render(
                request,
                'finanzas/expedientes/editar.html',
                {
                    'expediente': expediente,
                    'tipos': Expediente.Tipo.choices,
                    'estatuses': Expediente.Estatus.choices,
                    'tipos_contribuyente': Expediente.TipoContribuyente.choices,
                    'regimenes': Expediente.RegimenFiscal.choices,
                }
            )

        datos = _datos_expediente_desde_post(request.POST, tipo_contribuyente, rfc)

        if tipo_contribuyente == Expediente.TipoContribuyente.FISICA:
            nombres = request.POST.get('nombres', '')
            apellido_paterno = request.POST.get('apellido_paterno', '')
            apellido_materno = request.POST.get('apellido_materno', '')
            datos.update({
                'nombres': nombres,
                'apellido_paterno': apellido_paterno,
                'apellido_materno': apellido_materno,
                'razon_social': f"{nombres} {apellido_paterno} {apellido_materno}".strip(),
            })
        else:
            datos.update({
                'nombres': '',
                'apellido_paterno': '',
                'apellido_materno': '',
                'razon_social': request.POST.get('razon_social', ''),
            })

        for campo, valor in datos.items():
            setattr(expediente, campo, valor)

        expediente.save()

        messages.success(request, 'Expediente actualizado correctamente.')

        return redirect('expedientes_lista')

    return render(
        request,
        'finanzas/expedientes/editar.html',
        {
            'expediente': expediente,
            'tipos': Expediente.Tipo.choices,
            'estatuses': Expediente.Estatus.choices,
            'tipos_contribuyente': Expediente.TipoContribuyente.choices,
            'regimenes': Expediente.RegimenFiscal.choices,
        }
    )


# =====================================================
# ELIMINAR EXPEDIENTE
# =====================================================

@never_cache
@login_required
def expediente_eliminar(request, pk):

    expediente = get_object_or_404(Expediente, pk=pk)

    # NOTA: Expediente no tiene campo "archivo" propio (eso vive en
    # ExpedienteDocumento). Además, ExpedienteDocumento y FacturaCliente usan
    # on_delete=PROTECT hacia Expediente, así que Django ya impide borrar un
    # expediente que tenga documentos o facturas asociadas: solo hace falta
    # capturar esa excepción y mostrar un mensaje claro.
    if request.method == 'POST':

        try:
            expediente.delete()
        except models.ProtectedError:
            messages.error(
                request,
                'No se puede eliminar el expediente porque tiene documentos o facturas '
                'relacionadas. Elimine primero esos registros, o bien cambie el '
                'expediente a estatus Inactivo en lugar de borrarlo.'
            )
            return redirect('expedientes_lista')

        messages.success(request, 'Expediente eliminado correctamente.')

        return redirect('expedientes_lista')

    # GET: muestra la página de confirmación antes de borrar de verdad.
    return render(
        request,
        'finanzas/expedientes/eliminar.html',
        {'expediente': expediente}
    )


# =====================================================
# DETALLE DEL EXPEDIENTE
# =====================================================

@never_cache
@login_required
def expediente_detalle(request, pk):

    expediente = get_object_or_404(Expediente, pk=pk)

    categorias = ExpedienteDocumento.Categoria.choices

    # Orden según la posición de cada categoría dentro del TextChoices
    orden_categoria = Case(
        *[When(categoria=valor, then=pos) for pos, (valor, texto) in enumerate(categorias)]
    )

    documentos = (
        expediente.documentos
        .all()
        .order_by(orden_categoria, '-fecha_subida')
    )

    return render(
        request,
        'finanzas/expedientes/detalle.html',
        {
            'expediente': expediente,
            'documentos': documentos,
            'categorias': categorias,
        }
    )


# =====================================================
# SUBIR DOCUMENTO AL EXPEDIENTE
# =====================================================

@login_required
@require_POST
def expediente_documento_subir(request, pk):

    expediente = get_object_or_404(Expediente, pk=pk)

    categoria = request.POST.get('categoria')
    archivo = request.FILES.get('archivo')

    if not categoria or not archivo:
        messages.error(request, 'Debe seleccionar una categoría y un archivo.')
        return redirect('expediente_detalle', pk=pk)

    ExpedienteDocumento.objects.create(
        expediente=expediente,
        categoria=categoria,
        archivo=archivo,
    )

    messages.success(request, 'Documento agregado correctamente.')

    return redirect('expediente_detalle', pk=pk)


# =====================================================
# ELIMINAR DOCUMENTO
# =====================================================

@login_required
@require_POST
def expediente_documento_eliminar(request, pk):

    documento = get_object_or_404(ExpedienteDocumento, pk=pk)

    expediente_id = documento.expediente.pk

    # Elimina el archivo físico del storage antes de borrar el registro
    documento.archivo.delete(save=False)
    documento.delete()

    messages.success(request, 'Documento eliminado correctamente.')

    return redirect('expediente_detalle', pk=expediente_id)


# =====================================================
# LISTADO DE FACTURAS (CxC)
# =====================================================

@login_required
@never_cache
def facturas_lista(request):

    busqueda = request.GET.get("q", "")
    estatus = request.GET.get("estatus", "")

    facturas_base = (
        FacturaCliente.objects
        .select_related("expediente")
        .all()
    )

    # Las facturas canceladas ya no representan una cuenta por cobrar real
    # (nunca tienen pagos, por regla en factura_cancelar), así que se excluyen
    # de los indicadores para no inflar totales ni marcar como "vencidas"
    # facturas que en realidad ya no están activas. Sí se conservan en el
    # listado/búsqueda de abajo, para trazabilidad.
    facturas_activas = facturas_base.exclude(estatus=FacturaCliente.Estatus.CANCELADA)

    # --- Indicadores (calculados sobre el total activo, sin aplicar filtros de búsqueda) ---
    # total_pagado, saldo_pendiente y vencida son @property en el modelo (se derivan
    # de la suma de PagoCliente relacionados), no columnas reales.
    #
    # IMPORTANTE: con soporte multi-moneda, no se puede sumar el campo "total" en
    # crudo entre facturas de distinta moneda (mezclaría MXN con USD como si fueran
    # la misma unidad). Cada factura se convierte a MXN con su propio tipo_cambio
    # antes de sumarla, para que las tarjetas siempre muestren un total en pesos.
    monto_mxn = ExpressionWrapper(
        F("total") * F("tipo_cambio"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    total_facturado = facturas_activas.aggregate(t=Sum(monto_mxn))["t"] or 0

    pago_mxn = ExpressionWrapper(
        F("monto") * F("factura__tipo_cambio"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    total_cobrado = (
        PagoCliente.objects
        .filter(factura__in=facturas_activas)
        .aggregate(t=Sum(pago_mxn))["t"] or 0
    )

    saldo_pendiente = total_facturado - total_cobrado

    # Para "vencidas" comparamos el saldo dentro de la MISMA moneda de cada
    # factura (total vs. lo pagado de esa factura) — aquí no hace falta convertir,
    # porque es una comparación interna, no una suma acumulada entre monedas.
    total_vencidas = (
        facturas_activas
        .annotate(
            pagado_calc=Coalesce(
                Sum("pagos__monto"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .filter(
            fecha_vencimiento__lt=timezone.now().date(),
            total__gt=F("pagado_calc"),
        )
        .count()
    )

    # --- Filtros de búsqueda para la tabla ---
    # Aquí sí se parte de facturas_base (no facturas_activas): el usuario debe
    # poder seguir viendo/buscando facturas canceladas en el listado.
    facturas = facturas_base.order_by("-fecha_factura")

    if busqueda:
        facturas = facturas.filter(
            Q(factura__icontains=busqueda) |
            Q(expediente__razon_social__icontains=busqueda) |
            Q(expediente__nombres__icontains=busqueda) |
            Q(expediente__rfc__icontains=busqueda)
        )

    if estatus:
        facturas = facturas.filter(estatus=estatus)

    paginator = Paginator(facturas, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        "finanzas/cxc/lista.html",
        {
            "facturas": page_obj,
            "page_obj": page_obj,
            "busqueda": busqueda,
            "estatus_actual": estatus,
            "estatuses": FacturaCliente.Estatus.choices,
            "total_facturado": total_facturado,
            "total_cobrado": total_cobrado,
            "saldo_pendiente": saldo_pendiente,
            "total_vencidas": total_vencidas,
        },
    )


# =====================================================
# CREAR FACTURA (CxC)
# =====================================================

@login_required
@never_cache
def factura_crear(request):

    # CxC son facturas que deben los CLIENTES, no los proveedores.
    # Filtramos a expedientes tipo Cliente o Ambos para no permitir
    # capturar por error una factura de cliente contra un proveedor puro.
    expedientes_clientes = Expediente.objects.filter(
        tipo__in=[Expediente.Tipo.CLIENTE, Expediente.Tipo.AMBOS]
    )

    contexto_base = {
        "expedientes": expedientes_clientes,
        "estatuses": FacturaCliente.Estatus.choices,
        "monedas": FacturaCliente.Moneda.choices,
    }

    if request.method == "POST":

        expediente_id = request.POST.get("expediente")

        if not expediente_id:
            messages.error(request, "Debe seleccionar un cliente.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        try:
            expediente = get_object_or_404(Expediente, pk=expediente_id)
        except (ValueError, ValidationError):
            messages.error(request, "El cliente seleccionado no es válido.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        if expediente.tipo not in (Expediente.Tipo.CLIENTE, Expediente.Tipo.AMBOS):
            messages.error(
                request,
                f"{expediente.nombre_completo} está registrado como Proveedor, "
                "no se le pueden generar facturas de Cuentas por Cobrar."
            )
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        # --- Número de factura: requerido, único, y normalizado a mayúsculas ---
        factura_num = (request.POST.get("factura") or "").strip().upper()
        if not factura_num:
            messages.error(request, "Debe especificar el número de factura.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        if FacturaCliente.objects.filter(factura=factura_num).exists():
            messages.error(
                request,
                f"Ya existe una factura registrada con el número {factura_num}."
            )
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        # --- Moneda y tipo de cambio ---
        moneda = request.POST.get("moneda", FacturaCliente.Moneda.MXN)
        if moneda not in FacturaCliente.Moneda.values:
            messages.error(request, "Moneda no válida.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        if moneda == FacturaCliente.Moneda.MXN:
            # En pesos el tipo de cambio siempre es 1, sin importar lo que
            # mande el formulario (el campo se deshabilita en el HTML cuando
            # la moneda es MXN, pero igual lo forzamos aquí por seguridad).
            tipo_cambio = Decimal("1.0000")
        else:
            try:
                tipo_cambio = Decimal(request.POST.get("tipo_cambio") or "0")
            except InvalidOperation:
                messages.error(request, "El tipo de cambio debe ser un número válido.")
                return render(request, "finanzas/cxc/crear.html", contexto_base)

            if tipo_cambio <= 0:
                messages.error(
                    request,
                    "Debe especificar un tipo de cambio mayor a cero para moneda distinta a MXN."
                )
                return render(request, "finanzas/cxc/crear.html", contexto_base)

        # --- Subtotal e IVA: el modelo los requiere (no tienen default) ---
        # El total se calcula en el servidor a partir de subtotal + iva, en vez de
        # confiar en un campo "total" que mande el navegador, para que siempre
        # cuadre con la suma real.
        try:
            subtotal = Decimal(request.POST.get("subtotal") or "0")
            iva = Decimal(request.POST.get("iva") or "0")
        except InvalidOperation:
            messages.error(request, "Subtotal e IVA deben ser números válidos.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        if subtotal <= 0:
            messages.error(request, "El subtotal debe ser mayor a cero.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        if iva < 0:
            messages.error(request, "El IVA no puede ser negativo.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        total = subtotal + iva

        # --- Validar fechas presentes y coherentes ---
        fecha_factura = request.POST.get("fecha_factura")
        fecha_vencimiento = request.POST.get("fecha_vencimiento")

        if not fecha_factura or not fecha_vencimiento:
            messages.error(request, "Debe especificar fecha de factura y de vencimiento.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        if fecha_vencimiento < fecha_factura:
            messages.error(
                request,
                "La fecha de vencimiento no puede ser anterior a la fecha de la factura."
            )
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        # --- Estatus: validado contra los choices reales, igual que moneda ---
        estatus = request.POST.get("estatus", FacturaCliente.Estatus.PENDIENTE)
        if estatus not in FacturaCliente.Estatus.values:
            messages.error(request, "Estatus no válido.")
            return render(request, "finanzas/cxc/crear.html", contexto_base)

        dias_credito = _dias_credito_desde_post(request.POST)

        # Mayúsculas en todos los campos de texto libre, EXCEPTO observaciones
        # (ahí se respeta tal cual lo escribe el usuario, por legibilidad de notas largas).
        orden_servicio = (request.POST.get("orden_servicio") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        FacturaCliente.objects.create(
            expediente=expediente,
            factura=factura_num,
            orden_servicio=orden_servicio,
            fecha_factura=fecha_factura,
            fecha_vencimiento=fecha_vencimiento,
            dias_credito=dias_credito,
            moneda=moneda,
            tipo_cambio=tipo_cambio,
            subtotal=subtotal,
            iva=iva,
            total=total,
            observaciones=observaciones,
            estatus=estatus,
        )

        messages.success(request, "Factura creada correctamente.")

        return redirect("facturas_lista")

    return render(request, "finanzas/cxc/crear.html", contexto_base)


# =====================================================
# DETALLE DE FACTURA (CxC)
# =====================================================

@login_required
@never_cache
def factura_detalle(request, pk):

    factura = get_object_or_404(
        FacturaCliente.objects.select_related("expediente"),
        pk=pk
    )

    pagos = factura.pagos.all()

    total_pagado = factura.total_pagado
    saldo = factura.saldo_pendiente

    # Equivalente en MXN, solo relevante cuando la factura no está en pesos.
    total_mxn = factura.total * factura.tipo_cambio if factura.moneda != FacturaCliente.Moneda.MXN else None

    return render(
        request,
        "finanzas/cxc/detalle.html",
        {
            "factura": factura,
            "pagos": pagos,
            "total_pagado": total_pagado,
            "saldo": saldo,
            "total_mxn": total_mxn,
        },
    )


# =====================================================
# REGISTRAR PAGO (CxC)
# =====================================================

@login_required
@never_cache
def registrar_pago(request, pk):

    factura = get_object_or_404(FacturaCliente, pk=pk)

    # No tiene sentido registrar pagos sobre facturas ya cerradas.
    if factura.estatus == FacturaCliente.Estatus.CANCELADA:
        messages.error(request, "No se pueden registrar pagos a una factura cancelada.")
        return redirect("factura_detalle", pk=pk)

    if factura.estatus == FacturaCliente.Estatus.PAGADA:
        messages.info(request, "Esta factura ya está completamente pagada.")
        return redirect("factura_detalle", pk=pk)

    contexto_base = {
        "factura": factura,
        "metodos": PagoCliente.MetodoPago.choices,
    }

    if request.method == "POST":

        try:
            monto = Decimal(request.POST.get("monto") or "0")
        except InvalidOperation:
            messages.error(request, "El monto debe ser un número válido.")
            return render(request, "finanzas/cxc/registrar_pago.html", contexto_base)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return render(request, "finanzas/cxc/registrar_pago.html", contexto_base)

        saldo_actual = factura.saldo_pendiente
        if monto > saldo_actual:
            messages.error(
                request,
                f"El monto (${monto}) no puede exceder el saldo pendiente (${saldo_actual})."
            )
            return render(request, "finanzas/cxc/registrar_pago.html", contexto_base)

        fecha_pago = request.POST.get("fecha_pago")
        if not fecha_pago:
            messages.error(request, "Debe especificar la fecha de pago.")
            return render(request, "finanzas/cxc/registrar_pago.html", contexto_base)

        fecha_deposito = request.POST.get("fecha_deposito") or None

        # Mayúsculas en referencia (identificador), observaciones se respeta tal cual.
        referencia = (request.POST.get("referencia") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        # PagoCliente.save() ya llama internamente a factura.actualizar_estatus(),
        # así que no hace falta actualizar el estatus manualmente aquí.
        PagoCliente.objects.create(
            factura=factura,
            fecha_pago=fecha_pago,
            fecha_deposito=fecha_deposito,
            monto=monto,
            metodo_pago=request.POST.get("metodo_pago", PagoCliente.MetodoPago.TRANSFERENCIA),
            referencia=referencia,
            observaciones=observaciones,
        )

        messages.success(request, "Pago registrado correctamente.")

        return redirect("factura_detalle", pk=pk)

    return render(request, "finanzas/cxc/registrar_pago.html", contexto_base)


# =====================================================
# EDITAR FACTURA (CxC)
# =====================================================

@login_required
@never_cache
def factura_editar(request, pk):

    factura = get_object_or_404(
        FacturaCliente.objects.select_related("expediente"),
        pk=pk
    )

    if factura.estatus == FacturaCliente.Estatus.CANCELADA:
        messages.error(request, "No se puede editar una factura cancelada.")
        return redirect("factura_detalle", pk=pk)

    # Mismo criterio que en factura_crear: solo clientes o "ambos", nunca
    # proveedores puros, para no permitir facturar CxC contra un proveedor.
    expedientes_clientes = Expediente.objects.filter(
        tipo__in=[Expediente.Tipo.CLIENTE, Expediente.Tipo.AMBOS]
    )

    contexto_base = {
        "factura": factura,
        "expedientes": expedientes_clientes,
        "monedas": FacturaCliente.Moneda.choices,
    }

    if request.method == "POST":

        expediente_id = request.POST.get("expediente")

        if not expediente_id:
            messages.error(request, "Debe seleccionar un cliente.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        try:
            expediente = get_object_or_404(Expediente, pk=expediente_id)
        except (ValueError, ValidationError):
            messages.error(request, "El cliente seleccionado no es válido.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        if expediente.tipo not in (Expediente.Tipo.CLIENTE, Expediente.Tipo.AMBOS):
            messages.error(
                request,
                f"{expediente.nombre_completo} está registrado como Proveedor, "
                "no se le pueden generar facturas de Cuentas por Cobrar."
            )
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        # --- Número de factura: requerido, único (excluyendo esta misma factura) ---
        factura_num = (request.POST.get("factura") or "").strip().upper()
        if not factura_num:
            messages.error(request, "Debe especificar el número de factura.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        if FacturaCliente.objects.filter(factura=factura_num).exclude(pk=pk).exists():
            messages.error(
                request,
                f"Ya existe otra factura registrada con el número {factura_num}."
            )
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        # --- Moneda y tipo de cambio ---
        moneda = request.POST.get("moneda", FacturaCliente.Moneda.MXN)
        if moneda not in FacturaCliente.Moneda.values:
            messages.error(request, "Moneda no válida.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        if moneda == FacturaCliente.Moneda.MXN:
            tipo_cambio = Decimal("1.0000")
        else:
            try:
                tipo_cambio = Decimal(request.POST.get("tipo_cambio") or "0")
            except InvalidOperation:
                messages.error(request, "El tipo de cambio debe ser un número válido.")
                return render(request, "finanzas/cxc/editar.html", contexto_base)

            if tipo_cambio <= 0:
                messages.error(
                    request,
                    "Debe especificar un tipo de cambio mayor a cero para moneda distinta a MXN."
                )
                return render(request, "finanzas/cxc/editar.html", contexto_base)

        # --- Subtotal e IVA ---
        try:
            subtotal = Decimal(request.POST.get("subtotal") or "0")
            iva = Decimal(request.POST.get("iva") or "0")
        except InvalidOperation:
            messages.error(request, "Subtotal e IVA deben ser números válidos.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        if subtotal <= 0:
            messages.error(request, "El subtotal debe ser mayor a cero.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        if iva < 0:
            messages.error(request, "El IVA no puede ser negativo.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        total = subtotal + iva

        # No se puede bajar el total por debajo de lo que ya se cobró: dejaría
        # un saldo negativo y rompería la lógica de actualizar_estatus().
        total_pagado_actual = factura.total_pagado
        if total < total_pagado_actual:
            messages.error(
                request,
                f"El nuevo total (${total}) no puede ser menor a lo ya cobrado "
                f"(${total_pagado_actual}). Considere registrar una nota de crédito "
                f"en vez de reducir el total por debajo de lo cobrado."
            )
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        # --- Fechas ---
        fecha_factura = request.POST.get("fecha_factura")
        fecha_vencimiento = request.POST.get("fecha_vencimiento")

        if not fecha_factura or not fecha_vencimiento:
            messages.error(request, "Debe especificar fecha de factura y de vencimiento.")
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        if fecha_vencimiento < fecha_factura:
            messages.error(
                request,
                "La fecha de vencimiento no puede ser anterior a la fecha de la factura."
            )
            return render(request, "finanzas/cxc/editar.html", contexto_base)

        dias_credito = _dias_credito_desde_post(request.POST)
        orden_servicio = (request.POST.get("orden_servicio") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        factura.expediente = expediente
        factura.factura = factura_num
        factura.orden_servicio = orden_servicio
        factura.fecha_factura = fecha_factura
        factura.fecha_vencimiento = fecha_vencimiento
        factura.dias_credito = dias_credito
        factura.moneda = moneda
        factura.tipo_cambio = tipo_cambio
        factura.subtotal = subtotal
        factura.iva = iva
        factura.total = total
        factura.observaciones = observaciones
        factura.save()

        # El estatus NO se captura en este formulario: se recalcula solo, con
        # base en lo ya pagado contra el nuevo total (por si subtotal/iva cambiaron).
        factura.actualizar_estatus()

        messages.success(request, "Factura actualizada correctamente.")

        return redirect("factura_detalle", pk=pk)

    return render(request, "finanzas/cxc/editar.html", contexto_base)


# =====================================================
# CANCELAR FACTURA (CxC)
# =====================================================

@login_required
@never_cache
def factura_cancelar(request, pk):

    factura = get_object_or_404(
        FacturaCliente.objects.select_related("expediente"),
        pk=pk
    )

    if factura.estatus == FacturaCliente.Estatus.CANCELADA:
        messages.info(request, "Esta factura ya está cancelada.")
        return redirect("factura_detalle", pk=pk)

    # No se cancela una factura que ya tiene dinero cobrado: eso dejaría un
    # pago sin factura activa asociada. Primero hay que resolver/eliminar
    # esos pagos (punto pendiente aparte).
    if factura.total_pagado > 0:
        messages.error(
            request,
            "No se puede cancelar una factura que ya tiene pagos registrados "
            f"(${factura.total_pagado}). Elimine o ajuste los pagos primero."
        )
        return redirect("factura_detalle", pk=pk)

    if request.method == "POST":
        factura.estatus = FacturaCliente.Estatus.CANCELADA
        factura.save(update_fields=["estatus"])

        messages.success(request, "Factura cancelada correctamente.")

        return redirect("factura_detalle", pk=pk)

    # GET: página de confirmación, mismo patrón que expediente_eliminar.
    return render(
        request,
        "finanzas/cxc/cancelar.html",
        {"factura": factura}
    )


# =====================================================
# EDITAR PAGO (CxC)
# =====================================================

@login_required
@never_cache
def pago_editar(request, pk):

    pago = get_object_or_404(
        PagoCliente.objects.select_related("factura", "factura__expediente"),
        pk=pk
    )
    factura = pago.factura

    if factura.estatus == FacturaCliente.Estatus.CANCELADA:
        messages.error(request, "No se pueden editar pagos de una factura cancelada.")
        return redirect("factura_detalle", pk=factura.pk)

    contexto_base = {
        "pago": pago,
        "factura": factura,
        "metodos": PagoCliente.MetodoPago.choices,
    }

    if request.method == "POST":

        try:
            monto = Decimal(request.POST.get("monto") or "0")
        except InvalidOperation:
            messages.error(request, "El monto debe ser un número válido.")
            return render(request, "finanzas/cxc/pago_editar.html", contexto_base)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return render(request, "finanzas/cxc/pago_editar.html", contexto_base)

        # El tope es el saldo pendiente ACTUAL más lo que este mismo pago ya
        # está aportando (porque ese monto original hay que "liberarlo" antes
        # de comparar, si no, el pago se compara contra un saldo que ya lo
        # incluye descontado y nunca dejaría subirlo).
        saldo_disponible = factura.saldo_pendiente + pago.monto
        if monto > saldo_disponible:
            messages.error(
                request,
                f"El monto (${monto}) no puede exceder el saldo disponible "
                f"(${saldo_disponible})."
            )
            return render(request, "finanzas/cxc/pago_editar.html", contexto_base)

        fecha_pago = request.POST.get("fecha_pago")
        if not fecha_pago:
            messages.error(request, "Debe especificar la fecha de pago.")
            return render(request, "finanzas/cxc/pago_editar.html", contexto_base)

        fecha_deposito = request.POST.get("fecha_deposito") or None
        referencia = (request.POST.get("referencia") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        pago.monto = monto
        pago.fecha_pago = fecha_pago
        pago.fecha_deposito = fecha_deposito
        pago.metodo_pago = request.POST.get("metodo_pago", pago.metodo_pago)
        pago.referencia = referencia
        pago.observaciones = observaciones

        # PagoCliente.save() ya llama internamente a factura.actualizar_estatus().
        pago.save()

        messages.success(request, "Pago actualizado correctamente.")

        return redirect("factura_detalle", pk=factura.pk)

    return render(request, "finanzas/cxc/pago_editar.html", contexto_base)


# =====================================================
# ELIMINAR PAGO (CxC)
# =====================================================

@login_required
@never_cache
def pago_eliminar(request, pk):

    pago = get_object_or_404(
        PagoCliente.objects.select_related("factura", "factura__expediente"),
        pk=pk
    )
    factura = pago.factura

    if factura.estatus == FacturaCliente.Estatus.CANCELADA:
        messages.error(request, "No se pueden eliminar pagos de una factura cancelada.")
        return redirect("factura_detalle", pk=factura.pk)

    if request.method == "POST":

        pago.delete()

        # A diferencia de crear/editar, delete() NO pasa por el save()
        # personalizado de PagoCliente, así que aquí SÍ hay que recalcular
        # el estatus de la factura a mano.
        factura.actualizar_estatus()

        messages.success(request, "Pago eliminado correctamente.")

        return redirect("factura_detalle", pk=factura.pk)

    return render(
        request,
        "finanzas/cxc/pago_eliminar.html",
        {"pago": pago, "factura": factura}
    )

@never_cache
@login_required
def facturas_proveedor_lista(request):
    """
    Lista de facturas de proveedores para Cuentas por Pagar.
    """

    facturas = (
        FacturaProveedor.objects
        .select_related("expediente")
        .prefetch_related("pagos")
        .all()
        .order_by("-fecha_factura", "-id")
    )

    # ---------------------------------------------------------
    # BÚSQUEDA
    # ---------------------------------------------------------

    buscar = request.GET.get("buscar", "").strip()

    if buscar:
        facturas = facturas.filter(
            Q(factura__icontains=buscar)
            | Q(expediente__nombres__icontains=buscar)
            | Q(expediente__apellido_paterno__icontains=buscar)
            | Q(expediente__apellido_materno__icontains=buscar)
            | Q(expediente__razon_social__icontains=buscar)
            | Q(expediente__nombre_comercial__icontains=buscar)
            | Q(expediente__rfc__icontains=buscar)
        ).distinct()

    # ---------------------------------------------------------
    # FILTRO POR ESTATUS
    # ---------------------------------------------------------

    estatus = request.GET.get("estatus", "").strip()

    if estatus:
        facturas = facturas.filter(
            estatus=estatus
        )

    # ---------------------------------------------------------
    # FILTRO DE VENCIMIENTO
    # ---------------------------------------------------------

    vencimiento = request.GET.get(
        "vencimiento",
        "",
    ).strip()

    fecha_hoy = timezone.localdate()

    if vencimiento == "vencidas":

        facturas = facturas.filter(
            fecha_vencimiento__lt=fecha_hoy,
            estatus__in=[
                FacturaProveedor.Estatus.PENDIENTE,
                FacturaProveedor.Estatus.PARCIAL,
            ],
        )

    elif vencimiento == "por_vencer":

        facturas = facturas.filter(
            fecha_vencimiento__gte=fecha_hoy,
            estatus__in=[
                FacturaProveedor.Estatus.PENDIENTE,
                FacturaProveedor.Estatus.PARCIAL,
            ],
        )

    # ---------------------------------------------------------
    # TOTAL DE FACTURAS
    # ---------------------------------------------------------

    total_facturas = (
        facturas.aggregate(
            total=Sum("total")
        )["total"]
        or Decimal("0.00")
    )

    # ---------------------------------------------------------
    # TOTAL PAGADO
    # ---------------------------------------------------------

    total_pagado = sum(
        (
            factura.total_pagado
            for factura in facturas
        ),
        Decimal("0.00"),
    )

    # ---------------------------------------------------------
    # TOTAL PENDIENTE
    # ---------------------------------------------------------

    total_pendiente = sum(
        (
            factura.saldo_pendiente
            for factura in facturas
        ),
        Decimal("0.00"),
    )

    # ---------------------------------------------------------
    # TOTAL DE FACTURAS VENCIDAS
    # ---------------------------------------------------------
    # Se calcula sobre el mismo queryset ya filtrado por búsqueda/estatus/
    # vencimiento (antes de paginar), para que coincida con lo que el
    # usuario está viendo en la tabla.

    total_vencidas = facturas.filter(
        fecha_vencimiento__lt=fecha_hoy,
        estatus__in=[
            FacturaProveedor.Estatus.PENDIENTE,
            FacturaProveedor.Estatus.PARCIAL,
        ],
    ).count()

    # ---------------------------------------------------------
    # PAGINACIÓN
    # ---------------------------------------------------------

    paginator = Paginator(
        facturas,
        25,
    )

    pagina = request.GET.get(
        "page",
        1,
    )

    facturas = paginator.get_page(
        pagina
    )

    # ---------------------------------------------------------
    # CONTEXTO
    # ---------------------------------------------------------

    context = {
        "facturas": facturas,
        "buscar": buscar,
        "estatus_actual": estatus,
        "vencimiento_actual": vencimiento,
        "estatus_choices": FacturaProveedor.Estatus.choices,
        "total_facturas": total_facturas,
        "total_pagado": total_pagado,
        "total_pendiente": total_pendiente,
        "facturas_vencidas": total_vencidas,
    }

    return render(
        request,
        "finanzas/cxp/lista.html",
        context,
    )


@never_cache
@login_required
def factura_proveedor_crear(request):

 
    # =========================================================
    # DATOS PARA EL FORMULARIO
    # =========================================================

    expedientes = (
        Expediente.objects
        .filter(
            tipo=Expediente.Tipo.PROVEEDOR,
            estatus=Expediente.Estatus.ACTIVO,
        )
        .order_by("nombres", "razon_social")
    )

    monedas = FacturaProveedor.Moneda.choices
    estatuses = FacturaProveedor.Estatus.choices

    # =========================================================
    # GET
    # =========================================================

    if request.method == "GET":

        context = {
            "expedientes": expedientes,
            "monedas": monedas,
            "estatuses": estatuses,
        }

        return render(
            request,
            "finanzas/cxp/crear.html",
            context
        )

    # =========================================================
    # POST
    # =========================================================

    expediente_id = request.POST.get("expediente", "").strip()
    factura = request.POST.get("factura", "").strip().upper()
    orden_compra = request.POST.get("orden_compra", "").strip().upper()

    fecha_factura = request.POST.get("fecha_factura", "").strip()
    dias_credito = request.POST.get("dias_credito", "0").strip()

    moneda = request.POST.get("moneda", "MXN").strip()
    tipo_cambio = request.POST.get("tipo_cambio", "").strip()

    fecha_vencimiento = request.POST.get(
        "fecha_vencimiento",
        ""
    ).strip()

    estatus = request.POST.get(
        "estatus",
        FacturaProveedor.Estatus.PENDIENTE
    ).strip()

    subtotal = request.POST.get("subtotal", "").strip()
    iva = request.POST.get("iva", "0").strip()

    observaciones = request.POST.get(
        "observaciones",
        ""
    ).strip()

    errores = []

    # =========================================================
    # VALIDAR PROVEEDOR
    # =========================================================

    expediente = None

    if not expediente_id:
        errores.append("Debes seleccionar un proveedor.")
    else:
        try:
            expediente = (
                Expediente.objects
                .filter(
                    pk=expediente_id,
                    tipo=Expediente.Tipo.PROVEEDOR,
                    estatus=Expediente.Estatus.ACTIVO,
                )
                .first()
            )

            if not expediente:
                errores.append(
                    "El proveedor seleccionado no es válido "
                    "o se encuentra inactivo."
                )

        except (ValueError, TypeError):
            errores.append("El proveedor seleccionado no es válido.")

    # =========================================================
    # VALIDAR FACTURA
    # =========================================================

    if not factura:
        errores.append("El número de factura es obligatorio.")

    else:
        if FacturaProveedor.objects.filter(
            factura__iexact=factura
        ).exists():
            errores.append(
                f"La factura '{factura}' ya está registrada."
            )

    # =========================================================
    # VALIDAR FECHA DE FACTURA
    # =========================================================

    fecha_factura_obj = None

    if not fecha_factura:
        errores.append("La fecha de factura es obligatoria.")
    else:
        try:
            from datetime import datetime

            fecha_factura_obj = datetime.strptime(
                fecha_factura,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            errores.append(
                "La fecha de factura no tiene un formato válido."
            )

    # =========================================================
    # DÍAS DE CRÉDITO
    # =========================================================

    dias_credito_obj = 0

    try:
        dias_credito_obj = int(dias_credito or 0)

        if dias_credito_obj < 0:
            errores.append(
                "Los días de crédito no pueden ser negativos."
            )

    except ValueError:
        errores.append(
            "Los días de crédito deben ser un número entero."
        )

    # =========================================================
    # MONEDA
    # =========================================================

    monedas_validas = [
        valor for valor, texto in FacturaProveedor.Moneda.choices
    ]

    if moneda not in monedas_validas:
        errores.append("La moneda seleccionada no es válida.")

    # =========================================================
    # TIPO DE CAMBIO
    # =========================================================

    tipo_cambio_obj = Decimal("1.00")

    if moneda == FacturaProveedor.Moneda.MXN:

        tipo_cambio_obj = Decimal("1.00")

    else:

        if not tipo_cambio:
            errores.append(
                "Debes capturar el tipo de cambio para "
                "monedas diferentes a MXN."
            )

        else:
            try:
                tipo_cambio_limpio = tipo_cambio.replace(",", "")
                tipo_cambio_obj = Decimal(tipo_cambio_limpio)

                if tipo_cambio_obj <= 0:
                    errores.append(
                        "El tipo de cambio debe ser mayor a cero."
                    )

            except InvalidOperation:
                errores.append(
                    "El tipo de cambio no tiene un valor válido."
                )

    # =========================================================
    # SUBTOTAL
    # =========================================================

    subtotal_obj = Decimal("0.00")

    if not subtotal:
        errores.append("El subtotal es obligatorio.")

    else:
        try:
            subtotal_limpio = subtotal.replace(",", "")
            subtotal_obj = Decimal(subtotal_limpio)

            if subtotal_obj < 0:
                errores.append(
                    "El subtotal no puede ser negativo."
                )

        except InvalidOperation:
            errores.append(
                "El subtotal no tiene un valor válido."
            )

    # =========================================================
    # IVA
    # =========================================================

    iva_obj = Decimal("0.00")

    if iva:

        try:
            iva_limpio = iva.replace(",", "")
            iva_obj = Decimal(iva_limpio)

            if iva_obj < 0:
                errores.append(
                    "El IVA no puede ser negativo."
                )

        except InvalidOperation:
            errores.append(
                "El IVA no tiene un valor válido."
            )

    # =========================================================
    # TOTAL
    # =========================================================

    total_obj = subtotal_obj + iva_obj

    # =========================================================
    # FECHA DE VENCIMIENTO
    # =========================================================

    fecha_vencimiento_obj = None

    if fecha_vencimiento:

        try:
            from datetime import datetime

            fecha_vencimiento_obj = datetime.strptime(
                fecha_vencimiento,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            errores.append(
                "La fecha de vencimiento no tiene un formato válido."
            )

    elif fecha_factura_obj:

        fecha_vencimiento_obj = (
            fecha_factura_obj +
            timedelta(days=dias_credito_obj)
        )

    # =========================================================
    # VALIDAR ESTATUS
    # =========================================================

    estatus_validos = [
        valor for valor, texto in FacturaProveedor.Estatus.choices
    ]

    if estatus not in estatus_validos:
        errores.append(
            "El estatus seleccionado no es válido."
        )

    # =========================================================
    # MOSTRAR ERRORES
    # =========================================================

    if errores:

        for error in errores:
            messages.error(request, error)

        context = {
            "expedientes": expedientes,
            "monedas": monedas,
            "estatuses": estatuses,
        }

        return render(
            request,
            "finanzas/cxp/crear.html",
            context
        )

    # =========================================================
    # GUARDAR
    # =========================================================

    try:

        with transaction.atomic():

            factura_proveedor = FacturaProveedor.objects.create(
                expediente=expediente,
                fecha_factura=fecha_factura_obj,
                factura=factura,
                orden_compra=orden_compra,
                subtotal=subtotal_obj,
                iva=iva_obj,
                total=total_obj,
                dias_credito=dias_credito_obj,
                fecha_vencimiento=fecha_vencimiento_obj,
                moneda=moneda,
                tipo_cambio=tipo_cambio_obj,
                estatus=estatus,
                observaciones=observaciones,
            )

        messages.success(
            request,
            f"La factura {factura_proveedor.factura} "
            f"se registró correctamente."
        )

        return redirect("facturas_proveedor_lista")

    except IntegrityError:

        messages.error(
            request,
            "No fue posible registrar la factura. "
            "Verifica que el número de factura no esté duplicado."
        )

    except Exception as e:

        messages.error(
            request,
            f"Ocurrió un error al registrar la factura: {str(e)}"
        )

    # =========================================================
    # SI HUBO ERROR AL GUARDAR
    # =========================================================

    context = {
        "expedientes": expedientes,
        "monedas": monedas,
        "estatuses": estatuses,
    }

    return render(
        request,
        "finanzas/cxp/crear.html",
        context

    )

@never_cache
@login_required
def factura_proveedor_detalle(request, pk):
    """
    Muestra el detalle completo de una factura de proveedor.
    """

    # =========================================================
    # FACTURA
    # =========================================================

    factura = get_object_or_404(
        FacturaProveedor.objects.select_related("expediente"),
        pk=pk
    )

    # =========================================================
    # PAGOS
    # =========================================================

    pagos = (
        factura.pagos
        .all()
        .order_by("-fecha_pago", "-id")
    )

    # =========================================================
    # TOTAL PAGADO
    # =========================================================

    total_pagado = sum(
        (pago.monto or Decimal("0.00") for pago in pagos),
        Decimal("0.00")
    )

    # =========================================================
    # SALDO
    # =========================================================

    saldo = factura.total - total_pagado

    # Evitar saldos negativos por diferencias de centavos
    if saldo < Decimal("0.00"):
        saldo = Decimal("0.00")

    # =========================================================
    # TOTAL EN MXN
    # =========================================================

    total_mxn = factura.total

    if factura.moneda != FacturaProveedor.Moneda.MXN:
        tipo_cambio = factura.tipo_cambio or Decimal("0.00")

        if tipo_cambio > 0:
            total_mxn = factura.total * tipo_cambio
        else:
            total_mxn = Decimal("0.00")

    # =========================================================
    # CONTEXTO
    # =========================================================

    context = {
        "factura": factura,
        "pagos": pagos,
        "total_pagado": total_pagado,
        "saldo": saldo,
        "total_mxn": total_mxn,
    }

    return render(
        request,
        "finanzas/cxp/detalle.html",
        context
    )
@never_cache
@login_required
def factura_proveedor_editar(request, pk):

    factura = get_object_or_404(
        FacturaProveedor.objects.select_related("expediente"),
        pk=pk
    )

    if factura.estatus == FacturaProveedor.Estatus.CANCELADA:
        messages.error(request, "No se puede editar una factura cancelada.")
        return redirect("factura_proveedor_detalle", pk=pk)

    expedientes_proveedores = Expediente.objects.filter(
        tipo__in=[Expediente.Tipo.PROVEEDOR, Expediente.Tipo.AMBOS]
    )

    contexto_base = {
        "factura": factura,
        "expedientes": expedientes_proveedores,
        "monedas": FacturaProveedor.Moneda.choices,
    }

    if request.method == "POST":

        expediente_id = request.POST.get("expediente")

        if not expediente_id:
            messages.error(request, "Debe seleccionar un proveedor.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        try:
            expediente = get_object_or_404(Expediente, pk=expediente_id)
        except (ValueError, ValidationError):
            messages.error(request, "El proveedor seleccionado no es válido.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        if expediente.tipo not in (Expediente.Tipo.PROVEEDOR, Expediente.Tipo.AMBOS):
            messages.error(
                request,
                f"{expediente.nombre_completo} está registrado como Cliente, "
                "no se le pueden generar facturas de Cuentas por Pagar."
            )
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        factura_num = (request.POST.get("factura") or "").strip().upper()
        if not factura_num:
            messages.error(request, "Debe especificar el número de factura.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        if FacturaProveedor.objects.filter(factura=factura_num).exclude(pk=pk).exists():
            messages.error(
                request,
                f"Ya existe otra factura registrada con el número {factura_num}."
            )
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        moneda = request.POST.get("moneda", FacturaProveedor.Moneda.MXN)
        if moneda not in FacturaProveedor.Moneda.values:
            messages.error(request, "Moneda no válida.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        if moneda == FacturaProveedor.Moneda.MXN:
            tipo_cambio = Decimal("1.00")
        else:
            try:
                tipo_cambio = Decimal(request.POST.get("tipo_cambio") or "0")
            except InvalidOperation:
                messages.error(request, "El tipo de cambio debe ser un número válido.")
                return render(request, "finanzas/cxp/editar.html", contexto_base)

            if tipo_cambio <= 0:
                messages.error(
                    request,
                    "Debe especificar un tipo de cambio mayor a cero para moneda distinta a MXN."
                )
                return render(request, "finanzas/cxp/editar.html", contexto_base)

        try:
            subtotal = Decimal(request.POST.get("subtotal") or "0")
            iva = Decimal(request.POST.get("iva") or "0")
        except InvalidOperation:
            messages.error(request, "Subtotal e IVA deben ser números válidos.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        if subtotal <= 0:
            messages.error(request, "El subtotal debe ser mayor a cero.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        if iva < 0:
            messages.error(request, "El IVA no puede ser negativo.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        total = subtotal + iva

        total_pagado_actual = factura.total_pagado
        if total < total_pagado_actual:
            messages.error(
                request,
                f"El nuevo total (${total}) no puede ser menor a lo ya pagado "
                f"(${total_pagado_actual}). Considere registrar una nota de crédito "
                f"en vez de reducir el total por debajo de lo pagado."
            )
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        fecha_factura = request.POST.get("fecha_factura")
        fecha_vencimiento = request.POST.get("fecha_vencimiento")

        if not fecha_factura or not fecha_vencimiento:
            messages.error(request, "Debe especificar fecha de factura y de vencimiento.")
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        if fecha_vencimiento < fecha_factura:
            messages.error(
                request,
                "La fecha de vencimiento no puede ser anterior a la fecha de la factura."
            )
            return render(request, "finanzas/cxp/editar.html", contexto_base)

        dias_credito = _dias_credito_desde_post(request.POST)
        orden_servicio = (request.POST.get("orden_servicio") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        factura.expediente = expediente
        factura.factura = factura_num
        factura.orden_servicio = orden_servicio
        factura.fecha_factura = fecha_factura
        factura.fecha_vencimiento = fecha_vencimiento
        factura.dias_credito = dias_credito
        factura.moneda = moneda
        factura.tipo_cambio = tipo_cambio
        factura.subtotal = subtotal
        factura.iva = iva
        factura.total = total
        factura.observaciones = observaciones
        factura.save()

        factura.actualizar_estatus()

        messages.success(request, "Factura actualizada correctamente.")

        return redirect("factura_proveedor_detalle", pk=pk)

    return render(request, "finanzas/cxp/editar.html", contexto_base)


@login_required
@never_cache
def factura_proveedor_cancelar(request, pk):

    factura = get_object_or_404(
        FacturaProveedor.objects.select_related("expediente"),
        pk=pk
    )

    if factura.estatus == FacturaProveedor.Estatus.CANCELADA:
        messages.info(request, "Esta factura ya está cancelada.")
        return redirect("factura_proveedor_detalle", pk=pk)

    if factura.total_pagado > 0:
        messages.error(
            request,
            "No se puede cancelar una factura que ya tiene pagos registrados "
            f"(${factura.total_pagado}). Elimine o ajuste los pagos primero."
        )
        return redirect("factura_proveedor_detalle", pk=pk)

    if request.method == "POST":
        factura.estatus = FacturaProveedor.Estatus.CANCELADA
        factura.save(update_fields=["estatus"])

        messages.success(request, "Factura cancelada correctamente.")

        return redirect("factura_proveedor_detalle", pk=pk)

    return render(
        request,
        "finanzas/cxp/cancelar.html",
        {"factura": factura}
    )

@login_required
@never_cache
def registrar_proveedor_pago(request, pk):

    factura = get_object_or_404(FacturaProveedor, pk=pk)

    if factura.estatus == FacturaProveedor.Estatus.CANCELADA:
        messages.error(request, "No se pueden registrar pagos a una factura cancelada.")
        return redirect("factura_proveedor_detalle", pk=pk)

    if factura.estatus == FacturaProveedor.Estatus.PAGADA:
        messages.info(request, "Esta factura ya está completamente pagada.")
        return redirect("factura_proveedor_detalle", pk=pk)

    contexto_base = {
        "factura": factura,
        "metodos": PagoProveedor.MetodoPago.choices,
    }

    if request.method == "POST":

        try:
            monto = Decimal(request.POST.get("monto") or "0")
        except InvalidOperation:
            messages.error(request, "El monto debe ser un número válido.")
            return render(request, "finanzas/cxp/registrar_pago.html", contexto_base)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return render(request, "finanzas/cxp/registrar_pago.html", contexto_base)

        saldo_actual = factura.saldo_pendiente
        if monto > saldo_actual:
            messages.error(
                request,
                f"El monto (${monto}) no puede exceder el saldo pendiente (${saldo_actual})."
            )
            return render(request, "finanzas/cxp/registrar_pago.html", contexto_base)

        fecha_pago = request.POST.get("fecha_pago")
        if not fecha_pago:
            messages.error(request, "Debe especificar la fecha de pago.")
            return render(request, "finanzas/cxp/registrar_pago.html", contexto_base)

        fecha_deposito = request.POST.get("fecha_deposito") or None
        referencia = (request.POST.get("referencia") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        PagoProveedor.objects.create(
            factura=factura,
            fecha_pago=fecha_pago,
            fecha_deposito=fecha_deposito,
            monto=monto,
            metodo_pago=request.POST.get("metodo_pago", PagoProveedor.MetodoPago.TRANSFERENCIA),
            referencia=referencia,
            observaciones=observaciones,
        )

        messages.success(request, "Pago registrado correctamente.")

        return redirect("factura_proveedor_detalle", pk=pk)

    return render(request, "finanzas/cxp/registrar_pago.html", contexto_base)


@login_required
@never_cache
def pago_proveedor_editar(request, pk):

    pago = get_object_or_404(
        PagoProveedor.objects.select_related("factura", "factura__expediente"),
        pk=pk
    )
    factura = pago.factura

    if factura.estatus == FacturaProveedor.Estatus.CANCELADA:
        messages.error(request, "No se pueden editar pagos de una factura cancelada.")
        return redirect("factura_proveedor_detalle", pk=factura.pk)

    contexto_base = {
        "pago": pago,
        "factura": factura,
        "metodos": PagoProveedor.MetodoPago.choices,
    }

    if request.method == "POST":

        try:
            monto = Decimal(request.POST.get("monto") or "0")
        except InvalidOperation:
            messages.error(request, "El monto debe ser un número válido.")
            return render(request, "finanzas/cxp/pago_editar.html", contexto_base)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return render(request, "finanzas/cxp/pago_editar.html", contexto_base)

        saldo_disponible = factura.saldo_pendiente + pago.monto
        if monto > saldo_disponible:
            messages.error(
                request,
                f"El monto (${monto}) no puede exceder el saldo disponible "
                f"(${saldo_disponible})."
            )
            return render(request, "finanzas/cxp/pago_editar.html", contexto_base)

        fecha_pago = request.POST.get("fecha_pago")
        if not fecha_pago:
            messages.error(request, "Debe especificar la fecha de pago.")
            return render(request, "finanzas/cxp/pago_editar.html", contexto_base)

        fecha_deposito = request.POST.get("fecha_deposito") or None
        referencia = (request.POST.get("referencia") or "").strip().upper()
        observaciones = request.POST.get("observaciones", "")

        pago.monto = monto
        pago.fecha_pago = fecha_pago
        pago.fecha_deposito = fecha_deposito
        pago.metodo_pago = request.POST.get("metodo_pago", pago.metodo_pago)
        pago.referencia = referencia
        pago.observaciones = observaciones

        # PagoProveedor.save() ya llama internamente a factura.actualizar_estatus().
        pago.save()

        messages.success(request, "Pago actualizado correctamente.")

        return redirect("factura_proveedor_detalle", pk=factura.pk)

    return render(request, "finanzas/cxp/pago_editar.html", contexto_base)

@login_required
@never_cache
def pago_proveedor_eliminar(request, pk):

    pago = get_object_or_404(
        PagoProveedor.objects.select_related("factura", "factura__expediente"),
        pk=pk
    )
    factura = pago.factura

    if factura.estatus == FacturaProveedor.Estatus.CANCELADA:
        messages.error(request, "No se pueden eliminar pagos de una factura cancelada.")
        return redirect("factura_proveedor_detalle", pk=factura.pk)

    if request.method == "POST":

        # PagoProveedor.delete() ya llama internamente a
        # factura.actualizar_estatus(), a diferencia de PagoCliente.
        pago.delete()

        messages.success(request, "Pago eliminado correctamente.")

        return redirect("factura_proveedor_detalle", pk=factura.pk)

    return render(
        request,
        "finanzas/cxp/pago_eliminar.html",
        {"pago": pago, "factura": factura}
    )


@never_cache
@login_required
def presupuestos_lista(request):
    """
    Lista los presupuestos anuales registrados.
    """

    presupuestos = (
        PresupuestoAnual.objects
        .all()
        .order_by("-ejercicio")
    )

    return render(
        request,
        "finanzas/presupuestos/lista.html",
        {
            "presupuestos": presupuestos,
        }
    )


# =====================================================
# CREAR PRESUPUESTO
# =====================================================

@never_cache
@login_required
def presupuesto_crear(request):

    contexto_base = {
        "estatuses": PresupuestoAnual.Estatus.choices,
    }

    if request.method == "POST":

        nombre = (request.POST.get("nombre") or "").strip()
        observaciones = request.POST.get("observaciones", "")

        # --- Ejercicio: requerido, entero válido y mayor a cero ---
        try:
            ejercicio = int(request.POST.get("ejercicio") or 0)
        except ValueError:
            messages.error(request, "El ejercicio debe ser un número válido.")
            return render(request, "finanzas/presupuestos/crear.html", contexto_base)

        if ejercicio <= 0:
            messages.error(request, "Debe especificar un ejercicio (año) válido.")
            return render(request, "finanzas/presupuestos/crear.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre del presupuesto es obligatorio.")
            return render(request, "finanzas/presupuestos/crear.html", contexto_base)

        if PresupuestoAnual.objects.filter(ejercicio=ejercicio).exists():
            messages.error(request, f"Ya existe un presupuesto para el ejercicio {ejercicio}.")
            return render(request, "finanzas/presupuestos/crear.html", contexto_base)

        # --- Estatus: validado contra los choices reales, igual que en CxC/CxP ---
        estatus = request.POST.get("estatus") or PresupuestoAnual.Estatus.BORRADOR
        if estatus not in PresupuestoAnual.Estatus.values:
            messages.error(request, "Estatus no válido.")
            return render(request, "finanzas/presupuestos/crear.html", contexto_base)

        presupuesto = PresupuestoAnual.objects.create(
            ejercicio=ejercicio,
            nombre=nombre,
            estatus=estatus,
            observaciones=observaciones,
        )

        messages.success(request, "El presupuesto se creó correctamente.")
        return redirect("presupuestos_lista")

    return render(request, "finanzas/presupuestos/crear.html", contexto_base)


# =====================================================
# DETALLE DE PRESUPUESTO
# =====================================================

@never_cache
@login_required
def presupuesto_detalle(request, pk):

    presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)

    ingresos = presupuesto.ingresos.select_related("concepto").all()
    gastos = presupuesto.gastos.select_related("partida").all()

    total_ingresos = sum((ingreso.monto_anual for ingreso in ingresos), Decimal("0.00"))
    total_gastos = sum((gasto.monto_anual for gasto in gastos), Decimal("0.00"))
    resultado_presupuestario = total_ingresos - total_gastos

    return render(
        request,
        "finanzas/presupuestos/detalle.html",
        {
            "presupuesto": presupuesto,
            "ingresos": ingresos,
            "gastos": gastos,
            "total_ingresos": total_ingresos,
            "total_gastos": total_gastos,
            "resultado_presupuestario": resultado_presupuestario,
        }
    )

# =====================================================
# AGREGAR INGRESO AL PRESUPUESTO
# =====================================================

@never_cache
@login_required
def ingreso_crear(request, pk):

    presupuesto = get_object_or_404(
        PresupuestoAnual,
        pk=pk
    )

    conceptos = ConceptoIngreso.objects.filter(
        activo=True
    ).order_by("codigo")

    contexto_base = {
        "presupuesto": presupuesto,
        "conceptos": conceptos,
    }

    if request.method == "POST":

        concepto_id = request.POST.get("concepto")

        if not concepto_id:
            messages.error(
                request,
                "Debe seleccionar un concepto de ingreso."
            )
            return render(
                request,
                "finanzas/presupuestos/ingreso_crear.html",
                contexto_base
            )

        concepto = get_object_or_404(
            ConceptoIngreso,
            pk=concepto_id,
            activo=True
        )

        if PresupuestoIngreso.objects.filter(
            presupuesto=presupuesto,
            concepto=concepto,
        ).exists():

            messages.error(
                request,
                "Este concepto ya está registrado en el presupuesto."
            )

            return render(
                request,
                "finanzas/presupuestos/ingreso_crear.html",
                contexto_base
            )

        try:
            monto_anual = Decimal(
                request.POST.get("monto_anual") or "0"
            )
        except InvalidOperation:

            messages.error(
                request,
                "El monto anual debe ser un número válido."
            )

            return render(
                request,
                "finanzas/presupuestos/ingreso_crear.html",
                contexto_base
            )

        if monto_anual <= 0:

            messages.error(
                request,
                "El monto anual debe ser mayor a cero."
            )

            return render(
                request,
                "finanzas/presupuestos/ingreso_crear.html",
                contexto_base
            )

        PresupuestoIngreso.objects.create(
            presupuesto=presupuesto,
            concepto=concepto,
            monto_anual=monto_anual,
        )

        messages.success(
            request,
            "El ingreso fue agregado correctamente."
        )

        return redirect(
            "presupuesto_detalle",
            pk=presupuesto.pk
        )

    return render(
        request,
        "finanzas/presupuestos/ingreso_crear.html",
        contexto_base
    )


    # =====================================================
# AGREGAR GASTO AL PRESUPUESTO
# =====================================================

@never_cache
@login_required
def gasto_crear(request, pk):

    presupuesto = get_object_or_404(
        PresupuestoAnual,
        pk=pk
    )

    contexto_base = {
        "presupuesto": presupuesto,
    }

    if request.method == "POST":

        partida_id = request.POST.get("partida")

        if not partida_id:
            messages.error(request, "Debe seleccionar una partida de gasto.")
            return render(request, "finanzas/presupuestos/gasto_crear.html", contexto_base)

        # Valida existencia y estatus activo antes de llegar al create(),
        # evitando un IntegrityError de FK inválida sin capturar.
        partida = get_object_or_404(PartidaGasto, pk=partida_id, activo=True)

        if PresupuestoGasto.objects.filter(
            presupuesto=presupuesto,
            partida=partida,
        ).exists():
            messages.error(
                request,
                "Esta partida ya está registrada en el presupuesto."
            )
            return render(request, "finanzas/presupuestos/gasto_crear.html", contexto_base)

        try:
            monto_anual = Decimal(request.POST.get("monto_anual") or "0")
        except InvalidOperation:
            messages.error(request, "El monto anual debe ser un número válido.")
            return render(request, "finanzas/presupuestos/gasto_crear.html", contexto_base)

        if monto_anual <= 0:
            messages.error(request, "El monto anual debe ser mayor a cero.")
            return render(request, "finanzas/presupuestos/gasto_crear.html", contexto_base)

        PresupuestoGasto.objects.create(
            presupuesto=presupuesto,
            partida=partida,
            monto_anual=monto_anual,
        )

        messages.success(request, "El gasto fue agregado correctamente.")

        return redirect("presupuesto_detalle", pk=presupuesto.pk)

    partidas = PartidaGasto.objects.filter(
        activo=True,
        subpartidas__isnull=True,  # solo partidas hoja, sin subpartidas
    ).order_by("codigo")

    contexto_base = {
        "presupuesto": presupuesto,
        "partidas": partidas,
    }

    return render(request, "finanzas/presupuestos/gasto_crear.html", contexto_base)


# =====================================================
# DISTRIBUCIÓN MENSUAL DE INGRESO
# =====================================================

@never_cache
@login_required
def ingreso_mensual(request, pk):

    presupuesto_ingreso = get_object_or_404(
        PresupuestoIngreso.objects.select_related(
            "presupuesto",
            "concepto",
        ),
        pk=pk,
    )

    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]

    for numero, nombre in meses:
        PresupuestoIngresoMensual.objects.get_or_create(
            presupuesto_ingreso=presupuesto_ingreso,
            mes=numero,
            defaults={"monto": Decimal("0.00")}
        )

    mensualidades = (
        presupuesto_ingreso.mensualidades
        .all()
        .order_by("mes")
    )

    mensualidades_por_mes = {m.mes: m for m in mensualidades}
    meses_formulario = [
        {
            "numero": numero,
            "nombre": nombre,
            "monto": mensualidades_por_mes[numero].monto,
        }
        for numero, nombre in meses
    ]

    if request.method == "POST":

        valores = {}

        try:
            for numero, nombre in meses:
                valor = request.POST.get(f"mes_{numero}", "0")
                valor = Decimal(valor or "0")
                if valor < 0:
                    raise InvalidOperation
                valores[numero] = valor

        except (InvalidOperation, ValueError):
            messages.error(request, "Los montos mensuales deben ser números válidos.")
            return render(
                request,
                "finanzas/presupuestos/ingreso_mensual.html",
                {
                    "presupuesto_ingreso": presupuesto_ingreso,
                    "mensualidades": mensualidades,
                    "meses": meses_formulario,
                    "total_distribuido": sum(valores.values(), Decimal("0.00")) if valores else Decimal("0.00"),
                    "diferencia": presupuesto_ingreso.monto_anual - (sum(valores.values(), Decimal("0.00")) if valores else Decimal("0.00")),
                }
            )

        total_distribuido = sum(valores.values(), Decimal("0.00"))

        if total_distribuido != presupuesto_ingreso.monto_anual:
            messages.error(
                request,
                (
                    "La distribución mensual debe coincidir exactamente con el monto anual de "
                    f"${presupuesto_ingreso.monto_anual:,.2f}."
                )
            )
            return render(
                request,
                "finanzas/presupuestos/ingreso_mensual.html",
                {
                    "presupuesto_ingreso": presupuesto_ingreso,
                    "mensualidades": mensualidades,
                    "meses": meses_formulario,
                    "total_distribuido": total_distribuido,
                    "diferencia": presupuesto_ingreso.monto_anual - total_distribuido,
                }
            )

        for numero, monto in valores.items():
            PresupuestoIngresoMensual.objects.update_or_create(
                presupuesto_ingreso=presupuesto_ingreso,
                mes=numero,
                defaults={"monto": monto}
            )

        messages.success(request, "La distribución mensual del ingreso se guardó correctamente.")
        return redirect("presupuesto_detalle", pk=presupuesto_ingreso.presupuesto.pk)

    total_distribuido = sum((m.monto for m in mensualidades), Decimal("0.00"))

    return render(
        request,
        "finanzas/presupuestos/ingreso_mensual.html",
        {
            "presupuesto_ingreso": presupuesto_ingreso,
            "mensualidades": mensualidades,
            "meses": meses_formulario,
            "total_distribuido": total_distribuido,
            "diferencia": presupuesto_ingreso.monto_anual - total_distribuido,
        }
    )

# =====================================================
# DISTRIBUCIÓN MENSUAL DE GASTO
# =====================================================

@never_cache
@login_required
def gasto_mensual(request, pk):

    presupuesto_gasto = get_object_or_404(
        PresupuestoGasto.objects.select_related(
            "presupuesto",
            "partida",
        ),
        pk=pk,
    )

    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]

    for numero, nombre in meses:
        PresupuestoGastoMensual.objects.get_or_create(
            presupuesto_gasto=presupuesto_gasto,
            mes=numero,
            defaults={"monto": Decimal("0.00")}
        )

    mensualidades = (
        presupuesto_gasto.mensualidades
        .all()
        .order_by("mes")
    )

    mensualidades_por_mes = {m.mes: m for m in mensualidades}
    meses_formulario = [
        {
            "numero": numero,
            "nombre": nombre,
            "monto": mensualidades_por_mes[numero].monto,
        }
        for numero, nombre in meses
    ]

    if request.method == "POST":

        valores = {}

        try:
            for numero, nombre in meses:
                valor = request.POST.get(f"mes_{numero}", "0")
                valor = Decimal(valor or "0")
                if valor < 0:
                    raise InvalidOperation
                valores[numero] = valor

        except (InvalidOperation, ValueError):
            messages.error(request, "Los montos mensuales deben ser números válidos.")
            return render(
                request,
                "finanzas/presupuestos/gasto_mensual.html",
                {
                    "presupuesto_gasto": presupuesto_gasto,
                    "mensualidades": mensualidades,
                    "meses": meses_formulario,
                    "total_distribuido": sum(valores.values(), Decimal("0.00")) if valores else Decimal("0.00"),
                    "diferencia": presupuesto_gasto.monto_anual - (sum(valores.values(), Decimal("0.00")) if valores else Decimal("0.00")),
                }
            )

        total_distribuido = sum(valores.values(), Decimal("0.00"))

        if total_distribuido != presupuesto_gasto.monto_anual:
            messages.error(
                request,
                (
                    "La distribución mensual debe coincidir exactamente con el monto anual de "
                    f"${presupuesto_gasto.monto_anual:,.2f}."
                )
            )
            return render(
                request,
                "finanzas/presupuestos/gasto_mensual.html",
                {
                    "presupuesto_gasto": presupuesto_gasto,
                    "mensualidades": mensualidades,
                    "meses": meses_formulario,
                    "total_distribuido": total_distribuido,
                    "diferencia": presupuesto_gasto.monto_anual - total_distribuido,
                }
            )

        for numero, monto in valores.items():
            PresupuestoGastoMensual.objects.update_or_create(
                presupuesto_gasto=presupuesto_gasto,
                mes=numero,
                defaults={"monto": monto}
            )

        messages.success(request, "La distribución mensual del gasto se guardó correctamente.")
        return redirect("presupuesto_detalle", pk=presupuesto_gasto.presupuesto.pk)

    total_distribuido = sum((m.monto for m in mensualidades), Decimal("0.00"))

    return render(
        request,
        "finanzas/presupuestos/gasto_mensual.html",
        {
            "presupuesto_gasto": presupuesto_gasto,
            "mensualidades": mensualidades,
            "meses": meses_formulario,
            "total_distribuido": total_distribuido,
            "diferencia": presupuesto_gasto.monto_anual - total_distribuido,
        }
    )


@never_cache
@login_required
def presupuesto_editar(request, pk):

    presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)

    contexto_base = {
        "presupuesto": presupuesto,
        "estatuses": PresupuestoAnual.Estatus.choices,
    }

    if request.method == "POST":

        nombre = (request.POST.get("nombre") or "").strip()
        observaciones = request.POST.get("observaciones", "")

        try:
            ejercicio = int(request.POST.get("ejercicio") or 0)
        except ValueError:
            messages.error(request, "El ejercicio debe ser un número válido.")
            return render(request, "finanzas/presupuestos/editar.html", contexto_base)

        if ejercicio <= 0:
            messages.error(request, "Debe especificar un ejercicio (año) válido.")
            return render(request, "finanzas/presupuestos/editar.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre del presupuesto es obligatorio.")
            return render(request, "finanzas/presupuestos/editar.html", contexto_base)

        if PresupuestoAnual.objects.filter(ejercicio=ejercicio).exclude(pk=pk).exists():
            messages.error(request, f"Ya existe otro presupuesto para el ejercicio {ejercicio}.")
            return render(request, "finanzas/presupuestos/editar.html", contexto_base)

        estatus = request.POST.get("estatus") or PresupuestoAnual.Estatus.BORRADOR
        if estatus not in PresupuestoAnual.Estatus.values:
            messages.error(request, "Estatus no válido.")
            return render(request, "finanzas/presupuestos/editar.html", contexto_base)

        presupuesto.ejercicio = ejercicio
        presupuesto.nombre = nombre
        presupuesto.estatus = estatus
        presupuesto.observaciones = observaciones
        presupuesto.save()

        messages.success(request, "El presupuesto se actualizó correctamente.")
        return redirect("presupuesto_detalle", pk=presupuesto.pk)

    return render(request, "finanzas/presupuestos/editar.html", contexto_base)


# =====================================================
# ELIMINAR PRESUPUESTO
# =====================================================

@never_cache
@login_required
def presupuesto_eliminar(request, pk):

    presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)

    total_ingresos = presupuesto.ingresos.count()
    total_gastos = presupuesto.gastos.count()

    if request.method == "POST":
        presupuesto.delete()
        messages.success(request, "Presupuesto eliminado correctamente.")
        return redirect("presupuestos_lista")

    return render(
        request,
        "finanzas/presupuestos/eliminar.html",
        {
            "presupuesto": presupuesto,
            "total_ingresos": total_ingresos,
            "total_gastos": total_gastos,
        }
    )


@never_cache
@login_required
def ingreso_editar(request, pk):

    presupuesto_ingreso = get_object_or_404(
        PresupuestoIngreso.objects.select_related("presupuesto", "concepto"),
        pk=pk
    )

    if request.method == "POST":

        try:
            monto_anual = Decimal(request.POST.get("monto_anual") or "0")
        except InvalidOperation:
            messages.error(request, "El monto anual debe ser un número válido.")
            return render(
                request,
                "finanzas/presupuestos/ingreso_editar.html",
                {"presupuesto_ingreso": presupuesto_ingreso}
            )

        if monto_anual <= 0:
            messages.error(request, "El monto anual debe ser mayor a cero.")
            return render(
                request,
                "finanzas/presupuestos/ingreso_editar.html",
                {"presupuesto_ingreso": presupuesto_ingreso}
            )

        monto_anterior = presupuesto_ingreso.monto_anual
        presupuesto_ingreso.monto_anual = monto_anual
        presupuesto_ingreso.save()

        if monto_anual != monto_anterior:
            messages.warning(
                request,
                "El monto anual cambió — recuerda actualizar la distribución "
                "mensual de este ingreso para que siga sumando el nuevo total."
            )

        messages.success(request, "El ingreso presupuestado se actualizó correctamente.")
        return redirect("presupuesto_detalle", pk=presupuesto_ingreso.presupuesto.pk)

    return render(
        request,
        "finanzas/presupuestos/ingreso_editar.html",
        {"presupuesto_ingreso": presupuesto_ingreso}
    )


# =====================================================
# ELIMINAR INGRESO PRESUPUESTADO
# =====================================================

@never_cache
@login_required
def ingreso_eliminar(request, pk):

    presupuesto_ingreso = get_object_or_404(
        PresupuestoIngreso.objects.select_related("presupuesto", "concepto"),
        pk=pk
    )
    presupuesto_pk = presupuesto_ingreso.presupuesto.pk

    if request.method == "POST":
        presupuesto_ingreso.delete()
        messages.success(request, "El ingreso presupuestado fue eliminado.")
        return redirect("presupuesto_detalle", pk=presupuesto_pk)

    return render(
        request,
        "finanzas/presupuestos/ingreso_eliminar.html",
        {"presupuesto_ingreso": presupuesto_ingreso}
    )


# =====================================================
# EDITAR GASTO PRESUPUESTADO
# =====================================================

@never_cache
@login_required
def gasto_editar(request, pk):

    presupuesto_gasto = get_object_or_404(
        PresupuestoGasto.objects.select_related("presupuesto", "partida"),
        pk=pk
    )

    if request.method == "POST":

        try:
            monto_anual = Decimal(request.POST.get("monto_anual") or "0")
        except InvalidOperation:
            messages.error(request, "El monto anual debe ser un número válido.")
            return render(
                request,
                "finanzas/presupuestos/gasto_editar.html",
                {"presupuesto_gasto": presupuesto_gasto}
            )

        if monto_anual <= 0:
            messages.error(request, "El monto anual debe ser mayor a cero.")
            return render(
                request,
                "finanzas/presupuestos/gasto_editar.html",
                {"presupuesto_gasto": presupuesto_gasto}
            )

        monto_anterior = presupuesto_gasto.monto_anual
        presupuesto_gasto.monto_anual = monto_anual
        presupuesto_gasto.save()

        if monto_anual != monto_anterior:
            messages.warning(
                request,
                "El monto anual cambió — recuerda actualizar la distribución "
                "mensual de este gasto para que siga sumando el nuevo total."
            )

        messages.success(request, "El gasto presupuestado se actualizó correctamente.")
        return redirect("presupuesto_detalle", pk=presupuesto_gasto.presupuesto.pk)

    return render(
        request,
        "finanzas/presupuestos/gasto_editar.html",
        {"presupuesto_gasto": presupuesto_gasto}
    )


# =====================================================
# ELIMINAR GASTO PRESUPUESTADO
# =====================================================

@never_cache
@login_required
def gasto_eliminar(request, pk):

    presupuesto_gasto = get_object_or_404(
        PresupuestoGasto.objects.select_related("presupuesto", "partida"),
        pk=pk
    )
    presupuesto_pk = presupuesto_gasto.presupuesto.pk

    if request.method == "POST":
        presupuesto_gasto.delete()
        messages.success(request, "El gasto presupuestado fue eliminado.")
        return redirect("presupuesto_detalle", pk=presupuesto_pk)

    return render(
        request,
        "finanzas/presupuestos/gasto_eliminar.html",
        {"presupuesto_gasto": presupuesto_gasto}
    )


# =====================================================
# CATALOGO: CONCEPTOS DE INGRESO
# =====================================================

@never_cache
@login_required
def conceptos_lista(request):

    busqueda = request.GET.get("q", "")

    conceptos = ConceptoIngreso.objects.all().order_by("codigo")

    if busqueda:
        conceptos = conceptos.filter(
            Q(codigo__icontains=busqueda) | Q(nombre__icontains=busqueda)
        )

    return render(
        request,
        "finanzas/presupuestos/conceptos/lista.html",
        {"conceptos": conceptos, "busqueda": busqueda}
    )


@never_cache
@login_required
def concepto_crear(request):

    if request.method == "POST":

        codigo = (request.POST.get("codigo") or "").strip().upper()
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = request.POST.get("descripcion", "")
        activo = request.POST.get("activo") == "on"

        if not codigo:
            messages.error(request, "El código es obligatorio.")
            return render(request, "finanzas/presupuestos/conceptos/concepto_crear.html", {})

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return render(request, "finanzas/presupuestos/conceptos/concepto_crear.html", {})

        if ConceptoIngreso.objects.filter(codigo__iexact=codigo).exists():
            messages.error(request, f"Ya existe un concepto con el código {codigo}.")
            return render(request, "finanzas/presupuestos/conceptos/concepto_crear.html", {})

        ConceptoIngreso.objects.create(
            codigo=codigo, nombre=nombre, descripcion=descripcion, activo=activo,
        )

        messages.success(request, "El concepto de ingreso se creó correctamente.")
        return redirect("conceptos_lista")

    return render(request, "finanzas/presupuestos/conceptos/concepto_crear.html", {})


@never_cache
@login_required
def concepto_editar(request, pk):

    concepto = get_object_or_404(ConceptoIngreso, pk=pk)

    if request.method == "POST":

        codigo = (request.POST.get("codigo") or "").strip().upper()
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = request.POST.get("descripcion", "")
        activo = request.POST.get("activo") == "on"

        contexto_base = {"concepto": concepto}

        if not codigo:
            messages.error(request, "El código es obligatorio.")
            return render(request, "finanzas/presupuestos/conceptos/concepto_editar.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return render(request, "finanzas/presupuestos/concepto_editar.html", contexto_base)

        if ConceptoIngreso.objects.filter(codigo__iexact=codigo).exclude(pk=pk).exists():
            messages.error(request, f"Ya existe otro concepto con el código {codigo}.")
            return render(request, "finanzas/presupuestos/conceptos/concepto_editar.html", contexto_base)

        concepto.codigo = codigo
        concepto.nombre = nombre
        concepto.descripcion = descripcion
        concepto.activo = activo
        concepto.save()

        messages.success(request, "El concepto de ingreso se actualizó correctamente.")
        return redirect("conceptos_lista")

    return render(request, "finanzas/presupuestos/conceptos/concepto_editar.html", {"concepto": concepto})


@login_required
@require_POST
def concepto_toggle_activo(request, pk):

    concepto = get_object_or_404(ConceptoIngreso, pk=pk)
    concepto.activo = not concepto.activo
    concepto.save(update_fields=["activo"])

    estado = "activado" if concepto.activo else "desactivado"
    messages.success(request, f"El concepto {concepto.codigo} fue {estado}.")

    return redirect("conceptos_lista")


@never_cache
@login_required
def concepto_eliminar(request, pk):

    concepto = get_object_or_404(ConceptoIngreso, pk=pk)

    if request.method == "POST":

        try:
            concepto.delete()
        except models.ProtectedError:
            messages.error(
                request,
                "No se puede eliminar este concepto porque ya está siendo usado "
                "en uno o más presupuestos. Puedes desactivarlo en su lugar."
            )
            return redirect("conceptos_lista")

        messages.success(request, "El concepto de ingreso fue eliminado.")
        return redirect("conceptos_lista")

    return render(request, "finanzas/presupuestos/conceptos/concepto_eliminar.html", {"concepto": concepto})


# =====================================================
# CATALOGO: PARTIDAS DE GASTO
# =====================================================

@never_cache
@login_required
def partidas_lista(request):

    busqueda = request.GET.get("q", "")

    partidas = PartidaGasto.objects.select_related("partida_padre").all().order_by("codigo")

    if busqueda:
        partidas = partidas.filter(
            Q(codigo__icontains=busqueda) | Q(nombre__icontains=busqueda)
        )

    return render(
        request,
        "finanzas/presupuestos/partidas/lista.html",
        {"partidas": partidas, "busqueda": busqueda}
    )


@never_cache
@login_required
def partida_crear(request):

    partidas_disponibles = PartidaGasto.objects.filter(activo=True).order_by("codigo")
    contexto_base = {"partidas_disponibles": partidas_disponibles}

    if request.method == "POST":

        codigo = (request.POST.get("codigo") or "").strip().upper()
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = request.POST.get("descripcion", "")
        partida_padre_id = request.POST.get("partida_padre") or None
        activo = request.POST.get("activo") == "on"

        if not codigo:
            messages.error(request, "El código es obligatorio.")
            return render(request, "finanzas/presupuestos/partidas/partida_crear.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return render(request, "finanzas/presupuestos/partidas/partida_crear.html", contexto_base)

        if PartidaGasto.objects.filter(codigo__iexact=codigo).exists():
            messages.error(request, f"Ya existe una partida con el código {codigo}.")
            return render(request, "finanzas/presupuestos/partidas/partida_crear.html", contexto_base)

        partida_padre = None
        if partida_padre_id:
            partida_padre = get_object_or_404(PartidaGasto, pk=partida_padre_id)

        PartidaGasto.objects.create(
            codigo=codigo, nombre=nombre, descripcion=descripcion,
            partida_padre=partida_padre, activo=activo,
        )

        messages.success(request, "La partida de gasto se creó correctamente.")
        return redirect("partidas_lista")

    return render(request, "finanzas/presupuestos/partidas/partida_crear.html", contexto_base)


@never_cache
@login_required
def partida_editar(request, pk):

    partida = get_object_or_404(PartidaGasto, pk=pk)

    partidas_disponibles = (
        PartidaGasto.objects.filter(activo=True).exclude(pk=pk).order_by("codigo")
    )

    if request.method == "POST":

        codigo = (request.POST.get("codigo") or "").strip().upper()
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = request.POST.get("descripcion", "")
        partida_padre_id = request.POST.get("partida_padre") or None
        activo = request.POST.get("activo") == "on"

        contexto_base = {"partida": partida, "partidas_disponibles": partidas_disponibles}

        if not codigo:
            messages.error(request, "El código es obligatorio.")
            return render(request, "finanzas/presupuestos/partidas/partida_editar.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return render(request, "finanzas/presupuestos/partidas/partida_editar.html", contexto_base)

        if PartidaGasto.objects.filter(codigo__iexact=codigo).exclude(pk=pk).exists():
            messages.error(request, f"Ya existe otra partida con el código {codigo}.")
            return render(request, "finanzas/presupuestos/partidas/partida_editar.html", contexto_base)

        partida_padre = None
        if partida_padre_id:
            if str(partida_padre_id) == str(pk):
                messages.error(request, "Una partida no puede ser su propia partida padre.")
                return render(request, "finanzas/presupuestos/partidas/partida_editar.html", contexto_base)
            partida_padre = get_object_or_404(PartidaGasto, pk=partida_padre_id)

        partida.codigo = codigo
        partida.nombre = nombre
        partida.descripcion = descripcion
        partida.partida_padre = partida_padre
        partida.activo = activo
        partida.save()

        messages.success(request, "La partida de gasto se actualizó correctamente.")
        return redirect("partidas_lista")

    return render(
        request,
        "finanzas/presupuestos/partidas/partida_editar.html",
        {"partida": partida, "partidas_disponibles": partidas_disponibles}
    )


@login_required
@require_POST
def partida_toggle_activo(request, pk):

    partida = get_object_or_404(PartidaGasto, pk=pk)
    partida.activo = not partida.activo
    partida.save(update_fields=["activo"])

    estado = "activada" if partida.activo else "desactivada"
    messages.success(request, f"La partida {partida.codigo} fue {estado}.")

    return redirect("partidas_lista")


@never_cache
@login_required
def partida_eliminar(request, pk):

    partida = get_object_or_404(PartidaGasto, pk=pk)

    if request.method == "POST":

        try:
            partida.delete()
        except models.ProtectedError:
            messages.error(
                request,
                "No se puede eliminar esta partida porque tiene subpartidas o ya "
                "está siendo usada en uno o más presupuestos. Puedes desactivarla "
                "en su lugar."
            )
            return redirect("partidas_lista")

        messages.success(request, "La partida de gasto fue eliminada.")
        return redirect("partidas_lista")

    return render(request, "finanzas/presupuestos/partidas/partida_eliminar.html", {"partida": partida})

# =====================================================
# CATALOGO: CATEGORÍAS DE MOVIMIENTO
# =====================================================

@never_cache
@login_required
def categorias_movimiento_lista(request):

    busqueda = request.GET.get("q", "")

    categorias = CategoriaMovimiento.objects.all().order_by("tipo", "codigo")

    if busqueda:
        categorias = categorias.filter(
            Q(codigo__icontains=busqueda) | Q(nombre__icontains=busqueda)
        )

    return render(
        request,
        "finanzas/programa_pagos/categorias_lista.html",
        {"categorias": categorias, "busqueda": busqueda}
    )


@never_cache
@login_required
def categoria_movimiento_crear(request):

    contexto_base = {"tipos": CategoriaMovimiento.Tipo.choices}

    if request.method == "POST":

        codigo = (request.POST.get("codigo") or "").strip().upper()
        nombre = (request.POST.get("nombre") or "").strip()
        tipo = request.POST.get("tipo")
        activo = request.POST.get("activo") == "on"

        if not codigo:
            messages.error(request, "El código es obligatorio.")
            return render(request, "finanzas/programa_pagos/categoria_crear.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return render(request, "finanzas/programa_pagos/categoria_crear.html", contexto_base)

        if tipo not in CategoriaMovimiento.Tipo.values:
            messages.error(request, "Debe seleccionar un tipo válido (Ingreso o Egreso).")
            return render(request, "finanzas/programa_pagos/categoria_crear.html", contexto_base)

        if CategoriaMovimiento.objects.filter(codigo__iexact=codigo).exists():
            messages.error(request, f"Ya existe una categoría con el código {codigo}.")
            return render(request, "finanzas/programa_pagos/categoria_crear.html", contexto_base)

        CategoriaMovimiento.objects.create(codigo=codigo, nombre=nombre, tipo=tipo, activo=activo)

        messages.success(request, "La categoría se creó correctamente.")
        return redirect("categorias_movimiento_lista")

    return render(request, "finanzas/programa_pagos/categoria_crear.html", contexto_base)


@never_cache
@login_required
def categoria_movimiento_editar(request, pk):

    categoria = get_object_or_404(CategoriaMovimiento, pk=pk)
    contexto_base = {"categoria": categoria, "tipos": CategoriaMovimiento.Tipo.choices}

    if request.method == "POST":

        codigo = (request.POST.get("codigo") or "").strip().upper()
        nombre = (request.POST.get("nombre") or "").strip()
        tipo = request.POST.get("tipo")
        activo = request.POST.get("activo") == "on"

        if not codigo:
            messages.error(request, "El código es obligatorio.")
            return render(request, "finanzas/programa_pagos/categoria_editar.html", contexto_base)

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return render(request, "finanzas/programa_pagos/categoria_editar.html", contexto_base)

        if tipo not in CategoriaMovimiento.Tipo.values:
            messages.error(request, "Debe seleccionar un tipo válido (Ingreso o Egreso).")
            return render(request, "finanzas/programa_pagos/categoria_editar.html", contexto_base)

        if CategoriaMovimiento.objects.filter(codigo__iexact=codigo).exclude(pk=pk).exists():
            messages.error(request, f"Ya existe otra categoría con el código {codigo}.")
            return render(request, "finanzas/programa_pagos/categoria_editar.html", contexto_base)

        categoria.codigo = codigo
        categoria.nombre = nombre
        categoria.tipo = tipo
        categoria.activo = activo
        categoria.save()

        messages.success(request, "La categoría se actualizó correctamente.")
        return redirect("categorias_movimiento_lista")

    return render(request, "finanzas/programa_pagos/categoria_editar.html", contexto_base)


@login_required
@require_POST
def categoria_movimiento_toggle_activo(request, pk):

    categoria = get_object_or_404(CategoriaMovimiento, pk=pk)
    categoria.activo = not categoria.activo
    categoria.save(update_fields=["activo"])

    estado = "activada" if categoria.activo else "desactivada"
    messages.success(request, f"La categoría {categoria.codigo} fue {estado}.")

    return redirect("categorias_movimiento_lista")


@never_cache
@login_required
def categoria_movimiento_eliminar(request, pk):

    categoria = get_object_or_404(CategoriaMovimiento, pk=pk)

    if request.method == "POST":

        try:
            categoria.delete()
        except models.ProtectedError:
            messages.error(
                request,
                "No se puede eliminar esta categoría porque ya está siendo usada "
                "en uno o más movimientos programados. Puedes desactivarla en su lugar."
            )
            return redirect("categorias_movimiento_lista")

        messages.success(request, "La categoría fue eliminada.")
        return redirect("categorias_movimiento_lista")

    return render(request, "finanzas/programa_pagos/categoria_eliminar.html", {"categoria": categoria})


# =====================================================
# PROGRAMA DE PAGOS
# =====================================================

@never_cache
@login_required
def programas_lista(request):
    programas = ProgramaPago.objects.all().order_by("-fecha_inicio")
    return render(request, "finanzas/programa_pagos/lista.html", {"programas": programas})


@never_cache
@login_required
def programa_crear(request):

    # El "tail" de la cadena: el último programa que todavía no tiene
    # un programa_siguiente asignado. Así el saldo siempre se sugiere
    # a partir del periodo más reciente sin encadenar dos veces al mismo.
    ultimo_programa = (
        ProgramaPago.objects
        .filter(programa_siguiente__isnull=True)
        .order_by("-fecha_fin")
        .first()
    )

    saldo_sugerido = ultimo_programa.saldo_final if ultimo_programa else Decimal("0.00")

    contexto_base = {
        "saldo_sugerido": saldo_sugerido,
        "ultimo_programa": ultimo_programa,
    }

    if request.method == "POST":

        fecha_inicio = request.POST.get("fecha_inicio")
        fecha_fin = request.POST.get("fecha_fin")
        observaciones = request.POST.get("observaciones", "")

        if not fecha_inicio or not fecha_fin:
            messages.error(request, "Debe especificar fecha de inicio y de fin.")
            return render(request, "finanzas/programa_pagos/crear.html", contexto_base)

        if fecha_fin < fecha_inicio:
            messages.error(request, "La fecha de fin no puede ser anterior a la fecha de inicio.")
            return render(request, "finanzas/programa_pagos/crear.html", contexto_base)

        if ProgramaPago.objects.filter(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin).exists():
            messages.error(request, "Ya existe un programa de pagos para ese periodo exacto.")
            return render(request, "finanzas/programa_pagos/crear.html", contexto_base)

        try:
            saldo_inicial = Decimal(request.POST.get("saldo_inicial") or "0")
        except InvalidOperation:
            messages.error(request, "El saldo inicial debe ser un número válido.")
            return render(request, "finanzas/programa_pagos/crear.html", contexto_base)

        programa = ProgramaPago.objects.create(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            saldo_inicial=saldo_inicial,
            observaciones=observaciones,
            programa_anterior=ultimo_programa,
        )

        messages.success(request, "El programa de pagos se creó correctamente.")
        return redirect("programa_detalle", pk=programa.pk)

    return render(request, "finanzas/programa_pagos/crear.html", contexto_base)


@never_cache
@login_required
def programa_detalle(request, pk):

    programa = get_object_or_404(ProgramaPago, pk=pk)

    movimientos = (
        programa.movimientos
        .select_related("categoria", "factura_proveedor")
        .order_by("fecha_programada", "id")
    )

    ingresos = movimientos.filter(categoria__tipo=CategoriaMovimiento.Tipo.INGRESO)
    egresos = movimientos.filter(categoria__tipo=CategoriaMovimiento.Tipo.EGRESO)

    return render(
        request,
        "finanzas/programa_pagos/detalle.html",
        {
            "programa": programa,
            "ingresos": ingresos,
            "egresos": egresos,
            "total_ingresos": programa.total_ingresos,
            "total_egresos": programa.total_egresos,
            "saldo_final": programa.saldo_final,
        }
    )


@never_cache
@login_required
def programa_editar(request, pk):

    programa = get_object_or_404(ProgramaPago, pk=pk)

    if programa.estatus == ProgramaPago.Estatus.CERRADO:
        messages.error(request, "No se puede editar un programa de pagos cerrado.")
        return redirect("programa_detalle", pk=pk)

    contexto_base = {"programa": programa}

    if request.method == "POST":

        fecha_inicio = request.POST.get("fecha_inicio")
        fecha_fin = request.POST.get("fecha_fin")
        observaciones = request.POST.get("observaciones", "")

        if not fecha_inicio or not fecha_fin:
            messages.error(request, "Debe especificar fecha de inicio y de fin.")
            return render(request, "finanzas/programa_pagos/editar.html", contexto_base)

        if fecha_fin < fecha_inicio:
            messages.error(request, "La fecha de fin no puede ser anterior a la fecha de inicio.")
            return render(request, "finanzas/programa_pagos/editar.html", contexto_base)

        if ProgramaPago.objects.filter(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin).exclude(pk=pk).exists():
            messages.error(request, "Ya existe otro programa de pagos para ese periodo exacto.")
            return render(request, "finanzas/programa_pagos/editar.html", contexto_base)

        try:
            saldo_inicial = Decimal(request.POST.get("saldo_inicial") or "0")
        except InvalidOperation:
            messages.error(request, "El saldo inicial debe ser un número válido.")
            return render(request, "finanzas/programa_pagos/editar.html", contexto_base)

        programa.fecha_inicio = fecha_inicio
        programa.fecha_fin = fecha_fin
        programa.saldo_inicial = saldo_inicial
        programa.observaciones = observaciones
        programa.save()

        messages.success(request, "El programa de pagos se actualizó correctamente.")
        return redirect("programa_detalle", pk=pk)

    return render(request, "finanzas/programa_pagos/editar.html", contexto_base)


@never_cache
@login_required
def programa_eliminar(request, pk):

    programa = get_object_or_404(ProgramaPago, pk=pk)
    total_movimientos = programa.movimientos.count()

    if request.method == "POST":
        programa.delete()
        messages.success(request, "El programa de pagos fue eliminado.")
        return redirect("programas_lista")

    return render(
        request,
        "finanzas/programa_pagos/eliminar.html",
        {"programa": programa, "total_movimientos": total_movimientos}
    )


@never_cache
@login_required
def programa_cerrar(request, pk):

    programa = get_object_or_404(ProgramaPago, pk=pk)

    if programa.estatus == ProgramaPago.Estatus.CERRADO:
        messages.info(request, "Este programa ya está cerrado.")
        return redirect("programa_detalle", pk=pk)

    if request.method == "POST":
        programa.estatus = ProgramaPago.Estatus.CERRADO
        programa.save(update_fields=["estatus"])
        messages.success(request, "El programa de pagos fue cerrado.")
        return redirect("programa_detalle", pk=pk)

    return render(request, "finanzas/programa_pagos/cerrar.html", {"programa": programa})

# =====================================================
# MOVIMIENTOS DEL PROGRAMA
# =====================================================

@never_cache
@login_required
def movimiento_crear(request, pk):

    programa = get_object_or_404(ProgramaPago, pk=pk)

    if programa.estatus == ProgramaPago.Estatus.CERRADO:
        messages.error(request, "No se pueden agregar movimientos a un programa cerrado.")
        return redirect("programa_detalle", pk=pk)

    categorias = CategoriaMovimiento.objects.filter(activo=True).order_by("tipo", "codigo")

    # Facturas de proveedor aún no pagadas/canceladas, para poder ligarlas
    # opcionalmente a un movimiento de egreso.
    facturas_disponibles = (
        FacturaProveedor.objects
        .exclude(estatus__in=[FacturaProveedor.Estatus.PAGADA, FacturaProveedor.Estatus.CANCELADA])
        .select_related("expediente")
        .order_by("fecha_vencimiento")
    )

    contexto_base = {
        "programa": programa,
        "categorias": categorias,
        "facturas_disponibles": facturas_disponibles,
    }

    if request.method == "POST":

        categoria_id = request.POST.get("categoria")
        concepto = (request.POST.get("concepto") or "").strip()
        fecha_programada = request.POST.get("fecha_programada")
        factura_id = request.POST.get("factura_proveedor") or None
        observaciones = request.POST.get("observaciones", "")

        if not categoria_id:
            messages.error(request, "Debe seleccionar una categoría.")
            return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)

        categoria = get_object_or_404(CategoriaMovimiento, pk=categoria_id, activo=True)

        if not concepto:
            messages.error(request, "El concepto es obligatorio.")
            return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)

        if not fecha_programada:
            messages.error(request, "Debe especificar la fecha programada.")
            return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)

        if fecha_programada < str(programa.fecha_inicio) or fecha_programada > str(programa.fecha_fin):
            messages.error(
                request,
                "La fecha programada debe estar dentro del periodo del programa "
                f"({programa.fecha_inicio:%d/%m/%Y} - {programa.fecha_fin:%d/%m/%Y})."
            )
            return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)

        try:
            monto = Decimal(request.POST.get("monto") or "0")
        except InvalidOperation:
            messages.error(request, "El monto debe ser un número válido.")
            return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)

        factura_proveedor = None
        if factura_id:
            factura_proveedor = get_object_or_404(FacturaProveedor, pk=factura_id)

        MovimientoPrograma.objects.create(
            programa=programa,
            categoria=categoria,
            factura_proveedor=factura_proveedor,
            concepto=concepto,
            fecha_programada=fecha_programada,
            monto=monto,
            observaciones=observaciones,
        )

        messages.success(request, "El movimiento fue agregado correctamente.")
        return redirect("programa_detalle", pk=programa.pk)

    return render(request, "finanzas/programa_pagos/movimiento_crear.html", contexto_base)


@never_cache
@login_required
def movimiento_editar(request, pk):

    movimiento = get_object_or_404(
        MovimientoPrograma.objects.select_related("programa", "categoria", "factura_proveedor"),
        pk=pk
    )
    programa = movimiento.programa

    if programa.estatus == ProgramaPago.Estatus.CERRADO:
        messages.error(request, "No se pueden editar movimientos de un programa cerrado.")
        return redirect("programa_detalle", pk=programa.pk)

    categorias = CategoriaMovimiento.objects.filter(activo=True).order_by("tipo", "codigo")
    facturas_disponibles = (
        FacturaProveedor.objects
        .exclude(estatus__in=[FacturaProveedor.Estatus.PAGADA, FacturaProveedor.Estatus.CANCELADA])
        .select_related("expediente")
        .order_by("fecha_vencimiento")
    )

    contexto_base = {
        "movimiento": movimiento,
        "programa": programa,
        "categorias": categorias,
        "facturas_disponibles": facturas_disponibles,
    }

    if request.method == "POST":

        categoria_id = request.POST.get("categoria")
        concepto = (request.POST.get("concepto") or "").strip()
        fecha_programada = request.POST.get("fecha_programada")
        factura_id = request.POST.get("factura_proveedor") or None
        estatus = request.POST.get("estatus", movimiento.estatus)
        observaciones = request.POST.get("observaciones", "")

        if not categoria_id:
            messages.error(request, "Debe seleccionar una categoría.")
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        categoria = get_object_or_404(CategoriaMovimiento, pk=categoria_id, activo=True)

        if not concepto:
            messages.error(request, "El concepto es obligatorio.")
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        if not fecha_programada:
            messages.error(request, "Debe especificar la fecha programada.")
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        if fecha_programada < str(programa.fecha_inicio) or fecha_programada > str(programa.fecha_fin):
            messages.error(
                request,
                "La fecha programada debe estar dentro del periodo del programa "
                f"({programa.fecha_inicio:%d/%m/%Y} - {programa.fecha_fin:%d/%m/%Y})."
            )
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        try:
            monto = Decimal(request.POST.get("monto") or "0")
        except InvalidOperation:
            messages.error(request, "El monto debe ser un número válido.")
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        if estatus not in MovimientoPrograma.Estatus.values:
            messages.error(request, "Estatus no válido.")
            return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)

        factura_proveedor = None
        if factura_id:
            factura_proveedor = get_object_or_404(FacturaProveedor, pk=factura_id)

        movimiento.categoria = categoria
        movimiento.factura_proveedor = factura_proveedor
        movimiento.concepto = concepto
        movimiento.fecha_programada = fecha_programada
        movimiento.monto = monto
        movimiento.estatus = estatus
        movimiento.observaciones = observaciones
        movimiento.save()

        messages.success(request, "El movimiento se actualizó correctamente.")
        return redirect("programa_detalle", pk=programa.pk)

    return render(request, "finanzas/programa_pagos/movimiento_editar.html", contexto_base)


@never_cache
@login_required
def movimiento_eliminar(request, pk):

    movimiento = get_object_or_404(
        MovimientoPrograma.objects.select_related("programa", "categoria"),
        pk=pk
    )
    programa = movimiento.programa

    if programa.estatus == ProgramaPago.Estatus.CERRADO:
        messages.error(request, "No se pueden eliminar movimientos de un programa cerrado.")
        return redirect("programa_detalle", pk=programa.pk)

    if request.method == "POST":
        movimiento.delete()
        messages.success(request, "El movimiento fue eliminado.")
        return redirect("programa_detalle", pk=programa.pk)

    return render(
        request,
        "finanzas/programa_pagos/movimiento_eliminar.html",
        {"movimiento": movimiento, "programa": programa}
    )

# =====================================================
# CATALOGO: CUENTAS BANCARIAS
# =====================================================

@never_cache
@login_required
def cuentas_bancarias_lista(request):
    cuentas = CuentaBancaria.objects.all().order_by("banco", "alias")
    return render(request, "finanzas/bancos/cuentas_lista.html", {"cuentas": cuentas})


@never_cache
@login_required
def cuenta_bancaria_crear(request):

    contexto_base = {"monedas": CuentaBancaria.Moneda.choices}

    if request.method == "POST":

        alias = (request.POST.get("alias") or "").strip()
        banco = (request.POST.get("banco") or "").strip()
        numero_cuenta = (request.POST.get("numero_cuenta") or "").strip()
        clabe = (request.POST.get("clabe") or "").strip()
        moneda = request.POST.get("moneda", CuentaBancaria.Moneda.MXN)
        activa = request.POST.get("activa") == "on"

        if not alias:
            messages.error(request, "El alias es obligatorio.")
            return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)

        if not banco:
            messages.error(request, "El banco es obligatorio.")
            return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)

        if not numero_cuenta:
            messages.error(request, "El número de cuenta es obligatorio.")
            return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)

        if CuentaBancaria.objects.filter(numero_cuenta=numero_cuenta).exists():
            messages.error(request, "Ya existe una cuenta registrada con ese número.")
            return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)

        if moneda not in CuentaBancaria.Moneda.values:
            messages.error(request, "Moneda no válida.")
            return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)

        try:
            saldo_inicial = Decimal(request.POST.get("saldo_inicial") or "0")
        except InvalidOperation:
            messages.error(request, "El saldo inicial debe ser un número válido.")
            return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)

        CuentaBancaria.objects.create(
            alias=alias, banco=banco, numero_cuenta=numero_cuenta, clabe=clabe,
            moneda=moneda, saldo_inicial=saldo_inicial, activa=activa,
        )

        messages.success(request, "La cuenta bancaria se creó correctamente.")
        return redirect("cuentas_bancarias_lista")

    return render(request, "finanzas/bancos/cuenta_crear.html", contexto_base)


@never_cache
@login_required
def cuenta_bancaria_editar(request, pk):

    cuenta = get_object_or_404(CuentaBancaria, pk=pk)
    contexto_base = {"cuenta": cuenta, "monedas": CuentaBancaria.Moneda.choices}

    if request.method == "POST":

        alias = (request.POST.get("alias") or "").strip()
        banco = (request.POST.get("banco") or "").strip()
        numero_cuenta = (request.POST.get("numero_cuenta") or "").strip()
        clabe = (request.POST.get("clabe") or "").strip()
        moneda = request.POST.get("moneda", CuentaBancaria.Moneda.MXN)
        activa = request.POST.get("activa") == "on"

        if not alias:
            messages.error(request, "El alias es obligatorio.")
            return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)

        if not banco:
            messages.error(request, "El banco es obligatorio.")
            return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)

        if not numero_cuenta:
            messages.error(request, "El número de cuenta es obligatorio.")
            return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)

        if CuentaBancaria.objects.filter(numero_cuenta=numero_cuenta).exclude(pk=pk).exists():
            messages.error(request, "Ya existe otra cuenta registrada con ese número.")
            return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)

        if moneda not in CuentaBancaria.Moneda.values:
            messages.error(request, "Moneda no válida.")
            return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)

        try:
            saldo_inicial = Decimal(request.POST.get("saldo_inicial") or "0")
        except InvalidOperation:
            messages.error(request, "El saldo inicial debe ser un número válido.")
            return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)

        cuenta.alias = alias
        cuenta.banco = banco
        cuenta.numero_cuenta = numero_cuenta
        cuenta.clabe = clabe
        cuenta.moneda = moneda
        cuenta.saldo_inicial = saldo_inicial
        cuenta.activa = activa
        cuenta.save()

        messages.success(request, "La cuenta bancaria se actualizó correctamente.")
        return redirect("cuentas_bancarias_lista")

    return render(request, "finanzas/bancos/cuenta_editar.html", contexto_base)


@never_cache
@login_required
def cuenta_bancaria_eliminar(request, pk):

    cuenta = get_object_or_404(CuentaBancaria, pk=pk)

    if request.method == "POST":

        try:
            cuenta.delete()
        except models.ProtectedError:
            messages.error(
                request,
                "No se puede eliminar esta cuenta porque ya tiene movimientos "
                "bancarios registrados. Puedes desactivarla en su lugar."
            )
            return redirect("cuentas_bancarias_lista")

        messages.success(request, "La cuenta bancaria fue eliminada.")
        return redirect("cuentas_bancarias_lista")

    return render(request, "finanzas/bancos/cuenta_eliminar.html", {"cuenta": cuenta})

    # =====================================================
# MOVIMIENTOS BANCARIOS
# =====================================================

@never_cache
@login_required
def movimientos_bancarios_lista(request):

    cuenta_id = request.GET.get("cuenta", "")
    busqueda = request.GET.get("q", "")
    conciliado = request.GET.get("conciliado", "")

    movimientos = (
        MovimientoBancario.objects
        .select_related("cuenta", "expediente", "factura_cliente", "factura_proveedor")
        .all()
    )

    if cuenta_id:
        movimientos = movimientos.filter(cuenta_id=cuenta_id)

    if busqueda:
        movimientos = movimientos.filter(
            Q(concepto_bancario__icontains=busqueda) |
            Q(mov__icontains=busqueda) |
            Q(expediente__razon_social__icontains=busqueda) |
            Q(expediente__nombres__icontains=busqueda) |
            Q(expediente__rfc__icontains=busqueda)
        )

    if conciliado == "si":
        movimientos = movimientos.filter(conciliado=True)
    elif conciliado == "no":
        movimientos = movimientos.filter(conciliado=False)

    paginator = Paginator(movimientos, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "finanzas/bancos/movimientos_lista.html",
        {
            "movimientos": page_obj,
            "page_obj": page_obj,
            "cuentas": CuentaBancaria.objects.filter(activa=True).order_by("banco", "alias"),
            "cuenta_actual": cuenta_id,
            "busqueda": busqueda,
            "conciliado_actual": conciliado,
        }
    )


@never_cache
@login_required
def movimiento_bancario_crear(request):

    cuentas = CuentaBancaria.objects.filter(activa=True).order_by("banco", "alias")
    expedientes = Expediente.objects.all().order_by("razon_social", "nombres")
    facturas_cliente = (
        FacturaCliente.objects
        .exclude(estatus=FacturaCliente.Estatus.CANCELADA)
        .select_related("expediente")
        .order_by("-fecha_factura")
    )
    facturas_proveedor = (
        FacturaProveedor.objects
        .exclude(estatus=FacturaProveedor.Estatus.CANCELADA)
        .select_related("expediente")
        .order_by("-fecha_factura")
    )

    contexto_base = {
        "cuentas": cuentas,
        "expedientes": expedientes,
        "facturas_cliente": facturas_cliente,
        "facturas_proveedor": facturas_proveedor,
    }

    if request.method == "POST":

        cuenta_id = request.POST.get("cuenta")
        fecha = request.POST.get("fecha")
        concepto_bancario = (request.POST.get("concepto_bancario") or "").strip()
        mov = (request.POST.get("mov") or "").strip()
        expediente_id = request.POST.get("expediente") or None
        factura_cliente_id = request.POST.get("factura_cliente") or None
        factura_proveedor_id = request.POST.get("factura_proveedor") or None
        comentarios = request.POST.get("comentarios", "")

        if not cuenta_id:
            messages.error(request, "Debe seleccionar una cuenta bancaria.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        cuenta = get_object_or_404(CuentaBancaria, pk=cuenta_id, activa=True)

        if not fecha:
            messages.error(request, "Debe especificar la fecha del movimiento.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if not concepto_bancario:
            messages.error(request, "El concepto bancario es obligatorio.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        try:
            cargo = Decimal(request.POST.get("cargo") or "0")
            abono = Decimal(request.POST.get("abono") or "0")
            saldo = Decimal(request.POST.get("saldo") or "0")
        except InvalidOperation:
            messages.error(request, "Cargo, abono y saldo deben ser números válidos.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if cargo < 0 or abono < 0:
            messages.error(request, "Cargo y abono no pueden ser negativos.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if cargo > 0 and abono > 0:
            messages.error(request, "Un movimiento no puede tener cargo y abono al mismo tiempo.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if cargo == 0 and abono == 0:
            messages.error(request, "Debe capturar un cargo o un abono.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if factura_cliente_id and abono <= 0:
            messages.error(request, "Una factura de cliente solo puede ligarse a un movimiento de abono (cobro).")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if factura_proveedor_id and cargo <= 0:
            messages.error(request, "Una factura de proveedor solo puede ligarse a un movimiento de cargo (pago).")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        if factura_cliente_id and factura_proveedor_id:
            messages.error(request, "Un movimiento no puede ligarse a una factura de cliente y de proveedor a la vez.")
            return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        monto_factura_raw = request.POST.get("monto_factura")
        monto_factura = None
        if monto_factura_raw:
            try:
                monto_factura = Decimal(monto_factura_raw)
            except InvalidOperation:
                messages.error(request, "El monto de factura debe ser un número válido.")
                return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)

        expediente = get_object_or_404(Expediente, pk=expediente_id) if expediente_id else None
        factura_cliente = get_object_or_404(FacturaCliente, pk=factura_cliente_id) if factura_cliente_id else None
        factura_proveedor = get_object_or_404(FacturaProveedor, pk=factura_proveedor_id) if factura_proveedor_id else None

        MovimientoBancario.objects.create(
            cuenta=cuenta,
            fecha=fecha,
            concepto_bancario=concepto_bancario,
            mov=mov,
            cargo=cargo,
            abono=abono,
            saldo=saldo,
            expediente=expediente,
            factura_cliente=factura_cliente,
            factura_proveedor=factura_proveedor,
            monto_factura=monto_factura,
            comentarios=comentarios,
        )

        messages.success(request, "El movimiento bancario se registró correctamente.")
        return redirect("movimientos_bancarios_lista")

    return render(request, "finanzas/bancos/movimiento_crear.html", contexto_base)


@never_cache
@login_required
def movimiento_bancario_editar(request, pk):

    movimiento = get_object_or_404(
        MovimientoBancario.objects.select_related("cuenta", "expediente", "factura_cliente", "factura_proveedor"),
        pk=pk
    )

    cuentas = CuentaBancaria.objects.filter(activa=True).order_by("banco", "alias")
    expedientes = Expediente.objects.all().order_by("razon_social", "nombres")
    facturas_cliente = (
        FacturaCliente.objects
        .exclude(estatus=FacturaCliente.Estatus.CANCELADA)
        .select_related("expediente")
        .order_by("-fecha_factura")
    )
    facturas_proveedor = (
        FacturaProveedor.objects
        .exclude(estatus=FacturaProveedor.Estatus.CANCELADA)
        .select_related("expediente")
        .order_by("-fecha_factura")
    )

    contexto_base = {
        "movimiento": movimiento,
        "cuentas": cuentas,
        "expedientes": expedientes,
        "facturas_cliente": facturas_cliente,
        "facturas_proveedor": facturas_proveedor,
    }

    if request.method == "POST":

        cuenta_id = request.POST.get("cuenta")
        fecha = request.POST.get("fecha")
        concepto_bancario = (request.POST.get("concepto_bancario") or "").strip()
        mov = (request.POST.get("mov") or "").strip()
        expediente_id = request.POST.get("expediente") or None
        factura_cliente_id = request.POST.get("factura_cliente") or None
        factura_proveedor_id = request.POST.get("factura_proveedor") or None
        comentarios = request.POST.get("comentarios", "")
        conciliado = request.POST.get("conciliado") == "on"

        if not cuenta_id:
            messages.error(request, "Debe seleccionar una cuenta bancaria.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        cuenta = get_object_or_404(CuentaBancaria, pk=cuenta_id, activa=True)

        if not fecha:
            messages.error(request, "Debe especificar la fecha del movimiento.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if not concepto_bancario:
            messages.error(request, "El concepto bancario es obligatorio.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        try:
            cargo = Decimal(request.POST.get("cargo") or "0")
            abono = Decimal(request.POST.get("abono") or "0")
            saldo = Decimal(request.POST.get("saldo") or "0")
        except InvalidOperation:
            messages.error(request, "Cargo, abono y saldo deben ser números válidos.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if cargo < 0 or abono < 0:
            messages.error(request, "Cargo y abono no pueden ser negativos.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if cargo > 0 and abono > 0:
            messages.error(request, "Un movimiento no puede tener cargo y abono al mismo tiempo.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if cargo == 0 and abono == 0:
            messages.error(request, "Debe capturar un cargo o un abono.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if factura_cliente_id and abono <= 0:
            messages.error(request, "Una factura de cliente solo puede ligarse a un movimiento de abono (cobro).")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if factura_proveedor_id and cargo <= 0:
            messages.error(request, "Una factura de proveedor solo puede ligarse a un movimiento de cargo (pago).")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        if factura_cliente_id and factura_proveedor_id:
            messages.error(request, "Un movimiento no puede ligarse a una factura de cliente y de proveedor a la vez.")
            return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        monto_factura_raw = request.POST.get("monto_factura")
        monto_factura = None
        if monto_factura_raw:
            try:
                monto_factura = Decimal(monto_factura_raw)
            except InvalidOperation:
                messages.error(request, "El monto de factura debe ser un número válido.")
                return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)

        expediente = get_object_or_404(Expediente, pk=expediente_id) if expediente_id else None
        factura_cliente = get_object_or_404(FacturaCliente, pk=factura_cliente_id) if factura_cliente_id else None
        factura_proveedor = get_object_or_404(FacturaProveedor, pk=factura_proveedor_id) if factura_proveedor_id else None

        movimiento.cuenta = cuenta
        movimiento.fecha = fecha
        movimiento.concepto_bancario = concepto_bancario
        movimiento.mov = mov
        movimiento.cargo = cargo
        movimiento.abono = abono
        movimiento.saldo = saldo
        movimiento.expediente = expediente
        movimiento.factura_cliente = factura_cliente
        movimiento.factura_proveedor = factura_proveedor
        movimiento.monto_factura = monto_factura
        movimiento.comentarios = comentarios
        movimiento.conciliado = conciliado
        movimiento.save()

        messages.success(request, "El movimiento bancario se actualizó correctamente.")
        return redirect("movimientos_bancarios_lista")

    return render(request, "finanzas/bancos/movimiento_editar.html", contexto_base)


@login_required
@require_POST
def movimiento_bancario_toggle_conciliado(request, pk):

    movimiento = get_object_or_404(MovimientoBancario, pk=pk)
    movimiento.conciliado = not movimiento.conciliado
    movimiento.save(update_fields=["conciliado"])

    estado = "conciliado" if movimiento.conciliado else "marcado como pendiente"
    messages.success(request, f"El movimiento fue {estado}.")

    return redirect("movimientos_bancarios_lista")


@never_cache
@login_required
def movimiento_bancario_eliminar(request, pk):

    movimiento = get_object_or_404(MovimientoBancario, pk=pk)

    if request.method == "POST":
        movimiento.delete()
        messages.success(request, "El movimiento bancario fue eliminado.")
        return redirect("movimientos_bancarios_lista")

    return render(request, "finanzas/bancos/movimiento_eliminar.html", {"movimiento": movimiento})