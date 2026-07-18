/**
 * WPROP2 — contenus ÉDITABLES des tiroirs de détail du tableau d'équipement
 * de la proposition (/proposition/<token>).
 *
 * LE fichier que le fondateur édite pour enrichir les deux lignes qui n'ont
 * pas de fiche produit /produits/<slug> :
 *   - « Tableau de protection AC/DC » — squelette de composition à compléter
 *     (chaque entrée `value: null` s'affiche « à préciser » tant qu'elle n'est
 *     pas renseignée — on n'invente jamais une spécification).
 *   - « Installation » — l'équipe qui pose, l'ingénieur qui supervise, la
 *     garantie d'installation 2 ans (canon des garanties du PDF).
 *
 * Trois langues par entrée (fr/en/ar) — même discipline i18n que la page.
 */

export interface DrawerLine {
  fr: string;
  en: string;
  ar: string;
  /** null → la ligne s'affiche avec la mention « à préciser » (fondateur). */
  value?: string | null;
}

export interface DrawerContent {
  title: DrawerLine;
  lines: DrawerLine[];
  footer?: DrawerLine;
}

/** Tiroir « Tableau de protection AC/DC » — composition à compléter. */
export const TABLEAU_ACDC_DRAWER: DrawerContent = {
  title: {
    fr: 'Ce que contient votre tableau de protection',
    en: 'What your protection panel contains',
    ar: 'ما يحتويه لوح الحماية الخاص بكم',
  },
  lines: [
    {
      fr: 'Disjoncteurs DC (côté panneaux)',
      en: 'DC breakers (panel side)',
      ar: 'قواطع التيار المستمر (جهة الألواح)',
      value: null,
    },
    {
      fr: 'Parafoudre DC/AC type 2',
      en: 'DC/AC type 2 surge protection',
      ar: 'مانعة صواعق للتيار المستمر/المتناوب من النوع 2',
      value: null,
    },
    {
      fr: 'Disjoncteur différentiel 30 mA (protection des personnes)',
      en: '30 mA residual-current breaker (people protection)',
      ar: 'قاطع تفاضلي 30 مللي أمبير (حماية الأشخاص)',
      value: null,
    },
    {
      fr: 'Disjoncteur AC de coupure générale',
      en: 'AC main breaker',
      ar: 'قاطع رئيسي للتيار المتناوب',
      value: null,
    },
  ],
  footer: {
    fr: 'Composition exacte détaillée par votre conseiller selon votre installation.',
    en: 'Exact composition detailed by your advisor for your installation.',
    ar: 'التركيبة الدقيقة يفصّلها مستشاركم حسب تركيبكم.',
  },
};

/** Tiroir « Installation » — l'équipe, l'ingénieur superviseur, la garantie. */
export const INSTALLATION_DRAWER: DrawerContent = {
  title: {
    fr: 'Une installation supervisée par un ingénieur',
    en: 'An engineer-supervised installation',
    ar: 'تركيب تحت إشراف مهندس',
  },
  lines: [
    {
      fr: 'Équipe d’installation TAQINOR formée et certifiée',
      en: 'Trained, certified TAQINOR installation team',
      ar: 'فريق تركيب TAQINOR مدرَّب ومعتمد',
    },
    {
      fr: 'Un ingénieur superviseur dédié à chaque chantier',
      en: 'A dedicated supervising engineer on every site',
      ar: 'مهندس مشرف مخصص لكل ورش',
    },
    {
      fr: 'Garantie d’installation TAQINOR : 2 ans',
      en: 'TAQINOR installation warranty: 2 years',
      ar: 'ضمان التركيب من TAQINOR: سنتان',
    },
    {
      fr: 'Mise en service, tests et formation à l’application de suivi inclus',
      en: 'Commissioning, tests and monitoring-app training included',
      ar: 'التشغيل والاختبارات والتدريب على تطبيق المتابعة مشمولة',
    },
  ],
  footer: {
    fr: 'Nos réalisations : taqinor.ma/realisations',
    en: 'Our installations: taqinor.ma/realisations',
    ar: 'إنجازاتنا: taqinor.ma/realisations',
  },
};

/** Libellé « à préciser » d'une valeur de squelette non renseignée. */
export const TO_SPECIFY: DrawerLine = {
  fr: 'à préciser',
  en: 'to be specified',
  ar: 'يُحدَّد لاحقاً',
};
