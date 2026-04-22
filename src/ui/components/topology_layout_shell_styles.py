"""Shared CSS assets for the HT-076 topology shell."""

_TOPOLOGY_LAYOUT_SHELL_CSS = """
<style id="ht-topology-layout-shell">
  #ht-topology-page {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-height: 0;
    height: 100%;
    overflow: hidden;
    gap: 12px;
  }
  #ht-topology-page > :not(#ht-topology-shell) {
    flex-shrink: 0;
  }
  #ht-topology-shell {
    display: flex;
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    width: 100%;
    position: relative;
    overflow: hidden;
    align-items: stretch;
  }
  #ht-topology-left-rail {
    display: flex;
    flex-direction: column;
    flex: 0 0 260px;
    min-width: 244px;
    max-width: 260px;
    min-height: 0;
    padding: 12px;
    gap: 10px;
    overflow-x: hidden;
    overflow-y: auto;
    background: color-mix(in srgb, var(--ht-bg-surface-raised) 96%, transparent);
    border-right: 1px solid var(--ht-border);
    transition:
      flex-basis var(--ht-transition-fast),
      min-width var(--ht-transition-fast),
      max-width var(--ht-transition-fast),
      padding var(--ht-transition-fast),
      gap var(--ht-transition-fast);
  }
  #ht-topology-left-rail.ht-topology-left-rail--compact {
    flex-basis: 64px;
    min-width: 64px;
    max-width: 64px;
    padding: 8px 6px;
    gap: 6px;
  }
  #ht-topology-left-rail .ht-topology-rail-section {
    width: 100%;
    border: 1px solid var(--ht-border);
    border-radius: 14px;
    overflow: hidden;
    background: color-mix(in srgb, var(--ht-bg-surface) 82%, transparent);
  }
  #ht-topology-left-rail .q-expansion__content {
    padding: 0 12px 12px;
  }
  #ht-topology-left-rail .q-expansion-item__container > .q-item {
    min-height: 42px;
  }
  #ht-topology-left-rail.ht-topology-left-rail--compact .q-expansion-item__container > .q-item {
    justify-content: center;
    padding-left: 8px;
    padding-right: 8px;
  }
  #ht-topology-left-rail.ht-topology-left-rail--compact .q-item__label,
  #ht-topology-left-rail.ht-topology-left-rail--compact .q-item__section--side {
    display: none !important;
  }
  #ht-topology-left-rail.ht-topology-left-rail--compact .ht-topology-rail-section {
    border-radius: 12px;
  }
  #ht-topology-left-rail .ht-topology-palette-slot > * {
    width: 100% !important;
    min-width: 0 !important;
    max-width: none !important;
    flex: 1 1 auto !important;
    background: transparent !important;
    border-right: none !important;
    padding: 8px 0 0 !important;
  }
  #ht-topology-left-rail .ht-topology-palette-slot > * > :first-child {
    display: none !important;
  }
  #ht-topology-left-rail .ht-topology-stencils-slot #ht-stencils-panel {
    width: 100% !important;
    min-width: 0 !important;
    max-width: none !important;
    background: transparent !important;
    border-right: none !important;
    padding: 8px 0 0 !important;
  }
  #ht-topology-left-rail .ht-topology-stencils-slot #ht-stencils-panel > :first-child {
    display: none !important;
  }
  #ht-topology-left-rail #ht-stencil-collapse-btn {
    display: none !important;
  }
  #ht-topology-workspace {
    display: flex;
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    position: relative;
    overflow: hidden;
  }
  #ht-topology-canvas-stage {
    position: relative;
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
  }
  #ht-topology-right-rail {
    display: flex;
    flex-direction: column;
    width: 0;
    min-width: 0;
    flex: 0 0 0;
    min-height: 0;
    max-height: 100%;
    max-width: 0;
    overflow: hidden;
    z-index: 12;
    transition:
      width var(--ht-transition-fast),
      min-width var(--ht-transition-fast),
      max-width var(--ht-transition-fast),
      flex-basis var(--ht-transition-fast);
  }
  #ht-topology-right-rail > * {
    flex-shrink: 0;
  }
  #ht-topology-right-rail:has(> .ht-right-rail-panel[style*="display: flex"]) {
    width: min(320px, 100%);
    min-width: min(320px, 100%);
    max-width: min(320px, 100%);
    flex-basis: min(320px, 100%);
    overflow-x: hidden;
    overflow-y: auto;
  }
  @media (max-width: 1180px) {
    #ht-topology-right-rail {
      position: absolute;
      top: 12px;
      right: 12px;
      bottom: 12px;
      pointer-events: none;
    }
    #ht-topology-right-rail:has(> .ht-right-rail-panel[style*="display: flex"]) {
      width: min(320px, calc(100vw - 84px));
      min-width: min(320px, calc(100vw - 84px));
      max-width: calc(100vw - 84px);
      flex-basis: min(320px, calc(100vw - 84px));
    }
    #ht-topology-right-rail > * {
      width: 100% !important;
      min-width: 0 !important;
      pointer-events: auto;
      box-shadow: var(--ht-shadow-lg);
    }
  }
  @media (max-width: 960px) {
    #ht-topology-left-rail {
      position: absolute;
      top: 12px;
      left: 12px;
      bottom: 12px;
      max-width: min(260px, calc(100vw - 48px));
      z-index: 18;
      box-shadow: var(--ht-shadow-lg);
    }
  }
</style>
"""