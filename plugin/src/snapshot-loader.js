/**
 * NoQualis - Snapshot Loader
 *
 * Reads snapshot JSON files from the local data directory.
 * Snapshots are immutable, versioned by date, and contain
 * pre-calculated verdicts for all vehicles of an area.
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 * - Reads only from local filesystem (Zotero data directory)
 */

/* global Zotero, IOUtils, PathUtils */

var NoQualisSnapshotLoader = {
  /** @type {Map<number, object>} Loaded snapshots indexed by area code */
  _snapshots: new Map(),

  /** @type {object|null} Historical Qualis snapshot */
  _historicalSnapshot: null,

  /** @type {boolean} Whether any snapshot has an obsolescence warning */
  _hasObsolescenceWarning: false,

  /** @type {Map<number, {days: number, date: string}>} Obsolescence info per area */
  _obsolescenceInfo: new Map(),

  /**
   * Get the configured snapshot directory path.
   * Falls back to plugin's own snapshots/ directory.
   * @returns {string} Absolute path to snapshot directory
   */
  getSnapshotDirectory() {
    const customDir = Zotero.Prefs.get("extensions.noqualis.snapshotDirectory", true);
    if (customDir && customDir.trim().length > 0) {
      return customDir.trim();
    }
    // Default: plugin data directory under Zotero profile
    const dataDir = Zotero.DataDirectory.dir;
    return PathUtils.join(dataDir, "noqualis", "snapshots");
  },

  /**
   * Get the obsolescence threshold in days from preferences.
   * @returns {number} Threshold in days (default 180)
   */
  getObsolescenceThreshold() {
    return Zotero.Prefs.get("extensions.noqualis.obsolescenceThresholdDays", true) || 180;
  },

  /**
   * Load all snapshots from the configured directory.
   * Validates basic structure and detects obsolescence.
   * @returns {Promise<{loaded: number, warnings: string[]}>}
   */
  async loadAll() {
    const dir = this.getSnapshotDirectory();
    const warnings = [];
    let loaded = 0;

    this._snapshots.clear();
    this._historicalSnapshot = null;
    this._hasObsolescenceWarning = false;
    this._obsolescenceInfo.clear();

    // Check if directory exists
    let dirExists = false;
    try {
      dirExists = await IOUtils.exists(dir);
    } catch (e) {
      Zotero.log(`[NoQualis] Cannot access snapshot directory: ${dir}`, "warning");
      return { loaded: 0, warnings: [`Diretório de snapshots não encontrado: ${dir}`] };
    }

    if (!dirExists) {
      Zotero.log(`[NoQualis] Snapshot directory does not exist: ${dir}`, "warning");
      return { loaded: 0, warnings: [`Diretório de snapshots não encontrado: ${dir}`] };
    }

    // List JSON files in directory
    let entries;
    try {
      entries = await IOUtils.getChildren(dir);
    } catch (e) {
      Zotero.log(`[NoQualis] Error listing snapshot directory: ${e.message}`, "error");
      return { loaded: 0, warnings: [`Erro ao listar diretório: ${e.message}`] };
    }

    const jsonFiles = entries.filter(f => f.endsWith(".json"));

    for (const filePath of jsonFiles) {
      try {
        const result = await this._loadSnapshotFile(filePath);
        if (result.success) {
          loaded++;
          if (result.warning) {
            warnings.push(result.warning);
          }
        } else {
          warnings.push(result.error);
        }
      } catch (e) {
        const filename = PathUtils.filename(filePath);
        warnings.push(`Erro ao carregar ${filename}: ${e.message}`);
        Zotero.log(`[NoQualis] Error loading ${filePath}: ${e.message}`, "error");
      }
    }

    Zotero.log(`[NoQualis] Loaded ${loaded} snapshots, ${warnings.length} warnings`, "info");
    return { loaded, warnings };
  },

  /**
   * Load and validate a single snapshot file.
   * @param {string} filePath - Absolute path to JSON file
   * @returns {Promise<{success: boolean, warning?: string, error?: string}>}
   */
  async _loadSnapshotFile(filePath) {
    const filename = PathUtils.filename(filePath);

    // Read file contents
    const bytes = await IOUtils.read(filePath);
    const decoder = new TextDecoder("utf-8");
    const text = decoder.decode(bytes);

    // Parse JSON
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { success: false, error: `${filename}: JSON inválido — ${e.message}` };
    }

    // Validate basic structure
    const validation = this._validateSnapshot(data, filename);
    if (!validation.valid) {
      return { success: false, error: validation.error };
    }

    // Detect if this is a historical snapshot
    if (this._isHistoricalSnapshot(data, filename)) {
      this._historicalSnapshot = data;
      const obsolescence = this._checkObsolescence(data.data_snapshot, filename);
      if (obsolescence.obsolete) {
        this._hasObsolescenceWarning = true;
        return { success: true, warning: obsolescence.message };
      }
      return { success: true };
    }

    // Regular area snapshot
    const areaCode = data.area;
    this._snapshots.set(areaCode, data);

    // Check obsolescence
    const obsolescence = this._checkObsolescence(data.data_snapshot, filename);
    if (obsolescence.obsolete) {
      this._hasObsolescenceWarning = true;
      this._obsolescenceInfo.set(areaCode, {
        days: obsolescence.days,
        date: data.data_snapshot
      });
      return { success: true, warning: obsolescence.message };
    }

    return { success: true };
  },

  /**
   * Validate basic snapshot structure.
   * Checks required fields: area (or historical marker), escala, veiculos.
   * @param {object} data - Parsed JSON
   * @param {string} filename - For error messages
   * @returns {{valid: boolean, error?: string}}
   */
  _validateSnapshot(data, filename) {
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      return { valid: false, error: `${filename}: formato inválido (não é um objeto JSON)` };
    }

    // Historical snapshots have a different structure
    if (this._isHistoricalSnapshot(data, filename)) {
      if (!data.veiculos || typeof data.veiculos !== "object") {
        return { valid: false, error: `${filename}: campo 'veiculos' ausente ou inválido` };
      }
      return { valid: true };
    }

    // Regular area snapshot: requires area, escala, veiculos
    if (typeof data.area !== "number" || data.area < 1) {
      return { valid: false, error: `${filename}: campo 'area' ausente ou inválido (deve ser inteiro ≥ 1)` };
    }

    if (!data.escala || typeof data.escala !== "object") {
      return { valid: false, error: `${filename}: campo 'escala' ausente ou inválido` };
    }

    if (!Array.isArray(data.escala.rotulos) || data.escala.rotulos.length < 2) {
      return { valid: false, error: `${filename}: campo 'escala.rotulos' ausente ou com menos de 2 itens` };
    }

    if (!data.veiculos || typeof data.veiculos !== "object") {
      return { valid: false, error: `${filename}: campo 'veiculos' ausente ou inválido` };
    }

    if (!data.data_snapshot) {
      return { valid: false, error: `${filename}: campo 'data_snapshot' ausente` };
    }

    return { valid: true };
  },

  /**
   * Detect if a snapshot is a historical Qualis snapshot.
   * Historical snapshots have filenames like "qualis-historico-*.json"
   * or contain a "ciclo" field.
   * @param {object} data - Parsed JSON
   * @param {string} filename - Filename for detection
   * @returns {boolean}
   */
  _isHistoricalSnapshot(data, filename) {
    // Filename pattern detection
    if (filename.startsWith("qualis-historico") || filename.startsWith("qualis-eventos")) {
      return true;
    }
    // Data structure detection: has ciclo field or vigencia indicating old cycle
    if (data.ciclo) {
      return true;
    }
    if (data.vigencia && !data.vigencia.startsWith("2025")) {
      return true;
    }
    return false;
  },

  /**
   * Check if a snapshot date indicates obsolescence.
   * @param {string} dateStr - ISO 8601 date string (YYYY-MM-DD)
   * @param {string} filename - For warning message
   * @returns {{obsolete: boolean, days?: number, message?: string}}
   */
  _checkObsolescence(dateStr, filename) {
    if (!dateStr) {
      return { obsolete: false };
    }

    const snapshotDate = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - snapshotDate.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const threshold = this.getObsolescenceThreshold();

    if (diffDays > threshold) {
      return {
        obsolete: true,
        days: diffDays,
        message: `${filename}: dados com ${diffDays} dias de idade (limiar: ${threshold} dias)`
      };
    }

    return { obsolete: false, days: diffDays };
  },

  /**
   * Get a loaded snapshot by area code.
   * @param {number} areaCode
   * @returns {object|null}
   */
  getSnapshot(areaCode) {
    return this._snapshots.get(areaCode) || null;
  },

  /**
   * Get all loaded area snapshots.
   * @returns {Map<number, object>}
   */
  getAllSnapshots() {
    return this._snapshots;
  },

  /**
   * Get the historical Qualis snapshot.
   * @returns {object|null}
   */
  getHistoricalSnapshot() {
    return this._historicalSnapshot;
  },

  /**
   * Get list of available areas (loaded snapshots).
   * @returns {Array<{code: number, name: string, status: string, date: string}>}
   */
  getAvailableAreas() {
    const areas = [];
    for (const [code, snapshot] of this._snapshots) {
      areas.push({
        code,
        name: snapshot.nome || `Área ${code}`,
        status: snapshot.status || "experimental",
        date: snapshot.data_snapshot || "desconhecida"
      });
    }
    return areas.sort((a, b) => a.code - b.code);
  },

  /**
   * Check if any loaded snapshot has an obsolescence warning.
   * @returns {boolean}
   */
  hasObsolescenceWarning() {
    return this._hasObsolescenceWarning;
  },

  /**
   * Get obsolescence info for a specific area.
   * @param {number} areaCode
   * @returns {{days: number, date: string}|null}
   */
  getObsolescenceInfo(areaCode) {
    return this._obsolescenceInfo.get(areaCode) || null;
  },

  /**
   * Reload all snapshots (e.g., after preference change).
   * @returns {Promise<{loaded: number, warnings: string[]}>}
   */
  async reload() {
    return this.loadAll();
  }
};
