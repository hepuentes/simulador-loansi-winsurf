"""
SCORING_SERVICE.PY - Servicio de cálculo de scoring de crédito
===============================================================

ARQUITECTURA DE 4 CAPAS CON ESCALA UNIFICADA 0-100
==================================================
Capa 1: Filtro de Rechazo - Evalúa factores de rechazo (Binario)
Capa 2: Evaluación de Scoring - Calcula puntaje 0-100
Capa 3: Decisión de Aprobación - Aprobación Auto/Comité/Rechazo
Capa 4: Asignación de Pricing - Nivel de Riesgo, Tasa E.A. y Aval

REFACTORIZADO: 2026-02-02 - Migración de escala 0-45 a escala 0-100
"""

import json
from datetime import datetime


class ScoringService:
    """
    Servicio para cálculos de scoring de crédito.
    Centraliza toda la lógica de evaluación de riesgo crediticio.
    
    ESCALA UNIFICADA: 0-100
    """
    
    def __init__(self, scoring_config=None):
        """
        Inicializa el servicio de scoring.
        
        Args:
            scoring_config: Configuración de scoring (opcional)
        """
        self.config = scoring_config or {}
        self.criterios = self.config.get("criterios", {})
        self.niveles_riesgo = self.config.get("niveles_riesgo", [])
        self.factores_rechazo = self.config.get("factores_rechazo_automatico", [])
        # Umbrales en escala 0-100
        self.puntaje_minimo_aprobacion = self.config.get("puntaje_minimo_aprobacion", 38)
        self.puntaje_minimo_comite = self.config.get("puntaje_minimo_comite", 22)
        # Escala fija 0-100 (ya no usamos escala_max variable)
        self.ESCALA_MAX = 100
    
    def cargar_config(self, linea_credito=None):
        """
        Carga la configuración de scoring desde la base de datos.
        
        Args:
            linea_credito: Nombre de la línea de crédito (opcional)
        """
        import sys
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent.parent.resolve()
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        
        from db_helpers import cargar_scoring
        from db_helpers_scoring_linea import cargar_scoring_por_linea
        
        if linea_credito:
            # Intentar cargar configuración específica de la línea
            config_linea = cargar_scoring_por_linea(linea_credito)
            if config_linea:
                self.config = config_linea
            else:
                self.config = cargar_scoring()
        else:
            self.config = cargar_scoring()
        
        # Actualizar referencias
        self.criterios = self.config.get("criterios", {})
        self.niveles_riesgo = self.config.get("niveles_riesgo", [])
        self.factores_rechazo = self.config.get("factores_rechazo_automatico", [])
        # Umbrales en escala 0-100
        self.puntaje_minimo_aprobacion = self.config.get("puntaje_minimo_aprobacion", 38)
        self.puntaje_minimo_comite = self.config.get("puntaje_minimo_comite", 22)
    
    def evaluar_criterio(self, codigo, valor, criterio_config):
        """
        Evalúa un criterio individual.
        
        Args:
            codigo: Código del criterio
            valor: Valor a evaluar
            criterio_config: Configuración del criterio
            
        Returns:
            dict: {puntaje, detalle, ...}
        """
        if not criterio_config.get("activo", True):
            return {"puntaje": 0, "evaluado": False}
        
        peso = criterio_config.get("peso", 5)
        rangos = criterio_config.get("rangos", [])
        tipo_campo = criterio_config.get("tipo_campo", "numerico")
        
        puntaje = 0
        detalle = ""
        
        # Convertir valor según tipo
        # NOTA: tipo_campo puede ser "numerico", "number", "select", "seleccion", "boolean", "percentage", etc.
        if tipo_campo in ["numerico", "number", "currency", "percentage"]:
            try:
                # Limpiar valor de formato monetario
                # IMPORTANTE: No quitar el punto decimal, solo separadores de miles
                valor_str = str(valor).replace("$", "").replace(" ", "").strip()
                # Si tiene coma como decimal (formato europeo), convertir a punto
                # Si tiene puntos como separador de miles (ej: 1.000.000), quitarlos
                if "," in valor_str and "." in valor_str:
                    # Formato mixto: 1.000.000,50 → quitar puntos, coma a punto
                    valor_str = valor_str.replace(".", "").replace(",", ".")
                elif "," in valor_str:
                    # Solo coma: puede ser decimal (1,5) o miles (1,000)
                    # Si hay una sola coma y menos de 3 dígitos después, es decimal
                    partes = valor_str.split(",")
                    if len(partes) == 2 and len(partes[1]) <= 2:
                        valor_str = valor_str.replace(",", ".")  # Decimal
                    else:
                        valor_str = valor_str.replace(",", "")  # Miles
                # Si solo tiene puntos, verificar si es decimal o miles
                # (el punto decimal ya viene correcto de Python)
                valor_num = float(valor_str) if valor_str else 0
            except (ValueError, TypeError):
                valor_num = 0
            
            # Buscar rango que aplica
            for rango in rangos:
                min_val = rango.get("min", float("-inf"))
                max_val = rango.get("max", float("inf"))
                
                if min_val <= valor_num <= max_val:
                    # Los rangos usan "puntos" o "puntaje"
                    puntaje = rango.get("puntos") or rango.get("puntaje", 0)
                    detalle = rango.get("etiqueta") or rango.get("descripcion", "")
                    break
        
        elif tipo_campo in ["seleccion", "select", "composite", "hidden"]:
            # Para selects y hidden, el valor enviado ES el puntaje directamente
            # porque el <option value="X"> tiene X = puntos
            # Hidden: criterios solo para factores de rechazo, no visibles en formulario
            try:
                puntaje = float(str(valor).strip()) if valor else 0
                # Buscar etiqueta correspondiente
                for rango in rangos:
                    rango_puntos = rango.get("puntos") or rango.get("puntaje", 0)
                    if float(rango_puntos) == puntaje:
                        detalle = rango.get("etiqueta") or rango.get("descripcion", "")
                        break
            except (ValueError, TypeError):
                puntaje = 0
        
        elif tipo_campo in ["booleano", "boolean"]:
            valor_bool = str(valor).lower() in ["true", "1", "si", "sí", "yes"]
            for rango in rangos:
                if rango.get("valor") == valor_bool:
                    puntaje = rango.get("puntos") or rango.get("puntaje", 0)
                    detalle = rango.get("etiqueta") or rango.get("descripcion", "")
                    break
        
        # Aplicar peso
        puntaje_ponderado = puntaje * (peso / 100.0)
        
        return {
            "puntaje": puntaje,
            "puntaje_ponderado": puntaje_ponderado,
            "peso": peso,
            "detalle": detalle,
            "evaluado": True,
            "valor_original": valor
        }
    
    def verificar_rechazo_automatico(self, valores):
        """
        Verifica si hay factores de rechazo automático.
        Soporta tipo 'numerico' (operador+valor) y 'seleccion' (opciones).
        
        Args:
            valores: Dict con valores de los criterios
            
        Returns:
            dict: {rechazo: bool, razon: str, factor: str}
        """
        for factor in self.factores_rechazo:
            tipo_factor = factor.get("tipo_factor", "numerico")
            criterio = factor.get("criterio")
            
            # ---- Factores tipo SELECCIÓN ----
            if tipo_factor == "seleccion":
                if criterio not in valores:
                    continue
                
                # FIX: Si el criterio origen es numérico, evaluar primero para
                # obtener el puntaje. Las opciones del factor usan puntajes como
                # valor, no el monto crudo que digitó el asesor.
                criterio_config = self.criterios.get(criterio, {})
                
                # Si no hay config en self.criterios (criterio externo como edad),
                # usar el valor directo como string sin intentar evaluar_criterio()
                if not criterio_config:
                    valor_seleccionado = str(valores[criterio]).strip()
                else:
                    tipo_criterio = criterio_config.get("tipo_campo", "numerico")
                    
                    if tipo_criterio in ("numerico", "number", "currency", "percentage"):
                        resultado_eval = self.evaluar_criterio(criterio, valores[criterio], criterio_config)
                        valor_seleccionado = str(resultado_eval.get("puntaje", 0))
                    else:
                        valor_seleccionado = str(valores[criterio]).strip()
                
                opciones = factor.get("opciones", [])
                
                for opcion in opciones:
                    if str(opcion.get("valor", "")) == valor_seleccionado and opcion.get("rechaza", False):
                        mensaje_rechazo = opcion.get("mensaje", factor.get("mensaje", "Rechazo por selección"))
                        etiqueta = opcion.get("etiqueta", valor_seleccionado)
                        return {
                            "rechazo": True,
                            "razon": mensaje_rechazo,
                            "factor": criterio,
                            "valor": etiqueta,
                            "umbral": None
                        }
                continue
            
            # ---- Factores tipo NUMÉRICO (comportamiento original) ----
            operador = factor.get("operador", "<")
            umbral = factor.get("valor", 0)
            mensaje = factor.get("mensaje", "Rechazo automático")
            
            if criterio not in valores:
                continue
            
            valor = valores[criterio]
            
            # Convertir a número si es posible
            try:
                valor_num = float(str(valor).replace(",", "."))
                umbral_num = float(umbral)
            except (ValueError, TypeError):
                continue
            
            # Evaluar condición
            rechazado = False
            if operador == "<" and valor_num < umbral_num:
                rechazado = True
            elif operador == "<=" and valor_num <= umbral_num:
                rechazado = True
            elif operador == ">" and valor_num > umbral_num:
                rechazado = True
            elif operador == ">=" and valor_num >= umbral_num:
                rechazado = True
            elif operador == "==" and valor_num == umbral_num:
                rechazado = True
            
            if rechazado:
                # Reemplazar placeholders en el mensaje
                mensaje_formateado = mensaje.replace("{valor}", str(umbral_num))
                mensaje_formateado = mensaje_formateado.replace("{criterio}", str(criterio))
                mensaje_formateado = mensaje_formateado.replace("{operador}", str(operador))
                return {
                    "rechazo": True,
                    "razon": mensaje_formateado,
                    "factor": criterio,
                    "valor": valor,
                    "umbral": umbral
                }
        
        return {"rechazo": False, "razon": None, "factor": None}
    
    def determinar_nivel_riesgo(self, score):
        """
        Determina el nivel de riesgo según el score.
        Aplica interpolación dinámica si está activa.
        
        Args:
            score: Score calculado (escala 0-100)
            
        Returns:
            dict: Info del nivel de riesgo con tasas interpoladas
        """
        print(f"\n   🎯 DEBUG determinar_nivel_riesgo:")
        print(f"      Score recibido: {score}")
        print(f"      Niveles disponibles: {len(self.niveles_riesgo)}")
        
        for i, nivel in enumerate(self.niveles_riesgo):
            min_score = nivel.get("min", 0)
            max_score = nivel.get("max", 100)
            nombre = nivel.get("nombre", "Sin nombre")
            
            print(f"      [{i}] {nombre}: {min_score} - {max_score} | Score {score} en rango: {min_score <= score <= max_score}")
            
            if min_score <= score <= max_score:
                print(f"      ✅ MATCH: {nombre}")
                
                # Verificar si interpolación está activa
                interpolacion_activa = nivel.get("interpolacion_activa", False)
                
                if interpolacion_activa:
                    # Calcular factor de posición (0.0 a 1.0)
                    if max_score > min_score:
                        factor = (score - min_score) / (max_score - min_score)
                    else:
                        factor = 0.5
                    
                    # Obtener valores en extremos
                    tasa_at_min = nivel.get("tasa_ea_at_min") or nivel.get("tasa_ea", 24.0)
                    tasa_at_max = nivel.get("tasa_ea_at_max") or nivel.get("tasa_ea", 24.0)
                    aval_at_min = nivel.get("aval_at_min") or nivel.get("aval_porcentaje", 0.10)
                    aval_at_max = nivel.get("aval_at_max") or nivel.get("aval_porcentaje", 0.10)
                    
                    # Interpolación lineal inversa (mayor score = menor tasa/aval)
                    tasa_ea = tasa_at_min - (tasa_at_min - tasa_at_max) * factor
                    aval = aval_at_min - (aval_at_min - aval_at_max) * factor
                    
                    # Calcular tasa nominal desde E.A. interpolada
                    tasa_nominal = (pow(1 + tasa_ea/100, 1/12) - 1) * 100
                    
                    print(f"      📊 INTERPOLACIÓN ACTIVA:")
                    print(f"         Factor posición: {factor:.4f} ({factor*100:.2f}%)")
                    print(f"         Tasa: {tasa_at_min}% → {tasa_ea:.4f}% → {tasa_at_max}%")
                    print(f"         Aval: {aval_at_min*100:.1f}% → {aval*100:.2f}% → {aval_at_max*100:.1f}%")
                    
                    return {
                        "nombre": nombre,
                        "color": nivel.get("color", "#808080"),
                        "tasa_ea": round(tasa_ea, 4),
                        "tasa_nominal_mensual": round(tasa_nominal, 4),
                        "aval_porcentaje": round(aval, 4),
                        "min": min_score,
                        "max": max_score,
                        "interpolacion_activa": True,
                        "factor_posicion": round(factor, 4),
                        "desglose_interpolacion": {
                            "tasa_at_min": tasa_at_min,
                            "tasa_at_max": tasa_at_max,
                            "aval_at_min": aval_at_min,
                            "aval_at_max": aval_at_max
                        }
                    }
                else:
                    # Sin interpolación: usar valores fijos
                    return {
                        "nombre": nombre,
                        "color": nivel.get("color", "#808080"),
                        "tasa_ea": nivel.get("tasa_ea"),
                        "tasa_nominal_mensual": nivel.get("tasa_nominal_mensual"),
                        "aval_porcentaje": nivel.get("aval_porcentaje"),
                        "min": min_score,
                        "max": max_score,
                        "interpolacion_activa": False
                    }
        
        print(f"      ❌ Sin match - usando default")
        return {
            "nombre": "Sin clasificar",
            "color": "#808080",
            "tasa_ea": None,
            "tasa_nominal_mensual": None,
            "aval_porcentaje": None,
            "interpolacion_activa": False
        }
    
    def _degradar_nivel(self, nivel_actual):
        """
        Degrada el nivel de riesgo en un escalón (hacia mayor riesgo).
        Los niveles están ordenados de mayor score (bajo riesgo) a menor score (alto riesgo).
        Degradar = pasar al siguiente nivel con rango de score inferior.
        
        Args:
            nivel_actual: Dict del nivel de riesgo actual
            
        Returns:
            dict: Nivel degradado o None si no se puede degradar
        """
        if not self.niveles_riesgo or len(self.niveles_riesgo) < 2:
            return None
        
        # Ordenar niveles por min score descendente (bajo riesgo primero)
        niveles_ordenados = sorted(self.niveles_riesgo, key=lambda n: n.get("min", 0), reverse=True)
        
        # Encontrar posición del nivel actual
        idx_actual = -1
        for i, n in enumerate(niveles_ordenados):
            if n.get("nombre") == nivel_actual.get("nombre"):
                idx_actual = i
                break
        
        if idx_actual == -1 or idx_actual >= len(niveles_ordenados) - 1:
            return None  # Ya es el peor nivel o no se encontró
        
        # Nivel degradado = siguiente en orden descendente de score
        nivel_peor = niveles_ordenados[idx_actual + 1]
        
        return {
            "nombre": nivel_peor.get("nombre"),
            "color": nivel_peor.get("color", "#808080"),
            "tasa_ea": nivel_peor.get("tasa_ea"),
            "tasa_nominal_mensual": nivel_peor.get("tasa_nominal_mensual"),
            "aval_porcentaje": nivel_peor.get("aval_porcentaje"),
            "min": nivel_peor.get("min", 0),
            "max": nivel_peor.get("max", 100),
            "interpolacion_activa": False,
            "degradado": True
        }
    
    def calcular_scoring(self, valores, linea_credito=None):
        """
        CAPA 2: EVALUACIÓN DE SCORING
        ==============================
        Calcula el scoring completo en ESCALA 0-100.
        
        Fórmula: score = (suma_puntos_ponderados / suma_maxima_posible) * 100
        
        Args:
            valores: Dict con valores de todos los criterios
            linea_credito: Línea de crédito (opcional)
            
        Returns:
            dict: Resultado completo del scoring
        """
        # Cargar configuración SOLO si no hay criterios cargados
        if not self.criterios:
            self.cargar_config(linea_credito)
        
        # =====================================================================
        # CAPA 1: FILTRO DE RECHAZO
        # =====================================================================
        rechazo = self.verificar_rechazo_automatico(valores)
        
        # =====================================================================
        # CAPA 2: EVALUACIÓN DE SCORING (Escala 0-100)
        # Separa criterios normales (ponderados) de penalizaciones (Sin Categoría)
        # =====================================================================
        evaluaciones = []
        penalizaciones_detalle = []
        suma_puntos_ponderados = 0
        suma_maxima_posible = 0
        peso_total_evaluado = 0
        suma_penalizaciones = 0
        
        print(f"\n🔍 SCORING [ESCALA 0-100]:")
        print(f"   Criterios disponibles: {len(self.criterios)}")
        
        for codigo, config in self.criterios.items():
            if not config.get("activo", True):
                print(f"   ⏭️ SKIP (inactivo): {codigo}")
                continue
            
            # Criterios en "Sin Categoría" son penalizaciones (restan del score)
            es_penalizacion = config.get("seccion") == "Sin Categoría"
            
            valor = valores.get(codigo)
            peso = config.get("peso", 5)
            rangos = config.get("rangos", [])
            
            if es_penalizacion:
                # Penalizaciones: evaluar directamente sin ponderación
                if valor is None:
                    continue
                resultado = self.evaluar_criterio(codigo, valor, config)
                if resultado["evaluado"]:
                    # Los puntos de penalización son negativos (o 0)
                    puntos_penalizacion = resultado["puntaje"]
                    suma_penalizaciones += puntos_penalizacion
                    penalizaciones_detalle.append({
                        "codigo": codigo,
                        "nombre": config.get("nombre", codigo),
                        "valor": valor,
                        "puntos": puntos_penalizacion,
                        "detalle": resultado["detalle"],
                        "es_penalizacion": True
                    })
                    print(f"   ⚠️ PENALIZACIÓN: {config.get('nombre', codigo)} = {puntos_penalizacion} pts")
                continue
            
            # Criterios normales: cálculo ponderado estándar
            puntos_en_rangos = [r.get("puntos") or r.get("puntaje", 0) for r in rangos]
            puntos_max_criterio = max(puntos_en_rangos) if puntos_en_rangos else 25
            puntos_min_criterio = min(puntos_en_rangos) if puntos_en_rangos else 0
            
            # Contribución máxima ponderada: puntos_max * (peso/100)
            contrib_max_ponderada = puntos_max_criterio * (peso / 100.0)
            suma_maxima_posible += contrib_max_ponderada
            
            # DEBUG: mostrar info de cada criterio normal
            print(f"   📋 CRITERIO NORMAL: {config.get('nombre', codigo)} [{codigo}]")
            print(f"      seccion={config.get('seccion')} | tipo={config.get('tipo_campo')} | peso={peso} | valor_recibido={valor}")
            print(f"      rangos_puntos={puntos_en_rangos} | max={puntos_max_criterio} | contrib_max_pond={contrib_max_ponderada:.2f}")
            
            if valor is None:
                print(f"      ❌ SIN VALOR - no contribuye al score")
                continue
            
            resultado = self.evaluar_criterio(codigo, valor, config)
            
            if resultado["evaluado"]:
                tipo_campo = config.get("tipo_campo", "number")
                puntos_ponderados = resultado["puntaje_ponderado"]
                
                # DEBUG: mostrar evaluación detallada
                print(f"      ✅ puntaje_crudo={resultado['puntaje']} | puntaje_pond={puntos_ponderados:.2f} | detalle={resultado['detalle']}")
                # Mostrar rangos para debug
                for i, r in enumerate(rangos):
                    r_min = r.get('min', '-inf')
                    r_max = r.get('max', 'inf')
                    r_pts = r.get('puntos') or r.get('puntaje', 0)
                    r_etiq = r.get('etiqueta', '')
                    print(f"         rango[{i}]: {r_min} - {r_max} → {r_pts} pts ({r_etiq})")
                
                evaluaciones.append({
                    "codigo": codigo,
                    "nombre": config.get("nombre", codigo),
                    "valor": valor,
                    "puntaje": resultado["puntaje"],
                    "puntos_originales": resultado["puntaje"],
                    "puntos_ponderados": round(puntos_ponderados, 2),
                    "puntos_maximos": round(contrib_max_ponderada, 2),
                    "puntos_minimos": round(puntos_min_criterio * (peso / 100.0), 2),
                    "peso": peso,
                    "detalle": resultado["detalle"],
                    "descripcion": resultado["detalle"],
                    "es_moneda": tipo_campo == "currency",
                    "es_porcentaje": tipo_campo == "percentage"
                })
                
                suma_puntos_ponderados += puntos_ponderados
                peso_total_evaluado += peso
        
        # =====================================================================
        # CÁLCULO DEL SCORE EN ESCALA 0-100
        # Fórmula: score_base = (suma_puntos_ponderados / suma_maxima_posible) * 100
        # Luego: score_final = max(0, score_base + penalizaciones)
        # =====================================================================
        if suma_maxima_posible > 0:
            score_base = (suma_puntos_ponderados / suma_maxima_posible) * 100
        else:
            score_base = 0
        
        score_base = round(min(100, max(0, score_base)), 1)
        
        # Aplicar penalizaciones (suma_penalizaciones es ≤ 0)
        score_100 = round(max(0, score_base + suma_penalizaciones), 1)
        
        # Para debug: mostrar también el puntaje bruto
        score_bruto = round(suma_puntos_ponderados, 2)
        score_bruto_max = round(suma_maxima_posible, 2)
        
        print(f"   📊 Score bruto: {score_bruto} / {score_bruto_max}")
        print(f"   📊 Score base (0-100): {score_base}")
        if suma_penalizaciones != 0:
            print(f"   ⚠️ Penalizaciones: {suma_penalizaciones} pts ({len(penalizaciones_detalle)} alertas)")
        print(f"   📊 SCORE FINAL: {score_100}")
        
        # =====================================================================
        # CAPA 3: DECISIÓN DE APROBACIÓN (Escala 0-100)
        # =====================================================================
        umbral_aprobacion = self.puntaje_minimo_aprobacion
        umbral_comite = self.puntaje_minimo_comite
        
        # Determinar estado de decisión
        if rechazo["rechazo"]:
            estado_decision = "RECHAZO_AUTOMATICO_FILTRO"
            aprobado = False
            requiere_comite = False
        elif score_100 >= umbral_aprobacion:
            estado_decision = "APROBACION_AUTOMATICA"
            aprobado = True
            requiere_comite = False
        elif score_100 >= umbral_comite:
            estado_decision = "REQUIERE_COMITE"
            aprobado = False  # Pendiente de comité
            requiere_comite = True
        else:
            estado_decision = "RECHAZO_AUTOMATICO_SCORE"
            aprobado = False
            requiere_comite = False
        
        print(f"   📊 DECISIÓN: score={score_100} | umbral_aprob={umbral_aprobacion} | umbral_comite={umbral_comite}")
        print(f"   📊 ESTADO: {estado_decision}")
        
        # =====================================================================
        # CAPA 4: ASIGNACIÓN DE PRICING (Nivel de Riesgo)
        # =====================================================================
        nivel = self.determinar_nivel_riesgo(score_100)
        
        print(f"   📊 NIVEL RIESGO: {nivel['nombre']} (rango {nivel.get('min', 0)}-{nivel.get('max', 100)})")
        print(f"   💰 TASAS: EA={nivel.get('tasa_ea')}%, Mensual={nivel.get('tasa_nominal_mensual')}%, Aval={nivel.get('aval_porcentaje')}%")
        
        # =====================================================================
        # CAPA 5: DEGRADACIÓN POR MORA TELCOS
        # Si solo tiene mora telcos (sin mora financiera) y el monto está
        # dentro del umbral, degradar nivel de riesgo en un escalón.
        # Si mora telcos > umbral → enviar a comité.
        # Mora financiera activa anula esta degradación.
        # =====================================================================
        degradacion_aplicada = False
        nivel_original = nivel["nombre"]
        razon_degradacion = None
        
        umbral_telcos = self.config.get("umbral_mora_telcos_rechazo", 200000)
        mora_telcos_val = 0
        mora_financiera_val = 0
        
        # Buscar valor de mora telcos en los valores enviados
        for key in ["mora_sector_telcos", "monto_mora_telcos", "mora_telcos"]:
            if key in valores and valores[key]:
                try:
                    v = str(valores[key]).replace("$", "").replace(",", "").replace(".", "").strip()
                    mora_telcos_val = float(v) if v else 0
                    if mora_telcos_val > 0:
                        break
                except (ValueError, TypeError):
                    pass
        
        # Buscar mora financiera (si existe, NO degradar)
        for key in ["mora_financiero_dias", "mora_financiera", "mora_sector_financiero"]:
            if key in valores and valores[key]:
                try:
                    v = str(valores[key]).replace("$", "").replace(",", "").strip()
                    mora_financiera_val = float(v) if v else 0
                    if mora_financiera_val > 0:
                        break
                except (ValueError, TypeError):
                    pass
        
        if mora_telcos_val > 0 and mora_financiera_val == 0 and not rechazo["rechazo"]:
            if mora_telcos_val <= umbral_telcos:
                # Degradar nivel de riesgo en un escalón
                nivel_degradado = self._degradar_nivel(nivel)
                if nivel_degradado and nivel_degradado["nombre"] != nivel["nombre"]:
                    degradacion_aplicada = True
                    razon_degradacion = f"Mora Telcos ${mora_telcos_val:,.0f} (≤ ${umbral_telcos:,.0f}) sin mora financiera"
                    nivel = nivel_degradado
                    print(f"   ⚠️ DEGRADACIÓN TELCOS: {nivel_original} → {nivel['nombre']} ({razon_degradacion})")
            elif mora_telcos_val > umbral_telcos and not requiere_comite:
                # Mora telcos excede umbral → enviar a comité
                requiere_comite = True
                estado_decision = "COMITE_MORA_TELCOS"
                razon_degradacion = f"Mora Telcos ${mora_telcos_val:,.0f} excede umbral ${umbral_telcos:,.0f}"
                print(f"   🔴 COMITÉ TELCOS: {razon_degradacion}")
        
        return {
            # Score principal en escala 0-100 (ÚNICO)
            "score": score_100,
            "score_normalizado": score_100,  # Alias para compatibilidad
            # Desglose de score (base + penalizaciones = final)
            "score_base": score_base,
            "penalizaciones_total": round(suma_penalizaciones, 1),
            "penalizaciones_detalle": penalizaciones_detalle,
            # Debug: score bruto (para tooltip/debug temporal)
            "score_bruto": score_bruto,
            "score_bruto_max": score_bruto_max,
            # Nivel de riesgo
            "nivel": nivel["nombre"],
            "nivel_detalle": nivel,
            # Decisión
            "estado_decision": estado_decision,
            "aprobado": aprobado,
            "requiere_comite": requiere_comite,
            "rechazo_automatico": rechazo["rechazo"],
            "razon_rechazo": rechazo["razon"],
            "factor_rechazo": rechazo["factor"],
            # Criterios evaluados
            "criterios_evaluados": evaluaciones,
            # Umbrales (escala 0-100)
            "puntaje_minimo_aprobacion": umbral_aprobacion,
            "puntaje_minimo_comite": umbral_comite,
            "puntaje_minimo": umbral_aprobacion,  # Alias para compatibilidad
            "escala_max": self.ESCALA_MAX,  # Siempre 100
            # Tasas del nivel de riesgo
            "tasa_ea": nivel.get("tasa_ea"),
            "tasa_mensual": nivel.get("tasa_nominal_mensual"),
            "porcentaje_aval": nivel.get("aval_porcentaje"),
            # Degradación por mora telcos
            "degradacion_aplicada": degradacion_aplicada,
            "nivel_original": nivel_original if degradacion_aplicada else None,
            "razon_degradacion": razon_degradacion
        }


def calcular_ingreso_validado(ingreso_midecisor, ingreso_extracto, ingreso_documento, ingreso_declarado):
    """
    Determina el ingreso más confiable cruzando hasta 4 fuentes.
    Implementa triangulación de ingresos para verificación crediticia.

    Args:
        ingreso_midecisor: int o None - Del reporte MiDecisor DataCrédito
        ingreso_extracto: int o None - Del análisis del extracto bancario
        ingreso_documento: int o None - Del soporte de ingresos (nómina/certificado)
        ingreso_declarado: int o None - Lo que dijo el solicitante

    Returns:
        tuple: (ingreso_validado: int, metodo_usado: str, confianza: str)
    """
    fuentes = {}
    if ingreso_midecisor and ingreso_midecisor > 0:
        fuentes['midecisor'] = ingreso_midecisor
    if ingreso_extracto and ingreso_extracto > 0:
        fuentes['extracto'] = ingreso_extracto
    if ingreso_documento and ingreso_documento > 0:
        fuentes['documento'] = ingreso_documento

    # Si no hay ninguna fuente válida, usar el declarado o cero
    if not fuentes:
        if ingreso_declarado and ingreso_declarado > 0:
            return (ingreso_declarado, "solo_declarado", "baja")
        return (0, "sin_datos", "nula")

    # Si solo hay 1 fuente
    if len(fuentes) == 1:
        nombre_fuente = list(fuentes.keys())[0]
        unica = list(fuentes.values())[0]
        # Si solo tenemos MiDecisor, aplicar corrección del ~15% (subestimación conocida)
        if nombre_fuente == 'midecisor':
            return (int(unica * 1.15), "midecisor_corregido", "baja")
        return (unica, f"solo_{nombre_fuente}", "media")

    # BANDERA ROJA: Si documento dice >3x que extracto, ignorar documento (posible fraude)
    if 'documento' in fuentes and 'extracto' in fuentes:
        if fuentes['documento'] > fuentes['extracto'] * 3:
            del fuentes['documento']

    # Si hay 2+ fuentes, verificar coherencia (todas dentro del 30% entre sí)
    valores = list(fuentes.values())
    coherentes = True
    for i in range(len(valores)):
        for j in range(i + 1, len(valores)):
            mayor = max(valores[i], valores[j])
            menor = min(valores[i], valores[j])
            if mayor > 0 and (mayor - menor) / mayor > 0.30:
                coherentes = False
                break

    if coherentes:
        # Todas las fuentes coinciden: usar el promedio
        promedio = int(sum(valores) / len(valores))
        confianza = "alta" if len(fuentes) >= 3 else "media"
        return (promedio, f"promedio_{len(fuentes)}_fuentes", confianza)

    # Si no son coherentes, buscar las 2 que más coinciden
    if len(fuentes) >= 2:
        # Si extracto y midecisor coinciden (dentro del 40%), usar promedio
        if 'extracto' in fuentes and 'midecisor' in fuentes:
            ext = fuentes['extracto']
            mid = fuentes['midecisor']
            mayor = max(ext, mid)
            menor = min(ext, mid)
            if mayor > 0 and (mayor - menor) / mayor <= 0.40:
                return (max(ext, mid), "extracto_midecisor_max", "media")

        # Si extracto > midecisor (caso del ~70%)
        if 'extracto' in fuentes and 'midecisor' in fuentes:
            if fuentes['extracto'] > fuentes['midecisor']:
                return (int((fuentes['extracto'] + fuentes['midecisor']) / 2), "extracto_midecisor_promedio", "media")

    # Fallback: promedio de todas las fuentes disponibles
    return (int(sum(valores) / len(valores)), "promedio_fallback", "baja")
