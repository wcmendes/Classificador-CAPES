/* eslint-env mozilla/bootstrapped-addon */
/* global Components, ChromeUtils */

/**
 * NoQualis - Classificador CAPES para Zotero 7
 *
 * Bootstrap lifecycle for Zotero 7 plugin.
 * This file handles install, startup, shutdown, and uninstall events.
 *
 * CONSTRAINTS:
 * - Plugin MUST NOT access external sources, APIs, or network (R6.7)
 * - Plugin MUST NOT use localStorage/sessionStorage (R6.8)
 * - All data comes exclusively from local snapshots
 */

var NoQualis;

async function install(data, reason) {
  // Called when the plugin is first installed
  // No-op: initialization happens in startup
}

async function startup({ id, version, resourceURI, rootURI }, reason) {
  // Load the main module
  Services.scriptloader.loadSubScript(rootURI + "src/index.js");
  NoQualis = new NoQualisPlugin();
  await NoQualis.init({ id, version, rootURI });
}

function shutdown({ id, version, resourceURI, rootURI }, reason) {
  if (NoQualis) {
    NoQualis.destroy();
    NoQualis = null;
  }
}

function uninstall(data, reason) {
  // Called when the plugin is uninstalled
  // Cleanup is handled in shutdown
}
