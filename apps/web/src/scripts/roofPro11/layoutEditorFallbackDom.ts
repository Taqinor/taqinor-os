// Nouveau fichier car : layoutEditor.ts est un fichier gelé (C20) — échafaudage DOM de secours (PV29), sorti tel quel.

/**
 * PV29 — ÉCHAFAUDAGE DE SECOURS du panneau « Personnaliser la disposition ».
 *
 * La page astro publique porte ce balisage dans son HTML ; l'écran ERP (ToitureDesign)
 * a copié l'échafaudage `rp9-*` SANS cette fenêtre — l'éditeur y était donc totalement
 * injoignable (aucun bouton pour passer `ctx.layoutMode` à true, donc ni glissé, ni
 * sélection, ni flèches). On construit ici la MÊME structure d'identifiants, en surcouche
 * du conteneur de la carte, UNIQUEMENT quand la page hôte ne l'a pas fournie : la page
 * astro reste strictement inchangée (le `getElementById` trouve son propre balisage et on
 * ne crée rien), et l'ERP gagne la fonctionnalité sans toucher au code React.
 *
 * Volontairement sobre : replié sur un seul bouton tant que l'utilisateur ne l'ouvre pas.
 */
export function buildFallbackLayoutDom(container: HTMLElement | null): void {
  if (typeof document === 'undefined' || !container) return;
  if (document.getElementById('rp9-layout-window')) return; // la page hôte a son balisage
  if (!document.getElementById('rp9-layout-fallback-style')) {
    const style = document.createElement('style');
    style.id = 'rp9-layout-fallback-style';
    style.textContent = [
      '#rp9-layout-window.rp9-layout-fallback{position:absolute;left:8px;bottom:8px;z-index:5;',
      'max-width:340px;max-height:70%;overflow:auto;padding:10px 12px;border:1px solid rgba(255,255,255,.25);',
      'background:rgba(12,17,28,.92);color:#fff;font:12px/1.45 system-ui,sans-serif}',
      '#rp9-layout-window.rp9-layout-fallback[hidden]{display:none}',
      '.rp9-layout-fallback button{border:1px solid rgba(255,255,255,.3);background:transparent;color:inherit;',
      'padding:5px 9px;font:inherit;font-weight:600;cursor:pointer;min-height:30px}',
      '.rp9-layout-fallback button:disabled{opacity:.4;cursor:not-allowed}',
      '.rp9-layout-fallback button[aria-pressed="true"]{border-color:#e0b25c;color:#e0b25c}',
      '.rp9-layout-fallback .rp9-fb-row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px}',
      '.rp9-layout-fallback dl{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin:8px 0 0}',
      '.rp9-layout-fallback dt{opacity:.65;font-size:10px;text-transform:uppercase}',
      '.rp9-layout-fallback dd{margin:0;font-weight:700}',
      '.rp9-layout-fallback .rp9-layout-grid{display:flex;flex-wrap:wrap;gap:2px;margin-top:6px}',
      '.rp9-layout-fallback .rp9-layout-cell{width:14px;height:14px;min-height:0;padding:0;',
      'border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08)}',
      '.rp9-layout-fallback .rp9-layout-cell[data-occupied="true"]{background:#3f7fd0}',
      '.rp9-layout-fallback .rp9-layout-cell[aria-pressed="true"]{background:#e0b25c}',
      '.rp9-layout-fallback label{opacity:.7}',
      '.rp9-layout-fallback input{width:4.5em;border:1px solid rgba(255,255,255,.3);background:transparent;',
      'color:inherit;font:inherit;padding:4px 6px}',
      '#rp9-free-controls[hidden]{display:none}',
      '#rp9-free-measure{font-variant-numeric:tabular-nums;opacity:.85}',
    ].join('');
    document.head.appendChild(style);
  }
  const win = document.createElement('div');
  win.id = 'rp9-layout-window';
  win.className = 'rp9-layout-fallback';
  win.hidden = true;
  win.innerHTML = [
    '<button type="button" id="rp9-layout-toggle" aria-pressed="false">Déplacer les panneaux</button>',
    '<div id="rp9-layout-panel" hidden>',
    // PV30 — les deux modes, côte à côte. La lattice reste le mode d'entrée.
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-mode-lattice" aria-pressed="true">Emplacements validés</button>',
    '<button type="button" id="rp9-layout-mode-free" aria-pressed="false">Placement libre</button>',
    '</div>',
    '<div id="rp9-free-controls" hidden>',
    '<div class="rp9-fb-row">',
    '<label for="rp9-free-setback">Retrait de rive (cm)</label>',
    '<input id="rp9-free-setback" type="text" inputmode="decimal" step="any" size="4">',
    '<label for="rp9-free-gap">Écart panneaux (cm)</label>',
    '<input id="rp9-free-gap" type="text" inputmode="decimal" step="any" size="4">',
    '</div>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-free-add" aria-pressed="false">＋ Ajouter un panneau</button>',
    '<span id="rp9-free-measure" aria-live="polite"></span>',
    '</div>',
    '</div>',
    '<dl>',
    '<div><dd id="rp9-layout-count">—</dd><dt>Posés</dt></div>',
    '<div><dd id="rp9-layout-kwc">—</dd><dt>Puissance</dt></div>',
    '<div><dd id="rp9-layout-free">—</dd><dt>Libres</dt></div>',
    '<div><dd id="rp9-layout-cover">—</dd><dt>Couverture</dt></div>',
    '</dl>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-minus" aria-label="Retirer un panneau">−</button>',
    '<button type="button" id="rp9-layout-plus" aria-label="Ajouter un panneau">+</button>',
    '<button type="button" id="rp9-layout-fill">Remplir</button>',
    '<button type="button" id="rp9-layout-reset">↺ Optimale</button>',
    '</div>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-select" aria-pressed="false">▭ Sélection</button>',
    '<button type="button" id="rp9-layout-row" aria-pressed="false">⇔ Rangée</button>',
    '<button type="button" id="rp9-layout-clear-sel">✕ Effacer</button>',
    // PV34 — compteur TOUJOURS visible : on doit savoir à tout instant combien de
    // panneaux on tient, sans relire une note qui change à chaque geste.
    '<span id="rp9-layout-selcount" data-rp9-selcount="0" aria-live="polite">Aucun panneau sélectionné</span>',
    '</div>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-undo" disabled>↶ Annuler</button>',
    '<button type="button" id="rp9-layout-redo" disabled>↷ Rétablir</button>',
    '</div>',
    '<div class="rp9-fb-row" id="rp9-layout-azimuth" hidden>',
    '<span>Azimut</span>',
    '<button type="button" id="rp9-layout-az-minus" aria-label="Diminuer l’azimut d’un degré">−</button>',
    '<span id="rp9-layout-az-value">—</span>',
    '<button type="button" id="rp9-layout-az-plus" aria-label="Augmenter l’azimut d’un degré">+</button>',
    '</div>',
    '<div id="rp9-layout-grid" class="rp9-layout-grid" role="group" aria-label="Plan des emplacements de panneaux"></div>',
    '<p id="rp9-layout-note" aria-live="polite"></p>',
    '</div>',
  ].join('');
  container.appendChild(win);
}
