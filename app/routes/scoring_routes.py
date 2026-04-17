"""
SCORING_ROUTES.PY - Rutas de scoring de crédito
================================================
"""

from flask import render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import json
import traceback

from . import scoring_bp


def login_required(f):
    """Decorador que requiere autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("autorizado"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def requiere_permiso(permiso):
    """Decorador que requiere un permiso específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("autorizado"):
                return redirect(url_for("auth.login"))
            
            import sys
            from pathlib import Path
            BASE_DIR = Path(__file__).parent.parent.parent.resolve()
            if str(BASE_DIR) not in sys.path:
                sys.path.insert(0, str(BASE_DIR))
            
            from permisos import tiene_permiso
            
            if not tiene_permiso(permiso):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'error': 'Permiso denegado',
                        'code': 'PERMISSION_DENIED'
                    }), 403
                flash("No tienes permiso para acceder a esta función", "error")
                return redirect(url_for("main.dashboard"))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def _preparar_scoring_result(evaluacion, criterios_evaluados, nivel_riesgo):
    """
    Prepara el diccionario scoring_result con colores dinámicos según nivel de riesgo.
    
    Colores por nivel:
    - Alto Riesgo: Rojo (#dc3545) con texto blanco
    - Riesgo Moderado: Amarillo/Naranja (#ffc107) con texto oscuro
    - Bajo Riesgo: Verde (#28a745) con texto blanco
    """
    # evaluacion tiene estructura {"resultado": {...}, ...} - extraer el resultado interno
    resultado = evaluacion.get("resultado", {}) if isinstance(evaluacion, dict) else {}
    aprobado = resultado.get("aprobado", False)
    rechazo_automatico = resultado.get("rechazo_automatico", False)
    requiere_comite = resultado.get("requiere_comite", False)
    razon_comite = evaluacion.get("razon_comite")
    
    # Determinar colores según nivel de riesgo y estado
    nivel_lower = nivel_riesgo.lower() if nivel_riesgo else ""
    
    if rechazo_automatico:
        # Rechazado por filtro: rojo
        color = "#dc3545"
        text_color = "#ffffff"
        gradient = "linear-gradient(135deg, #dc3545 0%, #c82333 100%)"
    elif requiere_comite:
        # Pendiente comité: verde (aprobado condicionalmente)
        color = "#28a745"
        text_color = "#ffffff"
        gradient = "linear-gradient(135deg, #28a745 0%, #1e7e34 100%)"
    elif not aprobado:
        # Rechazado por score bajo: rojo
        color = "#dc3545"
        text_color = "#ffffff"
        gradient = "linear-gradient(135deg, #dc3545 0%, #c82333 100%)"
    elif "alto" in nivel_lower:
        # Alto riesgo: rojo/naranja
        color = "#fd7e14"  # Naranja
        text_color = "#ffffff"
        gradient = "linear-gradient(135deg, #fd7e14 0%, #dc3545 100%)"
    elif "moderado" in nivel_lower or "medio" in nivel_lower:
        # Riesgo moderado: amarillo/dorado
        color = "#ffc107"  # Amarillo Bootstrap warning
        text_color = "#212529"  # Texto oscuro para contraste
        gradient = "linear-gradient(135deg, #ffc107 0%, #e0a800 100%)"
    elif "bajo" in nivel_lower:
        # Bajo riesgo: verde
        color = "#28a745"  # Verde Bootstrap success
        text_color = "#ffffff"
        gradient = "linear-gradient(135deg, #28a745 0%, #1e7e34 100%)"
    else:
        # Default: gris
        color = "#6c757d"
        text_color = "#ffffff"
        gradient = "linear-gradient(135deg, #6c757d 0%, #545b62 100%)"
    
    # Extraer info de degradación de la evaluación
    degradacion_aplicada = evaluacion.get("degradacion_aplicada", False)
    nivel_original_deg = evaluacion.get("nivel_original")
    razon_degradacion = evaluacion.get("razon_degradacion")
    
    return {
        **resultado,
        "detalles": criterios_evaluados,
        "level": nivel_riesgo,
        "color": color,
        "text_color": text_color,
        "gradient": gradient,
        "razon_comite": razon_comite,
        "degradacion_aplicada": degradacion_aplicada,
        "nivel_original": nivel_original_deg,
        "razon_degradacion": razon_degradacion,
        "genero_solicitante": evaluacion.get("genero_solicitante", ""),
        "diferencial_genero": evaluacion.get("diferencial_genero", 0),
        "diferencial_genero_label": evaluacion.get("diferencial_genero_label", ""),
        "tasa_ea_sin_descuento": evaluacion.get("tasa_ea_sin_descuento")
    }


@scoring_bp.route("/scoring")
@login_required
@requiere_permiso("sco_ejecutar")
def scoring_page():
    """Página de evaluación de scoring - Carga configuración por línea de crédito"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import cargar_configuracion
    from db_helpers_scoring_linea import (
        obtener_lineas_credito_scoring,
        obtener_config_scoring_linea,
        agrupar_criterios_por_seccion
    )
    
    config = cargar_configuracion()
    lineas_credito = config.get("LINEAS_CREDITO", {})
    
    # Obtener líneas de crédito con scoring configurado
    lineas_scoring = obtener_lineas_credito_scoring()
    
    # Obtener línea por defecto (primera activa)
    linea_default_id = None
    linea_default_nombre = None
    if lineas_scoring:
        linea_default = lineas_scoring[0]
        linea_default_id = linea_default.get("id")
        linea_default_nombre = linea_default.get("nombre")
    
    # Cargar configuración de la línea por defecto
    scoring_criterios_agrupados = []
    criterios = {}
    niveles_riesgo = []
    factores_rechazo = []
    secciones = []
    
    if linea_default_id:
        config_linea = obtener_config_scoring_linea(linea_default_id)
        if config_linea:
            criterios_lista = config_linea.get("criterios", [])
            niveles_riesgo = config_linea.get("niveles_riesgo", [])
            factores_rechazo = config_linea.get("factores_rechazo", [])
            
            # Agrupar criterios por sección para el template
            scoring_criterios_agrupados = agrupar_criterios_por_seccion(criterios_lista)
            
            # Convertir lista de criterios a diccionario para compatibilidad
            for c in criterios_lista:
                criterios[c.get("codigo")] = c
    
    return render_template(
        "scoring.html",
        lineas_credito=lineas_credito,
        lineas_scoring=lineas_scoring,
        linea_default_id=linea_default_id,
        linea_default_nombre=linea_default_nombre,
        criterios=criterios,
        scoring_criterios=criterios,
        scoring_criterios_agrupados=scoring_criterios_agrupados,
        secciones=secciones,
        scoring_secciones=secciones,
        niveles_riesgo=niveles_riesgo,
        factores_rechazo=factores_rechazo,
        config_json=json.dumps({
            "lineas_credito": lineas_credito,
            "lineas_scoring": lineas_scoring,
            "criterios": criterios,
            "niveles_riesgo": niveles_riesgo
        })
    )


@scoring_bp.route("/scoring", methods=["POST"])
@login_required
@requiere_permiso("sco_ejecutar")
def calcular_scoring():
    """
    Procesar evaluación de scoring usando ScoringService.
    REFACTORIZADO: 2026-01-26 - Ahora usa ScoringService para lógica consistente.
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import cargar_scoring, guardar_evaluacion, cargar_configuracion, conectar_db
    from db_helpers_scoring_linea import cargar_scoring_por_linea
    from ..services.scoring_service import ScoringService
    from ..utils.timezone import obtener_hora_colombia
    from ..utils.formatting import parse_currency_value
    
    try:
        # Obtener datos del formulario
        form_data = request.form.to_dict()
        
        # DEBUG: Ver datos originales del formulario
        print(f"\n🔍 DEBUG FORM_DATA RECIBIDO:")
        for k, v in sorted(form_data.items()):
            if 'criterio' in k.lower() or 'saldo' in k.lower():
                print(f"   📥 {k}: '{v}' (tipo: {type(v).__name__})")
        
        # Los campos del formulario son nombre_cliente_nombre y nombre_cliente_cedula
        nombre_cliente = form_data.get("nombre_cliente", "") or form_data.get("nombre_cliente_nombre", "")
        nombre_cliente = nombre_cliente.strip()
        cedula = form_data.get("cedula", "") or form_data.get("nombre_cliente_cedula", "")
        cedula = cedula.strip()
        linea_credito = form_data.get("linea_credito", "")
        monto_solicitado = parse_currency_value(form_data.get("monto_solicitado", 0))
        
        if not nombre_cliente or not cedula:
            flash("Nombre y cédula son requeridos", "error")
            return redirect(url_for("scoring.scoring_page"))
        
        # =====================================================================
        # USAR SCORING SERVICE PARA CÁLCULO Y RECHAZO AUTOMÁTICO
        # =====================================================================
        
        # Cargar configuración específica de la línea de crédito (si existe)
        scoring_config_linea = None
        if linea_credito:
            scoring_config_linea = cargar_scoring_por_linea(linea_credito)
        
        # Si no hay config específica de línea, usar config global
        if not scoring_config_linea:
            scoring_config_linea = cargar_scoring()
        
        # Instanciar el servicio con la configuración
        scoring_service = ScoringService(scoring_config_linea)
        
        # Preparar valores para el servicio (limpiar datos del formulario)
        # Campos que NO son criterios de scoring
        campos_excluidos = [
            "nombre_cliente", "cedula", "linea_credito", "monto_solicitado", "csrf_token",
            "nombre_cliente_nombre", "nombre_cliente_cedula", "nombre_cliente_persist",
            "ingreso_declarado", "fecha_nacimiento", "edad_solicitante",
            "ingreso_verificado", "fuente_verificacion",
            "genero_solicitante"
        ]
        # Sufijos de campos auxiliares que no son criterios
        sufijos_excluidos = ["_normalized", "_hidden", "_persist"]
        
        valores_criterios = {}
        for key, value in form_data.items():
            # Excluir campos que no son criterios
            if key in campos_excluidos:
                continue
            # Excluir campos con sufijos auxiliares
            if any(key.endswith(sufijo) for sufijo in sufijos_excluidos):
                continue
            
            # Procesar valor - MANTENER string para selects
            try:
                # Si es un campo select (verificar si el valor coincide con opciones del criterio)
                if key in scoring_config_linea.get("criterios", {}) and scoring_config_linea.get("criterios", {}).get(key, {}).get('tipo_campo') in ('select', 'composite', 'seleccion', 'hidden'):
                    # Para selects, mantener el valor original string
                    valores_criterios[key] = str(value).strip()
                else:
                    # Para otros campos numéricos, convertir a float
                    tipo_campo_criterio = scoring_config_linea.get("criterios", {}).get(key, {}).get('tipo_campo', '')
                    raw_val = str(value).replace('$', '').replace('%', '').strip()
                    
                    if tipo_campo_criterio == 'currency':
                        # Currency: puntos son separadores de miles (3.350.000 → 3350000)
                        clean_val = raw_val.replace('.', '').replace(',', '')
                    else:
                        # Porcentaje/número: punto es decimal, coma puede ser decimal colombiano
                        # Si tiene punto Y coma, asumir punto=miles, coma=decimal (ej: 1.250,7)
                        if '.' in raw_val and ',' in raw_val:
                            clean_val = raw_val.replace('.', '').replace(',', '.')
                        elif ',' in raw_val:
                            # Solo coma: asumir es separador decimal (125,7 → 125.7)
                            clean_val = raw_val.replace(',', '.')
                        else:
                            # Solo punto o sin separadores: mantener tal cual (125.7 → 125.7)
                            clean_val = raw_val
                    
                    if clean_val and (clean_val.isdigit() or clean_val.replace('.', '', 1).isdigit() or clean_val.replace('-', '', 1).isdigit()):
                        valores_criterios[key] = float(clean_val)
                    else:
                        valores_criterios[key] = value
            except:
                valores_criterios[key] = value
        
        # Mapear campos del formulario a códigos de factores de rechazo
        # El formulario usa "monto_mora_telcos" pero los factores buscan "mora_telcos"
        if "monto_mora_telcos" in valores_criterios:
            valores_criterios["mora_telcos"] = valores_criterios["monto_mora_telcos"]
        
        # Mapear edad del solicitante (puede llegar como 'edad' o 'edad_solicitante')
        edad_valor = form_data.get('edad_solicitante') or form_data.get('edad')
        print(f"DEBUG edad: form_data.edad_solicitante='{form_data.get('edad_solicitante')}', form_data.edad='{form_data.get('edad')}', edad_valor='{edad_valor}'")
        if edad_valor:
            try:
                edad_num = float(str(edad_valor).replace(',', '.'))
                valores_criterios['edad_solicitante'] = edad_num
                valores_criterios['edad'] = edad_num
                print(f"DEBUG edad mapeada: edad_num={edad_num}")
            except (ValueError, TypeError):
                pass
        
        # =====================================================================
        # INGRESO DECISION + DTI TRIANGULADO (v4.5)
        # =====================================================================
        from ..services.scoring_service import calcular_ingreso_validado
        
        ingreso_midecisor = None
        ingreso_extracto = None
        ingreso_verificado_val = None
        ingreso_declarado_val = None
        fuente_verificacion = form_data.get('fuente_verificacion', 'No verificable')
        
        # --- Fuente 1: MiDecisor (criterio ingresos_netos) ---
        if 'ingresos_netos' in valores_criterios:
            try:
                ingreso_midecisor = int(float(str(valores_criterios['ingresos_netos']).replace('.', '').replace(',', '')))
            except (ValueError, TypeError):
                pass
        
        # --- Fuente 2: Extracto bancario (criterio_1772740929360 = Ingreso Promedio Mensual) ---
        if 'criterio_1772740929360' in valores_criterios:
            try:
                ingreso_extracto = int(float(str(valores_criterios['criterio_1772740929360']).replace('.', '').replace(',', '')))
            except (ValueError, TypeError):
                pass
        
        # --- Fuente 3: Ingreso verificado por el asesor ---
        ingreso_verificado_raw = form_data.get('ingreso_verificado', '').strip()
        if ingreso_verificado_raw:
            try:
                ingreso_verificado_val = int(float(
                    ingreso_verificado_raw.replace('.', '').replace(',', '').replace('$', '').replace(' ', '')
                ))
            except (ValueError, TypeError):
                pass
        
        # --- Fuente 4: Ingreso declarado ---
        ingreso_declarado_raw = form_data.get('ingreso_declarado', '').strip()
        if ingreso_declarado_raw:
            try:
                ingreso_declarado_val = int(float(
                    ingreso_declarado_raw.replace('.', '').replace(',', '').replace('$', '').replace(' ', '')
                ))
            except (ValueError, TypeError):
                pass
        
        # --- Calcular ingreso_decision ---
        # Regla: si hay ingreso verificado con fuente valida, usar max(midecisor, verificado)
        # Si fuente == "No verificable", usar triangulacion sin verificado
        ingreso_decision = None
        metodo_ingreso = "sin_datos"
        confianza_ingreso = "nula"
        alertas_comite_dti = []
        
        if fuente_verificacion != 'No verificable' and ingreso_verificado_val and ingreso_verificado_val > 0:
            # Con ingreso verificado: usar max(midecisor, verificado)
            base_midecisor = ingreso_midecisor or 0
            ingreso_decision = max(base_midecisor, ingreso_verificado_val)
            if ingreso_decision == ingreso_verificado_val:
                metodo_ingreso = f"verificado_{fuente_verificacion}"
            else:
                metodo_ingreso = "midecisor_mayor_que_verificado"
            confianza_ingreso = "alta" if ingreso_verificado_val and ingreso_midecisor else "media"
        else:
            # Sin ingreso verificado: usar triangulacion existente
            if ingreso_midecisor or ingreso_extracto or ingreso_declarado_val:
                ingreso_decision, metodo_ingreso, confianza_ingreso = calcular_ingreso_validado(
                    ingreso_midecisor, ingreso_extracto, None, ingreso_declarado_val
                )
        
        print(f"\n📊 INGRESO DECISION (v4.5):")
        print(f"   MiDecisor: {ingreso_midecisor}")
        print(f"   Extracto: {ingreso_extracto}")
        print(f"   Verificado: {ingreso_verificado_val} (fuente: {fuente_verificacion})")
        print(f"   Declarado: {ingreso_declarado_val}")
        print(f"   → Ingreso Decision: {ingreso_decision} (método: {metodo_ingreso}, confianza: {confianza_ingreso})")
        
        # --- DTI Triangulado ---
        # DTI = (cuotas_buro + libranzas_colilla + cuota_nueva) / ingreso_decision * 100
        # cuotas_buro: back-calculate desde relacion_deuda (DTI% de MiDecisor)
        # libranzas_colilla: por ahora 0 (requiere campo adicional en futuro)
        cuotas_buro = 0
        libranzas_colilla = 0
        dti_triangulado = None
        
        if ingreso_decision and ingreso_decision > 0 and 'relacion_deuda' in valores_criterios:
            try:
                dti_original = float(str(valores_criterios['relacion_deuda']).replace(',', '.'))
                
                # Back-calculate cuotas_buro desde el DTI original de MiDecisor
                if ingreso_midecisor and ingreso_midecisor > 0:
                    cuotas_buro = dti_original * ingreso_midecisor / 100
                else:
                    # Sin MiDecisor de referencia, asumir cuotas sobre ingreso_decision
                    cuotas_buro = dti_original * ingreso_decision / 100
                    alertas_comite_dti.append("DTI calculado sin ingreso MiDecisor de referencia")
                
                # Calcular DTI triangulado con ingreso_decision
                dti_triangulado = (cuotas_buro + libranzas_colilla) / ingreso_decision * 100
                
                print(f"   📈 DTI Triangulado:")
                print(f"      cuotas_buro (back-calc): ${cuotas_buro:,.0f}")
                print(f"      libranzas_colilla: ${libranzas_colilla:,.0f}")
                print(f"      DTI original: {dti_original:.1f}%")
                print(f"      DTI triangulado: {dti_triangulado:.1f}%")
                
                # Actualizar relacion_deuda con DTI triangulado
                if abs(dti_original - dti_triangulado) > 0.1:
                    print(f"      → Actualizando relacion_deuda: {dti_original:.1f}% → {dti_triangulado:.1f}%")
                    valores_criterios['relacion_deuda'] = round(dti_triangulado, 2)
                
                # Alerta de comite si DTI > 55%
                if dti_triangulado > 55:
                    alertas_comite_dti.append(f"DTI real {dti_triangulado:.1f}% supera 55%")
                
                if alertas_comite_dti:
                    for a in alertas_comite_dti:
                        print(f"      ⚠️ {a}")
            except (ValueError, TypeError) as e:
                print(f"   ⚠️ Error calculando DTI triangulado: {e}")
        
        # 1. VERIFICAR RECHAZO AUTOMÁTICO PRIMERO (usando el servicio)
        rechazo_info = scoring_service.verificar_rechazo_automatico(valores_criterios)
        
        rechazo_automatico = rechazo_info.get("rechazo", False)
        razon_rechazo = rechazo_info.get("razon")
        factor_rechazo = rechazo_info.get("factor")

        # 2. CALCULAR SCORING COMPLETO (usando el servicio)
        resultado_scoring = scoring_service.calcular_scoring(valores_criterios, linea_credito)

        # Extraer valores del resultado del servicio
        score_total = resultado_scoring.get("score", 0)
        score_normalizado = resultado_scoring.get("score_normalizado", 0)
        nivel_riesgo = resultado_scoring.get("nivel", "Sin clasificar")
        nivel_detalle = resultado_scoring.get("nivel_detalle", {})
        criterios_evaluados = resultado_scoring.get("criterios_evaluados", [])
        aprobado = resultado_scoring.get("aprobado", False)
        puntaje_minimo = resultado_scoring.get("puntaje_minimo", 38)
        puntaje_minimo_comite = resultado_scoring.get("puntaje_minimo_comite", 22)
        escala_max = resultado_scoring.get("escala_max", 100)
        # CAPA 3: Decisión de aprobación
        requiere_comite = resultado_scoring.get("requiere_comite", False)
        estado_decision = resultado_scoring.get("estado_decision", "")
        # Tasas del nivel de riesgo (CAPA 4)
        tasa_ea = resultado_scoring.get("tasa_ea")
        tasa_mensual = resultado_scoring.get("tasa_mensual")
        porcentaje_aval = resultado_scoring.get("porcentaje_aval")
        # Degradación por mora telcos (CAPA 5)
        degradacion_aplicada = resultado_scoring.get("degradacion_aplicada", False)
        nivel_original = resultado_scoring.get("nivel_original")
        razon_degradacion = resultado_scoring.get("razon_degradacion")

        # Sobrescribir aprobado si hubo rechazo automático
        if rechazo_automatico:
            aprobado = False
            requiere_comite = False
        
        # ============================================
        # DIFERENCIAL DE GÉNERO — Inclusión financiera
        # ============================================
        genero_solicitante = form_data.get('genero_solicitante', '')
        diferencial_genero = 0.0
        diferencial_genero_label = ''
        tasa_ea_sin_descuento = tasa_ea
        
        if tasa_ea is not None and genero_solicitante:
            try:
                db_genero = conectar_db()
                cursor_g = db_genero.cursor()
                
                cursor_g.execute(
                    "SELECT valor FROM parametros_sistema WHERE clave = ?",
                    ('diferencial_genero_activo',)
                )
                row_activo = cursor_g.fetchone()
                genero_activo = row_activo[0] == '1' if row_activo else False
                
                if genero_activo and genero_solicitante == 'F':
                    cursor_g.execute(
                        "SELECT valor FROM parametros_sistema WHERE clave = ?",
                        ('diferencial_genero_femenino',)
                    )
                    row_dif = cursor_g.fetchone()
                    if row_dif:
                        diferencial_genero = float(row_dif[0])
                        diferencial_genero_label = f'Inclusión financiera género: -{diferencial_genero} pp'
                        tasa_ea = tasa_ea - diferencial_genero
                        tasa_ea = max(tasa_ea, 0)
                        tasa_mensual = ((1 + tasa_ea / 100) ** (1/12) - 1) * 100
                        print(f"  👩 Diferencial género aplicado: -{diferencial_genero} pp EA")
                        print(f"  📊 Tasa final: {tasa_ea_sin_descuento}% → {tasa_ea}% EA ({tasa_mensual:.4f}% MV)")
                
                db_genero.close()
            except Exception as e:
                print(f"  ⚠️ Error leyendo diferencial género: {e}")

        # Determinar estado_comite según la decisión
        # Valores: "pending", "approved", "rejected", None (aprobación automática)
        razon_comite = None
        if requiere_comite:
            estado_comite = "pending"  # Aparecerá en panel de Comité de Crédito
            razon_comite = f"Score {score_total} en zona de revisión manual (entre {puntaje_minimo_comite} y {puntaje_minimo})"
        elif aprobado:
            estado_comite = None  # Aprobación automática, no requiere comité
        elif rechazo_automatico:
            estado_comite = "rejected"  # Rechazo por filtro
        else:
            estado_comite = "rejected"  # Rechazo por score bajo
        
        # Extraer puntaje DataCrédito de criterios_evaluados (para guardar como campo independiente)
        puntaje_dc = None
        if criterios_evaluados:
            for c in criterios_evaluados:
                if c.get("codigo") == "puntaje_datacredito" and c.get("valor") is not None:
                    try:
                        puntaje_dc = float(c["valor"])
                    except (ValueError, TypeError):
                        pass
                    break
        
        # Crear evaluación con datos del servicio
        evaluacion = {
            "timestamp": obtener_hora_colombia().isoformat(),
            "asesor": session.get("username"),
            "nombre_cliente": nombre_cliente,
            "cedula": cedula,
            "linea_credito": linea_credito,
            "monto_solicitado": monto_solicitado,
            "puntaje_datacredito": puntaje_dc,
            "resultado": {
                "score": score_total,
                "score_normalizado": score_normalizado,
                "nivel": nivel_riesgo,
                "aprobado": aprobado,
                "requiere_comite": requiere_comite,
                "estado_decision": estado_decision,
                "rechazo_automatico": rechazo_automatico,
                "razon_rechazo": razon_rechazo,
                "factor_rechazo": factor_rechazo,
                "puntaje_minimo": puntaje_minimo,
                "puntaje_minimo_comite": puntaje_minimo_comite,
                "escala_max": escala_max,
                "tasa_ea": tasa_ea,
                "tasa_mensual": tasa_mensual,
                "porcentaje_aval": porcentaje_aval
            },
            "criterios_evaluados": criterios_evaluados,
            "nivel_riesgo": nivel_riesgo,
            "nivel_detalle": nivel_detalle,
            "estado_comite": estado_comite,
            "razon_comite": razon_comite,
            "origen": "Manual",
            "ingreso_decision": {
                "valor": ingreso_decision,
                "metodo": metodo_ingreso,
                "confianza": confianza_ingreso,
                "fuentes": {
                    "midecisor": ingreso_midecisor,
                    "extracto": ingreso_extracto,
                    "verificado": ingreso_verificado_val,
                    "declarado": ingreso_declarado_val
                },
                "fuente_verificacion": fuente_verificacion
            },
            "dti_triangulado": {
                "valor": dti_triangulado,
                "cuotas_buro": round(cuotas_buro, 0) if cuotas_buro else 0,
                "libranzas_colilla": libranzas_colilla,
                "alertas": alertas_comite_dti
            },
            "degradacion_aplicada": degradacion_aplicada,
            "nivel_original": nivel_original,
            "razon_degradacion": razon_degradacion,
            "genero_solicitante": genero_solicitante,
            "diferencial_genero": diferencial_genero,
            "diferencial_genero_label": diferencial_genero_label,
            "tasa_ea_sin_descuento": tasa_ea_sin_descuento
        }
        
        # Guardar evaluación
        guardar_evaluacion(evaluacion)
        
        # =====================================================================
        # RE-RENDERIZAR FORMULARIO CON RESULTADOS
        # =====================================================================
        
        # Cargar configuración para el template
        config = cargar_configuracion()
        lineas_credito = config.get("LINEAS_CREDITO", {})
        
        # Usar la misma config que el servicio
        criterios_dict = scoring_config_linea.get("criterios", {})
        secciones = scoring_config_linea.get("secciones", [])
        niveles_riesgo = scoring_config_linea.get("niveles_riesgo", [])
        factores_rechazo = scoring_config_linea.get("factores_rechazo_automatico", [])
        
        print(f"\n🔍 DEBUG POST /scoring:")
        print(f"   criterios_dict tipo: {type(criterios_dict)}, cantidad: {len(criterios_dict)}")
        print(f"   evaluacion resultado: {evaluacion['resultado']}")
        print(f"   criterios_evaluados ({len(criterios_evaluados)}):")
        for ce in criterios_evaluados:
            print(f"      {ce.get('codigo')}: pond={ce.get('puntos_ponderados')} max={ce.get('puntos_maximos')} min={ce.get('puntos_minimos')} puntaje={ce.get('puntaje')}")
        
        # Convertir diccionario a lista para agrupar_criterios_por_seccion
        # La función espera lista de dicts con campo "codigo"
        criterios_lista = []
        for codigo, datos in criterios_dict.items():
            criterio = {"codigo": codigo}
            criterio.update(datos)
            criterios_lista.append(criterio)
        
        # Agrupar criterios por sección usando la nueva función
        from db_helpers_scoring_linea import agrupar_criterios_por_seccion, obtener_lineas_credito_scoring
        scoring_criterios_agrupados = agrupar_criterios_por_seccion(criterios_lista)
        
        # Usar el diccionario directamente para compatibilidad
        criterios = criterios_dict
        
        # Obtener líneas de scoring para el selector
        lineas_scoring = obtener_lineas_credito_scoring()
        
        # Renderizar scoring.html con los resultados Y el formulario
        return render_template(
            "scoring.html",
            lineas_credito=lineas_credito,
            lineas_scoring=lineas_scoring,
            linea_default_nombre=linea_credito,
            criterios=criterios,
            scoring_criterios=criterios,
            scoring_criterios_agrupados=scoring_criterios_agrupados,
            secciones=secciones,
            scoring_secciones=secciones,
            niveles_riesgo=niveles_riesgo,
            factores_rechazo=factores_rechazo,
            config_json=json.dumps({
                "lineas_credito": lineas_credito,
                "lineas_scoring": lineas_scoring,
                "criterios": criterios,
                "niveles_riesgo": niveles_riesgo
            }),
            # Agregar datos de resultado
            evaluacion=evaluacion,
            # scoring_result incluye resultado + detalles para el template
            # Determinar colores según nivel de riesgo y estado de aprobación
            scoring_result=_preparar_scoring_result(evaluacion, criterios_evaluados, nivel_riesgo),
            form_values=form_data  # Para mantener valores del formulario
        )
        
    except Exception as e:
        traceback.print_exc()
        flash(f"Error procesando evaluación: {str(e)}", "error")
        return redirect(url_for("scoring.scoring_page"))


@scoring_bp.route("/api/scoring/formulario/<int:linea_id>")
@login_required
@requiere_permiso("sco_ejecutar")
def api_scoring_formulario_linea(linea_id):
    """
    API para obtener la configuración de scoring de una línea específica.
    Usado para actualizar dinámicamente el formulario cuando se cambia de línea.
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_scoring_linea import obtener_config_scoring_linea, agrupar_criterios_por_seccion
    
    try:
        config_linea = obtener_config_scoring_linea(linea_id)
        
        if not config_linea:
            return jsonify({"success": False, "error": "Línea no encontrada"}), 404
        
        criterios_lista = config_linea.get("criterios", [])
        niveles_riesgo = config_linea.get("niveles_riesgo", [])
        factores_rechazo = config_linea.get("factores_rechazo", [])
        config_general = config_linea.get("config_general", {})
        
        # Agrupar criterios por sección
        criterios_agrupados = agrupar_criterios_por_seccion(criterios_lista)
        
        return jsonify({
            "success": True,
            "linea_id": linea_id,
            "criterios_agrupados": criterios_agrupados,
            "niveles_riesgo": niveles_riesgo,
            "factores_rechazo": factores_rechazo,
            "config_general": config_general
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@scoring_bp.route("/api/scoring/invalidar-cache", methods=["POST"])
@login_required
@requiere_permiso("cfg_sco_editar")
def api_scoring_invalidar_cache():
    """Invalida el cache de scoring."""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
        
    from db_helpers_scoring_linea import invalidar_cache_scoring_linea
    import logging
    logger = logging.getLogger(__name__)

    try:
        linea_id = request.get_json().get("linea_id") if request.is_json else None

        invalidar_cache_scoring_linea(linea_id)

        return jsonify({"success": True, "message": "Cache de scoring invalidado"})
    except Exception as e:
        logger.error(f"Error invalidando cache: {e}")
        return jsonify({"success": False, "error": str(e)}), 500