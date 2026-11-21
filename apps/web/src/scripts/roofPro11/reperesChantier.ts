// ACAL593 — couche « Repères de chantier » (point d'accroche antichute, accès, passage de câble).
// Contrat ACAL599 : clé racine `reperesChantier` (jamais `reperes`), point en [lng, lat], rayon SAISI
// (`rayonM`, null = non saisi : AUCUN rayon par défaut, aucun cercle). Le panneau est créé à
// l'exécution sous `#rp9-mesure-list`, à l'image de `mesureUi.ts::createMesureUi`.
import { type LngLat } from '../../lib/roof';
import { DEG2RAD, GOLD, WGS84_RADIUS } from './constants';
import { type Ctx } from './context';
import { esc } from './dom';

export type TypeRepere = 'ancre_antichute' | 'acces' | 'passage_cable' | 'autre';
export const TYPES_REPERE: Record<TypeRepere, string> = {
  ancre_antichute: "Point d'accroche (antichute)", acces: 'Accès', passage_cable: 'Passage de câble', autre: 'Autre',
};
export interface RepereChantier { id: string; type: TypeRepere; texte?: string; rayonM: number | null; point: LngLat; [cle: string]: unknown }
export const CHAMP_RAYON = 'Rayon (m)';

const copie = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const estPoint = (p: unknown): p is LngLat => Array.isArray(p) && p.length === 2 && p.every((v) => Number.isFinite(v));

/** Le rayon SAISI : vide, nul, négatif ou illisible ⇒ refus qui nomme le champ. */
export function validerRayon(saisie: string): { ok: true; rayonM: number } | { ok: false; motif: string } {
  const v = Number(String(saisie ?? '').trim().replace(',', '.'));
  if (String(saisie ?? '').trim() === '' || !Number.isFinite(v) || v <= 0) {
    return { ok: false, motif: `${CHAMP_RAYON} : saisissez un rayon supérieur à 0 (en mètres).` };
  }
  return { ok: true, rayonM: v };
}

/** Les repères du document relu (entrées hors contrat écartées, clés inconnues gardées) ; aucun ⇒ []. */
export function lireReperesChantier(doc: unknown): RepereChantier[] {
  const brut = (doc as { reperesChantier?: unknown } | null | undefined)?.reperesChantier;
  if (!Array.isArray(brut)) return [];
  return brut.filter((r): r is RepereChantier => !!r && typeof r === 'object' && typeof r.id === 'string' && r.id.trim() !== ''
    && r.type in TYPES_REPERE && estPoint(r.point))
    .map((r) => ({ ...copie(r), rayonM: typeof r.rayonM === 'number' && r.rayonM > 0 ? r.rayonM : null }));
}

/** Fragment du document : `{ reperesChantier }` s'il y en a, `{}` sinon (document inchangé à l'octet). */
export function emettreReperesChantier(liste: RepereChantier[] | undefined): { reperesChantier?: RepereChantier[] } {
  return Array.isArray(liste) && liste.length ? { reperesChantier: copie(liste) } : {};
}

/** Anneau [lng, lat] du cercle de rayon SAISI, ou `null` sans rayon (jamais un rayon par défaut). */
export function cercleDuRepere(r: Pick<RepereChantier, 'point' | 'rayonM'>, n = 48): LngLat[] | null {
  if (typeof r.rayonM !== 'number' || !(r.rayonM > 0)) return null;
  const [lng, lat] = r.point;
  const dLat = (r.rayonM / WGS84_RADIUS) / DEG2RAD;
  const dLng = dLat / Math.cos(lat * DEG2RAD);
  const anneau: LngLat[] = [];
  for (let i = 0; i <= n; i++) {
    const a = (2 * Math.PI * i) / n;
    anneau.push([lng + dLng * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  return anneau;
}

export function reperesGeoJSON(liste: readonly RepereChantier[]) {
  const features: object[] = [];
  for (const r of liste) {
    const label = `${TYPES_REPERE[r.type]}${r.texte ? ` — ${r.texte}` : ''}`;
    features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: r.point }, properties: { label } });
    const c = cercleDuRepere(r);
    if (c) features.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [c] }, properties: { label: '' } });
  }
  return { type: 'FeatureCollection', features };
}

interface CarteReperes {
  getSource?(id: string): { setData(d: unknown): void } | undefined;
  addSource?(id: string, s: unknown): void; addLayer?(l: unknown): void;
  isStyleLoaded?(): boolean; once?(ev: string, fn: () => void): void;
}
export interface ReperesUi { handleMapClick(p: LngLat): boolean; render(): void; list(): RepereChantier[] }

export function createReperesUi(ctx: Ctx, map: CarteReperes, deps: { setStatus?: (m: string) => void } = {}): ReperesUi {
  const liste = (): RepereChantier[] => (ctx.reperesChantier ??= []);
  let arme = false;
  const ancre = typeof document !== 'undefined' ? document.getElementById('rp9-mesure-list') : null;
  const bloc = ancre ? document.createElement('div') : null;
  if (bloc && ancre) {
    bloc.className = 'space-y-2 border border-border p-3';
    bloc.innerHTML = `<p class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Repères de chantier</p>
      <label class="block text-xs text-foreground">Type <select id="rp9-repere-type" class="h-11 w-full border border-border bg-transparent text-sm text-foreground">${
        Object.entries(TYPES_REPERE).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select></label>
      <label class="block text-xs text-foreground">Texte <input id="rp9-repere-texte" type="text" maxlength="200" class="h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground"></label>
      <label class="block text-xs text-foreground">${CHAMP_RAYON} <input id="rp9-repere-rayon" type="number" step="any" inputmode="decimal" class="h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground"></label>
      <p id="rp9-repere-erreur" class="text-xs text-alert-300" role="alert" hidden></p>
      <button type="button" id="rp9-repere-poser" class="h-11 border border-border px-3 text-sm text-foreground hover:border-brass-400">Poser sur le plan</button>
      <ul id="rp9-repere-list" class="space-y-1 text-xs text-foreground"></ul>`;
    ancre.insertAdjacentElement('afterend', bloc);
  }
  const q = <T extends HTMLElement>(id: string) => (bloc?.querySelector<T>(`#${id}`) ?? null);
  const erreurEl = q<HTMLElement>('rp9-repere-erreur');
  const installer = () => {
    if (!map.addSource || map.getSource?.('rp9-reperes')) return;
    map.addSource('rp9-reperes', { type: 'geojson', data: reperesGeoJSON(liste()) });
    map.addLayer?.({ id: 'rp9-reperes-cercle', type: 'line', source: 'rp9-reperes', filter: ['==', '$type', 'Polygon'], paint: { 'line-color': GOLD, 'line-width': 2, 'line-dasharray': [2, 1] } });
    map.addLayer?.({ id: 'rp9-reperes-point', type: 'circle', source: 'rp9-reperes', filter: ['==', '$type', 'Point'], paint: { 'circle-radius': 6, 'circle-color': GOLD } });
  };
  if (map.isStyleLoaded?.()) installer(); else map.once?.('load', installer);

  function render() {
    map.getSource?.('rp9-reperes')?.setData(reperesGeoJSON(liste()));
    const ul = q<HTMLUListElement>('rp9-repere-list');
    if (ul) {
      ul.innerHTML = liste().map((r) => `<li class="flex items-center gap-2">${esc(TYPES_REPERE[r.type])}${r.texte ? ` — ${esc(r.texte)}` : ''}${
        r.rayonM != null ? ` · ${String(r.rayonM).replace('.', ',')} m` : ''}<button type="button" data-repere-retirer="${esc(r.id)}" class="h-11 px-2 text-xs underline">Retirer</button></li>`).join('');
    }
    q<HTMLButtonElement>('rp9-repere-poser')?.setAttribute('aria-pressed', String(arme));
  }
  q<HTMLButtonElement>('rp9-repere-poser')?.addEventListener('click', () => {
    const v = validerRayon(q<HTMLInputElement>('rp9-repere-rayon')?.value ?? '');
    if (erreurEl) { erreurEl.hidden = v.ok; erreurEl.textContent = v.ok ? '' : v.motif; }
    arme = v.ok;
    if (v.ok) deps.setStatus?.('Touchez le plan pour poser le repère.');
    render();
  });
  q<HTMLUListElement>('rp9-repere-list')?.addEventListener('click', (ev) => {
    const id = (ev.target as HTMLElement | null)?.closest?.('[data-repere-retirer]')?.getAttribute('data-repere-retirer');
    if (!id) return;
    ctx.reperesChantier = liste().filter((r) => r.id !== id);
    render();
  });
  function handleMapClick(p: LngLat): boolean {
    if (!arme) return false;
    const v = validerRayon(q<HTMLInputElement>('rp9-repere-rayon')?.value ?? '');
    arme = false;
    if (v.ok && estPoint(p)) {
      const type = (q<HTMLSelectElement>('rp9-repere-type')?.value ?? 'autre') as TypeRepere;
      const texte = (q<HTMLInputElement>('rp9-repere-texte')?.value ?? '').trim().slice(0, 200);
      liste().push({ id: `rep-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`, type: type in TYPES_REPERE ? type : 'autre',
        ...(texte ? { texte } : {}), rayonM: v.rayonM, point: [p[0], p[1]] });
      deps.setStatus?.('Repère posé — enregistrez pour le garder.');
    }
    render();
    return true;
  }
  return { handleMapClick, render, list: () => copie(liste()) };
}
