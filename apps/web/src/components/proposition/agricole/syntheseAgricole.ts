/**
 * CPRW (27/10/2026) — déplacement PUR depuis src/lib/proposition.ts (aucune ligne de logique
 * changée) : la lecture de `synthese_agricole` pour /proposition. Propriétaire : session AGC.
 * `lib/proposition.ts` ré-exporte tout (`export *`) : les importeurs existants ne bougent pas.
 */
import {
  estRecord,
  nombreServi,
  resolveInstallMode,
  texteServi,
  type Lbl3,
  type PropLang,
  type ProposalResponse,
} from '../../../lib/proposition';
import type { SyntheseEtape, SyntheseNote } from '../../../lib/propositionAgricole';

// ════════════════════════════════════════════════════════════════════════════
// AGW303 — Jumeau web du document agricole (1/2) : `synthese_agricole`.
//
// LA PAGE NE CALCULE RIEN. Le serveur sert `synthese_agricole` (fonction pure du
// moteur, la MÊME que le PDF — contrat partagé `proposal_data.json` ›
// `exemple_agricole`, AGR304/AGR308) ; ces extracteurs la LISENT, défensivement :
// une clé absente → `null`, une série partielle → `null`, jamais un 0 fabriqué.
// Remplace `agricoleMonthlyDelivery` (livraison d'eau dérivée dans le navigateur
// de `m3_jour × 365` répartis sur la production — retirée).
// ════════════════════════════════════════════════════════════════════════════

/** Une entrée de provenance servie (forme unique {origine, detail, date}, AGR2). */
export interface SyntheseProvenance {
  cle: string;
  origine: string | null;
  detail: string | null;
  date: string | null;
  /** Rejeu AGQ41 — la valeur servie à côté de sa provenance (AGQ28), sinon `null`. */
  valeur?: number | null;
}

export interface SyntheseBesoinLivreMois {
  /** m³/jour de BESOIN du mois (servi par le moteur). */
  besoin: number;
  /** m³/jour LIVRÉ ce mois-là (servi par le moteur). */
  livre: number;
}

export interface SyntheseAgricole {
  version: number | null;
  /** `neuve` | `existante` | `null` (non renseigné — jamais deviné). */
  modePompe: 'neuve' | 'existante' | null;
  eau: {
    m3Jour: number | null;
    heuresPompage: number | null;
    hmtM: number | null;
    debitHmtM3h: number | null;
    /** `true` = le m³/jour est une estimation (jamais présenté comme mesuré). */
    estimation: boolean;
  } | null;
  provenance: SyntheseProvenance[];
  /** Entrées du point d'eau NON mesurées (D-AGR-4) — clés machine. */
  aConfirmerParVisite: string[];
  pompe: {
    cv: number | null;
    kw: number | null;
    plaque: { kw: number | null; tensionV: number | null; phases: string | null; cv: number | null; courantA: number | null } | null;
  } | null;
  champ: { kwc: number | null; nbPanneaux: number | null } | null;
  /** 12 mois COMPLETS ou `null` : jamais une série partielle complétée de zéros. */
  besoinVsLivre: {
    mois: SyntheseBesoinLivreMois[];
    /** 1-12, ou `null`. */
    moisLePlusSerre: number | null;
    hectaresIrrigables: number | null;
    baseBesoin: string | null;
    /** AGQ3/AGQ33 — chaque mois d'irrigation sous la tolérance de conception, avec sa couverture (% servi). */
    moisSousTolerance: Array<{ mois: number; couverturePct: number | null }>;
  } | null;
  pointFonctionnement: {
    courbe: Array<[number, number]>;
    point: { debitM3h: number; hmtM: number };
  } | null;
  /** SVG tel que servi (déjà échappé côté serveur) — inséré tel quel, jamais réécrit. */
  dessinSchema: string | null;
  /** AGQ30/AGQ33 — les étapes servies (`etapes_suivantes`), sans délai ; [] sinon. */
  etapesSuivantes: SyntheseEtape[];
  /** AGQ38/AGQ35 — notes client issues des alertes du noyau (`notes`), textes servis ; [] sinon. */
  notes: SyntheseNote[];
  omissions: Array<{ bloc: string; motif: string }>;
}

function lireProvenance(v: unknown): SyntheseProvenance[] {
  if (!estRecord(v)) return [];
  const out: SyntheseProvenance[] = [];
  for (const [cle, e] of Object.entries(v)) {
    if (!estRecord(e) || !texteServi(e.origine)) continue;
    out.push({ cle, origine: texteServi(e.origine), detail: texteServi(e.detail), date: texteServi(e.date), valeur: nombreServi(e.valeur) });
  }
  return out;
}

function lireBesoinVsLivre(v: unknown): SyntheseAgricole['besoinVsLivre'] {
  if (!estRecord(v) || !Array.isArray(v.mois) || v.mois.length !== 12) return null;
  const mois: SyntheseBesoinLivreMois[] = [];
  for (const m of v.mois) {
    if (!estRecord(m)) return null;
    const besoin = nombreServi(m.besoin_m3_jour);
    const livre = nombreServi(m.livre_m3_jour);
    if (besoin === null || livre === null) return null; // série partielle → null
    mois.push({ besoin, livre });
  }
  const serre = nombreServi(v.mois_le_plus_serre);
  return {
    mois,
    moisLePlusSerre: serre !== null && Number.isInteger(serre) && serre >= 1 && serre <= 12 ? serre : null,
    hectaresIrrigables: nombreServi(v.hectares_irrigables),
    baseBesoin: texteServi(v.base_besoin),
    moisSousTolerance: lireMoisSousTolerance(v.mois_sous_tolerance),
  };
}

function lirePointFonctionnement(v: unknown): SyntheseAgricole['pointFonctionnement'] {
  if (!estRecord(v) || !Array.isArray(v.courbe) || v.courbe.length < 2 || !estRecord(v.point)) return null;
  const courbe: Array<[number, number]> = [];
  for (const pt of v.courbe) {
    if (!Array.isArray(pt) || pt.length !== 2) return null;
    const q = nombreServi(pt[0]);
    const h = nombreServi(pt[1]);
    if (q === null || h === null) return null;
    courbe.push([q, h]);
  }
  const debit = nombreServi(v.point.debit_m3h);
  const hmt = nombreServi(v.point.hmt_m);
  if (debit === null || hmt === null) return null;
  return { courbe, point: { debitM3h: debit, hmtM: hmt } };
}

function lirePompe(v: unknown): SyntheseAgricole['pompe'] {
  if (!estRecord(v)) return null;
  const pl = estRecord(v.plaque) ? v.plaque : null;
  return {
    cv: nombreServi(v.cv),
    kw: nombreServi(v.kw),
    plaque: pl
      ? {
          kw: nombreServi(pl.kw),
          tensionV: nombreServi(pl.tension_v),
          phases: texteServi(pl.phases),
          cv: nombreServi(pl.cv),
          courantA: nombreServi(pl.courant_a),
        }
      : null,
  };
}

/**
 * AGW303 — extracteur PUR de `synthese_agricole` (partie eau / besoin / schéma /
 * point de fonctionnement / provenance / plaque). `null` hors mode agricole, quand
 * la clé est absente ou vide (un payload sans synthèse garde ses cartes pompe et
 * n'affiche ni graphe ni schéma). Aucune valeur n'est calculée, convertie ou
 * complétée ici.
 */
export function syntheseAgricole(
  p: Pick<ProposalResponse, 'mode_installation' | 'quote'> | null | undefined,
): SyntheseAgricole | null {
  if (!p || resolveInstallMode(p) !== 'agricole') return null;
  const brut = (p as { synthese_agricole?: unknown }).synthese_agricole;
  if (!estRecord(brut) || Object.keys(brut).length === 0) return null;

  const eauBrute = estRecord(brut.eau) ? brut.eau : null;
  const champBrut = estRecord(brut.champ) ? brut.champ : null;
  const mode = brut.mode_pompe === 'neuve' || brut.mode_pompe === 'existante' ? brut.mode_pompe : null;
  const omissions: Array<{ bloc: string; motif: string }> = [];
  if (Array.isArray(brut.omissions)) {
    for (const o of brut.omissions) {
      if (estRecord(o) && texteServi(o.bloc) && texteServi(o.motif)) {
        omissions.push({ bloc: o.bloc as string, motif: o.motif as string });
      }
    }
  }
  const svg = texteServi(brut.schema_svg);
  return {
    version: nombreServi(brut.version),
    modePompe: mode,
    eau: eauBrute
      ? {
          m3Jour: nombreServi(eauBrute.m3_jour),
          heuresPompage: nombreServi(eauBrute.heures_pompage),
          hmtM: nombreServi(eauBrute.hmt_m),
          debitHmtM3h: nombreServi(eauBrute.debit_hmt_m3h),
          estimation: eauBrute.estimation !== false, // sauf « false » explicite : une estimation
        }
      : null,
    provenance: lireProvenance(brut.provenance),
    aConfirmerParVisite: Array.isArray(brut.a_confirmer_par_visite)
      ? brut.a_confirmer_par_visite.filter((x): x is string => typeof x === 'string')
      : [],
    pompe: lirePompe(brut.pompe),
    champ: champBrut ? { kwc: nombreServi(champBrut.kwc), nbPanneaux: nombreServi(champBrut.nb_panneaux) } : null,
    besoinVsLivre: lireBesoinVsLivre(brut.besoin_vs_livre),
    pointFonctionnement: lirePointFonctionnement(brut.point_fonctionnement),
    dessinSchema: svg !== null && svg.trimStart().startsWith('<svg') ? svg : null,
    etapesSuivantes: lireListeTextes(brut.etapes_suivantes, 'cle', (cle, textes) => ({ cle, textes })),
    notes: lireListeTextes(brut.notes, 'code', (code, textes) => ({ code, textes })),
    omissions,
  };
}

/** AGQ33/AGQ35 — une liste `[{<cle>, textes}]` servie en trois voix ; les éléments sans `fr` sont ignorés. */
function lireListeTextes<T>(v: unknown, cle: string, construire: (nom: string | null, textes: Lbl3) => T): T[] {
  if (!Array.isArray(v)) return [];
  const out: T[] = [];
  for (const e of v) {
    if (!estRecord(e)) continue;
    const textes = lireTextesTroisVoix(e.textes);
    if (!textes) continue;
    out.push(construire(texteServi(e[cle]), textes));
  }
  return out;
}

function lireMoisSousTolerance(v: unknown): Array<{ mois: number; couverturePct: number | null }> {
  if (!Array.isArray(v)) return [];
  const out: Array<{ mois: number; couverturePct: number | null }> = [];
  for (const m of v) {
    if (!estRecord(m)) continue;
    const mois = nombreServi(m.mois);
    if (mois === null || !Number.isInteger(mois) || mois < 1 || mois > 12) continue;
    out.push({ mois, couverturePct: nombreServi(m.couverture_pct) });
  }
  return out;
}

/** Le motif d'omission servi pour un bloc (`besoin_vs_livre`, `point_fonctionnement`…), ou `null`. */
export function omissionSynthese(s: SyntheseAgricole | null, bloc: string): string | null {
  return s?.omissions.find((o) => o.bloc === bloc)?.motif ?? null;
}

/** Date ISO (AAAA-MM-JJ…) → JJ/MM/AAAA ; illisible → `null` (jamais une date inventée). */
export function dateJjMmAaaa(iso: string | null | undefined): string | null {
  const t = String(iso ?? '').slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(t) ? `${t.slice(8, 10)}/${t.slice(5, 7)}/${t.slice(0, 4)}` : null;
}

export type ProvenanceKind = 'declare' | 'mesure' | 'mesure_foreur' | 'mesure_essai' | 'a_confirmer';

/**
 * Classe une provenance servie — MÊME règle que le renderer agricole
 * (`mentions.cle_provenance`) : `mesure_visite` → mesuré par TAQINOR ; `foreur` → relevé
 * par votre foreur ; `essai` → relevé à l'essai de pompage (rejeu AGQ du 24/10 : un relevé
 * du foreur n'est jamais « mesuré par TAQINOR ») ; origine `saisie` / `lead` → déclaré
 * par vous ; sinon à confirmer. Sans date lisible,
 * « déclaré » / « mesuré » retombent sur « à confirmer par la visite » (jamais une
 * date inventée).
 */
export function provenanceKind(e: SyntheseProvenance): { kind: ProvenanceKind; date: string | null } {
  const date = dateJjMmAaaa(e.date);
  const mesure = ({ mesure_visite: 'mesure', foreur: 'mesure_foreur', essai: 'mesure_essai' } as const)[
    e.detail as 'mesure_visite' | 'foreur' | 'essai'
  ];
  if (mesure) {
    return date ? { kind: mesure, date } : { kind: 'a_confirmer', date: null };
  }
  if (e.origine === 'saisie' || e.origine === 'lead') {
    return date ? { kind: 'declare', date } : { kind: 'a_confirmer', date: null };
  }
  return { kind: 'a_confirmer', date: null };
}


/**
 * AGW303 — libellés STRUCTURELS de la section pompage de /proposition. Les mots sont
 * ceux du catalogue du document PDF (`quote_engine/i18n_labels.py`, préfixe `agr_`) :
 * site et devis ne disent jamais deux choses. L'arabe est écrit maintenant et relu par
 * un natif ensuite (D-AGR-11, manuel). Les DONNÉES servies ne sont jamais traduites.
 */
export const AGR_LBL = {
  titreBesoinLivre: { fr: 'Besoin et eau livrée', en: 'Need and water delivered', ar: 'الحاجة والماء المضخوخ' },
  legendeBarres: {
    fr: "Gris : votre besoin par jour ; bleu : l'eau livrée par jour.",
    en: 'Grey: your daily need; blue: water delivered per day.',
    ar: 'الرمادي: حاجتكم اليومية؛ الأزرق: الماء المضخوخ يوميا.',
  },
  moisSerre: { fr: 'Mois le plus serré :', en: 'Tightest month:', ar: 'الشهر الأصعب:' },
  surfaceIrrigable: { fr: 'Surface irrigable', en: 'Irrigable area', ar: 'المساحة القابلة للسقي' },
  titreComment: { fr: 'Comment ça marche', en: 'How it works', ar: 'كيف تعمل' },
  pointFonctionnement: { fr: 'Point de fonctionnement', en: 'Operating point', ar: 'نقطة التشغيل' },
  pointOmis: { fr: 'Point de fonctionnement omis.', en: 'Operating point omitted.', ar: 'نقطة التشغيل غير معروضة.' },
  courbeAbsente: {
    fr: 'Courbe constructeur non disponible pour cette pompe.',
    en: 'Manufacturer curve not available for this pump.',
    ar: 'منحنى الصانع غير متوفر لهذه المضخة.',
  },
  axeDebit: { fr: 'Débit (m³/h)', en: 'Flow (m³/h)', ar: 'الصبيب (م³/س)' },
  axeHmt: { fr: 'HMT (m)', en: 'Head (m)', ar: 'الارتفاع (م)' },
  titreProvenance: { fr: "D'où viennent ces chiffres", en: 'Where these figures come from', ar: 'مصدر هذه الأرقام' },
  aConfirmerVisite: { fr: 'À confirmer par la visite :', en: 'To be confirmed by the site visit:', ar: 'يؤكد خلال الزيارة:' },
  declare: { fr: 'déclaré par vous le {date}', en: 'declared by you on {date}', ar: 'صرحتم به بتاريخ {date}' },
  mesure: { fr: 'mesuré par TAQINOR le {date}', en: 'measured by TAQINOR on {date}', ar: 'قاسته TAQINOR بتاريخ {date}' },
  mesureForeur: {
    fr: 'relevé par votre foreur (saisi le {date})',
    en: 'recorded by your driller (entered on {date})',
    ar: 'سجله حفار البئر (أُدخل بتاريخ {date})',
  },
  mesureEssai: {
    fr: "relevé à l'essai de pompage (saisi le {date})",
    en: 'recorded at the pumping test (entered on {date})',
    ar: 'سُجل خلال تجربة الضخ (أُدخل بتاريخ {date})',
  },
  aConfirmer: { fr: 'à confirmer par la visite', en: 'to be confirmed by the site visit', ar: 'يجب تأكيده خلال الزيارة' },
  agronomique: { fr: 'besoin agronomique plein (FAO-56)', en: 'full agronomic need (FAO-56)', ar: 'الحاجة الفلاحية الكاملة (FAO-56)' },
  pompeExistante: { fr: 'Votre pompe existante', en: 'Your existing pump', ar: 'مضختكم الحالية' },
  plaqueRelevee: {
    fr: 'Plaque relevée : {plaque}. Le variateur et les panneaux sont dimensionnés sur cette plaque.',
    en: 'Nameplate read: {plaque}. The drive and the panels are sized on this nameplate.',
    ar: 'اللوحة المسجلة: {plaque}. تم تحديد المغير والألواح على أساس هذه اللوحة.',
  },
  plaqueIllisible: { fr: 'non lisible', en: 'not legible', ar: 'غير مقروءة' },
  plaqueNonRelevee: {
    fr: 'Plaque de la pompe non relevée : compatibilité à vérifier à la visite.',
    en: 'Pump nameplate not read: compatibility to be checked at the site visit.',
    ar: 'لوحة المضخة غير مسجلة: يتم التحقق من التوافق خلال الزيارة.',
  },
} satisfies Record<string, Lbl3>;

/** Libellés des entrées de provenance (catalogue `agr_entree_*`). */
export const AGR_ENTREE_LBL: Record<string, Lbl3> = {
  volume_m3_jour: { fr: "Volume d'eau par jour", en: 'Daily water volume', ar: 'حجم الماء اليومي' },
  niveau_statique_m: { fr: 'Niveau statique', en: 'Static water level', ar: 'المستوى الساكن' },
  niveau_dynamique_m: { fr: 'Niveau dynamique', en: 'Dynamic water level', ar: 'المستوى الدينامي' },
  debit_exploitation_m3h: { fr: "Débit d'exploitation du forage", en: 'Borehole operating flow', ar: 'صبيب استغلال الثقب' },
  profondeur_forage_m: { fr: 'Profondeur du forage', en: 'Borehole depth', ar: 'عمق الثقب' },
  hmt_m: { fr: 'Hauteur manométrique totale', en: 'Total dynamic head', ar: 'الارتفاع المانومتري الكلي' },
  energie_actuelle: { fr: 'Énergie actuelle', en: 'Current energy', ar: 'الطاقة الحالية' },
  plaque: { fr: 'Plaque de la pompe', en: 'Pump nameplate', ar: 'لوحة المضخة' },
  localisation: { fr: 'Localisation', en: 'Location', ar: 'الموقع' },
  cultures: { fr: 'Cultures', en: 'Crops', ar: 'الزراعات' },
  surface_ha: { fr: 'Surface', en: 'Area', ar: 'المساحة' },
};

/** Mois en toutes lettres (légende du mois le plus serré). */
export const AGR_MOIS_LONG: Record<PropLang, string[]> = {
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  ar: ['يناير', 'فبراير', 'مارس', 'أبريل', 'ماي', 'يونيو', 'يوليوز', 'غشت', 'شتنبر', 'أكتوبر', 'نونبر', 'دجنبر'],
};

/** Remplit les `{cle}` d'un libellé, dans les trois voix. */
export function remplirLbl(l: Lbl3, valeurs: Record<string, string>): Lbl3 {
  const f = (t: string) => t.replace(/\{(\w+)\}/g, (m, k: string) => (k in valeurs ? valeurs[k] : m));
  return { fr: f(l.fr), en: f(l.en), ar: f(l.ar) };
}

/** Libellé d'une entrée de provenance ; clé hors catalogue → lisible, jamais traduite. */
export function libelleEntree(cle: string): Lbl3 {
  const l = AGR_ENTREE_LBL[cle];
  if (l) return l;
  const brut = cle.replace(/_/g, ' ');
  return { fr: brut, en: brut, ar: brut };
}

/** La phrase de provenance d'une entrée servie, à trois voix (date déjà formatée). */
export function phraseProvenance(e: SyntheseProvenance): Lbl3 {
  const { kind, date } = provenanceKind(e);
  if (kind === 'declare') return remplirLbl(AGR_LBL.declare, { date: date as string });
  if (kind === 'mesure') return remplirLbl(AGR_LBL.mesure, { date: date as string });
  if (kind === 'mesure_foreur') return remplirLbl(AGR_LBL.mesureForeur, { date: date as string });
  if (kind === 'mesure_essai') return remplirLbl(AGR_LBL.mesureEssai, { date: date as string });
  return AGR_LBL.aConfirmer;
}

/**
 * Géométrie du graphe « courbe de la pompe + point de fonctionnement » : MISE À
 * L'ÉCHELLE seule (aucune valeur calculée). `null` sans point de fonctionnement.
 */
export interface CourbeGeometrie {
  largeur: number;
  hauteur: number;
  polyline: string;
  point: { x: number; y: number };
  axe: { x0: number; y0: number; x1: number; y1: number };
  debitMax: number;
  hmtMax: number;
}

export function courbeGeometrie(pf: SyntheseAgricole['pointFonctionnement']): CourbeGeometrie | null {
  if (!pf) return null;
  const L = 360;
  const H = 220;
  const x0 = 44;
  const y0 = 184;
  const x1 = 344;
  const y1 = 16;
  const debitMax = Math.max(...pf.courbe.map(([q]) => q), pf.point.debitM3h) || 1;
  const hmtMax = Math.max(...pf.courbe.map(([, h]) => h), pf.point.hmtM) || 1;
  const px = (q: number) => x0 + (q / debitMax) * (x1 - x0);
  const py = (h: number) => y0 - (h / hmtMax) * (y0 - y1);
  const r = (n: number) => Math.round(n * 10) / 10;
  return {
    largeur: L,
    hauteur: H,
    polyline: pf.courbe.map(([q, h]) => `${r(px(q))},${r(py(h))}`).join(' '),
    point: { x: r(px(pf.point.debitM3h)), y: r(py(pf.point.hmtM)) },
    axe: { x0, y0, x1, y1 },
    debitMax,
    hmtMax,
  };
}

// ════════════════════════════════════════════════════════════════════════════
// AGW304 — Jumeau web du document agricole (2/2) : argent déclaré, énergie
// actuelle, règle de l'aide FDA, garanties par composant, options du kit et
// formalités — LUS dans `synthese_agricole`, rendus tels que servis.
//
// DISCIPLINE (D-AGR-5, D-AGR-6, D-AGR-8) : aucun calcul ici. L'argent est le
// bloc PUBLIC `economie_pompage` (AGR3) recopié par le serveur, OMIS quand il
// n'est pas publiable ; l'aide FDA est la RÈGLE (plafonds + conditions + source),
// jamais un montant propre au client ni un délai ; les garanties sont celles des
// fiches produits, jamais complétées par une constante.
// ════════════════════════════════════════════════════════════════════════════

export interface SyntheseRemplacement {
  composant: string;
  annee: number;
  montantTtc: number;
}

export interface SyntheseEconomiesAgricole {
  /** `carburant` | … (nature du cas servi). */
  cas: string | null;
  /** Dépense actuelle déclarée, par an (MAD). */
  depenseActuelleMadAn: number | null;
  /** Entretien payé déclaré, par an (MAD). */
  entretienMadAn: number | null;
  /** Charges du solaire par an (barème société). */
  chargesSolairesMadAn: number | null;
  /** Économie nette de l'année 1 (flux an 1 servi). */
  economieNetteAn1: number | null;
  horizonAns: number | null;
  /** Retour SANS aide (années), tel que servi. */
  retourAns: number | null;
  /** Coût du m³ avant / avec le solaire (MAD). */
  /** AGQ17/AGQ35 — `actuel` reste `null` pour un NOUVEAU forage (aucune dépense actuelle) : le m³ solaire se dit seul. */
  coutM3: { actuel: number | null; solaire: number } | null;
  /** AGQ20/AGQ35 — motif SERVI quand le retour n'est pas publié (au-delà de l'horizon…), sinon `null`. */
  retourMotif: string | null;
  /** Remplacements COMPTÉS (année + montant TTC servis) ; les autres sont omis. */
  remplacements: SyntheseRemplacement[];
  /** Date de déclaration la plus récente des entrées (ISO), ou `null`. */
  declareLe: string | null;
  /** Les entrées déclarées {cle, valeur, unite} — recopiées telles quelles. */
  entreesDeclarees: Array<{ cle: string; valeur: unknown; unite: string | null }>;
}

export interface SyntheseAideFda {
  conditions: string[];
  /** Les QUATRE plafonds de la règle — AUCUN autre nombre n'est lu. */
  plafonds: { tauxPct: number | null; parHa: number | null; parKwc: number | null; parProjet: number | null };
  edition: string | null;
  source: string | null;
  releveLe: string | null;
  /** La règle en toutes lettres, par langue, telle que servie. */
  textes: Lbl3 | null;
}

export interface SyntheseGarantie {
  composant: string;
  mois: number | null;
  libelle: string | null;
}

export interface SyntheseOptionKit {
  ligneId: number | null;
  designation: string;
  totalTtc: number | null;
  /** AGQ11/AGQ35 — faux : « prix sur devis » (aucun montant, pas d'ajout en ligne). */
  prixConnu: boolean;
  /** AGQ11/AGQ35 — mention servie à côté de l'option (ex. compteur exigé), ou `null`. */
  mention: string | null;
}

export interface SyntheseFormalite {
  cle: string | null;
  textes: Lbl3;
  source: string | null;
}

export interface SyntheseAgricoleArgent {
  economies: SyntheseEconomiesAgricole | null;
  /** Énergie actuelle DÉCLARÉE (butane / diesel / électrique / aucune), avec provenance. */
  energieActuelle: { valeur: string; provenance: SyntheseProvenance } | null;
  aideFda: SyntheseAideFda | null;
  garanties: SyntheseGarantie[];
  optionsKit: SyntheseOptionKit[];
  nonInclus: string[];
  formalites: SyntheseFormalite[];
}

/** AGQ20/AGQ35 — le motif servi de l'omission du retour (`omissions[].cle` commençant par « retour »), seulement sans `retour_ans`. */
function lireMotifRetour(omissions: unknown, retourAns: number | null): string | null {
  if (retourAns !== null || !Array.isArray(omissions)) return null;
  for (const o of omissions) {
    if (estRecord(o) && typeof o.cle === 'string' && o.cle.startsWith('retour')) return texteServi(o.motif);
  }
  return null;
}

function lireEconomies(v: unknown): SyntheseEconomiesAgricole | null {
  if (!estRecord(v)) return null;
  // Le serveur n'envoie que le bloc publiable ; la garde est doublée ici : un bloc
  // non calculé / non publiable n'atteint JAMAIS l'écran.
  if (v.statut !== 'calcule' || v.publiable_client !== true) return null;
  const dep = estRecord(v.depense_actuelle) ? v.depense_actuelle : {};
  const charges = estRecord(v.charges_solaires) ? v.charges_solaires : {};
  const eco = estRecord(v.economie) ? v.economie : {};
  const flux = Array.isArray(eco.flux) ? eco.flux : [];
  const an1 = flux.find((f) => estRecord(f) && f.annee === 1);
  const m3 = estRecord(v.mad_par_m3) ? v.mad_par_m3 : null;
  const actuel = m3 ? nombreServi(m3.actuel) : null;
  const solaire = m3 ? nombreServi(m3.solaire) : null;
  const remplacements: SyntheseRemplacement[] = [];
  if (Array.isArray(v.remplacements)) {
    for (const r of v.remplacements) {
      if (!estRecord(r)) continue;
      const annee = nombreServi(r.annee);
      const montant = nombreServi(r.montant_ttc_mad);
      const composant = texteServi(r.composant);
      if (composant && annee !== null && annee > 0 && montant !== null) {
        remplacements.push({ composant, annee, montantTtc: montant });
      }
    }
  }
  const entrees: SyntheseEconomiesAgricole['entreesDeclarees'] = [];
  const dates: string[] = [];
  if (Array.isArray(v.entrees_declarees)) {
    for (const e of v.entrees_declarees) {
      if (!estRecord(e) || !texteServi(e.cle)) continue;
      entrees.push({ cle: e.cle as string, valeur: e.valeur ?? null, unite: texteServi(e.unite) });
      const d = texteServi(e.saisi_le);
      if (d && dateJjMmAaaa(d)) dates.push(d.slice(0, 10));
    }
  }
  return {
    cas: texteServi(v.cas),
    depenseActuelleMadAn: nombreServi(dep.annuelle_mad),
    entretienMadAn: nombreServi(dep.entretien_mad_an),
    chargesSolairesMadAn: nombreServi(charges.total_mad_an),
    economieNetteAn1: estRecord(an1) ? nombreServi(an1.flux_mad) : null,
    horizonAns: nombreServi(eco.horizon_ans),
    retourAns: nombreServi(eco.retour_ans),
    coutM3: solaire !== null ? { actuel, solaire } : null,
    retourMotif: lireMotifRetour(v.omissions, nombreServi(eco.retour_ans)),
    remplacements,
    declareLe: dates.length > 0 ? dates.sort()[dates.length - 1] : null,
    entreesDeclarees: entrees,
  };
}

function lireEnergieActuelle(v: unknown): SyntheseAgricoleArgent['energieActuelle'] {
  if (!estRecord(v)) return null;
  const valeur = texteServi(v.valeur);
  const prov = lireProvenance({ energie_actuelle: v.provenance })[0];
  // Sans provenance, ce n'est pas une déclaration (jamais le défaut de l'écran).
  return valeur && prov ? { valeur, provenance: prov } : null;
}

function lireTextesTroisVoix(v: unknown): Lbl3 | null {
  if (!estRecord(v)) return null;
  const fr = texteServi(v.fr);
  if (!fr) return null;
  return { fr, en: texteServi(v.en) ?? fr, ar: texteServi(v.ar) ?? fr };
}

function lireAideFda(v: unknown): SyntheseAideFda | null {
  if (!estRecord(v)) return null;
  const pl = estRecord(v.plafonds) ? v.plafonds : {};
  return {
    conditions: Array.isArray(v.conditions) ? v.conditions.filter((c): c is string => typeof c === 'string') : [],
    plafonds: {
      tauxPct: nombreServi(pl.taux_pct),
      parHa: nombreServi(pl.plafond_mad_par_ha),
      parKwc: nombreServi(pl.plafond_mad_par_kwc),
      parProjet: nombreServi(pl.plafond_mad_par_projet),
    },
    edition: texteServi(v.edition),
    source: texteServi(v.source),
    releveLe: texteServi(v.releve_le),
    textes: lireTextesTroisVoix(v.textes),
  };
}

function lireGaranties(v: unknown): SyntheseGarantie[] {
  if (!Array.isArray(v)) return [];
  const out: SyntheseGarantie[] = [];
  for (const g of v) {
    if (!estRecord(g) || !texteServi(g.composant)) continue;
    const mois = nombreServi(g.mois);
    out.push({
      composant: g.composant as string,
      mois: mois !== null && Number.isInteger(mois) && mois > 0 ? mois : null,
      libelle: texteServi(g.libelle),
    });
  }
  return out;
}

function lireOptionsKit(v: unknown): SyntheseOptionKit[] {
  if (!Array.isArray(v)) return [];
  const out: SyntheseOptionKit[] = [];
  for (const o of v) {
    if (!estRecord(o)) continue;
    const designation = texteServi(o.designation);
    if (!designation) continue;
    const id = nombreServi(o.ligne_id);
    const totalTtc = nombreServi(o.total_ttc);
    out.push({
      ligneId: id !== null && Number.isInteger(id) ? id : null,
      designation,
      totalTtc,
      prixConnu: o.prix_connu === true || (o.prix_connu === undefined && totalTtc !== null),
      mention: texteServi(o.mention),
    });
  }
  return out;
}

function lireFormalites(v: unknown): SyntheseFormalite[] {
  if (!Array.isArray(v)) return [];
  const out: SyntheseFormalite[] = [];
  for (const f of v) {
    if (!estRecord(f)) continue;
    const textes = lireTextesTroisVoix(f.textes);
    if (!textes) continue;
    out.push({ cle: texteServi(f.cle), textes, source: texteServi(f.source) });
  }
  return out;
}

/**
 * AGW304 — extracteur PUR des blocs « argent » de `synthese_agricole`. `null` hors
 * mode agricole ou sans synthèse. Bloc absent → `null` / liste vide (jamais un 0,
 * jamais une constante qui complète : une garantie sans durée servie reste sans durée).
 */
export function syntheseAgricoleArgent(
  p: Pick<ProposalResponse, 'mode_installation' | 'quote'> | null | undefined,
): SyntheseAgricoleArgent | null {
  if (!p || resolveInstallMode(p) !== 'agricole') return null;
  const brut = (p as { synthese_agricole?: unknown }).synthese_agricole;
  if (!estRecord(brut) || Object.keys(brut).length === 0) return null;
  return {
    economies: lireEconomies(brut.economies),
    energieActuelle: lireEnergieActuelle(brut.energie_actuelle),
    aideFda: lireAideFda(brut.aide_fda),
    garanties: lireGaranties(brut.garanties),
    optionsKit: lireOptionsKit(brut.options_kit),
    nonInclus: Array.isArray(brut.non_inclus) ? brut.non_inclus.filter((x): x is string => typeof x === 'string') : [],
    formalites: lireFormalites(brut.formalites),
  };
}

/** Durée d'une garantie (mois servis) en mots : 24 → « 2 ans », 18 → « 18 mois ». */
export function dureeGarantie(mois: number): Lbl3 {
  if (mois % 12 === 0) {
    const ans = String(mois / 12);
    return ans === '1'
      ? { fr: '1 an', en: '1 year', ar: '1 سنة' }
      : { fr: `${ans} ans`, en: `${ans} years`, ar: `${ans} سنوات` };
  }
  return { fr: `${mois} mois`, en: `${mois} months`, ar: `${mois} أشهر` };
}

/** Libellé d'une garantie par composant ; `null` si la durée n'est pas servie (le libellé servi est alors repris). */
export function libelleGarantie(g: SyntheseGarantie): { lbl: Lbl3; avecDuree: boolean } {
  const gabarits: Record<string, Lbl3> = {
    pompe: { fr: 'Garantie constructeur de la pompe : {duree}', en: 'Pump manufacturer warranty: {duree}', ar: 'ضمان الصانع للمضخة: {duree}' },
    variateur: { fr: 'Garantie constructeur du variateur : {duree}', en: 'Drive manufacturer warranty: {duree}', ar: 'ضمان الصانع للمغير: {duree}' },
    panneaux: { fr: 'Garantie produit des panneaux : {duree}', en: 'Panel product warranty: {duree}', ar: 'ضمان منتوج الألواح: {duree}' },
    performance_panneaux: { fr: 'Garantie de production des panneaux : {duree}', en: 'Panel output warranty: {duree}', ar: 'ضمان إنتاج الألواح: {duree}' },
  };
  const gab = gabarits[g.composant];
  if (gab && g.mois !== null) return { lbl: fillDuree(gab, dureeGarantie(g.mois)), avecDuree: true };
  const fr = g.libelle ?? g.composant;
  return { lbl: { fr, en: fr, ar: fr }, avecDuree: false };
}

function fillDuree(gab: Lbl3, d: Lbl3): Lbl3 {
  return { fr: gab.fr.replace('{duree}', d.fr), en: gab.en.replace('{duree}', d.en), ar: gab.ar.replace('{duree}', d.ar) };
}

/** Libellés structurels de la section « argent » (mots du catalogue du devis, `agr_*`). */
export const AGR_ARGENT_LBL = {
  titreArgent: { fr: 'Votre argent', en: 'Your money', ar: 'أموالكم' },
  depenseActuelle: { fr: 'Votre dépense actuelle par an', en: 'Your current spending per year', ar: 'مصاريفكم الحالية في السنة' },
  chargesSolaires: { fr: 'Entretien du solaire par an, selon nos tarifs', en: 'Solar upkeep per year, at our rates', ar: 'صيانة المنظومة الشمسية في السنة، حسب أسعارنا' },
  economieNetteAn1: { fr: 'Économie nette, année 1', en: 'Net saving, year 1', ar: 'التوفير الصافي، السنة الأولى' },
  retourSansAide: { fr: 'Retour sur investissement, sans aide', en: 'Payback, without subsidy', ar: 'استرجاع الاستثمار، بدون دعم' },
  coutM3: { fr: 'Coût du m³ : avant / avec le solaire', en: 'Cost per m³: before / with solar', ar: 'تكلفة المتر المكعب: قبل / مع الطاقة الشمسية' },
  remplacement: {
    fr: 'Remplacement {composant} prévu l’année {annee} (déjà compté dans le calcul)',
    en: 'Replacement of the {composant} planned in year {annee} (already included in the calculation)',
    ar: 'استبدال {composant} مبرمج في السنة {annee} (محتسب سلفاً في الحساب)',
  },
  composantPompe: { fr: 'pompe', en: 'pump', ar: 'المضخة' },
  composantVariateur: { fr: 'variateur', en: 'drive', ar: 'المغير' },
  consoPrixPaye: {
    fr: 'Consommation et prix payé : {phrase}.',
    en: 'Consumption and price paid: {phrase}.',
    ar: 'الاستهلاك والثمن المؤدى: {phrase}.',
  },
  indexation: { fr: 'Prix du carburant supposé stable (aucune hausse comptée).', en: 'Fuel price assumed stable (no increase counted).', ar: 'ثمن الوقود مفترض ثابتاً (دون احتساب أي زيادة).' },
  fdaNonComptee: {
    fr: "L'aide FDA éventuelle n'est pas comptée.",
    en: 'Any FDA subsidy is not counted.',
    ar: 'الدعم المحتمل من صندوق التنمية الفلاحية غير محتسب.',
  },
  condition: {
    fr: 'Si le solaire remplace tout votre pompage actuel, à volume pompé égal.',
    en: 'If solar replaces all of your current pumping, for the same volume pumped.',
    ar: 'إذا عوّضت الطاقة الشمسية كل ضخّكم الحالي، بنفس حجم الماء المضخوخ.',
  },
  nAns: { fr: '{n} ans', en: '{n} years', ar: '{n} سنوات' },
  energieActuelle: { fr: 'Énergie actuelle', en: 'Current energy', ar: 'الطاقة الحالية' },
  aideTitre: { fr: "Aide de l'État (FDA) : la règle", en: 'State aid (FDA): the rule', ar: 'دعم الدولة (صندوق التنمية الفلاحية): القاعدة' },
  garanties: { fr: 'Garanties', en: 'Warranties', ar: 'الضمانات' },
  optionsKit: {
    fr: 'Options du kit (prix du supplément, hors total ci-dessus)',
    en: 'Kit options (price of the extra, not in the total above)',
    ar: 'خيارات العدة (ثمن الإضافة، خارج المجموع أعلاه)',
  },
  nonInclus: { fr: 'Non inclus', en: 'Not included', ar: 'غير مشمول' },
  formalites: { fr: 'Formalités', en: 'Formalities', ar: 'الإجراءات' },
} satisfies Record<string, Lbl3>;

/** Composants remplaçables / garantis (clés machine du moteur) → libellé. */
export const AGR_COMPOSANT_LBL: Record<string, Lbl3> = {
  pompe: { fr: 'pompe', en: 'pump', ar: 'المضخة' },
  variateur: { fr: 'variateur', en: 'drive', ar: 'المغير' },
};

export const AGR_ENERGIE_LBL: Record<string, Lbl3> = {
  butane: { fr: 'butane (bouteilles)', en: 'butane (bottles)', ar: 'البوتان (قنينات)' },
  diesel: { fr: 'gasoil (groupe électrogène)', en: 'diesel (generator)', ar: 'الغازوال (مولد كهربائي)' },
  electrique: { fr: 'réseau électrique (facture)', en: 'grid electricity (bill)', ar: 'الشبكة الكهربائية (فاتورة)' },
  aucune: { fr: 'aucune (nouveau forage)', en: 'none (new borehole)', ar: 'لا شيء (ثقب جديد)' },
};
