/**
 * WAUD73/74/75 — contenu des pages d'information « subvention », « kit ou sur mesure » et
 * « lire deux devis », rendues par components/InfoPageBody.astro (une seule coquille, jamais
 * recopiée dans trois pages × trois langues). Faits UNIQUEMENT déjà publiés ailleurs sur le site :
 * chiffres importés de leurs constantes sources, aucun montant propre à ces pages (RÈGLE C).
 */
import type { Locale } from '../i18n/config';
import { ANRE_TARIF_HORS_POINTE, ANRE_TARIF_POINTE } from './constants82_21';
import { DECLARATION_BT_MAX_KW } from './regime';
import { lignesGaranties, TABLEAU_GARANTIES_AR, TABLEAU_GARANTIES_FR } from './warranty';
import {
  ANRE_PERIODE_AR,
  ANRE_PERIODE_EN,
  ANRE_PERIODE_FR,
  FDA_PLAFOND_PAR_HA_DH,
  FDA_PLAFOND_PAR_KWC_DH,
  FDA_PLAFOND_PAR_PROJET_DH,
  FDA_SOURCE_AR,
  FDA_SOURCE_EN,
  FDA_SOURCE_FR,
  FDA_TAUX_PCT,
} from './subventionFacts';

export interface InfoBlock {
  h2: string;
  paras: string[];
  /** Tableau d'inclusions : en-têtes + lignes (texte brut). */
  table?: { head: string[]; rows: string[][] };
  source?: string;
  links?: { href: string; label: string }[];
}
export interface InfoPage {
  title: string;
  description: string;
  kicker: string;
  h1: string;
  lead: string;
  crumb: string;
  blocks: InfoBlock[];
}
export type InfoPageId = 'subvention' | 'kit' | 'devis';

const dh = (n: number, loc: string) => n.toLocaleString(loc);
const tarif = (n: number, loc: string) => n.toLocaleString(loc, { minimumFractionDigits: 2 });
const SEUIL = DECLARATION_BT_MAX_KW;

const fr = (n: number) => dh(n, 'fr-FR');
const en = (n: number) => dh(n, 'en-US');

const SUBVENTION: Partial<Record<Locale, InfoPage>> = {
  fr: {
    title: 'Subvention et aides pour panneaux solaires au Maroc : ce qui existe vraiment | Taqinor',
    description:
      'Existe-t-il une aide de l’État pour installer des panneaux solaires au Maroc ? Aucune pour un particulier ; la règle du Fonds de développement agricole pour le pompage ; le tarif d’excédent ANRE réservé à la moyenne et haute tension, avec sa période.',
    kicker: 'Aides et tarifs',
    h1: 'Subvention et aides pour panneaux solaires au Maroc',
    lead: 'Trois situations très différentes sont souvent mélangées. Voici ce qui existe, ce qui n’existe pas, et la source de chaque règle.',
    crumb: 'Subvention et aides',
    blocks: [
      {
        h2: 'Particulier : aucune aide spéciale',
        paras: [
          'Aucune subvention résidentielle spéciale n’existe pour une installation solaire de particulier au Maroc — méfiez-vous de toute promesse de ce type. Taqinor n’est ni prêteur ni organisme subventionneur.',
        ],
        links: [{ href: '/financement', label: 'Financement : ce que nous faisons et ne faisons pas' }],
      },
      {
        h2: 'Agriculture : la règle du Fonds de développement agricole (FDA)',
        paras: [
          `Aide de l’État au pompage solaire : ${FDA_TAUX_PCT} % de l’investissement, plafonnée à ${fr(FDA_PLAFOND_PAR_HA_DH)} DH par hectare, ${fr(FDA_PLAFOND_PAR_KWC_DH)} DH par kWc et ${fr(FDA_PLAFOND_PAR_PROJET_DH)} DH par projet. Conditions : remplacement d’une pompe au butane, irrigation localisée, compteur d’eau.`,
          'Accord préalable à obtenir avant travaux ; l’aide n’est pas déduite du prix et elle est versée après réalisation ; un seul projet par exploitation. Décision de la DPA/ORMVA, non garantie.',
        ],
        source: `Source : ${FDA_SOURCE_FR}.`,
        links: [{ href: '/pompage-solaire', label: 'Pompage solaire' }],
      },
      {
        h2: 'Moyenne et haute tension : le tarif d’excédent ANRE (ce n’est pas une subvention)',
        paras: [
          `La décision ANRE 04/26 fixe un tarif d’excédent de ${tarif(ANRE_TARIF_HORS_POINTE, 'fr-FR')} DH/kWh hors pointe et ${tarif(ANRE_TARIF_POINTE, 'fr-FR')} DH/kWh en pointe, hors taxes, pour la période du ${ANRE_PERIODE_FR}, indexé.`,
          'Il rémunère le surplus injecté en moyenne, haute et très haute tension seulement ; en basse tension, aucune revente du surplus n’est ouverte.',
        ],
        links: [{ href: '/loi-82-21', label: 'Loi 82-21 : quel régime pour votre installation ?' }],
      },
    ],
  },
  en: {
    title: 'Solar panel subsidies and aid in Morocco: what actually exists | Taqinor',
    description:
      'Is there state aid for installing solar panels in Morocco? None for households; the Agricultural Development Fund rule for pumping; the ANRE surplus tariff reserved for medium and high voltage, with its period.',
    kicker: 'Aid and tariffs',
    h1: 'Solar panel subsidies and aid in Morocco',
    lead: 'Three very different situations are often mixed up. Here is what exists, what does not, and the source of each rule.',
    crumb: 'Subsidies and aid',
    blocks: [
      {
        h2: 'Households: no special aid',
        paras: [
          'No special residential subsidy exists for a household solar installation in Morocco — be wary of any such promise. Taqinor is neither a lender nor a subsidy body.',
        ],
        links: [{ href: '/financement', label: 'Financing: what we do and do not do' }],
      },
      {
        h2: 'Agriculture: the Agricultural Development Fund (FDA) rule',
        paras: [
          `State aid for solar pumping: ${FDA_TAUX_PCT}% of the investment, capped at ${en(FDA_PLAFOND_PAR_HA_DH)} DH per hectare, ${en(FDA_PLAFOND_PAR_KWC_DH)} DH per kWp and ${en(FDA_PLAFOND_PAR_PROJET_DH)} DH per project. Conditions: replacing a butane pump, drip irrigation, a water meter.`,
          'Prior approval is required before works; the aid is not deducted from the price and is paid after completion; one project per farm. Decided by the DPA/ORMVA, not guaranteed.',
        ],
        source: `Source: ${FDA_SOURCE_EN}.`,
        links: [{ href: '/pompage-solaire', label: 'Solar pumping' }],
      },
      {
        h2: 'Medium and high voltage: the ANRE surplus tariff (not a subsidy)',
        paras: [
          `ANRE decision 04/26 sets a surplus tariff of ${tarif(ANRE_TARIF_HORS_POINTE, 'en-US')} DH/kWh off-peak and ${tarif(ANRE_TARIF_POINTE, 'en-US')} DH/kWh at peak, excluding taxes, for the period ${ANRE_PERIODE_EN}, indexed.`,
          'It pays for surplus injected in medium, high and very high voltage only; in low voltage, no resale of surplus is open.',
        ],
        links: [{ href: '/loi-82-21', label: 'Law 82-21: which regime applies to your installation?' }],
      },
    ],
  },
  ar: {
    title: 'الدعم والمساعدات للألواح الشمسية بالمغرب: ما هو موجود فعلاً | Taqinor',
    description:
      'هل توجد مساعدة من الدولة لتركيب الألواح الشمسية بالمغرب؟ لا شيء للأفراد؛ قاعدة صندوق التنمية الفلاحية للضخ؛ وتعريفة الفائض لدى ANRE المخصّصة للتوتر المتوسط والعالي مع مدّتها.',
    kicker: 'المساعدات والتعريفات',
    h1: 'الدعم والمساعدات للألواح الشمسية بالمغرب',
    lead: 'كثيراً ما تُخلط ثلاث حالات مختلفة جداً. إليكم ما هو موجود وما ليس موجوداً، ومصدر كل قاعدة.',
    crumb: 'الدعم والمساعدات',
    blocks: [
      {
        h2: 'الأفراد: لا مساعدة خاصة',
        paras: [
          'لا يوجد أي دعم سكني خاص لتركيب الطاقة الشمسية لدى الأفراد بالمغرب — احذروا أي وعد من هذا النوع. تاكينور ليست مُقرِضاً ولا هيئة مانحة للدعم.',
        ],
        links: [{ href: '/financement', label: 'التمويل: ما نفعله وما لا نفعله' }],
      },
      {
        h2: 'الفلاحة: قاعدة صندوق التنمية الفلاحية (FDA)',
        paras: [
          `مساعدة الدولة للضخ الشمسي: ${FDA_TAUX_PCT} % من الاستثمار، بسقف ${en(FDA_PLAFOND_PAR_HA_DH)} درهم للهكتار و${en(FDA_PLAFOND_PAR_KWC_DH)} درهم لكل kWc و${en(FDA_PLAFOND_PAR_PROJET_DH)} درهم للمشروع. الشروط: استبدال مضخة البوتان، السقي الموضعي، عدّاد الماء.`,
          'موافقة مسبقة قبل الأشغال؛ المساعدة لا تُخصم من الثمن وتُصرف بعد الإنجاز؛ مشروع واحد لكل استغلالية. قرار المديرية الإقليمية للفلاحة/المكتب الجهوي للاستثمار الفلاحي، وهي غير مضمونة.',
        ],
        source: `المصدر: ${FDA_SOURCE_AR}.`,
        links: [{ href: '/pompage-solaire', label: 'الضخ الشمسي' }],
      },
      {
        h2: 'التوتر المتوسط والعالي: تعريفة الفائض لدى ANRE (ليست دعماً)',
        paras: [
          `يحدّد قرار ANRE 04/26 تعريفة للفائض قدرها ${tarif(ANRE_TARIF_HORS_POINTE, 'en-US')} درهم/kWh خارج الذروة و${tarif(ANRE_TARIF_POINTE, 'en-US')} درهم/kWh في الذروة، دون احتساب الرسوم، للفترة ${ANRE_PERIODE_AR}، مع الفهرسة.`,
          'تُؤدّى هذه التعريفة عن الفائض المحقون في التوتر المتوسط والعالي والعالي جداً فقط؛ وفي التوتر المنخفض لا يُفتح بيع الفائض.',
        ],
        links: [{ href: '/loi-82-21', label: 'القانون 82-21: أي نظام ينطبق على تركيبتك؟' }],
      },
    ],
  },
};

const KIT: Partial<Record<Locale, InfoPage>> = {
  fr: {
    title: 'Kit solaire ou installation sur mesure au Maroc : ce qu’un kit n’inclut pas | Taqinor',
    description:
      'Un kit solaire suffit-il ? Ce qu’un kit n’inclut généralement pas : protections AC/DC, structure adaptée au toit, démarche loi 82-21 selon la puissance, suivi de production.',
    kicker: 'Kit ou sur mesure',
    h1: 'Kit solaire ou installation sur mesure ?',
    lead: 'Un kit réunit du matériel ; une installation, c’est aussi ce qui l’entoure. Voici ce qu’il faut vérifier avant de choisir.',
    crumb: 'Kit solaire ou sur mesure',
    blocks: [
      {
        h2: 'Ce qu’un kit n’inclut en général pas',
        paras: [
          'Les protections côté courant continu et côté courant alternatif, à choisir selon l’installation réelle.',
          'La structure de fixation, qui dépend du type de toit (tuiles, tôle, terrasse) et de son état.',
          'Le suivi de la production, pour constater que l’installation tient ses promesses.',
        ],
      },
      {
        h2: 'La démarche loi 82-21 dépend de la puissance',
        paras: [
          `En basse tension, une installation de moins de ${SEUIL} kW relève du régime de déclaration ; à partir de ${SEUIL} kW (ou en moyenne tension), c’est un accord de raccordement. Un kit ne fait pas cette démarche à votre place.`,
        ],
        links: [{ href: '/loi-82-21', label: 'Identifier votre régime en 3 questions' }],
      },
      {
        h2: 'Et le prix ?',
        paras: ['Les ordres de grandeur sont sur la page prix ; le vrai chiffre vient toujours d’une visite technique.'],
        links: [
          { href: '/prix-panneaux-solaires-maroc', label: 'Prix des panneaux solaires au Maroc' },
          { href: '/ressources/10-questions-avant-de-signer', label: '10 questions avant de signer' },
        ],
      },
    ],
  },
};

const DEVIS_LIGNES_FR: string[][] = [
  ['Panneaux', 'Marque, modèle et puissance unitaire réels ; nombre de panneaux ; puissance totale en kWc'],
  ['Onduleur', 'Marque, type (réseau ou hybride) et puissance'],
  ['Structure de fixation', 'Matière et adaptation au type de toit'],
  ['Protections AC/DC', 'Présentes, listées, et pas seulement « câblage inclus »'],
  ['Déclaration loi 82-21', 'Qui la dépose, et selon quelle puissance'],
  ['Suivi de production', 'Application fournie, accès client'],
];
const DEVIS_LIGNES_AR: string[][] = [
  ['الألواح', 'العلامة والطراز والقدرة الفعلية للوحة؛ عدد الألواح؛ القدرة الإجمالية بالـ kWc'],
  ['العاكس', 'العلامة والنوع (شبكة أو هجين) والقدرة'],
  ['هيكل التثبيت', 'المادة وملاءمته لنوع السطح'],
  ['حمايات التيار المستمر والمتناوب', 'موجودة ومُفصَّلة، وليس مجرّد «الكابلات مشمولة»'],
  ['التصريح وفق القانون 82-21', 'من يودعه، وحسب أي قدرة'],
  ['مراقبة الإنتاج', 'تطبيق مُقدَّم، وولوج الزبون'],
];

const DEVIS: Partial<Record<Locale, InfoPage>> = {
  fr: {
    title: 'Devis de panneaux solaires au Maroc : lire et comparer deux devis | Taqinor',
    description:
      'Comment comparer deux devis solaires ligne à ligne : marque et puissance des panneaux, onduleur, structure, protections AC/DC, déclaration loi 82-21, suivi et garanties par composant.',
    kicker: 'Comparer deux devis',
    h1: 'Devis de panneaux solaires : lire et comparer deux devis',
    lead: 'Deux devis au même total peuvent ne pas contenir la même installation. Comparez-les ligne à ligne.',
    crumb: 'Lire et comparer deux devis',
    blocks: [
      {
        h2: 'Tableau d’inclusions',
        paras: ['Pour chaque ligne, le devis doit nommer précisément ce qui est fourni.'],
        table: { head: ['Ligne', 'Ce que le devis doit préciser'], rows: DEVIS_LIGNES_FR },
      },
      {
        h2: 'Garanties par composant',
        paras: ['Demandez la durée de garantie de chaque composant, pas une durée unique. Chez Taqinor :'],
        table: { head: ['Composant', 'Garantie'], rows: lignesGaranties(TABLEAU_GARANTIES_FR) },
      },
      {
        h2: 'Pour aller plus loin',
        paras: ['Les ordres de grandeur sont sur la page prix, et la checklist complète dans les 10 questions.'],
        links: [
          { href: '/prix-panneaux-solaires-maroc', label: 'Prix des panneaux solaires au Maroc' },
          { href: '/ressources/10-questions-avant-de-signer', label: '10 questions avant de signer' },
        ],
      },
    ],
  },
  ar: {
    title: 'عرض ثمن الألواح الشمسية بالمغرب: قراءة ومقارنة عرضين | Taqinor',
    description:
      'كيف تقارن عرضَي ثمن شمسيين سطراً بسطر: علامة وقدرة الألواح، العاكس، الهيكل، حمايات التيار المستمر والمتناوب، التصريح وفق القانون 82-21، المراقبة والضمانات لكل مكوّن.',
    kicker: 'مقارنة عرضين',
    h1: 'عرض ثمن الألواح الشمسية: قراءة ومقارنة عرضين',
    lead: 'قد يحمل عرضان بالمجموع نفسه تركيبتين مختلفتين. قارنوهما سطراً بسطر.',
    crumb: 'قراءة ومقارنة عرضين',
    blocks: [
      {
        h2: 'جدول المشمولات',
        paras: ['في كل سطر، يجب أن يسمّي العرض بدقة ما هو مُقدَّم.'],
        table: { head: ['السطر', 'ما يجب أن يوضّحه العرض'], rows: DEVIS_LIGNES_AR },
      },
      {
        h2: 'الضمانات لكل مكوّن',
        paras: ['اطلبوا مدة ضمان كل مكوّن، لا مدة واحدة. لدى تاكينور:'],
        table: { head: ['المكوّن', 'الضمان'], rows: lignesGaranties(TABLEAU_GARANTIES_AR) },
      },
      {
        h2: 'للمزيد',
        paras: ['الهوامش الاسترشادية في صفحة الأسعار، واللائحة الكاملة في الأسئلة العشرة.'],
        links: [
          { href: '/prix-panneaux-solaires-maroc', label: 'أسعار الألواح الشمسية بالمغرب' },
          { href: '/ressources/10-questions-avant-de-signer', label: '10 أسئلة قبل التوقيع' },
        ],
      },
    ],
  },
};

export const INFO_PAGES: Record<InfoPageId, Partial<Record<Locale, InfoPage>>> = {
  subvention: SUBVENTION,
  kit: KIT,
  devis: DEVIS,
};

/** Chemin racine de chaque page (FR), pour registre, llms.txt et tests. */
export const INFO_PAGE_PATHS: Record<InfoPageId, string> = {
  subvention: '/subvention-panneaux-solaires-maroc',
  kit: '/kit-solaire-maroc',
  devis: '/devis-panneaux-solaires-maroc',
};
