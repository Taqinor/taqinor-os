/**
 * CPRW (27/10/2026) — blocs client C&I de /proposition qui reprennent les MÊMES mots que le PDF
 * (`quote_engine/i18n_labels.py`, `ci/blocs.py`). Aucun chiffre n'est calculé ici : tout est lu dans
 * `synthese_ci` (extracteur `syntheseCi.ts`) ; une valeur non servie est omise, jamais un « 0 ».
 */
import { formatMAD } from '../../../lib/proposition';
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

/** Le nom de la société émettrice dans la phrase de raccordement (repli fondateur du PDF). */
const SOCIETE_CI = 'TAQINOR';

/**
 * Le bloc « Services » du PDF (`ci/blocs.py::bloc_services`) : O&M nommée (prix HT servi, sinon « tarif sur
 * demande » ; « proposé, non inclus » si `statut === 'propose'`), suivi de production (délai seulement
 * s'il est servi et > 0), phrase de raccordement quand un régime est servi. `null` sans aucun service.
 */
export function servicesCi(ci: SyntheseCi | null): { titre: TextesCi; lignes: TextesCi[] } | null {
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
          const prix = li.totalHt !== null && li.totalHt > 0 ? `${formatMAD(li.totalHt)} ${L.ht![lg]}` : L.tarif_sur_demande![lg];
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
    lignes.push(par((lg) => L.dossier_raccordement![lg].replace('{societe}', SOCIETE_CI)));
  }
  return lignes.length > 0 ? { titre: L.services!, lignes } : null;
}
