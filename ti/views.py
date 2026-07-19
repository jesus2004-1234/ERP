from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db import models
from django.utils import timezone
from .models import Empleado, Equipo, Consumible, Mantenimiento, Asignacion, Correos
import requests


@never_cache
@login_required
def dashboard(request):
    import json
    from django.db.models import Count

    total_empleados   = Empleado.objects.count()
    total_equipos     = Equipo.objects.count()
    tickets_abiertos  = 0
    consumibles_bajos = Consumible.objects.filter(stock_actual__lte=5).count()

    tickets_recientes = []
    try:
        import requests as req
        response = req.get('https://jesusaav4.pythonanywhere.com/api/tickets', timeout=5)
        data = response.json()
        todos_tickets     = data.get('tickets', [])
        tickets_abiertos  = sum(1 for t in todos_tickets if t['estado'] == 'Abierto')
        tickets_recientes = todos_tickets[:5]
    except Exception:
        todos_tickets = []

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
        proxima_fecha_mantenimiento__gte=timezone.now().date()
    ).order_by('proxima_fecha_mantenimiento')[:5]

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
    return render(request, 'ti/dashboard.html', context)


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
        empleados = empleados.filter(departamento__icontains=departamento)

    departamentos = Empleado.objects.values_list('departamento', flat=True).distinct()

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
        Empleado.objects.create(
            nombre=request.POST['nombre'],
            apellido=request.POST['apellido'],
            departamento=request.POST['departamento'],
        )
        messages.success(request, 'Empleado creado correctamente.')
        return redirect('empleados_lista')
    return render(request, 'ti/empleados/crear.html')


@never_cache
@login_required
def empleado_editar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        empleado.nombre             = request.POST['nombre']
        empleado.apellido           = request.POST['apellido']
        empleado.departamento       = request.POST['departamento']
        empleado.save()
        messages.success(request, 'Empleado actualizado correctamente.')
        return redirect('empleados_lista')
    return render(request, 'ti/empleados/editar.html', {'empleado': empleado})


@never_cache
@login_required
def empleado_eliminar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        empleado.delete()
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
        Equipo.objects.create(
            tipo=request.POST['tipo'],
            marca=request.POST['marca'],
            modelo=request.POST['modelo'],
            numero_serie=request.POST['numero_serie'],
            sistema_operativo=request.POST.get('sistema_operativo', ''),
            estatus=request.POST['estatus'],

        )
        messages.success(request, 'Equipo creado correctamente.')
        return redirect('equipos_lista')
    return render(request, 'ti/equipos/crear.html', {'empleados': empleados})


@never_cache
@login_required
def equipo_editar(request, pk):
    equipo    = get_object_or_404(Equipo, pk=pk)
    empleados = Empleado.objects.all()
    if request.method == 'POST':
        equipo.tipo              = request.POST['tipo']
        equipo.marca             = request.POST['marca']
        equipo.modelo            = request.POST['modelo']
        equipo.numero_serie      = request.POST['numero_serie']
        equipo.sistema_operativo = request.POST.get('sistema_operativo', '')
        equipo.estatus           = request.POST['estatus']
        equipo.save()
        messages.success(request, 'Equipo actualizado correctamente.')
        return redirect('equipos_lista')
    return render(request, 'ti/equipos/editar.html', {'equipo': equipo, 'empleados': empleados})


@never_cache
@login_required
def equipo_eliminar(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    if request.method == 'POST':
        equipo.delete()
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
    if request.method == 'POST':
        Asignacion.objects.create(
            equipo_id=request.POST['equipo'],
            empleado_id=request.POST['empleado'],
            fecha_devolucion=request.POST.get('fecha_devolucion') or None,
            estatus=request.POST['estatus'],
            entregado_por=request.POST.get('entregado_por', ''),
        )
        messages.success(request, 'Asignación creada correctamente.')
        return redirect('asignaciones_lista')
    return render(request, 'ti/asignaciones/crear.html', {'equipos': equipos, 'empleados': empleados})


@never_cache
@login_required
def asignacion_editar(request, pk):
    asignacion = get_object_or_404(Asignacion, pk=pk)
    equipos    = Equipo.objects.filter(estatus='Activo')
    empleados  = Empleado.objects.all()
    if request.method == 'POST':
        asignacion.equipo_id        = request.POST['equipo']
        asignacion.empleado_id      = request.POST['empleado']
        asignacion.fecha_devolucion = request.POST.get('fecha_devolucion') or None
        asignacion.entregado_por    = request.POST.get('entregado_por', '')
        asignacion.save()
        messages.success(request, 'Asignación actualizada correctamente.')
        return redirect('asignaciones_lista')
    return render(request, 'ti/asignaciones/editar.html', {
        'asignacion': asignacion,
        'equipos':    equipos,
        'empleados':  empleados,
    })


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
        Mantenimiento.objects.create(
            equipo_id=request.POST['equipo'],
            tipo=request.POST['tipo'],
            descripcion=request.POST.get('descripcion', ''),
            ultima_fecha_mantenimiento=request.POST.get('ultima_fecha_mantenimiento') or None,
            proxima_fecha_mantenimiento=request.POST.get('proxima_fecha_mantenimiento') or None,
            realizado_por=request.POST.get('realizado_por', ''),
        )
        messages.success(request, 'Mantenimiento registrado correctamente.')
        return redirect('mantenimientos_lista')
    return render(request, 'ti/mantenimientos/crear.html', {'equipos': equipos})


@never_cache
@login_required
def mantenimiento_editar(request, pk):
    mantenimiento = get_object_or_404(Mantenimiento, pk=pk)
    equipos       = Equipo.objects.all()
    if request.method == 'POST':
        mantenimiento.equipo_id                   = request.POST['equipo']
        mantenimiento.tipo                        = request.POST['tipo']
        mantenimiento.descripcion                 = request.POST.get('descripcion', '')
        mantenimiento.ultima_fecha_mantenimiento  = request.POST.get('ultima_fecha_mantenimiento') or None
        mantenimiento.proxima_fecha_mantenimiento = request.POST.get('proxima_fecha_mantenimiento') or None
        mantenimiento.realizado_por               = request.POST.get('realizado_por', '')
        mantenimiento.save()
        messages.success(request, 'Mantenimiento actualizado correctamente.')
        return redirect('mantenimientos_lista')
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
        Correos.objects.create(
            tipo=request.POST.get('tipo', 'Correo'),
            empleado_id=request.POST.get('empleado') or None,
            correo_asignado=request.POST['correo_asignado'],
            estatus=request.POST['estatus'],
            observaciones=request.POST.get('observaciones', ''),
        )
        messages.success(request, 'Registro creado correctamente.')
        return redirect('correos_lista')
    return render(request, 'ti/correos/crear.html', {'empleados': empleados})


@never_cache
@login_required
def correo_editar(request, pk):
    correo    = get_object_or_404(Correos, pk=pk)
    empleados = Empleado.objects.all()
    if request.method == 'POST':
        correo.tipo            = request.POST.get('tipo', 'Correo')
        correo.empleado_id     = request.POST.get('empleado') or None
        correo.correo_asignado = request.POST['correo_asignado']
        correo.estatus         = request.POST['estatus']
        correo.observaciones   = request.POST.get('observaciones', '')
        correo.save()
        messages.success(request, 'Registro actualizado correctamente.')
        return redirect('correos_lista')
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
   

    consumibles = Consumible.objects.all()

    if busqueda:
        consumibles = consumibles.filter(
            models.Q(nombre__icontains=busqueda) |
            models.Q(descripcion__icontains=busqueda)
        )
    if categoria:
        consumibles = consumibles.filter(categoria=categoria)
        consumibles = [c for c in consumibles if c.stock_bajo]

    return render(request, 'ti/consumibles/lista.html', {
        'consumibles':      consumibles,
        'busqueda':         busqueda,
        'categoria_actual': categoria,
    })


@never_cache
@login_required
def consumible_crear(request):
    if request.method == 'POST':
        Consumible.objects.create(
            nombre=request.POST['nombre'],
            categoria=request.POST['categoria'],
            descripcion=request.POST.get('descripcion', ''),
            stock_actual=request.POST['stock_actual'],
            unidad_medida=request.POST.get('unidad_medida', ''),
        )
        messages.success(request, 'Consumible registrado correctamente.')
        return redirect('consumibles_lista')
    return render(request, 'ti/consumibles/crear.html')


@never_cache
@login_required
def consumible_editar(request, pk):
    consumible = get_object_or_404(Consumible, pk=pk)
    if request.method == 'POST':
        consumible.nombre         = request.POST['nombre']
        consumible.categoria      = request.POST['categoria']
        consumible.descripcion    = request.POST.get('descripcion', '')
        consumible.stock_actual   = request.POST['stock_actual']
        consumible.unidad_medida  = request.POST.get('unidad_medida', '')
        consumible.save()
        messages.success(request, 'Consumible actualizado correctamente.')
        return redirect('consumibles_lista')
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