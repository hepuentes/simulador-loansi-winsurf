"""
SEGURO_SERVICE.PY - Servicio de cálculo de seguros
===================================================
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta


class SeguroService:
    """
    Servicio para cálculos de seguros asociados a créditos.
    Centraliza la lógica de cálculo de seguros de vida y otros.
    """
    
    def __init__(self, config=None):
        """
        Inicializa el servicio de seguros.
        
        Args:
            config: Configuración de seguros (opcional)
        """
        self.config = config or {}
        self.tabla_seguros = self.config.get("SEGURO_VIDA", [])
    
    def cargar_config(self):
        """Carga la configuración de seguros desde la base de datos."""
        import sys
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent.parent.resolve()
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        
        from db_helpers import cargar_configuracion
        
        config = cargar_configuracion()
        seguros = config.get("SEGUROS", {})
        self.tabla_seguros = seguros.get("SEGURO_VIDA", [])
    
    def calcular_edad_desde_fecha(self, fecha_nacimiento_str, fecha_referencia=None):
        """
        Calcula la edad a partir de una fecha de nacimiento.
        
        Args:
            fecha_nacimiento_str: Fecha de nacimiento en formato string
            fecha_referencia: Fecha de referencia (default: hoy)
            
        Returns:
            int: Edad calculada o None si hay error
        """
        if not fecha_nacimiento_str:
            return None
        
        try:
            # Parsear fecha de nacimiento
            if isinstance(fecha_nacimiento_str, str):
                # Intentar varios formatos
                formatos = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
                fecha_nac = None
                
                for formato in formatos:
                    try:
                        fecha_nac = datetime.strptime(fecha_nacimiento_str, formato)
                        break
                    except ValueError:
                        continue
                
                if fecha_nac is None:
                    return None
            else:
                fecha_nac = fecha_nacimiento_str
            
            # Fecha de referencia
            if fecha_referencia is None:
                fecha_referencia = datetime.now()
            
            # Calcular edad
            edad = fecha_referencia.year - fecha_nac.year
            
            # Ajustar si aún no ha cumplido años
            if (fecha_referencia.month, fecha_referencia.day) < (fecha_nac.month, fecha_nac.day):
                edad -= 1
            
            return edad
            
        except Exception as e:
            print(f"Error calculando edad: {e}")
            return None
    
    def obtener_tasa_seguro_por_edad(self, edad):
        """
        Obtiene la tasa de seguro según la edad del cliente.
        
        Args:
            edad: Edad del cliente en años
            
        Returns:
            dict: {tasa_mensual, tasa_anual, rango} o None si no aplica
        """
        if not self.tabla_seguros:
            self.cargar_config()
        
        if not self.tabla_seguros:
            return None
        
        for rango in self.tabla_seguros:
            edad_min = rango.get("edad_min", 0)
            edad_max = rango.get("edad_max", 120)
            
            if edad_min <= edad <= edad_max:
                return {
                    "tasa_mensual": rango.get("tasa_mensual", 0),
                    "tasa_anual": rango.get("tasa_anual", 0),
                    "rango": f"{edad_min}-{edad_max} años"
                }
        
        return None
    
    def calcular_seguro_anual(self, edad, monto_solicitado, plazo_meses):
        """
        Calcula el seguro de vida anual prorrateado.
        
        Fórmula: Seguro = (Monto / 1,000,000) * Tasa_Anual_Edad * (Plazo / 12)
        
        Args:
            edad: Edad del cliente
            monto_solicitado: Monto del crédito
            plazo_meses: Plazo del crédito en meses
            
        Returns:
            dict: {seguro, tasa, detalle} o None si no aplica
        """
        if not edad or not monto_solicitado or plazo_meses <= 0:
            return None
        
        tasa_info = self.obtener_tasa_seguro_por_edad(edad)
        
        if not tasa_info:
            return None
        
        tasa_anual = tasa_info["tasa_anual"]
        
        # Fórmula: (Monto / 1,000,000) * Tasa_Anual * (Plazo / 12)
        seguro = (monto_solicitado / 1_000_000) * tasa_anual * (plazo_meses / 12)
        
        return {
            "seguro": int(round(seguro, 0)),
            "tasa_anual": tasa_anual,
            "tasa_mensual": tasa_info["tasa_mensual"],
            "edad": edad,
            "rango": tasa_info["rango"],
            "formula": f"({monto_solicitado:,} / 1,000,000) × {tasa_anual} × ({plazo_meses} / 12)"
        }
    
    def calcular_seguro_proporcional_fecha(self, edad, monto_solicitado, 
                                            fecha_desembolso, fecha_fin):
        """
        Calcula el seguro proporcionalmente entre dos fechas.
        Útil para cuando el plazo no es un número exacto de meses.
        
        Args:
            edad: Edad del cliente
            monto_solicitado: Monto del crédito
            fecha_desembolso: Fecha de desembolso
            fecha_fin: Fecha de finalización del crédito
            
        Returns:
            dict: {seguro, dias, tasa, detalle}
        """
        if not edad or not monto_solicitado:
            return None
        
        tasa_info = self.obtener_tasa_seguro_por_edad(edad)
        
        if not tasa_info:
            return None
        
        # Parsear fechas
        try:
            if isinstance(fecha_desembolso, str):
                fecha_desembolso = datetime.strptime(fecha_desembolso, "%Y-%m-%d")
            if isinstance(fecha_fin, str):
                fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
        except ValueError:
            return None
        
        # Calcular días
        dias = (fecha_fin - fecha_desembolso).days
        
        if dias <= 0:
            return None
        
        # Calcular seguro proporcional
        # Tasa anual prorrateada por días
        tasa_diaria = tasa_info["tasa_anual"] / 365
        seguro = (monto_solicitado / 1_000_000) * tasa_diaria * dias
        
        return {
            "seguro": int(round(seguro, 0)),
            "dias": dias,
            "tasa_anual": tasa_info["tasa_anual"],
            "tasa_diaria": round(tasa_diaria, 6),
            "edad": edad,
            "rango": tasa_info["rango"]
        }
    
    def validar_rangos_seguros(self, rangos):
        """
        Valida que los rangos de edad de seguros no se solapen.
        
        Args:
            rangos: Lista de rangos de seguro
            
        Returns:
            dict: {valido: bool, errores: list}
        """
        errores = []
        
        if not rangos:
            return {"valido": True, "errores": []}
        
        # Ordenar por edad mínima
        rangos_ordenados = sorted(rangos, key=lambda x: x.get("edad_min", 0))
        
        for i in range(len(rangos_ordenados) - 1):
            actual = rangos_ordenados[i]
            siguiente = rangos_ordenados[i + 1]
            
            edad_max_actual = actual.get("edad_max", 0)
            edad_min_siguiente = siguiente.get("edad_min", 0)
            
            # Verificar que no haya solapamiento
            if edad_max_actual >= edad_min_siguiente:
                errores.append(
                    f"Solapamiento entre rango {actual.get('edad_min')}-{edad_max_actual} "
                    f"y {edad_min_siguiente}-{siguiente.get('edad_max')}"
                )
            
            # Verificar que no haya huecos
            if edad_max_actual + 1 < edad_min_siguiente:
                errores.append(
                    f"Hueco de edades entre {edad_max_actual + 1} y {edad_min_siguiente - 1}"
                )
        
        return {
            "valido": len(errores) == 0,
            "errores": errores
        }
