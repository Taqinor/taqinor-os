// T4-V2-021 — UN chiffre par valeur entre la carte de la pose, le total et les cartes de variante.
// Sorti d'`optimizer.ts` (2 000 lignes et plus : il ne grossit pas). Le balayage des variantes (`fineGridMatrixV6`)
// pave avec le module de RÉFÉRENCE de l'atelier (720 Wc, 2,384 × 1,303 m) ; la pose et le total, avec le module CHOISI
// du pan (« 10 × 710 W · 7,1 kWc »). La carte de la variante POSÉE lit donc les chiffres de la pose (mêmes panneaux,
// même module, même production) ; une autre carte reste une estimation du balayage, dite telle quelle.
import { kwcDuPan, MODULE_PAR_DEFAUT_ATELIER, type ModuleDocument } from './moduleSelect';

/** Ce que la carte de la pose affiche : nombre posé, kWc du module posé, watt, production (`null` = rien à dire). */
export interface ChiffresPose { count: number; kwc: number | null; watt: number | null; annualKwh: number | null; estimee?: boolean }

/**
 * ACAL1914 — la part des modules d'un pan que les chaînes RACCORDENT, lue sur la table d'affectation SERVIE (la même que la teinte
 * et l'info-bulle) : modules du pan portant une chaîne ÷ modules du pan que la table nomme. `null` (estimation inchangée) sans table,
 * sans module nommé pour ce pan, ou tant qu'AUCUNE chaîne n'est formée ; 1 quand tous sont raccordés. Les modules sont `<pan>#<n>`.
 */
export function partRaccordeeDuPan(
  coloration: { colorByModule: ReadonlyMap<string, unknown>; labelByModule: ReadonlyMap<string, string> } | null | undefined,
  clePan: string | null | undefined,
): number | null {
  if (!coloration || !clePan) return null;
  let nommes = 0;
  let raccordes = 0;
  for (const id of coloration.colorByModule.keys()) {
    if (!id.startsWith(`${clePan}#`)) continue;
    nommes += 1;
    if (coloration.labelByModule.has(id)) raccordes += 1;
  }
  return nommes > 0 && raccordes > 0 ? raccordes / nommes : null;
}

/** Les chiffres de la pose : kWc au module CHOISI du pan (le défaut sans choix), production SERVIE quand elle l'est
 *  (`prodServie`), sinon l'estimation du navigateur. Une seule définition, lue par la carte et par la variante posée. */
export function chiffresDeLaPose(
  d: { count: number; kwc: number; annualKwh: number },
  choisi: ModuleDocument | null,
  prodServie: (kwc: number | null) => number | null,
  partRaccordee: number | null = null, // ACAL1914 — l'estimation ne compte que la part RACCORDÉE du pan (`partRaccordeeDuPan`), jamais la servie
): ChiffresPose {
  const kwc = choisi ? kwcDuPan(d.count, choisi) : d.kwc;
  const servie = prodServie(kwc);
  return {
    count: d.count,
    kwc,
    watt: (choisi ?? MODULE_PAR_DEFAUT_ATELIER).pmaxWc,
    annualKwh: servie != null ? servie : d.annualKwh > 0 ? d.annualKwh * (partRaccordee ?? 1) : null,
    estimee: servie == null && d.annualKwh > 0, // T4-X2-006 — la production est l'estimation du navigateur
  };
}

/** Vrai quand le module choisi du pan n'est pas celui avec lequel le balayage a pavé (watt ou cotes). */
function autreQueLaReference(choisi: ModuleDocument | null): boolean {
  const ref = MODULE_PAR_DEFAUT_ATELIER;
  return !!choisi && (choisi.pmaxWc !== ref.pmaxWc || choisi.longueurMm !== ref.longueurMm || choisi.largeurMm !== ref.largeurMm);
}

type Fmt = (n: number) => string;

/** La ligne de chiffres d'une carte de variante : celle de la pose quand la variante est POSÉE ; sinon l'estimation du
 *  balayage, dite « Estimation », avec le module de référence quand le pan en porte un autre. */
export function texteChiffresVariante(
  c: { count: number; kwc: number; annualKwh: number },
  posee: ChiffresPose | null,
  choisi: ModuleDocument | null,
  fmt: Fmt,
  fmtKwc: Fmt,
  erp: boolean | 'pompage' = false, // ACAL1268 — 'pompage' : atelier ERP d'un lead de pompage, jamais de kWh de réseau
): string {
  const pompage = erp === 'pompage';
  if (posee) {
    // T4-X2-006 (rejeu R5B, 26/11) — atelier ERP : la variante posée EST la pose ; son estimation de navigateur faisait un
    // second chiffre à côté du Total (« 21 735 » contre « 27 305 · simulation », mêmes 24 panneaux). Règle D-ACAL-86 / 97
    // (un seul chiffre par valeur ; pendant le dessin, panneaux et kWc seulement) : la carte ne dit plus de production
    // estimée pour la pose, elle renvoie au Total ; les AUTRES cartes restent « Estimation » (autres poses, pour comparer).
    const kwc = posee.kwc == null ? '—' : `${fmtKwc(posee.kwc)} kWc`;
    if (pompage) return `${fmt(posee.count)} panneaux · ${kwc}`;
    if (erp && posee.estimee) return `${fmt(posee.count)} panneaux · ${kwc} · production : voir le Total`;
    return `${fmt(posee.count)} panneaux · ${kwc} · ${posee.annualKwh == null ? '—' : `${fmt(Math.round(posee.annualKwh))} kWh/an`}`;
  }
  const chiffres = `${fmt(c.count)} panneaux · ${fmtKwc(c.kwc)} kWc${pompage ? '' : ` · ${fmt(Math.round(c.annualKwh))} kWh/an`}`;
  return autreQueLaReference(choisi)
    ? `Estimation (module de référence ${fmt(MODULE_PAR_DEFAUT_ATELIER.pmaxWc as number)} Wc) : ${chiffres}`
    : `Estimation : ${chiffres}`;
}
