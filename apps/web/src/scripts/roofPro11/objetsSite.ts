// ACAL533 — bloc replié « Objets du site » : tous les obstacles de TOUS les pans en un tableau
// (type, cotes, hauteur, provenance, pan), filtrable par type et par provenance. Lecture seule :
// aucune édition, aucun export ; un clic sélectionne l'obstacle sur la carte.
import { isNonEngageable, type Obstacle, type ObstacleProvenance } from '../../lib/obstacles';
import { areaLabel } from '../../lib/roofAreas';
import { $, esc } from './dom';
import type { Ctx } from './context';
import { OBSTACLE_TYPES } from './types';

export interface LigneObjet {
  id: string;
  panId: string;
  pan: string;
  type: string;
  typeLabel: string;
  cotes: string;
  hauteur: string;
  provenance: string;
  provenanceLabel: string;
  nonMesure: boolean;
}

export interface FiltresObjets {
  type?: string;
  provenance?: string;
}

const PROVENANCES: Record<string, string> = {
  RELEVE: 'Relevé sur place',
  MESURE: 'Relevé sur place',
  RELEVE_DOUTEUX: 'Relevé douteux',
  MESURE_DOUTEUX: 'Relevé douteux',
  DECLARE_CLIENT: 'Déclaré par le client',
  PLAN: 'Plan',
  DEVINE: 'Deviné',
  ECARTE: 'Écarté',
};
const SANS_PROVENANCE = 'Non renseignée';
const fr1 = (n: number): string => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Les obstacles de tous les pans, les provenances NON mesurées d'abord (ordre d'origine sinon). */
export function lignesObjetsSite(
  ctx: Pick<Ctx, 'obstacles' | 'areas' | 'activeAreaId'>,
  filtres: FiltresObjets = {},
): LigneObjet[] {
  const lignes: LigneObjet[] = [];
  (ctx.areas ?? []).forEach((a, i) => {
    const obstacles: Obstacle[] = (a.id === ctx.activeAreaId ? ctx.obstacles : a.obstacles) ?? [];
    for (const o of obstacles) {
      const type = o.type ?? '';
      const provenance = o.provenance ?? '';
      lignes.push({
        id: o.id,
        panId: a.id,
        pan: a.label || areaLabel(i),
        type,
        typeLabel: OBSTACLE_TYPES.find((t) => t.id === type)?.label ?? 'Obstacle',
        cotes: `${fr1(o.lengthM)} × ${fr1(o.widthM)} m`,
        hauteur: o.heightM != null ? `${fr1(o.heightM)} m` : '—',
        provenance,
        provenanceLabel: PROVENANCES[provenance] ?? SANS_PROVENANCE,
        nonMesure: isNonEngageable((provenance || null) as ObstacleProvenance | null),
      });
    }
  });
  const gardees = lignes.filter((l) => (!filtres.type || l.type === filtres.type)
    && (!filtres.provenance || l.provenance === filtres.provenance));
  return [...gardees.filter((l) => l.nonMesure), ...gardees.filter((l) => !l.nonMesure)];
}

/** Clic sur une ligne : le pan de l'obstacle devient actif d'abord (geste existant), puis l'obstacle est
 *  sélectionné — `selectObstacle` ne sait choisir que dans les obstacles du pan actif. */
export function ouvrirObjet(
  ligne: Pick<LigneObjet, 'id' | 'panId'>,
  activeAreaId: string,
  deps: { selectArea: (id: string) => void; selectObstacle: (id: string) => void },
): void {
  if (ligne.panId !== activeAreaId) deps.selectArea(ligne.panId);
  deps.selectObstacle(ligne.id);
}

/** Monte le bloc replié à côté de `rp9-env-panel` (créé à l'exécution, absent tant qu'aucun obstacle). */
export function monterObjetsSite(
  ctx: Ctx,
  deps: { selectArea: (id: string) => void; selectObstacle: (id: string) => void },
): { redessiner: () => void } {
  const ancre = $('rp9-env-panel');
  if (!ancre || typeof document.createElement !== 'function') return { redessiner: () => undefined };
  const bloc = document.createElement('details');
  bloc.id = 'rp9-objets-site';
  bloc.className = 'rp9-objets-site mt-2 text-xs';
  bloc.hidden = true;
  ancre.insertAdjacentElement('afterend', bloc);
  const filtres: FiltresObjets = {};
  const options = (valeurs: Array<[string, string]>, choisi: string | undefined, tous: string): string =>
    [`<option value="">${tous}</option>`, ...valeurs.map(([v, l]) => `<option value="${esc(v)}"${v === choisi ? ' selected' : ''}>${esc(l)}</option>`)].join('');

  function redessiner(): void {
    const toutes = lignesObjetsSite(ctx);
    bloc.hidden = toutes.length === 0;
    if (toutes.length === 0) return;
    const uniques = (cle: 'type' | 'provenance', label: 'typeLabel' | 'provenanceLabel'): Array<[string, string]> => [
      ...new Map(toutes.map((l) => [l[cle], l[label]] as [string, string])).entries(),
    ];
    const lignes = lignesObjetsSite(ctx, filtres);
    bloc.innerHTML =
      `<summary class="cursor-pointer min-h-11 flex items-center font-semibold">Objets du site (${toutes.length})</summary>` +
      `<div class="flex flex-wrap gap-2 my-2">` +
      `<label class="inline-flex items-center gap-1" for="rp9-objets-type">Type` +
      `<select id="rp9-objets-type" class="rp9-input">${options(uniques('type', 'typeLabel'), filtres.type, 'Tous')}</select></label>` +
      `<label class="inline-flex items-center gap-1" for="rp9-objets-prov">Provenance` +
      `<select id="rp9-objets-prov" class="rp9-input">${options(uniques('provenance', 'provenanceLabel'), filtres.provenance, 'Toutes')}</select></label></div>` +
      `<ul class="flex flex-col gap-1">${lignes.map((l) => `<li><button type="button" class="rp9-btn w-full text-left" data-objet="${esc(l.id)}" data-pan="${esc(l.panId)}">` +
        `${esc(l.typeLabel)} · ${esc(l.cotes)} · hauteur ${esc(l.hauteur)} · ${esc(l.provenanceLabel)} · ${esc(l.pan)}</button></li>`).join('')}</ul>`;
  }

  bloc.addEventListener('click', (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>('[data-objet]');
    if (b?.dataset.objet && b.dataset.pan) ouvrirObjet({ id: b.dataset.objet, panId: b.dataset.pan }, ctx.activeAreaId, deps);
  });
  bloc.addEventListener('change', (e) => {
    const t = e.target as HTMLSelectElement;
    if (t.id === 'rp9-objets-type') filtres.type = t.value || undefined;
    else if (t.id === 'rp9-objets-prov') filtres.provenance = t.value || undefined;
    else return;
    redessiner();
  });
  redessiner();
  return { redessiner };
}
