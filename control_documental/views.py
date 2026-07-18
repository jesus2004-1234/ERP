from django.shortcuts import render
from .models import Documento

def lista(request):
    documentos = Documento.objects.all()
    return render(request, 'control_documental/lista.html', {'documentos': documentos})
# Create your views here.
