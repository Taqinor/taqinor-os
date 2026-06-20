/**
 * Régimes de la loi 82-21 (autoproduction d'énergie électrique),
 * décret d'application 2-25-100 — en vigueur depuis le 9 juin 2026.
 *
 *  - déclaration : < 11 kW en basse tension, ou installation non raccordée
 *    au réseau (site isolé) ;
 *  - accord de raccordement : du seuil de déclaration jusqu'à 5 MW (BT/MT) ;
 *  - autorisation : ≥ 5 MW (MT/HT/THT).
 */
export type Voltage = 'BT' | 'MT' | 'HT';
export type RegimeId = 'declaration' | 'accord' | 'autorisation';

export interface RegimeInput {
  powerKw: number;
  gridConnected: boolean;
  voltage: Voltage;
}

export const AUTORISATION_THRESHOLD_KW = 5000; // 5 MW
export const DECLARATION_BT_MAX_KW = 11;

export function determineRegime(input: RegimeInput): RegimeId {
  if (!input.gridConnected) return 'declaration';
  if (input.powerKw >= AUTORISATION_THRESHOLD_KW) return 'autorisation';
  if (input.voltage === 'BT' && input.powerKw < DECLARATION_BT_MAX_KW) return 'declaration';
  return 'accord';
}

export interface RegimeInfo {
  id: RegimeId;
  title: string;
  summary: string;
  obligations: string[];
}

export const REGIMES: Record<RegimeId, RegimeInfo> = {
  declaration: {
    id: 'declaration',
    title: 'Régime de déclaration',
    summary:
      'Installations de moins de 11 kW raccordées en basse tension, ou installations non raccordées au réseau (sites isolés). Une déclaration préalable suffit.',
    obligations: [
      'Déposer une déclaration avant la mise en service',
      'Respecter les prescriptions techniques de raccordement (si raccordé)',
      'Conserver l’accusé de dépôt de la déclaration',
    ],
  },
  accord: {
    id: 'accord',
    title: 'Régime de l’accord de raccordement',
    summary:
      'Installations raccordées au réseau, du seuil de déclaration jusqu’à 5 MW, en basse ou moyenne tension. Un accord de raccordement avec le gestionnaire de réseau est requis avant la mise en service.',
    obligations: [
      'Obtenir l’accord de raccordement du gestionnaire de réseau avant mise en service',
      'Installer un dispositif de comptage conforme',
      'Respecter les conditions techniques de l’accord (puissance injectée, protections)',
    ],
  },
  autorisation: {
    id: 'autorisation',
    title: 'Régime d’autorisation',
    summary:
      'Installations de 5 MW et plus, raccordées en moyenne, haute ou très haute tension. Une autorisation préalable est exigée.',
    obligations: [
      'Obtenir l’autorisation avant tout démarrage des travaux',
      'Constituer un dossier technique complet (étude de raccordement, schémas, conformité)',
      'Se conformer au suivi et au contrôle de l’ANRE',
    ],
  },
};

// ───────────────────────────────────────────────────────────────────────────
// i18n (W67) — copies localisées EN/AR des régimes, additives. Le FR reste
// la source `REGIMES` ci-dessus (importée telle quelle par regime.test.ts).
// Les FAITS de droit sont IDENTIQUES dans toutes les langues : seuils (< 11 kW
// BT, jusqu'à 5 MW, ≥ 5 MW), ANRE, loi 82-21, décret 2-25-100. Seul le texte
// est traduit ; aucun chiffre n'est inventé ni modifié.
// ───────────────────────────────────────────────────────────────────────────
import type { Locale } from '../i18n/config';

const REGIMES_EN: Record<RegimeId, RegimeInfo> = {
  declaration: {
    id: 'declaration',
    title: 'Declaration regime',
    summary:
      'Installations under 11 kW connected at low voltage, or installations not connected to the grid (off-grid sites). A prior declaration is enough.',
    obligations: [
      'File a declaration before commissioning',
      'Meet the technical connection requirements (if grid-connected)',
      'Keep the declaration filing receipt',
    ],
  },
  accord: {
    id: 'accord',
    title: 'Connection-agreement regime',
    summary:
      'Grid-connected installations, from the declaration threshold up to 5 MW, at low or medium voltage. A connection agreement with the grid operator is required before commissioning.',
    obligations: [
      'Obtain the grid operator’s connection agreement before commissioning',
      'Install a compliant metering device',
      'Comply with the technical terms of the agreement (injected power, protections)',
    ],
  },
  autorisation: {
    id: 'autorisation',
    title: 'Authorization regime',
    summary:
      'Installations of 5 MW and above, connected at medium, high or very high voltage. A prior authorization is required.',
    obligations: [
      'Obtain the authorization before any works begin',
      'Compile a complete technical file (connection study, diagrams, compliance)',
      'Comply with ANRE monitoring and oversight',
    ],
  },
};

const REGIMES_AR: Record<RegimeId, RegimeInfo> = {
  declaration: {
    id: 'declaration',
    title: 'نظام التصريح',
    summary:
      'تركيبات أقل من 11 كيلوواط موصولة بالجهد المنخفض، أو تركيبات غير موصولة بالشبكة (مواقع معزولة). يكفي تصريح مسبق.',
    obligations: [
      'إيداع تصريح قبل وضع التركيبة قيد الخدمة',
      'احترام المواصفات التقنية للربط (في حال الربط بالشبكة)',
      'الاحتفاظ بوصل إيداع التصريح',
    ],
  },
  accord: {
    id: 'accord',
    title: 'نظام اتفاق الربط',
    summary:
      'تركيبات موصولة بالشبكة، من عتبة التصريح إلى غاية 5 ميغاواط، بالجهد المنخفض أو المتوسط. يلزم اتفاق ربط مع مدبّر الشبكة قبل وضعها قيد الخدمة.',
    obligations: [
      'الحصول على اتفاق الربط من مدبّر الشبكة قبل وضعها قيد الخدمة',
      'تركيب جهاز عدّ مطابق',
      'احترام الشروط التقنية للاتفاق (الاستطاعة المحقونة، الحمايات)',
    ],
  },
  autorisation: {
    id: 'autorisation',
    title: 'نظام الترخيص',
    summary:
      'تركيبات تبلغ 5 ميغاواط فما فوق، موصولة بالجهد المتوسط أو العالي أو العالي جداً. يُشترط ترخيص مسبق.',
    obligations: [
      'الحصول على الترخيص قبل أي انطلاق للأشغال',
      'تكوين ملف تقني كامل (دراسة الربط، التصاميم، المطابقة)',
      'الامتثال لمتابعة ومراقبة الهيئة الوطنية لضبط الكهرباء (ANRE)',
    ],
  },
};

/** Régimes par locale (FR = la source `REGIMES`, inchangée). */
export const REGIMES_BY_LOCALE: Record<Locale, Record<RegimeId, RegimeInfo>> = {
  fr: REGIMES,
  en: REGIMES_EN,
  ar: REGIMES_AR,
};

/** Régimes pour une locale, avec repli sur le FR. */
export const regimesFor = (locale: Locale): Record<RegimeId, RegimeInfo> =>
  REGIMES_BY_LOCALE[locale] ?? REGIMES;
