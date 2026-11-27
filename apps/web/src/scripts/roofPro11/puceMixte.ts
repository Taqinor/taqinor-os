// Nouveau fichier car : roof-tool-pro11.ts est un fichier gelé (C20) — puce « Mixte » (PV62), sortie telle quelle (DOM pur, appelée au chargement).

// PV62 — PUCE « Mixte » (pose choisie rangée par rangée) : ajoutée au groupe de pose si
// la page ne la fournit pas déjà, AVANT le câblage ci-dessous pour qu'elle reçoive le
// même écouteur que les autres puces `[data-orient]` (verrou / re-clic = auto). Toit
// PLAT uniquement : en pente la pose affleurante n'a pas de mixte (masquée par
// `syncRoofTypeChips`). Idempotente.
export function ensureMixedOrientChip() {
  if (document.querySelector('[data-orient="mixed"]')) return;
  const sibling =
    document.querySelector<HTMLButtonElement>('[data-orient="landscape"]') ??
    document.querySelector<HTMLButtonElement>('[data-orient="portrait"]');
  const group = sibling?.parentElement;
  if (!sibling || !group) return;
  const chip = document.createElement('button');
  chip.type = 'button';
  chip.className = sibling.className;
  chip.dataset.orient = 'mixed';
  chip.setAttribute('aria-pressed', 'false');
  chip.title =
    'Pose mixte : portrait ou paysage choisi rangée par rangée. Ne pose jamais moins de panneaux qu’une pose uniforme.';
  chip.textContent = 'Mixte';
  const badge = sibling.querySelector('.rp9-reco-badge');
  if (badge) {
    const clone = badge.cloneNode(true) as HTMLElement;
    clone.hidden = true; // le mixte ne se BADGE jamais « Recommandé » (il ne balaie pas)
    chip.appendChild(clone);
  }
  group.appendChild(chip);
}
