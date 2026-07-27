/**
 * NoQualis - Batch Tagger
 *
 * Provides a batch action that applies tags with a fixed prefix
 * to items based on their classification.
 *
 * Tag format: "Qualis:<Area>:<Estrato>"
 * Example: "Qualis:Computação:A1"
 *
 * If item already has a tag for the same area, the old tag is
 * replaced before applying the new one.
 *
 * CONSTRAINTS:
 * - MUST NOT access external sources, APIs, or network (R6.7)
 * - MUST NOT use localStorage/sessionStorage (R6.8)
 */

/* global Zotero, NoQualisSnapshotLoader, NoQualisEvaluator */

var NoQualisTagger = {
  /** @type {string} Tag prefix from preferences */
  _prefix: "Qualis",

  /**
   * Initialize the tagger module.
   */
  init() {
    this._prefix = Zotero.Prefs.get("extensions.noqualis.tagPrefix", true) || "Qualis";
  },

  /**
   * Apply Qualis tags to a set of selected items for all active areas.
   * This is the main batch action entry point.
   *
   * @param {object[]} items - Array of Zotero items
   * @returns {Promise<{tagged: number, skipped: number, errors: string[]}>}
   */
  async tagItems(items) {
    const selectedAreas = this._getSelectedAreas();
    const results = { tagged: 0, skipped: 0, errors: [] };

    if (selectedAreas.length === 0) {
      results.errors.push("Nenhuma área selecionada.");
      return results;
    }

    for (const item of items) {
      // Skip non-regular items
      if (typeof item.isRegularItem === "function" && !item.isRegularItem()) {
        results.skipped++;
        continue;
      }

      try {
        let itemTagged = false;

        for (const areaCode of selectedAreas) {
          const snapshot = NoQualisSnapshotLoader.getSnapshot(areaCode);
          if (!snapshot) continue;

          const verdict = NoQualisEvaluator.evaluate(item, areaCode);
          const areaName = snapshot.nome || `Área ${areaCode}`;

          // Only tag items that have a classifiable stratum
          if (verdict.estado === "NAO_CLASSIFICAVEL" || verdict.estado === "NAO_CONSIDERADO") {
            continue;
          }

          const newTag = this._buildTag(areaName, verdict.estrato);

          // Remove existing tag for the same area (if any)
          await this._removeAreaTag(item, areaName);

          // Add new tag
          item.addTag(newTag, 0); // type 0 = user tag
          itemTagged = true;
        }

        if (itemTagged) {
          await item.saveTx();
          results.tagged++;
        } else {
          results.skipped++;
        }
      } catch (e) {
        results.errors.push(`Item ${item.id}: ${e.message}`);
        Zotero.log(`[NoQualis] Tagging error for item ${item.id}: ${e.message}`, "error");
      }
    }

    Zotero.log(
      `[NoQualis] Tagging complete: ${results.tagged} tagged, ${results.skipped} skipped, ${results.errors.length} errors`,
      "info"
    );

    return results;
  },

  /**
   * Apply Qualis tags for a specific area only.
   *
   * @param {object[]} items - Array of Zotero items
   * @param {number} areaCode - Area code to tag for
   * @returns {Promise<{tagged: number, skipped: number, errors: string[]}>}
   */
  async tagItemsForArea(items, areaCode) {
    const results = { tagged: 0, skipped: 0, errors: [] };

    const snapshot = NoQualisSnapshotLoader.getSnapshot(areaCode);
    if (!snapshot) {
      results.errors.push(`Snapshot não carregado para área ${areaCode}`);
      return results;
    }

    const areaName = snapshot.nome || `Área ${areaCode}`;

    for (const item of items) {
      if (typeof item.isRegularItem === "function" && !item.isRegularItem()) {
        results.skipped++;
        continue;
      }

      try {
        const verdict = NoQualisEvaluator.evaluate(item, areaCode);

        if (verdict.estado === "NAO_CLASSIFICAVEL" || verdict.estado === "NAO_CONSIDERADO") {
          results.skipped++;
          continue;
        }

        const newTag = this._buildTag(areaName, verdict.estrato);

        // Remove existing tag for same area
        await this._removeAreaTag(item, areaName);

        // Add new tag
        item.addTag(newTag, 0);
        await item.saveTx();
        results.tagged++;
      } catch (e) {
        results.errors.push(`Item ${item.id}: ${e.message}`);
      }
    }

    return results;
  },

  /**
   * Remove all NoQualis tags from selected items.
   *
   * @param {object[]} items - Array of Zotero items
   * @returns {Promise<{cleaned: number}>}
   */
  async removeAllTags(items) {
    let cleaned = 0;

    for (const item of items) {
      if (typeof item.isRegularItem === "function" && !item.isRegularItem()) {
        continue;
      }

      const tags = item.getTags();
      let modified = false;

      for (const tagObj of tags) {
        const tag = tagObj.tag || tagObj;
        if (this._isNoQualisTag(tag)) {
          item.removeTag(tag);
          modified = true;
        }
      }

      if (modified) {
        await item.saveTx();
        cleaned++;
      }
    }

    return { cleaned };
  },

  /**
   * Build a tag string from area name and stratum.
   * Format: "Qualis:<Area>:<Estrato>"
   * @param {string} areaName
   * @param {string} estrato
   * @returns {string}
   */
  _buildTag(areaName, estrato) {
    return `${this._prefix}:${areaName}:${estrato}`;
  },

  /**
   * Remove existing NoQualis tag for the same area on an item.
   * @param {object} item - Zotero item
   * @param {string} areaName - Area name to match
   */
  async _removeAreaTag(item, areaName) {
    const tags = item.getTags();
    const areaPrefix = `${this._prefix}:${areaName}:`;

    for (const tagObj of tags) {
      const tag = tagObj.tag || tagObj;
      if (tag.startsWith(areaPrefix)) {
        item.removeTag(tag);
      }
    }
  },

  /**
   * Check if a tag is a NoQualis tag.
   * @param {string} tag
   * @returns {boolean}
   */
  _isNoQualisTag(tag) {
    return tag.startsWith(this._prefix + ":");
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
   * Destroy (cleanup on shutdown).
   */
  destroy() {
    // No persistent resources to clean up
  }
};
