"""
CONFIG_EXTRACCION.PY - Fuentes de extracción de datos para scoring
===================================================================

Define las fuentes disponibles para extracción automática de datos
de los criterios de scoring. Cada fuente puede ser:
- documento: PDF/imagen que requiere procesamiento IA
- api: Consulta automática a servicio externo
- manual: Ingreso directo por el analista
"""

FUENTES_EXTRACCION = {
    "midecisor_pdf": {
        "label": "Reporte MiDecisor (DataCrédito)",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "PDF del reporte MiDecisor de DataCrédito Experian"
    },
    "extracto_bancario": {
        "label": "Extracto Bancario (PDF/Imagen)",
        "tipo": "documento",
        "requiere_password": True,
        "descripcion": "Extracto bancario últimos 3 meses, puede estar protegido con cédula"
    },
    "soporte_ingresos": {
        "label": "Soporte de Ingresos (Nómina/Certificado)",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Comprobante de nómina, certificación laboral o carta laboral"
    },
    "certificado_laboral": {
        "label": "Certificado Laboral",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Carta o certificado del empleador"
    },
    "colilla_pago": {
        "label": "Colilla / Desprendible de Nómina",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Desprendible de nómina últimos 3 meses"
    },
    "declaracion_renta": {
        "label": "Declaración de Renta DIAN (Formato 210)",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Declaración de renta persona natural"
    },
    "apitude_runt": {
        "label": "RUNT (vía Apitude API)",
        "tipo": "api",
        "requiere_password": False,
        "descripcion": "Consulta automática RUNT por cédula"
    },
    "apitude_adres": {
        "label": "ADRES / Régimen de Salud (vía Apitude API)",
        "tipo": "api",
        "requiere_password": False,
        "descripcion": "Consulta automática afiliación salud por cédula"
    },
    "apitude_simit": {
        "label": "SIMIT - Multas Tránsito (vía Apitude API)",
        "tipo": "api",
        "requiere_password": False,
        "descripcion": "Consulta automática multas de tránsito"
    },
    "apitude_judicial": {
        "label": "Procesos Judiciales (vía Apitude API)",
        "tipo": "api",
        "requiere_password": False,
        "descripcion": "Consulta automática Rama Judicial"
    },
    "cedula_imagen": {
        "label": "Cédula de Ciudadanía (foto)",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Foto frontal y trasera de la cédula colombiana"
    },
    "credolab_reporte": {
        "label": "Reporte Credolab",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Reporte de score conductual Credolab"
    },
    "recibo_servicios": {
        "label": "Recibo de Servicios Publicos (Luz/Agua/Gas)",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Recibo reciente de servicios publicos para verificar estrato y direccion"
    },
    "certificado_seguridad_social": {
        "label": "Certificado EPS / Fondo Pension / Caja Compensacion",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Certificado de afiliacion a EPS, fondo de pensiones o caja de compensacion"
    },
    "planilla_pila": {
        "label": "Planilla PILA (opcional)",
        "tipo": "documento",
        "requiere_password": False,
        "descripcion": "Planilla de aportes a seguridad social. Valida ingreso base de cotizacion"
    },
    "formulario_manual": {
        "label": "Ingreso Manual (formulario)",
        "tipo": "manual",
        "requiere_password": False,
        "descripcion": "El analista ingresa el valor directamente"
    }
}
