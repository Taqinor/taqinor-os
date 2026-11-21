// ACAL579 — PIEDS DU CHÂSSIS DE TOIT PLAT À LA PORTÉE SAISIE (contrat ACAL587, `zones[].porteeEntrePieds`).
// LA RÈGLE (contrat, même que la nomenclature ACAL578) : pour un tronçon de m modules contigus de
// pas p, k = max(1, ⌊valeurM ÷ p⌋) modules entre deux pieds et pieds = ⌈m ÷ k⌉ + 1. Sans portée
// saisie : un triangle à CHAQUE jointure (m + 1), la scène d'aujourd'hui. Le visionneur CLIENT
// (`readOnly`) garde toujours m + 1 (D-ACAL-38 : ce n'est pas un ajout visible autorisé).

export interface PorteeEntrePieds { valeurM: number; source: string }

export function lirePortee(brut: unknown): PorteeEntrePieds | null {
  const p = brut as Partial<PorteeEntrePieds> | null | undefined;
  if (!p || typeof p !== 'object' || typeof p.valeurM !== 'number' || !(p.valeurM > 0)) return null;
  return typeof p.source === 'string' && p.source.trim() ? { valeurM: p.valeurM, source: p.source } : null;
}

/** Fragment de pan : `{ porteeEntrePieds }` s'il y en a une, `{}` sinon. */
export function emettrePortee(brut: unknown): { porteeEntrePieds?: PorteeEntrePieds } {
  const p = lirePortee(brut);
  return p ? { porteeEntrePieds: { ...p } } : {};
}

/** Saisie : deux champs vides ⇒ aucune portée ; valeur ≤ 0 ou source vide ⇒ refus qui nomme le champ. */
export function validerPortee(valeur: string, source: string): { ok: true; portee: PorteeEntrePieds | null } | { ok: false; motif: string } {
  const [v, s] = [valeur, source].map((x) => String(x ?? '').trim());
  if (!v && !s) return { ok: true, portee: null };
  const n = Number(v.replace(',', '.'));
  if (!v || !Number.isFinite(n) || n <= 0) return { ok: false, motif: 'Portée entre pieds (m) : un nombre supérieur à 0.' };
  if (!s) return { ok: false, motif: 'Source de la portée : dites d’où elle vient (notice du système…).' };
  return { ok: true, portee: { valeurM: n, source: s } };
}

/** Indices des jointures portantes d'un tronçon de m modules (0 = bord amont, m = bord aval). */
export function jointuresPortantes(m: number, pasM: number, porteeM: number | null): number[] {
  const toutes = Array.from({ length: m + 1 }, (_, i) => i);
  if (porteeM == null || !(porteeM > 0) || !(pasM > 0)) return toutes;
  const k = Math.max(1, Math.floor(porteeM / pasM + 1e-9));
  return toutes.filter((i) => i % k === 0 || i === m);
}

/** Le champ « Portée entre pieds (m) » + sa source, sous « Personnaliser la disposition » (rubrique « Avancé »). */
export function monterChampPortee(ctx: { activeArea?: () => { porteeEntrePieds?: PorteeEntrePieds } | undefined }, deps: { recalc: () => void }): void {
  const hote = typeof document !== 'undefined' ? document.getElementById('rp9-layout-panel') : null;
  if (!hote || document.getElementById('rp9-portee')) return;
  const bloc = document.createElement('details');
  bloc.id = 'rp9-portee';
  bloc.className = 'mt-2 text-xs';
  bloc.innerHTML = '<summary class="min-h-11 cursor-pointer">Avancé — pieds du châssis</summary>'
    + '<label class="flex min-h-11 items-center gap-2" for="rp9-portee-valeur">Portée entre pieds (m)<input type="text" id="rp9-portee-valeur" class="rp9-input w-24" inputmode="decimal" /></label>'
    + '<label class="flex min-h-11 items-center gap-2" for="rp9-portee-source">Source<input type="text" id="rp9-portee-source" class="rp9-input" /></label>'
    + '<p id="rp9-portee-erreur" class="text-alert-300" role="alert" hidden></p>';
  hote.appendChild(bloc);
  const champ = (id: string) => document.getElementById(id) as HTMLInputElement | null;
  const erreur = document.getElementById('rp9-portee-erreur');
  bloc.addEventListener('toggle', () => {
    const p = lirePortee(ctx.activeArea?.()?.porteeEntrePieds);
    const [v, s] = [champ('rp9-portee-valeur'), champ('rp9-portee-source')];
    if (v) v.value = p ? String(p.valeurM).replace('.', ',') : '';
    if (s) s.value = p?.source ?? '';
  });
  bloc.addEventListener('change', () => {
    const r = validerPortee(champ('rp9-portee-valeur')?.value ?? '', champ('rp9-portee-source')?.value ?? '');
    if (erreur) { erreur.hidden = r.ok; erreur.textContent = r.ok ? '' : r.motif; }
    const pan = ctx.activeArea?.();
    if (!r.ok || !pan) return;
    if (r.portee) pan.porteeEntrePieds = r.portee; else delete pan.porteeEntrePieds;
    deps.recalc();
  });
}

/** La portée que la scène applique : jamais dans le visionneur client. */
export const porteeAppliquee = (readOnly: boolean, brut: unknown): number | null => (readOnly ? null : lirePortee(brut)?.valeurM ?? null);

/** ACAL579 — boucle des tronçons d'une rangée (sortie de `scene3d.ts`) : pose un triangle à
 *  chaque jointure portante (bord amont, jointures internes retenues, bord aval). */
export function poserTrianglesDeRangee<T extends { la: number; halfA: number }>(row: T[], ecartContigM: number, porteeM: number | null, poser: (xa: number, p: T) => void): void {
  row.sort((a, b) => a.la - b.la);
  let i = 0;
  while (i < row.length) {
    // Fin du TRONÇON contigu : deux voisins se touchent tant que l'écart de leurs centres ne
    // dépasse pas la somme de leurs demi-largeurs + le jeu toléré.
    let j = i;
    while (j + 1 < row.length && row[j + 1].la - row[j].la <= row[j].halfA + row[j + 1].halfA + ecartContigM) j++;
    const pas = j > i ? (row[j].la - row[i].la) / (j - i) : 2 * row[i].halfA;
    for (const n of jointuresPortantes(j - i + 1, pas, porteeM)) {
      if (n === 0) poser(row[i].la - row[i].halfA, row[i]);
      else if (n === j - i + 1) poser(row[j].la + row[j].halfA, row[j]);
      else poser((row[i + n - 1].la + row[i + n - 1].halfA + row[i + n].la - row[i + n].halfA) / 2, row[i + n - 1]);
    }
    i = j + 1;
  }
}
