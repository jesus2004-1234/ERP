import mimetypes
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect
from django.utils._os import safe_join

from .middleware import usuario_puede_acceder


@login_required
def dashboard(request):

    empleado = getattr(request.user, "empleado", None)

    if not empleado:
        messages.error(
            request,
            "Usuario sin empleado asociado."
        )
        return redirect("login")


    modulos = {
        "CIT": "ti_dashboard",
        "CPF": "finanzas_dashboard",
    }


    destino = modulos.get(
        empleado.departamento
    )


    if destino:
        return redirect(destino)


    messages.error(
        request,
        "Departamento sin módulo configurado."
    )

    return redirect("login")


# Qué departamentos pueden ver cada carpeta de /media/.
MEDIA_PERMISOS = {
    "finanzas/": "/finanzas/",
    "ti/": "/ti/",
    "documentos/ccc/": "CCC",
    "documentos/cpf/": "CPF",
    "documentos/cit/": "CIT",
    "documentos/chg/": "CHG",
    "documentos/gop/": "GOP",
    "documentos/gaf/": "GAF",
}


@login_required
def media_protegida(request, ruta):
    """
    Entrega los archivos de /media/ solo a usuarios con permiso sobre su módulo.
    Antes /media/ quedaba abierto a cualquiera que conociera la URL (INE, poderes
    notariales, constancias fiscales...).
    """
    try:
        ruta_abs = safe_join(settings.MEDIA_ROOT, ruta)
    except Exception:
        raise Http404

    if not os.path.isfile(ruta_abs):
        raise Http404

   
    
    for carpeta, permiso in MEDIA_PERMISOS.items():
        if not ruta.startswith(carpeta):
            continue

        if request.user.is_superuser:
            break

        if permiso.startswith("/"):
            permitido = usuario_puede_acceder(request.user, permiso)
        else:
            empleado = getattr(request.user, "empleado", None)
            permitido = bool(
                empleado and empleado.departamento == permiso
            )

        if not permitido:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        break
    
    tipo, _ = mimetypes.guess_type(ruta_abs)
    tipo = tipo or "application/octet-stream"

    if settings.USE_X_ACCEL_REDIRECT:
        respuesta = HttpResponse(content_type=tipo)
        respuesta["X-Accel-Redirect"] = "/protected_media/" + ruta.lstrip("/")
        return respuesta

    return FileResponse(open(ruta_abs, "rb"), content_type=tipo)
