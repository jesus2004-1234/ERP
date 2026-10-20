"""
Control de acceso por departamento.

Hoy todas las vistas solo exigen @login_required, lo que permite que cualquier
usuario autenticado (p. ej. de Capital Humano) entre a /finanzas/ o /ti/.
Este middleware cierra ese hueco en un solo lugar, sin tocar cada vista:
la tabla prefijo -> departamentos vive en settings.ACCESO_POR_DEPARTAMENTO.
"""
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def departamentos_permitidos(path):
    """Devuelve el conjunto de departamentos que pueden ver `path`, o None si es libre."""
    for prefijo, departamentos in getattr(settings, "ACCESO_POR_DEPARTAMENTO", {}).items():
        if path.startswith(prefijo):
            return departamentos
    return None


def usuario_puede_acceder(user, path):
    permitidos = departamentos_permitidos(path)
    if permitidos is None:
        return True
    if user.is_superuser:
        return True
    empleado = getattr(user, "empleado", None)
    return bool(empleado and empleado.departamento in permitidos)


class AccesoPorDepartamentoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Usuarios sin sesión: que decida @login_required (redirige al login).
        if not request.user.is_authenticated:
            return None

        if usuario_puede_acceder(request.user, request.path):
            return None

        messages.error(request, "No tienes permiso para acceder a esa sección.")
        # Evita bucles: si ni siquiera puede ver su dashboard, 403 directo.
        if request.path.rstrip("/") == "/dashboard":
            raise PermissionDenied
        return redirect("dashboard")
