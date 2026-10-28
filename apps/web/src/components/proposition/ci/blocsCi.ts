/**
 * CPRW (27/10/2026) — blocs client C&I de /proposition qui reprennent les MÊMES mots que le PDF
 * (`quote_engine/i18n_labels.py`, `ci/blocs.py`). Aucun chiffre n'est calculé ici : tout est lu dans
 * `synthese_ci` (extracteur `syntheseCi.ts`) ; une valeur non servie est omise, jamais un « 0 ».
 */
import { formatMAD, formatMADCentimes, formatNumber } from '../../../lib/proposition';
import { argentCiCalcule } from './syntheseCi';
import type { SyntheseCi, TextesCi } from './syntheseCi';

// ── CPRW15 — garanties ─────────────────────────────────────────────────────────────────────

export const TITRE_GARANTIES_CI: TextesCi = { fr: 'Garanties', en: 'Warranties', ar: 'الضمانات' };

/** `i18n_labels.py` `ci_garantie_*` (clé = `composant` servi). */
export const LBL_GARANTIES_CI: Record<string, TextesCi> = {
  installation: { fr: 'Installation', en: 'Installation', ar: 'التركيب' },
  onduleur: { fr: 'Onduleur', en: 'Inverter', ar: 'العاكس' },
  panneaux: { fr: 'Panneaux', en: 'Panels', ar: 'الألواح' },
  panneaux_performance: { fr: 'Performance', en: 'Performance', ar: 'المردودية' },
  batterie: { fr: 'Batterie', en: 'Battery', ar: 'البطارية' },
};

/** `i18n_labels.py` `ci_ans`. */
export const ANS_CI: TextesCi = { fr: 'ans', en: 'years', ar: 'سنوات' };

/** `i18n_labels.py` `ci_legende_garanties` (légende du PDF). */
export const LEGENDE_GARANTIES_CI: TextesCi = {
  fr: "Durées : garanties du fabricant (fiches produit) ; pose : engagement de l'installateur.",
  en: "Durations: manufacturer warranties (product sheets); installation: the installer's commitment.",
  ar: 'المدد: ضمانات الصانع (بطاقات المنتجات)؛ التركيب: التزام المركِّب.',
};

/** Les garanties fabricant SERVIES avec une durée lisible et un composant connu ; rien d'autre. */
export function garantiesCi(
  ci: SyntheseCi | null,
): Array<{ composant: string; libelle: TextesCi; annees: number }> {
  return (ci?.services?.garanties ?? []).flatMap((g) => {
    const libelle = LBL_GARANTIES_CI[g.composant];
    return libelle && g.annees !== null && g.composant !== 'installation'
      ? [{ composant: g.composant, libelle, annees: g.annees }]
      : [];
  });
}

// ── CPRW16 — échéancier de paiement ────────────────────────────────────────────────────────

export const TITRE_ECHEANCIER_CI: TextesCi = { fr: 'Échéancier de paiement', en: 'Payment schedule', ar: 'جدول الأداء' };

/** `i18n_labels.py` `ci_jalon_*` (clé = `jalon` servi). */
export const JALONS_CI: Record<string, TextesCi> = {
  commande: { fr: 'À la commande', en: 'On order', ar: 'عند الطلب' },
  livraison: { fr: 'À la livraison', en: 'On delivery', ar: 'عند التسليم' },
  mise_en_service: { fr: 'À la mise en service', en: 'On commissioning', ar: 'عند التشغيل' },
  reception_definitive: { fr: 'À la réception définitive', en: 'On final acceptance', ar: 'عند التسلم النهائي' },
};

/** `i18n_labels.py` `ci_ttc`. */
export const TTC_CI: TextesCi = { fr: 'TTC', en: 'incl. VAT', ar: 'شامل الضريبة' };

/**
 * Les jalons SERVIS : % servi, montant TTC seulement s'il est servi et non nul ; jalon inconnu →
 * le libellé servi (même texte dans les trois langues), jamais un libellé inventé.
 */
export function echeancierCi(
  ci: SyntheseCi | null,
): Array<{ jalon: string | null; libelle: TextesCi; pct: number; montantTtc: number | null }> {
  return (ci?.echeancier ?? []).flatMap((e) => {
    const connu = e.jalon ? JALONS_CI[e.jalon] : undefined;
    const libelle = connu ?? (e.libelle ? { fr: e.libelle, en: e.libelle, ar: e.libelle } : null);
    if (!libelle) return [];
    return [{ jalon: e.jalon, libelle, pct: e.pct, montantTtc: e.montantTtc !== null && e.montantTtc > 0 ? e.montantTtc : null }];
  });
}

// ── CPRW17 — services (O&M, suivi de production, raccordement) ─────────────────────────────

/** Mots du PDF (`i18n_labels.py` `ci_<clé>`, entités HTML décodées) ; `{heures}` / `{societe}` à remplacer. */
export const LBL_SERVICES_CI: Record<string, TextesCi> = {
  services: { fr: 'Services', en: 'Services', ar: 'الخدمات' },
  maintenance: { fr: 'Maintenance (O&M)', en: 'Maintenance (O&M)', ar: 'الصيانة (التشغيل والصيانة)' },
  ht: { fr: 'HT', en: 'excl. VAT', ar: 'دون احتساب الضريبة' },
  tarif_sur_demande: { fr: 'tarif sur demande', en: 'price on request', ar: 'السعر عند الطلب' },
  propose_non_inclus: {
    fr: ' (proposé, non inclus dans le total)',
    en: ' (proposed, not included in the total)',
    ar: ' (مقترح، غير مدرج في المجموع)',
  },
  suivi_production: { fr: 'Suivi de production', en: 'Production monitoring', ar: 'تتبع الإنتاج' },
  suivi_production_inclus: {
    fr: 'Suivi de production inclus',
    en: 'Production monitoring included',
    ar: 'تتبع الإنتاج مشمول',
  },
  intervention_sous: {
    fr: 'intervention sous {heures} h',
    en: 'intervention within {heures} h',
    ar: 'التدخل في غضون {heures} ساعة',
  },
  dossier_raccordement: {
    fr: 'Raccordement et autorisations du site : dossier monté et suivi par {societe}',
    en: 'Site grid connection and permits: file prepared and followed up by {societe}',
    ar: 'الربط بالشبكة وتراخيص الموقع: ملف تعدّه وتتابعه {societe}',
  },
};

/** Repli du nom de la société émettrice, le même que le PDF sans identité servie (`residential/theme.py::_DEFAULT_BRAND`). */
const SOCIETE_CI = 'TAQINOR';

/**
 * Nom de la société ÉMETTRICE servi (`emetteur.nom`, même `company_identity` que le PDF —
 * `ci/blocs.py::bloc_services` remplit `{societe}` avec `brand_name`) ; absent ou vide → repli du PDF.
 */
export function nomSocieteEmettrice(payload: unknown): string {
  const e = payload && typeof payload === 'object' ? (payload as { emetteur?: unknown }).emetteur : undefined;
  const nom = e && typeof e === 'object' ? (e as { nom?: unknown }).nom : undefined;
  return typeof nom === 'string' && nom.trim() !== '' ? nom.trim() : SOCIETE_CI;
}

/**
 * Le bloc « Services » du PDF (`ci/blocs.py::bloc_services`) : O&M nommée (prix HT servi, sinon « tarif sur
 * demande » ; « proposé, non inclus » si `statut === 'propose'`), suivi de production (délai seulement
 * s'il est servi et > 0), phrase de raccordement quand un régime est servi. `null` sans aucun service.
 */
export function servicesCi(ci: SyntheseCi | null, societe: string = SOCIETE_CI): { titre: TextesCi; lignes: TextesCi[] } | null {
  const s = ci?.services ?? null;
  if (!s) return null;
  const par = (f: (lg: keyof TextesCi) => string): TextesCi => ({ fr: f('fr'), en: f('en'), ar: f('ar') });
  const L = LBL_SERVICES_CI;
  const lignes: TextesCi[] = [];
  const om = s.omOption;
  if (om) {
    lignes.push(
      par((lg) => {
        const detail = (om.lignes.length > 0 ? om.lignes : [{ designation: om.libelle, totalHt: null }]).map((li) => {
          const prix = li.totalHt !== null && li.totalHt > 0 ? `${formatMADCentimes(li.totalHt)} ${L.ht![lg]}` : L.tarif_sur_demande![lg];
          return `${li.designation ?? ''} — ${prix}`;
        });
        return `${L.maintenance![lg]} : ${detail.join(' ; ')}${om.statut === 'propose' ? L.propose_non_inclus![lg] : ''}`;
      }),
    );
  }
  if (s.suiviProduction) {
    const h = s.suiviProduction.delaiHeures;
    lignes.push(
      h !== null && h > 0
        ? par((lg) => `${L.suivi_production![lg]} : ${L.intervention_sous![lg].replace('{heures}', String(h))}`)
        : L.suivi_production_inclus!,
    );
  }
  if (s.raccordementRegime) {
    lignes.push(par((lg) => L.dossier_raccordement![lg].replace('{societe}', societe)));
  }
  return lignes.length > 0 ? { titre: L.services!, lignes } : null;
}

// ── CPRW18 — comparaison sans / avec batterie ──────────────────────────────────────────────

/** Mots du PDF : `ci/blocs.py::LIBELLES_OPTION_AVEC` (titre, economie, retour, ans) et `i18n_labels.py` `total_ttc`. */
export const LBL_COMPARAISON_CI = {
  titre: { fr: 'Option avec batterie', en: 'Battery option', ar: 'خيار مع بطارية' },
  economie: { fr: 'Économie annuelle HT', en: 'Annual saving excl. VAT', ar: 'التوفير السنوي دون ضريبة' },
  retour: { fr: 'Retour sur investissement', en: 'Payback', ar: 'مدة استرداد الاستثمار' },
  ans: { fr: 'ans', en: 'years', ar: 'سنوات' },
  total_ttc: { fr: 'Total TTC', en: 'Total incl. VAT', ar: 'المجموع شامل الضريبة' },
} satisfies Record<string, TextesCi>;

/** Titre de la colonne « sans » : celui de la carte de la page (offre réseau d'abord). */
const TITRE_SANS_CI: TextesCi = {
  fr: 'Offre réseau (autoconsommation)',
  en: 'Grid-connected offer (self-consumption)',
  ar: 'عرض الربط بالشبكة (استهلاك ذاتي)',
};

export interface LigneComparaisonCi {
  cle: 'total_ttc' | 'valeur' | 'economie' | 'retour';
  libelle: TextesCi | null;
  /** Valeur déjà formatée (nombres) ; vide pour la phrase servie. */
  valeur: string;
  /** Phrase servie par le moteur (FR/EN/AR) — jamais composée ici. */
  textes?: TextesCi;
}

/**
 * Deux colonnes — offre réseau / option avec batterie — qui ne portent QUE des valeurs servies : Total TTC
 * par option (payload, sinon `option_batterie.totaux`), puis pour « avec » la phrase servie du moteur
 * (capacité utile, énergie restituée), l'économie annuelle HT et le retour (`valeur_chiffree`). Une valeur
 * absente ou nulle est omise, jamais un « 0 » ; aucune autoconsommation/couverture par option (non servie).
 * `null` sans `option_batterie` servie.
 */
export function comparaisonBatterieCi(
  ci: SyntheseCi | null,
  sansTtc: number | null | undefined,
  avecTtc: number | null | undefined,
): { titre: TextesCi; colonnes: Array<{ cle: 'sans' | 'avec'; titre: TextesCi; lignes: LigneComparaisonCi[] }> } | null {
  const ob = ci?.optionBatterie ?? null;
  if (!ob) return null;
  const positif = (n: number | null | undefined): n is number => typeof n === 'number' && Number.isFinite(n) && n > 0;
  const ttcAvec = positif(avecTtc) ? avecTtc : (ob.totaux?.ttc ?? null);
  const sans: LigneComparaisonCi[] = [];
  if (positif(sansTtc)) sans.push({ cle: 'total_ttc', libelle: LBL_COMPARAISON_CI.total_ttc, valeur: formatMAD(sansTtc) });
  const avec: LigneComparaisonCi[] = [];
  if (positif(ttcAvec)) avec.push({ cle: 'total_ttc', libelle: LBL_COMPARAISON_CI.total_ttc, valeur: formatMAD(ttcAvec) });
  const v = ob.chiffres;
  if (ob.valeurChiffree && (positif(v?.capaciteUtileKwh) || positif(v?.restitueKwhAn) || positif(v?.economieAnnuelleMad))) {
    avec.push({ cle: 'valeur', libelle: null, valeur: '', textes: ob.valeurChiffree });
  }
  // La phrase servie porte déjà l'économie annuelle : la ligne chiffrée ne sort que sans phrase (jamais deux fois le même chiffre).
  if (positif(v?.economieAnnuelleMad) && !avec.some((l) => l.cle === 'valeur')) avec.push({ cle: 'economie', libelle: LBL_COMPARAISON_CI.economie, valeur: formatMAD(v.economieAnnuelleMad) });
  if (positif(v?.retourSimpleAns)) avec.push({ cle: 'retour', libelle: LBL_COMPARAISON_CI.retour, valeur: formatNumber(v.retourSimpleAns, 1) });
  return {
    titre: LBL_COMPARAISON_CI.titre,
    colonnes: [
      { cle: 'sans', titre: TITRE_SANS_CI, lignes: sans },
      { cle: 'avec', titre: LBL_COMPARAISON_CI.titre, lignes: avec },
    ],
  };
}

// ── CPRW25 — offre de financement (commercial ET industriel) ──────────────────────────────

export const TITRE_FINANCEMENT_CI: TextesCi = { fr: 'Offre de financement', en: 'Financing offer', ar: 'عرض التمويل' };
const HT_CI: TextesCi = { fr: 'HT', en: 'excl. VAT', ar: 'دون احتساب الضريبة' };
const NBSP = ' ';

/**
 * L'offre de financement SERVIE (`synthese_ci.argent.financement`, `ci/blocs.py::bloc_financement`) : libellé
 * client (sinon le titre), échéance mensuelle (+ « sur N mois »), économie mensuelle moyenne estimée, écart
 * mensuel, source — sur la base HT/TTC servie. `null` sans échéance servie (comme le PDF). Aucun taux inventé.
 */
export function financementCi(ci: SyntheseCi | null): { titre: TextesCi; lignes: TextesCi[] } | null {
  const a = argentCiCalcule(ci);
  const f = a?.financement ?? null;
  if (!a || !f || f.echeanceMad === null) return null;
  const suffixe = (lg: keyof TextesCi): string => (a.base === 'ht' ? ` ${HT_CI[lg]}` : a.base === 'ttc' ? ` ${TTC_CI[lg]}` : '');
  const par = (g: (lg: keyof TextesCi) => string): TextesCi => ({ fr: g('fr'), en: g('en'), ar: g('ar') });
  const sur = { fr: (n: string) => `sur ${n} mois`, en: (n: string) => `over ${n} months`, ar: (n: string) => `على مدى ${n} شهرا` };
  const lignes: TextesCi[] = [];
  if (f.libelleClient) lignes.push({ fr: f.libelleClient, en: f.libelleClient, ar: f.libelleClient });
  else lignes.push(TITRE_FINANCEMENT_CI);
  lignes.push(
    par((lg) => `${LBL_FINANCEMENT_CI.echeance[lg]}${NBSP}: ${formatMADCentimes(f.echeanceMad!)}${suffixe(lg)}${f.dureeMois ? ' ' + sur[lg](formatNumber(f.dureeMois, 0)) : ''}`),
  );
  if (f.economieMensuelleMoyenneMad !== null)
    lignes.push(par((lg) => `${LBL_FINANCEMENT_CI.economie[lg]}${NBSP}: ${formatMADCentimes(f.economieMensuelleMoyenneMad!)}${suffixe(lg)}`));
  if (f.ecartMensuelMad !== null)
    lignes.push(par((lg) => `${LBL_FINANCEMENT_CI.ecart[lg]}${NBSP}: ${formatMADCentimes(f.ecartMensuelMad!)}${suffixe(lg)}`));
  // CEC15 (affichage) — apport et frais servis (> 0), retour de l'offre servi ; omis sans la clé (`ci_fin_*` du PDF).
  if (f.apportMad !== null && f.apportMad > 0)
    lignes.push(par((lg) => `${LBL_FINANCEMENT_CI.apport[lg]}${NBSP}: ${formatMADCentimes(f.apportMad!)}`));
  if (f.fraisMad !== null && f.fraisMad > 0)
    lignes.push(par((lg) => `${LBL_FINANCEMENT_CI.frais[lg]}${NBSP}: ${formatMADCentimes(f.fraisMad!)}`));
  if (f.retourOffreAns !== null) {
    const r = f.retourOffreAns.toFixed(1).replace('.', ',');
    // Accord arabe du PDF (`couverture.annees_accordees`) : « سنوات » de 3 à 10 ans entiers, « سنة » sinon.
    const entier = Number.isInteger(Number(f.retourOffreAns.toFixed(1)));
    const ans: TextesCi = { ...ANS_CI, ar: entier && f.retourOffreAns >= 3 && f.retourOffreAns <= 10 ? ANS_CI.ar : 'سنة' };
    lignes.push(par((lg) => `${LBL_FINANCEMENT_CI.retour[lg]}${NBSP}: ${r}${NBSP}${ans[lg]}`));
  }
  if (f.source) lignes.push(par((lg) => `${LBL_FINANCEMENT_CI.source[lg]}${NBSP}: ${f.source}`));
  return { titre: TITRE_FINANCEMENT_CI, lignes };
}

/** `i18n_labels.py` `ci_echeance_mensuelle`, `ci_economie_mensuelle`, `ci_ecart_mensuel`, `ci_source`. */
const LBL_FINANCEMENT_CI = {
  echeance: { fr: 'Échéance mensuelle', en: 'Monthly instalment', ar: 'القسط الشهري' } as TextesCi,
  economie: { fr: 'Économie mensuelle moyenne estimée', en: 'Estimated average monthly saving', ar: 'متوسط الوفر الشهري المقدر' } as TextesCi,
  ecart: { fr: 'Écart mensuel', en: 'Monthly difference', ar: 'الفارق الشهري' } as TextesCi,
  source: { fr: 'Source', en: 'Source', ar: 'المصدر' } as TextesCi,
  /** CEC15 — `i18n_labels_ci.py` `ci_fin_apport`, `ci_fin_frais`, `ci_fin_retour`. */
  apport: { fr: 'Apport à la signature', en: 'Deposit at signature', ar: 'المساهمة عند التوقيع' } as TextesCi,
  frais: { fr: "Frais de l'offre", en: 'Offer fees', ar: 'مصاريف العرض' } as TextesCi,
  retour: { fr: "Retour sur l'offre", en: 'Payback with the offer', ar: 'مدة الاسترداد مع العرض' } as TextesCi,
};
