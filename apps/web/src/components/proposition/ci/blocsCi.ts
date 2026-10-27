/**
 * CPRW (27/10/2026) — blocs client C&I de /proposition qui reprennent les MÊMES mots que le PDF
 * (`quote_engine/i18n_labels.py`, `ci/blocs.py`). Aucun chiffre n'est calculé ici : tout est lu dans
 * `synthese_ci` (extracteur `syntheseCi.ts`) ; une valeur non servie est omise, jamais un « 0 ».
 */
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
