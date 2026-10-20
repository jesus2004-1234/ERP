import os

from django.conf import settings


def validar_archivo_subido(archivo):
    """
    Valida extensión y tamaño de un archivo subido.
    Devuelve (True, "") si es válido o (False, "mensaje") si no.
    """
    extension = os.path.splitext(archivo.name)[1].lower()
    permitidas = getattr(settings, "EXTENSIONES_PERMITIDAS", set())
    if permitidas and extension not in permitidas:
        return False, (
            f"Tipo de archivo no permitido ({extension or 'sin extensión'}). "
            f"Permitidos: {', '.join(sorted(permitidas))}."
        )

    max_mb = getattr(settings, "MAX_UPLOAD_MB", 30)
    if archivo.size > max_mb * 1024 * 1024:
        return False, f"El archivo excede el tamaño máximo de {max_mb} MB."

    return True, ""
