/**
 * ACAL413 — UN FILET POUR LES EFFACEMENTS DE MASSE.
 *
 * « Tout effacer » (obstacles) était sans photo d'historique : un clic perdait tous les obstacles
 * sans retour. Il photographie maintenant l'atelier (`ctx.pushWorkshopHistory`, CAL100) AVANT de
 * vider, puis montre un bandeau « Obstacles effacés — Annuler » (`role="status"`) qui reste affiché
 * jusqu'au prochain geste d'édition ou « Fermer » — aucune durée inventée. « Effacer » (tout le
 * site), lui, ne s'annule pas (consommation et ombres ne se restaurent pas) : il DEMANDE d'abord,
 * en nommant ce qui sera perdu, et ne demande rien quand il n'y a rien à perdre.
 */
export interface BandeauAnnuler {
  montrer: (message: string) => void;
  fermer: () => void;
}

/** Bandeau sous l'ancre (la barre du toit). `annuler` = `undo` d'ACAL412. */
export function creerBandeauAnnuler(ancre: HTMLElement | null, annuler: () => boolean): BandeauAnnuler {
  let el: HTMLElement | null = null;
  const fermer = () => {
    el?.remove();
    el = null;
  };
  const montrer = (message: string) => {
    fermer();
    const parent = ancre?.parentElement;
    if (!parent || typeof document === 'undefined') return;
    el = document.createElement('div');
    el.id = 'rp9-bandeau-annuler';
    el.setAttribute('role', 'status');
    el.className = 'text-sm text-lune-faint';
    el.append(`${message} — `);
    for (const [libelle, agir] of [
      ['Annuler', () => { annuler(); fermer(); }],
      ['Fermer', fermer],
    ] as const) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'underline mr-2';
      b.textContent = libelle;
      b.addEventListener('click', agir);
      el.append(b);
    }
    parent.insertAdjacentElement('afterend', el);
  };
  return { montrer, fermer };
}

/** Le bandeau se retire au prochain geste d'édition : toute photo d'historique le ferme. */
export function fermerAuProchainGeste(
  ctx: { pushWorkshopHistory?: () => void },
  bandeau: Pick<BandeauAnnuler, 'fermer'>,
): void {
  const pousser = ctx.pushWorkshopHistory;
  ctx.pushWorkshopHistory = () => {
    bandeau.fermer();
    pousser?.();
  };
}

/** Vide les obstacles APRÈS la photo d'historique (sans elle, « Annuler » ne rendrait rien). */
export function viderObstaclesAnnulable(ctx: { obstacles: unknown[]; pushWorkshopHistory?: () => void }): number {
  const n = ctx.obstacles.length;
  if (!n) return 0;
  ctx.pushWorkshopHistory?.();
  ctx.obstacles = [];
  return n;
}

export interface AEffacer {
  pans: number;
  obstacles: number;
  consommation: boolean;
  ombres: boolean;
}

/** La question de « Effacer », ou null quand il n'y a rien à perdre. */
export function questionEffacer(a: AEffacer): string | null {
  const parts = [
    a.pans ? `${a.pans} pan${a.pans > 1 ? 's' : ''}` : '',
    a.obstacles ? `${a.obstacles} obstacle${a.obstacles > 1 ? 's' : ''}` : '',
    a.consommation ? 'la consommation saisie' : '',
    a.ombres ? 'les ombres tracées' : '',
  ].filter(Boolean);
  if (!parts.length) return null;
  const liste = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} et ${parts[parts.length - 1]}` : parts[0];
  return `Effacer ${liste} ?`;
}

/** Demande (confirmation injectable, `window.confirm` par défaut) ; true = on peut effacer. */
export function confirmerEffacer(a: AEffacer, confirmer?: (m: string) => boolean): boolean {
  const q = questionEffacer(a);
  if (!q) return true;
  return (confirmer ?? ((m: string) => (typeof window === 'undefined' ? true : window.confirm(m))))(q);
}
