from django.shortcuts import render
from .models import Documento

def lista(request):
    documentos = Documento.objects.all()
    return render(request, 'control_documental/lista.html', {'documentos': documentos})
# Create your views here.

def documentos_cit(request):
    documentos = Documento.objects.filter(modulo=Documento.Modulo.CIT).order_by("nombre","categoria")
    return render(request, 'control_documental/lista.html', {'documentos': documentos, 'titulo': 'Documentos de Innovacion y Tecnología', 'modulo': Documento.Modulo.CIT})