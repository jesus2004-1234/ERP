from django.shortcuts import render, redirect
from .models import Documento
from django.shortcuts import get_object_or_404


def documentos_cit(request):

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


            return redirect("documentos_cit")


    documentos = Documento.objects.filter(
        modulo=Documento.Modulo.CIT,
        activo=True
    ).order_by(
        "categoria",
        "nombre"
    )


    return render(
        request,
        "control_documental/lista.html",
        {
            "documentos": documentos,
            "categorias": Documento.Categoria.choices,
            "titulo": "Documentos de Innovación y Tecnología"
        }
    )

def ocultar_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    documento.activo = False
    documento.save()
    return redirect("documentos_cit")

def cambiar_estado_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    if documento.estado == Documento.Estado.VIGENTE:
        documento.estado = Documento.Estado.OBSOLETO
    documento.save()
    return redirect("documentos_cit")