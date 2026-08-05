from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Case, When

from .models import Expediente, ExpedienteDocumento, FacturaCliente
from .validators import validar_rfc


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
            models.Q(razon_social__icontains=busqueda) |
            models.Q(nombre_comercial__icontains=busqueda) |
            models.Q(rfc__icontains=busqueda)
        )


    if tipo:

        expedientes = expedientes.filter(
            tipo=tipo
        )


    if estatus:

        expedientes = expedientes.filter(
            estatus=estatus
        )



    return render(
        request,
        'finanzas/expedientes/lista.html',
        {
            'expedientes': expedientes,
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


        tipo_contribuyente = request.POST.get(
            'tipo_contribuyente'
        )


        rfc = (
            request.POST.get('rfc') or ""
        ).strip().upper()



        valido, mensaje = validar_rfc(
            tipo_contribuyente,
            rfc
        )




        if not valido:


            messages.error(
                request,
                mensaje
            )


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




        expediente = Expediente.objects.create(


            tipo=request.POST.get(
                'tipo'
            ),


            tipo_contribuyente=tipo_contribuyente,



            razon_social=request.POST.get(
                'razon_social',
                ''
            ),



            nombres=request.POST.get(
                'nombres',
                ''
            ),



            apellido_paterno=request.POST.get(
                'apellido_paterno',
                ''
            ),



            apellido_materno=request.POST.get(
                'apellido_materno',
                ''
            ),



            nombre_comercial=request.POST.get(
                'nombre_comercial',
                ''
            ),



            rfc=rfc or None,



            contacto_nombre=request.POST.get(
                'contacto_nombre',
                ''
            ),



            contacto_telefono=request.POST.get(
                'contacto_telefono',
                ''
            ),



            contacto_email=request.POST.get(
                'contacto_email',
                ''
            ),



            correo_pagos=request.POST.get(
                'correo_pagos',
                ''
            ) if request.POST.get('tipo') == Expediente.Tipo.PROVEEDOR else '',



            direccion=request.POST.get(
                'direccion',
                ''
            ),



            dias_credito=request.POST.get(
                'dias_credito'
            ) or 0,



            limite_credito=request.POST.get(
                'limite_credito'
            ) or None,



            estatus=request.POST.get(
                'estatus',
                Expediente.Estatus.ACTIVO
            ),



            observaciones=request.POST.get(
                'observaciones',
                ''
            ),

            regimen_fiscal=request.POST.get(
                'regimen_fiscal', 
                ''
            )

        )



        messages.success(
            request,
            'Expediente creado correctamente.'
        )



        return redirect(
            'expedientes_lista'
        )





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

    expediente = get_object_or_404(
        Expediente,
        pk=pk
    )


    if request.method == 'POST':


        tipo_contribuyente = request.POST.get(
            'tipo_contribuyente'
        )


        rfc = (
            request.POST.get('rfc') or ""
        ).strip().upper()



        valido, mensaje = validar_rfc(
            tipo_contribuyente,
            rfc,
            expediente_id=pk
        )



        if not valido:


            messages.error(
                request,
                mensaje
            )


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



        expediente.tipo = request.POST.get(
            'tipo'
        )


        expediente.tipo_contribuyente = tipo_contribuyente



        # Persona Física

        if tipo_contribuyente == Expediente.TipoContribuyente.FISICA:


            expediente.nombres = request.POST.get(
                'nombres',
                ''
            )


            expediente.apellido_paterno = request.POST.get(
                'apellido_paterno',
                ''
            )


            expediente.apellido_materno = request.POST.get(
                'apellido_materno',
                ''
            )




            expediente.razon_social = (
                expediente.nombres +
                " " +
                expediente.apellido_paterno +
                " " +
                expediente.apellido_materno
            ).strip()



        # Persona Moral

        else:


            expediente.razon_social = request.POST.get(
                'razon_social',
                ''
            )


            expediente.nombres = ''

            expediente.apellido_paterno = ''

            expediente.apellido_materno = ''




        expediente.nombre_comercial = request.POST.get(
            'nombre_comercial',
            ''
        )


        expediente.rfc = rfc or None

        expediente.regimen_fiscal = request.POST.get(
            'regimen_fiscal',
            ''
        )



        expediente.contacto_nombre = request.POST.get(
            'contacto_nombre',
            ''
        )


        expediente.contacto_telefono = request.POST.get(
            'contacto_telefono',
            ''
        )


        expediente.contacto_email = request.POST.get(
            'contacto_email',
            ''
        )


        expediente.correo_pagos = request.POST.get(
            'correo_pagos',
            ''
        ) if expediente.tipo == Expediente.Tipo.PROVEEDOR else ''


        expediente.direccion = request.POST.get(
            'direccion',
            ''
        )



        expediente.dias_credito = request.POST.get(
            'dias_credito'
        ) or 0



        expediente.limite_credito = request.POST.get(
            'limite_credito'
        ) or None



        expediente.estatus = request.POST.get(
            'estatus',
            Expediente.Estatus.ACTIVO
        )



        expediente.observaciones = request.POST.get(
            'observaciones',
            ''
        )



        expediente.save()



        messages.success(
            request,
            'Expediente actualizado correctamente.'
        )



        return redirect(
            'expedientes_lista'
        )





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
@require_POST
@login_required
def expediente_eliminar(request, pk):


    expediente = get_object_or_404(
        Expediente,
        pk=pk
    )



    if request.method == 'POST':

        expediente.archivo.delete(save=False)
        expediente.delete()



        messages.success(
            request,
            'Expediente eliminado correctamente.'
        )



        return redirect(
            'expedientes_lista'
        )



    return render(
        request,
        'finanzas/expedientes/eliminar.html',
        {
            'expediente': expediente
        }
    )

# =====================================================
# DETALLE DEL EXPEDIENTE
# =====================================================

@never_cache
@login_required
def expediente_detalle(request, pk):

    expediente = get_object_or_404(
        Expediente,
        pk=pk
    )

    categorias = ExpedienteDocumento.Categoria.choices

    # Orden según la posición de cada categoría dentro del TextChoices
    orden_categoria = Case(
        *[
            When(categoria=valor, then=pos)
            for pos, (valor, texto) in enumerate(categorias)
        ]
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


    expediente = get_object_or_404(
        Expediente,
        pk=pk
    )



    categoria = request.POST.get(
        'categoria'
    )


    archivo = request.FILES.get(
        'archivo'
    )



    if not categoria or not archivo:


        messages.error(
            request,
            'Debe seleccionar una categoría y un archivo.'
        )


        return redirect(
            'expediente_detalle',
            pk=pk
        )




    ExpedienteDocumento.objects.create(

        expediente=expediente,

        categoria=categoria,

        archivo=archivo

    )



    messages.success(
        request,
        'Documento agregado correctamente.'
    )



    return redirect(
        'expediente_detalle',
        pk=pk
    )





# =====================================================
# ELIMINAR DOCUMENTO
# =====================================================

@login_required
@require_POST
def expediente_documento_eliminar(request, pk):


    documento = get_object_or_404(
        ExpedienteDocumento,
        pk=pk
    )


    expediente_id = documento.expediente.pk


    # Elimina el archivo físico del storage antes de borrar el registro
    documento.archivo.delete(save=False)


    documento.delete()



    messages.success(
        request,
        'Documento eliminado correctamente.'
    )



    return redirect(
        'expediente_detalle',
        pk=expediente_id
    )


@login_required
@never_cache
def facturas_lista(request):

    busqueda = request.GET.get("q", "")
    estatus = request.GET.get("estatus", "")

    facturas = (
        FacturaCliente.objects
        .select_related("expediente")
        .all()
        .order_by("-fecha_factura")
    )

    if busqueda:
        facturas = facturas.filter(
            models.Q(factura__icontains=busqueda) |
            models.Q(expediente__razon_social__icontains=busqueda) |
            models.Q(expediente__nombres__icontains=busqueda) |
            models.Q(expediente__rfc__icontains=busqueda)
        )

    if estatus:
        facturas = facturas.filter(
            estatus=estatus
        )

    return render(
        request,
        "finanzas/cxc/lista.html",
        {
            "facturas": facturas,
            "busqueda": busqueda,
            "estatus_actual": estatus,
            "estatuses": FacturaCliente.Estatus.choices,
        },
    )