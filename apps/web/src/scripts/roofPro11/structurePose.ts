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

/** ACAL1530 — « Personnaliser la disposition » reste visible quand le pavage ne retient aucun emplacement : une
 *  phrase dit pourquoi (seuil d'accès solaire, retraits, obstacles) et « Déplacer » ne se touche pas dans le vide. */
export function direPoseIndisponible(fenetre: HTMLElement, bouton: HTMLButtonElement | null, indisponible: boolean): void {
  let phrase = fenetre.querySelector<HTMLElement>('#rp9-layout-indispo');
  if (indisponible && !phrase) {
    phrase = fenetre.ownerDocument.createElement('p');
    phrase.id = 'rp9-layout-indispo';
    phrase.setAttribute('role', 'status');
    phrase.textContent = 'Aucun emplacement à personnaliser : tous sont sous le seuil d’accès solaire, ou écartés par les retraits et les obstacles.';
    fenetre.prepend(phrase);
  }
  if (phrase) phrase.hidden = !indisponible;
  if (bouton && (indisponible || bouton.dataset.indispoSeuil)) {
    bouton.disabled = indisponible;
    if (indisponible) bouton.dataset.indispoSeuil = '1'; else delete bouton.dataset.indispoSeuil;
  }
}
