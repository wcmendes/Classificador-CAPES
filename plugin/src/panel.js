/**
 * NoQualis - Item Pane Section
 *
 * Registers a section in Zotero's item pane via
 * ItemPaneManager.registerSection, showing:
 * - Verdict (stratum + state) with color coding
 * - Full decision trail
 * - Source metrics with dates
 * - Historical Qualis with cycle label (task 10.8)
 *
 * Three distinct visual states:
 * - COMPLETO: green (#2e7d32)
 * - ESTIMATIVA_CONSERVADORA: yellow/amber (#f9a825)
 * - NAO_CLASSIFICAVEL: gray (#757575)
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 */

/* global Zotero, NoQualisSnapshotLoader, NoQualisEvaluator */

var NoQualisPanel = {
  /** @type {string|null} Registered section ID */
  _sectionId: null,

  /**
   * Initialize the panel section.
   */
  init() {
    this._registerSection();
  },

  /**
   * Register the item pane section.
   */
  _registerSection() {
    try {
      this._sectionId = Zotero.ItemPaneManager.registerSection({
        paneID: "noqualis-classification",
        pluginID: "noqualis@wcmendes.github.io",
        header: {
          label: "NoQualis — Classificação CAPES",
          icon: "chrome://zotero/skin/16/universal/book.svg"
        },
        sidenav: {
          label: "NoQualis",
          icon: "chrome://zotero/skin/16/universal/book.svg"
        },
        bodyXHTML: "",
        onRender: ({ body, item }) => {
          this._renderPanel(body, item);
        },
        onItemChange: ({ body, item }) => {
          this._renderPanel(body, item);
        }
      });

      Zotero.log("[NoQualis] Registered item pane section", "info");
    } catch (e) {
      Zotero.log(`[NoQualis] Failed to register pane section: ${e.message}`, "error");
    }
  },

  /**
   * Render the panel content for a given item.
   * @param {HTMLElement} body - Panel body element
   * @param {object} item - Zotero item
   */
  _renderPanel(body, item) {
    // Clear existing content
    while (body.firstChild) {
      body.removeChild(body.firstChild);
    }

    if (!item || !item.isRegularItem || !item.isRegularItem()) {
      body.appendChild(this._createText("Selecione um item regular."));
      return;
    }

    const selectedAreas = this._getSelectedAreas();
    if (selectedAreas.length === 0) {
      body.appendChild(this._createText(
        "Nenhuma área selecionada. Configure nas preferências do NoQualis."
      ));
      return;
    }

    const container = body.ownerDocument.createElement("div");
    container.style.padding = "8px";
    container.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    container.style.fontSize = "12px";
    container.style.lineHeight = "1.5";

    // Render verdict for each active area
    for (const areaCode of selectedAreas) {
      const snapshot = NoQualisSnapshotLoader.getSnapshot(areaCode);
      if (!snapshot) continue;

      const verdict = NoQualisEvaluator.evaluate(item, areaCode);
      const areaName = snapshot.nome || `Área ${areaCode}`;

      const areaSection = this._renderAreaVerdict(
        body.ownerDocument, areaName, areaCode, verdict, snapshot
      );
      container.appendChild(areaSection);
    }

    // Render historical Qualis section (task 10.8)
    const historicalSection = this._renderHistoricalSection(body.ownerDocument, item);
    if (historicalSection) {
      container.appendChild(historicalSection);
    }

    // Link to LIMITATIONS.md
    const limitsLink = this._createLimitationsLink(body.ownerDocument);
    container.appendChild(limitsLink);

    body.appendChild(container);
  },

  /**
   * Render the verdict section for one area.
   * @param {Document} doc
   * @param {string} areaName
   * @param {number} areaCode
   * @param {object} verdict
   * @param {object} snapshot
   * @returns {HTMLElement}
   */
  _renderAreaVerdict(doc, areaName, areaCode, verdict, snapshot) {
    const section = doc.createElement("div");
    section.style.marginBottom = "12px";
    section.style.borderRadius = "4px";
    section.style.padding = "8px";
    section.style.border = "1px solid #e0e0e0";

    // Header with area name
    const header = doc.createElement("div");
    header.style.fontWeight = "bold";
    header.style.marginBottom = "6px";
    header.style.fontSize = "13px";
    header.textContent = areaName;

    // Status badge with area status
    if (snapshot.status === "experimental") {
      const badge = doc.createElement("span");
      badge.style.fontSize = "10px";
      badge.style.marginLeft = "6px";
      badge.style.padding = "1px 4px";
      badge.style.borderRadius = "3px";
      badge.style.backgroundColor = "#fff3e0";
      badge.style.color = "#e65100";
      badge.textContent = "experimental";
      header.appendChild(badge);
    }

    section.appendChild(header);

    // Verdict display with color coding
    const verdictEl = this._renderVerdictBadge(doc, verdict);
    section.appendChild(verdictEl);

    // Obsolescence warning
    const obsInfo = NoQualisSnapshotLoader.getObsolescenceInfo(areaCode);
    if (obsInfo) {
      const warning = doc.createElement("div");
      warning.style.color = "#e65100";
      warning.style.fontSize = "11px";
      warning.style.marginTop = "4px";
      warning.textContent = `⚠ Dados com ${obsInfo.days} dias (snapshot: ${obsInfo.date})`;
      section.appendChild(warning);
    }

    // Decision trail
    if (verdict.trilha && verdict.trilha.length > 0) {
      const trailSection = this._renderTrail(doc, verdict.trilha);
      section.appendChild(trailSection);
    }

    // Source metrics with dates
    if (verdict.metricas_utilizadas && Object.keys(verdict.metricas_utilizadas).length > 0) {
      const metricsSection = this._renderMetrics(doc, verdict.metricas_utilizadas);
      section.appendChild(metricsSection);
    }

    // Missing metrics
    if (verdict.metricas_ausentes && verdict.metricas_ausentes.length > 0) {
      const missingSection = this._renderMissingMetrics(doc, verdict.metricas_ausentes);
      section.appendChild(missingSection);
    }

    return section;
  },

  /**
   * Render the verdict badge with appropriate color.
   * @param {Document} doc
   * @param {object} verdict
   * @returns {HTMLElement}
   */
  _renderVerdictBadge(doc, verdict) {
    const container = doc.createElement("div");
    container.style.marginBottom = "6px";

    const badge = doc.createElement("span");
    badge.style.display = "inline-block";
    badge.style.padding = "2px 8px";
    badge.style.borderRadius = "4px";
    badge.style.fontWeight = "bold";
    badge.style.fontSize = "14px";

    // Color coding by state
    switch (verdict.estado) {
      case "COMPLETO":
        badge.style.backgroundColor = "#e8f5e9";
        badge.style.color = "#2e7d32";
        badge.textContent = verdict.estrato;
        break;

      case "ESTIMATIVA_CONSERVADORA":
        badge.style.backgroundColor = "#fff8e1";
        badge.style.color = "#f9a825";
        badge.textContent = `${verdict.estrato} ⚠`;
        break;

      case "NAO_CLASSIFICAVEL":
        badge.style.backgroundColor = "#f5f5f5";
        badge.style.color = "#757575";
        badge.textContent = "Não classificável";
        break;

      case "NAO_CONSIDERADO":
        badge.style.backgroundColor = "#f5f5f5";
        badge.style.color = "#757575";
        badge.textContent = "Não considerado";
        break;

      default:
        badge.style.backgroundColor = "#f5f5f5";
        badge.style.color = "#757575";
        badge.textContent = verdict.estrato || "?";
    }

    container.appendChild(badge);

    // State label
    const stateLabel = doc.createElement("span");
    stateLabel.style.fontSize = "11px";
    stateLabel.style.marginLeft = "8px";
    stateLabel.style.color = "#616161";
    stateLabel.textContent = this._translateState(verdict.estado);
    container.appendChild(stateLabel);

    // Reason (for NAO_CLASSIFICAVEL)
    if (verdict.motivo) {
      const reason = doc.createElement("div");
      reason.style.fontSize = "11px";
      reason.style.color = "#9e9e9e";
      reason.style.marginTop = "2px";
      reason.textContent = verdict.motivo;
      container.appendChild(reason);
    }

    return container;
  },

  /**
   * Render the decision trail.
   * @param {Document} doc
   * @param {Array} trilha
   * @returns {HTMLElement}
   */
  _renderTrail(doc, trilha) {
    const section = doc.createElement("details");
    section.style.marginTop = "6px";

    const summary = doc.createElement("summary");
    summary.style.cursor = "pointer";
    summary.style.fontSize = "11px";
    summary.style.color = "#424242";
    summary.style.fontWeight = "500";
    summary.textContent = `Trilha de decisão (${trilha.length} etapas)`;
    section.appendChild(summary);

    const list = doc.createElement("ol");
    list.style.margin = "4px 0";
    list.style.paddingLeft = "20px";
    list.style.fontSize = "11px";
    list.style.color = "#616161";

    for (const entry of trilha) {
      const li = doc.createElement("li");
      li.style.marginBottom = "2px";
      li.textContent = this._formatTrailEntry(entry);
      list.appendChild(li);
    }

    section.appendChild(list);
    return section;
  },

  /**
   * Format a single trail entry for display.
   * @param {object} entry
   * @returns {string}
   */
  _formatTrailEntry(entry) {
    const parts = [];

    if (entry.etapa) {
      parts.push(entry.etapa.replace(/_/g, " "));
    }

    if (entry.metrica) {
      parts.push(`métrica: ${entry.metrica}`);
    }

    if (entry.valor !== undefined) {
      parts.push(`valor: ${entry.valor}`);
    }

    if (entry.regra) {
      parts.push(`regra: ${entry.regra}`);
    }

    if (entry.resultado) {
      parts.push(`→ ${entry.resultado}`);
    }

    if (entry.efeito) {
      parts.push(`efeito: ${entry.efeito}`);
    }

    return parts.join(" | ");
  },

  /**
   * Render source metrics with dates.
   * @param {Document} doc
   * @param {object} metricas - Map of metric name → {valor, fonte, data}
   * @returns {HTMLElement}
   */
  _renderMetrics(doc, metricas) {
    const section = doc.createElement("details");
    section.style.marginTop = "4px";

    const summary = doc.createElement("summary");
    summary.style.cursor = "pointer";
    summary.style.fontSize = "11px";
    summary.style.color = "#424242";
    summary.style.fontWeight = "500";
    summary.textContent = `Métricas-fonte (${Object.keys(metricas).length})`;
    section.appendChild(summary);

    const table = doc.createElement("table");
    table.style.width = "100%";
    table.style.fontSize = "11px";
    table.style.borderCollapse = "collapse";
    table.style.marginTop = "4px";

    // Header row
    const thead = doc.createElement("tr");
    for (const h of ["Métrica", "Valor", "Fonte", "Data"]) {
      const th = doc.createElement("th");
      th.style.textAlign = "left";
      th.style.padding = "2px 4px";
      th.style.borderBottom = "1px solid #e0e0e0";
      th.style.color = "#757575";
      th.textContent = h;
      thead.appendChild(th);
    }
    table.appendChild(thead);

    // Data rows
    for (const [name, info] of Object.entries(metricas)) {
      const tr = doc.createElement("tr");

      const tdName = doc.createElement("td");
      tdName.style.padding = "2px 4px";
      tdName.textContent = name;
      tr.appendChild(tdName);

      const tdVal = doc.createElement("td");
      tdVal.style.padding = "2px 4px";
      tdVal.textContent = info.valor != null ? String(info.valor) : "—";
      tr.appendChild(tdVal);

      const tdFonte = doc.createElement("td");
      tdFonte.style.padding = "2px 4px";
      tdFonte.textContent = info.fonte || "—";
      tr.appendChild(tdFonte);

      const tdData = doc.createElement("td");
      tdData.style.padding = "2px 4px";
      tdData.textContent = info.data || "—";
      tr.appendChild(tdData);

      table.appendChild(tr);
    }

    section.appendChild(table);
    return section;
  },

  /**
   * Render missing metrics list.
   * @param {Document} doc
   * @param {string[]} ausentes
   * @returns {HTMLElement}
   */
  _renderMissingMetrics(doc, ausentes) {
    const div = doc.createElement("div");
    div.style.marginTop = "4px";
    div.style.fontSize = "11px";
    div.style.color = "#9e9e9e";
    div.textContent = `Métricas ausentes: ${ausentes.join(", ")}`;
    return div;
  },

  /**
   * Render the Historical Qualis section (task 10.8).
   * Separate section with cycle label.
   * If historical snapshot is absent, omit section without error.
   * Never merge with 2025-2028 classification.
   *
   * @param {Document} doc
   * @param {object} item - Zotero item
   * @returns {HTMLElement|null}
   */
  _renderHistoricalSection(doc, item) {
    const historicalSnapshot = NoQualisSnapshotLoader.getHistoricalSnapshot();

    // If historical snapshot absent, omit section without error
    if (!historicalSnapshot) {
      return null;
    }

    const historicalVerdict = NoQualisEvaluator.evaluateHistorical(item);
    if (!historicalVerdict) {
      return null;
    }

    const section = doc.createElement("div");
    section.style.marginTop = "12px";
    section.style.borderRadius = "4px";
    section.style.padding = "8px";
    section.style.border = "1px solid #e0e0e0";
    section.style.backgroundColor = "#fafafa";

    // Determine cycle label
    const cycleLabel = this._getHistoricalCycleLabel(historicalSnapshot, historicalVerdict);

    // Header
    const header = doc.createElement("div");
    header.style.fontWeight = "bold";
    header.style.marginBottom = "6px";
    header.style.fontSize = "12px";
    header.style.color = "#616161";
    header.textContent = cycleLabel;
    section.appendChild(header);

    // Historical classification display
    if (historicalVerdict.estrato || historicalVerdict.qualis) {
      const estrato = historicalVerdict.estrato || historicalVerdict.qualis;
      const badge = doc.createElement("span");
      badge.style.display = "inline-block";
      badge.style.padding = "2px 6px";
      badge.style.borderRadius = "3px";
      badge.style.backgroundColor = "#e8eaf6";
      badge.style.color = "#283593";
      badge.style.fontWeight = "bold";
      badge.style.fontSize = "13px";
      badge.textContent = estrato;
      section.appendChild(badge);

      // Cycle info
      if (historicalVerdict.ciclo) {
        const cicloLabel = doc.createElement("span");
        cicloLabel.style.fontSize = "11px";
        cicloLabel.style.marginLeft = "8px";
        cicloLabel.style.color = "#757575";
        cicloLabel.textContent = historicalVerdict.ciclo;
        section.appendChild(cicloLabel);
      }

      // Area info if present
      if (historicalVerdict.area_nome) {
        const areaInfo = doc.createElement("div");
        areaInfo.style.fontSize = "11px";
        areaInfo.style.color = "#9e9e9e";
        areaInfo.style.marginTop = "2px";
        areaInfo.textContent = `Área: ${historicalVerdict.area_nome}`;
        section.appendChild(areaInfo);
      }
    } else if (typeof historicalVerdict === "object" && historicalVerdict.tipos) {
      // Snapshot format with tipos structure
      for (const [tipo, info] of Object.entries(historicalVerdict.tipos)) {
        const row = doc.createElement("div");
        row.style.marginTop = "2px";
        const badge = doc.createElement("span");
        badge.style.display = "inline-block";
        badge.style.padding = "1px 5px";
        badge.style.borderRadius = "3px";
        badge.style.backgroundColor = "#e8eaf6";
        badge.style.color = "#283593";
        badge.style.fontWeight = "bold";
        badge.style.fontSize = "12px";
        badge.textContent = info.estrato || "?";
        row.appendChild(badge);

        if (info.ciclo) {
          const cicloSpan = doc.createElement("span");
          cicloSpan.style.fontSize = "11px";
          cicloSpan.style.marginLeft = "6px";
          cicloSpan.style.color = "#757575";
          cicloSpan.textContent = info.ciclo;
          row.appendChild(cicloSpan);
        }

        section.appendChild(row);
      }
    }

    // Disclaimer
    const disclaimer = doc.createElement("div");
    disclaimer.style.marginTop = "6px";
    disclaimer.style.fontSize = "10px";
    disclaimer.style.color = "#9e9e9e";
    disclaimer.style.fontStyle = "italic";
    disclaimer.textContent = "Classificação de ciclo anterior. Não mesclar com 2025-2028.";
    section.appendChild(disclaimer);

    return section;
  },

  /**
   * Determine the cycle label for the historical section.
   * @param {object} snapshot - Historical snapshot
   * @param {object} verdict - Historical verdict for the item
   * @returns {string}
   */
  _getHistoricalCycleLabel(snapshot, verdict) {
    // Check verdict-level cycle info
    if (verdict && verdict.ciclo) {
      if (verdict.ciclo.toLowerCase().includes("evento")) {
        return "Qualis Eventos 2025";
      }
      return `Histórico ${verdict.ciclo}`;
    }

    // Check snapshot-level info
    if (snapshot.ciclo) {
      if (snapshot.ciclo.toLowerCase().includes("evento")) {
        return "Qualis Eventos 2025";
      }
      return `Histórico ${snapshot.ciclo}`;
    }

    if (snapshot.vigencia) {
      if (snapshot.vigencia === "2025") {
        return "Qualis Eventos 2025";
      }
      return `Histórico ${snapshot.vigencia}`;
    }

    // Default based on filename pattern
    return "Histórico 2021-2024";
  },

  /**
   * Create a link/reference to LIMITATIONS.md.
   * @param {Document} doc
   * @returns {HTMLElement}
   */
  _createLimitationsLink(doc) {
    const div = doc.createElement("div");
    div.style.marginTop = "10px";
    div.style.paddingTop = "6px";
    div.style.borderTop = "1px solid #eeeeee";
    div.style.fontSize = "10px";
    div.style.color = "#9e9e9e";
    div.textContent = "⚠ Classificação não-oficial. Consulte LIMITATIONS.md para limitações conhecidas.";
    return div;
  },

  /**
   * Translate state enum to human-readable Portuguese.
   * @param {string} estado
   * @returns {string}
   */
  _translateState(estado) {
    const translations = {
      COMPLETO: "Completo",
      ESTIMATIVA_CONSERVADORA: "Estimativa conservadora",
      NAO_CLASSIFICAVEL: "Não classificável",
      NAO_CONSIDERADO: "Não considerado"
    };
    return translations[estado] || estado || "";
  },

  /**
   * Get selected areas from preferences.
   * @returns {number[]}
   */
  _getSelectedAreas() {
    const areasJson = Zotero.Prefs.get("extensions.noqualis.selectedAreas", true) || "[]";
    try {
      const areas = JSON.parse(areasJson);
      return Array.isArray(areas) ? areas : [];
    } catch (e) {
      return [];
    }
  },

  /**
   * Destroy the panel section (plugin shutdown).
   */
  destroy() {
    if (this._sectionId) {
      try {
        Zotero.ItemPaneManager.unregisterSection(this._sectionId);
      } catch (e) {
        // Ignore if already unregistered
      }
      this._sectionId = null;
    }
  }
};
