/**
 * ADEV107 — LA CARTE « CUMUL 25 ANS » (niveau ≤ 2) SUIT L'OPTION COCHÉE.
 *
 * Aucun chiffre n'est calculé ici : chaque option est LUE par `savingsHeadline`
 * (cumul servi `economies_cumul_25_ans[opt]`, mensualité = économie annuelle
 * servie ÷ 12) puis FORMATÉE par `formatMAD`, la fonction du rendu serveur.
 *
 * Deux défauts du rejeu du 04/11/2026 (enregistrement ADEV e8306483b) vivent ici :
 *  - la mensualité « ≈ N MAD/mois » perdait sa mise en valeur `.text-brass-300`
 *    parce que la bascule réécrivait le `textContent` du span FR : la sous-ligne
 *    FR est désormais REBÂTIE avec la même structure que le rendu serveur ;
 *  - la bascule d'option, après une bascule de TAILLE (Éco/Max), réécrivait la
 *    carte avec le cumul de la taille RECOMMANDÉE : la page n'appelle
 *    `peindreCumulOption` que sur la taille du devis ; une autre taille chargée
 *    suit l'option par son propre détail servi (section des tailles, `liaisons.ts`).
 */
import { formatMAD, savingsHeadline, type OptionKey, type ProposalResponse } from '../proposition';

/** Une option, déjà formatée : le cumul, la mensualité, et la sous-ligne FR/EN/AR. */
export interface CumulOption {
  valeur: string;
  annees: number;
  /** « ≈ N MAD » sans le « /mois », ou `null` quand l'économie annuelle n'est pas servie. */
  mensuel: string | null;
  fr: string;
  en: string;
  ar: string;
}

/** La sous-ligne de la carte, en trois langues (une seule rédaction : rendu serveur ET bascule). */
export function sousLigneCumul(h: { years: number; monthly: number | null }): { fr: string; en: string; ar: string } {
  return {
    fr: `Économies cumulées estimées sur ${h.years} ans${h.monthly ? ` — soit ≈ ${formatMAD(h.monthly)}/mois qui restent dans votre poche` : ''} (loi 82-21, autoconsommation).`,
    en: `Estimated cumulative savings over ${h.years} years${h.monthly ? ` — that's ≈ ${formatMAD(h.monthly)}/month staying in your pocket` : ''} (law 82-21, self-consumption).`,
    ar: `توفير تراكمي مقدّر على مدى ${h.years} سنة${h.monthly ? ` — أي ما يعادل ≈ ${formatMAD(h.monthly)}/شهر تبقى في جيبكم` : ''} (القانون 82-21، الاستهلاك الذاتي).`,
  };
}

/** Chaque option servie, lue par `savingsHeadline` ; `{}` hors niveau ≤ 2 ou devis à une option. */
export function cumulParOption(data: ProposalResponse | null, actif: boolean): Partial<Record<OptionKey, CumulOption>> {
  if (!data || !actif) return {};
  const table: Partial<Record<OptionKey, CumulOption>> = {};
  for (const o of ['sans_batterie', 'avec_batterie'] as const) {
    const h = savingsHeadline(data, o);
    if (h.cumulative === null) continue;
    table[o] = { valeur: formatMAD(h.cumulative), annees: h.years, mensuel: h.monthly ? `≈ ${formatMAD(h.monthly)}` : null, ...sousLigneCumul(h) };
  }
  return table;
}

/**
 * Peint la carte pour l'option `opt` : valeur, `data-figure-option`, sous-ligne.
 * `sous` porte le triplet FR/EN/AR de `prepareI18n` (FR = balisage du serveur,
 * EN/AR = texte) ; le span FR est rebâti à l'identique du rendu serveur, la
 * mensualité dans son `<span class="text-brass-300">`.
 */
export function peindreCumulOption(valeur: HTMLElement, sous: HTMLElement | null, c: CumulOption, opt: OptionKey): void {
  valeur.textContent = c.valeur;
  valeur.dataset.figureOption = opt === 'avec_batterie' ? 'avec' : 'sans';
  if (!sous || sous.children.length !== 3) return;
  const doc = sous.ownerDocument;
  const fr: Node[] = [doc.createTextNode(`Économies cumulées estimées sur ${c.annees} ans`)];
  if (c.mensuel) {
    const mis = doc.createElement('span');
    mis.className = 'text-brass-300';
    mis.textContent = `${c.mensuel}/mois`;
    fr.push(doc.createTextNode(' — soit '), mis, doc.createTextNode(' qui restent dans votre poche'));
  }
  const loi = doc.createElement('span');
  loi.className = 'text-lune-faint';
  loi.textContent = ' (loi 82-21, autoconsommation).';
  fr.push(loi);
  sous.children[0].replaceChildren(...fr);
  sous.children[1].textContent = c.en;
  sous.children[2].textContent = c.ar;
}
