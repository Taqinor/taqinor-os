// W1 — marqueur « Recommandé » sur la bonne option de CHAQUE groupe (extrait de
// `roof-tool-pro11.ts::updateRecoBadges`, ACAL562 : corps inchangé, déplacé tel quel).

/** Les options recommandées lues par les puces (sous-ensemble de `rec.recommendedOptions`). */
export interface OptionsRecommandees {
  family: string;
  tiltDeg: number;
  panelOrientation: string;
  azimuthDeg: number;
  margin: string;
}

/**
 * Calculé depuis `rec.recommendedOptions` (pur, indépendant de la sélection courante) :
 * l'utilisateur voit « vous avez choisi X mais Y est recommandé ».
 */
export function majBadgesReco(ro: OptionsRecommandees | null | undefined): void {
  const show = (b: Element | null, on: boolean) => {
    const badge = b?.querySelector<HTMLElement>('.rp9-reco-badge');
    if (badge) badge.hidden = !on;
  };
  // Famille
  document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => {
    show(b, !!ro && b.dataset.family === ro.family);
  });
  // Inclinaison : badge le chip numérique == tilt arrondi, sinon le chip « reco ».
  const tiltRounded = ro ? Math.round(ro.tiltDeg) : null;
  const tiltChips = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-tilt]'));
  const numericMatch = tiltChips.find((b) => b.dataset.tilt !== 'reco' && Number(b.dataset.tilt) === tiltRounded);
  tiltChips.forEach((b) => {
    if (!ro) return show(b, false);
    if (numericMatch) show(b, b === numericMatch);
    else show(b, b.dataset.tilt === 'reco'); // aucun chip numérique ne colle → badge « Recommandé »
  });
  // Portrait / paysage (« Auto » jamais badgé)
  document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) => {
    show(b, !!ro && b.dataset.orient !== 'auto' && b.dataset.orient === ro.panelOrientation);
  });
  // Azimut : 'south' si l'azimut recommandé est plein sud, sinon 'aligned'.
  const azReco = ro ? (ro.azimuthDeg === 180 ? 'south' : 'aligned') : null;
  document.querySelectorAll<HTMLButtonElement>('[data-azimuth]').forEach((b) => {
    show(b, b.dataset.azimuth === azReco);
  });
  // Marge ('keep' / 'remove')
  document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => {
    show(b, !!ro && b.dataset.margin === ro.margin);
  });
}
