/**
 * NoQualis - Classificador CAPES para Zotero 7
 * Main entry point.
 *
 * Orchestrates all plugin modules:
 * - snapshot-loader: reads local JSON snapshots
 * - evaluator: looks up pre-calculated verdicts by ISSN
 * - columns: registers custom columns in item tree
 * - panel: registers item pane section with full verdict display
 * - tagger: batch tagging action
 * - preferences: area selector, threshold, directory config
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 * - All data comes exclusively from local snapshots
 */

/* global Zotero, Services,
   NoQualisSnapshotLoader, NoQualisEvaluator,
   NoQualisColumns, NoQualisPanel,
   NoQualisTagger, NoQualisPreferences */

class NoQualisPlugin {
  constructor() {
    this.id = null;
    this.version = null;
    this.rootURI = null;
    this.initialized = false;
  }

  /**
   * Initialize the plugin.
   * @param {object} params - Plugin metadata from bootstrap
   * @param {string} params.id - Plugin ID
   * @param {string} params.version - Plugin version
   * @param {string} params.rootURI - Root URI for plugin resources
   */
  async init({ id, version, rootURI }) {
    if (this.initialized) return;

    this.id = id;
    this.version = version;
    this.rootURI = rootURI;

    Zotero.log(`[NoQualis] Initializing v${version}`, "info");

    // Load all module scripts (they register globals)
    const modules = [
      "snapshot-loader.js",
      "evaluator.js",
      "columns.js",
      "panel.js",
      "tagger.js",
      "preferences.js"
    ];

    for (const mod of modules) {
      try {
        Services.scriptloader.loadSubScript(rootURI + "src/" + mod);
      } catch (e) {
        Zotero.log(`[NoQualis] Failed to load ${mod}: ${e.message}`, "error");
      }
    }

    // Initialize preferences first (ensures defaults)
    if (typeof NoQualisPreferences !== "undefined") {
      NoQualisPreferences.init();
    }

    // Load snapshots
    if (typeof NoQualisSnapshotLoader !== "undefined") {
      const result = await NoQualisSnapshotLoader.loadAll();
      Zotero.log(`[NoQualis] Loaded ${result.loaded} snapshots`, "info");
      if (result.warnings.length > 0) {
        for (const w of result.warnings) {
          Zotero.log(`[NoQualis] Warning: ${w}`, "warning");
        }
      }
    }

    // Initialize tagger
    if (typeof NoQualisTagger !== "undefined") {
      NoQualisTagger.init();
    }

    // Initialize columns (registers in item tree)
    if (typeof NoQualisColumns !== "undefined") {
      NoQualisColumns.init();
    }

    // Initialize panel (registers in item pane)
    if (typeof NoQualisPanel !== "undefined") {
      NoQualisPanel.init();
    }

    this.initialized = true;
    Zotero.log("[NoQualis] Initialization complete", "info");
  }

  /**
   * Destroy the plugin and clean up resources.
   */
  destroy() {
    Zotero.log("[NoQualis] Shutting down", "info");

    if (typeof NoQualisColumns !== "undefined") NoQualisColumns.destroy();
    if (typeof NoQualisPanel !== "undefined") NoQualisPanel.destroy();
    if (typeof NoQualisTagger !== "undefined") NoQualisTagger.destroy();
    if (typeof NoQualisPreferences !== "undefined") NoQualisPreferences.destroy();

    this.initialized = false;
  }
}
