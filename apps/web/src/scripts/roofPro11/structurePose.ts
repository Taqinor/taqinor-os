// ACAL1522 — « Structure et pose » : coupures, châssis N × M et pieds, visibles sans « Déplacer les panneaux ».
// Les trois montages (`monterChampsCoupures`, `monterChampsChassis`, `monterChampPortee`) rangent leur rubrique dans
// `#rp9-layout-panel`, caché tant que le mode déplacement est éteint : ce groupe les en sort, tels quels.

const RUBRIQUES = ['rp9-coupures', 'rp9-portee', 'rp9-chassis'] as const;

/** Range les rubriques déjà montées dans un seul groupe, ouvertes, juste avant le panneau de déplacement. */
export function grouperStructurePose(doc: Document = document): HTMLElement | null {
  const panneau = doc.getElementById('rp9-layout-panel');
  const fenetre = panneau?.parentElement;
  if (!panneau || !fenetre) return null;
  let groupe = doc.getElementById('rp9-structure-pose');
  if (!groupe) {
    groupe = doc.createElement('section');
    groupe.id = 'rp9-structure-pose';
    groupe.className = 'mt-4 text-sm';
    groupe.setAttribute('aria-label', 'Structure et pose');
    groupe.innerHTML = '<p class="tech-label text-brass-300">Structure et pose</p>';
    fenetre.insertBefore(groupe, panneau);
  }
  for (const id of RUBRIQUES) {
    const rubrique = doc.getElementById(id) as HTMLDetailsElement | null;
    if (!rubrique || rubrique.parentElement === groupe) continue;
    groupe.appendChild(rubrique);
    rubrique.open = true;
  }
  return groupe;
}
