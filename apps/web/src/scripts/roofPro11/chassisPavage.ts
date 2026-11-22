// ACAL585 — PAVAGE EN CHÂSSIS N × M DE L'ATELIER (contrat ACAL581, `zones[].chassis`).
// Lecture/écriture du document, option passée à `packConfig` (ACAL583), note « n châssis de
// N × M posés », et les champs de saisie sous « Personnaliser la disposition » (rubrique « Avancé »).
// Sans saisie : aucune clé au document, aucune option, le pavage d'aujourd'hui.
import { chassisApplicable, type OptionChassis } from '../../lib/estimatorBrainV2Blocs';

/** Le châssis SAISI d'un pan (forme du contrat). `jeuEntreRangsM` : obligatoire dès 2 rangs. */
export interface ChassisPan {
  rangs: number;
  modulesParRang: number;
  jeuEntreRangsM?: number | null;
  source: string;
}

const entierPositif = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v) && v >= 1;

/** Le châssis d'un document relu, ou `null` (forme non conforme : jamais « corrigée » en douce). */
export function lireChassis(brut: unknown): ChassisPan | null {
  const c = brut as Partial<ChassisPan> | null | undefined;
  if (!c || typeof c !== 'object' || !entierPositif(c.rangs) || !entierPositif(c.modulesParRang)) return null;
  if (typeof c.source !== 'string' || !c.source.trim()) return null;
  const jeu = c.jeuEntreRangsM;
  if (c.rangs > 1 && !(typeof jeu === 'number' && Number.isFinite(jeu) && jeu >= 0)) return null;
  return {
    rangs: c.rangs,
    modulesParRang: c.modulesParRang,
    ...(typeof jeu === 'number' && Number.isFinite(jeu) && jeu >= 0 ? { jeuEntreRangsM: jeu } : {}),
    source: c.source,
  };
}

/** Fragment de pan : `{ chassis }` s'il y en a un, `{}` sinon (aucune clé quand rien n'est saisi). */
export function emettreChassis(brut: unknown): { chassis?: ChassisPan } {
  const c = lireChassis(brut);
  return c ? { chassis: { ...c } } : {};
}

/** L'option de `packConfig` pour ce pan : `undefined` sans saisie ou à 1 × 1 (pavage d'aujourd'hui). */
export function optionChassis(brut: unknown): OptionChassis | undefined {
  const c = lireChassis(brut);
  if (!c) return undefined;
  const option = chassisApplicable({ rangs: c.rangs, modulesParRang: c.modulesParRang, jeuEntreRangsM: c.jeuEntreRangsM ?? 0 });
  return option ?? undefined;
}

/** Saisie : quatre champs vides ⇒ aucun châssis ; sinon chaque champ fautif est NOMMÉ. */
export function validerChassis(
  rangs: string, modules: string, jeu: string, source: string,
): { ok: true; chassis: ChassisPan | null } | { ok: false; champ: 'rangs' | 'modules' | 'jeu' | 'source'; motif: string } {
  const [r, m, j, s] = [rangs, modules, jeu, source].map((x) => String(x ?? '').trim());
  if (!r && !m && !j && !s) return { ok: true, chassis: null };
  const nr = Number(r.replace(',', '.'));
  const nm = Number(m.replace(',', '.'));
  if (!entierPositif(nr)) return { ok: false, champ: 'rangs', motif: 'Rangs par châssis : un nombre entier supérieur à 0.' };
  if (!entierPositif(nm)) return { ok: false, champ: 'modules', motif: 'Modules par rang : un nombre entier supérieur à 0.' };
  const nj = j ? Number(j.replace(',', '.')) : null;
  if (nj !== null && !(Number.isFinite(nj) && nj >= 0)) return { ok: false, champ: 'jeu', motif: 'Jeu entre rangs (m) : un nombre supérieur ou égal à 0.' };
  if (nr > 1 && nj === null) return { ok: false, champ: 'jeu', motif: 'Jeu entre rangs (m) : à saisir dès 2 rangs.' };
  if (!s) return { ok: false, champ: 'source', motif: 'Source du châssis : dites d’où viennent ces valeurs (notice du châssis…).' };
  return { ok: true, chassis: { rangs: nr, modulesParRang: nm, ...(nj !== null ? { jeuEntreRangsM: nj } : {}), source: s } };
}

/** La phrase sous les champs : le nombre de châssis posés, ou le motif de l'option ignorée. */
export function noteChassis(
  pack: { chassisMotif?: string } | null | undefined,
  grid: { chassis?: { nombre: number; rangs: number; modulesParRang: number } } | null | undefined,
): string {
  if (pack?.chassisMotif) return pack.chassisMotif;
  const c = grid?.chassis;
  return c ? `${c.nombre} châssis de ${c.rangs} × ${c.modulesParRang} posés` : '';
}

/** Écrit la note dans le champ monté par `monterChampsChassis` (rien si les champs n'existent pas). */
export function majNoteChassis(
  pack: Parameters<typeof noteChassis>[0],
  grid: Parameters<typeof noteChassis>[1],
): void {
  const el = typeof document !== 'undefined' ? document.getElementById('rp9-chassis-note') : null;
  if (el) el.textContent = noteChassis(pack, grid);
}

/** Les champs « Châssis N × M », sous « Personnaliser la disposition » (rubrique « Avancé »). */
export function monterChampsChassis(
  ctx: { activeArea?: () => { chassis?: ChassisPan } | undefined },
  deps: { recalc: () => void },
): void {
  const hote = typeof document !== 'undefined' ? document.getElementById('rp9-layout-panel') : null;
  if (!hote || document.getElementById('rp9-chassis')) return;
  const bloc = document.createElement('details');
  bloc.id = 'rp9-chassis';
  bloc.className = 'mt-2 text-xs';
  const ligne = (id: string, libelle: string, large = 'w-24') =>
    `<label class="flex min-h-11 items-center gap-2" for="${id}">${libelle}<input type="text" id="${id}" class="rp9-input ${large}" inputmode="decimal" /></label>`
    + `<p id="${id}-erreur" class="text-alert-300" role="alert" hidden></p>`;
  bloc.innerHTML = '<summary class="min-h-11 cursor-pointer">Avancé — châssis N × M</summary>'
    + ligne('rp9-chassis-rangs', 'Rangs par châssis') + ligne('rp9-chassis-modules', 'Modules par rang')
    + ligne('rp9-chassis-jeu', 'Jeu entre rangs (m)') + ligne('rp9-chassis-source', 'Source', '')
    + '<p id="rp9-chassis-note" aria-live="polite"></p>';
  hote.appendChild(bloc);
  const champ = (id: string) => document.getElementById(id) as HTMLInputElement | null;
  const ids = { rangs: 'rp9-chassis-rangs', modules: 'rp9-chassis-modules', jeu: 'rp9-chassis-jeu', source: 'rp9-chassis-source' } as const;
  const dire = (cle: keyof typeof ids | null, motif: string) => {
    for (const k of Object.keys(ids) as Array<keyof typeof ids>) {
      const e = document.getElementById(`${ids[k]}-erreur`);
      if (!e) continue;
      e.hidden = k !== cle;
      e.textContent = k === cle ? motif : '';
    }
  };
  bloc.addEventListener('toggle', () => {
    const c = lireChassis(ctx.activeArea?.()?.chassis);
    const val = (id: keyof typeof ids, v: unknown) => { const el = champ(ids[id]); if (el) el.value = v == null ? '' : String(v).replace('.', ','); };
    val('rangs', c?.rangs); val('modules', c?.modulesParRang); val('jeu', c?.jeuEntreRangsM); val('source', c?.source);
  });
  bloc.addEventListener('change', () => {
    const r = validerChassis(champ(ids.rangs)?.value ?? '', champ(ids.modules)?.value ?? '', champ(ids.jeu)?.value ?? '', champ(ids.source)?.value ?? '');
    dire(r.ok ? null : r.champ, r.ok ? '' : r.motif);
    const pan = ctx.activeArea?.();
    if (!r.ok || !pan) return;
    if (r.chassis) pan.chassis = r.chassis; else delete pan.chassis;
    deps.recalc();
  });
}
