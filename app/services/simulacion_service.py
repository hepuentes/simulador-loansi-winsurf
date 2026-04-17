"""
SIMULACION_SERVICE.PY - Servicio de cálculos de simulación de crédito
======================================================================
"""

import math
from datetime import datetime
from dateutil.relativedelta import relativedelta


class SimulacionService:
    """
    Servicio para cálculos de simulación de crédito.
    Centraliza toda la lógica de cálculo financiero.
    """
    
    # Constantes
    SEMANAS_POR_MES = 52.0 / 12.0  # 4.333333...
    
    def __init__(self, config=None):
        """
        Inicializa el servicio de simulación.
        
        Args:
            config: Configuración de líneas de crédito (opcional)
        """
        self.config = config or {}
        self.lineas_credito = self.config.get("LINEAS_CREDITO", {})
        self.costos_asociados = self.config.get("COSTOS_ASOCIADOS", {})
    
    def cargar_config(self):
        """Carga la configuración desde la base de datos."""
        import sys
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent.parent.resolve()
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        
        from db_helpers import cargar_configuracion
        
        self.config = cargar_configuracion()
        self.lineas_credito = self.config.get("LINEAS_CREDITO", {})
        self.costos_asociados = self.config.get("COSTOS_ASOCIADOS", {})
    
    def calcular_cuota(self, monto_total, tasa_mensual, plazo_meses):
        """
        Calcula la cuota mensual usando fórmula de amortización francesa.
        
        Args:
            monto_total: Monto total a financiar
            tasa_mensual: Tasa de interés mensual (decimal, ej: 0.02 para 2%)
            plazo_meses: Plazo en meses
            
        Returns:
            float: Cuota mensual
        """
        if plazo_meses <= 0 or monto_total <= 0:
            return 0
        
        if tasa_mensual <= 0:
            # Sin interés, cuota simple
            return monto_total / plazo_meses
        
        # Fórmula de amortización francesa
        # Cuota = P * [i(1+i)^n] / [(1+i)^n - 1]
        i = tasa_mensual
        n = plazo_meses
        
        cuota = monto_total * (i * pow(1 + i, n)) / (pow(1 + i, n) - 1)
        
        return round(cuota, 0)
    
    def calcular_tasa_ea_a_mensual(self, tasa_ea):
        """
        Convierte tasa efectiva anual a tasa nominal mensual.
        
        Args:
            tasa_ea: Tasa efectiva anual (porcentaje, ej: 25 para 25%)
            
        Returns:
            float: Tasa mensual (porcentaje)
        """
        # Fórmula: i_mensual = (1 + i_ea)^(1/12) - 1
        tasa_mensual = (pow(1 + tasa_ea / 100, 1/12) - 1) * 100
        return round(tasa_mensual, 4)
    
    def calcular_tasa_mensual_a_ea(self, tasa_mensual):
        """
        Convierte tasa nominal mensual a tasa efectiva anual.
        
        Args:
            tasa_mensual: Tasa mensual (porcentaje, ej: 2 para 2%)
            
        Returns:
            float: Tasa efectiva anual (porcentaje)
        """
        # Fórmula: i_ea = (1 + i_mensual)^12 - 1
        tasa_ea = (pow(1 + tasa_mensual / 100, 12) - 1) * 100
        return round(tasa_ea, 2)
    
    def obtener_costos_linea(self, linea_credito):
        """
        Obtiene los costos asociados a una línea de crédito.
        
        Args:
            linea_credito: Nombre de la línea
            
        Returns:
            dict: Costos asociados
        """
        return self.costos_asociados.get(linea_credito, {})
    
    def calcular_aval(self, monto, porcentaje_aval):
        """
        Calcula el valor del aval.
        
        Args:
            monto: Monto base
            porcentaje_aval: Porcentaje de aval (decimal, ej: 0.10 para 10%)
            
        Returns:
            int: Valor del aval
        """
        return int(round(monto * porcentaje_aval, 0))
    
    def calcular_seguro(self, monto, tasa_seguro, plazo_meses):
        """
        Calcula el valor del seguro.
        
        Args:
            monto: Monto base
            tasa_seguro: Tasa del seguro por mes
            plazo_meses: Plazo en meses
            
        Returns:
            int: Valor del seguro
        """
        # Calcular seguro mensual y multiplicar por plazo
        seguro_total = monto * tasa_seguro * plazo_meses
        return int(round(seguro_total, 0))
    
    def calcular_plataforma(self, monto, tasa_plataforma):
        """
        Calcula el costo de plataforma.
        
        Args:
            monto: Monto base
            tasa_plataforma: Porcentaje de plataforma
            
        Returns:
            int: Costo de plataforma
        """
        return int(round(monto * tasa_plataforma, 0))
    
    def simular_credito(self, monto, plazo, linea_credito, nivel_riesgo=None, 
                        modalidad_desembolso="completo"):
        """
        Realiza una simulación completa de crédito.
        
        Args:
            monto: Monto solicitado
            plazo: Plazo (en la unidad de la línea: meses, semanas, etc.)
            linea_credito: Nombre de la línea de crédito
            nivel_riesgo: Nivel de riesgo del cliente (opcional)
            modalidad_desembolso: 'completo' o 'neto'
            
        Returns:
            dict: Resultado de la simulación
        """
        # Cargar configuración si es necesario
        if not self.lineas_credito:
            self.cargar_config()
        
        # Obtener configuración de la línea
        linea_config = self.lineas_credito.get(linea_credito, {})
        
        if not linea_config:
            return {"error": f"Línea de crédito '{linea_credito}' no encontrada"}
        
        # Validar monto
        monto_min = linea_config.get("monto_min", 0)
        monto_max = linea_config.get("monto_max", float("inf"))
        
        if monto < monto_min or monto > monto_max:
            return {
                "error": f"Monto fuera de rango. Mínimo: {monto_min:,}, Máximo: {monto_max:,}"
            }
        
        # Validar plazo
        plazo_min = linea_config.get("plazo_min", 1)
        plazo_max = linea_config.get("plazo_max", 36)
        plazo_tipo = linea_config.get("plazo_tipo", "meses")
        
        if plazo < plazo_min or plazo > plazo_max:
            return {
                "error": f"Plazo fuera de rango. Mínimo: {plazo_min}, Máximo: {plazo_max} {plazo_tipo}"
            }
        
        # Convertir plazo a meses si es necesario
        if plazo_tipo == "semanas":
            plazo_meses = plazo / self.SEMANAS_POR_MES
        elif plazo_tipo == "dias":
            plazo_meses = plazo / 30
        else:
            plazo_meses = plazo
        
        # Obtener tasas
        tasa_mensual = linea_config.get("tasa_mensual", 2.0) / 100  # Convertir a decimal
        tasa_ea = linea_config.get("tasa_anual", 25.0)
        
        # Obtener porcentaje de aval
        aval_porcentaje = linea_config.get("aval_porcentaje", 0.10)
        
        # Calcular costos
        costos = self.obtener_costos_linea(linea_credito)
        
        # Calcular aval
        aval = self.calcular_aval(monto, aval_porcentaje)
        
        # Calcular seguro (si aplica)
        tasa_seguro = costos.get("seguro", 0) / 100 if costos.get("seguro") else 0
        seguro = self.calcular_seguro(monto, tasa_seguro, int(plazo_meses))
        
        # Calcular plataforma (si aplica)
        tasa_plataforma = costos.get("plataforma", 0) / 100 if costos.get("plataforma") else 0
        plataforma = self.calcular_plataforma(monto, tasa_plataforma)
        
        # Calcular total a financiar según modalidad
        if modalidad_desembolso == "neto":
            # Desembolso neto: costos se descuentan del monto
            total_financiar = monto
            monto_desembolso = monto - aval - seguro - plataforma
        else:
            # Desembolso completo: costos se suman al monto
            total_financiar = monto + aval + seguro + plataforma
            monto_desembolso = monto
        
        # Calcular cuota
        cuota = self.calcular_cuota(total_financiar, tasa_mensual, int(plazo_meses))
        
        # Convertir cuota a frecuencia de pago si es semanal
        if plazo_tipo == "semanas":
            cuota_pago = cuota / self.SEMANAS_POR_MES
        else:
            cuota_pago = cuota
        
        # Calcular totales
        total_intereses = (cuota * plazo_meses) - total_financiar
        total_a_pagar = cuota * plazo_meses
        
        return {
            "monto_solicitado": monto,
            "monto_desembolso": monto_desembolso,
            "plazo": plazo,
            "plazo_tipo": plazo_tipo,
            "plazo_meses": round(plazo_meses, 2),
            "linea_credito": linea_credito,
            "nivel_riesgo": nivel_riesgo,
            "modalidad_desembolso": modalidad_desembolso,
            "tasa_mensual": round(tasa_mensual * 100, 4),
            "tasa_ea": tasa_ea,
            "aval": aval,
            "aval_porcentaje": aval_porcentaje * 100,
            "seguro": seguro,
            "plataforma": plataforma,
            "total_financiar": total_financiar,
            "cuota_mensual": int(cuota),
            "cuota_pago": int(cuota_pago),
            "total_intereses": int(total_intereses),
            "total_a_pagar": int(total_a_pagar),
            "costos_detalle": {
                "aval": aval,
                "seguro": seguro,
                "plataforma": plataforma
            }
        }
    
    def generar_tabla_amortizacion(self, monto, tasa_mensual, plazo_meses, fecha_inicio=None):
        """
        Genera la tabla de amortización completa.
        
        Args:
            monto: Monto a financiar
            tasa_mensual: Tasa mensual (decimal)
            plazo_meses: Plazo en meses
            fecha_inicio: Fecha de inicio del crédito (opcional)
            
        Returns:
            list: Tabla de amortización
        """
        if fecha_inicio is None:
            fecha_inicio = datetime.now()
        
        cuota = self.calcular_cuota(monto, tasa_mensual, plazo_meses)
        saldo = monto
        tabla = []
        
        for i in range(1, plazo_meses + 1):
            interes = saldo * tasa_mensual
            capital = cuota - interes
            saldo -= capital
            
            # Ajustar última cuota por redondeo
            if i == plazo_meses:
                capital += saldo
                saldo = 0
            
            fecha_pago = fecha_inicio + relativedelta(months=i)
            
            tabla.append({
                "numero_cuota": i,
                "fecha_pago": fecha_pago.strftime("%Y-%m-%d"),
                "cuota": round(cuota, 0),
                "capital": round(capital, 0),
                "interes": round(interes, 0),
                "saldo": round(max(0, saldo), 0)
            })
        
        return tabla
