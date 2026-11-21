/**
 * ACAL416 — « Je ne connais pas la pente » sur la carte : un pourcentage, ou une portée et une
 * hauteur de faîtage, donnent la pente en degrés ET la source à ranger dans `pitchSource`.
 * Mêmes formules que `frontend/src/features/calepinage/SaisiePente.helpers.js`
 * (`penteDepuisPourcentage`, `penteDepuisCotes`) et `prefill.ts::penteDecrite` (parité testée).
 * Portée vide ou nulle, nombre illisible : rien n'est appliqué, jamais 0°.
 */
export type SourceAide =
  | { mode: 'pourcentage'; pourcentage: number }
  | { mode: 'cotes'; porteeM: number; hauteurFaitageM: number };

export interface EntreeAide { pourcentage?: string; porteeM?: string; hauteurFaitageM?: string }
export type ResultatAide = { degres: number; source: SourceAide } | { erreur: string };

const DEG = 180 / Math.PI;
const nombre = (v: string | undefined): number | null => {
  if (v == null || v.trim() === '') return null;
  const n = Number(v.trim().replace(',', '.'));
  return Number.isFinite(n) ? n : null;
};

/** `mode` dit quelle saisie vient d'être faite (la dernière gagne). */
export function penteDepuisAide(e: EntreeAide, mode: 'pourcentage' | 'cotes'): ResultatAide {
  if (mode === 'pourcentage') {
    const p = nombre(e.pourcentage);
    if (p === null) return { erreur: 'Pourcentage illisible : rien n’est appliqué.' };
    return { degres: Math.atan(p / 100) * DEG, source: { mode, pourcentage: p } };
  }
  const portee = nombre(e.porteeM);
  const hauteur = nombre(e.hauteurFaitageM);
  if (portee === null || portee === 0) return { erreur: 'La portée est vide ou nulle : rien n’est appliqué.' };
  if (hauteur === null) return { erreur: 'La hauteur de faîtage est illisible : rien n’est appliquée.' };
  return { degres: Math.atan(hauteur / portee) * DEG, source: { mode, porteeM: portee, hauteurFaitageM: hauteur } };
}

/** Monte les champs (`step="any"`) sous la ligne « Pente fine » ; `appliquer` reçoit la pente et sa source. */
export function monterAidePente(
  ligne: HTMLElement | null,
  appliquer: (degres: number, source: SourceAide) => void,
): void {
  if (!ligne?.parentElement || typeof document === 'undefined') return;
  const bloc = document.createElement('div');
  bloc.id = 'rp9-pente-aide';
  bloc.className = 'flex flex-wrap items-center gap-2 text-xs text-lune-soft';
  const champ = (cle: keyof EntreeAide, libelle: string) => {
    const l = document.createElement('label');
    l.textContent = `${libelle} `;
    const i = document.createElement('input');
    i.type = 'number'; i.step = 'any'; i.id = `rp9-pente-aide-${cle}`; i.className = 'w-20';
    l.appendChild(i);
    bloc.appendChild(l);
    return i;
  };
  const champs = { pourcentage: champ('pourcentage', 'Pente en %'), porteeM: champ('porteeM', 'Portée (m)'), hauteurFaitageM: champ('hauteurFaitageM', 'Hauteur faîtage (m)') };
  const msg = document.createElement('p');
  msg.setAttribute('aria-live', 'polite');
  bloc.appendChild(msg);
  const lire = (mode: 'pourcentage' | 'cotes') => {
    const r = penteDepuisAide({ pourcentage: champs.pourcentage.value, porteeM: champs.porteeM.value, hauteurFaitageM: champs.hauteurFaitageM.value }, mode);
    if ('erreur' in r) { msg.textContent = r.erreur; return; }
    msg.textContent = '';
    appliquer(r.degres, r.source);
  };
  champs.pourcentage.addEventListener('change', () => lire('pourcentage'));
  champs.porteeM.addEventListener('change', () => lire('cotes'));
  champs.hauteurFaitageM.addEventListener('change', () => lire('cotes'));
  ligne.parentElement.insertBefore(bloc, ligne.nextSibling);
}
