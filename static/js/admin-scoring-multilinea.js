/**
 * ADMIN-SCORING-MULTILINEA.JS
 * ===========================
 *
 * JavaScript para gestionar el scoring por línea de crédito
 * en el panel de administración.
 *
 * Author: Sistema Loansi
 * Date: 2026-01-13
 */

// ============================================================================
// VARIABLES GLOBALES
// ============================================================================

let lineaSeleccionadaId = null;
let lineaSeleccionadaNombre = "";
let configScoringLinea = null;
let lineasCreditoDisponibles = [];

/**
 * Fetch con verificacion de sesion. Si el servidor retorna 401,
 * redirige al login automaticamente.
 */
function fetchConAuth(url, options) {
  return fetch(url, options).then(r => {
    if (r.status === 401) {
      console.warn('Sesion expirada — redirigiendo al login');
      alert('Tu sesion ha expirado. Seras redirigido al login.');
      window.location.href = '/login';
      return Promise.reject(new Error('SESSION_EXPIRED'));
    }
    return r;
  });
}
// Mapa de colores personalizados de sección (se guardará en config si es posible)
let customSectionColors = {};
// Mapa de metadatos de sección (icono, descripción, orden)
let customSectionMeta = {};

// Colores disponibles para secciones
const SECCION_COLORS = {
  // Default mappings
  "Probabilidad de Pago": "purple",
  "Análisis de Ingresos": "green",
  "Análisis de Endeudamiento": "blue",
  "Historial Crediticio": "orange",
  "Comportamiento de Pago": "cyan",
  "Análisis Sectorial": "teal",
  "Verificación Documental": "red",
  "Información Personal": "indigo",
  "Otros Criterios": "secondary",
  "Sin Categoría": "#16162e"
};

const AVAILABLE_COLORS = [
  { value: 'primary', label: 'Azul (Primary)' },
  { value: 'secondary', label: 'Gris (Secondary)' },
  { value: 'success', label: 'Verde (Success)' },
  { value: 'danger', label: 'Rojo (Danger)' },
  { value: 'warning', label: 'Amarillo (Warning)' },
  { value: 'info', label: 'Celeste (Info)' },
  { value: 'dark', label: 'Oscuro (Dark)' },
  { value: 'purple', label: 'Morado' },
  { value: 'indigo', label: 'Indigo' },
  { value: 'teal', label: 'Verde Azulado' },
  { value: 'orange', label: 'Naranja' }
];

/**
 * Aclara un color HEX para usarlo como fondo
 * @param {string} hex - Color en formato #RRGGBB
 * @param {number} factor - Factor de aclarado (0-1, donde 1 es blanco)
 * @returns {string} Color aclarado en formato #RRGGBB
 */
function lightenColor(hex, factor) {
  // Remover # si existe
  hex = hex.replace('#', '');
  
  // Convertir a RGB
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  
  // Aclarar mezclando con blanco
  const newR = Math.round(r + (255 - r) * factor);
  const newG = Math.round(g + (255 - g) * factor);
  const newB = Math.round(b + (255 - b) * factor);
  
  // Convertir de vuelta a HEX
  return `#${newR.toString(16).padStart(2, '0')}${newG.toString(16).padStart(2, '0')}${newB.toString(16).padStart(2, '0')}`;
}

// ============================================================================
// INICIALIZACIÓN
// ============================================================================

document.addEventListener("DOMContentLoaded", function () {
  // Verificar si estamos en la pestaña de Scoring
  const scoringTab = document.getElementById("Scoring");
  if (scoringTab) {
    console.log("🔄 Inicializando scoring multi-línea...");
    // Inicializar selector de línea
    initSelectorLineaCredito();
    // Inyectar estilos para colores custom si faltan
    injectCustomColorStyles();
  }
});

function injectCustomColorStyles() {
  const styleId = 'custom-section-colors-style';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
            .bg-purple-subtle { background-color: #e0cffc !important; }
            .bg-indigo-subtle { background-color: #cff4fc !important; } /* Bootstrap info-like */
            .bg-teal-subtle { background-color: #20c997 !important; opacity: 0.2; }
            .text-purple-emphasis { color: #6f42c1 !important; }
            .text-teal-emphasis { color: #0ca678 !important; }
            .border-purple { border-color: #6f42c1 !important; }
            .border-teal { border-color: #20c997 !important; }
        `;
    document.head.appendChild(style);
  }
}

/**
 * Inicializa el selector de línea de crédito
 */
async function initSelectorLineaCredito() {
  console.log("🔄 Cargando líneas de crédito para scoring...");

  try {
    const response = await fetchConAuth("/api/scoring/lineas-credito", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRFToken(),
      },
    });

    const data = await response.json();

    if (data.success) {
      console.log("✅ Líneas de crédito cargadas:", data.lineas.length);
      lineasCreditoDisponibles = data.lineas;
      renderSelectorLinea(data.lineas);

      // Seleccionar primera línea por defecto
      if (data.lineas.length > 0) {
        await seleccionarLineaCredito(data.lineas[0].id, data.lineas[0].nombre);
      }
    } else {
      console.error("❌ Error cargando líneas:", data.error);
      mostrarAlertaScoring("Error al cargar líneas de crédito", "danger");
    }
  } catch (error) {
    console.error("❌ Error en initSelectorLineaCredito:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  }
}

/**
 * Renderiza el selector de línea de crédito
 */
function renderSelectorLinea(lineas) {
  const container = document.getElementById("selectorLineaCreditoContainer");
  if (!container) {
    console.warn("Contenedor de selector no encontrado");
    return;
  }

  let html = `
        <div class="card mb-4 border-primary">
            <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                <span><i class="bi bi-box-seam me-2"></i>Línea de Crédito</span>
                <span class="badge bg-light fw-bold border border-primary" id="badgeLineaActual" style="font-size: 0.9rem; color: #000 !important;">Sin seleccionar</span>
            </div>
            <div class="card-body">
                <div class="row align-items-end">
                    <div class="col-md-6 mb-2 mb-md-0">
                        <label class="form-label fw-bold">Seleccionar línea para configurar:</label>
                        <select class="form-select form-select-lg" id="selectLineaCredito" 
                                onchange="onCambioLineaCredito(this.value)">
                            <option value="">-- Seleccione una línea --</option>
                            ${lineas
      .map(
        (l) => `
                                <option value="${l.id}" data-nombre="${l.nombre
          }">
                                    ${l.nombre} ${l.tiene_config_scoring ? "✓" : "⚠️"
          }
                                    ${l.tiene_config_scoring ? `(${l.num_niveles_riesgo}N / ${l.num_factores_rechazo}F)` : "(Sin config)"
          }
                                </option>
                            `
      )
      .join("")}
                        </select>
                    </div>
                    <div class="col-md-3 mb-2 mb-md-0">
                        <button type="button" class="btn btn-outline-secondary w-100" 
                                onclick="copiarConfiguracionModal()" 
                                ${lineas.length < 2 ? "disabled" : ""}>
                            <i class="bi bi-clipboard-plus me-1"></i>Copiar de otra línea
                        </button>
                    </div>
                    <div class="col-md-3">
                        <button type="button" class="btn btn-outline-info w-100" 
                                onclick="refrescarConfigLinea()">
                            <i class="bi bi-arrow-clockwise me-1"></i>Refrescar
                        </button>
                    </div>
                </div>
                
                <div id="infoLineaSeleccionada" class="mt-3" style="display:none;">
                    <div class="alert alert-info mb-0">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong id="nombreLineaInfo">-</strong>
                                <span class="ms-2 text-muted" id="estadoConfigInfo">-</span>
                            </div>
                            <div class="text-end">
                                <span class="badge bg-secondary me-1" id="numNivelesInfo">0 niveles</span>
                                <span class="badge bg-secondary" id="numFactoresInfo">0 factores</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

  container.innerHTML = html;
}

/**
 * Actualiza el texto del selector de línea después de guardar config de aprobación
 * para reflejar cambios en score_datacredito_minimo y otros valores
 */
function actualizarSelectorLineaDespuesDeGuardar() {
  if (!lineaSeleccionadaId || !configScoringLinea) return;
  
  const select = document.getElementById("selectLineaCredito");
  if (!select) return;
  
  const numNiveles = configScoringLinea.niveles_riesgo?.length || 0;
  const numFactores = configScoringLinea.factores_rechazo?.length || 0;
  
  // Actualizar la opción del selector
  for (let i = 0; i < select.options.length; i++) {
    if (select.options[i].value == lineaSeleccionadaId) {
      const nombre = select.options[i].dataset.nombre || lineaSeleccionadaNombre;
      select.options[i].textContent = `${nombre} ✓ (${numNiveles}N / ${numFactores}F)`;
      break;
    }
  }
  
  // Actualizar también el cache de líneas disponibles
  if (lineasCreditoDisponibles) {
    const linea = lineasCreditoDisponibles.find(l => l.id == lineaSeleccionadaId);
    if (linea) {
      linea.num_niveles_riesgo = numNiveles;
      linea.num_factores_rechazo = numFactores;
    }
  }
}

/**
 * Maneja el cambio de línea de crédito seleccionada
 */
async function onCambioLineaCredito(lineaId) {
  if (!lineaId) {
    lineaSeleccionadaId = null;
    lineaSeleccionadaNombre = "";
    configScoringLinea = null;
    ocultarContenidoScoring();
    return;
  }

  const select = document.getElementById("selectLineaCredito");
  const selectedOption = select.options[select.selectedIndex];
  const nombreLinea = selectedOption.dataset.nombre;

  await seleccionarLineaCredito(parseInt(lineaId), nombreLinea);
}

/**
 * Selecciona una línea de crédito y carga su configuración
 */
async function seleccionarLineaCredito(lineaId, nombreLinea) {
  console.log(`🔄 Cargando configuración de línea ${nombreLinea} (ID: ${lineaId})...`);

  try {
    lineaSeleccionadaId = lineaId;
    lineaSeleccionadaNombre = nombreLinea;

    // Actualizar UI del selector
    const select = document.getElementById("selectLineaCredito");
    if (select) {
      select.value = lineaId;
    }

    // Actualizar badge principal
    const badge = document.getElementById("badgeLineaActual");
    if (badge) {
      badge.textContent = nombreLinea;
    }

    // Actualizar badges en las pestañas
    const badgeNiveles = document.getElementById("badgeLineaNiveles");
    const badgeFactores = document.getElementById("badgeLineaFactores");
    if (badgeNiveles) badgeNiveles.textContent = nombreLinea;
    if (badgeFactores) badgeFactores.textContent = nombreLinea;

    // Cargar configuración de la línea
    const response = await fetchConAuth(`/api/scoring/linea/${lineaId}/config`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRFToken(),
      },
    });

    const data = await response.json();

    if (data.success) {
      console.log(`✅ Configuración de ${nombreLinea} cargada correctamente`);
      configScoringLinea = data.config;
      
      // IMPORTANTE: Limpiar metadatos de sección al cambiar de línea
      customSectionColors = {};
      customSectionMeta = {};
      // Limpiar secciones activas - solo mantener "Sin Categoría" como base
      seccionesActivas = new Set(["Sin Categoría"]);

      // DEBUG: Log loaded criterios
      console.log("🔍 DEBUG seleccionarLineaCredito: criterios recibidos");
      console.log("   📥 Total:", data.config.criterios?.length || 0);
      if (data.config.criterios) {
        // Restaurar colores y metadatos personalizados desde los criterios (persistencia)
        data.config.criterios.forEach(c => {
          if (c.seccion) {
            if (c.color_context) {
              customSectionColors[c.seccion] = c.color_context;
            }
            // Restaurar metadatos de sección (icono, descripción, orden)
            if (c.seccion_icono || c.seccion_descripcion || c.seccion_orden !== undefined && c.seccion_orden !== null) {
              if (!customSectionMeta[c.seccion]) {
                customSectionMeta[c.seccion] = {};
              }
              if (c.seccion_icono) customSectionMeta[c.seccion].icono = c.seccion_icono;
              if (c.seccion_descripcion) customSectionMeta[c.seccion].descripcion = c.seccion_descripcion;
              // Convertir orden a número (viene como TEXT de la BD)
              if (c.seccion_orden !== undefined && c.seccion_orden !== null) {
                customSectionMeta[c.seccion].orden = parseInt(c.seccion_orden) || 0;
              }
            }
          }
        });

        data.config.criterios.slice(0, 3).forEach((c, i) => {
          console.log(`      [${i}] ${c.codigo}: seccion='${c.seccion}', peso=${c.peso}`);
        });
      }

      // Actualizar info de línea
      actualizarInfoLinea(data.config);

      // Renderizar contenido de las pestañas (nueva estructura)
      renderNivelesRiesgoLinea(data.config.niveles_riesgo);
      // Resetear estado de cambios en niveles al cargar nueva línea
      unsavedNivelesChanges = false;
      updateNivelesButtonState();
      renderAprobacionLinea(data.config.config_general, data.config.factores_rechazo);
      // Resetear estado de cambios en aprobación al cargar nueva línea
      unsavedAprobacionChanges = false;
      updateAprobacionButtonState();
      renderCriteriosLinea(data.config.criterios);
      // Resetear estado de cambios en criterios al cargar nueva línea
      unsavedChanges = false;
      updateSaveButtonState();

      mostrarContenidoScoring();
      console.log(`✅ Línea ${nombreLinea} lista para editar`);
    } else {
      console.error("❌ Error cargando config:", data.error);
      mostrarAlertaScoring(
        `Error al cargar configuración: ${data.error}`,
        "danger"
      );
    }
  } catch (error) {
    console.error("❌ Error en seleccionarLineaCredito:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  }
}

/**
 * Actualiza la información de la línea seleccionada
 */
function actualizarInfoLinea(config) {
  const infoContainer = document.getElementById("infoLineaSeleccionada");
  const nombreInfo = document.getElementById("nombreLineaInfo");
  const estadoInfo = document.getElementById("estadoConfigInfo");
  const numNivelesInfo = document.getElementById("numNivelesInfo");
  const numFactoresInfo = document.getElementById("numFactoresInfo");

  if (!infoContainer) return;

  infoContainer.style.display = "block";

  if (nombreInfo) {
    nombreInfo.textContent =
      config.config_general?.linea_nombre || lineaSeleccionadaNombre;
  }

  if (estadoInfo) {
    const tieneConfig =
      config.niveles_riesgo && config.niveles_riesgo.length > 0;
    estadoInfo.innerHTML = tieneConfig
      ? '<span class="text-success"><i class="bi bi-check-circle"></i> Configuración activa</span>'
      : '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> Sin configuración específica</span>';
  }

  if (numNivelesInfo) {
    numNivelesInfo.textContent = `${config.niveles_riesgo?.length || 0
      } niveles`;
  }

  if (numFactoresInfo) {
    numFactoresInfo.textContent = `${config.factores_rechazo?.length || 0
      } factores`;
  }
}

// ============================================================================
// RENDERIZADO DE NIVELES DE RIESGO
// ============================================================================

/**
 * Renderiza los niveles de riesgo para la línea seleccionada
 */
function renderNivelesRiesgoLinea(niveles) {
  const container = document.getElementById("nivelesRiesgoLineaContainer");
  if (!container) return;

  // Header con botón agregar
  let html = `
    <div class="mb-3 d-flex justify-content-end align-items-center">
      <button type="button" class="btn btn-sm btn-outline-success" onclick="agregarNivelRiesgoLinea()">
        <i class="bi bi-plus-lg me-1"></i>Agregar nivel
      </button>
    </div>
  `;

  if (!niveles || niveles.length === 0) {
    html += `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i>
                No hay niveles de riesgo configurados para esta línea.
                <button type="button" class="btn btn-sm btn-primary ms-2" 
                        onclick="crearNivelesRiesgoPorDefecto()">
                    Crear niveles por defecto
                </button>
            </div>
        `;
    container.innerHTML = html;
    return;
  }

  html += `<div class="row">`;

  niveles.forEach((nivel, index) => {
    html += `
            <div class="col-md-4 mb-3">
                <div class="card h-100" style="border: 2px solid ${nivel.color
      };">
                    <div class="card-header d-flex justify-content-between align-items-center" style="background-color: ${nivel.color
      };">
                        <input type="text" class="form-control form-control-sm fw-bold flex-grow-1 me-2"
                               value="${nivel.nombre}"
                               onchange="actualizarNivelLinea(${index}, 'nombre', this.value)"
                               style="background: transparent; border: none;">
                        <button type="button" class="btn btn-sm btn-delete-nivel" 
                                onclick="eliminarNivelRiesgoLinea(${index})" title="Eliminar nivel"
                                style="background-color: white; border: 1px solid #dee2e6;">
                            <i class="bi bi-trash" style="color: #000; font-size: 1.1rem;"></i>
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label small">Score Mín</label>
                                <input type="number" class="form-control form-control-sm"
                                       value="${nivel.min
      }" min="0" max="100" step="0.1"
                                       onchange="actualizarNivelLinea(${index}, 'min', this.value)">
                            </div>
                            <div class="col-6">
                                <label class="form-label small">Score Máx</label>
                                <input type="number" class="form-control form-control-sm"
                                       value="${nivel.max
      }" min="0" max="100" step="0.1"
                                       onchange="actualizarNivelLinea(${index}, 'max', this.value)">
                            </div>
                        </div>
                        
                        <hr>
                        <h6 class="text-muted small">Tasas para ${lineaSeleccionadaNombre}</h6>
                        
                        <div class="mb-2">
                            <label class="form-label small">Tasa E.A. (%)</label>
                            <div class="input-group input-group-sm">
                                <input type="number" class="form-control" step="0.01"
                                       value="${nivel.tasa_ea}"
                                       onchange="actualizarNivelLinea(${index}, 'tasa_ea', this.value)">
                                <span class="input-group-text">%</span>
                            </div>
                        </div>
                        
                        <div class="mb-2">
                            <label class="form-label small">Tasa Nom. Mensual (%) <small class="text-info">(auto)</small></label>
                            <div class="input-group input-group-sm">
                                <input type="number" class="form-control bg-light" step="0.0001"
                                       value="${nivel.tasa_nominal_mensual}" readonly
                                       title="Se calcula automáticamente desde la Tasa E.A.">
                                <span class="input-group-text">%</span>
                            </div>
                        </div>
                        
                        <div class="mb-2">
                            <label class="form-label small">Aval (%)</label>
                            <div class="input-group input-group-sm">
                                <input type="number" class="form-control" step="0.01"
                                       value="${(
        nivel.aval_porcentaje * 100
      ).toFixed(2)}"
                                       onchange="actualizarNivelLinea(${index}, 'aval_porcentaje', this.value / 100)">
                                <span class="input-group-text">%</span>
                            </div>
                        </div>
                        
                        <!-- Sección de Interpolación (colapsable) -->
                        <div class="mt-3 border-top pt-2">
                            <div class="form-check form-switch mb-2">
                                <input class="form-check-input" type="checkbox" 
                                       id="interpolacion_${index}"
                                       ${nivel.interpolacion_activa ? 'checked' : ''}
                                       onchange="toggleInterpolacionNivel(${index}, this.checked)">
                                <label class="form-check-label small" for="interpolacion_${index}">
                                    <i class="bi bi-graph-up me-1"></i>Interpolación dinámica
                                </label>
                            </div>
                            
                            <div id="interpolacion_config_${index}" 
                                 style="display: ${nivel.interpolacion_activa ? 'block' : 'none'};">
                                <div class="alert alert-info py-1 px-2 small mb-2">
                                    <i class="bi bi-info-circle me-1"></i>
                                    Configura tasa/aval en los extremos del rango. El sistema interpolará según el score.
                                </div>
                                
                                <div class="row g-1 mb-2">
                                    <div class="col-6">
                                        <label class="form-label small text-danger">Tasa en Score ${nivel.min}</label>
                                        <div class="input-group input-group-sm">
                                            <input type="number" class="form-control" step="0.01"
                                                   value="${nivel.tasa_ea_at_min || nivel.tasa_ea}"
                                                   onchange="actualizarNivelLinea(${index}, 'tasa_ea_at_min', this.value)">
                                            <span class="input-group-text">%</span>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small text-success">Tasa en Score ${nivel.max}</label>
                                        <div class="input-group input-group-sm">
                                            <input type="number" class="form-control" step="0.01"
                                                   value="${nivel.tasa_ea_at_max || nivel.tasa_ea}"
                                                   onchange="actualizarNivelLinea(${index}, 'tasa_ea_at_max', this.value)">
                                            <span class="input-group-text">%</span>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row g-1">
                                    <div class="col-6">
                                        <label class="form-label small text-danger">Aval en Score ${nivel.min}</label>
                                        <div class="input-group input-group-sm">
                                            <input type="number" class="form-control" step="0.1"
                                                   value="${((nivel.aval_at_min || nivel.aval_porcentaje) * 100).toFixed(1)}"
                                                   onchange="actualizarNivelLinea(${index}, 'aval_at_min', this.value / 100)">
                                            <span class="input-group-text">%</span>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small text-success">Aval en Score ${nivel.max}</label>
                                        <div class="input-group input-group-sm">
                                            <input type="number" class="form-control" step="0.1"
                                                   value="${((nivel.aval_at_max || nivel.aval_porcentaje) * 100).toFixed(1)}"
                                                   onchange="actualizarNivelLinea(${index}, 'aval_at_max', this.value / 100)">
                                            <span class="input-group-text">%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <label class="form-label small">Color</label>
                            <input type="color" class="form-control form-control-sm"
                                   value="${nivel.color}" style="height: 35px;"
                                   onchange="actualizarNivelLinea(${index}, 'color', this.value)">
                        </div>
                    </div>
                </div>
            </div>
        `;
  });

  html += `</div>`;

  // Botón guardar
  html += `
        <div class="mt-3 text-end">
            <button type="button" id="btnCancelarNiveles" class="btn btn-outline-secondary me-2" disabled
                    onclick="cancelarCambiosNiveles()">
                <i class="bi bi-arrow-clockwise me-1"></i>Cancelar cambios
            </button>
            <button type="button" id="btnGuardarNiveles" class="btn btn-primary" 
                    onclick="guardarNivelesRiesgoLinea()">
                <i class="bi bi-check-lg me-1"></i>Guardar niveles de riesgo
            </button>
        </div>
    `;

  container.innerHTML = html;
}

/**
 * Activa/desactiva la interpolación dinámica para un nivel
 */
function toggleInterpolacionNivel(index, activo) {
  if (!configScoringLinea || !configScoringLinea.niveles_riesgo) return;
  
  const nivel = configScoringLinea.niveles_riesgo[index];
  nivel.interpolacion_activa = activo;
  markUnsavedNivelesChanges();
  
  // Si se activa interpolación y no hay valores, inicializar con los valores actuales
  if (activo) {
    if (!nivel.tasa_ea_at_min) nivel.tasa_ea_at_min = nivel.tasa_ea;
    if (!nivel.tasa_ea_at_max) nivel.tasa_ea_at_max = nivel.tasa_ea;
    if (!nivel.aval_at_min) nivel.aval_at_min = nivel.aval_porcentaje;
    if (!nivel.aval_at_max) nivel.aval_at_max = nivel.aval_porcentaje;
  }
  
  // Mostrar/ocultar sección de configuración
  const configDiv = document.getElementById(`interpolacion_config_${index}`);
  if (configDiv) {
    configDiv.style.display = activo ? 'block' : 'none';
  }
}

/**
 * Actualiza un campo de nivel de riesgo en memoria
 */
function actualizarNivelLinea(index, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.niveles_riesgo) return;

  // Campos numéricos
  const camposNumericos = [
    "min", "max", "tasa_ea", "tasa_nominal_mensual", "aval_porcentaje",
    "tasa_ea_at_min", "tasa_ea_at_max", "aval_at_min", "aval_at_max"
  ];
  
  if (camposNumericos.includes(campo)) {
    valor = parseFloat(valor);
  }

  configScoringLinea.niveles_riesgo[index][campo] = valor;
  markUnsavedNivelesChanges();

  // Si cambió la tasa EA, calcular automáticamente la tasa nominal mensual
  if (campo === "tasa_ea") {
    const tasaEA = valor / 100; // Convertir a decimal
    // Fórmula: tasa_nominal_mensual = ((1 + tasa_ea)^(1/12) - 1) * 100
    const tasaNominalMensual = (Math.pow(1 + tasaEA, 1 / 12) - 1) * 100;
    configScoringLinea.niveles_riesgo[index].tasa_nominal_mensual = parseFloat(tasaNominalMensual.toFixed(4));
    // Re-renderizar para mostrar el nuevo valor
    renderNivelesRiesgoLinea(configScoringLinea.niveles_riesgo);
  }

  // Si cambió el color o los scores min/max, actualizar visualmente
  if (campo === "color" || campo === "min" || campo === "max") {
    renderNivelesRiesgoLinea(configScoringLinea.niveles_riesgo);
  }
}

/**
 * Agrega un nuevo nivel de riesgo
 */
function agregarNivelRiesgoLinea() {
  if (!configScoringLinea) return;

  if (!configScoringLinea.niveles_riesgo) {
    configScoringLinea.niveles_riesgo = [];
  }

  // Determinar valores por defecto para el nuevo nivel
  const numNiveles = configScoringLinea.niveles_riesgo.length;
  const colores = ["#28a745", "#ffc107", "#fd7e14", "#dc3545", "#6c757d"];
  const nombres = ["Bajo Riesgo", "Moderado", "Alto Riesgo", "Muy Alto Riesgo", "Nivel " + (numNiveles + 1)];

  const nuevoNivel = {
    nombre: nombres[numNiveles] || "Nivel " + (numNiveles + 1),
    min: 0,
    max: 100,
    tasa_ea: 30,
    tasa_nominal_mensual: 2.21,
    aval_porcentaje: 0.10,
    color: colores[numNiveles] || "#6c757d"
  };

  configScoringLinea.niveles_riesgo.push(nuevoNivel);
  renderNivelesRiesgoLinea(configScoringLinea.niveles_riesgo);
  markUnsavedNivelesChanges();
  mostrarAlertaScoring("Nuevo nivel agregado. No olvide guardar los cambios.", "info");
}

/**
 * Elimina un nivel de riesgo
 */
function eliminarNivelRiesgoLinea(index) {
  if (!configScoringLinea || !configScoringLinea.niveles_riesgo) return;

  if (configScoringLinea.niveles_riesgo.length <= 1) {
    mostrarAlertaScoring("Debe mantener al menos un nivel de riesgo.", "warning");
    return;
  }

  const nivel = configScoringLinea.niveles_riesgo[index];
  if (confirm(`¿Está seguro de eliminar el nivel "${nivel.nombre}"?`)) {
    configScoringLinea.niveles_riesgo.splice(index, 1);
    renderNivelesRiesgoLinea(configScoringLinea.niveles_riesgo);
    markUnsavedNivelesChanges();
    mostrarAlertaScoring("Nivel eliminado. No olvide guardar los cambios.", "info");
  }
}

/**
 * Guarda los niveles de riesgo de la línea
 */
async function guardarNivelesRiesgoLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  try {
    const response = await fetchConCSRF(
      `/api/scoring/linea/${lineaSeleccionadaId}/niveles-riesgo`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          niveles: configScoringLinea.niveles_riesgo,
        }),
      }
    );

    const data = await response.json();

    if (data.success) {
      unsavedNivelesChanges = false;
      updateNivelesButtonState();
      mostrarAlertaScoring(
        "Niveles de riesgo guardados exitosamente",
        "success"
      );
    } else {
      mostrarAlertaScoring(`Error: ${data.error}`, "danger");
    }
  } catch (error) {
    console.error("Error guardando niveles:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  }
}

/**
 * Crea niveles de riesgo por defecto para la línea
 */
async function crearNivelesRiesgoPorDefecto() {
  configScoringLinea.niveles_riesgo = [
    {
      nombre: "Bajo riesgo",
      codigo: "BAJO",
      min: 70.1,
      max: 100,
      tasa_ea: 22.0,
      tasa_nominal_mensual: 1.67,
      aval_porcentaje: 0.05,
      color: "#2ECC40",
      orden: 1,
    },
    {
      nombre: "Riesgo moderado",
      codigo: "MODERADO",
      min: 40.1,
      max: 70,
      tasa_ea: 24.0,
      tasa_nominal_mensual: 1.81,
      aval_porcentaje: 0.1,
      color: "#FFDC00",
      orden: 2,
    },
    {
      nombre: "Alto riesgo",
      codigo: "ALTO",
      min: 0,
      max: 40,
      tasa_ea: 30.0,
      tasa_nominal_mensual: 2.21,
      aval_porcentaje: 0.15,
      color: "#FF4136",
      orden: 3,
    },
  ];

  renderNivelesRiesgoLinea(configScoringLinea.niveles_riesgo);
  mostrarAlertaScoring(
    "Niveles por defecto creados. Recuerde guardar los cambios.",
    "info"
  );
}

// ============================================================================
// RENDERIZADO DE FACTORES DE RECHAZO (v3.1 - Solo Criterios de Scoring + Personalizado)
// ============================================================================

/**
 * Genera las opciones del dropdown para criterios de factores de rechazo
 * Solo muestra: Criterios de Scoring de la línea activa + Personalizado
 */
/**
 * Busca un criterio en configScoringLinea.criterios por índice numérico o por codigo slug
 */
function buscarCriterioEnLinea(criterioId) {
  if (!configScoringLinea || !configScoringLinea.criterios) return null;
  // Intentar por índice numérico
  const idx = parseInt(criterioId);
  if (!isNaN(idx) && configScoringLinea.criterios[idx]) {
    return configScoringLinea.criterios[idx];
  }
  if (typeof criterioId === 'string' && criterioId !== '') {
    // Intentar por codigo exacto
    const porCodigo = configScoringLinea.criterios.find(c => c.codigo === criterioId);
    if (porCodigo) return porCodigo;
    // Intentar por nombre exacto (criterio_nombre guardado)
    const porNombre = configScoringLinea.criterios.find(c => c.nombre === criterioId);
    if (porNombre) return porNombre;
    // Intentar por slug derivado del nombre (ej: "validacion_identidad_estado" vs "Validacion Identidad, Estado.")
    const slugBuscar = criterioId.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '');
    const porSlug = configScoringLinea.criterios.find(c => {
      const slugNombre = (c.nombre || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '');
      return slugNombre === slugBuscar;
    });
    if (porSlug) return porSlug;
  }
  return null;
}

function generarOpcionesCriteriosFactores(criterioSeleccionado) {
  let html = '';
  const nombreLinea = lineaSeleccionadaNombre || 'Línea actual';
  let existeEnScoring = false;
  
  // Grupo 1: Criterios de Scoring de la línea actual
  if (configScoringLinea && configScoringLinea.criterios) {
    const criteriosScoring = Object.entries(configScoringLinea.criterios);
    if (criteriosScoring.length > 0) {
      // Ordenar alfabéticamente por nombre (A-Z)
      const criteriosOrdenados = [...criteriosScoring].sort((a, b) => {
        const nombreA = (a[1].nombre || a[0]).toLowerCase();
        const nombreB = (b[1].nombre || b[0]).toLowerCase();
        return nombreA.localeCompare(nombreB, 'es');
      });
      html += `<optgroup label="── CRITERIOS SCORING [${nombreLinea}] ──">`;
      // Pre-calcular slug del criterio seleccionado para matching por nombre
      const slugSeleccionado = criterioSeleccionado ? criterioSeleccionado.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '') : '';
      criteriosOrdenados.forEach(([id, c]) => {
        const codigoCriterio = c.codigo || '';
        const slugNombre = (c.nombre || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+$/, '');
        // Matching: comparar por codigo (principal), luego por índice, nombre, o slug
        const isSelected = (codigoCriterio && criterioSeleccionado === codigoCriterio) ||
                           criterioSeleccionado === id ||
                           criterioSeleccionado === String(id) ||
                           criterioSeleccionado === (c.nombre || id) ||
                           (slugSeleccionado && slugNombre && slugSeleccionado === slugNombre);
        if (isSelected) existeEnScoring = true;
        const selected = isSelected ? 'selected' : '';
        // Usar codigo del criterio como value (no el índice del array)
        const optionValue = codigoCriterio || id;
        html += `<option value="${optionValue}" data-nombre="${c.nombre || id}" data-source="scoring" data-codigo="${codigoCriterio}" ${selected}>${c.nombre || id}</option>`;
      });
      html += '</optgroup>';
    }
  }
  
  // Si no hay criterios de scoring configurados, mostrar mensaje informativo
  if (!configScoringLinea || !configScoringLinea.criterios || Object.keys(configScoringLinea.criterios).length === 0) {
    html += `<optgroup label="── CRITERIOS SCORING [${nombreLinea}] ──">`;
    html += `<option value="" disabled>(No hay criterios configurados - cree criterios en la pestaña "Criterios de Scoring")</option>`;
    html += '</optgroup>';
  }
  
  // Grupo 2: Opción Personalizado
  // Seleccionar Personalizado si: explícitamente es __personalizado__ O si el criterio no existe en scoring
  html += '<optgroup label="── OTRO ──">';
  const esPersonalizado = criterioSeleccionado === '__personalizado__' || 
    (criterioSeleccionado && criterioSeleccionado !== '' && !existeEnScoring);
  const customSelected = esPersonalizado ? 'selected' : '';
  html += `<option value="__personalizado__" ${customSelected}>+ Personalizado...</option>`;
  html += '</optgroup>';
  
  return html;
}

/**
 * Renderiza los factores de rechazo para la línea seleccionada
 */
/**
 * Obtiene info de un criterio de scoring por su índice en configScoringLinea.criterios
 * Retorna {nombre, tipo_campo, rangos, esCompuesto} o null
 */
function obtenerInfoCriterioScoring(criterioId) {
  if (!configScoringLinea || !configScoringLinea.criterios) return null;
  const criterio = buscarCriterioEnLinea(criterioId);
  if (!criterio) return null;
  return {
    nombre: criterio.nombre || criterioId,
    tipo_campo: criterio.tipo_campo || 'number',
    rangos: criterio.rangos || [],
    esCompuesto: criterio.tipo_campo === 'composite'
  };
}

/**
 * Genera HTML del campo operador/valor según si el criterio es compuesto o numérico.
 * Si es compuesto: muestra un select con las descripciones de los rangos del criterio
 * Si es numérico: muestra operador + valor tradicional
 */
function generarCampoOperadorValor(factor, index) {
  const criterioId = factor.criterio || '';
  const infoCriterio = obtenerInfoCriterioScoring(criterioId);

  if (infoCriterio && infoCriterio.esCompuesto && infoCriterio.rangos.length > 0) {
    // Criterio compuesto: mostrar select con descripciones de rangos
    let optsHtml = '<option value="">-- Seleccione condición --</option>';
    infoCriterio.rangos.forEach(rango => {
      const desc = rango.descripcion || rango.etiqueta || `${rango.min}-${rango.max}`;
      const val = rango.puntos !== undefined ? rango.puntos : rango.min;
      const sel = String(factor.valor) === String(val) ? 'selected' : '';
      optsHtml += `<option value="${val}" ${sel}>${desc} (${rango.puntos} pts)</option>`;
    });
    return `
      <div class="col-4">
        <label class="form-label small mb-1">Condición (desplegable)</label>
        <select class="form-select form-select-sm border-info" 
                onchange="actualizarFactorLinea(${index}, 'valor', this.value); actualizarFactorLinea(${index}, 'operador', '=')">
          ${optsHtml}
        </select>
        <small class="text-info"><i class="bi bi-list-ul me-1"></i>Criterio compuesto</small>
      </div>
      <div class="col-4">
        <label class="form-label small mb-1">Mensaje</label>
        <div class="input-group input-group-sm">
          <input type="text" class="form-control factor-mensaje-input" data-index="${index}"
                 value="${factor.mensaje || ''}" onchange="actualizarFactorLinea(${index}, 'mensaje', this.value)">
          <button type="button" class="btn btn-outline-secondary" onclick="sugerirMensajeFactorLinea(${index})" title="Sugerir">
            <i class="bi bi-magic"></i>
          </button>
        </div>
      </div>`;
  }

  // Numérico: operador + valor + mensaje
  return `
    <div class="col-2">
      <label class="form-label small mb-1">Operador</label>
      <select class="form-select form-select-sm" onchange="actualizarFactorLinea(${index}, 'operador', this.value)">
        <option value="<" ${factor.operador === "<" ? "selected" : ""}>< menor</option>
        <option value="<=" ${factor.operador === "<=" ? "selected" : ""}>≤</option>
        <option value=">" ${factor.operador === ">" ? "selected" : ""}>> mayor</option>
        <option value=">=" ${factor.operador === ">=" ? "selected" : ""}>≥</option>
        <option value="=" ${factor.operador === "=" ? "selected" : ""}>=</option>
      </select>
    </div>
    <div class="col-2">
      <label class="form-label small mb-1">Valor</label>
      <input type="number" class="form-control form-control-sm" value="${factor.valor}"
             onchange="actualizarFactorLinea(${index}, 'valor', this.value)">
    </div>
    <div class="col-4">
      <label class="form-label small mb-1">Mensaje</label>
      <div class="input-group input-group-sm">
        <input type="text" class="form-control factor-mensaje-input" data-index="${index}"
               value="${factor.mensaje || ''}" onchange="actualizarFactorLinea(${index}, 'mensaje', this.value)">
        <button type="button" class="btn btn-outline-secondary" onclick="sugerirMensajeFactorLinea(${index})" title="Sugerir">
          <i class="bi bi-magic"></i>
        </button>
      </div>
    </div>`;
}

/**
 * Abre modal para confirmar cambio de tipo de un factor existente
 */
function cambiarTipoFactor(index) {
  if (!configScoringLinea?.factores_rechazo?.[index]) return;
  const factor = configScoringLinea.factores_rechazo[index];
  const tipoActual = factor.tipo_factor || 'numerico';
  
  // Resolver nombre real del criterio vinculado (por índice o por codigo slug)
  let nombreFactor = factor.criterio_nombre || factor.criterio || 'Factor ' + (index + 1);
  let esCompuestoVinculado = false;
  if (tipoActual === 'numerico' && configScoringLinea?.criterios) {
    const criterioRef = buscarCriterioEnLinea(factor.criterio);
    if (criterioRef) {
      nombreFactor = criterioRef.nombre || nombreFactor;
      esCompuestoVinculado = criterioRef.tipo_campo === 'composite' || criterioRef.tipo_campo === 'select';
    }
  }
  
  // Tipo efectivo: si es numérico pero vinculado a compuesto, funciona como selección
  const tipoEfectivo = (tipoActual === 'seleccion' || esCompuestoVinculado) ? 'seleccion' : 'numerico';
  const tipoNuevo = tipoEfectivo === 'numerico' ? 'Selección (Desplegable)' : 'Numérico';
  const tipoEfectivoLabel = tipoEfectivo === 'seleccion' ? 'Selección' : 'Numérico';

  const modalId = 'modalCambiarTipoFactor';
  const oldModal = document.getElementById(modalId);
  if (oldModal) oldModal.remove();

  let infoCompuesto = '';
  if (esCompuestoVinculado && tipoActual === 'numerico') {
    infoCompuesto = `<div class="alert alert-info mt-2 py-1 px-2 small mb-0">
      <i class="bi bi-info-circle me-1"></i>Este factor está vinculado a un criterio compuesto, por lo que ya funciona como selección.
    </div>`;
  }

  const modalHtml = `
    <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header bg-warning text-dark py-2">
            <h6 class="modal-title"><i class="bi bi-arrow-repeat me-2"></i>Cambiar Tipo de Factor</h6>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <p class="mb-2">Factor: <strong>${nombreFactor}</strong></p>
            <p class="mb-2">Tipo actual: <span class="badge ${tipoEfectivo === 'seleccion' ? 'bg-info text-dark' : 'bg-secondary'}">${tipoEfectivoLabel}</span></p>
            <p class="mb-0">Cambiar a: <span class="badge ${tipoEfectivo === 'seleccion' ? 'bg-secondary' : 'bg-info text-dark'}">${tipoNuevo}</span></p>
            ${infoCompuesto}
            <div class="alert alert-warning mt-2 py-1 px-2 small mb-0">
              <i class="bi bi-exclamation-triangle me-1"></i>Esta acción puede modificar la estructura del factor. Recuerde guardar después.
            </div>
          </div>
          <div class="modal-footer p-1">
            <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-sm btn-warning" onclick="confirmarCambioTipoFactor(${index}, '${modalId}')">
              <i class="bi bi-check-lg me-1"></i>Confirmar Cambio
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
  new bootstrap.Modal(document.getElementById(modalId)).show();
}

/**
 * Ejecuta el cambio de tipo tras confirmación del modal
 */
function confirmarCambioTipoFactor(index, modalId) {
  const modalEl = document.getElementById(modalId);
  if (modalEl) {
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  }

  if (!configScoringLinea?.factores_rechazo?.[index]) return;
  const factor = configScoringLinea.factores_rechazo[index];
  const tipoActual = factor.tipo_factor || 'numerico';

  // Determinar tipo EFECTIVO (mismo cálculo que en cambiarTipoFactor)
  let esCompuestoVinculado = false;
  if (tipoActual === 'numerico' && configScoringLinea?.criterios) {
    const criterioRef = buscarCriterioEnLinea(factor.criterio);
    if (criterioRef) {
      esCompuestoVinculado = criterioRef.tipo_campo === 'composite' || criterioRef.tipo_campo === 'select';
    }
  }
  const tipoEfectivo = (tipoActual === 'seleccion' || esCompuestoVinculado) ? 'seleccion' : 'numerico';

  if (tipoEfectivo === 'numerico') {
    factor.tipo_factor = 'seleccion';
    if (!factor.opciones || factor.opciones.length === 0) {
      factor.opciones = [
        { valor: '', etiqueta: '', rechaza: true, mensaje: '' }
      ];
    }
  } else {
    factor.tipo_factor = 'numerico';
    factor.operador = factor.operador || '<';
    factor.valor = factor.valor || 0;
  }

  renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  markUnsavedAprobacionChanges();
  mostrarAlertaScoring('Tipo de factor cambiado. Recuerde guardar.', 'info');
}

function renderFactoresRechazoLinea(factores) {
  const container = document.getElementById("factoresRechazoLineaContainer");
  if (!container) return;

  let html = `
        <div class="mb-3 d-flex justify-content-between align-items-center">
            <h6 class="mb-0">
                <i class="bi bi-shield-x me-2"></i>Factores de rechazo automático 
                <span class="badge bg-secondary">${factores?.length || 0}</span>
            </h6>
            <div class="d-flex align-items-center gap-2">
                <span class="text-muted small fw-bold">Crear criterio tipo:</span>
                <div class="btn-group btn-group-sm">
                    <button type="button" class="btn btn-outline-primary" 
                            onclick="agregarFactorRechazoLinea()">
                        <i class="bi bi-123 me-1"></i>Numérico
                    </button>
                    <button type="button" class="btn btn-outline-info" 
                            onclick="agregarFactorRechazoLinea('seleccion')">
                        <i class="bi bi-list-ul me-1"></i>Selección
                    </button>
                </div>
            </div>
        </div>
    `;

  if (!factores || factores.length === 0) {
    html += `
            <div id="factoresRechazoSortable">
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i>
                No hay factores de rechazo configurados para esta línea.
            </div>
            </div>
        `;
  } else {
    html += `<div id="factoresRechazoSortable">`;
    factores.forEach((factor, index) => {
      const tipoFactor = factor.tipo_factor || 'numerico';
      const criterioActual = factor.criterio || factor.criterio_nombre || '';
      const esPersonalizado = factor.tipo_criterio === 'personalizado' || criterioActual === '__personalizado__';
      
      // Resolver nombre real del criterio vinculado (por índice o por codigo slug)
      let nombreMostrar = factor.criterio_nombre || criterioActual || 'Factor ' + (index + 1);
      let esCompuestoVinculado = false;
      if (!esPersonalizado && configScoringLinea?.criterios) {
        const criterioRef = buscarCriterioEnLinea(criterioActual);
        if (criterioRef) {
          nombreMostrar = criterioRef.nombre || nombreMostrar;
          // Sincronizar criterio_nombre con el nombre real
          factor.criterio_nombre = nombreMostrar;
          esCompuestoVinculado = criterioRef.tipo_campo === 'composite' || criterioRef.tipo_campo === 'select';
        }
      }
      
      let badgeTipo;
      if (tipoFactor === 'seleccion') {
        badgeTipo = '<span class="badge bg-info text-dark me-1"><i class="bi bi-list-ul me-1"></i>Selección</span>';
      } else if (esCompuestoVinculado) {
        badgeTipo = '<span class="badge bg-info text-dark me-1"><i class="bi bi-list-ul me-1"></i>Selección</span>';
      } else {
        badgeTipo = '<span class="badge bg-secondary me-1"><i class="bi bi-123 me-1"></i>Numérico</span>';
      }
      
      // Botón para cambiar tipo (izquierda del eliminar)
      const tipoOpuesto = tipoFactor === 'seleccion' ? 'Numérico' : 'Selección';
      const iconoOpuesto = tipoFactor === 'seleccion' ? 'bi-123' : 'bi-list-ul';
      
      // Color del borde según tipo efectivo
      const borderClass = (tipoFactor === 'seleccion' || esCompuestoVinculado) ? 'border-info' : 'border-secondary';
      
      html += `<div class="card mb-2 border-start border-3 ${borderClass}" data-factor-index="${index}">
        <div class="card-body p-2">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <div class="d-flex align-items-center gap-2">
              <span class="factor-handle me-1" style="cursor: grab;" title="Arrastrar para reordenar">
                <i class="bi bi-grip-vertical text-muted"></i>
              </span>
              ${badgeTipo}
              <strong class="small">${nombreMostrar}</strong>
            </div>
            <div class="btn-group btn-group-sm">
              <button type="button" class="btn btn-outline-warning" onclick="cambiarTipoFactor(${index})" title="Editar tipo (cambiar a ${tipoOpuesto})">
                <i class="bi bi-pencil me-1"></i><small>Tipo</small>
              </button>
              <button type="button" class="btn btn-outline-danger" onclick="eliminarFactorLinea(${index})" title="Eliminar">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>`;
      
      if (tipoFactor === 'seleccion') {
        // ---- FACTOR TIPO SELECCIÓN (criterio único por factor) ----
        html += `
          <div class="row g-2 mb-2">
            <div class="col-6">
              <label class="form-label small mb-1">Criterio</label>
              <select class="form-select form-select-sm factor-criterio-select" data-index="${index}"
                      onchange="onCambiarCriterioLinea(this, ${index})">
                ${generarOpcionesCriteriosFactores(criterioActual)}
              </select>
              <input type="text" class="form-control form-control-sm mt-1 factor-custom-input" data-index="${index}"
                     value="${factor.criterio_personalizado || (esPersonalizado ? factor.criterio_nombre : '')}"
                     placeholder="Nombre del criterio personalizado"
                     onchange="actualizarFactorLinea(${index}, 'criterio_personalizado', this.value)"
                     style="display: ${esPersonalizado ? 'block' : 'none'};">
            </div>
            <div class="col-6 d-flex align-items-end">
              <small class="text-muted">El criterio seleccionado aplica a todas las filas de condición.</small>
            </div>
          </div>
          <label class="form-label small mb-1">Condiciones de rechazo 
            <button type="button" class="btn btn-sm btn-outline-primary py-0 px-1" onclick="agregarCondicionRechazo(${index})" title="Agregar condición">
              <i class="bi bi-plus"></i>
            </button>
          </label>
          <div class="table-responsive">
            <table class="table table-sm table-bordered mb-0">
              <thead class="table-light">
                <tr>
                  <th style="width:45%">Condición (desplegable)</th>
                  <th style="width:32%">Mensaje</th>
                  <th style="width:10%" class="text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>`;
        
        const opciones = factor.opciones || [];
        const criterioInfoFactor = obtenerInfoCriterioScoring(criterioActual);
        opciones.forEach((op, opIdx) => {
          // Generar dropdown de condición usando sólo el criterio activo del factor
          let condicionHtml = '<option value="">-- Seleccione condición --</option>';
          if (criterioInfoFactor && criterioInfoFactor.rangos && criterioInfoFactor.rangos.length > 0) {
            criterioInfoFactor.rangos.forEach(rango => {
              const desc = rango.descripcion || rango.etiqueta || `${rango.min}-${rango.max}`;
              const val = rango.puntos !== undefined ? rango.puntos : rango.min;
              const sel = String(op.valor) === String(val) ? 'selected' : '';
              condicionHtml += `<option value="${val}" ${sel}>${desc} (${rango.puntos} pts)</option>`;
            });
          }
          const tieneRangos = criterioInfoFactor && criterioInfoFactor.rangos && criterioInfoFactor.rangos.length > 0;
          
          html += `
                <tr>
                  <td>
                    <select class="form-select form-select-sm ${tieneRangos ? 'border-info' : ''}" 
                            onchange="actualizarCondicionRechazo(${index}, ${opIdx}, this)">
                      ${condicionHtml}
                    </select>
                    ${tieneRangos ? '<small class="text-info"><i class="bi bi-list-ul me-1"></i>Criterio compuesto</small>' : '<small class="text-muted">Seleccione criterio</small>'}
                  </td>
                  <td>
                    <div class="input-group input-group-sm">
                      <input type="text" class="form-control" value="${op.mensaje || ''}" 
                             onchange="actualizarOpcionFactor(${index}, ${opIdx}, 'mensaje', this.value)">
                      <button type="button" class="btn btn-outline-secondary" 
                              onclick="sugerirMensajeCondicion(${index}, ${opIdx})" title="Sugerir mensaje">
                        <i class="bi bi-magic"></i>
                      </button>
                    </div>
                  </td>
                  <td class="text-center">
                    <button type="button" class="btn btn-sm btn-outline-danger py-0" 
                            onclick="eliminarCondicionRechazo(${index}, ${opIdx})">
                      <i class="bi bi-trash"></i>
                    </button>
                  </td>
                </tr>`;
        });
        
        html += `</tbody></table></div>`;
      } else {
        // ---- FACTOR TIPO NUMÉRICO ----
        html += `
          <div class="row g-2">
            <div class="col-4">
              <label class="form-label small mb-1">Criterio</label>
              <select class="form-select form-select-sm factor-criterio-select" data-index="${index}"
                      onchange="onCambiarCriterioLinea(this, ${index})">
                ${generarOpcionesCriteriosFactores(criterioActual)}
              </select>
              <input type="text" class="form-control form-control-sm mt-1 factor-custom-input" data-index="${index}"
                     value="${factor.criterio_personalizado || (esPersonalizado ? factor.criterio_nombre : '')}"
                     placeholder="Criterio personalizado"
                     onchange="actualizarFactorLinea(${index}, 'criterio_personalizado', this.value)"
                     style="display: ${esPersonalizado ? 'block' : 'none'};">
            </div>
            ${generarCampoOperadorValor(factor, index)}
          </div>`;
      }
      
      html += `</div></div>`;
    });
    html += `</div>`;
  }

  container.innerHTML = html;
  
  // Inicializar drag & drop para factores de rechazo
  initSortableFactoresRechazo();
}

/**
 * Inicializa Sortable.js para reordenar factores de rechazo con drag & drop
 */
function initSortableFactoresRechazo() {
  const container = document.getElementById('factoresRechazoSortable');
  if (!container || typeof Sortable === 'undefined') return;
  
  // Destruir instancia anterior si existe
  if (container._sortable) {
    container._sortable.destroy();
  }
  
  container._sortable = Sortable.create(container, {
    handle: '.factor-handle',
    animation: 150,
    ghostClass: 'sortable-ghost',
    chosenClass: 'sortable-chosen',
    scroll: false,  // Desactivar scroll automático
    scrollSensitivity: 30,  // Reducir sensibilidad del scroll
    scrollSpeed: 10,  // Reducir velocidad del scroll
    bubbleScroll: false,  // Evitar que el scroll suba por los padres
    onEnd: function (evt) {
      if (evt.oldIndex === evt.newIndex) return;
      if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;
      
      // Reordenar el array en memoria según el nuevo orden del DOM
      const factores = configScoringLinea.factores_rechazo;
      const [movedItem] = factores.splice(evt.oldIndex, 1);
      factores.splice(evt.newIndex, 0, movedItem);
      
      // Re-renderizar para actualizar los índices de onclick
      renderFactoresRechazoLinea(factores);
      markUnsavedAprobacionChanges();
    }
  });
}

// Funciones auxiliares para opciones/condiciones de factores tipo selección

/**
 * Agrega una nueva condición de rechazo a un factor tipo selección
 */
function agregarCondicionRechazo(factorIndex) {
  if (!configScoringLinea?.factores_rechazo?.[factorIndex]) return;
  if (!configScoringLinea.factores_rechazo[factorIndex].opciones) {
    configScoringLinea.factores_rechazo[factorIndex].opciones = [];
  }
  // Nueva condición vacía usando el criterio activo del factor
  configScoringLinea.factores_rechazo[factorIndex].opciones.push({
    valor: '',
    etiqueta: '',
    rechaza: true,
    mensaje: ''
  });
  renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  markUnsavedAprobacionChanges();
}

/**
 * Actualiza el valor de condición seleccionado en una fila de rechazo
 */
function actualizarCondicionRechazo(factorIndex, opcionIndex, select) {
  if (!configScoringLinea?.factores_rechazo?.[factorIndex]?.opciones?.[opcionIndex]) return;
  
  const valor = select.value;
  const etiqueta = select.options[select.selectedIndex]?.textContent || '';
  
  const opcion = configScoringLinea.factores_rechazo[factorIndex].opciones[opcionIndex];
  opcion.valor = valor;
  opcion.etiqueta = etiqueta;
  opcion.operador = '=';
  
  markUnsavedAprobacionChanges();
}

/**
 * Elimina una condición de rechazo de un factor tipo selección
 */
function eliminarCondicionRechazo(factorIndex, opcionIndex) {
  if (!configScoringLinea?.factores_rechazo?.[factorIndex]?.opciones) return;
  configScoringLinea.factores_rechazo[factorIndex].opciones.splice(opcionIndex, 1);
  renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  markUnsavedAprobacionChanges();
}

/**
 * Sugiere un mensaje de rechazo basado en el criterio y condición de una fila
 */
function sugerirMensajeCondicion(factorIndex, opcionIndex) {
  if (!configScoringLinea?.factores_rechazo?.[factorIndex]?.opciones?.[opcionIndex]) return;
  
  const factor = configScoringLinea.factores_rechazo[factorIndex];
  const opcion = configScoringLinea.factores_rechazo[factorIndex].opciones[opcionIndex];
  const nombreCriterio = factor.criterio_nombre || 'Criterio';
  const etiqueta = opcion.etiqueta || opcion.valor || '';
  
  const mensajeSugerido = etiqueta 
    ? `Rechazo: ${nombreCriterio} - ${etiqueta}`
    : `Rechazo por ${nombreCriterio}`;
  
  opcion.mensaje = mensajeSugerido;
  renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  markUnsavedAprobacionChanges();
}

/**
 * Actualiza un campo de una opción de factor (compatible con ambos formatos)
 */
function actualizarOpcionFactor(factorIndex, opcionIndex, campo, valor) {
  if (!configScoringLinea?.factores_rechazo?.[factorIndex]?.opciones?.[opcionIndex]) return;
  configScoringLinea.factores_rechazo[factorIndex].opciones[opcionIndex][campo] = valor;
  markUnsavedAprobacionChanges();
}

/**
 * Compatibilidad: agregarOpcionFactor redirige a agregarCondicionRechazo
 */
function agregarOpcionFactor(factorIndex) {
  agregarCondicionRechazo(factorIndex);
}

/**
 * Compatibilidad: eliminarOpcionFactor redirige a eliminarCondicionRechazo
 */
function eliminarOpcionFactor(factorIndex, opcionIndex) {
  eliminarCondicionRechazo(factorIndex, opcionIndex);
}

/**
 * Maneja el cambio de criterio en el dropdown híbrido
 */
function onCambiarCriterioLinea(select, index) {
  const valor = select.value;
  const customInput = document.querySelector(`.factor-custom-input[data-index="${index}"]`);
  
  if (valor === '__personalizado__') {
    if (customInput) {
      customInput.style.display = 'block';
      customInput.focus();
    }
    configScoringLinea.factores_rechazo[index].tipo_criterio = 'personalizado';
    configScoringLinea.factores_rechazo[index].criterio = '__personalizado__';
  } else {
    if (customInput) {
      customInput.style.display = 'none';
      customInput.value = '';
    }
    
    // Obtener nombre y codigo del criterio seleccionado
    const option = select.options[select.selectedIndex];
    const nombreCriterio = option.dataset.nombre || option.textContent;
    const codigoCriterio = option.dataset.codigo || '';
    
    // Guardar codigo slug si existe, sino el valor numérico (índice)
    configScoringLinea.factores_rechazo[index].criterio = codigoCriterio || valor;
    configScoringLinea.factores_rechazo[index].criterio_nombre = nombreCriterio;
    configScoringLinea.factores_rechazo[index].tipo_criterio = 'scoring';
    configScoringLinea.factores_rechazo[index].criterio_personalizado = '';
    
    // Si es factor tipo selección, cargar rangos del criterio scoring como opciones
    const factor = configScoringLinea.factores_rechazo[index];
    if (factor.tipo_factor === 'seleccion') {
      const infoCriterio = obtenerInfoCriterioScoring(codigoCriterio || valor);
      if (infoCriterio && infoCriterio.rangos && infoCriterio.rangos.length > 0) {
        // Reiniciar filas de condición para que usen el nuevo criterio activo
        factor.opciones = [{ valor: '', etiqueta: '', rechaza: true, mensaje: '' }];
        console.log(`✅ Opciones cargadas desde criterio scoring "${nombreCriterio}":`, factor.opciones.length);
      } else {
        factor.opciones = [{ valor: '', etiqueta: '', rechaza: true, mensaje: '' }];
      }
    }
    
    // Re-renderizar para actualizar operador inteligente (compuesto vs numérico)
    renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  }
  
  markUnsavedAprobacionChanges();
}

/**
 * Sugiere un mensaje de rechazo basado en el criterio seleccionado
 */
function sugerirMensajeFactorLinea(index) {
  const factor = configScoringLinea?.factores_rechazo?.[index];
  if (!factor) return;
  
  const criterioId = factor.criterio;
  const operador = factor.operador || '<';
  const valor = factor.valor || 0;
  
  const opTexto = {
    '<': 'menor que',
    '<=': 'menor o igual a',
    '>': 'mayor que',
    '>=': 'mayor o igual a',
    '=': 'igual a'
  }[operador] || operador;
  
  let mensaje = '';
  
  if (criterioId === '__personalizado__') {
    const customName = factor.criterio_personalizado || 'Criterio';
    mensaje = `${customName} ${opTexto} {valor}`;
  } else {
    // Buscar en criterios de scoring de la línea activa (por índice o codigo slug)
    let nombreCriterio = factor.criterio_nombre || criterioId;
    if (configScoringLinea && configScoringLinea.criterios) {
      const criterioEnLinea = buscarCriterioEnLinea(criterioId);
      if (criterioEnLinea) {
        nombreCriterio = criterioEnLinea.nombre || nombreCriterio;
      }
    }
    mensaje = `${nombreCriterio} ${opTexto} {valor}`;
  }
  
  // Actualizar el campo de mensaje
  const mensajeInput = document.querySelector(`.factor-mensaje-input[data-index="${index}"]`);
  if (mensajeInput) {
    mensajeInput.value = mensaje;
    factor.mensaje = mensaje;
    markUnsavedAprobacionChanges();
  }
}

// NOTA: Las funciones actualizarFactorLinea, agregarFactorRechazoLinea y eliminarFactorLinea
// están definidas más abajo en la sección de CONFIGURACIÓN DE APROBACIÓN

/**
 * Guarda los factores de rechazo de la línea
 */
async function guardarFactoresRechazoLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  try {
    const response = await fetchConCSRF(
      `/api/scoring/linea/${lineaSeleccionadaId}/factores-rechazo`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          factores: configScoringLinea.factores_rechazo,
        }),
      }
    );

    const data = await response.json();

    if (data.success) {
      mostrarAlertaScoring(
        "Factores de rechazo guardados exitosamente",
        "success"
      );
    } else {
      mostrarAlertaScoring(`Error: ${data.error}`, "danger");
    }
  } catch (error) {
    console.error("Error guardando factores:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  }
}

/**
 * Agrega un nuevo factor de rechazo en la pestaña de aprobación
 */
function agregarFactorRechazoLinea(tipo = 'numerico') {
  if (!configScoringLinea) return;

  if (!configScoringLinea.factores_rechazo) {
    configScoringLinea.factores_rechazo = [];
  }

  if (tipo === 'seleccion') {
    configScoringLinea.factores_rechazo.push({
      criterio_nombre: "Nuevo Factor Selección",
      criterio: "nuevo_factor_seleccion",
      tipo_factor: "seleccion",
      operador: "=",
      valor: 0,
      mensaje: "",
      opciones: [
        { valor: '', etiqueta: '', rechaza: true, mensaje: '' }
      ]
    });
  } else {
    configScoringLinea.factores_rechazo.push({
      criterio_nombre: "Nuevo Factor",
      criterio: "nuevo_factor",
      tipo_factor: "numerico",
      operador: "<",
      valor: 0,
      mensaje: `Valor {valor} no cumple con el criterio`
    });
  }

  // Índice del nuevo factor para hacer scroll
  const nuevoIndex = configScoringLinea.factores_rechazo.length - 1;

  renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  markUnsavedAprobacionChanges();
  mostrarAlertaScoring(`Factor ${tipo === 'seleccion' ? 'de selección' : 'numérico'} agregado. Recuerde guardar.`, "info");

  // Auto-scroll al nuevo factor creado
  setTimeout(() => {
    const nuevoFactorEl = document.querySelector(`[data-factor-index="${nuevoIndex}"]`);
    if (nuevoFactorEl) {
      nuevoFactorEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Resaltar brevemente el nuevo factor
      nuevoFactorEl.classList.add('border-warning', 'shadow');
      setTimeout(() => {
        nuevoFactorEl.classList.remove('border-warning', 'shadow');
      }, 2000);
    }
  }, 100);
}

/**
 * Actualiza un factor de rechazo en memoria
 * Si el campo es 'valor', también actualiza el placeholder {valor} en el mensaje
 */
function actualizarFactorLinea(index, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;

  if (campo === 'valor') {
    if (valor === '' || valor === null || valor === undefined) {
      valor = '';
    } else {
      const valorNumerico = parseFloat(valor);
      valor = Number.isNaN(valorNumerico) ? '' : valorNumerico;
    }
    // Actualizar placeholder {valor} en el mensaje automáticamente
    const factor = configScoringLinea.factores_rechazo[index];
    if (factor && factor.mensaje && factor.mensaje.includes('{valor}')) {
      // El mensaje ya tiene el placeholder, se resolverá al mostrar
    }
  }

  configScoringLinea.factores_rechazo[index][campo] = valor;

  // Si se actualiza el nombre personalizado, sincronizar criterio_nombre y re-renderizar
  if (campo === 'criterio_personalizado' && valor) {
    configScoringLinea.factores_rechazo[index].criterio_nombre = valor;
    
    // Validar si el criterio personalizado existe (async)
    validarCriterioPersonalizado(valor, index).then(() => {
      renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
    });
  }

  markUnsavedAprobacionChanges();
}

/**
 * Valida si un criterio personalizado existe en el scoring de la línea o en criterios del sistema
 */
async function validarCriterioPersonalizado(nombreCriterio, index) {
  if (!nombreCriterio || !configScoringLinea) return;
  
  // 1. Buscar en criterios de scoring de la línea
  let existeEnScoring = false;
  if (configScoringLinea.criterios) {
    existeEnScoring = Object.values(configScoringLinea.criterios).some(c =>
      c.nombre.toLowerCase() === nombreCriterio.toLowerCase() ||
      c.codigo.toLowerCase() === nombreCriterio.toLowerCase()
    );
  }
  
  // 2. Cargar criterios del sistema si no están disponibles
  let existeEnSistema = false;
  if (!window.criteriosSistema && lineaSeleccionadaId) {
    try {
      const response = await fetchConAuth(`/api/scoring/linea/${lineaSeleccionadaId}/criterios-factores-rechazo`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
      });
      
      const data = await response.json();
      if (data.success && data.criterios_sistema) {
        window.criteriosSistema = data.criterios_sistema;
      }
    } catch (error) {
      console.error("Error cargando criterios del sistema:", error);
    }
  }
  
  // 3. Buscar en criterios del sistema
  if (window.criteriosSistema) {
    existeEnSistema = window.criteriosSistema.some(c => 
      c.nombre.toLowerCase() === nombreCriterio.toLowerCase() ||
      c.id.toLowerCase() === nombreCriterio.toLowerCase()
    );
  }
  
  // 4. Mostrar advertencia si no existe
  if (!existeEnSistema && !existeEnScoring) {
    let mensaje = `⚠️ El criterio personalizado "${nombreCriterio}" no existe en el scoring de la línea ni en los criterios del sistema.\n\n`;
    mensaje += `• En scoring de la línea: ${Object.keys(configScoringLinea.criterios || {}).length > 0 ? 'Sí hay criterios configurados' : 'No hay criterios configurados'}\n`;
    mensaje += `• En criterios del sistema: ${window.criteriosSistema ? window.criteriosSistema.length + ' disponibles' : 'No cargados'}\n\n`;
    mensaje += `Este factor no se activará hasta que el criterio exista. `;
    mensaje += `Verifique que:\n`;
    mensaje += `1. El nombre sea exacto (sensible a mayúsculas/minúsculas)\n`;
    mensaje += `2. El criterio esté configurado en la pestaña "Criterios de Scoring"`;
    
    mostrarAlertaScoring(mensaje, 'warning');
  } else {
    console.log(`✅ Criterio personalizado "${nombreCriterio}" validado correctamente`);
  }
}

/**
 * Elimina un factor de rechazo de la lista
 */
function eliminarFactorLinea(index) {
  if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;

  if (confirm("¿Está seguro de eliminar este factor de rechazo?")) {
    configScoringLinea.factores_rechazo.splice(index, 1);
    renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
    markUnsavedAprobacionChanges();
    mostrarAlertaScoring("Factor eliminado. Recuerde guardar los cambios.", "info");
  }
}

// ============================================================================
// RENDERIZADO DE CONFIGURACIÓN DE APROBACIÓN
// ============================================================================

/**
 * Renderiza la configuración de aprobación de la línea
 * Incluye: parámetros de aprobación, umbrales y factores de rechazo
 */
function renderAprobacionLinea(config, factores) {
  const container = document.getElementById("aprobacionLineaContainer");
  if (!container) return;

  const cg = config || {};
  const factoresArr = factores || [];

  let html = `
    <div class="row">
      <!-- Parámetros de Aprobación -->
      <div class="col-12">
        <div class="card mb-3 border-success">
          <div class="card-header bg-success text-white">
            <i class="bi bi-check-circle me-2"></i>Parámetros de Aprobación
          </div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-6">
                <div class="mb-3">
                  <label class="form-label fw-bold">Puntaje mínimo para Aprobación Automática</label>
                  <input type="number" class="form-control" id="cfgPuntajeMinimo"
                         value="${cg.puntaje_minimo_aprobacion || 38}" min="0" max="100"
                         onchange="actualizarConfigAprobacion('puntaje_minimo_aprobacion', this.value)">
                  <small class="text-muted">Clientes con puntaje ≥ a este valor serán <strong>aprobados automáticamente</strong></small>
                  <small class="d-block text-info mt-1">Escala unificada 0-100.</small>
                </div>
              </div>
              <div class="col-md-6">
                <div class="alert alert-warning mb-0 h-100 d-flex align-items-center">
                  <div>
                    <i class="bi bi-info-circle-fill me-2"></i>
                    <strong>Configuración del Comité</strong><br>
                    <small>Para configurar el umbral de revisión manual (comité) y otros parámetros, 
                    dirígete a <a href="/admin/comite-credito/config" class="alert-link">Comité de Crédito → Configuración</a></small>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Nota: Los umbrales de rechazo se configuran en la tabla de Factores de Rechazo Personalizados -->
    <div class="alert alert-info mb-3">
      <i class="bi bi-lightbulb me-2"></i>
      <strong>Factores de Rechazo:</strong> Configure todos los umbrales de rechazo automático 
      (Score DataCrédito, Mora Telcos, Edad, DTI, etc.) usando la tabla de <strong>Factores de Rechazo Personalizados</strong> a continuación.
      Esto le permite personalizar completamente las reglas de rechazo por línea de crédito.
    </div>
    
    <!-- Factores de Rechazo Personalizados (contenedor delegado a renderFactoresRechazoLinea) -->
    <div id="factoresRechazoLineaContainer"></div>
    
    <div class="text-end">
      <button type="button" id="btnCancelarAprobacion" class="btn btn-outline-secondary me-2" onclick="cancelarCambiosAprobacion()">
        <i class="bi bi-arrow-clockwise me-1"></i>Cancelar cambios
      </button>
      <button type="button" id="btnGuardarAprobacion" class="btn btn-primary" onclick="guardarAprobacionLinea()">
        <i class="bi bi-check-lg me-1"></i>Guardar Configuración de Aprobación
      </button>
    </div>
  `;

  container.innerHTML = html;
  
  // Delegar renderizado de factores de rechazo a la función especializada
  renderFactoresRechazoLinea(factoresArr);
}

// Variable para trackear cambios en niveles de riesgo
let unsavedNivelesChanges = false;

/**
 * Marca cambios sin guardar en niveles y actualiza botones
 */
function markUnsavedNivelesChanges() {
  unsavedNivelesChanges = true;
  updateNivelesButtonState();
}

/**
 * Actualiza el estado visual de los botones guardar/cancelar de niveles
 */
function updateNivelesButtonState() {
  const btn = document.getElementById('btnGuardarNiveles');
  if (btn) {
    if (unsavedNivelesChanges) {
      btn.innerHTML = '<i class="bi bi-save me-1"></i>Guardar Cambios *';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-warning', 'btn-save-unsaved', 'text-dark', 'fw-bold');
    } else {
      btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Guardar niveles de riesgo';
      btn.classList.add('btn-primary');
      btn.classList.remove('btn-warning', 'btn-save-unsaved', 'text-dark', 'fw-bold');
    }
  }
  const btnCancel = document.getElementById('btnCancelarNiveles');
  if (btnCancel) {
    btnCancel.disabled = !unsavedNivelesChanges;
    if (unsavedNivelesChanges) {
      btnCancel.classList.remove('btn-outline-secondary');
      btnCancel.classList.add('btn-outline-danger');
    } else {
      btnCancel.classList.add('btn-outline-secondary');
      btnCancel.classList.remove('btn-outline-danger');
    }
  }
}

/**
 * Cancela cambios en niveles de riesgo y recarga desde servidor
 */
async function cancelarCambiosNiveles() {
  if (!unsavedNivelesChanges) return;
  if (!confirm('¿Deseas descartar los cambios en niveles de riesgo?')) return;
  await refrescarConfigLinea();
  unsavedNivelesChanges = false;
  updateNivelesButtonState();
  mostrarAlertaScoring('Cambios en niveles descartados.', 'info');
}

// Variable para trackear cambios en aprobación
let unsavedAprobacionChanges = false;

/**
 * Actualiza un campo de configuración de aprobación en memoria
 */
function actualizarConfigAprobacion(campo, valor) {
  if (!configScoringLinea) return;
  if (!configScoringLinea.config_general) {
    configScoringLinea.config_general = {};
  }
  configScoringLinea.config_general[campo] = parseFloat(valor);
  // Marcar cambios sin guardar
  markUnsavedAprobacionChanges();
}

/**
 * Marca cambios sin guardar en aprobación y actualiza el botón
 */
function markUnsavedAprobacionChanges() {
  unsavedAprobacionChanges = true;
  updateAprobacionButtonState();
}

/**
 * Actualiza el estado visual del botón de guardar aprobación
 */
function updateAprobacionButtonState() {
  const btn = document.getElementById('btnGuardarAprobacion');
  if (btn) {
    if (unsavedAprobacionChanges) {
      btn.innerHTML = '<i class="bi bi-save me-1"></i>Guardar Cambios *';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-warning', 'btn-save-unsaved', 'text-dark', 'fw-bold');
    } else {
      btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Guardar Configuración de Aprobación';
      btn.classList.add('btn-primary');
      btn.classList.remove('btn-warning', 'btn-save-unsaved', 'text-dark', 'fw-bold');
    }
  }
  const btnCancel = document.getElementById('btnCancelarAprobacion');
  if (btnCancel) {
    btnCancel.disabled = !unsavedAprobacionChanges;
    if (unsavedAprobacionChanges) {
      btnCancel.classList.remove('btn-outline-secondary');
      btnCancel.classList.add('btn-outline-danger');
    } else {
      btnCancel.classList.add('btn-outline-secondary');
      btnCancel.classList.remove('btn-outline-danger');
    }
  }
}

/**
 * Cancela cambios en aprobación y recarga desde servidor
 */
async function cancelarCambiosAprobacion() {
  if (!unsavedAprobacionChanges) return;
  if (!confirm('¿Deseas descartar los cambios en configuración de aprobación?')) return;
  await refrescarConfigLinea();
  unsavedAprobacionChanges = false;
  updateAprobacionButtonState();
  mostrarAlertaScoring('Cambios en aprobación descartados.', 'info');
}

/**
 * Guarda la configuración de aprobación (config general + factores de rechazo)
 */
async function guardarAprobacionLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  // Validar factores de rechazo antes de guardar
  const factores = configScoringLinea.factores_rechazo || [];
  for (let i = 0; i < factores.length; i++) {
    const f = factores[i];
    const tipoFactor = f.tipo_factor || 'numerico';
    const criterio = f.criterio || '';
    
    if (tipoFactor === 'seleccion') {
      // Validar factor tipo selección: necesita nombre y al menos 1 opción
      if (!f.criterio_nombre || !f.criterio_nombre.trim()) {
        mostrarAlertaScoring(`Factor #${i + 1}: El factor de selección requiere un nombre`, "warning");
        return;
      }
      if (!f.opciones || f.opciones.length === 0) {
        mostrarAlertaScoring(`Factor #${i + 1}: El factor de selección necesita al menos una opción`, "warning");
        return;
      }
      // Autogenerar código interno único basado en el nombre
      const codigoBase = f.criterio_nombre.trim().toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
      let codigoFinal = codigoBase;
      let sufijo = 2;
      // Verificar que no esté repetido entre todos los factores
      const otrosCodigos = factores.filter((_, idx) => idx !== i).map(ff => ff.criterio);
      while (otrosCodigos.includes(codigoFinal)) {
        codigoFinal = codigoBase + '_' + sufijo;
        sufijo++;
      }
      f.criterio = codigoFinal;
    } else {
      // Validar factor tipo numérico
      const esPersonalizado = criterio === '__personalizado__' || f.tipo_criterio === 'personalizado';
      
      if (esPersonalizado) {
        const nombrePersonalizado = f.criterio_personalizado || f.criterio_nombre || '';
        if (!nombrePersonalizado.trim()) {
          mostrarAlertaScoring(`Factor #${i + 1}: El criterio personalizado requiere un nombre`, "warning");
          return;
        }
        f.criterio_nombre = nombrePersonalizado.trim();
      }
      
      // Validar que el valor sea numérico
      if (f.valor === undefined || f.valor === null || f.valor === '' || isNaN(Number(f.valor))) {
        mostrarAlertaScoring(`Factor #${i + 1}: El valor debe ser numérico`, "warning");
        return;
      }
      
      // Validar operador
      const operadoresValidos = ['<', '<=', '>', '>=', '='];
      if (!operadoresValidos.includes(f.operador)) {
        mostrarAlertaScoring(`Factor #${i + 1}: Operador inválido`, "warning");
        return;
      }
    }
  }

  try {
    // Guardar configuración general
    const responseConfig = await fetchConCSRF(
      `/api/scoring/linea/${lineaSeleccionadaId}/config`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          config_general: configScoringLinea.config_general,
        }),
      }
    );

    // Guardar factores de rechazo
    const responseFactores = await fetchConCSRF(
      `/api/scoring/linea/${lineaSeleccionadaId}/factores-rechazo`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          factores: configScoringLinea.factores_rechazo || [],
        }),
      }
    );

    const dataConfig = await responseConfig.json();
    const dataFactores = await responseFactores.json();

    if (dataConfig.success && dataFactores.success) {
      mostrarAlertaScoring("Configuración de aprobación guardada exitosamente", "success");
      // Resetear estado de guardado para ambos botones
      unsavedChanges = false;
      unsavedAprobacionChanges = false;
      updateSaveButtonState();
      updateAprobacionButtonState();
      // Actualizar el texto del selector de línea con los valores nuevos
      actualizarSelectorLineaDespuesDeGuardar();
    } else {
      const errorMsg = dataConfig.error || dataFactores.error || "Error desconocido";
      mostrarAlertaScoring(`Error: ${errorMsg}`, "danger");
    }
  } catch (error) {
    console.error("Error guardando configuración:", error);
    mostrarAlertaScoring(`Error de conexión: ${error.message || 'Sin detalles'}`, "danger");
  }
}

// ============================================================================
// RENDERIZADO DE CRITERIOS DE SCORING CON SECCIONES Y DRAG & DROP
// ============================================================================

// Variable global para trackear estado de secciones colapsadas
let seccionesColapsadas = {};
// Variable para trackear todas las secciones activas (incluyendo vacías)
let seccionesActivas = new Set(["Probabilidad de Pago", "Capacidad de Pago", "Historial Crediticio", "Información Personal", "Sin Categoría"]);
// Variable para trackear cambios sin guardar
let unsavedChanges = false;

// Colores por sección


// Inyectar estilos CSS dinámicamente
(function injectScoringStyles() {
  const styleId = 'scoring-ui-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .btn-save-unsaved {
        animation: pulse-primary 2s infinite;
        box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.7);
      }
      @keyframes pulse-primary {
        0% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(13, 110, 253, 0); }
        100% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0); }
      }
      .seccion-header-custom {
        transition: background-color 0.3s ease;
      }
      .seccion-header-custom:hover {
        filter: brightness(0.98);
      }
      /* Asegurar que inputs en sección estática sean editables */
      .seccion-estatica input,
      .seccion-estatica select,
      .seccion-estatica textarea {
        pointer-events: auto !important;
        user-select: text !important;
        -webkit-user-select: text !important;
        position: relative;
        z-index: 10;
      }
      .seccion-estatica .form-control {
        pointer-events: auto !important;
      }
      .seccion-estatica .accordion-body {
        pointer-events: auto !important;
      }
      .seccion-estatica .accordion-body * {
        pointer-events: auto !important;
      }
    `;
    document.head.appendChild(style);
  }
})();

// Log de diagnóstico para inputs en sección estática
document.addEventListener('click', function(e) {
  if (e.target.matches('.seccion-estatica input, .seccion-estatica .form-control')) {
    console.log('🔍 [DEBUG] Click en input de sección estática:', {
      tagName: e.target.tagName,
      type: e.target.type,
      value: e.target.value,
      disabled: e.target.disabled,
      readOnly: e.target.readOnly,
      pointerEvents: getComputedStyle(e.target).pointerEvents,
      userSelect: getComputedStyle(e.target).userSelect,
      parentPointerEvents: getComputedStyle(e.target.parentElement).pointerEvents
    });
  }
});

/**
 * Marca la configuración como "con cambios sin guardar"
 */
function markUnsavedChanges() {
  unsavedChanges = true;
  updateSaveButtonState();
}

/**
 * Actualiza el estado visual del botón guardar
 */
function updateSaveButtonState() {
  const btn = document.getElementById('btnGuardarScoring');
  if (btn) {
    if (unsavedChanges) {
      btn.innerHTML = '<i class="bi bi-save me-1"></i>Guardar Cambios *';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-warning', 'btn-save-unsaved', 'text-dark', 'fw-bold');
    } else {
      btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Guardar Criterios';
      btn.classList.add('btn-primary');
      btn.classList.remove('btn-warning', 'btn-save-unsaved', 'text-dark', 'fw-bold');
    }

    // Actualizar botón cancelar
    const btnCancel = document.getElementById('btnCancelarScoring');
    if (btnCancel) {
      btnCancel.disabled = !unsavedChanges;
      if (unsavedChanges) {
        btnCancel.classList.remove('btn-outline-secondary');
        btnCancel.classList.add('btn-outline-danger');
      } else {
        btnCancel.classList.add('btn-outline-secondary');
        btnCancel.classList.remove('btn-outline-danger');
      }
    }
  }
}

/**
 * Cancela los cambios no guardados y recarga la configuración original
 */
async function cancelarCambiosScoring() {
  if (!lineaSeleccionadaId) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }
  
  // Confirmar cancelación
  if (!confirm("¿Deseas descartar todos los cambios no guardados?")) {
    return;
  }
  
  console.log("🔄 Cancelando cambios y recargando configuración...");
  
  // Recargar la configuración desde el servidor
  await seleccionarLineaCredito(lineaSeleccionadaId, lineaSeleccionadaNombre);
  
  // Marcar como sin cambios pendientes
  unsavedChanges = false;
  updateSaveButtonState();
  
  mostrarAlertaScoring("Cambios descartados. Se restauró la configuración guardada.", "info");
}

/**
 * Guarda los criterios de scoring de la línea actual
 */
async function guardarConfiguracionScoringLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  const criterios = configScoringLinea.criterios || [];

  // Adjuntar colores y metadatos de sección a cada criterio para persistencia
  criterios.forEach(c => {
    if (c.seccion) {
      if (customSectionColors[c.seccion]) {
        c.color_context = customSectionColors[c.seccion];
      }
      // Adjuntar metadatos de sección
      if (customSectionMeta[c.seccion]) {
        const meta = customSectionMeta[c.seccion];
        if (meta.icono) c.seccion_icono = meta.icono;
        if (meta.descripcion) c.seccion_descripcion = meta.descripcion;
        if (meta.orden !== undefined) c.seccion_orden = meta.orden;
      }
    }
  });

  // DEBUG: Log criterios being sent
  console.log("🔧 DEBUG guardarConfiguracionScoringLinea");
  console.log("   📤 Enviando", criterios.length, "criterios");
  console.log("   📦 customSectionMeta:", JSON.stringify(customSectionMeta));
  criterios.slice(0, 3).forEach((c, i) => {
    console.log(`      [${i}] ${c.codigo}: seccion='${c.seccion}', peso=${c.peso}, seccion_orden=${c.seccion_orden}, icono=${c.seccion_icono}`);
  });

  // Validar suma de pesos = 100% (EXCLUIR criterios en "Sin Categoría" - son penalizaciones)
  const criteriosActivos = criterios.filter(c => c.seccion !== 'Sin Categoría');
  const sumaPesos = criteriosActivos.reduce((sum, c) => sum + (parseFloat(c.peso) || 0), 0);
  if (Math.abs(sumaPesos - 100) > 0.1) {
    mostrarAlertaScoring(`La suma de pesos debe ser 100%. Actualmente: ${Math.round(sumaPesos)}%`, "warning");
    return;
  }

  // Validar que criterios de penalización (Sin Categoría) solo tengan puntos ≤ 0
  const criteriosPenalizacion = criterios.filter(c => c.seccion === 'Sin Categoría');
  for (const cp of criteriosPenalizacion) {
    const rangosInvalidos = (cp.rangos || []).filter(r => (parseFloat(r.puntos) || 0) > 0);
    if (rangosInvalidos.length > 0) {
      mostrarAlertaScoring(`El criterio de penalización "${cp.nombre}" tiene rangos con puntos positivos. Solo se permiten valores ≤ 0.`, "danger");
      return;
    }
  }

  try {
    const response = await fetchConCSRF(`/api/scoring/linea/${lineaSeleccionadaId}/criterios`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ criterios }),
    });
    
    const data = await response.json();

    if (data.success) {
      mostrarAlertaScoring("Criterios guardados correctamente", "success");
      unsavedChanges = false;
      updateSaveButtonState();
      // Refrescar tab de aprobación para sincronizar nombres de criterios en dropdowns
      renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
    } else {
      mostrarAlertaScoring(data.error || "Error al guardar criterios", "danger");
    }
  } catch (error) {
    console.error("Error guardando criterios:", error);
    mostrarAlertaScoring("Error de conexión al guardar. Recarga la página (F5) si el problema persiste.", "danger");
  }
}

/**
 * Expande o colapsa todos los acordeones de criterios
 */
function toggleAllCriteriosAccordions() {
  const collapses = document.querySelectorAll('.accordion-collapse[id^="collapse-crit-"]');
  const allOpen = Array.from(collapses).every(el => el.classList.contains('show'));

  collapses.forEach(el => {
    const btn = document.querySelector(`button[data-bs-target="#${el.id}"]`);
    if (allOpen) {
      el.classList.remove('show');
      if (btn) {
        btn.classList.add('collapsed');
        btn.setAttribute('aria-expanded', 'false');
      }
    } else {
      el.classList.add('show');
      if (btn) {
        btn.classList.remove('collapsed');
        btn.setAttribute('aria-expanded', 'true');
      }
    }
  });

  // Actualizar texto del botón
  const toggleBtn = document.getElementById('btnToggleAllAccordions');
  if (toggleBtn) {
    if (allOpen) {
      toggleBtn.innerHTML = '<i class="bi bi-arrows-expand me-1"></i>Expandir';
    } else {
      toggleBtn.innerHTML = '<i class="bi bi-arrows-collapse me-1"></i>Colapsar';
    }
  }
}

/**
 * Expande o colapsa un acordeón de criterio individual
 */
function toggleCriterioAccordion(collapseId) {
  console.log('🔧 toggleCriterioAccordion called with:', collapseId);

  const el = document.getElementById(collapseId);
  if (!el) {
    console.error('❌ Element not found:', collapseId);
    return;
  }

  const isOpen = el.classList.contains('show');
  const chevron = document.getElementById(`chevron-${collapseId}`);
  const btn = el.closest('.accordion-item')?.querySelector('.criterio-toggle-btn');

  console.log('📊 Current state:', { isOpen, hasChevron: !!chevron, hasBtn: !!btn });

  if (isOpen) {
    console.log('📥 Collapsing...');
    el.classList.remove('show');
    if (btn) {
      btn.setAttribute('aria-expanded', 'false');
    }
    if (chevron) {
      chevron.classList.remove('bi-chevron-down');
      chevron.classList.add('bi-chevron-right');
    }
  } else {
    console.log('📤 Expanding...');
    el.classList.add('show');
    if (btn) {
      btn.setAttribute('aria-expanded', 'true');
    }
    if (chevron) {
      chevron.classList.remove('bi-chevron-right');
      chevron.classList.add('bi-chevron-down');
    }
  }
  console.log('✅ toggleCriterioAccordion done');
}

/**
 * Renderiza los criterios de scoring agrupados por sección con drag & drop
 */
/**
 * Renderiza los criterios de scoring agrupados por sección con drag & drop
 */
function renderCriteriosLinea(criterios) {
  const container = document.getElementById("criteriosLineaContainer");
  if (!container) return;

  // CAPTURAR ESTADO: Guardar qué acordeones DE CRITERIOS están abiertos
  const openItems = [];
  document.querySelectorAll('.accordion-collapse.show').forEach(el => {
    // Solo guardar los de nivel criterio (que tienen id collapse-crit-...)
    if (el.id && el.id.startsWith('collapse-crit-')) {
      openItems.push(el.id);
    }
  });

  // Convertir objeto a array si es necesario
  let criteriosArray = [];
  if (criterios) {
    if (Array.isArray(criterios)) {
      criteriosArray = criterios;
    } else if (typeof criterios === 'object') {
      criteriosArray = Object.entries(criterios).map(([codigo, c]) => ({
        codigo,
        ...c
      }));
    }
  }

  // Asegurar que cada criterio tenga seccion y orden
  criteriosArray.forEach((c, i) => {
    if (!c.seccion) c.seccion = "Sin Categoría";
    if (c.orden === undefined) c.orden = i;
    seccionesActivas.add(c.seccion);
  });

  // Ordenar por orden
  criteriosArray.sort((a, b) => (a.orden || 0) - (b.orden || 0));

  // Agrupar criterios por sección
  const seccionesMap = {};
  criteriosArray.forEach(c => {
    const sec = c.seccion || "Sin Categoría";
    if (!seccionesMap[sec]) {
      seccionesMap[sec] = [];
    }
    seccionesMap[sec].push(c);
  });

  // Obtener lista final de secciones (Unión de mapa y set global)
  seccionesActivas.forEach(sec => {
    if (!seccionesMap[sec]) seccionesMap[sec] = [];
  });

  // Ordenar secciones - usar seccion_orden guardado si existe, sino orden predefinido
  const ordenPredefinido = ["Probabilidad de Pago", "Capacidad de Pago", "Historial Crediticio", "Información Personal"];
  const seccionesOrdenadas = Object.keys(seccionesMap).sort((a, b) => {
    if (a === "Sin Categoría") return 1;
    if (b === "Sin Categoría") return -1;
    
    // Usar orden guardado en customSectionMeta si existe
    const ordenA = customSectionMeta[a]?.orden;
    const ordenB = customSectionMeta[b]?.orden;
    
    if (ordenA !== undefined && ordenB !== undefined) {
      return ordenA - ordenB;
    }
    if (ordenA !== undefined) return -1;
    if (ordenB !== undefined) return 1;

    // Fallback a orden predefinido
    const idxA = ordenPredefinido.indexOf(a);
    const idxB = ordenPredefinido.indexOf(b);

    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;

    return a.localeCompare(b);
  });

  // Calcular suma de pesos (EXCLUIR criterios en "Sin Categoría" - son inactivos/borradores)
  const sumaPesos = criteriosArray
    .filter(c => c.seccion !== 'Sin Categoría')
    .reduce((sum, c) => sum + (parseFloat(c.peso) || 0), 0);

  let html = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div>
        <h5 class="mb-0">
          <i class="bi bi-list-check me-2"></i>Criterios de Evaluación
          <span class="badge bg-primary ms-2">${lineaSeleccionadaNombre}</span>
        </h5>
        <small class="text-muted">Arrastra para reordenar secciones y criterios.</small>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span class="badge ${Math.abs(sumaPesos - 100) < 0.1 ? 'bg-success' : 'bg-danger'} fs-6">
          Suma: ${Math.round(sumaPesos)}%
        </span>
        <button type="button" class="btn btn-outline-primary btn-sm" onclick="agregarSeccionModal()">
          <i class="bi bi-folder-plus me-1"></i>Nueva Sección
        </button>
        <button type="button" class="btn btn-success btn-sm" onclick="agregarCriterioLinea()">
          <i class="bi bi-plus-lg me-1"></i>Agregar Criterio
        </button>
      </div>
    </div>
    
    ${Math.abs(sumaPesos - 100) > 0.1 ? `
      <div class="alert alert-warning py-2 mb-3 shadow-sm border-warning">
        <i class="bi bi-exclamation-triangle me-2"></i>
        Los pesos deben sumar 100%. Actualmente: <strong>${Math.round(sumaPesos)}%</strong>
      </div>
    ` : ''}
  `;

  if (criteriosArray.length === 0 && seccionesOrdenadas.length === 0) {
    html += `
      <div class="alert alert-info py-4 text-center">
        <i class="bi bi-info-circle fs-4 d-block mb-2"></i>
        No hay criterios configurados.
        <div class="mt-2">
          <button type="button" class="btn btn-primary btn-sm" onclick="crearCriteriosPorDefecto()">
            <i class="bi bi-magic me-1"></i>Crear por defecto
          </button>
        </div>
      </div>
    `;
  } else {
    // Contenedor de secciones (sortable)
    html += `<div id="seccionesContainer" class="secciones-sortable">`;

    seccionesOrdenadas.forEach((seccion, secIndex) => {
      const criteriosSeccion = seccionesMap[seccion] || [];
      const colapsada = seccionesColapsadas[seccion] || false;
      const seccionId = `seccion-${secIndex}`;
      // Usar color personalizado o default
      const colorContext = customSectionColors[seccion] || SECCION_COLORS[seccion] || "secondary";
      // Obtener metadatos de sección (icono, descripción)
      const seccionMeta = customSectionMeta[seccion] || {};
      const seccionIcono = seccionMeta.icono || 'bi-folder';
      
      // Detectar si es color HEX o nombre de clase
      const isHexColor = colorContext.startsWith('#');
      
      // Generar estilos según tipo de color
      let headerStyle = '';
      let headerClass = '';
      let badgeStyle = '';
      let borderStyle = '';
      
      if (isHexColor) {
        // Color HEX: usar el color original sin atenuar
        headerStyle = `background-color: ${colorContext};`;
        badgeStyle = `background-color: ${colorContext}; color: white;`;
        borderStyle = `border-color: ${colorContext} !important;`;
      } else {
        // Nombre de clase: usar el color sólido en lugar de subtle
        headerClass = `bg-${colorContext}`;
        badgeStyle = '';
      }

      // "Sin Categoría" es estática, no se puede arrastrar
      const esSinCategoria = seccion === "Sin Categoría";
      
      html += `
        <div class="card mb-3 seccion-card shadow-sm ${!isHexColor ? 'border-' + colorContext : ''} bg-opacity-10 ${esSinCategoria ? 'seccion-estatica' : ''}" data-seccion="${seccion}" data-seccion-orden="${secIndex}" ${isHexColor ? `style="${borderStyle}"` : ''}>
          <div class="card-header ${headerClass} d-flex justify-content-between align-items-center py-2 seccion-header-custom" ${isHexColor ? `style="${headerStyle}"` : ''}>
            <div class="d-flex align-items-center flex-grow-1">
              ${!esSinCategoria ? `
              <span class="seccion-handle me-2" style="cursor: grab; opacity: 0.6;" title="Arrastrar sección">
                <i class="bi bi-grip-vertical fs-5"></i>
              </span>
              ` : `
              <span class="me-2" style="opacity: 0.7;" title="Sección fija - Penalizaciones">
                <i class="bi bi-shield-exclamation fs-5 text-warning"></i>
              </span>
              `}
              <button class="btn btn-link text-decoration-none p-0 d-flex align-items-center fw-bold text-start flex-grow-1" 
                      onclick="toggleSeccion('${seccion}', '${seccionId}')" type="button">
                <i class="bi ${colapsada ? 'bi-chevron-right' : 'bi-chevron-down'} me-2 text-white" id="icon-${seccionId}"></i>
                <i class="bi ${esSinCategoria ? 'bi-exclamation-triangle' : seccionIcono} me-2 ${esSinCategoria ? 'text-warning' : 'text-white'}"></i>
                <span class="text-white">${esSinCategoria ? 'Alertas Escaneo Preventivo' : seccion}</span>
                ${esSinCategoria ? '<span class="badge bg-warning text-dark ms-2" style="font-size: 0.65em;">Solo penalizaciones - No suma al 100%</span>' : ''}
                <span class="badge bg-white text-dark ms-2 rounded-pill" style="border: 1px solid rgba(0,0,0,0.1);">${criteriosSeccion.length}</span>
              </button>
            </div>
            <div class="btn-group btn-group-sm bg-white rounded shadow-sm">
              <button type="button" class="btn btn-outline-success border-0" onclick="agregarCriterioEnSeccion('${seccion}')" title="Crear criterio en esta sección">
                <i class="bi bi-plus-lg"></i>
              </button>
              ${!esSinCategoria ? `
              <button type="button" class="btn btn-outline-secondary border-0" onclick="editarSeccion('${seccion}')" title="Editar Nombre y Color">
                <i class="bi bi-pencil"></i>
              </button>
              <button type="button" class="btn btn-outline-danger border-0" onclick="eliminarSeccionLinea('${seccion}')" title="Eliminar sección">
                <i class="bi bi-trash"></i>
              </button>
              ` : ''}
            </div>
          </div>
          <div class="card-body p-0 ${colapsada ? 'd-none' : ''}" id="body-${seccionId}">
            <ul class="list-group list-group-flush criterios-list" data-seccion="${seccion}" style="min-height: 50px;">
              ${criteriosSeccion.map((criterio, idx) => renderCriterioItemAccordion(criterio, idx, seccion)).join('')}
            </ul>
            ${criteriosSeccion.length === 0 ? `
                <div class="text-center text-muted py-4 small bg-light bg-opacity-50">
                    ${esSinCategoria 
                      ? '<i class="bi bi-exclamation-triangle me-1 text-warning"></i>Arrastra criterios de penalización aquí (puntos negativos que restan del score)'
                      : '<i class="bi bi-arrow-down-up me-1"></i>Arrastra criterios aquí'}
                </div>
            ` : ''}
          </div>
        </div>
      `;
    });

    html += `</div>`;
  }

  html += `
    <div class="d-flex justify-content-between align-items-center mt-4 sticky-bottom bg-white p-3 border-top shadow-lg rounded-top" style="z-index: 1020; bottom: 0;">
      <div>
        <span id="badgeSumaPesosSticky" class="badge ${Math.abs(sumaPesos - 100) < 0.1 ? 'bg-success' : 'bg-danger'} fs-6">
          Suma: ${Math.round(sumaPesos)}%
        </span>
      </div>
      <div>
        <button id="btnCancelarScoring" class="btn btn-outline-danger" onclick="cancelarCambiosScoring()" disabled>
          <i class="bi bi-x-circle me-1"></i>Cancelar Cambios
        </button>
        <button id="btnGuardarScoring" class="btn btn-primary ms-2" onclick="guardarConfiguracionScoringLinea()">
          <i class="bi bi-check-lg me-1"></i>Guardar Criterios
        </button>
      </div>
    </div>
  `;

  container.innerHTML = html;

  // Actualizar estado del botón inmediatamente
  updateSaveButtonState();

  // Restaurar estado de acordeones de CRITERIOS abiertos (sin animación)
  if (openItems.length > 0) {
    openItems.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        // Agregar clase show directamente sin animación Bootstrap
        el.classList.add('show');
        // Actualizar botón y chevron del acordeón
        const accordionItem = el.closest('.accordion-item');
        if (accordionItem) {
          const btn = accordionItem.querySelector('.criterio-toggle-btn');
          if (btn) {
            btn.setAttribute('aria-expanded', 'true');
          }
          const chevron = document.getElementById(`chevron-${id}`);
          if (chevron) {
            chevron.classList.remove('bi-chevron-right');
            chevron.classList.add('bi-chevron-down');
          }
        }
      }
    });
  }

  // Inicializar drag & drop después de renderizar
  initSortableSecciones();
  initSortableCriterios();
}

/**
 * Renderiza un item de criterio con Acordeón completo para edición (Restaurado)
 */
function renderCriterioItemAccordion(criterio, idx, seccion) {
  const rangos = criterio.rangos || [];
  const tieneRangos = rangos.length > 0;
  const collapseId = `collapse-crit-${criterio.codigo}`;
  const esPenalizacion = seccion === "Sin Categoría";

  return `
    <li class="list-group-item criterio-item p-0 border-bottom" 
        data-codigo="${criterio.codigo}" data-seccion="${seccion}">
        
      <div class="accordion-item border-0">
        <h2 class="accordion-header" id="heading-${collapseId}">
          <div class="d-flex align-items-center w-100 px-2 py-1">
            <span class="criterio-handle me-2" style="cursor: grab;" title="Arrastrar criterio">
               <i class="bi bi-grip-vertical text-muted"></i>
            </span>
            
            <button class="btn btn-link w-100 text-start text-decoration-none p-1 d-flex align-items-center criterio-toggle-btn" type="button" 
                    onclick="event.stopPropagation(); toggleCriterioAccordion('${collapseId}')">
              <div class="d-flex justify-content-between align-items-center w-100 me-2">
                <span>
                  ${esPenalizacion 
                    ? '<span class="badge bg-warning text-dark me-2"><i class="bi bi-exclamation-triangle me-1"></i>Penalización</span>'
                    : `<span class="badge bg-primary me-2">${criterio.peso || 0}%</span>`}
                  <strong class="text-dark">${criterio.nombre || criterio.codigo}</strong>
                  ${(criterio.tipo_campo === 'composite' || criterio.tipo_campo === 'select') 
                    ? '<span class="badge bg-info text-dark ms-1" style="font-size: 0.65em;"><i class="bi bi-list me-1"></i>Compuesto</span>'
                    : '<span class="badge bg-light text-muted ms-1 border" style="font-size: 0.65em;"><i class="bi bi-123 me-1"></i>Numérico</span>'}
                  ${criterio.activo_extraccion ? '<span class="badge ms-1" title="Extracción IA activa: ' + (criterio.fuente_extraccion || '') + '" style="font-size: 0.65em; background-color: #7c3aed; color: white;"><i class="bi bi-cpu-fill me-1"></i>IA Auto</span>' : ''}
                </span>
                <span class="d-flex align-items-center gap-1">
                  <span class="badge ${tieneRangos ? 'bg-success' : 'bg-secondary'}" style="font-size: 0.75em;">${rangos.length} rangos</span>
                  <i class="bi bi-chevron-right text-muted ms-1 criterio-chevron" 
                     style="font-size: 0.8rem;" 
                     title="Expandir/Contraer detalles"
                     id="chevron-${collapseId}"></i>
                </span>
              </div>
            </button>
          </div>
        </h2>
        
        <div id="${collapseId}" class="accordion-collapse collapse" data-bs-parent="">
          <div class="accordion-body bg-light border-top px-3">
            ${esPenalizacion ? '<div class="alert alert-warning py-1 px-2 mb-2 small"><i class="bi bi-info-circle me-1"></i>Los puntos de penalización restan directamente del score final. Solo se permiten valores ≤ 0.</div>' : ''}
            <div class="row mb-3">
              <div class="${esPenalizacion ? 'col-md-5' : 'col-md-4'}">
                <label class="form-label small fw-bold">Nombre</label>
                <input type="text" class="form-control form-control-sm" value="${criterio.nombre || ''}"
                       onclick="event.stopPropagation()"
                       onchange="actualizarCriterioLinea('${criterio.codigo}', 'nombre', this.value)">
              </div>
              ${!esPenalizacion ? `
              <div class="col-md-2">
                <label class="form-label small fw-bold">Peso (%)</label>
                <input type="number" class="form-control form-control-sm" value="${criterio.peso || 0}" min="0" max="100"
                       onclick="event.stopPropagation()"
                       onchange="actualizarCriterioLinea('${criterio.codigo}', 'peso', this.value)">
              </div>
              ` : ''}
              <div class="${esPenalizacion ? 'col-md-5' : 'col-md-4'}">
                <label class="form-label small fw-bold">Descripción</label>
                <input type="text" class="form-control form-control-sm" value="${criterio.descripcion || ''}"
                       onclick="event.stopPropagation()"
                       onchange="actualizarCriterioLinea('${criterio.codigo}', 'descripcion', this.value)">
              </div>
              <div class="col-md-2 d-flex align-items-end gap-1">
                <button type="button" class="btn btn-outline-primary btn-sm flex-grow-1" onclick="editarCriterioModal('${criterio.codigo}')" title="Editar tipo y propiedades">
                  <i class="bi bi-pencil"></i>
                </button>
                <button type="button" class="btn btn-outline-danger btn-sm flex-grow-1" onclick="eliminarCriterioLinea('${criterio.codigo}')" title="Eliminar criterio">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
            
            <h6 class="small fw-bold text-muted"><i class="bi bi-rulers me-2"></i>Rangos de Puntuación</h6>
            ${tieneRangos ? `
              <div class="table-responsive bg-white rounded shadow-sm mb-2">
                <table class="table table-sm table-bordered mb-0" style="font-size: 0.85rem;">
                  <thead class="table-light">
                    <tr>
                      <th>Mínimo</th>
                      <th>Máximo</th>
                      <th>Puntos</th>
                      <th>Descripción</th>
                      <th class="text-center">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${rangos.map((r, ri) => `
                      <tr>
                        <td><input type="number" class="form-control form-control-sm border-0" value="${r.min}" 
                                   onclick="event.stopPropagation()"
                                   onchange="actualizarRangoCriterio('${criterio.codigo}', ${ri}, 'min', this.value)"></td>
                        <td><input type="number" class="form-control form-control-sm border-0" value="${r.max}"
                                   onclick="event.stopPropagation()"
                                   onchange="actualizarRangoCriterio('${criterio.codigo}', ${ri}, 'max', this.value)"></td>
                        <td><input type="number" class="form-control form-control-sm border-0" value="${r.puntos}"
                                   onclick="event.stopPropagation()"
                                   onchange="actualizarRangoCriterio('${criterio.codigo}', ${ri}, 'puntos', this.value)"></td>
                        <td><input type="text" class="form-control form-control-sm border-0" value="${r.descripcion || ''}"
                                   onclick="event.stopPropagation()"
                                   onchange="actualizarRangoCriterio('${criterio.codigo}', ${ri}, 'descripcion', this.value)"></td>
                        <td class="text-center">
                          <button type="button" class="btn btn-link text-danger p-0" 
                                  onclick="eliminarRangoCriterio('${criterio.codigo}', ${ri})">
                            <i class="bi bi-trash"></i>
                          </button>
                        </td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            ` : `<p class="text-muted small mb-2">No hay rangos definidos.</p>`}
            
            <button class="btn btn-sm btn-outline-success" onclick="agregarRangoCriterio('${criterio.codigo}')">
              <i class="bi bi-plus-lg me-1"></i>Agregar Rango
            </button>
          </div>
        </div>
      </div>
    </li>
  `;
}

/**
 * Obtiene el índice global de un criterio por su código
 */
function getCriterioGlobalIndex(codigo) {
  if (!configScoringLinea || !configScoringLinea.criterios) return -1;
  const criterios = configScoringLinea.criterios;
  if (Array.isArray(criterios)) {
    return criterios.findIndex(c => c.codigo === codigo);
  } else {
    return Object.keys(criterios).indexOf(codigo);
  }
}

/**
 * Inicializa Sortable para las secciones
 */
function initSortableSecciones() {
  const container = document.getElementById('seccionesContainer');
  if (!container || typeof Sortable === 'undefined') return;

  // Destruir instancia anterior si existe
  if (container.sortableInstance) {
    container.sortableInstance.destroy();
  }

  container.sortableInstance = new Sortable(container, {
    animation: 150,
    handle: '.seccion-handle',
    ghostClass: 'bg-primary-subtle',
    filter: '.seccion-estatica, input, select, textarea, button, .btn', // Excluir secciones estáticas e inputs
    preventOnFilter: false, // Permitir interacción normal con inputs y elementos filtrados
    onEnd: function (evt) {
      actualizarOrdenSecciones();
      markUnsavedChanges();
    }
  });
}

/**
 * Inicializa Sortable para los criterios dentro de cada sección
 */
function initSortableCriterios() {
  if (typeof Sortable === 'undefined') return;

  document.querySelectorAll('.criterios-list').forEach(list => {
    // Destruir instancia anterior si existe
    if (list.sortableInstance) {
      list.sortableInstance.destroy();
    }
    
    list.sortableInstance = new Sortable(list, {
      group: 'criterios', // Permite mover entre secciones
      animation: 150,
      handle: '.criterio-handle',
      ghostClass: 'bg-warning-subtle',
      filter: 'input, select, textarea, button, .btn', // Excluir inputs del drag
      preventOnFilter: false, // Permitir interacción normal con inputs
      onEnd: function (evt) {
        const codigo = evt.item.dataset.codigo;
        const nuevaSeccion = evt.to.dataset.seccion;
        const seccionAnterior = evt.from.dataset.seccion;

        // Actualizar sección del criterio en el modelo de datos
        actualizarSeccionCriterio(codigo, nuevaSeccion);

        // Actualizar orden de todos los criterios
        actualizarOrdenCriterios();

        // Si el criterio cambió entre sección normal y penalización,
        // re-renderizar para actualizar badge, campo peso y suma
        const cambioTipo = (nuevaSeccion === 'Sin Categoría') !== (seccionAnterior === 'Sin Categoría');
        if (cambioTipo && configScoringLinea && configScoringLinea.criterios) {
          renderCriteriosLinea(configScoringLinea.criterios);
        } else {
          // Solo actualizar contadores y suma de pesos
          actualizarContadoresSecciones();
        }
      }
    });
  });
}

/**
 * Actualiza el orden de las secciones basado en el DOM actual
 */
function actualizarOrdenSecciones() {
  markUnsavedChanges();
  const secciones = document.querySelectorAll('.seccion-card');
  let ordenCriterio = 0;
  let ordenSeccion = 0;

  secciones.forEach(card => {
    const seccionNombre = card.dataset.seccion;
    const lista = card.querySelector('.criterios-list');
    
    // Actualizar orden de la sección en customSectionMeta
    if (!customSectionMeta[seccionNombre]) {
      customSectionMeta[seccionNombre] = {};
    }
    customSectionMeta[seccionNombre].orden = ordenSeccion++;
    
    // Actualizar data-seccion-orden en el DOM
    card.dataset.seccionOrden = customSectionMeta[seccionNombre].orden;

    if (lista) {
      lista.querySelectorAll('.criterio-item').forEach(item => {
        const codigo = item.dataset.codigo;
        // Actualizar orden del criterio y también seccion_orden
        actualizarCriterioEnConfig(codigo, { 
          orden: ordenCriterio++,
          seccion_orden: customSectionMeta[seccionNombre].orden
        });
      });
    }
  });

  console.log('📦 Orden de secciones actualizado');
}

/**
 * Actualiza el orden de los criterios basado en el DOM actual
 */
function actualizarOrdenCriterios() {
  markUnsavedChanges();
  let ordenActual = 0;

  document.querySelectorAll('.criterios-list').forEach(lista => {
    const seccionNombre = lista.dataset.seccion;
    const seccionOrden = customSectionMeta[seccionNombre]?.orden;
    
    lista.querySelectorAll('.criterio-item').forEach(item => {
      const codigo = item.dataset.codigo;
      const props = { orden: ordenActual++ };
      if (seccionOrden !== undefined) {
        props.seccion_orden = seccionOrden;
      }
      actualizarCriterioEnConfig(codigo, props);
    });
  });

  console.log('📋 Orden de criterios actualizado');
}

/**
 * Actualiza la sección de un criterio
 */
function actualizarSeccionCriterio(codigo, nuevaSeccion) {
  markUnsavedChanges();
  actualizarCriterioEnConfig(codigo, { seccion: nuevaSeccion });
  console.log(`📁 Criterio ${codigo} movido a sección "${nuevaSeccion}"`);
}

/**
 * Actualiza los contadores de badges de cada sección en tiempo real
 * Cuenta los criterios visibles en el DOM de cada sección
 */
function actualizarContadoresSecciones() {
  document.querySelectorAll('.seccion-card').forEach(card => {
    const seccionNombre = card.dataset.seccion;
    const lista = card.querySelector('.criterios-list');
    const badge = card.querySelector('.badge.bg-white.text-dark');
    
    if (lista && badge) {
      const cantidadCriterios = lista.querySelectorAll('.criterio-item').length;
      badge.textContent = cantidadCriterios;
    }
  });
  
  // También actualizar el badge principal de suma de pesos
  actualizarBadgeSumaPesos();
  
  console.log('🔢 Contadores de secciones actualizados');
}

/**
 * Actualiza el badge de suma de pesos en tiempo real
 * Excluye criterios en "Sin Categoría"
 */
function actualizarBadgeSumaPesos() {
  if (!configScoringLinea || !configScoringLinea.criterios) return;
  
  const criterios = configScoringLinea.criterios;
  const sumaPesos = criterios
    .filter(c => c.seccion !== 'Sin Categoría')
    .reduce((sum, c) => sum + (parseFloat(c.peso) || 0), 0);
  
  const esValido = Math.abs(sumaPesos - 100) < 0.1;
  const badgeClass = `badge ${esValido ? 'bg-success' : 'bg-danger'} fs-6`;
  const badgeText = `Suma: ${Math.round(sumaPesos)}%`;
  
  // Actualizar TODOS los badges de suma (header y sticky)
  document.querySelectorAll('.badge.fs-6.bg-success, .badge.fs-6.bg-danger, #badgeSumaPesosSticky').forEach(badge => {
    badge.className = badgeClass;
    badge.id = badge.id || ''; // Preservar id si existe
    if (badge.id === 'badgeSumaPesosSticky') badge.id = 'badgeSumaPesosSticky';
    badge.innerHTML = badgeText;
  });
  
  // Actualizar o mostrar/ocultar la alerta de warning
  const alertaExistente = document.querySelector('.alert.alert-warning.py-2.mb-3');
  if (alertaExistente) {
    if (Math.abs(sumaPesos - 100) > 0.1) {
      alertaExistente.innerHTML = `
        <i class="bi bi-exclamation-triangle me-2"></i>
        Los pesos deben sumar 100%. Actualmente: <strong>${Math.round(sumaPesos)}%</strong>
      `;
      alertaExistente.style.display = 'block';
    } else {
      alertaExistente.style.display = 'none';
    }
  }
  
  console.log(`📊 Suma de pesos actualizada: ${Math.round(sumaPesos)}%`);
}

/**
 * Actualiza propiedades de un criterio en la configuración
 */
function actualizarCriterioEnConfig(codigo, propiedades) {
  markUnsavedChanges();
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const criterios = configScoringLinea.criterios;

  if (Array.isArray(criterios)) {
    const idx = criterios.findIndex(c => c.codigo === codigo);
    if (idx !== -1) {
      Object.assign(criterios[idx], propiedades);
    }
  } else { // Assuming it's an object if not an array
    if (criterios[codigo]) {
      Object.assign(criterios[codigo], propiedades);
    }
  }
}

/**
 * Colapsa/expande una sección de forma robusta
 */
function toggleSeccion(seccionNombre, seccionId) {
  seccionesColapsadas[seccionNombre] = !seccionesColapsadas[seccionNombre];

  const bodyId = `body-${seccionId}`;
  const iconId = `icon-${seccionId}`;

  const body = document.getElementById(bodyId);
  const icon = document.getElementById(iconId);

  if (body) {
    if (seccionesColapsadas[seccionNombre]) {
      body.classList.add('d-none');
    } else {
      body.classList.remove('d-none');
    }
  }

  if (icon) {
    if (seccionesColapsadas[seccionNombre]) {
      icon.className = 'bi bi-chevron-right me-2';
    } else {
      icon.className = 'bi bi-chevron-down me-2';
    }
  }
}

/**
 * Muestra modal para agregar nueva sección con color
 */
function agregarSeccionModal() {
  mostrarModalSeccion();
}

/**
 * Muestra modal para editar sección existente
 */
function editarSeccion(seccionActual) {
  // Capturar orden actual de TODAS las secciones antes de editar
  document.querySelectorAll('.seccion-card').forEach((card, idx) => {
    const secNombre = card.dataset.seccion;
    if (!customSectionMeta[secNombre]) {
      customSectionMeta[secNombre] = {};
    }
    customSectionMeta[secNombre].orden = idx;
  });
  
  const colorActual = customSectionColors[seccionActual] || SECCION_COLORS[seccionActual] || 'secondary';
  const metaActual = customSectionMeta[seccionActual] || {};
  mostrarModalSeccion(seccionActual, colorActual, metaActual.icono || 'bi-folder', metaActual.descripcion || '');
}

/**
 * Función auxiliar para mostrar modal de sección (Crear/Editar)
 */
function mostrarModalSeccion(nombreActual = "", colorActual = "primary", iconoActual = "bi-folder", descripcionActual = "") {
  // Crear modal dinámicamente si no existe
  let modalEl = document.getElementById('seccionModal');
  if (!modalEl) {
    const iconosDisponibles = [
      { value: 'bi-folder', label: '📁 Carpeta' },
      { value: 'bi-graph-up', label: '📊 Gráfico' },
      { value: 'bi-cash-stack', label: '💰 Dinero' },
      { value: 'bi-credit-card', label: '💳 Tarjeta' },
      { value: 'bi-person', label: '👤 Persona' },
      { value: 'bi-clock-history', label: '🕐 Historial' },
      { value: 'bi-shield-check', label: '🛡️ Verificación' },
      { value: 'bi-building', label: '🏢 Empresa' },
      { value: 'bi-briefcase', label: '💼 Trabajo' },
      { value: 'bi-calculator', label: '🧮 Calculadora' }
    ];
    const modalHtml = `
      <div class="modal fade" id="seccionModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="seccionModalTitle">Gestión de Sección</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <input type="hidden" id="seccionModalOldName">
              <div class="mb-3">
                <label for="seccionModalName" class="form-label">Nombre de la Sección</label>
                <input type="text" class="form-control" id="seccionModalName" placeholder="Ej: Historial Crediticio">
              </div>
              <div class="mb-3">
                <label for="seccionModalIcono" class="form-label">Icono</label>
                <select class="form-select" id="seccionModalIcono">
                  ${iconosDisponibles.map(i => `<option value="${i.value}">${i.label}</option>`).join('')}
                </select>
              </div>
              <div class="mb-3">
                <label for="seccionModalColor" class="form-label">Color del Tema</label>
                <select class="form-select" id="seccionModalColor">
                  ${AVAILABLE_COLORS.map(c => `<option value="${c.value}">${c.label}</option>`).join('')}
                </select>
              </div>
              <div class="mb-3">
                <label for="seccionModalDescripcion" class="form-label">Descripción (opcional)</label>
                <textarea class="form-control" id="seccionModalDescripcion" rows="2" placeholder="Breve descripción de esta sección"></textarea>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button type="button" class="btn btn-primary" onclick="guardarSeccionModal()">Guardar</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    modalEl = document.getElementById('seccionModal');
  }

  // Configurar modal - usar IDs del modal existente en admin.html
  // Primero intentar IDs del modal dinámico, si no existen usar los de admin.html
  let title = document.getElementById('seccionModalTitle');
  let nameInput = document.getElementById('seccionModalName');
  let colorInput = document.getElementById('seccionModalColor');
  let oldNameInput = document.getElementById('seccionModalOldName');
  let iconoInput = document.getElementById('seccionModalIcono');
  let descripcionInput = document.getElementById('seccionModalDescripcion');
  
  // Fallback a IDs de admin.html si el modal ya existía
  if (!title) title = document.getElementById('seccionModalLabel');
  if (!nameInput) nameInput = document.getElementById('seccion_nombre');
  if (!colorInput) colorInput = document.getElementById('seccion_color');
  if (!oldNameInput) oldNameInput = document.getElementById('seccion_id');
  if (!iconoInput) iconoInput = document.getElementById('seccion_icono');
  if (!descripcionInput) descripcionInput = document.getElementById('seccion_descripcion');

  if (nombreActual) {
    title.textContent = "Editar Sección";
    nameInput.value = nombreActual;
    colorInput.value = colorActual;
    oldNameInput.value = nombreActual;
    if (iconoInput) iconoInput.value = iconoActual;
    if (descripcionInput) descripcionInput.value = descripcionActual;
    console.log(`📝 Editando sección: ${nombreActual}, icono: ${iconoActual}, descripcion: ${descripcionActual}`);
  } else {
    title.textContent = "Nueva Sección";
    nameInput.value = "";
    colorInput.value = "primary"; // Default
    oldNameInput.value = "";
    if (iconoInput) iconoInput.value = "bi-folder";
    if (descripcionInput) descripcionInput.value = "";
  }

  const modal = new bootstrap.Modal(modalEl);
  modal.show();
}

/**
 * Guarda cambios del modal de sección
 */
function guardarSeccionModal() {
  // Usar IDs del modal dinámico o fallback a IDs de admin.html
  let nameInput = document.getElementById('seccionModalName');
  let colorInput = document.getElementById('seccionModalColor');
  let oldNameInput = document.getElementById('seccionModalOldName');
  let iconoInput = document.getElementById('seccionModalIcono');
  let descripcionInput = document.getElementById('seccionModalDescripcion');
  
  // Fallback a IDs de admin.html
  if (!nameInput) nameInput = document.getElementById('seccion_nombre');
  if (!colorInput) colorInput = document.getElementById('seccion_color');
  if (!oldNameInput) oldNameInput = document.getElementById('seccion_id');
  if (!iconoInput) iconoInput = document.getElementById('seccion_icono');
  if (!descripcionInput) descripcionInput = document.getElementById('seccion_descripcion');

  const nombre = nameInput.value.trim();
  const color = colorInput.value;
  const oldNombre = oldNameInput.value;
  const icono = iconoInput ? iconoInput.value : 'bi-folder';
  const descripcion = descripcionInput ? descripcionInput.value.trim() : '';

  if (!nombre) {
    alert("El nombre es requerido");
    return;
  }

  const modalEl = document.getElementById('seccionModal');
  const modal = bootstrap.Modal.getInstance(modalEl);

  if (oldNombre) {
    // Editar existente
    if (oldNombre !== nombre) {
      renombrarSeccion(oldNombre, nombre);
    }
    // Actualizar color en memoria
    customSectionColors[nombre] = color;
    // Persistir si se renombra también
    if (oldNombre !== nombre) {
      delete customSectionColors[oldNombre];
      // Mover metadatos al nuevo nombre
      if (customSectionMeta[oldNombre]) {
        customSectionMeta[nombre] = customSectionMeta[oldNombre];
        delete customSectionMeta[oldNombre];
      }
    }
    
    // Actualizar metadatos de sección (icono, descripción)
    if (!customSectionMeta[nombre]) {
      customSectionMeta[nombre] = {};
    }
    customSectionMeta[nombre].icono = icono;
    customSectionMeta[nombre].descripcion = descripcion;
    // Preservar orden actual de la sección
    const seccionCard = document.querySelector(`.seccion-card[data-seccion="${oldNombre}"]`);
    if (seccionCard) {
      const ordenActual = parseInt(seccionCard.dataset.seccionOrden) || 0;
      customSectionMeta[nombre].orden = ordenActual;
    }
    
    // IMPORTANTE: Actualizar color_context y metadatos en los criterios para persistencia
    if (configScoringLinea && configScoringLinea.criterios) {
      configScoringLinea.criterios.forEach(c => {
        if (c.seccion === nombre || c.seccion === oldNombre) {
          c.seccion = nombre;
          c.color_context = color;
          c.seccion_icono = icono;
          c.seccion_descripcion = descripcion;
          if (customSectionMeta[nombre] && customSectionMeta[nombre].orden !== undefined) {
            c.seccion_orden = customSectionMeta[nombre].orden;
          }
        }
        // También actualizar orden de otras secciones
        if (c.seccion && customSectionMeta[c.seccion] && customSectionMeta[c.seccion].orden !== undefined) {
          c.seccion_orden = customSectionMeta[c.seccion].orden;
        }
      });
    }
    
    console.log('📦 Metadatos de secciones actualizados:', JSON.stringify(customSectionMeta));

    // Actualizar UI
    renderCriteriosLinea(configScoringLinea.criterios);
    mostrarAlertaScoring("Sección actualizada. Guarda los criterios para persistir los cambios.", "success");
    
    // Marcar cambios sin guardar
    unsavedChanges = true;
    updateSaveButtonState();

  } else {
    // Crear nueva
    customSectionColors[nombre] = color;
    customSectionMeta[nombre] = { icono, descripcion };
    agregarSeccion(nombre);
  }

  modal.hide();
}

/**
 * Agrega una nueva sección vacía
 */
function agregarSeccion(nombre) {
  // Verificar que no exista
  if (!configScoringLinea) return;

  const criterios = configScoringLinea.criterios || [];
  const existe = (Array.isArray(criterios) ? criterios : Object.values(criterios))
    .some(c => c.seccion === nombre);

  if (existe || seccionesActivas.has(nombre)) {
    mostrarAlertaScoring(`La sección "${nombre}" ya existe`, "warning");
    return;
  }

  // Agregar a activas
  seccionesActivas.add(nombre);

  // Re-renderizar (la sección aparecerá cuando se mueva un criterio a ella)
  mostrarAlertaScoring(`Sección "${nombre}" creada. Arrastra criterios para agregarlos.`, "success");

  // Forzar re-render para mostrar sección vacía (opcional: agregar a estructura)
  renderCriteriosLinea(configScoringLinea.criterios);
}

/**
 * Muestra prompt para renombrar sección
 */
function editarSeccionNombre(seccionActual) {
  const nuevoNombre = prompt(`Renombrar sección "${seccionActual}" a:`, seccionActual);
  if (nuevoNombre && nuevoNombre.trim() && nuevoNombre !== seccionActual) {
    renombrarSeccion(seccionActual, nuevoNombre.trim());
  }
}

/**
 * Renombra una sección actualizando todos sus criterios
 */
function renombrarSeccion(nombreViejo, nombreNuevo) {
  markUnsavedChanges();
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const criterios = configScoringLinea.criterios;

  if (Array.isArray(criterios)) {
    criterios.forEach(c => {
      if (c.seccion === nombreViejo) {
        c.seccion = nombreNuevo;
      }
    });
  } else {
    Object.values(criterios).forEach(c => {
      if (c.seccion === nombreViejo) {
        c.seccion = nombreNuevo;
      }
    });
  }

  // Actualizar estado de colapso
  if (seccionesColapsadas[nombreViejo] !== undefined) {
    seccionesColapsadas[nombreNuevo] = seccionesColapsadas[nombreViejo];
    delete seccionesColapsadas[nombreViejo];
  }

  // Actualizar set de activas
  seccionesActivas.delete(nombreViejo);
  seccionesActivas.add(nombreNuevo);

  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring(`Sección renombrada a "${nombreNuevo}"`, "success");
}

/**
 * Elimina una sección moviendo sus criterios a "Sin Categoría"
 */
function eliminarSeccionLinea(seccionNombre) {
  if (!confirm(`¿Eliminar la sección "${seccionNombre}"?\nLos criterios se moverán a "Sin Categoría".`)) {
    return;
  }
  markUnsavedChanges();

  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const criterios = configScoringLinea.criterios;

  if (Array.isArray(criterios)) {
    criterios.forEach(c => {
      if (c.seccion === seccionNombre) {
        c.seccion = "Sin Categoría";
      }
    });
  } else {
    Object.values(criterios).forEach(c => {
      if (c.seccion === seccionNombre) {
        c.seccion = "Sin Categoría";
      }
    });
  }

  // Actualizar set de activas
  seccionesActivas.delete(seccionNombre);

  delete seccionesColapsadas[seccionNombre];

  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring(`Sección "${seccionNombre}" eliminada`, "success");
}

/**
 * Muestra modal para editar un criterio completo
 */
function editarCriterioModal(codigo) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const criterios = configScoringLinea.criterios;
  let criterio = null;
  let idx = -1;

  if (Array.isArray(criterios)) {
    idx = criterios.findIndex(c => c.codigo === codigo);
    criterio = idx !== -1 ? criterios[idx] : null;
  } else {
    criterio = criterios[codigo];
    idx = Object.keys(criterios).indexOf(codigo);
  }

  if (!criterio) {
    mostrarAlertaScoring("Criterio no encontrado", "danger");
    return;
  }

  // Usar el acordeón existente expandiéndolo
  const accordionItem = document.querySelector(`[data-codigo="${codigo}"]`);
  if (accordionItem) {
    // Scroll al item
    accordionItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Flash visual
    accordionItem.classList.add('border-primary');
    setTimeout(() => accordionItem.classList.remove('border-primary'), 2000);
  }

  // Por ahora usar prompt simple para edición rápida
  const nuevoNombre = prompt("Nombre del criterio:", criterio.nombre || "");
  if (nuevoNombre === null) return;

  const nuevoPeso = prompt("Peso (%):", criterio.peso || 0);
  if (nuevoPeso === null) return;

  const nuevaSeccion = prompt("Sección:", criterio.seccion || "Sin Categoría");
  if (nuevaSeccion === null) return;

  // Actualizar
  actualizarCriterioEnConfig(codigo, {
    nombre: nuevoNombre.trim() || criterio.nombre,
    peso: parseFloat(nuevoPeso) || criterio.peso,
    seccion: nuevaSeccion.trim() || "Sin Categoría"
  });

  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring("Criterio actualizado", "success");
}

// ============================================================================
// FUNCIONES DE UTILIDAD
// ============================================================================

/**
 * Refresca la configuración de la línea seleccionada
 */
async function refrescarConfigLinea() {
  if (lineaSeleccionadaId) {
    await seleccionarLineaCredito(lineaSeleccionadaId, lineaSeleccionadaNombre);
  }
}

/**
 * Muestra/oculta el contenido de scoring
 */
function mostrarContenidoScoring() {
  const containers = [
    "nivelesRiesgoLineaContainer",
    "aprobacionLineaContainer",
    "criteriosLineaContainer",
  ];

  containers.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = "block";
  });
}

function ocultarContenidoScoring() {
  const containers = [
    "nivelesRiesgoLineaContainer",
    "aprobacionLineaContainer",
    "criteriosLineaContainer",
  ];

  containers.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  });

  const infoContainer = document.getElementById("infoLineaSeleccionada");
  if (infoContainer) infoContainer.style.display = "none";
}

/**
 * Muestra loading en el contenido de scoring
 */
function mostrarLoadingScoring(show) {
  const loadingId = "scoringLoadingOverlay";
  let loading = document.getElementById(loadingId);

  if (show) {
    if (!loading) {
      loading = document.createElement("div");
      loading.id = loadingId;
      loading.className =
        "position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center";
      loading.style.cssText = "background: rgba(0,0,0,0.3); z-index: 9999;";
      loading.innerHTML = `
                <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                    <span class="visually-hidden">Cargando...</span>
                </div>
            `;
      document.body.appendChild(loading);
    }
    loading.style.display = "flex";
  } else if (loading) {
    loading.style.display = "none";
  }
}

/**
 * Muestra una alerta en el área de scoring
 */
function mostrarAlertaScoring(mensaje, tipo = "info", duracion = 5000) {
  const alertContainer = document.getElementById("scoringAlertContainer");
  if (!alertContainer) {
    // Crear contenedor si no existe
    const container = document.createElement("div");
    container.id = "scoringAlertContainer";
    container.className = "position-fixed top-0 end-0 p-3";
    container.style.cssText = "z-index: 9999; max-width: 400px;";
    document.body.appendChild(container);
  }

  const alertId = "alert_" + Date.now();
  const alertHtml = `
        <div id="${alertId}" class="alert alert-${tipo} alert-dismissible fade show" role="alert">
            <span class="pe-4">${mensaje}</span>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

  document
    .getElementById("scoringAlertContainer")
    .insertAdjacentHTML("beforeend", alertHtml);

  if (duracion > 0) {
    setTimeout(() => {
      const alert = document.getElementById(alertId);
      if (alert) {
        alert.classList.remove("show");
        setTimeout(() => alert.remove(), 150);
      }
    }, duracion);
  }
}

/**
 * Muestra el modal para copiar configuración
 */
function copiarConfiguracionModal() {
  console.log("📋 Abriendo modal copiar configuración...");
  console.log("📋 Línea seleccionada:", lineaSeleccionadaId, lineaSeleccionadaNombre);
  console.log("📋 Líneas disponibles:", lineasCreditoDisponibles.length);

  if (lineasCreditoDisponibles.length < 2) {
    mostrarAlertaScoring("Necesita al menos 2 líneas de crédito", "warning");
    return;
  }

  if (!lineaSeleccionadaId || !lineaSeleccionadaNombre) {
    mostrarAlertaScoring("Primero seleccione una línea de crédito destino", "warning");
    return;
  }

  // Eliminar TODOS los modales de copia existentes
  document.querySelectorAll('#copiarConfigModal').forEach(m => {
    try {
      const bsModal = bootstrap.Modal.getInstance(m);
      if (bsModal) bsModal.dispose();
    } catch (e) { }
    m.remove();
  });

  // Crear opciones del select (excluir línea actual)
  const opcionesOrigen = lineasCreditoDisponibles
    .filter((l) => l.id !== lineaSeleccionadaId)
    .map((l) => `<option value="${l.id}">${l.nombre}</option>`)
    .join("");

  console.log("📋 Opciones origen (excluye línea actual):", opcionesOrigen);

  const modalHtml = `
    <div class="modal fade" id="copiarConfigModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header bg-primary text-white">
            <h5 class="modal-title">
              <i class="bi bi-clipboard-plus me-2"></i>Copiar configuración
            </h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="alert alert-info mb-3">
              <i class="bi bi-info-circle me-2"></i>
              Seleccione qué elementos desea copiar. Los datos existentes en la línea destino serán <strong>reemplazados</strong>.
            </div>
            <div class="mb-3">
              <label class="form-label fw-bold">Copiar desde:</label>
              <select class="form-select" id="selectLineaOrigen">
                ${opcionesOrigen}
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label fw-bold">Hacia (línea actual):</label>
              <input type="text" class="form-control bg-warning text-dark fw-bold" 
                     value="${lineaSeleccionadaNombre}" readonly>
              <input type="hidden" id="lineaDestinoId" value="${lineaSeleccionadaId}">
              <small class="text-muted">La configuración se copiará a esta línea</small>
            </div>
            <hr>
            <label class="form-label fw-bold mb-2">¿Qué desea copiar?</label>
            <div class="form-check mb-2">
              <input type="checkbox" class="form-check-input" id="chkIncluirNiveles" checked>
              <label class="form-check-label" for="chkIncluirNiveles">
                <i class="bi bi-bar-chart-steps me-1 text-primary"></i>Niveles de Riesgo
                <small class="text-muted d-block">Tasas, avales, rangos de score y colores</small>
              </label>
            </div>
            <div class="form-check mb-2">
              <input type="checkbox" class="form-check-input" id="chkIncluirCriterios" checked>
              <label class="form-check-label" for="chkIncluirCriterios">
                <i class="bi bi-list-check me-1 text-success"></i>Criterios de Scoring
                <small class="text-muted d-block">Secciones, criterios, pesos y rangos de puntuación</small>
              </label>
            </div>
            <div class="form-check mb-2">
              <input type="checkbox" class="form-check-input" id="chkIncluirAprobacion" checked>
              <label class="form-check-label" for="chkIncluirAprobacion">
                <i class="bi bi-shield-check me-1 text-danger"></i>Configuración de Aprobación
                <small class="text-muted d-block">Umbrales generales y factores de rechazo automático</small>
              </label>
            </div>
            <div id="copiarValidacionMsg" class="text-danger small mt-2 d-none">
              <i class="bi bi-exclamation-circle me-1"></i>Seleccione al menos una opción
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-primary" onclick="ejecutarCopiaConfig()">
              <i class="bi bi-clipboard-check me-1"></i>Copiar
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
  const modal = document.getElementById("copiarConfigModal");
  new bootstrap.Modal(modal).show();
}

/**
 * Ejecuta la copia de configuración
 */
async function ejecutarCopiaConfig() {
  const origenId = document.getElementById("selectLineaOrigen").value;
  const destinoId = document.getElementById("lineaDestinoId").value;
  const incluirNiveles = document.getElementById("chkIncluirNiveles").checked;
  const incluirCriterios = document.getElementById("chkIncluirCriterios").checked;
  const incluirAprobacion = document.getElementById("chkIncluirAprobacion").checked;

  if (!origenId || !destinoId) {
    mostrarAlertaScoring("Seleccione las líneas", "warning");
    return;
  }

  // Validar que al menos una opción esté seleccionada
  const msgEl = document.getElementById("copiarValidacionMsg");
  if (!incluirNiveles && !incluirCriterios && !incluirAprobacion) {
    if (msgEl) msgEl.classList.remove("d-none");
    return;
  }
  if (msgEl) msgEl.classList.add("d-none");

  // Construir resumen de lo que se va a copiar
  const items = [];
  if (incluirNiveles) items.push("Niveles de Riesgo");
  if (incluirCriterios) items.push("Criterios de Scoring");
  if (incluirAprobacion) items.push("Configuración de Aprobación");

  // Confirmar antes de copiar
  const origenNombre = document.getElementById("selectLineaOrigen").selectedOptions[0].text;
  const destinoNombre = document.querySelector('#copiarConfigModal input[readonly]').value;
  
  if (!confirm(`¿Confirma copiar de "${origenNombre}" a "${destinoNombre}"?\n\nSe copiarán:\n• ${items.join('\n• ')}\n\nEsto reemplazará los datos actuales en la línea destino.`)) {
    return;
  }

  // Deshabilitar botón mientras copia
  const btnCopiar = document.querySelector('#copiarConfigModal .btn-primary');
  if (btnCopiar) {
    btnCopiar.disabled = true;
    btnCopiar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Copiando...';
  }

  try {
    const response = await fetchConCSRF("/api/scoring/copiar-config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        linea_origen_id: parseInt(origenId),
        linea_destino_id: parseInt(destinoId),
        incluir_niveles: incluirNiveles,
        incluir_criterios: incluirCriterios,
        incluir_aprobacion: incluirAprobacion,
      }),
    });

    const data = await response.json();

    if (data.success) {
      bootstrap.Modal.getInstance(
        document.getElementById("copiarConfigModal")
      ).hide();
      mostrarAlertaScoring(`Configuración copiada exitosamente (${items.join(', ')})`, "success");
      // Recargar configuración
      await refrescarConfigLinea();
    } else {
      mostrarAlertaScoring(`Error: ${data.error}`, "danger");
    }
  } catch (error) {
    console.error("Error copiando config:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  } finally {
    // Restaurar botón
    if (btnCopiar) {
      btnCopiar.disabled = false;
      btnCopiar.innerHTML = '<i class="bi bi-clipboard-check me-1"></i>Copiar';
    }
  }
}

// ============================================================================
// HELPER PARA CSRF TOKEN
// ============================================================================

function getCSRFToken() {
  // Buscar en input hidden
  const tokenInput = document.querySelector('input[name="csrf_token"]');
  if (tokenInput) return tokenInput.value;

  // Buscar en meta tag
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if (metaTag) return metaTag.content;

  // Buscar en cualquier formulario
  const allTokens = document.querySelectorAll('input[name="csrf_token"]');
  if (allTokens.length > 0) return allTokens[0].value;

  console.warn("No se encontró token CSRF");
  return "";
}

/**
 * Renueva el token CSRF desde el servidor y lo actualiza en el DOM
 */
async function renovarCSRFToken() {
  try {
    const resp = await fetch('/api/csrf-token', { method: 'GET', credentials: 'same-origin' });
    if (resp.ok) {
      const data = await resp.json();
      const nuevoToken = data.csrf_token;
      // Actualizar todos los inputs hidden de CSRF en la página
      document.querySelectorAll('input[name="csrf_token"]').forEach(input => {
        input.value = nuevoToken;
      });
      // Actualizar meta tag si existe
      const meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) meta.content = nuevoToken;
      console.log('🔄 Token CSRF renovado exitosamente');
      return nuevoToken;
    }
  } catch (e) {
    console.warn('⚠️ Error renovando token CSRF:', e);
  }
  return null;
}

/**
 * Fetch con auto-renovación de CSRF token
 * Si la petición falla con 400 por CSRF, renueva el token y reintenta
 */
async function fetchConCSRF(url, options = {}) {
  // Primera intentona con token actual
  const headers = options.headers || {};
  headers['X-CSRFToken'] = getCSRFToken();
  options.headers = headers;
  
  let response = await fetch(url, options);
  
  // Si la sesion expiro, redirigir al login
  if (response.status === 401) {
    console.warn('Sesion expirada — redirigiendo al login');
    alert('Tu sesion ha expirado. Seras redirigido al login.');
    window.location.href = '/login';
    throw new Error('SESSION_EXPIRED');
  }
  
  // Si falla con 400, intentar renovar token y reintentar
  if (response.status === 400) {
    const errorData = await response.clone().json().catch(() => ({}));
    if (errorData.code === 'CSRF_ERROR' || (errorData.error && errorData.error.includes('CSRF'))) {
      console.log('🔄 Token CSRF expirado, renovando...');
      const nuevoToken = await renovarCSRFToken();
      if (nuevoToken) {
        options.headers['X-CSRFToken'] = nuevoToken;
        response = await fetch(url, options);
        if (response.ok) {
          mostrarAlertaScoring('Token renovado automáticamente. Cambios guardados.', 'info');
        }
      } else {
        mostrarAlertaScoring('No se pudo renovar el token. Recarga la página.', 'danger');
      }
    }
  }
  
  return response;
}

// Renovar token CSRF cada 30 minutos preventivamente
setInterval(renovarCSRFToken, 30 * 60 * 1000);

// ============================================================================
// FUNCIONES PARA MANEJO DE CRITERIOS
// ============================================================================

/**
 * Agrega un nuevo criterio a la línea
 */
function agregarCriterioLinea() {
  if (!configScoringLinea) return;

  if (!configScoringLinea.criterios) {
    configScoringLinea.criterios = [];
  }

  // Lista de secciones disponibles
  const seccionesArr = Array.from(seccionesActivas);

  // Crear modal de selección con opciones de tipo y sección
  const tempModalId = 'modalAgregarCriterio';
  const modalHtml = `
    <div class="modal fade" id="${tempModalId}" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header bg-success text-white py-2">
            <h6 class="modal-title"><i class="bi bi-plus-lg me-2"></i>Nuevo Criterio</h6>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label small fw-bold">Tipo de Criterio</label>
              <select class="form-select form-select-sm" id="nuevoCriterioTipo">
                <option value="simple">Simple (Numérico)</option>
                <option value="composite">Compuesto (Múltiples factores)</option>
                <option value="hidden">Oculto (Hidden) - No visible para el asesor</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Sección</label>
              <select class="form-select form-select-sm" id="nuevoCriterioSeccion">
                ${seccionesArr.map(s => `<option value="${s}">${s}</option>`).join('')}
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Nombre</label>
              <input type="text" class="form-control form-control-sm" id="nuevoCriterioNombre" value="Nuevo Criterio">
            </div>
          </div>
          <div class="modal-footer p-1">
            <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-sm btn-success" onclick="confirmarAgregarCriterio('${tempModalId}')">Agregar</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Remover modal anterior si existe
  const oldModal = document.getElementById(tempModalId);
  if (oldModal) oldModal.remove();

  document.body.insertAdjacentHTML('beforeend', modalHtml);
  new bootstrap.Modal(document.getElementById(tempModalId)).show();
}

/**
 * Confirma la creación del criterio desde el modal
 */
function confirmarAgregarCriterio(modalId) {
  const tipo = document.getElementById('nuevoCriterioTipo').value;
  const seccion = document.getElementById('nuevoCriterioSeccion').value;
  const nombre = document.getElementById('nuevoCriterioNombre').value;

  // Cerrar modal
  const modalEl = document.getElementById(modalId);
  const modal = bootstrap.Modal.getInstance(modalEl);
  modal.hide();

  const numCriterios = configScoringLinea.criterios.length;

  configScoringLinea.criterios.push({
    codigo: `criterio_${Date.now()}`,
    nombre: nombre || `Nuevo Criterio ${numCriterios + 1}`,
    descripcion: tipo === 'composite' ? "Criterio compuesto" : (tipo === 'hidden' ? "Criterio oculto para factores de rechazo" : ""),
    peso: tipo === 'hidden' ? 0 : 0,  // Hidden siempre peso 0
    tipo_campo: tipo === 'composite' ? "composite" : (tipo === 'hidden' ? "hidden" : "number"),
    seccion: seccion,
    rangos: [],
    activo: true
  });

  markUnsavedChanges();
  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring(`Criterio "${nombre}" agregado a sección "${seccion}"`, "success");
}

/**
 * Agrega un criterio directamente en una sección específica (desde el botón + de la sección)
 */
function agregarCriterioEnSeccion(seccionNombre) {
  if (!configScoringLinea) return;
  if (!configScoringLinea.criterios) {
    configScoringLinea.criterios = [];
  }

  const tempModalId = 'modalAgregarCriterioSeccion';
  const oldModal = document.getElementById(tempModalId);
  if (oldModal) oldModal.remove();

  const modalHtml = `
    <div class="modal fade" id="${tempModalId}" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header bg-success text-white py-2">
            <h6 class="modal-title"><i class="bi bi-plus-lg me-2"></i>Nuevo Criterio en "${seccionNombre}"</h6>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label small fw-bold">Tipo de Criterio</label>
              <select class="form-select form-select-sm" id="nuevoCriterioSecTipo">
                <option value="simple">Simple (Numérico)</option>
                <option value="composite">Compuesto (Desplegable)</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Nombre</label>
              <input type="text" class="form-control form-control-sm" id="nuevoCriterioSecNombre" value="Nuevo Criterio">
            </div>
          </div>
          <div class="modal-footer p-1">
            <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-sm btn-success" onclick="confirmarAgregarCriterioEnSeccion('${tempModalId}', '${seccionNombre.replace(/'/g, "\\'")}')">Agregar</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
  new bootstrap.Modal(document.getElementById(tempModalId)).show();
}

/**
 * Confirma creación de criterio en sección específica
 */
function confirmarAgregarCriterioEnSeccion(modalId, seccionNombre) {
  const tipo = document.getElementById('nuevoCriterioSecTipo').value;
  const nombre = document.getElementById('nuevoCriterioSecNombre').value;

  const modalEl = document.getElementById(modalId);
  const modal = bootstrap.Modal.getInstance(modalEl);
  modal.hide();

  const numCriterios = configScoringLinea.criterios.length;

  configScoringLinea.criterios.push({
    codigo: 'criterio_' + Date.now(),
    nombre: nombre || 'Nuevo Criterio ' + (numCriterios + 1),
    descripcion: tipo === 'composite' ? 'Criterio compuesto' : '',
    peso: 0,
    tipo_campo: tipo === 'composite' ? 'composite' : 'number',
    seccion: seccionNombre,
    rangos: [],
    activo: true
  });

  markUnsavedChanges();
  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring('Criterio "' + nombre + '" agregado a sección "' + seccionNombre + '"', 'success');
}

/**
 * Abre modal para editar propiedades del criterio (tipo, nombre, sección)
 */
function editarCriterioModal(codigo) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;
  
  const criterio = configScoringLinea.criterios.find(c => c.codigo === codigo);
  if (!criterio) return;
  
  // Obtener secciones disponibles
  const seccionesSet = new Set(configScoringLinea.criterios.map(c => c.seccion || 'Sin Categoría'));
  const seccionesArr = Array.from(seccionesSet);
  
  const tipoCampo = criterio.tipo_campo || 'number';
  const esCompuesto = tipoCampo === 'composite';
  
  const modalId = 'modalEditarCriterio';
  const oldModal = document.getElementById(modalId);
  if (oldModal) oldModal.remove();
  
  const modalHtml = `
    <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header bg-primary text-white py-2">
            <h6 class="modal-title"><i class="bi bi-pencil me-2"></i>Editar Criterio</h6>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label small fw-bold">Nombre</label>
              <input type="text" class="form-control form-control-sm" id="editCriterioNombre" value="${criterio.nombre || ''}">
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Tipo de Criterio</label>
              <select class="form-select form-select-sm" id="editCriterioTipo">
                <option value="number" ${!esCompuesto && tipoCampo !== 'hidden' ? 'selected' : ''}>Simple (Numérico)</option>
                <option value="composite" ${esCompuesto ? 'selected' : ''}>Compuesto (Desplegable)</option>
                <option value="hidden" ${tipoCampo === 'hidden' ? 'selected' : ''}>Oculto (Hidden) - No visible para el asesor</option>
              </select>
              <div class="form-text small text-muted">Simple = valor numérico. Compuesto = selección desplegable en calculadora.</div>
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Sección</label>
              <select class="form-select form-select-sm" id="editCriterioSeccion">
                ${seccionesArr.map(s => `<option value="${s}" ${s === criterio.seccion ? 'selected' : ''}>${s === 'Sin Categoría' ? 'Alertas Escaneo Preventivo' : s}</option>`).join('')}
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Descripción</label>
              <input type="text" class="form-control form-control-sm" id="editCriterioDescripcion" value="${criterio.descripcion || ''}">
            </div>
            <div class="mb-3">
              <label class="form-label small fw-bold">Código</label>
              <input type="text" class="form-control form-control-sm bg-light" id="editCriterioCodigo" value="${criterio.codigo}" readonly>
              <div class="form-text small text-muted">El código no se puede cambiar.</div>
            </div>
            <hr>
            <div class="mb-2">
              <button class="btn btn-sm btn-outline-secondary w-100 text-start py-1" type="button"
                      data-bs-toggle="collapse" data-bs-target="#collapseExtraccionModal" aria-expanded="false">
                <i class="bi bi-cloud-download me-1"></i>Fuente de Datos (extracción automática)
                ${criterio.activo_extraccion ? '<span class="badge bg-success ms-2">Activa</span>' : '<span class="badge bg-secondary ms-2">Inactiva</span>'}
              </button>
              <div class="collapse" id="collapseExtraccionModal">
                <div class="card card-body mt-2 p-2 bg-dark border-secondary">
                  <div class="mb-2">
                    <label class="form-label small text-white mb-1">Fuente de extracción</label>
                    <select class="form-select form-select-sm" id="editCriterioFuente"
                            onchange="toggleExtraccionModal()">
                      <option value="">-- Sin extracción automática --</option>
                    </select>
                  </div>
                  <div class="mb-2" id="editContInstruccion"
                       style="display:${criterio.fuente_extraccion && criterio.fuente_extraccion !== 'formulario_manual' ? 'block' : 'none'}">
                    <label class="form-label small text-white mb-1">Instrucción para la IA</label>
                    <textarea class="form-control form-control-sm" id="editCriterioInstruccion" rows="3"
                              maxlength="3000"
                              placeholder="Describe qué debe buscar la IA en este documento."
                              oninput="document.getElementById('contadorInstruccion').textContent = this.value.length + '/3000'"
                    >${criterio.instruccion_extraccion || ''}</textarea>
                    <div class="text-end"><small class="text-white" id="contadorInstruccion">${(criterio.instruccion_extraccion || '').length}/3000</small></div>
                  </div>
                  <div class="form-check form-switch" id="editContActivo"
                       style="display:${criterio.fuente_extraccion ? 'block' : 'none'}">
                    <input class="form-check-input" type="checkbox" id="editCriterioActivo"
                           ${criterio.activo_extraccion ? 'checked' : ''}>
                    <label class="form-check-label small text-white" for="editCriterioActivo">Activar extracción automática</label>
                  </div>
                  <div id="editChipApi" style="display:none">
                    <span class="badge bg-warning text-dark mt-1">⚠ Requiere integración API configurada</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer p-1">
            <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-sm btn-primary" onclick="confirmarEditarCriterio('${codigo}')">
              <i class="bi bi-check-lg me-1"></i>Guardar
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  const modal = new bootstrap.Modal(document.getElementById(modalId));
  modal.show();
  
  // Poblar select de fuentes de extracción
  fetchConAuth('/api/fuentes-extraccion')
    .then(r => r.json())
    .then(data => {
      if (!data.success || !data.fuentes) return;
      const select = document.getElementById('editCriterioFuente');
      if (!select) return;
      
      const documentos = [];
      const apis = [];
      const manuales = [];
      for (const [key, info] of Object.entries(data.fuentes)) {
        const item = { valor: key, label: info.label, tipo: info.tipo };
        if (info.tipo === 'documento') documentos.push(item);
        else if (info.tipo === 'api') apis.push(item);
        else manuales.push(item);
      }
      
      if (documentos.length) {
        const grp = document.createElement('optgroup');
        grp.label = 'Documentos del cliente';
        documentos.forEach(f => {
          const opt = new Option(f.label, f.valor);
          if (criterio.fuente_extraccion === f.valor) opt.selected = true;
          grp.appendChild(opt);
        });
        select.appendChild(grp);
      }
      if (apis.length) {
        const grp = document.createElement('optgroup');
        grp.label = 'APIs externas';
        apis.forEach(f => {
          const opt = new Option(f.label, f.valor);
          if (criterio.fuente_extraccion === f.valor) opt.selected = true;
          grp.appendChild(opt);
        });
        select.appendChild(grp);
      }
      if (manuales.length) {
        manuales.forEach(f => {
          const opt = new Option(f.label, f.valor);
          if (criterio.fuente_extraccion === f.valor) opt.selected = true;
          select.appendChild(opt);
        });
      }
      
      // Mostrar chip API si la fuente actual es tipo api
      if (criterio.fuente_extraccion) {
        const fuenteInfo = data.fuentes[criterio.fuente_extraccion];
        const chipApi = document.getElementById('editChipApi');
        if (chipApi && fuenteInfo && fuenteInfo.tipo === 'api') {
          chipApi.style.display = 'block';
        }
      }
    }).catch(err => console.warn('No se pudieron cargar fuentes de extracción:', err));
}

/**
 * Toggle de campos de extracción en el modal de edición
 */
function toggleExtraccionModal() {
  const fuente = document.getElementById('editCriterioFuente').value;
  const contInst = document.getElementById('editContInstruccion');
  const contActivo = document.getElementById('editContActivo');
  const chipApi = document.getElementById('editChipApi');
  
  if (contInst) contInst.style.display = (fuente && fuente !== 'formulario_manual') ? 'block' : 'none';
  if (contActivo) contActivo.style.display = fuente ? 'block' : 'none';
  
  // Actualizar chip API
  if (chipApi) {
    chipApi.style.display = 'none';
    if (fuente) {
      fetchConAuth('/api/fuentes-extraccion')
        .then(r => r.json())
        .then(data => {
          if (data.success && data.fuentes && data.fuentes[fuente] && data.fuentes[fuente].tipo === 'api') {
            chipApi.style.display = 'block';
          }
        }).catch(() => {});
    }
  }
}

/**
 * Confirma la edición del criterio desde el modal
 */
function confirmarEditarCriterio(codigo) {
  const nombre = document.getElementById('editCriterioNombre').value.trim();
  const tipo = document.getElementById('editCriterioTipo').value;
  const seccion = document.getElementById('editCriterioSeccion').value;
  const descripcion = document.getElementById('editCriterioDescripcion').value.trim();
  
  if (!nombre) {
    mostrarAlertaScoring('El nombre es obligatorio', 'warning');
    return;
  }
  
  const index = configScoringLinea.criterios.findIndex(c => c.codigo === codigo);
  if (index === -1) return;
  
  configScoringLinea.criterios[index].nombre = nombre;
  configScoringLinea.criterios[index].tipo_campo = tipo;
  configScoringLinea.criterios[index].seccion = seccion;
  configScoringLinea.criterios[index].descripcion = descripcion;
  
  // Campos de extracción automática
  const fuenteEl = document.getElementById('editCriterioFuente');
  const instruccionEl = document.getElementById('editCriterioInstruccion');
  const activoEl = document.getElementById('editCriterioActivo');
  if (fuenteEl) configScoringLinea.criterios[index].fuente_extraccion = fuenteEl.value || null;
  if (instruccionEl) configScoringLinea.criterios[index].instruccion_extraccion = instruccionEl.value.trim() || null;
  if (activoEl) configScoringLinea.criterios[index].activo_extraccion = activoEl.checked ? 1 : 0;
  
  // Si cambia a hidden, asegurar peso 0
  if (tipo === 'hidden') {
    configScoringLinea.criterios[index].peso = 0;
  }
  
  markUnsavedChanges();
  
  // Cerrar modal
  const modalEl = document.getElementById('modalEditarCriterio');
  const modal = bootstrap.Modal.getInstance(modalEl);
  modal.hide();
  
  // Re-renderizar para reflejar cambios de sección y tipo
  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring(`Criterio "${nombre}" actualizado. Recuerde guardar.`, 'success');
}


/**
 * Actualiza un campo de criterio en memoria
 */
function actualizarCriterioLinea(codigo, campo, valor) {
  markUnsavedChanges();
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const index = configScoringLinea.criterios.findIndex(c => c.codigo === codigo);
  if (index === -1) return;

  if (campo === 'peso') {
    valor = parseFloat(valor) || 0;
  }

  configScoringLinea.criterios[index][campo] = valor;

  // Actualizar badge de peso en el header del criterio en vivo
  if (campo === 'peso') {
    const criterioEl = document.querySelector(`[data-codigo="${codigo}"]`);
    if (criterioEl) {
      const badgePeso = criterioEl.querySelector('.badge.bg-primary');
      if (badgePeso) {
        badgePeso.textContent = `${valor}%`;
      }
    }
    actualizarBadgeSumaPesos();
  }
  
  // Actualizar nombre en el header del criterio en vivo
  if (campo === 'nombre') {
    const criterioEl = document.querySelector(`[data-codigo="${codigo}"]`);
    if (criterioEl) {
      const nombreEl = criterioEl.querySelector('.criterio-toggle-btn strong.text-dark');
      if (nombreEl) {
        nombreEl.textContent = valor;
      }
    }
  }
}

/**
 * Elimina un criterio de la línea (con re-render completo para evitar fantasmas en DOM)
 */
function eliminarCriterioLinea(codigo) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const index = configScoringLinea.criterios.findIndex(c => c.codigo === codigo);
  if (index === -1) {
    console.warn(`⚠️ Criterio ${codigo} no encontrado en array (ya fue eliminado?)`);
    return;
  }

  const criterio = configScoringLinea.criterios[index];
  if (confirm(`¿Está seguro de eliminar el criterio "${criterio.nombre}"?`)) {
    markUnsavedChanges();
    configScoringLinea.criterios.splice(index, 1);
    
    // Re-render completo para garantizar sincronía DOM ↔ datos
    renderCriteriosLinea(configScoringLinea.criterios);
    mostrarAlertaScoring("Criterio eliminado. Recuerde guardar los cambios.", "info");
  }
}

/**
 * Actualiza el badge de conteo de rangos de un criterio en el DOM
 */
function actualizarBadgeRangosCriterio(criterioCard, totalRangos) {
  if (!criterioCard) return;
  const badgeRangos = criterioCard.querySelector('.badge.bg-success, .badge.bg-secondary');
  if (badgeRangos) {
    badgeRangos.className = `badge ${totalRangos > 0 ? 'bg-success' : 'bg-secondary'}`;
    badgeRangos.style.fontSize = '0.75em';
    badgeRangos.textContent = `${totalRangos} rangos`;
  }
}

/**
 * Agrega un nuevo rango a un criterio (re-render completo para garantizar sincronía DOM)
 */
function agregarRangoCriterio(codigo) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const index = configScoringLinea.criterios.findIndex(c => c.codigo === codigo);
  if (index === -1) return;

  if (!configScoringLinea.criterios[index].rangos) {
    configScoringLinea.criterios[index].rangos = [];
  }

  // Si es criterio de penalización (Sin Categoría), usar puntos negativos por defecto
  const esPenalizacion = configScoringLinea.criterios[index].seccion === 'Sin Categoría';
  const nuevoRango = {
    min: 0,
    max: 100,
    puntos: esPenalizacion ? -10 : 10,
    descripcion: esPenalizacion ? "Penalización detectada" : "Nuevo rango"
  };
  
  configScoringLinea.criterios[index].rangos.push(nuevoRango);
  markUnsavedChanges();
  
  // Re-render completo para garantizar sincronía DOM ↔ datos
  renderCriteriosLinea(configScoringLinea.criterios);
}

/**
 * Actualiza un rango de criterio
 */
function actualizarRangoCriterio(codigo, rangoIndex, campo, valor) {
  markUnsavedChanges();
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const index = configScoringLinea.criterios.findIndex(c => c.codigo === codigo);
  if (index === -1) return;

  if (campo === 'min' || campo === 'max' || campo === 'puntos') {
    valor = parseFloat(valor);
  }

  // Validar puntos negativos para criterios de penalización (Sin Categoría)
  if (campo === 'puntos' && configScoringLinea.criterios[index].seccion === 'Sin Categoría') {
    if (valor > 0) {
      mostrarAlertaScoring('Los criterios de penalización solo admiten puntos negativos o cero', 'warning');
      return;
    }
  }

  configScoringLinea.criterios[index].rangos[rangoIndex][campo] = valor;
}

/**
 * Elimina un rango de criterio (re-render completo para garantizar sincronía DOM)
 */
function eliminarRangoCriterio(codigo, rangoIndex) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const index = configScoringLinea.criterios.findIndex(c => c.codigo === codigo);
  if (index === -1) return;

  if (confirm("¿Está seguro de eliminar este rango?")) {
    markUnsavedChanges();
    configScoringLinea.criterios[index].rangos.splice(rangoIndex, 1);
    
    // Re-render completo para garantizar sincronía DOM ↔ datos
    renderCriteriosLinea(configScoringLinea.criterios);
  }
}

/**
 * Crea criterios por defecto para la línea
 */
function crearCriteriosPorDefecto() {
  if (!configScoringLinea) return;
  markUnsavedChanges();

  configScoringLinea.criterios = [
    {
      codigo: "edad",
      nombre: "Edad del Cliente",
      descripcion: "Rango de edad del solicitante",
      peso: 10,
      tipo_campo: "numerico",
      rangos: [
        { min: 18, max: 25, puntos: 15, descripcion: "Joven" },
        { min: 26, max: 40, puntos: 25, descripcion: "Adulto joven" },
        { min: 41, max: 60, puntos: 20, descripcion: "Adulto" },
        { min: 61, max: 84, puntos: 10, descripcion: "Adulto mayor" }
      ]
    },
    {
      codigo: "score_datacredito",
      nombre: "Score DataCrédito",
      descripcion: "Puntaje de buró de crédito",
      peso: 25,
      tipo_campo: "numerico",
      rangos: [
        { min: 700, max: 950, puntos: 25, descripcion: "Excelente" },
        { min: 600, max: 699, puntos: 20, descripcion: "Bueno" },
        { min: 500, max: 599, puntos: 15, descripcion: "Regular" },
        { min: 400, max: 499, puntos: 10, descripcion: "Bajo" }
      ]
    },
    {
      codigo: "ingresos",
      nombre: "Nivel de Ingresos",
      descripcion: "Ingresos mensuales del solicitante",
      peso: 20,
      tipo_campo: "numerico",
      rangos: [
        { min: 5000000, max: 999999999, puntos: 25, descripcion: "Muy alto" },
        { min: 3000000, max: 4999999, puntos: 20, descripcion: "Alto" },
        { min: 1500000, max: 2999999, puntos: 15, descripcion: "Medio" },
        { min: 1000000, max: 1499999, puntos: 10, descripcion: "Bajo" }
      ]
    },
    {
      codigo: "antiguedad_laboral",
      nombre: "Antigüedad Laboral",
      descripcion: "Tiempo en el empleo actual (meses)",
      peso: 15,
      tipo_campo: "numerico",
      rangos: [
        { min: 36, max: 999, puntos: 25, descripcion: "3+ años" },
        { min: 24, max: 35, puntos: 20, descripcion: "2-3 años" },
        { min: 12, max: 23, puntos: 15, descripcion: "1-2 años" },
        { min: 6, max: 11, puntos: 10, descripcion: "6-12 meses" }
      ]
    },
    {
      codigo: "tipo_contrato",
      nombre: "Tipo de Contrato",
      descripcion: "Estabilidad laboral",
      peso: 15,
      tipo_campo: "seleccion",
      rangos: [
        { min: 0, max: 0, puntos: 25, descripcion: "Indefinido" },
        { min: 1, max: 1, puntos: 15, descripcion: "Fijo" },
        { min: 2, max: 2, puntos: 10, descripcion: "Prestación de servicios" }
      ]
    },
    {
      codigo: "nivel_endeudamiento",
      nombre: "Nivel de Endeudamiento",
      descripcion: "DTI - Relación deuda/ingreso",
      peso: 15,
      tipo_campo: "numerico",
      rangos: [
        { min: 0, max: 20, puntos: 25, descripcion: "Muy bajo" },
        { min: 21, max: 35, puntos: 20, descripcion: "Bajo" },
        { min: 36, max: 50, puntos: 15, descripcion: "Moderado" },
        { min: 51, max: 70, puntos: 5, descripcion: "Alto" }
      ]
    }
  ];

  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring("Criterios por defecto creados. Recuerde guardar los cambios.", "success");
}

/**
 * Guarda los criterios de la línea
 */
async function guardarCriteriosLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  // Validar que los pesos sumen 100 (EXCLUIR criterios en "Sin Categoría" - son penalizaciones)
  const criterios = configScoringLinea.criterios || [];
  const criteriosActivos = criterios.filter(c => c.seccion !== 'Sin Categoría');
  const sumaPesos = criteriosActivos.reduce((sum, c) => sum + (parseFloat(c.peso) || 0), 0);

  if (Math.abs(sumaPesos - 100) > 0.1) {
    mostrarAlertaScoring(`Los pesos deben sumar 100%. Actualmente suman ${Math.round(sumaPesos)}%`, "danger");
    return;
  }

  // Validar que criterios de penalización (Sin Categoría) solo tengan puntos ≤ 0
  const criteriosPen = criterios.filter(c => c.seccion === 'Sin Categoría');
  for (const cp of criteriosPen) {
    const rangosInvalidos = (cp.rangos || []).filter(r => (parseFloat(r.puntos) || 0) > 0);
    if (rangosInvalidos.length > 0) {
      mostrarAlertaScoring(`El criterio de penalización "${cp.nombre}" tiene rangos con puntos positivos. Solo se permiten valores ≤ 0.`, "danger");
      return;
    }
  }

  try {
    const response = await fetchConCSRF(
      `/api/scoring/linea/${lineaSeleccionadaId}/criterios`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          criterios: configScoringLinea.criterios,
        }),
      }
    );

    const data = await response.json();

    if (data.success) {
      mostrarAlertaScoring("Criterios guardados exitosamente", "success");
    } else {
      mostrarAlertaScoring(`Error: ${data.error}`, "danger");
    }
  } catch (error) {
    console.error("Error guardando criterios:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  }
}
