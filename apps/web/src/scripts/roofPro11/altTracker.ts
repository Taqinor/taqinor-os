/**
 * Suivi de la touche Alt (jamais mémorisé au-delà de la pression) : partagé par `mapDraw.ts`
 * (suspend l'aide d'angle le temps d'un point) et `obstaclesUi.ts` (Alt+clic supprime un
 * sommet). ENF19 — c'était le même bloc recopié. `etat.enfoncee` est relu à chaque événement ;
 * obstaclesUi peut aussi l'écraser avec la valeur portée par l'événement souris (source la
 * plus sûre).
 */
export function suivreAlt(): { enfoncee: boolean } {
  const etat = { enfoncee: false };
  if (typeof document.addEventListener === 'function') {
    document.addEventListener('keydown', (e) => {
      if ((e as KeyboardEvent).key === 'Alt') etat.enfoncee = true;
    });
    document.addEventListener('keyup', (e) => {
      if ((e as KeyboardEvent).key === 'Alt') etat.enfoncee = false;
    });
    // Le focus peut partir pendant qu'Alt est enfoncée (Alt+Tab) : on ne garde jamais l'état.
    window.addEventListener?.('blur', () => {
      etat.enfoncee = false;
    });
  }
  return etat;
}
