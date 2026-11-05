/**
 * WAUD87 — en-tête EN/AR des fiches techniques /produits (catégorie, marque, nom, modèle, résumé).
 * Traduction de ce que dit la fiche française (lib/fiches.ts) — aucune spécification ajoutée ; le
 * corps détaillé (caractéristiques, normes, FAQ, garantie) reste en français et la page EN/AR y
 * renvoie explicitement (repli FR). Arabe non relu par un arabophone (DONE LOG WAUD87).
 * Une fiche ajoutée à FICHES sans entrée ici fait échouer tests/i18n-components.test.ts.
 */
import type { FicheCategorie } from './fiches';

export type LocaleFiche = 'en' | 'ar';

export interface EnTeteFiche {
  nom: string;
  /** Absent : la marque (nom propre) est affichée telle quelle. */
  marque?: string;
  /** Absent : la référence constructeur est affichée telle quelle. */
  modele?: string;
  resume: string;
}

export const CATEGORIES_FICHE: Record<FicheCategorie, Record<LocaleFiche, string>> = {
  'Panneaux photovoltaïques': { en: 'Solar panels', ar: 'الألواح الشمسية' },
  'Onduleurs réseau': { en: 'Grid-tied inverters', ar: 'عاكسات الربط بالشبكة' },
  'Onduleurs hybrides': { en: 'Hybrid inverters', ar: 'العاكسات الهجينة' },
  Batteries: { en: 'Batteries', ar: 'البطاريات' },
  'Structure & pose': { en: 'Mounting & installation', ar: 'الهيكل والتركيب' },
  'Protection & câblage': { en: 'Protection & cabling', ar: 'الحماية والأسلاك' },
  'Supervision & comptage': { en: 'Monitoring & metering', ar: 'المراقبة والعدّ' },
  'Grands projets': { en: 'Large projects', ar: 'المشاريع الكبرى' },
};

const GENERIQUE = { en: 'Generic item', ar: 'بند عام' } as const;

export const EN_TETES_FICHE: Record<string, Record<LocaleFiche, EnTeteFiche>> = {
  'canadian-solar-710': {
    en: {
      nom: 'Canadian Solar 710 Wc panel',
      resume: 'Bifacial N-type TOPCon module: it also captures the light reflected by the roof — output gained without extra surface.',
    },
    ar: {
      nom: 'لوح Canadian Solar بقدرة 710 Wc',
      resume: 'وحدة ثنائية الوجه من نوع N بتقنية TOPCon: تلتقط أيضاً الضوء المنعكس عن السطح، فتكسب مردوداً دون مساحة إضافية.',
    },
  },
  'jinko-710': {
    en: {
      nom: 'Jinko 710 Wc panel',
      resume: 'The Tiger Neo N-type cell goes after output rather than surface — useful when roof space is limited.',
    },
    ar: {
      nom: 'لوح Jinko بقدرة 710 Wc',
      resume: 'خلية Tiger Neo من نوع N تبحث عن المردود بدل المساحة — مفيدة حين تكون مساحة السطح محدودة.',
    },
  },
  'onduleur-huawei-reseau': {
    en: {
      nom: 'Huawei SUN2000 grid-tied inverter',
      modele: 'SUN2000 (string series)',
      resume: 'Pure string inverter when the study does not include a battery: it optimises string by string, so one shaded panel no longer drags down the whole row.',
    },
    ar: {
      nom: 'عاكس الربط بالشبكة Huawei SUN2000',
      modele: 'SUN2000 (سلسلة string)',
      resume: 'عاكس string خالص حين لا تعتمد الدراسة بطارية: يحسّن الأداء سلسلةً بسلسلة، فلا يعود لوح واحد في الظل يُضعف الصف كله.',
    },
  },
  'onduleur-deye-hybride': {
    en: {
      nom: 'Deye hybrid inverter',
      resume: 'The conductor of the installation: it arbitrates in real time between panels, battery and grid.',
    },
    ar: {
      nom: 'العاكس الهجين Deye',
      resume: 'قائد التركيبة: يوزّع في الوقت الفعلي بين الألواح والبطارية والشبكة.',
    },
  },
  'batterie-dyness': {
    en: {
      nom: 'Dyness DL5.0C battery',
      resume: 'Lithium iron phosphate does not go into thermal runaway: the safe choice for storage at home.',
    },
    ar: {
      nom: 'بطارية Dyness DL5.0C',
      resume: 'فوسفات الحديد والليثيوم لا ينفلت حرارياً: خيار الأمان للتخزين في المنزل.',
    },
  },
  'structure-fixation': {
    en: {
      nom: 'Mounting structure',
      marque: GENERIQUE.en,
      modele: 'Bolted triangles in perforated galvanised 41 × 41 mm C-profile',
      resume: 'What holds your panels through thirty years of wind, sun and rain — a triangle assembled on site at every panel joint.',
    },
    ar: {
      nom: 'هيكل التثبيت',
      marque: GENERIQUE.ar,
      modele: 'مثلثات مثبتة بالبراغي من مقطع C مجلفن ومثقّب 41 × 41 مم',
      resume: 'ما يحمل ألواحك طوال ثلاثين سنة من الرياح والشمس والمطر — مثلث يُجمَّع في الموقع عند كل وصلة بين الألواح.',
    },
  },
  'socles-lestage': {
    en: {
      nom: 'Ballast blocks',
      marque: GENERIQUE.en,
      modele: 'Precast concrete blocks — installation without drilling',
      resume: 'The only part laid directly on your roof slab: it holds the installation by its weight, without a single hole drilled in the waterproofing.',
    },
    ar: {
      nom: 'قواعد التثقيل',
      marque: GENERIQUE.ar,
      modele: 'كتل خرسانية مسبقة الصنع — تركيب دون ثقب',
      resume: 'القطعة الوحيدة الموضوعة مباشرة على سطحك: تثبّت التركيبة بوزنها، دون ثقب واحد في طبقة العزل المائي.',
    },
  },
  'protection-dc': {
    en: {
      nom: 'DC protection (panel side)',
      marque: GENERIQUE.en,
      modele: 'DC enclosure — composition set by the study',
      resume: 'Between your panels and the inverter flows a direct current that does not switch itself off: this enclosure is the only way to cut it and absorb it.',
    },
    ar: {
      nom: 'حماية التيار المستمر (جهة الألواح)',
      marque: GENERIQUE.ar,
      modele: 'علبة DC — تكوينها حسب الدراسة',
      resume: 'بين ألواحك والعاكس يمرّ تيار مستمر لا ينقطع من تلقاء نفسه: هذه العلبة هي الوسيلة الوحيدة لقطعه وامتصاصه.',
    },
  },
  'protection-ac': {
    en: {
      nom: 'AC protection (grid side)',
      marque: GENERIQUE.en,
      modele: 'AC enclosure — composition set by the study',
      resume: 'Between the inverter and your distribution board, the device that protects people and the building — and lets you disconnect the installation from the grid.',
    },
    ar: {
      nom: 'حماية التيار المتردد (جهة الشبكة)',
      marque: GENERIQUE.ar,
      modele: 'علبة AC — تكوينها حسب الدراسة',
      resume: 'بين العاكس ولوحة التوزيع، الجهاز الذي يحمي الأشخاص والمبنى — ويتيح فصل التركيبة عن الشبكة.',
    },
  },
  cablage: {
    en: {
      nom: 'Cabling',
      marque: GENERIQUE.en,
      modele: 'H1Z2Z2-K solar cable · original connectors — cross-sections set by the study',
      resume: 'The least talked-about line of the quote, and the one that decides how everything else holds up: what connects the panels to the inverter stays in full sun for the whole life of the installation.',
    },
    ar: {
      nom: 'الأسلاك',
      marque: GENERIQUE.ar,
      modele: 'كابل شمسي H1Z2Z2-K · موصلات أصلية — المقاطع حسب الدراسة',
      resume: 'أقل سطر يُتحدّث عنه في عرض السعر، وهو الذي يحدد صمود كل ما عداه: ما يربط الألواح بالعاكس يبقى تحت الشمس طوال عمر التركيبة.',
    },
  },
  'accessoires-pose': {
    en: {
      nom: 'Installation accessories',
      marque: GENERIQUE.en,
      modele: 'Cable routing · cable glands · earthing',
      resume: 'Everything that makes an installation age well rather than badly: the cable is guided, the entries are sealed, the metal parts are earthed.',
    },
    ar: {
      nom: 'ملحقات التركيب',
      marque: GENERIQUE.ar,
      modele: 'مسارات الكابلات · سدادات الكابلات · التأريض',
      resume: 'كل ما يجعل التركيبة تشيخ جيداً لا سيئاً: الكابل موجَّه، والمداخل محكمة، والأجزاء المعدنية موصولة بالأرض.',
    },
  },
  'poste-mt-raccordement': {
    en: {
      nom: 'MV substation and grid connection',
      marque: GENERIQUE.en,
      modele: 'HTA delivery substation — composition set by the study and the distributor’s requirements',
      resume: 'Above a certain power, you no longer connect to the distribution board: you connect to the medium-voltage grid, with a substation and a contract.',
    },
    ar: {
      nom: 'محطة الجهد المتوسط والربط',
      marque: GENERIQUE.ar,
      modele: 'محطة تسليم HTA — تكوينها حسب الدراسة ومتطلبات الموزّع',
      resume: 'فوق قدرة معيّنة، لا يعود الربط بلوحة التوزيع: بل بشبكة الجهد المتوسط، بمحطة وعقد.',
    },
  },
  'supervision-comptage': {
    en: {
      nom: 'Monitoring and metering (large projects)',
      marque: GENERIQUE.en,
      modele: 'Production metering · data acquisition · monitoring — architecture set by the study',
      resume: 'On a large installation, production is not an impression: it is a measurement, enforceable, on which the contract and the financing rest.',
    },
    ar: {
      nom: 'المراقبة والعدّ (المشاريع الكبرى)',
      marque: GENERIQUE.ar,
      modele: 'عدّ الإنتاج · اقتناء البيانات · المراقبة — البنية حسب الدراسة',
      resume: 'في تركيبة كبيرة، الإنتاج ليس انطباعاً: إنه قياس يُحتجّ به، يقوم عليه العقد والتمويل.',
    },
  },
  'structures-grandes-installations': {
    en: {
      nom: 'Structures for large installations',
      marque: GENERIQUE.en,
      modele: 'Industrial roof, carport or ground mount — system set by the study',
      resume: 'At the scale of an industrial roof, a carport or a ground-mounted field, the structure becomes a civil-engineering work — with its calculation note and its acceptance.',
    },
    ar: {
      nom: 'هياكل التركيبات الكبرى',
      marque: GENERIQUE.ar,
      modele: 'سطح صناعي أو مظلة أو تركيب أرضي — النظام حسب الدراسة',
      resume: 'على مستوى سطح صناعي أو مظلة أو حقل أرضي، يصبح الهيكل منشأة هندسة مدنية — بمذكرة حسابها ومحضر استلامها.',
    },
  },
  'smart-meter-huawei': {
    en: {
      nom: 'Huawei Smart Meter',
      resume: 'The smart meter measures the flows in both directions — the basis for honest self-consumption control.',
    },
    ar: {
      nom: 'العداد الذكي Huawei',
      resume: 'يقيس العداد الذكي التدفقات في الاتجاهين — أساس تحكّم نزيه في الاستهلاك الذاتي.',
    },
  },
  'wifi-dongle-huawei': {
    en: {
      nom: 'Huawei WiFi dongle',
      resume: 'An installation that is not measured is an installation taken on trust: this dongle links the roof to online monitoring.',
    },
    ar: {
      nom: 'مفتاح WiFi من Huawei',
      resume: 'تركيبة لا تُقاس هي تركيبة نصدّقها على كلمتها: هذا المفتاح يربط السطح بالمتابعة عبر الإنترنت.',
    },
  },
};

/** En-tête localisé d'une fiche (repli : les champs français, qui restent des noms propres). */
export function enTeteFiche(
  f: { slug: string; nom: string; marque: string; modele: string; categorie: FicheCategorie; resume: string },
  locale: LocaleFiche,
) {
  const t = EN_TETES_FICHE[f.slug]?.[locale];
  return {
    categorie: CATEGORIES_FICHE[f.categorie]?.[locale] ?? f.categorie,
    nom: t?.nom ?? f.nom,
    marque: t?.marque ?? f.marque,
    modele: t?.modele ?? f.modele,
    resume: t?.resume ?? f.resume,
  };
}
