"""
FORMATTING.PY - Utilidades para formateo de datos
==================================================
"""

import re


def formatear_monto(valor):
    """
    Formatea un número como moneda colombiana
    Ejemplo: 1500000 -> "$1.500.000"
    """
    try:
        if valor is None:
            return "$0"
        numero = int(float(valor))
        # Formatear con separadores de miles (punto en Colombia)
        formateado = "{:,}".format(numero).replace(",", ".")
        return f"${formateado}"
    except (ValueError, TypeError):
        return "$0"


def formatear_con_miles(numero):
    """
    Formatea un número con separadores de miles (punto)
    Ejemplo: 1500000 -> "1.500.000"
    """
    try:
        if numero is None:
            return "0"
        valor = int(float(numero))
        return "{:,}".format(valor).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def parse_currency_value(value_str):
    """
    Parsea un valor de moneda del frontend y retorna entero.
    Maneja formatos como:
    - "1.500.000" (formato colombiano)
    - "1,500,000" (formato estadounidense)
    - "1500000" (sin separadores)
    - "$1.500.000" (con símbolo)
    
    Args:
        value_str: String con el valor monetario
        
    Returns:
        int: Valor numérico o None si no se puede parsear
    """
    if value_str is None:
        return None
        
    if isinstance(value_str, (int, float)):
        return int(value_str)
    
    try:
        # Convertir a string si no lo es
        value_str = str(value_str).strip()
        
        # Quitar símbolo de moneda y espacios
        value_str = value_str.replace("$", "").replace(" ", "")
        
        if not value_str:
            return None
        
        # Detectar formato: si tiene . como separador de miles y , como decimal
        # o viceversa
        tiene_punto = "." in value_str
        tiene_coma = "," in value_str
        
        if tiene_punto and tiene_coma:
            # Determinar cuál es el decimal
            pos_punto = value_str.rfind(".")
            pos_coma = value_str.rfind(",")
            
            if pos_punto > pos_coma:
                # Formato: 1,500,000.00 (punto es decimal)
                value_str = value_str.replace(",", "")
            else:
                # Formato: 1.500.000,00 (coma es decimal)
                value_str = value_str.replace(".", "").replace(",", ".")
        elif tiene_punto:
            # Solo puntos - podría ser decimal o separador de miles
            # Si hay más de un punto, son separadores de miles
            if value_str.count(".") > 1:
                value_str = value_str.replace(".", "")
            # Si el punto está al final con 1-2 dígitos, es decimal
            elif re.match(r".*\.\d{1,2}$", value_str):
                pass  # Es decimal, dejarlo como está
            else:
                # Es separador de miles
                value_str = value_str.replace(".", "")
        elif tiene_coma:
            # Solo comas - podrían ser decimales o separadores de miles
            if value_str.count(",") > 1:
                value_str = value_str.replace(",", "")
            elif re.match(r".*,\d{1,2}$", value_str):
                # Es decimal
                value_str = value_str.replace(",", ".")
            else:
                value_str = value_str.replace(",", "")
        
        # Convertir a número
        return int(float(value_str))
        
    except (ValueError, TypeError):
        return None


def formatear_numero_resultado(valor, decimales=None):
    """
    Formatea un número para mostrar en resultados de scoring.
    - Si es entero o termina en .0, muestra sin decimales
    - Si tiene decimales significativos, usa coma como separador decimal
    - Aplica separador de miles (punto)
    
    Args:
        valor: Número a formatear
        decimales: Número de decimales forzado (None = auto)
        
    Returns:
        str: Número formateado
    """
    try:
        if valor is None:
            return "0"
        
        num = float(valor)
        
        # Determinar si es entero
        es_entero = num == int(num)
        
        if decimales is not None:
            # Forzar decimales específicos
            if decimales == 0:
                resultado = "{:,}".format(int(num)).replace(",", ".")
            else:
                resultado = "{:,.{dec}f}".format(num, dec=decimales).replace(",", "X").replace(".", ",").replace("X", ".")
        elif es_entero:
            # Mostrar como entero sin decimales
            resultado = "{:,}".format(int(num)).replace(",", ".")
        else:
            # Mostrar con decimales usando coma
            # Determinar decimales significativos (máximo 2)
            dec = 2 if abs(num - round(num, 1)) > 0.001 else 1
            resultado = "{:,.{d}f}".format(num, d=dec).replace(",", "X").replace(".", ",").replace("X", ".")
        
        return resultado
        
    except (ValueError, TypeError):
        return str(valor) if valor else "0"


def formatear_valor_criterio(valor, es_moneda=False, es_porcentaje=False):
    """
    Formatea un valor de criterio según su tipo.
    
    Args:
        valor: Valor a formatear
        es_moneda: Si es True, formatea como moneda
        es_porcentaje: Si es True, formatea como porcentaje con 1 decimal
        
    Returns:
        str: Valor formateado
    """
    try:
        if valor is None:
            return "-"
        
        # Intentar convertir a número
        num = float(valor)
        
        if es_moneda:
            return formatear_monto(num)
        elif es_porcentaje:
            # Formatear porcentaje con 1 decimal usando coma
            return "{:.1f}".format(num).replace(".", ",")
        else:
            return formatear_numero_resultado(num)
            
    except (ValueError, TypeError):
        # No es número, devolver como string
        return str(valor)
