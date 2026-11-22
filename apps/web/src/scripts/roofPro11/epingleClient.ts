/* ACAL972 — le repère (épingle) du client sur la carte : retiré à l'effacement, MASQUÉ à la fermeture du
   toit (il resterait dessiné par-dessus les panneaux 3D). Masquer n'oublie rien : l'objet reste en mémoire,
   `pin` et `pinSource` du document ne bougent pas. Aides pures, testables avec une doublure de marqueur. */

/** Le strict nécessaire d'un `maplibregl.Marker` : une doublure de test peut n'avoir que `remove`. */
export interface MarqueurEpingle {
  remove: () => unknown;
  getElement?: () => HTMLElement;
}

/** Retire le marqueur de la carte ; rend `null` pour que l'appelant range sa référence. */
export function retirerMarqueur(marqueur: MarqueurEpingle | null): null {
  marqueur?.remove();
  return null;
}

/** Masque (ou ré-affiche) l'élément du marqueur sans le retirer. Sans marqueur ni élément : rien. */
export function masquerMarqueur(marqueur: MarqueurEpingle | null, masque = true): void {
  const el = marqueur?.getElement?.();
  if (el) el.hidden = masque;
}
