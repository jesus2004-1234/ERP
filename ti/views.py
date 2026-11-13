import json
import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, ProtectedError
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import (
    AsignacionForm, ConsumibleForm, CorreoForm, EmpleadoForm, EquipoForm, MantenimientoForm,
)
from .models import Empleado, Equipo, Consumible, Mantenimiento, Asignacion, Correos

logger = logging.getLogger(__name__)

TICKETS_CACHE_KEY = 'ti_tickets_api'


def _obtener_tickets():
    """
    Tickets de la API externa. Se guarda en caché unos minutos para que el dashboard
    no dependa de un servicio de terceros en cada carga; si la API falla, se registra
    en el log y se cachea la falla unos segundos (así no se espera el timeout en
    cada recarga).
    """
    tickets = cache.get(TICKETS_CACHE_KEY)
    if tickets is not None:
        return tickets

    try:
        respuesta = requests.get(settings.TICKETS_API_URL, timeout=3)
        respuesta.raise_for_status()
        tickets = respuesta.json().get('tickets', [])
    except (requests.RequestException, ValueError):
        logger.warning('No se pudo consultar la API de tickets', exc_info=True)
        cache.set(TICKETS_CACHE_KEY, [], 30)
        return []

    cache.set(TICKETS_CACHE_KEY, tickets, settings.TICKETS_API_CACHE_SECONDS)
    return tickets


def _errores_a_mensajes(request, form):
    """Muestra los errores de validación de un formulario como mensajes de la página."""
    for campo, errores in form.errors.items():
        etiqueta = ''
        if campo in form.fields:
            etiqueta = f'{form.fields[campo].label or campo}: '
        for error in errores:
            messages.error(request, f'{etiqueta}{error}')


@never_cache
@login_required
def dashboard(request):
    total_empleados   = Empleado.objects.count()
    total_equipos     = Equipo.objects.count()
    consumibles_bajos = Consumible.objects.filter(stock_actual__lte=5).count()

    todos_tickets     = _obtener_tickets()
    tickets_abiertos  = sum(1 for t in todos_tickets if t.get('estado') == 'Abierto')
    tickets_recientes = todos_tickets[:5]

    equipos_por_tipo = list(
        Equipo.objects.values('tipo').annotate(total=Count('tipo')).order_by('-total')
    )
    equipos_labels = json.dumps([e['tipo'] for e in equipos_por_tipo])
    equipos_data   = json.dumps([e['total'] for e in equipos_por_tipo])

    equipos_por_estatus = list(
    Equipo.objects
    .values('estatus').annotate(total=Count('estatus')).order_by('estatus')
)
    estatus_labels = json.dumps([e['estatus'] for e in equipos_por_estatus])
    estatus_data   = json.dumps([e['total'] for e in equipos_por_estatus])

    consumibles_por_cat = list(
        Consumible.objects.values('categoria').annotate(total=Count('categoria')).order_by('categoria')
    )
    consumibles_labels = json.dumps([c['categoria'] for c in consumibles_por_cat])
    consumibles_data   = json.dumps([c['total'] for c in consumibles_por_cat])

    proximos_mantenimientos = Mantenimiento.objects.filter(
        proxima_fecha_mantenimiento__isnull=False,
        proxima_fecha_mantenimiento__gte=timezone.localdate()
    ).order_by('proxima_fecha_mantenimiento')[:3]


    context = {
        'total_empleados':         total_empleados,
        'total_equipos':           total_equipos,
        'tickets_abiertos':        tickets_abiertos,
        'consumibles_bajos':       consumibles_bajos,
        'tickets_recientes':       tickets_recientes,
        'proximos_mantenimientos': proximos_mantenimientos,
        'equipos_labels':          equipos_labels,
        'equipos_data':            equipos_data,
        'estatus_labels':          estatus_labels,
        'estatus_data':            estatus_data,
        'consumibles_labels':      consumibles_labels,
        'consumibles_data':        consumibles_data,
    }
    return render(request, 'ti/ti_dashboard.html', context)


@never_cache
@login_required
def empleados_lista(request):
    busqueda     = request.GET.get('q', '')
    departamento = request.GET.get('departamento', '')

    empleados = Empleado.objects.all()

    if busqueda:
        empleados = empleados.filter(
            models.Q(nombre__icontains=busqueda) |
            models.Q(apellido__icontains=busqueda)
        )
    if departamento:
        empleados = empleados.filter(departamento=departamento)

    departamentos = Empleado.Departamento.choices

    return render(request, 'ti/empleados/lista.html', {
        'empleados':     empleados,
        'busqueda':      busqueda,
        'departamento':  departamento,
        'departamentos': departamentos,
    })


@never_cache
@login_required
def empleado_crear(request):
    if request.method == 'POST':
        form = EmpleadoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empleado creado correctamente.')
            return redirect('empleados_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/empleados/crear.html', {'departamentos': Empleado.Departamento.choices})


@never_cache
@login_required
def empleado_editar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        form = EmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empleado actualizado correctamente.')
            return redirect('empleados_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/empleados/editar.html', {'empleado': empleado, 'departamentos': Empleado.Departamento.choices})


@never_cache
@login_required
def empleado_eliminar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        try:
            empleado.delete()
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar al empleado porque tiene asignaciones de equipo '
                'registradas. Elimina o reasigna esas asignaciones primero.'
            )
            return redirect('empleados_lista')
        messages.success(request, 'Empleado eliminado correctamente.')
        return redirect('empleados_lista')
    return render(request, 'ti/empleados/eliminar.html', {'empleado': empleado})


@never_cache
@login_required
def equipos_lista(request):
    busqueda = request.GET.get('q', '')
    tipo     = request.GET.get('tipo', '')
    estatus  = request.GET.get('estatus', '')

    equipos = Equipo.objects.all()

    if busqueda:
        equipos = equipos.filter(
            models.Q(marca__icontains=busqueda) |
            models.Q(modelo__icontains=busqueda) |
            models.Q(numero_serie__icontains=busqueda)
        )
    if tipo:
        equipos = equipos.filter(tipo=tipo)
    if estatus:
        equipos = equipos.filter(estatus=estatus)

    return render(request, 'ti/equipos/lista.html', {
        'equipos':        equipos,
        'busqueda':       busqueda,
        'tipo_actual':    tipo,
        'estatus_actual': estatus,
    })


@never_cache
@login_required
def equipo_crear(request):
    empleados = Empleado.objects.all()
    if request.method == 'POST':
        form = EquipoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Equipo creado correctamente.')
            return redirect('equipos_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/equipos/crear.html', {'empleados': empleados})


@never_cache
@login_required
def equipo_editar(request, pk):
    equipo    = get_object_or_404(Equipo, pk=pk)
    empleados = Empleado.objects.all()
    if request.method == 'POST':
        form = EquipoForm(request.POST, instance=equipo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Equipo actualizado correctamente.')
            return redirect('equipos_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/equipos/editar.html', {'equipo': equipo, 'empleados': empleados})


@never_cache
@login_required
def equipo_eliminar(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    if request.method == 'POST':
        try:
            equipo.delete()
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar el equipo porque tiene asignaciones registradas. '
                'Cámbialo a estatus Baja o Inactivo en lugar de borrarlo.'
            )
            return redirect('equipos_lista')
        messages.success(request, 'Equipo eliminado correctamente.')
        return redirect('equipos_lista')
    return render(request, 'ti/equipos/eliminar.html', {'equipo': equipo})


@never_cache
@login_required
def asignaciones_lista(request):
    busqueda = request.GET.get('q', '')
    estatus  = request.GET.get('estatus', '')

    asignaciones = Asignacion.objects.all()

    if busqueda:
        asignaciones = asignaciones.filter(
            models.Q(equipo__marca__icontains=busqueda) |
            models.Q(equipo__modelo__icontains=busqueda) |
            models.Q(empleado__nombre__icontains=busqueda) |
            models.Q(empleado__apellido__icontains=busqueda)
        )
    if estatus:
        asignaciones = asignaciones.filter(estatus=estatus)

    return render(request, 'ti/asignaciones/lista.html', {
        'asignaciones':   asignaciones,
        'busqueda':       busqueda,
        'estatus_actual': estatus,
    })


@never_cache
@login_required
def asignacion_crear(request):
    equipos   = Equipo.objects.filter(estatus='Activo')
    empleados = Empleado.objects.all()
    contexto = {'equipos': equipos, 'empleados': empleados}
    if request.method == 'POST':
        form = AsignacionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                form.guardar()
            except ValidationError as error:
                # Equipo ya asignado (revisado dentro de la transacción con el equipo bloqueado).
                for mensaje in error.messages:
                    messages.error(request, mensaje)
            else:
                messages.success(request, 'Asignación creada correctamente.')
                return redirect('asignaciones_lista')
        else:
            _errores_a_mensajes(request, form)
    return render(request, 'ti/asignaciones/crear.html', contexto)


@never_cache
@login_required
def asignacion_editar(request, pk):
    asignacion = get_object_or_404(Asignacion, pk=pk)
    equipos    = Equipo.objects.filter(estatus='Activo')
    empleados  = Empleado.objects.all()
    contexto = {'asignacion': asignacion, 'equipos': equipos, 'empleados': empleados}
    if request.method == 'POST':
        form = AsignacionForm(request.POST, request.FILES, instance=asignacion)
        if form.is_valid():
            try:
                form.guardar()
            except ValidationError as error:
                for mensaje in error.messages:
                    messages.error(request, mensaje)
            else:
                messages.success(request, 'Asignación actualizada correctamente.')
                return redirect('asignaciones_lista')
        else:
            _errores_a_mensajes(request, form)
    return render(request, 'ti/asignaciones/editar.html', contexto)


@never_cache
@login_required
def asignacion_eliminar(request, pk):
    asignacion = get_object_or_404(Asignacion, pk=pk)
    if request.method == 'POST':
        asignacion.delete()
        messages.success(request, 'Asignación eliminada correctamente.')
        return redirect('asignaciones_lista')
    return render(request, 'ti/asignaciones/eliminar.html', {'asignacion': asignacion})


@never_cache
@login_required
def mantenimientos_lista(request):
    busqueda       = request.GET.get('q', '')
    tipo           = request.GET.get('tipo', '')
    estatus_filtro = request.GET.get('estatus', '')

    mantenimientos = Mantenimiento.objects.all()

    if busqueda:
        mantenimientos = mantenimientos.filter(
            models.Q(equipo__marca__icontains=busqueda) |
            models.Q(equipo__modelo__icontains=busqueda) |
            models.Q(realizado_por__icontains=busqueda)
        )
    if tipo:
        mantenimientos = mantenimientos.filter(tipo=tipo)
    if estatus_filtro:
        mantenimientos = [m for m in mantenimientos if m.estatus == estatus_filtro]

    return render(request, 'ti/mantenimientos/lista.html', {
        'mantenimientos': mantenimientos,
        'busqueda':       busqueda,
        'tipo_actual':    tipo,
        'estatus_actual': estatus_filtro,
    })


@never_cache
@login_required
def mantenimiento_crear(request):
    equipos = Equipo.objects.all()
    if request.method == 'POST':
        form = MantenimientoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mantenimiento registrado correctamente.')
            return redirect('mantenimientos_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/mantenimientos/crear.html', {'equipos': equipos})


@never_cache
@login_required
def mantenimiento_editar(request, pk):
    mantenimiento = get_object_or_404(Mantenimiento, pk=pk)
    equipos       = Equipo.objects.all()
    if request.method == 'POST':
        form = MantenimientoForm(request.POST, instance=mantenimiento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mantenimiento actualizado correctamente.')
            return redirect('mantenimientos_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/mantenimientos/editar.html', {'mantenimiento': mantenimiento, 'equipos': equipos})


@never_cache
@login_required
def mantenimiento_eliminar(request, pk):
    mantenimiento = get_object_or_404(Mantenimiento, pk=pk)
    if request.method == 'POST':
        mantenimiento.delete()
        messages.success(request, 'Mantenimiento eliminado correctamente.')
        return redirect('mantenimientos_lista')
    return render(request, 'ti/mantenimientos/eliminar.html', {'mantenimiento': mantenimiento})


@never_cache
@login_required
def correos_lista(request):
    busqueda = request.GET.get('q', '')
    estatus  = request.GET.get('estatus', '')
    tipo     = request.GET.get('tipo', '')

    correos = Correos.objects.all()

    if busqueda:
        correos = correos.filter(
            models.Q(correo_asignado__icontains=busqueda) |
            models.Q(empleado__nombre__icontains=busqueda) |
            models.Q(empleado__apellido__icontains=busqueda)
        )
    if estatus:
        correos = correos.filter(estatus=estatus)
    if tipo:
        correos = correos.filter(tipo=tipo)

    return render(request, 'ti/correos/lista.html', {
        'correos':        correos,
        'busqueda':       busqueda,
        'estatus_actual': estatus,
        'tipo_actual':    tipo,
    })


@never_cache
@login_required
def correo_crear(request):
    empleados = Empleado.objects.all()
    if request.method == 'POST':
        form = CorreoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registro creado correctamente.')
            return redirect('correos_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/correos/crear.html', {'empleados': empleados})


@never_cache
@login_required
def correo_editar(request, pk):
    correo    = get_object_or_404(Correos, pk=pk)
    empleados = Empleado.objects.all()
    if request.method == 'POST':
        form = CorreoForm(request.POST, instance=correo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registro actualizado correctamente.')
            return redirect('correos_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/correos/editar.html', {'correo': correo, 'empleados': empleados})


@never_cache
@login_required
def correo_eliminar(request, pk):
    correo = get_object_or_404(Correos, pk=pk)
    if request.method == 'POST':
        correo.delete()
        messages.success(request, 'Registro eliminado correctamente.')
        return redirect('correos_lista')
    return render(request, 'ti/correos/eliminar.html', {'correo': correo})


@never_cache
@login_required
def consumibles_lista(request):
    busqueda   = request.GET.get('q', '')
    categoria  = request.GET.get('categoria', '')
    stock_bajo = request.GET.get('stock_bajo','')
   

    consumibles = Consumible.objects.all()

    if busqueda:
        consumibles = consumibles.filter(
            models.Q(nombre__icontains=busqueda) |
            models.Q(descripcion__icontains=busqueda)
        )
    if categoria:
        consumibles = consumibles.filter(categoria=categoria)

    if stock_bajo:
        consumibles = consumibles.filter(stock_actual__lte=5)

    return render(request, 'ti/consumibles/lista.html', {
        'consumibles':      consumibles,
        'busqueda':         busqueda,
        'categoria_actual': categoria,
        'stock_actual': stock_bajo,
    })


@never_cache
@login_required
def consumible_crear(request):
    if request.method == 'POST':
        form = ConsumibleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Consumible registrado correctamente.')
            return redirect('consumibles_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/consumibles/crear.html')


@never_cache
@login_required
def consumible_editar(request, pk):
    consumible = get_object_or_404(Consumible, pk=pk)
    if request.method == 'POST':
        form = ConsumibleForm(request.POST, instance=consumible)
        if form.is_valid():
            form.save()
            messages.success(request, 'Consumible actualizado correctamente.')
            return redirect('consumibles_lista')
        _errores_a_mensajes(request, form)
    return render(request, 'ti/consumibles/editar.html', {'consumible': consumible})


@never_cache
@login_required
def consumible_eliminar(request, pk):
    consumible = get_object_or_404(Consumible, pk=pk)
    if request.method == 'POST':
        consumible.delete()
        messages.success(request, 'Consumible eliminado correctamente.')
        return redirect('consumibles_lista')
    return render(request, 'ti/consumibles/eliminar.html', {'consumible': consumible})


@never_cache
@login_required
def tickets_lista(request):
    try:
        response = requests.get('https://jesusaav4.pythonanywhere.com/api/tickets', timeout=5)
        data     = response.json()
        tickets  = data.get('tickets', [])
    except Exception:
        tickets = []
        messages.error(request, 'No se pudo conectar con el sistema de tickets.')
    return render(request, 'ti/tickets/lista.html', {'tickets': tickets})