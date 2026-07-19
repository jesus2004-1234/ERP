from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Documento


@login_required
def documentos_cit(request):

    # -------- SUBIR DOCUMENTO --------

    if request.method == "POST":

        categoria = request.POST.get("categoria")
        archivo = request.FILES.get("archivo")

        if archivo and categoria:

            Documento.objects.create(
                modulo=Documento.Modulo.CIT,
                categoria=categoria,
                archivo=archivo,
                nombre=archivo.name
            )

            messages.success(request, "Documento subido correctamente.")

        else:

            messages.error(request, "Debes seleccionar una categoría y un archivo.")

        return redirect("documentos_cit")


    # -------- FILTROS --------

    busqueda = request.GET.get("q", "")
    categoria = request.GET.get("categoria")
    estado = request.GET.get("estado")

    documentos = Documento.objects.filter(
        modulo=Documento.Modulo.CIT,
        activo=True
    )

    if categoria:

        documentos = documentos.filter(
            categoria=categoria
        )

    if estado:

        documentos = documentos.filter(
            estado=estado
        )

    if busqueda:

        documentos = documentos.filter(
            nombre__icontains=busqueda
        )

    documentos = documentos.order_by(
        "categoria",
        "nombre"
    )

    return render(
        request,
        "control_documental/lista.html",
        {
            "documentos": documentos,
            "categorias": Documento.Categoria.choices,
            "categoria_actual": categoria,
            "estado_actual": estado,
            "busqueda": busqueda,
            "titulo": "Documentos de Innovación y Tecnología"
        }
    )


@login_required
@require_POST
def ocultar_documento(request, pk):

    documento = get_object_or_404(
        Documento,
        pk=pk
    )

    documento.activo = False
    documento.save()

    messages.success(request, "Documento eliminado correctamente.")

    return redirect("documentos_cit")


@login_required
@require_POST
def cambiar_estado_documento(request, pk):

    documento = get_object_or_404(
        Documento,
        pk=pk
    )

    if documento.estado == Documento.Estado.VIGENTE:

        documento.estado = Documento.Estado.OBSOLETO
        documento.save()

        messages.success(request, "Documento marcado como obsoleto.")

    return redirect("documentos_cit")