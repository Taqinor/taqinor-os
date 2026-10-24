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
      answer: "Les panneaux sont fixés sur une structure au sol avec une visserie antivol et le coffret est fermé à clé ; une clôture ou un gardiennage restent de votre côté. Le choix d'une assurance se fait avec votre assureur.",
      answerAr: 'تُثبت الألواح على هيكل أرضي ببراغي مضادة للسرقة ويُقفل الصندوق بمفتاح؛ أما السياج أو الحراسة فيبقيان على عاتقكم. اختيار التأمين يتم مع شركة التأمين.',
      answerEn: 'The panels are fixed on a ground structure with anti-theft fasteners and the cabinet is locked; a fence or guarding remains on your side. Insurance is a decision to take with your insurer.',
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
} as const satisfies Record<string, Lbl3>;
