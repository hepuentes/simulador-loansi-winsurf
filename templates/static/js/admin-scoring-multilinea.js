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
  }
});

/**
 * Inicializa el selector de línea de crédito
 */
async function initSelectorLineaCredito() {
  console.log("🔄 Cargando líneas de crédito para scoring...");

  try {
    const response = await fetch("/api/scoring/lineas-credito", {
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
                <span class="badge bg-light text-primary fw-bold border border-primary" id="badgeLineaActual" style="font-size: 0.9rem;">Sin seleccionar</span>
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
                                    (Score min: ${l.score_datacredito_minimo || "N/A"
          })
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
    const response = await fetch(`/api/scoring/linea/${lineaId}/config`, {
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

      // Actualizar info de línea
      actualizarInfoLinea(data.config);

      // Renderizar contenido de las pestañas (nueva estructura)
      renderNivelesRiesgoLinea(data.config.niveles_riesgo);
      renderAprobacionLinea(data.config.config_general, data.config.factores_rechazo);
      renderCriteriosLinea(data.config.criterios);

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
    <div class="mb-3 d-flex justify-content-between align-items-center">
      <h6 class="mb-0">
        <i class="bi bi-bar-chart-steps me-2"></i>Niveles de Riesgo y Tasas Diferenciadas
        <span class="badge bg-primary text-white ms-2">${lineaSeleccionadaNombre}</span>
      </h6>
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
                    <div class="card-header d-flex justify-content-between align-items-center" style="background-color: ${nivel.color};">
                        <input type="text" class="form-control form-control-sm fw-bold flex-grow-1 me-2"
                               value="${nivel.nombre}"
                               onchange="actualizarNivelLinea(${index}, 'nombre', this.value)"
                               style="background: transparent; border: none;">
                        <button type="button" class="btn btn-sm btn-outline-danger" 
                                onclick="eliminarNivelRiesgoLinea(${index})" title="Eliminar nivel">
                            <i class="bi bi-trash"></i>
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
            <button type="button" class="btn btn-outline-secondary me-2" 
                    onclick="refrescarConfigLinea()">
                <i class="bi bi-arrow-clockwise me-1"></i>Cancelar cambios
            </button>
            <button type="button" class="btn btn-primary" 
                    onclick="guardarNivelesRiesgoLinea()">
                <i class="bi bi-check-lg me-1"></i>Guardar niveles de riesgo
            </button>
        </div>
    `;

  container.innerHTML = html;
}

/**
 * Actualiza un campo de nivel de riesgo en memoria
 */
function actualizarNivelLinea(index, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.niveles_riesgo) return;

  if (
    campo === "min" ||
    campo === "max" ||
    campo === "tasa_ea" ||
    campo === "tasa_nominal_mensual" ||
    campo === "aval_porcentaje"
  ) {
    valor = parseFloat(valor);
  }

  configScoringLinea.niveles_riesgo[index][campo] = valor;

  // Si cambió la tasa EA, calcular automáticamente la tasa nominal mensual
  if (campo === "tasa_ea") {
    const tasaEA = valor / 100; // Convertir a decimal
    // Fórmula: tasa_nominal_mensual = ((1 + tasa_ea)^(1/12) - 1) * 100
    const tasaNominalMensual = (Math.pow(1 + tasaEA, 1 / 12) - 1) * 100;
    configScoringLinea.niveles_riesgo[index].tasa_nominal_mensual = parseFloat(tasaNominalMensual.toFixed(4));
    // Re-renderizar para mostrar el nuevo valor
    renderNivelesRiesgoLinea(configScoringLinea.niveles_riesgo);
  }

  // Si cambió el color, actualizar visualmente
  if (campo === "color") {
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
    const response = await fetch(
      `/api/scoring/linea/${lineaSeleccionadaId}/niveles-riesgo`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({
          niveles: configScoringLinea.niveles_riesgo,
        }),
      }
    );

    const data = await response.json();

    if (data.success) {
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
// RENDERIZADO DE FACTORES DE RECHAZO
// ============================================================================

/**
 * Renderiza los factores de rechazo para la línea seleccionada
 */
function renderFactoresRechazoLinea(factores) {
  const container = document.getElementById("factoresRechazoLineaContainer");
  if (!container) return;

  let html = `
        <div class="mb-3 d-flex justify-content-between align-items-center">
            <h6 class="mb-0">
                <i class="bi bi-shield-x me-2"></i>Factores de rechazo automático 
                <span class="badge bg-secondary">${factores?.length || 0}</span>
            </h6>
            <button type="button" class="btn btn-sm btn-outline-primary" 
                    onclick="agregarFactorRechazoLinea()">
                <i class="bi bi-plus-lg me-1"></i>Agregar factor
            </button>
        </div>
    `;

  if (!factores || factores.length === 0) {
    html += `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i>
                No hay factores de rechazo configurados para esta línea.
            </div>
        `;
  } else {
    html += `
            <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead class="table-dark">
                        <tr>
                            <th style="width: 25%;">Criterio</th>
                            <th style="width: 15%;">Operador</th>
                            <th style="width: 15%;">Valor</th>
                            <th style="width: 35%;">Mensaje de rechazo</th>
                            <th style="width: 10%;" class="text-center">Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

    factores.forEach((factor, index) => {
      html += `
                <tr data-factor-id="${factor.id || index}">
                    <td>
                        <input type="text" class="form-control form-control-sm"
                               value="${factor.criterio_nombre || factor.criterio
        }"
                               onchange="actualizarFactorLinea(${index}, 'criterio_nombre', this.value)"
                               data-criterio-key="${factor.criterio}">
                    </td>
                    <td>
                        <select class="form-select form-select-sm"
                                onchange="actualizarFactorLinea(${index}, 'operador', this.value)">
                            <option value="<" ${factor.operador === "<" ? "selected" : ""
        }>< menor que</option>
                            <option value="<=" ${factor.operador === "<=" ? "selected" : ""
        }>≤ menor o igual</option>
                            <option value=">" ${factor.operador === ">" ? "selected" : ""
        }>> mayor que</option>
                            <option value=">=" ${factor.operador === ">=" ? "selected" : ""
        }>≥ mayor o igual</option>
                            <option value="=" ${factor.operador === "=" ? "selected" : ""
        }}>= igual a</option>
                        </select>
                    </td>
                    <td>
                        <input type="number" class="form-control form-control-sm"
                               value="${factor.valor}"
                               onchange="actualizarFactorLinea(${index}, 'valor', this.value)">
                    </td>
                    <td>
                        <input type="text" class="form-control form-control-sm"
                               value="${factor.mensaje || ""}"
                               onchange="actualizarFactorLinea(${index}, 'mensaje', this.value)">
                    </td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm btn-outline-danger"
                                onclick="eliminarFactorLinea(${index})" title="Eliminar">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
    });

    html += `
                    </tbody>
                </table>
            </div>
        `;
  }

  // Botón guardar
  html += `
        <div class="mt-3 text-end">
            <button type="button" class="btn btn-primary" 
                    onclick="guardarFactoresRechazoLinea()">
                <i class="bi bi-check-lg me-1"></i>Guardar factores de rechazo
            </button>
        </div>
    `;

  container.innerHTML = html;
}

/**
 * Actualiza un campo de factor de rechazo en memoria
 */
function actualizarFactorLinea(index, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;

  if (campo === "valor") {
    valor = parseFloat(valor);
  }

  configScoringLinea.factores_rechazo[index][campo] = valor;
}

/**
 * Agrega un nuevo factor de rechazo
 */
function agregarFactorRechazoLinea() {
  if (!configScoringLinea) return;

  if (!configScoringLinea.factores_rechazo) {
    configScoringLinea.factores_rechazo = [];
  }

  configScoringLinea.factores_rechazo.push({
    criterio: "nuevo_criterio",
    criterio_nombre: "Nuevo criterio",
    operador: "<",
    valor: 0,
    mensaje: "Mensaje de rechazo",
    activo: true,
  });

  renderFactoresRechazoLinea(configScoringLinea.factores_rechazo);
}

/**
 * Elimina un factor de rechazo
 */
function eliminarFactorLinea(index) {
  if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;

  if (confirm("¿Está seguro de eliminar este factor de rechazo?")) {
    configScoringLinea.factores_rechazo.splice(index, 1);
    renderFactoresRechazoLinea(configScoringLinea.factores_rechazo);
  }
}

/**
 * Guarda los factores de rechazo de la línea
 */
async function guardarFactoresRechazoLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  try {
    const response = await fetch(
      `/api/scoring/linea/${lineaSeleccionadaId}/factores-rechazo`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
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
function agregarFactorRechazoLinea() {
  if (!configScoringLinea) return;

  if (!configScoringLinea.factores_rechazo) {
    configScoringLinea.factores_rechazo = [];
  }

  configScoringLinea.factores_rechazo.push({
    criterio_nombre: "Nuevo Factor",
    criterio: "nuevo_factor",
    operador: "<",
    valor: 0,
    mensaje: "Mensaje de rechazo"
  });

  renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
  mostrarAlertaScoring("Factor agregado. Recuerde guardar los cambios.", "info");
}

/**
 * Actualiza un factor de rechazo en memoria
 */
function actualizarFactorLinea(index, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;

  if (campo === 'valor') {
    valor = parseFloat(valor);
  }

  configScoringLinea.factores_rechazo[index][campo] = valor;
}

/**
 * Elimina un factor de rechazo de la lista
 */
function eliminarFactorLinea(index) {
  if (!configScoringLinea || !configScoringLinea.factores_rechazo) return;

  if (confirm("¿Está seguro de eliminar este factor de rechazo?")) {
    configScoringLinea.factores_rechazo.splice(index, 1);
    renderAprobacionLinea(configScoringLinea.config_general, configScoringLinea.factores_rechazo);
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
      <div class="col-md-6">
        <div class="card mb-3 border-success">
          <div class="card-header bg-success text-white">
            <i class="bi bi-check-circle me-2"></i>Parámetros de Aprobación
          </div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label fw-bold">Puntaje mínimo para aprobación</label>
              <input type="number" class="form-control" id="cfgPuntajeMinimo"
                     value="${cg.puntaje_minimo_aprobacion || 17}" min="0" max="100"
                     onchange="actualizarConfigAprobacion('puntaje_minimo_aprobacion', this.value)">
              <small class="text-muted">Clientes con puntaje ≥ a este valor serán <strong>aprobados automáticamente</strong></small>
            </div>
            <div class="mb-3">
              <label class="form-label fw-bold">Puntaje para revisión manual (Comité)</label>
              <input type="number" class="form-control" id="cfgPuntajeRevision"
                     value="${cg.puntaje_revision_manual || 10}" min="0" max="100"
                     onchange="actualizarConfigAprobacion('puntaje_revision_manual', this.value)">
              <small class="text-muted">Puntaje entre este valor y el mínimo va a <strong>comité de crédito</strong></small>
            </div>
            <div class="alert alert-info py-2 mb-0">
              <small>
                <i class="bi bi-info-circle me-1"></i>
                <strong>Lógica:</strong> Puntaje ≥ ${cg.puntaje_minimo_aprobacion || 17} = Aprobado | 
                Puntaje ${cg.puntaje_revision_manual || 10}-${(cg.puntaje_minimo_aprobacion || 17) - 1} = Comité |
                Puntaje < ${cg.puntaje_revision_manual || 10} = Rechazado
              </small>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Umbrales de Rechazo Automático -->
      <div class="col-md-6">
        <div class="card mb-3 border-danger">
          <div class="card-header bg-danger text-white">
            <i class="bi bi-shield-x me-2"></i>Umbrales de Rechazo Automático
          </div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label fw-bold">Score DataCrédito mínimo</label>
              <input type="number" class="form-control" id="cfgScoreMin"
                     value="${cg.score_datacredito_minimo || 400}" min="150" max="900"
                     onchange="actualizarConfigAprobacion('score_datacredito_minimo', this.value)">
              <small class="text-muted">Por debajo de este score = <strong>rechazo automático</strong></small>
            </div>
            <div class="mb-3">
              <label class="form-label fw-bold">Umbral mora telcos ($)</label>
              <div class="input-group">
                <span class="input-group-text">$</span>
                <input type="number" class="form-control" id="cfgMoraTelcos"
                       value="${cg.umbral_mora_telcos || 200000}" min="0" step="10000"
                       onchange="actualizarConfigAprobacion('umbral_mora_telcos', this.value)">
              </div>
              <small class="text-muted">Mora superior a este monto = <strong>rechazo automático</strong></small>
            </div>
            <div class="row">
              <div class="col-6 mb-3">
                <label class="form-label fw-bold">Edad mínima</label>
                <input type="number" class="form-control" id="cfgEdadMin"
                       value="${cg.edad_minima || 18}" min="18" max="99"
                       onchange="actualizarConfigAprobacion('edad_minima', this.value)">
              </div>
              <div class="col-6 mb-3">
                <label class="form-label fw-bold">Edad máxima</label>
                <input type="number" class="form-control" id="cfgEdadMax"
                       value="${cg.edad_maxima || 84}" min="18" max="99"
                       onchange="actualizarConfigAprobacion('edad_maxima', this.value)">
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label fw-bold">DTI máximo (%)</label>
              <div class="input-group">
                <input type="number" class="form-control" id="cfgDTI"
                       value="${cg.dti_maximo || 50}" min="10" max="100"
                       onchange="actualizarConfigAprobacion('dti_maximo', this.value)">
                <span class="input-group-text">%</span>
              </div>
              <small class="text-muted">Relación deuda/ingreso máxima permitida</small>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Factores de Rechazo Personalizados -->
    <div class="card mb-3 border-warning">
      <div class="card-header bg-warning text-dark d-flex justify-content-between align-items-center">
        <span><i class="bi bi-exclamation-triangle me-2"></i>Factores de Rechazo Personalizados</span>
        <button type="button" class="btn btn-sm btn-dark" onclick="agregarFactorRechazoLinea()">
          <i class="bi bi-plus-lg me-1"></i>Agregar Factor
        </button>
      </div>
      <div class="card-body">
        ${factoresArr.length === 0 ? `
          <div class="text-center text-muted py-3">
            <i class="bi bi-inbox fs-1 d-block mb-2"></i>
            No hay factores de rechazo personalizados.
            <br><small>Use el botón "Agregar Factor" para crear condiciones de rechazo específicas.</small>
          </div>
        ` : `
          <div class="table-responsive">
            <table class="table table-sm table-hover">
              <thead class="table-dark">
                <tr>
                  <th>Criterio</th>
                  <th>Operador</th>
                  <th>Valor</th>
                  <th>Mensaje de rechazo</th>
                  <th class="text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>
                ${factoresArr.map((f, i) => `
                  <tr>
                    <td>
                      <input type="text" class="form-control form-control-sm"
                             value="${f.criterio_nombre || f.criterio}"
                             onchange="actualizarFactorLinea(${i}, 'criterio_nombre', this.value)">
                    </td>
                    <td>
                      <select class="form-select form-select-sm" onchange="actualizarFactorLinea(${i}, 'operador', this.value)">
                        <option value="<" ${f.operador === '<' ? 'selected' : ''}>< menor</option>
                        <option value="<=" ${f.operador === '<=' ? 'selected' : ''}>≤ menor o igual</option>
                        <option value=">" ${f.operador === '>' ? 'selected' : ''}>> mayor</option>
                        <option value=">=" ${f.operador === '>=' ? 'selected' : ''}>≥ mayor o igual</option>
                        <option value="=" ${f.operador === '=' ? 'selected' : ''}}>= igual</option>
                      </select>
                    </td>
                    <td>
                      <input type="number" class="form-control form-control-sm"
                             value="${f.valor}" onchange="actualizarFactorLinea(${i}, 'valor', this.value)">
                    </td>
                    <td>
                      <input type="text" class="form-control form-control-sm"
                             value="${f.mensaje || ''}" onchange="actualizarFactorLinea(${i}, 'mensaje', this.value)">
                    </td>
                    <td class="text-center">
                      <button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarFactorLinea(${i})">
                        <i class="bi bi-trash"></i>
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    </div>
    
    <div class="text-end">
      <button type="button" class="btn btn-outline-secondary me-2" onclick="refrescarConfigLinea()">
        <i class="bi bi-arrow-clockwise me-1"></i>Cancelar cambios
      </button>
      <button type="button" class="btn btn-primary" onclick="guardarAprobacionLinea()">
        <i class="bi bi-check-lg me-1"></i>Guardar Configuración de Aprobación
      </button>
    </div>
  `;

  container.innerHTML = html;
}

/**
 * Actualiza un campo de configuración de aprobación en memoria
 */
function actualizarConfigAprobacion(campo, valor) {
  if (!configScoringLinea) return;
  if (!configScoringLinea.config_general) {
    configScoringLinea.config_general = {};
  }
  configScoringLinea.config_general[campo] = parseFloat(valor);
}

/**
 * Guarda la configuración de aprobación (config general + factores de rechazo)
 */
async function guardarAprobacionLinea() {
  if (!lineaSeleccionadaId || !configScoringLinea) {
    mostrarAlertaScoring("No hay línea seleccionada", "warning");
    return;
  }

  try {
    // Guardar configuración general
    const responseConfig = await fetch(
      `/api/scoring/linea/${lineaSeleccionadaId}/config`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({
          config_general: configScoringLinea.config_general,
        }),
      }
    );

    // Guardar factores de rechazo
    const responseFactores = await fetch(
      `/api/scoring/linea/${lineaSeleccionadaId}/factores-rechazo`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
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
    } else {
      mostrarAlertaScoring(`Error: ${dataConfig.error || dataFactores.error}`, "danger");
    }
  } catch (error) {
    console.error("Error guardando configuración:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
  }
}

// ============================================================================
// RENDERIZADO DE CRITERIOS DE SCORING
// ============================================================================

/**
 * Renderiza los criterios de scoring para la línea
 */
function renderCriteriosLinea(criterios, openIndex = 0) {
  const container = document.getElementById("criteriosLineaContainer");
  if (!container) return;

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

  // Calcular suma de pesos
  const sumaPesos = criteriosArray.reduce((sum, c) => sum + (parseFloat(c.peso) || 0), 0);

  let html = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div>
        <h5 class="mb-0">
          <i class="bi bi-list-check me-2"></i>Criterios de Evaluación
          <span class="badge bg-primary ms-2">${lineaSeleccionadaNombre}</span>
        </h5>
        <small class="text-muted">Los criterios determinan el puntaje del cliente. Los pesos deben sumar 100%.</small>
      </div>
      <div>
        <span class="badge ${sumaPesos === 100 ? 'bg-success' : 'bg-danger'} fs-6">
          Suma de pesos: ${sumaPesos.toFixed(1)}%
        </span>
        <button type="button" class="btn btn-success ms-2" onclick="agregarCriterioLinea()">
          <i class="bi bi-plus-lg me-1"></i>Agregar Criterio
        </button>
      </div>
    </div>
    
    ${sumaPesos !== 100 ? `
      <div class="alert alert-warning">
        <i class="bi bi-exclamation-triangle me-2"></i>
        <strong>Atención:</strong> Los pesos de los criterios deben sumar exactamente 100%. 
        Actualmente suman ${sumaPesos.toFixed(1)}%.
      </div>
    ` : ''}
  `;

  if (criteriosArray.length === 0) {
    html += `
      <div class="alert alert-info">
        <i class="bi bi-info-circle me-2"></i>
        No hay criterios de scoring configurados para esta línea.
        <br><br>
        <button type="button" class="btn btn-primary" onclick="crearCriteriosPorDefecto()">
          <i class="bi bi-magic me-1"></i>Crear criterios por defecto
        </button>
      </div>
    `;
  } else {
    // Mostrar criterios en acordeón
    html += `<div class="accordion" id="accordionCriterios">`;

    criteriosArray.forEach((criterio, index) => {
      const rangos = criterio.rangos || [];
      const tieneRangos = rangos.length > 0;

      html += `
        <div class="accordion-item">
          <h2 class="accordion-header">
            <button class="accordion-button ${index !== openIndex ? 'collapsed' : ''}" type="button" 
                    data-bs-toggle="collapse" data-bs-target="#criterio${index}">
              <div class="d-flex justify-content-between align-items-center w-100 me-3">
                <span>
                  <span class="badge bg-primary me-2">${criterio.peso || 0}%</span>
                  <strong>${criterio.nombre || criterio.codigo}</strong>
                  ${criterio.descripcion ? `<small class="text-muted ms-2">- ${criterio.descripcion}</small>` : ''}
                </span>
                <span>
                  <span class="badge ${tieneRangos ? 'bg-success' : 'bg-secondary'}">${rangos.length} rangos</span>
                </span>
              </div>
            </button>
          </h2>
          <div id="criterio${index}" class="accordion-collapse collapse ${index === openIndex ? 'show' : ''}">
            <div class="accordion-body">
              <div class="row mb-3">
                <div class="col-md-4">
                  <label class="form-label">Nombre</label>
                  <input type="text" class="form-control" value="${criterio.nombre || ''}"
                         onchange="actualizarCriterioLinea(${index}, 'nombre', this.value)">
                </div>
                <div class="col-md-2">
                  <label class="form-label">Peso (%)</label>
                  <input type="number" class="form-control" value="${criterio.peso || 0}" min="0" max="100"
                         onchange="actualizarCriterioLinea(${index}, 'peso', this.value)">
                </div>
                <div class="col-md-4">
                  <label class="form-label">Descripción</label>
                  <input type="text" class="form-control" value="${criterio.descripcion || ''}"
                         onchange="actualizarCriterioLinea(${index}, 'descripcion', this.value)">
                </div>
                <div class="col-md-2 d-flex align-items-end">
                  <button type="button" class="btn btn-outline-danger w-100" onclick="eliminarCriterioLinea(${index})">
                    <i class="bi bi-trash me-1"></i>Eliminar
                  </button>
                </div>
              </div>
              
              <h6><i class="bi bi-rulers me-2"></i>Rangos de Puntuación</h6>
              ${tieneRangos ? `
                <div class="table-responsive">
                  <table class="table table-sm table-bordered">
                    <thead class="table-primary">
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
                          <td><input type="number" class="form-control form-control-sm" value="${r.min}" 
                                     onchange="actualizarRangoCriterio(${index}, ${ri}, 'min', this.value)"></td>
                          <td><input type="number" class="form-control form-control-sm" value="${r.max}"
                                     onchange="actualizarRangoCriterio(${index}, ${ri}, 'max', this.value)"></td>
                          <td><input type="number" class="form-control form-control-sm" value="${r.puntos}"
                                     onchange="actualizarRangoCriterio(${index}, ${ri}, 'puntos', this.value)"></td>
                          <td><input type="text" class="form-control form-control-sm" value="${r.descripcion || ''}"
                                     onchange="actualizarRangoCriterio(${index}, ${ri}, 'descripcion', this.value)"></td>
                          <td class="text-center">
                            <button type="button" class="btn btn-sm btn-outline-danger" 
                                    onclick="eliminarRangoCriterio(${index}, ${ri})">
                              <i class="bi bi-trash"></i>
                            </button>
                          </td>
                        </tr>
                      `).join('')}
                    </tbody>
                  </table>
                </div>
              ` : `
                <div class="text-center text-muted py-2">
                  <small>No hay rangos configurados</small>
                </div>
              `}
              <button type="button" class="btn btn-sm btn-outline-success" onclick="agregarRangoCriterio(${index})">
                <i class="bi bi-plus me-1"></i>Agregar Rango
              </button>

              <!-- Fuente de Datos: Extracción Automática -->
              <hr class="mt-3">
              <div class="mt-2">
                <button class="btn btn-sm btn-outline-secondary w-100 text-start" 
                        type="button"
                        data-bs-toggle="collapse" 
                        data-bs-target="#extraccion${index}"
                        aria-expanded="false">
                  📥 Fuente de Datos (extracción automática)
                  ${criterio.activo_extraccion ? 
                    '<span class="badge bg-success ms-2">Activa</span>' : 
                    '<span class="badge bg-secondary ms-2">Inactiva</span>'}
                </button>
                <div class="collapse" id="extraccion${index}">
                  <div class="card card-body mt-2 bg-dark border-secondary">
                    
                    <div class="mb-2">
                      <label class="form-label small text-muted">Fuente de extracción</label>
                      <select class="form-select form-select-sm"
                              id="fuente_${index}"
                              onchange="actualizarExtraccion(${index}, 'fuente', this.value)">
                        <option value="">-- Sin extracción automática --</option>
                      </select>
                    </div>
                    
                    <div class="mb-2" id="cont_instruccion_${index}" 
                         style="display:${criterio.fuente_extraccion && criterio.fuente_extraccion !== 'formulario_manual' ? 'block' : 'none'}">
                      <label class="form-label small text-muted">Instrucción para la IA</label>
                      <textarea class="form-control form-control-sm" rows="3"
                                maxlength="3000"
                                placeholder="Describe qué debe buscar la IA en este documento."
                                onchange="actualizarExtraccion(${index}, 'instruccion', this.value)"
                      >${criterio.instruccion_extraccion || ''}</textarea>
                      <div class="text-end"><small class="text-muted">${(criterio.instruccion_extraccion || '').length}/3000</small></div>
                    </div>
                    
                    <div class="form-check form-switch" 
                         id="cont_activo_${index}"
                         style="display:${criterio.fuente_extraccion ? 'block' : 'none'}">
                      <input class="form-check-input" type="checkbox"
                             id="activo_${index}"
                             ${criterio.activo_extraccion ? 'checked' : ''}
                             onchange="actualizarExtraccion(${index}, 'activo', this.checked)">
                      <label class="form-check-label small" for="activo_${index}">
                        Activar extracción automática
                      </label>
                    </div>
                    
                    <div id="chip_api_${index}" style="display:none">
                      <span class="badge bg-warning text-dark mt-1">
                        ⚠ Requiere integración API configurada
                      </span>
                    </div>
                    
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
  }

  html += `
    <div class="text-end mt-3">
      <button type="button" class="btn btn-outline-secondary me-2" onclick="refrescarConfigLinea()">
        <i class="bi bi-arrow-clockwise me-1"></i>Cancelar cambios
      </button>
      <button type="button" class="btn btn-primary" onclick="guardarCriteriosLinea()">
        <i class="bi bi-check-lg me-1"></i>Guardar Criterios
      </button>
    </div>
  `;

  container.innerHTML = html;

  // Poblar selects de fuente de extracción
  fetch('/api/fuentes-extraccion')
    .then(r => r.json())
    .then(data => {
      if (!data.success || !data.fuentes) return;
      const fuentes = data.fuentes;

      // Clasificar fuentes por tipo
      const documentos = [];
      const apis = [];
      const manuales = [];
      for (const [key, info] of Object.entries(fuentes)) {
        const item = { valor: key, label: info.label, tipo: info.tipo };
        if (info.tipo === 'documento') documentos.push(item);
        else if (info.tipo === 'api') apis.push(item);
        else manuales.push(item);
      }

      criteriosArray.forEach((criterio, index) => {
        const select = document.getElementById(`fuente_${index}`);
        if (!select) return;

        select.innerHTML = '<option value="">-- Sin extracción automática --</option>';

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

        // Mostrar chip API si aplica
        const chipApi = document.getElementById(`chip_api_${index}`);
        if (chipApi && criterio.fuente_extraccion) {
          const fuenteInfo = fuentes[criterio.fuente_extraccion];
          chipApi.style.display = (fuenteInfo && fuenteInfo.tipo === 'api') ? 'block' : 'none';
        }
      });
    }).catch(err => console.warn('No se pudieron cargar fuentes de extracción:', err));
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
            ${mensaje}
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
            <div class="alert alert-info">
              <i class="bi bi-info-circle me-2"></i>
              Esta acción copiará niveles de riesgo, factores de rechazo y configuración general.
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
            <div class="form-check">
              <input type="checkbox" class="form-check-input" id="chkIncluirCriterios" checked>
              <label class="form-check-label" for="chkIncluirCriterios">
                Incluir criterios y pesos
              </label>
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
  const incluirCriterios = document.getElementById(
    "chkIncluirCriterios"
  ).checked;

  if (!origenId || !destinoId) {
    mostrarAlertaScoring("Seleccione las líneas", "warning");
    return;
  }

  try {
    const response = await fetch("/api/scoring/copiar-config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRFToken(),
      },
      body: JSON.stringify({
        linea_origen_id: parseInt(origenId),
        linea_destino_id: parseInt(destinoId),
        incluir_criterios: incluirCriterios,
      }),
    });

    const data = await response.json();

    if (data.success) {
      bootstrap.Modal.getInstance(
        document.getElementById("copiarConfigModal")
      ).hide();
      mostrarAlertaScoring("Configuración copiada exitosamente", "success");
      // Recargar configuración
      await refrescarConfigLinea();
    } else {
      mostrarAlertaScoring(`Error: ${data.error}`, "danger");
    }
  } catch (error) {
    console.error("Error copiando config:", error);
    mostrarAlertaScoring("Error de conexión", "danger");
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

  const numCriterios = configScoringLinea.criterios.length;

  configScoringLinea.criterios.push({
    codigo: `criterio_${Date.now()}`,
    nombre: `Nuevo Criterio ${numCriterios + 1}`,
    descripcion: "",
    peso: 10,
    tipo_campo: "numerico",
    rangos: []
  });

  renderCriteriosLinea(configScoringLinea.criterios);
  mostrarAlertaScoring("Criterio agregado. Recuerde guardar los cambios.", "info");
}

/**
 * Actualiza un campo de criterio en memoria
 */
function actualizarCriterioLinea(index, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  if (campo === 'peso') {
    valor = parseFloat(valor);
  }

  configScoringLinea.criterios[index][campo] = valor;

  // Re-renderizar para actualizar la suma de pesos
  if (campo === 'peso') {
    renderCriteriosLinea(configScoringLinea.criterios);
  }
}

/**
 * Actualiza campos de extracción automática de un criterio en memoria
 */
function actualizarExtraccion(index, campo, valor) {
  const criterios = configScoringLinea.criterios;
  if (!criterios || !criterios[index]) return;

  if (campo === 'fuente') {
    criterios[index].fuente_extraccion = valor || null;
    // Mostrar/ocultar campos dependientes
    const contInst = document.getElementById(`cont_instruccion_${index}`);
    const contActivo = document.getElementById(`cont_activo_${index}`);
    const chipApi = document.getElementById(`chip_api_${index}`);
    if (contInst) contInst.style.display = (valor && valor !== 'formulario_manual') ? 'block' : 'none';
    if (contActivo) contActivo.style.display = valor ? 'block' : 'none';
    cargarChipApi(index, valor, chipApi);
  } else if (campo === 'instruccion') {
    criterios[index].instruccion_extraccion = valor || null;
  } else if (campo === 'activo') {
    criterios[index].activo_extraccion = valor ? 1 : 0;
  }
}

/**
 * Muestra/oculta chip de advertencia API según tipo de fuente
 */
function cargarChipApi(index, fuente, chipElement) {
  if (!chipElement) return;
  fetch('/api/fuentes-extraccion')
    .then(r => r.json())
    .then(data => {
      const todas = [...(data.documentos || []), ...(data.apis || []), ...(data.manual || [])];
      const encontrada = todas.find(f => f.valor === fuente);
      chipElement.style.display = (encontrada && encontrada.tipo === 'api') ? 'block' : 'none';
    }).catch(() => {});
}

/**
 * Elimina un criterio de la línea
 */
function eliminarCriterioLinea(index) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  const criterio = configScoringLinea.criterios[index];
  if (confirm(`¿Está seguro de eliminar el criterio "${criterio.nombre}"?`)) {
    configScoringLinea.criterios.splice(index, 1);
    renderCriteriosLinea(configScoringLinea.criterios);
    mostrarAlertaScoring("Criterio eliminado. Recuerde guardar los cambios.", "info");
  }
}

/**
 * Agrega un rango a un criterio
 */
function agregarRangoCriterio(criterioIndex) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  if (!configScoringLinea.criterios[criterioIndex].rangos) {
    configScoringLinea.criterios[criterioIndex].rangos = [];
  }

  configScoringLinea.criterios[criterioIndex].rangos.push({
    min: 0,
    max: 100,
    puntos: 10,
    descripcion: "Nuevo rango"
  });

  renderCriteriosLinea(configScoringLinea.criterios, criterioIndex);
}

/**
 * Actualiza un rango de criterio
 */
function actualizarRangoCriterio(criterioIndex, rangoIndex, campo, valor) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  if (campo === 'min' || campo === 'max' || campo === 'puntos') {
    valor = parseFloat(valor);
  }

  configScoringLinea.criterios[criterioIndex].rangos[rangoIndex][campo] = valor;
}

/**
 * Elimina un rango de criterio
 */
function eliminarRangoCriterio(criterioIndex, rangoIndex) {
  if (!configScoringLinea || !configScoringLinea.criterios) return;

  if (confirm("¿Está seguro de eliminar este rango?")) {
    configScoringLinea.criterios[criterioIndex].rangos.splice(rangoIndex, 1);
    renderCriteriosLinea(configScoringLinea.criterios, criterioIndex);
  }
}

/**
 * Crea criterios por defecto para la línea
 */
function crearCriteriosPorDefecto() {
  if (!configScoringLinea) return;

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

  // Validar que los pesos sumen 100
  const criterios = configScoringLinea.criterios || [];
  const sumaPesos = criterios.reduce((sum, c) => sum + (parseFloat(c.peso) || 0), 0);

  if (Math.abs(sumaPesos - 100) > 0.1) {
    mostrarAlertaScoring(`Los pesos deben sumar 100%. Actualmente suman ${sumaPesos.toFixed(1)}%`, "danger");
    return;
  }

  try {
    const response = await fetch(
      `/api/scoring/linea/${lineaSeleccionadaId}/criterios`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
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
