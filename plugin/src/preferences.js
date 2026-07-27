/**
 * NoQualis - Preferences
 *
 * Manages user preferences:
 * - Area selector (multiple areas can be active simultaneously)
 * - Obsolescence threshold (default: 180 days)
 * - Snapshot directory path
 *
 * Uses Zotero.Prefs for storage — NO localStorage/sessionStorage (R6.8).
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 */

/* global Zotero, NoQualisSnapshotLoader, NoQualisColumns */

var NoQualisPreferences = {
  /** Preference keys */
  PREF_SELECTED_AREAS: "extensions.noqualis.selectedAreas",
  PREF_OBSOLESCENCE_THRESHOLD: "extensions.noqualis.obsolescenceThresholdDays",
  PREF_SNAPSHOT_DIRECTORY: "extensions.noqualis.snapshotDirectory",
  PREF_TAG_PREFIX: "extensions.noqualis.tagPrefix",

  /**
   * Initialize preferences module.
   * Ensures default values are set.
   */
  init() {
    this._ensureDefaults();
  },

  /**
   * Ensure default preference values exist.
   */
  _ensureDefaults() {
    if (!Zotero.Prefs.get(this.PREF_SELECTED_AREAS, true)) {
      Zotero.Prefs.set(this.PREF_SELECTED_AREAS, "[]", true);
    }
    if (!Zotero.Prefs.get(this.PREF_OBSOLESCENCE_THRESHOLD, true)) {
      Zotero.Prefs.set(this.PREF_OBSOLESCENCE_THRESHOLD, 180, true);
    }
    if (Zotero.Prefs.get(this.PREF_SNAPSHOT_DIRECTORY, true) === undefined) {
      Zotero.Prefs.set(this.PREF_SNAPSHOT_DIRECTORY, "", true);
    }
    if (!Zotero.Prefs.get(this.PREF_TAG_PREFIX, true)) {
      Zotero.Prefs.set(this.PREF_TAG_PREFIX, "Qualis", true);
    }
  },

  // ──────────────────────────────────────────────────────────────
  // Area Selection
  // ──────────────────────────────────────────────────────────────

  /**
   * Get the list of currently selected area codes.
   * @returns {number[]}
   */
  getSelectedAreas() {
    const json = Zotero.Prefs.get(this.PREF_SELECTED_AREAS, true) || "[]";
    try {
      const areas = JSON.parse(json);
      return Array.isArray(areas) ? areas : [];
    } catch (e) {
      return [];
    }
  },

  /**
   * Set the selected areas.
   * @param {number[]} areaCodes - Array of area codes to select
   */
  setSelectedAreas(areaCodes) {
    const valid = Array.isArray(areaCodes)
      ? areaCodes.filter(c => typeof c === "number" && c >= 1)
      : [];
    Zotero.Prefs.set(this.PREF_SELECTED_AREAS, JSON.stringify(valid), true);

    // Refresh columns when areas change
    if (typeof NoQualisColumns !== "undefined" && NoQualisColumns.refresh) {
      NoQualisColumns.refresh();
    }
  },

  /**
   * Add an area to the selection.
   * @param {number} areaCode
   */
  addArea(areaCode) {
    const current = this.getSelectedAreas();
    if (!current.includes(areaCode)) {
      current.push(areaCode);
      this.setSelectedAreas(current);
    }
  },

  /**
   * Remove an area from the selection.
   * @param {number} areaCode
   */
  removeArea(areaCode) {
    const current = this.getSelectedAreas();
    const filtered = current.filter(c => c !== areaCode);
    this.setSelectedAreas(filtered);
  },

  /**
   * Toggle an area in the selection.
   * @param {number} areaCode
   * @returns {boolean} New state (true = selected)
   */
  toggleArea(areaCode) {
    const current = this.getSelectedAreas();
    if (current.includes(areaCode)) {
      this.removeArea(areaCode);
      return false;
    } else {
      this.addArea(areaCode);
      return true;
    }
  },

  /**
   * Get available areas from loaded snapshots.
   * Returns all areas that have snapshots loaded, with selection state.
   * @returns {Array<{code: number, name: string, selected: boolean, status: string, date: string}>}
   */
  getAvailableAreasWithSelection() {
    const available = NoQualisSnapshotLoader.getAvailableAreas();
    const selected = this.getSelectedAreas();

    return available.map(area => ({
      ...area,
      selected: selected.includes(area.code)
    }));
  },

  // ──────────────────────────────────────────────────────────────
  // Obsolescence Threshold
  // ──────────────────────────────────────────────────────────────

  /**
   * Get the obsolescence threshold in days.
   * @returns {number}
   */
  getObsolescenceThreshold() {
    return Zotero.Prefs.get(this.PREF_OBSOLESCENCE_THRESHOLD, true) || 180;
  },

  /**
   * Set the obsolescence threshold in days.
   * @param {number} days - Must be positive integer
   */
  setObsolescenceThreshold(days) {
    const value = Math.max(1, Math.floor(Number(days) || 180));
    Zotero.Prefs.set(this.PREF_OBSOLESCENCE_THRESHOLD, value, true);
  },

  // ──────────────────────────────────────────────────────────────
  // Snapshot Directory
  // ──────────────────────────────────────────────────────────────

  /**
   * Get the configured snapshot directory path.
   * Empty string means use default location.
   * @returns {string}
   */
  getSnapshotDirectory() {
    return Zotero.Prefs.get(this.PREF_SNAPSHOT_DIRECTORY, true) || "";
  },

  /**
   * Set the snapshot directory path.
   * @param {string} path - Absolute path to directory, or empty for default
   */
  setSnapshotDirectory(path) {
    Zotero.Prefs.set(this.PREF_SNAPSHOT_DIRECTORY, path ? path.trim() : "", true);
  },

  /**
   * Reset snapshot directory to default.
   */
  resetSnapshotDirectory() {
    this.setSnapshotDirectory("");
  },

  // ──────────────────────────────────────────────────────────────
  // Tag Prefix
  // ──────────────────────────────────────────────────────────────

  /**
   * Get the tag prefix.
   * @returns {string}
   */
  getTagPrefix() {
    return Zotero.Prefs.get(this.PREF_TAG_PREFIX, true) || "Qualis";
  },

  /**
   * Set the tag prefix.
   * @param {string} prefix
   */
  setTagPrefix(prefix) {
    const value = prefix ? prefix.trim() : "Qualis";
    Zotero.Prefs.set(this.PREF_TAG_PREFIX, value, true);
  },

  // ──────────────────────────────────────────────────────────────
  // Bulk Operations
  // ──────────────────────────────────────────────────────────────

  /**
   * Select all available areas.
   */
  selectAllAreas() {
    const available = NoQualisSnapshotLoader.getAvailableAreas();
    const codes = available.map(a => a.code);
    this.setSelectedAreas(codes);
  },

  /**
   * Deselect all areas.
   */
  deselectAllAreas() {
    this.setSelectedAreas([]);
  },

  /**
   * Export current preferences as a plain object (for debugging).
   * @returns {object}
   */
  exportPreferences() {
    return {
      selectedAreas: this.getSelectedAreas(),
      obsolescenceThreshold: this.getObsolescenceThreshold(),
      snapshotDirectory: this.getSnapshotDirectory(),
      tagPrefix: this.getTagPrefix()
    };
  },

  /**
   * Destroy (cleanup on shutdown).
   */
  destroy() {
    // No persistent resources to clean up
  }
};
