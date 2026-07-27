/**
 * NoQualis - Custom Columns
 *
 * Registers custom columns in Zotero's item tree via
 * ItemTreeManager.registerColumns, displaying the classification
 * stratum per active area.
 *
 * Display format:
 * - "A1" for COMPLETO
 * - "A1 ⚠" for ESTIMATIVA_CONSERVADORA
 * - "?" for NAO_CLASSIFICAVEL
 * - "—" for NAO_CONSIDERADO
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 */

/* global Zotero, NoQualisSnapshotLoader, NoQualisEvaluator */

var NoQualisColumns = {
  /** @type {string[]} IDs of registered columns (for cleanup) */
  _registeredColumnIds: [],

  /**
   * Initialize columns for all active areas.
   * Should be called after snapshots are loaded and areas are selected.
   */
  init() {
    this._unregisterAll();
    this._registerColumns();
  },

  /**
   * Register columns for each selected area.
   */
  _registerColumns() {
    const selectedAreas = this._getSelectedAreas();

    for (const areaCode of selectedAreas) {
      const snapshot = NoQualisSnapshotLoader.getSnapshot(areaCode);
      if (!snapshot) continue;

      const areaName = snapshot.nome || `Área ${areaCode}`;
      const columnId = `noqualis-area-${areaCode}`;

      try {
        Zotero.ItemTreeManager.registerColumns({
          dataKey: columnId,
          label: `Qualis ${areaName}`,
          pluginID: "noqualis@wcmendes.github.io",
          dataProvider: (item, dataKey) => {
            return this._getColumnValue(item, areaCode);
          },
          zopiconIcon: null,
          fixedWidth: false,
          minWidth: 50
        });

        this._registeredColumnIds.push(columnId);
        Zotero.log(`[NoQualis] Registered column: ${columnId}`, "info");
      } catch (e) {
        Zotero.log(`[NoQualis] Failed to register column ${columnId}: ${e.message}`, "error");
      }
    }
  },

  /**
   * Get the display value for a column cell.
   * @param {object} item - Zotero item
   * @param {number} areaCode - Area code
   * @returns {string} Display string
   */
  _getColumnValue(item, areaCode) {
    // Skip non-regular items (notes, attachments)
    if (!item.isRegularItem || !item.isRegularItem()) {
      return "";
    }

    const verdict = NoQualisEvaluator.evaluate(item, areaCode);
    return this._formatVerdict(verdict);
  },

  /**
   * Format a verdict for column display.
   * @param {object} verdict
   * @returns {string}
   */
  _formatVerdict(verdict) {
    if (!verdict) return "";

    switch (verdict.estado) {
      case "COMPLETO":
        return verdict.estrato;

      case "ESTIMATIVA_CONSERVADORA":
        return `${verdict.estrato} \u26A0`; // ⚠ warning sign

      case "NAO_CLASSIFICAVEL":
        return "?";

      case "NAO_CONSIDERADO":
        return "\u2014"; // — em dash

      default:
        return verdict.estrato || "?";
    }
  },

  /**
   * Unregister all previously registered columns.
   */
  _unregisterAll() {
    for (const columnId of this._registeredColumnIds) {
      try {
        Zotero.ItemTreeManager.unregisterColumns(columnId);
      } catch (e) {
        // Column may not exist anymore, ignore
      }
    }
    this._registeredColumnIds = [];
  },

  /**
   * Refresh columns (e.g., when areas selection changes).
   */
  refresh() {
    this._unregisterAll();
    this._registerColumns();
  },

  /**
   * Destroy all registered columns (plugin shutdown).
   */
  destroy() {
    this._unregisterAll();
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
  }
};
