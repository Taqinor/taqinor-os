/**
 * AGQ33/AGQ35 — le contenu AGRICOLE de la page /proposition qui ne dépend de
 * rien : étapes sans délai (D-AGQ-11), FAQ du fermier (C-AGQ-031), libellés
 * jumeaux du PDF. `proposition.ts` (fichier-mur, C20) l'importe ; ce module
 * n'importe de lui que des TYPES — aucun cycle à l'exécution.
 */
import type { FaqItem, Lbl3, NextStep } from './proposition';

/** AGQ38/AGQ35 — une note client servie (`{code, textes}`), jamais recalculée. */
export interface SyntheseNote {
  code: string | null;
  textes: Lbl3;
}

/** AGQ30/AGQ33 — une étape agricole servie (`{cle, textes}`) : jamais de délai. */
export interface SyntheseEtape {
  cle: string | null;
  textes: Lbl3;
}

/**
 * AGQ33 (D-AGQ-11) — les 5 étapes agricoles, textes IDENTIQUES à
 * `quote_engine/agricole/mentions.py::_ETAPES` (parité testée contre le contrat).
 * Aucun jour, aucune heure : un chantier de pompage se cale sur la visite du
 * point d'eau et l'accord FDA, jamais sur un délai promis.
 */
export const ETAPES_AGRICOLES: ReadonlyArray<{ cle: string; textes: Lbl3 }> = [
  {
    cle: 'visite_point_eau',
    textes: {
      fr: "Visite du point d'eau : niveau, débit du forage et HMT relevés sur place.",
      en: 'Water point visit: level, borehole flow and head measured on site.',
      ar: 'زيارة نقطة الماء: قياس المستوى وصبيب الثقب والارتفاع في عين المكان.',
    },
  },
  {
    cle: 'accord_fda',
    textes: {
      fr: "Accord FDA, si vous demandez l'aide : dossier déposé avant toute commande.",
      en: 'FDA approval, if you apply for the subsidy: file submitted before any order.',
      ar: 'موافقة صندوق التنمية الفلاحية، إن طلبتم الدعم: يودع الملف قبل أي طلب.',
    },
  },
  {
    cle: 'commande',
    textes: {
      fr: 'Commande : acompte versé, matériel commandé.',
      en: 'Order: down payment made, equipment ordered.',
      ar: 'الطلب: أداء الدفعة المقدمة وطلب المعدات.',
    },
  },
  {
    cle: 'pose',
    textes: {
      fr: 'Pose : pompe, variateur, champ solaire et protections.',
      en: 'Installation: pump, drive, solar array and protections.',
      ar: 'التركيب: المضخة والمغير والحقل الشمسي والحمايات.',
    },
  },
  {
    cle: 'mise_en_service',
    textes: {
      fr: 'À la mise en service : débit et HMT mesurés, écart affiché contre ce devis.',
      en: 'At commissioning: flow and head measured, gap shown against this quote.',
      ar: 'عند التشغيل: قياس الصبيب والارتفاع، وإظهار الفرق مقارنة بهذا العرض.',
    },
  },
];

/** « Visite du point d'eau : niveau… » → titre « Visite du point d'eau », corps « niveau… ». */
function titreEtCorps(texte: string): [string, string] {
  const i = texte.indexOf(':');
  if (i <= 0) return [texte, texte];
  return [texte.slice(0, i).trim(), texte.slice(i + 1).trim()];
}

export function etapesAgricole(servies?: ReadonlyArray<SyntheseEtape> | null): NextStep[] {
  const source: ReadonlyArray<SyntheseEtape> = servies && servies.length > 0 ? servies : ETAPES_AGRICOLES;
  return source.map((e, i) => {
    const [title, body] = titreEtCorps(e.textes.fr);
    const [titleEn, bodyEn] = titreEtCorps(e.textes.en);
    const [titleAr, bodyAr] = titreEtCorps(e.textes.ar);
    return { id: e.cle ?? `etape-${i + 1}`, title, titleAr, titleEn, body, bodyAr, bodyEn };
  });
}

/**
 * AGQ33 (C-AGQ-031) — les objections d'un fermier (plus celles d'un toit) :
 * puits à sec, jours nuageux, vol, entretien, délai FDA. Aucun chiffre, aucune
 * promesse datée : chaque réponse renvoie au document (débit mesuré, FDA avant
 * commande).
 */
export function objectionFaqAgricole(): FaqItem[] {
  return [
    {
      id: 'puits-sec',
      question: 'Et si le puits ou le forage donne moins que prévu ?',
      questionAr: 'وماذا لو أعطى البئر أو الثقب أقل مما هو متوقع؟',
      questionEn: 'What if the well or borehole yields less than expected?',
      answer: "Le débit du forage est relevé sur place avant le devis définitif et la pompe est choisie en dessous de ce débit. À la mise en service, le débit réel est mesuré et l'écart avec le devis est écrit.",
      answerAr: 'يُقاس صبيب الثقب في عين المكان قبل العرض النهائي وتُختار المضخة دون هذا الصبيب. عند التشغيل يُقاس الصبيب الحقيقي ويُكتب الفرق مع العرض.',
      answerEn: 'The borehole flow is measured on site before the final quote and the pump is chosen below that flow. At commissioning, the real flow is measured and the gap against the quote is written down.',
    },
    {
      id: 'nuages',
      question: 'Que se passe-t-il les jours nuageux ?',
      questionAr: 'ماذا يحدث في الأيام الغائمة؟',
      questionEn: 'What happens on cloudy days?',
      answer: "La pompe tourne moins vite et livre moins d'eau ce jour-là ; le document montre l'eau livrée mois par mois sur l'ensoleillement réel du site, pas sur une journée idéale. Un bassin de stockage lisse ces journées.",
      answerAr: 'تدور المضخة أبطأ وتضخ ماءً أقل في ذلك اليوم؛ يعرض المستند الماء المضخوخ شهراً بشهر وفق الإشعاع الحقيقي للموقع، لا وفق يوم مثالي. حوض التخزين يعوض هذه الأيام.',
      answerEn: 'The pump runs slower and delivers less water that day; the document shows the water delivered month by month on the site’s real sunshine, not an ideal day. A storage basin smooths those days out.',
    },
    {
      id: 'vol',
      question: 'Les panneaux peuvent-ils être volés ?',
      questionAr: 'هل يمكن أن تُسرق الألواح؟',
      questionEn: 'Can the panels be stolen?',
      answer: "Les panneaux sont fixés sur une structure au sol ; des fixations antivol et une clôture du champ sont proposées en option dans ce devis, le gardiennage reste de votre côté. Le choix d'une assurance se fait avec votre assureur.",
      answerAr: 'تُثبت الألواح على هيكل أرضي؛ وتُقترح في هذا العرض تثبيتات مضادة للسرقة وسياج للحقل كخيارات، أما الحراسة فتبقى على عاتقكم. اختيار التأمين يتم مع شركة التأمين.',
      answerEn: 'The panels are fixed on a ground structure; anti-theft fasteners and a field fence are offered as options in this quote, guarding remains on your side. Insurance is a decision to take with your insurer.',
    },
    {
      id: 'entretien-pompage',
      question: 'Quel entretien demande une pompe solaire ?',
      questionAr: 'ما الصيانة التي تتطلبها مضخة شمسية؟',
      questionEn: 'What maintenance does a solar pump need?',
      answer: "Nettoyer les panneaux après les vents de sable, vérifier le filtre et la crépine, et faire contrôler la pompe et le variateur chaque année. Il n'y a ni carburant à acheter ni moteur à vidanger.",
      answerAr: 'تنظيف الألواح بعد الرياح الرملية، وفحص المرشح والمصفاة، ومراقبة المضخة والمغير كل سنة. لا وقود يُشترى ولا محرك يحتاج تغيير الزيت.',
      answerEn: 'Clean the panels after sandstorms, check the filter and strainer, and have the pump and drive inspected every year. There is no fuel to buy and no engine to service.',
    },
    {
      id: 'delai-fda',
      question: "Faut-il attendre l'accord FDA avant de commencer ?",
      questionAr: 'هل يجب انتظار موافقة صندوق التنمية الفلاحية قبل البدء؟',
      questionEn: 'Do we have to wait for the FDA approval before starting?',
      answer: "Oui si vous demandez l'aide : le dossier est déposé et l'accord obtenu avant toute commande, sinon l'aide est perdue. Si vous ne demandez pas l'aide, la commande peut partir dès l'acompte.",
      answerAr: 'نعم إن طلبتم الدعم: يودع الملف وتُحصل الموافقة قبل أي طلب، وإلا ضاع الدعم. وإن لم تطلبوا الدعم فيمكن أن ينطلق الطلب بمجرد الدفعة المقدمة.',
      answerEn: 'Yes if you apply for the subsidy: the file is submitted and the approval obtained before any order, otherwise the subsidy is lost. If you do not apply, the order can start as soon as the down payment is made.',
    },
  ];
}

/** AGQ33/AGQ35 — libellés de la page agricole, mêmes textes que le PDF (`i18n_labels.py`). */
export const AGR_LBL_AGQ = {
  // AGQ3/AGQ33 — même phrase que la page 2 du PDF (`agr_mois_sous_tolerance`, `agr_mois_couverture`).
  moisSousTolerance: { fr: 'Mois sous la tolérance de conception :', en: 'Months below the design tolerance:', ar: 'أشهر دون هامش التصميم:' },
  couverture: { fr: '{mois} : {pct} % de votre besoin', en: '{mois}: {pct} % of your need', ar: '{mois}: {pct} % من حاجتكم' },
  // AGQ11/AGQ35 — option sans prix (`agr_prix_sur_devis`), notes du noyau (`agr_notes_titre`).
  prixSurDevis: { fr: 'prix sur devis', en: 'price on request', ar: 'السعر حسب العرض' },
  notesTitre: { fr: 'Notes de dimensionnement', en: 'Sizing notes', ar: 'ملاحظات التحجيم' },
  coutM3Solaire: { fr: 'Coût du m³ avec le solaire', en: 'Cost per m³ with solar', ar: 'تكلفة المتر المكعب مع الطاقة الشمسية' },
  // AGQ42 — la page d'un pompage parle d'eau, pas de toit.
  eauJour: { fr: 'm³ d’eau par jour', en: 'm³ of water per day', ar: 'م³ من الماء يومياً' },
  kitTitre: { fr: 'Votre kit de pompage solaire', en: 'Your solar pumping kit', ar: 'عدة الضخ الشمسي الخاصة بكم' },
  revisionEau: { fr: 'Ajuster le volume d’eau ou la pompe', en: 'Adjust the water volume or the pump', ar: 'تعديل كمية الماء أو المضخة' },
  etEnsuite: { fr: 'Et ensuite : accord FDA si vous demandez l’aide, commande, pose, mise en service', en: 'And then: FDA approval if you apply for the grant, order, installation, commissioning', ar: 'ثم: موافقة صندوق التنمية الفلاحية إن طلبتم الدعم، الطلبية، التركيب، التشغيل' },
  hypotheses: { fr: 'Chaque chiffre est étudié sur vos propres données — point d’eau, besoin en eau, énergie actuelle —, pas promis.', en: 'Every figure is studied from your own data — water source, water need, current energy — not promised.', ar: 'كل رقم مدروس انطلاقاً من معطياتكم — نقطة الماء، الحاجة إلى الماء، الطاقة الحالية — وليس وعداً.' },
} as const satisfies Record<string, Lbl3>;

/** Rejeu live AGQ41 — libellés des options du kit listées dans « Non inclus » (clés servies par
 *  `synthese_agricole.non_inclus`, AGQ11) : MÊMES textes que le PDF (`i18n_labels.agr_option_<clé>`). */
const AGR_OPTIONS_NON_INCLUS_LBL: Record<string, Lbl3> = {
  protection_dc: { fr: "Protections DC/AC", en: "DC/AC protection devices", ar: "حمايات التيار المستمر والمتناوب" },
  sonde_niveau: { fr: "Sonde de niveau (marche à sec)", en: "Level probe (dry-run protection)", ar: "مسبار المستوى (الحماية من التشغيل الجاف)" },
  compteur_eau: { fr: "Compteur d'eau", en: "Water meter", ar: "عداد الماء" },
  cable_descente: { fr: "Câble de descente", en: "Drop cable", ar: "كابل النزول" },
  colonne_refoulement: { fr: "Colonne de refoulement", en: "Rising main", ar: "أنبوب الدفع" },
  clapet: { fr: "Clapet anti-retour", en: "Non-return valve", ar: "صمام عدم الرجوع" },
  tuyauterie: { fr: "Tuyauterie", en: "Pipework", ar: "الأنابيب" },
  bassin: { fr: "Bassin", en: "Storage tank", ar: "الحوض" },
  entretien_pompage: { fr: "Contrat d'entretien", en: "Maintenance contract", ar: "عقد الصيانة" },
  antivol: { fr: "Fixations antivol", en: "Anti-theft fixings", ar: "تثبيتات مضادة للسرقة" },
  cloture: { fr: "Clôture du champ", en: "Array fence", ar: "سياج الحقل" },
  afficheur_variateur: { fr: "Afficheur du variateur", en: "Drive display", ar: "شاشة المغير" },
};

/** AGW304 — « Non inclus » : forage, génie civil et chaque option du kit (jamais une clé brute). */
export const AGR_NON_INCLUS_LBL: Record<string, Lbl3> = {
  forage: { fr: 'le forage', en: 'the borehole', ar: 'الثقب' },
  genie_civil: { fr: 'le génie civil', en: 'civil works', ar: 'الهندسة المدنية' },
  ...AGR_OPTIONS_NON_INCLUS_LBL,
};

/** Rejeu AGQ41 — unité d'une entrée de provenance (mêmes unités que le PDF, `_UNITE_ENTREE`). */
const UNITE_ENTREE: Record<string, Lbl3> = {
  volume_m3_jour: { fr: 'm³/j', en: 'm³/day', ar: 'م³/يوم' },
  niveau_statique_m: { fr: 'm', en: 'm', ar: 'م' },
  niveau_dynamique_m: { fr: 'm', en: 'm', ar: 'م' },
  profondeur_forage_m: { fr: 'm', en: 'm', ar: 'م' },
  hmt_m: { fr: 'm', en: 'm', ar: 'م' },
  debit_exploitation_m3h: { fr: 'm³/h', en: 'm³/h', ar: 'م³/س' },
};

/** « 36 m³/h » à côté de la provenance (AGQ28, parité PDF) ; `null` sans valeur servie. */
export function valeurProvenance(cle: string, valeur: number | null | undefined, format: (n: number) => string): Lbl3 | null {
  if (valeur === null || valeur === undefined || !Number.isFinite(valeur)) return null;
  const u = UNITE_ENTREE[cle];
  const n = format(valeur);
  return u ? { fr: `${n} ${u.fr}`, en: `${n} ${u.en}`, ar: `${n} ${u.ar}` } : { fr: n, en: n, ar: n };
}
