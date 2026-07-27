/**
 * NoQualis - Evaluator
 *
 * Looks up pre-calculated verdicts by ISSN from loaded snapshots.
 * The plugin does NOT execute the rules engine - it only queries
 * pre-computed results from snapshots.
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 */

/* global Zotero, NoQualisSnapshotLoader */

var NoQualisEvaluator = {
  /**
   * Evaluate a Zotero item against a specific area snapshot.
   * Returns the pre-calculated verdict from the snapshot.
   *
   * @param {object} item - Zotero item object
   * @param {number} areaCode - Area code to evaluate against
   * @returns {object} Verdict object with estrato, estado, trilha
   */
  evaluate(item, areaCode) {
    const snapshot = NoQualisSnapshotLoader.getSnapshot(areaCode);
    if (!snapshot) {
      return this._makeNaoClassificavel(
        "Snapshot não carregado para esta área",
        []
      );
    }

    // Extract ISSN from item
    const issn = this._extractISSN(item);
    if (!issn) {
      return this._makeNaoClassificavel(
        "Item sem ISSN",
        [{ etapa: "busca_issn", resultado: "ISSN ausente no item" }]
      );
    }

    // Look up vehicle in snapshot by ISSN
    const vehicle = this._findVehicle(snapshot, issn);
    if (!vehicle) {
      return this._makeNaoClassificavel(
        `ISSN ${issn} não encontrado no snapshot da área ${areaCode}`,
        [{ etapa: "busca_veiculo", issn, resultado: "Veículo não encontrado no snapshot" }]
      );
    }

    // Determine item type for verdict lookup
    const itemType = this._mapItemType(item);
    const verdict = this._getVerdictForType(vehicle, itemType, snapshot);

    return verdict;
  },

  /**
   * Evaluate a Zotero item against all active areas.
   * @param {object} item - Zotero item object
   * @returns {Map<number, object>} Map of areaCode → verdict
   */
  evaluateAllAreas(item) {
    const results = new Map();
    const selectedAreas = this._getSelectedAreas();

    for (const areaCode of selectedAreas) {
      results.set(areaCode, this.evaluate(item, areaCode));
    }

    return results;
  },

  /**
   * Look up historical Qualis for an item.
   * @param {object} item - Zotero item object
   * @returns {object|null} Historical verdict or null if not available
   */
  evaluateHistorical(item) {
    const historicalSnapshot = NoQualisSnapshotLoader.getHistoricalSnapshot();
    if (!historicalSnapshot) {
      return null;
    }

    const issn = this._extractISSN(item);
    if (!issn) {
      return null;
    }

    // Look up in historical snapshot
    const vehicle = this._findVehicleInHistorical(historicalSnapshot, issn);
    if (!vehicle) {
      return null;
    }

    return vehicle;
  },

  /**
   * Extract ISSN from a Zotero item.
   * Tries the ISSN field directly.
   * @param {object} item - Zotero item
   * @returns {string|null} Normalized ISSN or null
   */
  _extractISSN(item) {
    let issn = null;

    // Try item.getField for Zotero items
    if (typeof item.getField === "function") {
      issn = item.getField("ISSN");
    } else if (item.ISSN) {
      // Plain object (for testing)
      issn = item.ISSN;
    }

    if (!issn || issn.trim().length === 0) {
      return null;
    }

    // Normalize: take first ISSN if multiple are separated by comma/space
    issn = issn.trim().split(/[,;\s]+/)[0].trim();

    // Validate format: should be XXXX-XXXX
    const normalized = this._normalizeISSN(issn);
    return normalized;
  },

  /**
   * Normalize ISSN to XXXX-XXXX format.
   * @param {string} raw - Raw ISSN string
   * @returns {string|null} Normalized ISSN or null if invalid
   */
  _normalizeISSN(raw) {
    if (!raw) return null;

    // Remove hyphens and spaces for processing
    const digits = raw.replace(/[-\s]/g, "").toUpperCase();

    // Must be exactly 8 characters (digits + optional X at end)
    if (digits.length !== 8) return null;
    if (!/^[0-9]{7}[0-9X]$/.test(digits)) return null;

    // Format as XXXX-XXXX
    return digits.substring(0, 4) + "-" + digits.substring(4);
  },

  /**
   * Find a vehicle in the snapshot by ISSN.
   * Checks the main key and also the issns array in each vehicle.
   * @param {object} snapshot
   * @param {string} issn - Normalized ISSN
   * @returns {object|null} Vehicle object or null
   */
  _findVehicle(snapshot, issn) {
    const veiculos = snapshot.veiculos;
    if (!veiculos) return null;

    // Direct lookup by ISSN key
    if (veiculos[issn]) {
      return veiculos[issn];
    }

    // Search through vehicles' issns arrays (ISSN-L variants)
    for (const [key, vehicle] of Object.entries(veiculos)) {
      if (vehicle.issns && Array.isArray(vehicle.issns)) {
        if (vehicle.issns.includes(issn)) {
          return vehicle;
        }
      }
    }

    return null;
  },

  /**
   * Find a vehicle in the historical snapshot.
   * Historical snapshots may have different structure.
   * @param {object} snapshot - Historical snapshot
   * @param {string} issn - Normalized ISSN
   * @returns {object|null}
   */
  _findVehicleInHistorical(snapshot, issn) {
    const veiculos = snapshot.veiculos;
    if (!veiculos) return null;

    // Direct lookup
    if (veiculos[issn]) {
      return veiculos[issn];
    }

    // Search through issns arrays
    for (const [key, vehicle] of Object.entries(veiculos)) {
      if (vehicle.issns && Array.isArray(vehicle.issns)) {
        if (vehicle.issns.includes(issn)) {
          return vehicle;
        }
      }
    }

    return null;
  },

  /**
   * Map Zotero item type to the type keys used in snapshot.
   * @param {object} item - Zotero item
   * @returns {string} Mapped type key
   */
  _mapItemType(item) {
    let type;
    if (typeof item.itemTypeID !== "undefined") {
      // Zotero item — get type name
      type = Zotero.ItemTypes.getName(item.itemTypeID);
    } else if (item.itemType) {
      type = item.itemType;
    } else {
      type = "journalArticle";
    }

    // Map Zotero types to snapshot type keys
    const typeMap = {
      journalArticle: "journalArticle",
      conferencePaper: "conferencePaper",
      book: "book",
      bookSection: "bookSection"
    };

    return typeMap[type] || type;
  },

  /**
   * Get the verdict for a specific item type from a vehicle.
   * If type is not defined, tries fallback logic.
   * @param {object} vehicle - Vehicle object from snapshot
   * @param {string} itemType - Item type key
   * @param {object} snapshot - Area snapshot (for scale info)
   * @returns {object} Verdict
   */
  _getVerdictForType(vehicle, itemType, snapshot) {
    const tipos = vehicle.tipos;
    if (!tipos) {
      return this._makeNaoClassificavel(
        "Veículo sem tipos definidos no snapshot",
        [{ etapa: "busca_tipo", resultado: "Campo 'tipos' ausente no veículo" }]
      );
    }

    // Direct type match
    if (tipos[itemType]) {
      const verdict = tipos[itemType];
      return {
        estrato: verdict.estrato,
        estado: verdict.estado,
        trilha: verdict.trilha || [],
        metricas_utilizadas: verdict.metricas_utilizadas || {},
        metricas_ausentes: verdict.metricas_ausentes || [],
        titulo: vehicle.titulo || ""
      };
    }

    // Fallback: check if there's a generic "default" type
    if (tipos["*"]) {
      const verdict = tipos["*"];
      return {
        estrato: verdict.estrato,
        estado: verdict.estado,
        trilha: verdict.trilha || [],
        metricas_utilizadas: verdict.metricas_utilizadas || {},
        metricas_ausentes: verdict.metricas_ausentes || [],
        titulo: vehicle.titulo || ""
      };
    }

    // No matching type — NAO_CLASSIFICAVEL
    return this._makeNaoClassificavel(
      `Tipo '${itemType}' não definido para este veículo`,
      [{
        etapa: "busca_tipo",
        tipo_solicitado: itemType,
        tipos_disponiveis: Object.keys(tipos),
        resultado: "Tipo não encontrado no snapshot"
      }]
    );
  },

  /**
   * Create a NAO_CLASSIFICAVEL verdict.
   * @param {string} motivo - Reason
   * @param {Array} trilha - Trail entries
   * @returns {object}
   */
  _makeNaoClassificavel(motivo, trilha) {
    return {
      estrato: "NAO_CLASSIFICAVEL",
      estado: "NAO_CLASSIFICAVEL",
      trilha: trilha || [],
      metricas_utilizadas: {},
      metricas_ausentes: [],
      motivo,
      titulo: ""
    };
  },

  /**
   * Get list of selected/active areas from preferences.
   * @returns {number[]} Array of area codes
   */
  _getSelectedAreas() {
    const areasJson = Zotero.Prefs.get("extensions.noqualis.selectedAreas", true) || "[]";
    try {
      const areas = JSON.parse(areasJson);
      return Array.isArray(areas) ? areas : [];
    } catch (e) {
      return [];
    }
  }
};
