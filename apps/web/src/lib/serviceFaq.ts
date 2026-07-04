/**
 * W263 — Banque de FAQ partagée par page de service (résidentiel, professionnel,
 * pompage-solaire, batteries-stockage) + garanties par composant.
 *
 * INTÉGRITÉ : aucune réponse n'invente un fait. Chaque cluster reprend
 * STRICTEMENT des données déjà publiées ailleurs sur le site :
 *  - « Comment le prix est calculé » → même mécanique que /faq (cluster
 *    « Prix & ordres de grandeur » : facture → puissance → visite technique).
 *  - « Inclus / exclus » → tableau + exclusions génériques de /garanties
 *    (WG16 encore ouvert sur la liste d'exclusions définitive — même wording
 *    prudent « à confirmer » repris ici).
 *  - « Délais » → le process en 3 temps de /faq (cluster « Délais & process »)
 *    et, pour le SAV, l'engagement de réponse « sous 1 h, 7j/7 » de /garanties
 *    (WG9, résolu par le fondateur le 2026-07-03).
 *  - « Garanties » → le tableau structuré de /garanties (fiches.ts + les deux
 *    lignes hors-catalogue structure/main-d'œuvre de facts.ts).
 *  - « Fréquence d'entretien » → PAS de cadence chiffrée inventée : la page
 *    /maintenance-monitoring documente des visites programmées dont le SLA et
 *    le prix restent « en attente de validation du fondateur » (WG10, gate
 *    encore ouvert) — la réponse ici décrit le mécanisme réel (monitoring
 *    proactif + visite programmée) sans jamais avancer un nombre de fois par
 *    an qui ne serait pas confirmé.
 *
 * Pompage solaire (W23/W261) n'a NI onduleur NI batterie dans sa composition
 * (repo fact) — ses clusters « garanties »/« inclus-exclus » ne parlent donc
 * que du champ photovoltaïque + de la main-d'œuvre, jamais d'un onduleur ou
 * d'une batterie qu'il ne pose pas.
 *
 * Chaque page appelante importe `serviceFaqItems(service, locale)` et rend le
 * résultat via le composant `<Faq>` existant avec `schema={false}` — /faq
 * reste l'unique page émettant le FAQPage JSON-LD (W19).
 */
import type { Locale } from '../i18n/config';
import { FICHES } from './fiches';

export type ServiceKey = 'residentiel' | 'professionnel' | 'pompage-solaire' | 'batteries-stockage';

export interface ServiceFaqItem {
  q: string;
  a: string;
  cluster?: string;
}

// ─── Garanties par composant — dérivées de fiches.ts (aucune valeur recalculée) ───

export interface WarrantyRow {
  /** Libellé du composant (FR/EN/AR selon la locale appelante). */
  label: string;
  /** Durée affichée, ex. "12 ans produit · 30 ans performance". */
  years: string;
  note?: string;
}

const ficheByCategorie = (categorie: (typeof FICHES)[number]['categorie']) =>
  FICHES.find((f) => f.categorie === categorie);

const YEARS_UNIT: Record<Locale, (n: number) => string> = {
  fr: (n) => (n === 1 ? '1 an' : `${n} ans`),
  en: (n) => (n === 1 ? '1 year' : `${n} years`),
  ar: (n) => (n === 2 ? 'سنتان' : n === 1 ? 'سنة واحدة' : `${n} سنوات`),
};

const PANNEAUX_NOTE: Record<Locale, string> = {
  fr: '12 ans produit · 30 ans performance linéaire (≥ 87,4 % de la puissance initiale)',
  en: '12 years product · 30 years linear performance (≥ 87.4 % of initial power)',
  ar: '12 سنة على المنتج · 30 سنة على الأداء الخطي (≥ 87.4 % من القدرة الأولية)',
};

const LABELS: Record<Locale, { panneaux: string; onduleur: string; batterie: string; structure: string; poseMainOeuvre: string }> = {
  fr: {
    panneaux: 'Panneaux photovoltaïques',
    onduleur: 'Onduleur',
    batterie: 'Batterie',
    structure: 'Structure acier galvanisé',
    poseMainOeuvre: 'Installation et main-d’œuvre Taqinor',
  },
  en: {
    panneaux: 'Photovoltaic panels',
    onduleur: 'Inverter',
    batterie: 'Battery',
    structure: 'Galvanised steel structure',
    poseMainOeuvre: 'Installation and Taqinor labour',
  },
  ar: {
    panneaux: 'الألواح الكهروضوئية',
    onduleur: 'العاكس',
    batterie: 'البطارية',
    structure: 'الهيكل من الفولاذ المجلفن',
    poseMainOeuvre: 'التركيب واليد العاملة لتاكينور',
  },
};

/**
 * Lignes de garantie par composant pour une page de service donnée.
 * `includeOnduleur`/`includeBatterie` par défaut à `true` — mettre à `false`
 * pour le pompage solaire (aucun onduleur ni batterie dans sa composition,
 * cf. repo facts) afin de ne jamais afficher une garantie sur un composant
 * qui n'est pas posé pour ce service.
 */
export function componentWarrantyRows(
  locale: Locale,
  opts: { includeOnduleur?: boolean; includeBatterie?: boolean } = {},
): WarrantyRow[] {
  const { includeOnduleur = true, includeBatterie = true } = opts;
  const L = LABELS[locale] ?? LABELS.fr;
  const yrs = YEARS_UNIT[locale] ?? YEARS_UNIT.fr;

  const panneau = ficheByCategorie('Panneaux photovoltaïques');
  const onduleurHybride = FICHES.find((f) => f.slug === 'onduleur-deye-hybride');
  const batterie = ficheByCategorie('Batteries');

  const rows: WarrantyRow[] = [
    {
      label: L.panneaux,
      years: yrs(panneau?.warranty.years ?? 30),
      note: PANNEAUX_NOTE[locale] ?? PANNEAUX_NOTE.fr,
    },
  ];

  if (includeOnduleur && onduleurHybride) {
    rows.push({ label: L.onduleur, years: yrs(onduleurHybride.warranty.years) });
  }
  if (includeBatterie && batterie) {
    rows.push({ label: L.batterie, years: yrs(batterie.warranty.years) });
  }

  // Structure + pose : hors catalogue fiches.ts, publiées sur /garanties
  // (mêmes valeurs que facts.ts warrantyPageSource.additionalCoverage).
  rows.push({ label: L.structure, years: yrs(20) });
  rows.push({ label: L.poseMainOeuvre, years: yrs(2) });

  return rows;
}

// ─── FAQ clusters par service ───

const CLUSTER_LABEL: Record<Locale, { entretien: string; prix: string; inclusExclus: string; delais: string; garanties: string }> = {
  fr: {
    entretien: 'Fréquence d’entretien',
    prix: 'Comment le prix est calculé',
    inclusExclus: 'Ce qui est inclus / exclus',
    delais: 'Délais',
    garanties: 'Garanties',
  },
  en: {
    entretien: 'Maintenance frequency',
    prix: 'How the price is calculated',
    inclusExclus: 'What’s included / excluded',
    delais: 'Timelines',
    garanties: 'Warranties',
  },
  ar: {
    entretien: 'وتيرة الصيانة',
    prix: 'كيف يُحسب الثمن',
    inclusExclus: 'ما هو مُدرَج / مُستثنى',
    delais: 'الآجال',
    garanties: 'الضمانات',
  },
};

interface ServiceCopy {
  entretienQ: string;
  entretienA: string;
  prixQ: string;
  prixA: string;
  inclusQ: string;
  inclusA: string;
  exclusQ: string;
  exclusA: string;
  delaisQ: string;
  delaisA: string;
  garantiesQ: string;
  garantiesA: string;
}

// Résidentiel — reprend /résidentiel (fourchettes, 3–7 ans, ONEE) + /garanties
// + /faq (process 3 temps) + /maintenance-monitoring (SAV proactif, SLA pending WG10).
const RESIDENTIEL: Record<Locale, ServiceCopy> = {
  fr: {
    entretienQ: 'Une installation résidentielle demande-t-elle un entretien régulier ?',
    entretienA:
      'Le socle est déjà couvert par le monitoring Deye Cloud, remonté sur chaque installation : nous voyons une anomalie avant vous, sur alerte automatique. Au-delà, un passage d’entretien programmé (nettoyage des panneaux notamment) existe en contrat — cadence, délai de réponse et prix exacts sont encore en attente de validation du fondateur, nous ne publions donc aucun chiffre tant qu’il n’est pas arrêté. Voir la page Maintenance & monitoring.',
    prixQ: 'Comment le prix d’une installation résidentielle est-il calculé ?',
    prixA:
      'Le prix suit la puissance, et la puissance suit votre facture — jamais un tarif au mètre carré de toiture. Le diagnostic en ligne donne une première fourchette en 60 secondes à partir de votre facture mensuelle ; le chiffre exact tombe après la visite technique, qui vérifie la toiture et le matériel retenu.',
    inclusQ: 'Qu’est-ce qui est inclus dans une installation Taqinor ?',
    inclusA:
      'Le matériel posé (panneaux, onduleur, éventuellement batterie), la structure de fixation, la pose par notre équipe, le dossier technique complet à la livraison (schémas unifilaires, calcul de câbles, liste des protections) et l’accès personnel au monitoring Deye Cloud.',
    exclusQ: 'Qu’est-ce qui n’est pas couvert par la garantie ?',
    exclusA:
      'Le dommage accidentel ou un choc externe, une intervention par un tiers non habilité par Taqinor, un défaut d’entretien manifeste, un événement de force majeure (relève alors de votre assurance habitation, pas de notre garantie matériel) et l’usure normale au-delà des seuils de performance garantis. Liste indicative, à confirmer — voir la page Garanties pour le détail.',
    delaisQ: 'Combien de temps entre le premier contact et l’installation ?',
    delaisA:
      'Trois temps, sans détour : d’abord un diagnostic de 60 secondes qui renvoie une première fourchette, puis un échange WhatsApp direct avec un technicien (photos de toiture à l’appui), enfin la visite technique, l’étude complète gratuite et le devis. Vous parlez à la personne qui dimensionne, pas à un standard qui rappellera.',
    garantiesQ: 'Quelles garanties couvrent une installation résidentielle ?',
    garantiesA:
      'Panneaux : 12 ans produit et 30 ans de performance linéaire (≥ 87,4 % de la puissance initiale à 30 ans). Onduleur et batterie : 10 ans. Structure acier galvanisé : 20 ans. Installation et main-d’œuvre Taqinor : 2 ans. Le détail par composant est ci-dessous et sur la page Garanties.',
  },
  en: {
    entretienQ: 'Does a residential installation need regular maintenance?',
    entretienA:
      'The baseline is already covered by the Deye Cloud monitoring shipped with every installation: we see an anomaly before you do, on an automatic alert. Beyond that, a scheduled maintenance visit (panel cleaning in particular) exists as a contract — the exact cadence, response time and price are still pending founder validation, so we publish no figure until it is settled. See the Maintenance & monitoring page.',
    prixQ: 'How is the price of a residential installation calculated?',
    prixA:
      'The price follows the power, and the power follows your bill — never a price per square metre of roof. The online assessment gives a first range in 60 seconds from your monthly bill; the exact figure comes after the technical visit, which checks the roof and the equipment retained.',
    inclusQ: 'What is included in a Taqinor installation?',
    inclusA:
      'The equipment fitted (panels, inverter, battery where relevant), the mounting structure, the install by our team, the full technical file on delivery (single-line diagrams, cable sizing, list of protections) and personal access to Deye Cloud monitoring.',
    exclusQ: 'What is not covered by the warranty?',
    exclusA:
      'Accidental damage or an external impact, an intervention by a third party not authorised by Taqinor, a clear lack of maintenance, a force-majeure event (a matter for your home insurance, not our hardware warranty) and normal wear beyond the guaranteed performance thresholds. Indicative list, to be confirmed — see the Warranties page for detail.',
    delaisQ: 'How long between first contact and installation?',
    delaisA:
      'Three steps, straightforward: first a 60-second assessment that returns a first range, then a direct WhatsApp exchange with a technician (roof photos included), finally the technical visit, the full free assessment and the quote. You speak to the person who sizes the system, not a call centre that will call back.',
    garantiesQ: 'What warranties cover a residential installation?',
    garantiesA:
      'Panels: 12 years product and 30 years linear performance (≥ 87.4 % of initial power at 30 years). Inverter and battery: 10 years. Galvanised steel structure: 20 years. Taqinor installation and labour: 2 years. The breakdown by component is below and on the Warranties page.',
  },
  ar: {
    entretienQ: 'هل تحتاج التركيبة السكنية إلى صيانة منتظمة؟',
    entretienA:
      'القاعدة مُغطّاة بالفعل بمراقبة Deye Cloud المُدرَجة مع كل تركيبة: نرى الخلل قبلكم، عبر تنبيه آلي. إضافة إلى ذلك، تتوفّر زيارة صيانة مبرمجة (تنظيف الألواح خصوصاً) ضمن عقد — الوتيرة الدقيقة وزمن الاستجابة والثمن ما زالت في انتظار مصادقة المؤسس، فلا ننشر أي رقم قبل أن يُحسم. انظر صفحة الصيانة والمراقبة.',
    prixQ: 'كيف يُحسب ثمن تركيبة سكنية؟',
    prixA:
      'الثمن يتبع القدرة، والقدرة تتبع فاتورتكم — لا سعر بالمتر المربع من السطح أبداً. التشخيص عبر الإنترنت يُعطي مجالاً أولياً خلال 60 ثانية انطلاقاً من فاتورتكم الشهرية؛ الرقم الدقيق يأتي بعد الزيارة التقنية التي تتحقّق من السطح والعتاد المُختار.',
    inclusQ: 'ما الذي يُدرَج ضمن تركيبة تاكينور؟',
    inclusA:
      'العتاد المُركَّب (الألواح، العاكس، البطارية عند الاقتضاء)، بنية التثبيت، التركيب من طرف فريقنا، الملف التقني الكامل عند التسليم (مخططات أحادية الخط، حساب الكوابل، لائحة الحمايات) والولوج الشخصي إلى مراقبة Deye Cloud.',
    exclusQ: 'ما الذي لا يُغطّيه الضمان؟',
    exclusA:
      'الضرر العرضي أو الصدمة الخارجية، تدخّل طرف ثالث غير معتمد من تاكينور، إهمال صيانة واضح، حدث قوة قاهرة (يخصّ تأمين سكنكم، لا ضمان معداتنا) والتآكل العادي بما يتجاوز عتبات الأداء المضمونة. لائحة إرشادية، قيد التأكيد — انظر صفحة الضمانات للتفصيل.',
    delaisQ: 'كم يستغرق الأمر من أول اتصال إلى التركيب؟',
    delaisA:
      'ثلاث مراحل، دون التفاف: أولاً تشخيص لمدة 60 ثانية يُعيد مجالاً أولياً، ثم تواصل مباشر عبر واتساب مع تقني (بصور السطح)، وأخيراً الزيارة التقنية والدراسة الكاملة المجانية والثمن. تتحدّثون مع الشخص الذي يحدّد المقاس، لا مع مركز نداء سيتصل لاحقاً.',
    garantiesQ: 'ما الضمانات التي تُغطّي تركيبة سكنية؟',
    garantiesA:
      'الألواح: 12 سنة على المنتج و30 سنة على الأداء الخطي (≥ 87.4 % من القدرة الأولية عند 30 سنة). العاكس والبطارية: 10 سنوات. الهيكل الفولاذي المجلفن: 20 سنة. التركيب واليد العاملة لتاكينور: سنتان. التفصيل حسب المكوّن أسفله وعلى صفحة الضمانات.',
  },
};

// Professionnel — reprend /professionnel (3–5 ans, 5 MW, TVA/amortissement) +
// /garanties + /faq process + /maintenance-monitoring.
const PROFESSIONNEL: Record<Locale, ServiceCopy> = {
  fr: {
    entretienQ: 'Un site professionnel demande-t-il un entretien particulier ?',
    entretienA:
      'Le monitoring Deye Cloud tourne en continu sur l’ensemble du parc et déclenche une alerte chez nous avant que vous ne constatiez quoi que ce soit. Un passage d’entretien programmé peut s’ajouter en contrat ; la cadence, le délai de réponse et le prix exacts restent en attente de validation du fondateur — aucun chiffre n’est publié tant qu’il n’est pas arrêté. Voir la page Maintenance & monitoring.',
    prixQ: 'Comment le prix d’un site professionnel est-il calculé ?',
    prixA:
      'Le chiffrage se cale sur vos courbes de charge et sur les conditions de votre raccordement, jamais sur un gabarit générique. Les fourchettes indicatives publiées donnent un ordre de grandeur par tranche de facture ; le devis réel dépend de la visite technique et, en moyenne tension, du régime loi 82-21 applicable (accord de raccordement jusqu’à 5 MW, autorisation au-delà).',
    inclusQ: 'Qu’est-ce qui est inclus dans une installation professionnelle ?',
    inclusA:
      'Le matériel tier-1 (panneaux, onduleur, structure), le dossier technique complet, le montage du dossier loi 82-21 (accord de raccordement ou autorisation selon la puissance) et l’accès au monitoring Deye Cloud pour l’ensemble du site.',
    exclusQ: 'Qu’est-ce qui n’est pas couvert par la garantie ?',
    exclusA:
      'Le dommage accidentel ou un choc externe, une intervention par un tiers non habilité par Taqinor, un défaut d’entretien manifeste, un événement de force majeure (assurance du bâtiment, pas notre garantie matériel) et l’usure normale au-delà des seuils garantis. Liste indicative, à confirmer — voir la page Garanties.',
    delaisQ: 'Quel est le délai entre le premier contact et la mise en service ?',
    delaisA:
      'Le même process en trois temps que pour un site résidentiel : diagnostic initial, échange direct avec un technicien, puis visite technique et étude complète. Sur un site professionnel, l’étude intègre en plus vos courbes de charge et, selon la puissance, le montage du dossier loi 82-21 — ce qui peut allonger le délai selon le régime applicable (accord de raccordement ou autorisation).',
    garantiesQ: 'Quelles garanties couvrent une installation professionnelle ?',
    garantiesA:
      'Mêmes garanties tier-1 que le résidentiel : panneaux 12 ans produit / 30 ans performance linéaire (≥ 87,4 %), onduleur 10 ans, structure acier galvanisé 20 ans, installation et main-d’œuvre Taqinor 2 ans. Le détail par composant est ci-dessous et sur la page Garanties.',
  },
  en: {
    entretienQ: 'Does a business site need particular maintenance?',
    entretienA:
      'Deye Cloud monitoring runs continuously across the whole fleet and triggers an alert on our side before you notice anything. A scheduled maintenance visit can be added as a contract; the exact cadence, response time and price are still pending founder validation — no figure is published until it is settled. See the Maintenance & monitoring page.',
    prixQ: 'How is the price for a business site calculated?',
    prixA:
      'The costing is set on your load curves and on your grid-connection conditions, never on a generic template. The published indicative ranges give an order of magnitude per bill bracket; the real quote depends on the technical visit and, in medium voltage, on the applicable law 82-21 regime (grid-connection agreement up to 5 MW, authorisation beyond).',
    inclusQ: 'What is included in a business installation?',
    inclusA:
      'Tier-1 equipment (panels, inverter, structure), the full technical file, building the law 82-21 file (grid-connection agreement or authorisation depending on power) and Deye Cloud monitoring access for the whole site.',
    exclusQ: 'What is not covered by the warranty?',
    exclusA:
      'Accidental damage or an external impact, an intervention by a third party not authorised by Taqinor, a clear lack of maintenance, a force-majeure event (a matter for the building’s insurance, not our hardware warranty) and normal wear beyond the guaranteed thresholds. Indicative list, to be confirmed — see the Warranties page.',
    delaisQ: 'What is the timeline from first contact to commissioning?',
    delaisA:
      'The same three-step process as a residential site: initial assessment, direct exchange with a technician, then the technical visit and full assessment. On a business site, the assessment also factors in your load curves and, depending on power, building the law 82-21 file — which can extend the timeline depending on the applicable regime (grid-connection agreement or authorisation).',
    garantiesQ: 'What warranties cover a business installation?',
    garantiesA:
      'The same tier-1 warranties as residential: panels 12 years product / 30 years linear performance (≥ 87.4 %), inverter 10 years, galvanised steel structure 20 years, Taqinor installation and labour 2 years. The breakdown by component is below and on the Warranties page.',
  },
  ar: {
    entretienQ: 'هل يحتاج الموقع المهني إلى صيانة خاصة؟',
    entretienA:
      'تعمل مراقبة Deye Cloud باستمرار على كامل الأسطول وتُطلق تنبيهاً لدينا قبل أن تلاحظوا أي شيء. يمكن إضافة زيارة صيانة مبرمجة ضمن عقد؛ الوتيرة الدقيقة وزمن الاستجابة والثمن ما زالت في انتظار مصادقة المؤسس — لا يُنشَر أي رقم قبل أن يُحسم. انظر صفحة الصيانة والمراقبة.',
    prixQ: 'كيف يُحسب ثمن موقع مهني؟',
    prixA:
      'يُضبط التسعير على منحنيات الحمل لديكم وعلى شروط ربطكم بالشبكة، لا على نموذج عام أبداً. المجالات الإرشادية المنشورة تُعطي أمر مقدار حسب شريحة الفاتورة؛ الثمن الحقيقي يعتمد على الزيارة التقنية، وفي المتوسط الجهد، على نظام القانون 82-21 المطبَّق (اتفاقية ربط إلى غاية 5 ميغاواط، ترخيص فوق ذلك).',
    inclusQ: 'ما الذي يُدرَج ضمن تركيبة مهنية؟',
    inclusA:
      'عتاد من الفئة الأولى (ألواح، عاكس، بنية)، الملف التقني الكامل، إعداد ملف القانون 82-21 (اتفاقية ربط أو ترخيص حسب القدرة) وولوج مراقبة Deye Cloud لكامل الموقع.',
    exclusQ: 'ما الذي لا يُغطّيه الضمان؟',
    exclusA:
      'الضرر العرضي أو الصدمة الخارجية، تدخّل طرف ثالث غير معتمد من تاكينور، إهمال صيانة واضح، حدث قوة قاهرة (يخصّ تأمين المبنى، لا ضمان معداتنا) والتآكل العادي بما يتجاوز العتبات المضمونة. لائحة إرشادية، قيد التأكيد — انظر صفحة الضمانات.',
    delaisQ: 'ما الأجل بين أول اتصال والتشغيل الفعلي؟',
    delaisA:
      'نفس المسار من ثلاث مراحل كما في الموقع السكني: تشخيص أولي، تواصل مباشر مع تقني، ثم الزيارة التقنية والدراسة الكاملة. في الموقع المهني، تُدمج الدراسة كذلك منحنيات الحمل، وحسب القدرة، إعداد ملف القانون 82-21 — ما قد يُطيل الأجل حسب النظام المطبَّق (اتفاقية ربط أو ترخيص).',
    garantiesQ: 'ما الضمانات التي تُغطّي تركيبة مهنية؟',
    garantiesA:
      'نفس ضمانات الفئة الأولى كما في السكني: الألواح 12 سنة على المنتج / 30 سنة على الأداء الخطي (≥ 87.4 %)، العاكس 10 سنوات، الهيكل الفولاذي المجلفن 20 سنة، التركيب واليد العاملة لتاكينور سنتان. التفصيل حسب المكوّن أسفله وعلى صفحة الضمانات.',
  },
};

// Pompage solaire — W23/W261 : ZÉRO onduleur, ZÉRO batterie dans la
// composition. Prix/délais/garanties ne parlent que du champ PV + pose,
// jamais d'un composant absent de ce service.
const POMPAGE: Record<Locale, ServiceCopy> = {
  fr: {
    entretienQ: 'Un système de pompage solaire demande-t-il un entretien ?',
    entretienA:
      'Sans batterie ni électronique de stockage à surveiller, l’entretien porte surtout sur le champ photovoltaïque (nettoyage) et le variateur qui pilote la pompe. La cadence exacte d’un contrat d’entretien dédié reste à définir au cas par cas selon le site — nous ne publions aucune fréquence chiffrée générique tant qu’elle n’est pas mesurée sur votre parcelle.',
    prixQ: 'Comment le prix d’un système de pompage solaire est-il calculé ?',
    prixA:
      'Le prix suit le champ photovoltaïque et la pompe, dimensionnés sur quatre mesures relevées sur place : le débit visé, la HMT, la profondeur du forage et les besoins en eau de la culture. Sans ces quatre chiffres, nous ne pouvons avancer aucun ordre de grandeur — le calcul se fait toujours à l’étude, jamais sur une moyenne nationale.',
    inclusQ: 'Qu’est-ce qui est inclus dans un système de pompage solaire ?',
    inclusA:
      'Le champ photovoltaïque et son variateur — dimensionnés sur le débit, la HMT et les besoins en eau —, le même matériel tier-1 que nos toitures, et le dossier technique. Le pompage solaire ne comprend ni onduleur ni batterie : la pompe tourne au fil du soleil, l’eau se stocke dans le bassin, pas dans une batterie.',
    exclusQ: 'Qu’est-ce qui n’est pas couvert par la garantie ?',
    exclusA:
      'Le dommage accidentel ou un choc externe, une intervention par un tiers non habilité par Taqinor, un défaut d’entretien manifeste, un événement de force majeure et l’usure normale au-delà des seuils garantis — la même règle générique que pour nos toitures résidentielles et professionnelles. Aucun onduleur ni aucune batterie n’est concerné ici, ce service n’en pose pas.',
    delaisQ: 'Quel est le délai entre le relevé du forage et la mise en service ?',
    delaisA:
      'Le relevé des quatre mesures (débit, HMT, profondeur du forage, besoins en eau) précède tout chiffrage : sans elles, nous ne dimensionnons rien. Une fois ces mesures en main, le système se calcule et le devis suit le même parcours que pour un site professionnel — diagnostic, échange direct, puis étude complète.',
    garantiesQ: 'Quelles garanties couvrent un système de pompage solaire ?',
    garantiesA:
      'Panneaux : 12 ans produit et 30 ans de performance linéaire (≥ 87,4 % de la puissance initiale à 30 ans) — le même matériel tier-1 que nos toitures. Installation et main-d’œuvre Taqinor : 2 ans. Aucune garantie onduleur ou batterie n’est listée ici : ce service ne comprend ni l’un ni l’autre.',
  },
  en: {
    entretienQ: 'Does a solar pumping system need maintenance?',
    entretienA:
      'With no battery or storage electronics to monitor, maintenance mainly concerns the photovoltaic array (cleaning) and the variable-speed drive that runs the pump. The exact cadence of a dedicated maintenance contract remains to be set case by case per site — we publish no generic figure until it is measured on your plot.',
    prixQ: 'How is the price of a solar pumping system calculated?',
    prixA:
      'The price follows the photovoltaic array and the pump, sized on four measurements taken on site: the target flow rate, the total dynamic head, the borehole depth and the crop’s water needs. Without those four figures we cannot give any order of magnitude — the calculation is always done at the assessment stage, never from a national average.',
    inclusQ: 'What is included in a solar pumping system?',
    inclusA:
      'The photovoltaic array and its variable-speed drive — sized on flow rate, head and water needs —, the same tier-1 equipment as our roofs, and the technical file. Solar pumping includes neither an inverter nor a battery: the pump runs with the sun, and the water is stored in the reservoir, not in a battery.',
    exclusQ: 'What is not covered by the warranty?',
    exclusA:
      'Accidental damage or an external impact, an intervention by a third party not authorised by Taqinor, a clear lack of maintenance, a force-majeure event and normal wear beyond the guaranteed thresholds — the same generic rule as for our residential and business roofs. No inverter or battery is concerned here, as this service does not fit either.',
    delaisQ: 'What is the timeline from the borehole survey to commissioning?',
    delaisA:
      'Surveying the four measurements (flow rate, head, borehole depth, water needs) comes before any costing: without them, we size nothing. Once those measurements are in hand, the system is calculated and the quote follows the same path as a business site — assessment, direct exchange, then full study.',
    garantiesQ: 'What warranties cover a solar pumping system?',
    garantiesA:
      'Panels: 12 years product and 30 years linear performance (≥ 87.4 % of initial power at 30 years) — the same tier-1 equipment as our roofs. Taqinor installation and labour: 2 years. No inverter or battery warranty is listed here: this service includes neither.',
  },
  ar: {
    entretienQ: 'هل يحتاج نظام الضخ الشمسي إلى صيانة؟',
    entretienA:
      'دون بطارية أو إلكترونيات تخزين تستوجب المراقبة، تخصّ الصيانة أساساً الحقل الكهروضوئي (التنظيف) والمُغيِّر الذي يشغّل المضخة. الوتيرة الدقيقة لعقد صيانة مخصَّص تبقى تُحدَّد حالة بحالة حسب الموقع — لا ننشر أي وتيرة عامة مُرقَّمة قبل أن تُقاس على قطعتكم الأرضية.',
    prixQ: 'كيف يُحسب ثمن نظام الضخ الشمسي؟',
    prixA:
      'يتبع الثمن الحقل الكهروضوئي والمضخة، المُحدَّدين المقاس على أربع قياسات تُؤخذ في الموقع: التدفق المستهدف، الارتفاع المانومتري الكلي، عمق البئر واحتياجات المحصول من الماء. دون هذه الأرقام الأربعة، لا يمكننا تقديم أي أمر مقدار — الحساب يتم دائماً عند الدراسة، لا انطلاقاً من متوسط وطني.',
    inclusQ: 'ما الذي يُدرَج ضمن نظام ضخ شمسي؟',
    inclusA:
      'الحقل الكهروضوئي ومُغيِّره — مُحدَّدَين المقاس على التدفق والارتفاع المانومتري واحتياجات الماء —، نفس عتاد الفئة الأولى كأسطحنا، والملف التقني. لا يشمل الضخ الشمسي لا عاكساً ولا بطارية: تعمل المضخة على إيقاع الشمس، ويُخزَّن الماء في الخزان، لا في بطارية.',
    exclusQ: 'ما الذي لا يُغطّيه الضمان؟',
    exclusA:
      'الضرر العرضي أو الصدمة الخارجية، تدخّل طرف ثالث غير معتمد من تاكينور، إهمال صيانة واضح، حدث قوة قاهرة والتآكل العادي بما يتجاوز العتبات المضمونة — نفس القاعدة العامة كأسطحنا السكنية والمهنية. لا يخصّ الأمر هنا أي عاكس أو بطارية، لأن هذه الخدمة لا تشملهما.',
    delaisQ: 'ما الأجل بين معاينة البئر والتشغيل الفعلي؟',
    delaisA:
      'معاينة القياسات الأربعة (التدفق، الارتفاع المانومتري، عمق البئر، احتياجات الماء) تسبق أي تسعير: دونها، لا نُحدِّد مقاس أي شيء. بمجرد توفّر هذه القياسات، يُحسب النظام ويتّبع الثمن نفس مسار الموقع المهني — تشخيص، تواصل مباشر، ثم دراسة كاملة.',
    garantiesQ: 'ما الضمانات التي تُغطّي نظام ضخ شمسي؟',
    garantiesA:
      'الألواح: 12 سنة على المنتج و30 سنة على الأداء الخطي (≥ 87.4 % من القدرة الأولية عند 30 سنة) — نفس عتاد الفئة الأولى كأسطحنا. التركيب واليد العاملة لتاكينور: سنتان. لا ضمان عاكس أو بطارية مُدرَج هنا: هذه الخدمة لا تشمل أياً منهما.',
  },
};

// Batteries & stockage — reprend /batteries-stockage (Dyness LFP, 6000
// cycles, 90% DoD, garantie 10 ans, CAN BMS/Deye) + /garanties + /faq.
const BATTERIES: Record<Locale, ServiceCopy> = {
  fr: {
    entretienQ: 'Une batterie de stockage demande-t-elle un entretien ?',
    entretienA:
      'Le BMS intégré gère la charge et la décharge automatiquement, sans intervention manuelle. Le monitoring Deye Cloud remonte l’état de la batterie en continu ; un passage d’entretien programmé peut s’ajouter en contrat, mais sa cadence, son délai de réponse et son prix exacts restent en attente de validation du fondateur — aucun chiffre publié tant qu’il n’est pas arrêté.',
    prixQ: 'Comment le prix d’une batterie de stockage est-il calculé ?',
    prixA:
      'La capacité — donc le prix — suit votre creux de consommation du soir, pas un palier de catalogue : nos modules Dyness s’empilent par tranches de 5 kWh, et on empile juste assez de modules pour couvrir ce que vos panneaux ne fournissent plus une fois le soleil couché.',
    inclusQ: 'Qu’est-ce qui est inclus avec une batterie Dyness ?',
    inclusA:
      'La batterie lithium-fer-phosphate (LFP) elle-même, son dialogue CAN BMS natif avec l’onduleur hybride Deye qui pilote charge et décharge, le raccordement, et l’accès au monitoring Deye Cloud pour suivre son état.',
    exclusQ: 'Qu’est-ce qui n’est pas couvert par la garantie batterie ?',
    exclusA:
      'Le dommage accidentel ou un choc externe, une intervention par un tiers non habilité par Taqinor, un défaut d’entretien manifeste, un événement de force majeure et l’usure normale au-delà des seuils garantis (≥ 70 % de capacité conservée à 10 ans). Liste indicative, à confirmer — voir la page Garanties.',
    delaisQ: 'Quel est le délai pour ajouter une batterie à une installation ?',
    delaisA:
      'Le même process qu’une nouvelle installation : d’abord la lecture de votre courbe de consommation heure par heure pour vérifier que le stockage se justifie, puis un échange direct avec un technicien, enfin la visite technique qui confirme la capacité (en modules de 5 kWh) et le devis.',
    garantiesQ: 'Quelle garantie couvre une batterie Dyness ?',
    garantiesA:
      '10 ans, avec au moins 70 % de la capacité initiale conservée sur cette durée — plus de 6 000 cycles à 90 % de profondeur de décharge. Même règle de garantie activable sur place que le reste du matériel tier-1 Taqinor (sourcé via des distributeurs officiels au Maroc).',
  },
  en: {
    entretienQ: 'Does a storage battery need maintenance?',
    entretienA:
      'The built-in BMS manages charge and discharge automatically, with no manual intervention. Deye Cloud monitoring reports the battery’s state continuously; a scheduled maintenance visit can be added as a contract, but its exact cadence, response time and price are still pending founder validation — no figure published until it is settled.',
    prixQ: 'How is the price of a storage battery calculated?',
    prixA:
      'Capacity — and therefore price — follows your evening consumption dip, not a catalogue tier: our Dyness modules stack in 5 kWh increments, and we stack just enough modules to cover what your panels no longer provide once the sun has set.',
    inclusQ: 'What is included with a Dyness battery?',
    inclusA:
      'The lithium-iron-phosphate (LFP) battery itself, its native CAN BMS dialogue with the Deye hybrid inverter that drives charge and discharge, the wiring, and Deye Cloud monitoring access to track its state.',
    exclusQ: 'What is not covered by the battery warranty?',
    exclusA:
      'Accidental damage or an external impact, an intervention by a third party not authorised by Taqinor, a clear lack of maintenance, a force-majeure event and normal wear beyond the guaranteed thresholds (≥ 70 % capacity retained at 10 years). Indicative list, to be confirmed — see the Warranties page.',
    delaisQ: 'What is the timeline to add a battery to an installation?',
    delaisA:
      'The same process as a new installation: first reading your hour-by-hour consumption curve to check storage is justified, then a direct exchange with a technician, finally the technical visit that confirms the capacity (in 5 kWh modules) and the quote.',
    garantiesQ: 'What warranty covers a Dyness battery?',
    garantiesA:
      '10 years, with at least 70 % of initial capacity retained over that period — more than 6,000 cycles at 90 % depth of discharge. Same on-the-spot activatable warranty rule as the rest of Taqinor’s tier-1 equipment (sourced through official distributors in Morocco).',
  },
  ar: {
    entretienQ: 'هل تحتاج بطارية التخزين إلى صيانة؟',
    entretienA:
      'يدير نظام BMS المُدمَج الشحن والتفريغ تلقائياً، دون أي تدخّل يدوي. تنقل مراقبة Deye Cloud حالة البطارية باستمرار؛ يمكن إضافة زيارة صيانة مبرمجة ضمن عقد، لكن وتيرتها الدقيقة وزمن استجابتها وثمنها ما زالت في انتظار مصادقة المؤسس — لا يُنشَر أي رقم قبل أن يُحسم.',
    prixQ: 'كيف يُحسب ثمن بطارية التخزين؟',
    prixA:
      'تتبع السعة — وبالتالي الثمن — تراجع استهلاككم المسائي، لا شريحة كاطالوݣ: تتراكم وحدات Dyness لدينا بشرائح 5 kWh، ونُركِّب فقط ما يكفي من الوحدات لتغطية ما لم تعد ألواحكم توفّره بعد غروب الشمس.',
    inclusQ: 'ما الذي يُدرَج مع بطارية Dyness؟',
    inclusA:
      'البطارية نفسها من الليثيوم-حديد-فوسفات (LFP)، تواصلها الأصلي عبر CAN BMS مع العاكس الهجين Deye الذي يُدير الشحن والتفريغ، التوصيل، وولوج مراقبة Deye Cloud لمتابعة حالتها.',
    exclusQ: 'ما الذي لا يُغطّيه ضمان البطارية؟',
    exclusA:
      'الضرر العرضي أو الصدمة الخارجية، تدخّل طرف ثالث غير معتمد من تاكينور، إهمال صيانة واضح، حدث قوة قاهرة والتآكل العادي بما يتجاوز العتبات المضمونة (≥ 70 % من السعة محفوظة عند 10 سنوات). لائحة إرشادية، قيد التأكيد — انظر صفحة الضمانات.',
    delaisQ: 'ما الأجل لإضافة بطارية إلى تركيبة قائمة؟',
    delaisA:
      'نفس مسار التركيبة الجديدة: أولاً قراءة منحنى استهلاككم ساعة بساعة للتحقّق من وجاهة التخزين، ثم تواصل مباشر مع تقني، وأخيراً الزيارة التقنية التي تؤكّد السعة (بوحدات 5 kWh) والثمن.',
    garantiesQ: 'ما الضمان الذي يُغطّي بطارية Dyness؟',
    garantiesA:
      '10 سنوات، مع الحفاظ على 70 % على الأقل من السعة الأولية خلال هذه المدة — أكثر من 6 000 دورة عند عمق تفريغ 90 %. نفس قاعدة الضمان القابل للتفعيل محلياً كباقي عتاد تاكينور من الفئة الأولى (مُورَّد عبر موزّعين رسميين بالمغرب).',
  },
};

const SERVICE_COPY: Record<ServiceKey, Record<Locale, ServiceCopy>> = {
  'residentiel': RESIDENTIEL,
  'professionnel': PROFESSIONNEL,
  'pompage-solaire': POMPAGE,
  'batteries-stockage': BATTERIES,
};

/**
 * FAQ localisée pour une page de service, prête à passer à `<Faq items={...}
 * schema={false} />`. Ordre fixe : entretien, prix, inclus, exclus, délais,
 * garanties — chaque item porte un `cluster` pour le regroupement visuel de
 * `<Faq>` (W330).
 */
export function serviceFaqItems(service: ServiceKey, locale: Locale): ServiceFaqItem[] {
  const copy = (SERVICE_COPY[service] ?? SERVICE_COPY['residentiel'])[locale] ?? SERVICE_COPY['residentiel'].fr;
  const cl = CLUSTER_LABEL[locale] ?? CLUSTER_LABEL.fr;

  return [
    { cluster: cl.entretien, q: copy.entretienQ, a: copy.entretienA },
    { cluster: cl.prix, q: copy.prixQ, a: copy.prixA },
    { cluster: cl.inclusExclus, q: copy.inclusQ, a: copy.inclusA },
    { cluster: cl.inclusExclus, q: copy.exclusQ, a: copy.exclusA },
    { cluster: cl.delais, q: copy.delaisQ, a: copy.delaisA },
    { cluster: cl.garanties, q: copy.garantiesQ, a: copy.garantiesA },
  ];
}
