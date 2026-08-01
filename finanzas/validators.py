import re


def validar_rfc(tipo_contribuyente, rfc, expediente_id=None):
    """
    Valida el RFC según el tipo de contribuyente.

    Retorna:
        (True, "") si es válido.
        (False, "mensaje") si es inválido.
    """

    from .models import Expediente

    if not rfc:
        return True, ""

    rfc = rfc.strip().upper()

    # Persona Física
    if tipo_contribuyente == "PF":
        if len(rfc) != 13:
            return False, "El RFC de una Persona Física debe tener 13 caracteres."

        patron_pf = r"^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$"

        if not re.match(patron_pf, rfc):
            return False, "El RFC de Persona Física no tiene un formato válido."

    # Persona Moral
    elif tipo_contribuyente == "PM":
        if len(rfc) != 12:
            return False, "El RFC de una Persona Moral debe tener 12 caracteres."

        patron_pm = r"^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$"

        if not re.match(patron_pm, rfc):
            return False, "El RFC de Persona Moral no tiene un formato válido."

    # Verifica que el RFC no esté ya registrado en otro expediente
    duplicado = Expediente.objects.filter(rfc=rfc)

    if expediente_id:
        duplicado = duplicado.exclude(pk=expediente_id)

    if duplicado.exists():
        return False, "Ya existe un expediente registrado con este RFC."

    return True, ""