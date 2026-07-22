from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


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
        "GAF": "finanzas_dashboard",
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