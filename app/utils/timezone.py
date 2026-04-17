"""
TIMEZONE.PY - Utilidades para manejo de zona horaria Colombia
=============================================================
"""

from datetime import datetime, timedelta, timezone


def obtener_hora_colombia():
    """
    Retorna datetime en zona horaria de Colombia (UTC-5)
    Usado para GUARDAR timestamps con timezone correcto
    """
    tz_colombia = timezone(timedelta(hours=-5))
    return datetime.now(tz_colombia)


def obtener_hora_colombia_naive():
    """
    Retorna datetime en hora de Colombia pero SIN timezone (naive)
    Usado para COMPARACIONES con timestamps viejos que no tienen timezone
    """
    tz_colombia = timezone(timedelta(hours=-5))
    return datetime.now(tz_colombia).replace(tzinfo=None)


def formatear_fecha_colombia(fecha_iso):
    """
    Convierte ISO string a formato legible en Colombia con AM/PM
    Ejemplo: "2025-11-27 5:30 PM"
    Usado en templates via filtro Jinja
    """
    try:
        # Parsear fecha ISO
        if isinstance(fecha_iso, str):
            # Intentar con timezone
            if "+" in fecha_iso or "Z" in fecha_iso:
                fecha = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
            else:
                # Timestamp viejo sin timezone
                fecha = datetime.fromisoformat(fecha_iso)
                # Asumir que es hora Colombia
                tz_colombia = timezone(timedelta(hours=-5))
                fecha = fecha.replace(tzinfo=tz_colombia)
        else:
            fecha = fecha_iso

        # Convertir a zona horaria Colombia si tiene timezone
        if fecha.tzinfo is not None:
            tz_colombia = timezone(timedelta(hours=-5))
            fecha = fecha.astimezone(tz_colombia)

        # Formatear: "2025-11-27 5:30 PM"
        return fecha.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        # Si falla, retornar string original
        return str(fecha_iso)


def parsear_timestamp_naive(timestamp_str):
    """
    Parsea timestamp ISO string y retorna datetime naive en hora Colombia
    Maneja timestamps con y sin timezone de forma segura
    Usado para comparaciones (cálculo de horas de espera)
    """
    try:
        # Parsear timestamp
        if isinstance(timestamp_str, str):
            if "+" in timestamp_str or "Z" in timestamp_str:
                # Tiene timezone
                fecha = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                # No tiene timezone (timestamp viejo)
                fecha = datetime.fromisoformat(timestamp_str)
        else:
            fecha = timestamp_str

        # Si tiene timezone, convertir a Colombia y quitar tzinfo
        if fecha.tzinfo is not None:
            tz_colombia = timezone(timedelta(hours=-5))
            fecha = fecha.astimezone(tz_colombia).replace(tzinfo=None)

        return fecha
    except Exception:
        # Si falla, retornar fecha actual
        return obtener_hora_colombia_naive()
