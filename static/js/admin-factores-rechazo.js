/**
 * ADMIN-FACTORES-RECHAZO.JS
 * Sistema de Factores de Rechazo con Dropdown Híbrido
 * =====================================================
 * 
 * Características:
 * - Dropdown agrupado con criterios del sistema, scoring y personalizado
 * - Auto-sugerencia de mensajes de rechazo
 * - Validaciones según tipo de criterio (binario, rangos)
 */

// Variables globales para criterios de factores de rechazo
let criteriosFactoresRechazo = {
    sistema: [],
    scoring: [],
    nombreLinea: '',
    cargado: false
};

/**
 * Carga los criterios disponibles para factores de rechazo desde la API
 */
async function cargarCriteriosFactoresRechazo() {
    const lineaId = window.lineaCreditoActualId || 5;
    try {
        const response = await fetch(`/api/scoring/linea/${lineaId}/criterios-factores-rechazo`);
        const data = await response.json();
        if (data.success) {
            criteriosFactoresRechazo.sistema = data.criterios_sistema || [];
            criteriosFactoresRechazo.scoring = data.criterios_scoring || [];
            criteriosFactoresRechazo.nombreLinea = data.nombre_linea || 'Línea actual';
            criteriosFactoresRechazo.cargado = true;
            console.log('✅ Criterios para factores de rechazo cargados:', {
                sistema: criteriosFactoresRechazo.sistema.length,
                scoring: criteriosFactoresRechazo.scoring.length
            });
        }
    } catch (error) {
        console.error('❌ Error cargando criterios:', error);
    }
}

/**
 * Genera las opciones del dropdown con optgroups
 */
function generarOpcionesDropdownCriterios(criterioSeleccionado) {
    let html = '';
    
    // Grupo 1: Criterios del Sistema
    html += '<optgroup label="── CRITERIOS DEL SISTEMA ──">';
    criteriosFactoresRechazo.sistema.forEach(c => {
        const selected = criterioSeleccionado === c.id ? 'selected' : '';
        const unidad = c.unidad ? ` (${c.unidad})` : '';
        html += `<option value="${c.id}" data-tipo="${c.tipo}" data-rango-min="${c.rango_min || ''}" data-rango-max="${c.rango_max || ''}" ${selected}>${c.nombre}${unidad}</option>`;
    });
    html += '</optgroup>';
    
    // Grupo 2: Criterios de Scoring de la línea actual
    if (criteriosFactoresRechazo.scoring.length > 0) {
        html += `<optgroup label="── CRITERIOS SCORING [${criteriosFactoresRechazo.nombreLinea}] ──">`;
        criteriosFactoresRechazo.scoring.forEach(c => {
            const selected = criterioSeleccionado === c.id ? 'selected' : '';
            html += `<option value="${c.id}" data-tipo="${c.tipo}" data-source="scoring" ${selected}>${c.nombre}</option>`;
        });
        html += '</optgroup>';
    }
    
    // Grupo 3: Opción Personalizado
    html += '<optgroup label="── OTRO ──">';
    const customSelected = criterioSeleccionado === '__personalizado__' ? 'selected' : '';
    html += `<option value="__personalizado__" data-tipo="personalizado" ${customSelected}>+ Personalizado...</option>`;
    html += '</optgroup>';
    
    return html;
}

/**
 * Genera las opciones del dropdown usando solo criterios de scoring (fallback)
 */
function generarOpcionesDropdownScoringOnly(criterioSeleccionado) {
    let html = '';
    if (window.scoringData && window.scoringData.criterios) {
        Object.keys(window.scoringData.criterios).forEach(id => {
            const criterio = window.scoringData.criterios[id];
            const nombreMostrar = criterio.nombre || id;
            const selected = criterioSeleccionado === id ? 'selected' : '';
            html += `<option value="${id}" ${selected}>${nombreMostrar}</option>`;
        });
    }
    return html;
}

/**
 * Carga y renderiza los factores de rechazo (VERSIÓN 3.0 - Dropdown Híbrido)
 */
async function cargarFactoresRechazoV3() {
    const tbody = document.getElementById('factores-rechazo-body');
    if (!tbody) {
        console.error('❌ Elemento factores-rechazo-body no encontrado');
        return;
    }

    // Cargar criterios si no están cargados
    if (!criteriosFactoresRechazo.cargado) {
        await cargarCriteriosFactoresRechazo();
    }

    if (typeof scoringData === 'undefined') {
        console.error('❌ scoringData no está definido');
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error: No se pudo cargar la configuración de scoring</td></tr>';
        return;
    }

    tbody.innerHTML = '';

    if (!scoringData.factores_rechazo_automatico || !Array.isArray(scoringData.factores_rechazo_automatico)) {
        console.warn('⚠️ No hay factores de rechazo configurados');
        scoringData.factores_rechazo_automatico = [];
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted"><i class="bi bi-info-circle me-2"></i>No hay factores de rechazo configurados. Haz clic en "Agregar Factor de Rechazo".</td></tr>';
        return;
    }

    console.log('✅ Cargando', scoringData.factores_rechazo_automatico.length, 'factores de rechazo...');

    scoringData.factores_rechazo_automatico.forEach((factor, index) => {
        const criterioId = factor.criterio || '';
        const criterioPersonalizado = factor.criterio_personalizado || '';
        const operador = factor.operador || '<';
        const valorLimite = factor.valor_limite || factor.valor_minimo || 0;
        const mensaje = factor.mensaje || '';
        const esPersonalizado = factor.tipo_criterio === 'personalizado' || criterioId === '__personalizado__';

        // Determinar qué opciones mostrar
        const tieneOpciones = criteriosFactoresRechazo.cargado && criteriosFactoresRechazo.sistema.length > 0;
        const opcionesHtml = tieneOpciones 
            ? generarOpcionesDropdownCriterios(esPersonalizado ? '__personalizado__' : criterioId)
            : generarOpcionesDropdownScoringOnly(criterioId);

        const row = document.createElement('tr');
        row.id = `factor-row-${index}`;
        row.innerHTML = `
            <td>
                <select class="form-select form-select-sm factor-criterio" data-index="${index}" onchange="onCriterioChange(this, ${index})">
                    ${opcionesHtml}
                </select>
                <input type="text" class="form-control form-control-sm factor-criterio-custom mt-1" 
                       data-index="${index}" placeholder="Nombre del criterio personalizado"
                       value="${criterioPersonalizado}" style="display: ${esPersonalizado ? 'block' : 'none'};">
            </td>
            <td>
                <div class="input-group input-group-sm">
                    <select class="form-select factor-operador" data-index="${index}" style="min-width: 140px;">
                        <option value="<" ${operador === '<' ? 'selected' : ''}>< menor que</option>
                        <option value="<=" ${operador === '<=' ? 'selected' : ''}>≤ menor o igual</option>
                        <option value=">" ${operador === '>' ? 'selected' : ''}>> mayor que</option>
                        <option value=">=" ${operador === '>=' ? 'selected' : ''}>≥ mayor o igual</option>
                        <option value="==" ${operador === '==' ? 'selected' : ''}>== igual a</option>
                    </select>
                    <input type="number" class="form-control factor-valor" data-index="${index}"
                           value="${valorLimite}" style="max-width: 100px;">
                </div>
                <small class="text-muted factor-ayuda" data-index="${index}"></small>
            </td>
            <td>
                <div class="input-group input-group-sm">
                    <input type="text" class="form-control factor-mensaje" data-index="${index}"
                           value="${mensaje}" placeholder="Mensaje de rechazo">
                    <button type="button" class="btn btn-outline-secondary" onclick="sugerirMensajeRechazo(${index})" title="Sugerir mensaje automático">
                        <i class="bi bi-magic"></i>
                    </button>
                </div>
            </td>
            <td class="text-center">
                <button type="button" class="btn btn-danger btn-sm" onclick="eliminarFactorRechazoV3(${index})" title="Eliminar">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
        
        // Actualizar ayuda según tipo de criterio
        actualizarAyudaCriterio(index);
    });

    // Agregar listeners para cambios
    agregarListenersFactoresV3();
    console.log('✅ Factores de rechazo cargados exitosamente (v3.0)');
}

/**
 * Manejar cambio de criterio en el dropdown
 */
function onCriterioChange(select, index) {
    const valor = select.value;
    const customInput = document.querySelector(`.factor-criterio-custom[data-index="${index}"]`);
    
    if (valor === '__personalizado__') {
        if (customInput) {
            customInput.style.display = 'block';
            customInput.focus();
        }
        scoringData.factores_rechazo_automatico[index].tipo_criterio = 'personalizado';
        scoringData.factores_rechazo_automatico[index].criterio = '__personalizado__';
    } else {
        if (customInput) {
            customInput.style.display = 'none';
            customInput.value = '';
        }
        
        // Determinar tipo de criterio
        const option = select.options[select.selectedIndex];
        const source = option?.dataset?.source;
        scoringData.factores_rechazo_automatico[index].tipo_criterio = source === 'scoring' ? 'scoring' : 'sistema';
        scoringData.factores_rechazo_automatico[index].criterio = valor;
        scoringData.factores_rechazo_automatico[index].criterio_personalizado = '';
    }
    
    actualizarAyudaCriterio(index);
}

/**
 * Actualiza el texto de ayuda según el tipo de criterio seleccionado
 */
function actualizarAyudaCriterio(index) {
    const select = document.querySelector(`.factor-criterio[data-index="${index}"]`);
    const ayuda = document.querySelector(`.factor-ayuda[data-index="${index}"]`);
    if (!select || !ayuda) return;
    
    const option = select.options[select.selectedIndex];
    const tipo = option?.dataset?.tipo || '';
    const rangoMin = option?.dataset?.rangoMin || '';
    const rangoMax = option?.dataset?.rangoMax || '';
    
    if (tipo === 'binario') {
        ayuda.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> Binario: 0=Falla, 1=OK</span>';
    } else if (rangoMin && rangoMax) {
        ayuda.innerHTML = `<span class="text-info"><i class="bi bi-info-circle"></i> Rango válido: ${rangoMin} - ${rangoMax}</span>`;
    } else {
        ayuda.innerHTML = '';
    }
}

/**
 * Sugiere un mensaje de rechazo basado en el criterio seleccionado
 */
async function sugerirMensajeRechazo(index) {
    const factor = scoringData.factores_rechazo_automatico[index];
    if (!factor) return;
    
    const criterioId = factor.criterio;
    const operador = factor.operador || '<';
    const valor = factor.valor_limite || 0;
    const mensajeInput = document.querySelector(`.factor-mensaje[data-index="${index}"]`);
    
    // Si es personalizado, generar mensaje simple
    if (criterioId === '__personalizado__') {
        const customName = factor.criterio_personalizado || 'Criterio';
        const opTexto = {
            '<': 'menor que',
            '<=': 'menor o igual a',
            '>': 'mayor que',
            '>=': 'mayor o igual a',
            '==': 'igual a'
        }[operador] || operador;
        
        if (mensajeInput) {
            mensajeInput.value = `${customName} ${opTexto} ${valor}`;
            factor.mensaje = mensajeInput.value;
        }
        return;
    }
    
    // Llamar API para generar mensaje
    try {
        const response = await fetch('/api/scoring/generar-mensaje-rechazo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ criterio_id: criterioId, operador, valor })
        });
        const data = await response.json();
        if (data.success && data.mensaje_sugerido && mensajeInput) {
            mensajeInput.value = data.mensaje_sugerido;
            factor.mensaje = data.mensaje_sugerido;
            console.log('✅ Mensaje sugerido:', data.mensaje_sugerido);
        }
    } catch (error) {
        console.error('Error sugiriendo mensaje:', error);
        // Fallback: mensaje genérico
        if (mensajeInput) {
            mensajeInput.value = `Rechazo por ${criterioId}: valor ${operador} ${valor}`;
            factor.mensaje = mensajeInput.value;
        }
    }
}

/**
 * Agrega listeners a los campos de factores de rechazo
 */
function agregarListenersFactoresV3() {
    document.querySelectorAll('.factor-criterio, .factor-operador, .factor-valor, .factor-mensaje, .factor-criterio-custom').forEach(input => {
        // Remover listeners anteriores
        input.removeEventListener('change', handleFactorChange);
        // Agregar nuevo listener
        input.addEventListener('change', handleFactorChange);
    });
}

/**
 * Manejador de cambios en campos de factores
 */
function handleFactorChange(event) {
    const input = event.target;
    const index = parseInt(input.dataset.index);
    
    if (isNaN(index) || !scoringData.factores_rechazo_automatico[index]) {
        scoringData.factores_rechazo_automatico[index] = {};
    }

    if (input.classList.contains('factor-criterio-custom')) {
        scoringData.factores_rechazo_automatico[index].criterio_personalizado = input.value;
    } else if (input.classList.contains('factor-operador')) {
        scoringData.factores_rechazo_automatico[index].operador = input.value;
    } else if (input.classList.contains('factor-valor')) {
        const valor = parseFloat(input.value) || 0;
        scoringData.factores_rechazo_automatico[index].valor_limite = valor;
        scoringData.factores_rechazo_automatico[index].valor_minimo = valor;
    } else if (input.classList.contains('factor-mensaje')) {
        scoringData.factores_rechazo_automatico[index].mensaje = input.value;
    }
}

/**
 * Agrega un nuevo factor de rechazo
 */
async function agregarFactorRechazoV3() {
    // Cargar criterios si no están cargados
    if (!criteriosFactoresRechazo.cargado) {
        await cargarCriteriosFactoresRechazo();
    }
    
    // Usar primer criterio del sistema como default
    const primerCriterio = criteriosFactoresRechazo.sistema[0];
    const nuevoFactor = {
        criterio: primerCriterio ? primerCriterio.id : 'score_datacredito',
        tipo_criterio: 'sistema',
        criterio_personalizado: '',
        operador: "<",
        valor_limite: primerCriterio ? (primerCriterio.rango_min || 0) : 0,
        valor_minimo: primerCriterio ? (primerCriterio.rango_min || 0) : 0,
        mensaje: ''
    };

    if (!scoringData.factores_rechazo_automatico) {
        scoringData.factores_rechazo_automatico = [];
    }

    scoringData.factores_rechazo_automatico.push(nuevoFactor);
    await cargarFactoresRechazoV3();
    
    // Auto-sugerir mensaje para el nuevo factor
    const nuevoIndex = scoringData.factores_rechazo_automatico.length - 1;
    setTimeout(() => sugerirMensajeRechazo(nuevoIndex), 100);
}

/**
 * Elimina un factor de rechazo
 */
function eliminarFactorRechazoV3(index) {
    if (confirm('¿Eliminar este factor de rechazo?')) {
        scoringData.factores_rechazo_automatico.splice(index, 1);
        cargarFactoresRechazoV3();
    }
}

// Exponer funciones globalmente para compatibilidad
window.cargarFactoresRechazo = cargarFactoresRechazoV3;
window.agregarFactorRechazo = agregarFactorRechazoV3;
window.eliminarFactorRechazo = eliminarFactorRechazoV3;
window.onCriterioChange = onCriterioChange;
window.sugerirMensajeRechazo = sugerirMensajeRechazo;

console.log('✅ admin-factores-rechazo.js cargado (v3.0 - Dropdown Híbrido)');
