import type { Locale } from '../i18n/config';

/**
 * Liens WhatsApp pré-remplis (wa.me). `number` : chiffres uniquement,
 * avec indicatif pays (ex. 2126XXXXXXXX).
 */
export function whatsappLink(number: string, text: string): string {
  const digits = number.replace(/\D/g, '');
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

/** Message pré-rempli après soumission du formulaire (nom + ville + bande ROI). */
export function leadWhatsappText(p: { fullName: string; city: string; kwcLabel: string; paybackLabel: string }): string {
  return (
    `Bonjour, je suis ${p.fullName} (${p.city}). ` +
    `Je viens de faire la simulation sur taqinor.ma : ${p.kwcLabel}, retour estimé ${p.paybackLabel}. ` +
    `Je souhaite être rappelé(e) pour une étude.`
  );
}

/**
 * WJ50 — invitation au message vocal, ajoutée à la fin du texte pré-rempli du
 * parcours (« Mon toit ») : une large part des clients marocains répond
 * naturellement par vocal, et la photo de facture/compteur ne peut pas être
 * jointe au deeplink wa.me (limite de la plateforme) — on invite donc
 * explicitement à l'envoyer en vocal juste après l'ouverture du chat.
 */
export const VOICE_NOTE_INVITE =
  'Vous pouvez aussi m’envoyer un vocal avec une photo de ma facture.';

/**
 * W349 — « La porte sans formulaire » : un message pré-rempli qui ne demande
 * RIEN à lire ni à remplir — juste une photo de facture (ou de compteur) et/ou
 * un vocal. Cible le visiteur WhatsApp-only à faible littératie numérique
 * (persona confirmé, notamment agricole) qui n'arrive à compléter AUCUN
 * assistant à étapes. Distinct de `captureWhatsappText` (qui suppose un
 * parcours déjà entamé avec nom/ville/estimation) : ici il n'y a AUCUN champ
 * préalable — le lien s'ouvre directement depuis un CTA de page, pas depuis
 * un formulaire soumis.
 *
 * `locale === 'ar'` ajoute UNE ligne courte en darija (arabe marocain parlé)
 * après la ligne en arabe standard (fus'ha) : le persona ciblé par cette
 * porte (agricole, faible littératie) communique naturellement en darija à
 * l'oral, même quand l'UI de la page reste en fus'ha (registre écrit
 * standard, cohérent avec le reste du site). Les autres locales ne changent
 * pas de comportement (repli FR identique à avant).
 */
export type ZeroFormVariant = 'facture' | 'pompage';

/**
 * AGW402 — variante `'pompage'` : un agriculteur au butane n'a pas de facture
 * d'électricité à photographier. Le message demande sa POSITION et la photo de
 * la plaque de sa pompe (ou de son forage). Ni prix, ni promesse d'aide.
 * Darija écrite maintenant, relue par Reda ensuite (D-AGR-11). Une locale 'en'
 * existe aussi pour la variante `'facture'` : l'anglais n'est plus servi en
 * français (le FR reste identique à l'octet).
 */
export function zeroFormWhatsappText(locale?: Locale, variant: ZeroFormVariant = 'facture'): string {
  if (variant === 'pompage') {
    if (locale === 'ar') {
      return (
        'مرحباً، أرغب في الضخ الشمسي لاستغلالي الفلاحي. أرسل لكم موقعي وصورة للوحة مضختي (أو لبئري). ' +
        'هادي موقعي وصورة ديال البلاكة د المضخة (ولا د البير) — عافاك عاونوني.'
      );
    }
    if (locale === 'en') {
      return (
        'Hello, I would like solar pumping for my farm. ' +
        'I am sending you my location and a photo of my pump’s nameplate (or of my borehole).'
      );
    }
    return (
      'Bonjour, je souhaite un pompage solaire pour mon exploitation. ' +
      'Je vous envoie ma position et une photo de la plaque de ma pompe (ou de mon forage).'
    );
  }
  if (locale === 'ar') {
    return (
      'مرحبا، هادي صورة فاتورة الكهرباء ديالي (ولا نصيفط ليكم صوت مباشرة من بعد). ' +
      'عافاك تكلفو بكلشي.'
    );
  }
  if (locale === 'en') {
    return (
      'Hello, here is a photo of my electricity bill (or I will send you a voice note right after). ' +
      'Thank you for taking care of everything.'
    );
  }
  return (
    'Bonjour, voici une photo de ma facture d’électricité (ou je vous envoie un vocal juste après). ' +
    'Merci de vous occuper de tout.'
  );
}

/**
 * WJ3 — message pré-rempli pour la CAPTURE WhatsApp-first (/devis/mon-toit).
 * Le client envoie son estimation à Taqinor sur WhatsApp. Toujours complet,
 * jamais de blancs à éditer ; l'estimation (kWc + économies) est jointe quand
 * elle a pu être calculée honnêtement, sinon le message reste naturel sans
 * « undefined ». Aucun chiffre inventé : `kwcLabel`/`savingsLabel` viennent du
 * moteur (billEstimate) et sont absents si l'estimation est indisponible.
 * WJ50 — se termine par l'invitation au vocal (VOICE_NOTE_INVITE) : que
 * l'équipe ET le client sachent, dès l'ouverture du chat, qu'une photo de
 * facture peut suivre en vocal plutôt que d'attendre un champ d'upload.
 */
export function captureWhatsappText(p: {
  fullName: string;
  city: string;
  kwcLabel?: string;
  savingsLabel?: string;
  /** WREF — le code affiché sur l'écran de succès (« Votre référence :
   *  TQ-XXXX »). L'écran promettait « Mentionnez ce code sur WhatsApp » mais
   *  le message pré-rempli ne le portait JAMAIS : le client devait le retaper
   *  de mémoire. Optionnel : absent, le message reste identique à l'octet. */
  clientRef?: string;
}, locale: Locale = 'fr'): string {
  if (locale === 'en' || locale === 'ar') return captureWhatsappTextLocale(p, locale);
  const name = p.fullName.trim() || 'un visiteur';
  const city = p.city.trim();
  const parts: string[] = [
    `Bonjour, je suis ${name}${city ? ` (${city})` : ''}.`,
    "Je souhaite recevoir mon estimation solaire de taqinor.ma.",
  ];
  if (p.clientRef?.trim()) {
    parts.push(`Ma référence : ${p.clientRef.trim()}.`);
  }
  if (p.kwcLabel?.trim() || p.savingsLabel?.trim()) {
    const bits: string[] = [];
    if (p.kwcLabel?.trim()) bits.push(`installation estimée ${p.kwcLabel.trim()}`);
    if (p.savingsLabel?.trim()) bits.push(`économies estimées ${p.savingsLabel.trim()}`);
    parts.push(`Mon estimation préliminaire : ${bits.join(', ')}.`);
  }
  parts.push('Pouvez-vous me recontacter pour une étude ?');
  parts.push(VOICE_NOTE_INVITE);
  return parts.join(' ');
}

/** WAUD10 — invitation au vocal, EN et AR (le FR reste `VOICE_NOTE_INVITE`). */
const VOICE_NOTE_INVITE_LOC: Record<'en' | 'ar', string> = {
  en: 'I can also send you a voice note with a photo of my bill.',
  ar: 'يمكنني أيضاً أن أرسل لكم رسالة صوتية مع صورة فاتورتي. نقدر نصيفط ليكم أوديو مع تصويرة الفاتورة.',
};

/** WAUD10 (D-WAUD-3=a) — `captureWhatsappText` dans la langue de la page EN/AR. */
function captureWhatsappTextLocale(
  p: { fullName: string; city: string; kwcLabel?: string; savingsLabel?: string; clientRef?: string },
  locale: 'en' | 'ar',
): string {
  const en = locale === 'en';
  const name = p.fullName.trim();
  const city = p.city.trim();
  const parts: string[] = [];
  if (en) {
    parts.push(`Hello, I am ${name || 'a visitor'}${city ? ` (${city})` : ''}.`);
    parts.push('I would like to receive my solar estimate from taqinor.ma.');
  } else {
    parts.push(`مرحباً، أنا ${name || 'زائر'}${city ? ` (${city})` : ''}.`);
    parts.push('أرغب في الحصول على تقديري الشمسي من taqinor.ma.');
  }
  if (p.clientRef?.trim()) parts.push(en ? `My reference: ${p.clientRef.trim()}.` : `مرجعي: ${p.clientRef.trim()}.`);
  if (p.kwcLabel?.trim() || p.savingsLabel?.trim()) {
    const bits: string[] = [];
    if (p.kwcLabel?.trim()) bits.push(en ? `estimated installation ${p.kwcLabel.trim()}` : `تركيب مُقدَّر ${p.kwcLabel.trim()}`);
    if (p.savingsLabel?.trim()) bits.push(en ? `estimated savings ${p.savingsLabel.trim()}` : `توفير مُقدَّر ${p.savingsLabel.trim()}`);
    parts.push(en ? `My preliminary estimate: ${bits.join(', ')}.` : `تقديري الأولي: ${bits.join('، ')}.`);
  }
  parts.push(en ? 'Could you contact me for a study?' : 'هل يمكنكم التواصل معي لإجراء دراسة؟');
  parts.push(VOICE_NOTE_INVITE_LOC[locale]);
  return parts.join(' ');
}

/** WAUD10 — « Mon numéro : … » ajouté au lien d'abandon, dans la locale. */
export function monNumeroWhatsapp(phone: string, locale: Locale = 'fr'): string {
  if (locale === 'en') return ` My number: ${phone}.`;
  if (locale === 'ar') return ` رقمي: ${phone}.`;
  return ` Mon numéro : ${phone}.`;
}

/**
 * W350 — message pré-rempli PAR INSTALLATION pour le bouton WhatsApp d'une
 * étude de cas (/realisations/[slug]) : cite la ville + la puissance + la
 * référence EXACTES de l'étude que le visiteur est en train de lire, pour
 * qu'un partage réseaux sociaux (bio Instagram/TikTok → réalisation →
 * WhatsApp) arrive déjà contextualisé côté équipe. Aucun chiffre inventé :
 * les trois champs viennent tels quels de `Realisation` (lib/realisations.ts).
 */
export function caseStudyWhatsappText(p: { ville: string; kwc?: string; ref: string }, locale: Locale = 'fr'): string {
  if (locale === 'en') {
    const kwcEn = p.kwc ? `${p.kwc} ` : '';
    return (
      `Hello, I saw the ${kwcEn}installation in ${p.ville} (ref. ${p.ref}) on taqinor.ma ` +
      'and I would like a similar study for my own project.'
    );
  }
  if (locale === 'ar') {
    const kwcAr = p.kwc ? ` بقدرة ${p.kwc}` : '';
    return (
      `مرحباً، رأيت التركيبة${kwcAr} في ${p.ville} (المرجع ${p.ref}) على taqinor.ma ` +
      'وأرغب في دراسة مماثلة لمشروعي. عافاك تواصلو معايا.'
    );
  }
  // (2026-09) `kwc` absent (chantier filmé avant tout relevé de puissance,
  // ex. Bouskoura) : le segment "de X" est omis plutôt que d'écrire "de
  // undefined" — jamais de chiffre deviné dans un message pré-rempli.
  const kwcPart = p.kwc ? `de ${p.kwc} ` : '';
  return (
    `Bonjour, j'ai vu l'installation ${kwcPart}à ${p.ville} (réf. ${p.ref}) sur taqinor.ma ` +
    `et je souhaite une étude similaire pour mon propre projet.`
  );
}

/**
 * Message pré-rempli pour la régularisation Article 33 — TOUJOURS complet,
 * jamais de blancs « ___ » à éditer par le client. Les champs viennent du
 * mini-formulaire de la page Régularisation ; sans eux, le message reste
 * naturel et complet.
 */
export function regularizationWhatsappText(p?: { kwc?: string; ville?: string }, locale: Locale = 'fr'): string {
  const kwc = p?.kwc?.trim();
  const ville = p?.ville?.trim();
  if (locale === 'en') {
    return (
      'Hello, I have an existing solar installation and I would like to regularise it ' +
      'under Article 33 of Law 82-21. ' +
      (kwc ? `Approximate capacity: ${kwc} kWp. ` : 'Capacity: to be determined together. ') +
      (ville ? `City: ${ville}. ` : '') +
      'Please contact me to prepare the file.'
    );
  }
  if (locale === 'ar') {
    return (
      'مرحباً، لديّ تركيبة شمسية قائمة وأرغب في تسويتها في إطار المادة 33 من القانون 82-21. ' +
      (kwc ? `القدرة التقريبية: ${kwc} kWc. ` : 'القدرة: نحدّدها معاً. ') +
      (ville ? `المدينة: ${ville}. ` : '') +
      'المرجو التواصل معي لإعداد الملف. عافاك تواصلو معايا.'
    );
  }
  return (
    'Bonjour, je dispose d’une installation solaire existante et je souhaite la régulariser ' +
    'dans le cadre de l’Article 33 de la loi 82-21. ' +
    (kwc ? `Puissance approximative : ${kwc} kWc. ` : 'Puissance : à déterminer ensemble. ') +
    (ville ? `Ville : ${ville}. ` : '') +
    'Merci de me recontacter pour constituer le dossier.'
  );
}

/**
 * WJ50 — libellés FR de PAGE, pour que les CTA WhatsApp SITE-WIDE (bandeau
 * collant, pied de page) ouvrent un chat déjà informé de la page d'où le
 * client écrit, ET pour que chaque point d'entrée reste distinguable dans le
 * CRM (une équipe qui reçoit « … depuis la page Financement » sait tout de
 * suite dans quel contexte répondre). Reprend les libellés déjà en ligne
 * (nav / footer, `src/i18n/ui.ts`) plutôt que d'inventer un nouveau texte ;
 * clé = chemin RACINE (sans préfixe de locale, cf. `stripLocale`).
 *
 * INTENTIONNELLEMENT INCOMPLET : toute page absente de cette table retombe
 * sur `DEFAULT_PAGE_LABEL` (jamais un « undefined » ni un chemin technique
 * dans le message) plutôt que de bloquer sur une entrée manquante.
 */
const PAGE_LABELS_FR: Record<string, string> = {
  '/': "la page d'accueil",
  '/résidentiel': 'la page Résidentiel',
  '/professionnel': 'la page Professionnel',
  '/pompage-solaire': 'la page Pompage solaire',
  '/batteries-stockage': 'la page Batteries & stockage',
  '/maintenance-monitoring': 'la page Maintenance & monitoring',
  '/recharge-voiture-electrique-solaire': 'la page Recharge voiture électrique',
  '/regularization-article-33': 'la page Régularisation Loi 82-21',
  '/loi-82-21': 'la page Loi 82-21 expliquée',
  '/réalisations': 'la page Réalisations',
  '/realisations': 'la page Réalisations',
  '/équipement': 'la page Équipement',
  '/guides': 'la page Guides',
  '/faq': 'la page FAQ',
  '/pourquoi-taqinor': 'la page Pourquoi Taqinor',
  '/financement': 'la page Financement & rentabilité',
  '/marocains-du-monde': 'la page Marocains du monde',
  '/à-propos': 'la page À propos',
  '/contact': 'la page Contact',
  '/garanties': 'la page Nos garanties',
  '/nos-solutions': 'la page Nos solutions',
  '/impact-taqinor': 'la page Impact Taqinor',
  '/production-mesuree': 'la page Production mesurée',
  '/ensoleillement-maroc': 'la page Ensoleillement au Maroc',
  '/parrainage': 'la page Parrainage',
  '/prix-panneaux-solaires-maroc': 'la page Prix des panneaux solaires au Maroc',
  '/methodologie-estimation': "la page Méthodologie d'estimation",
  '/blog': 'le blog',
  '/produits': 'la page Produits',
  '/devis/mon-toit': 'le parcours devis « Mon toit »',
};

/** Repli neutre pour toute page absente de `PAGE_LABELS_FR` — jamais un chemin technique. */
const DEFAULT_PAGE_LABEL = 'le site taqinor.ma';

/**
 * Familles de pages DYNAMIQUES (préfixe de chemin racine → libellé) : villes,
 * études de cas, guides et articles de blog n'ont pas une entrée par slug
 * dans `PAGE_LABELS_FR` (des dizaines de villes/réalisations) — un préfixe
 * suffit pour rester distinguable dans le CRM sans devoir lister chaque page.
 */
const PAGE_LABEL_PREFIXES: readonly [string, string][] = [
  ['/installation-solaire-', 'une page Installation solaire par ville'],
  ['/realisations/', 'une étude de cas Réalisations'],
  ['/réalisations/', 'une étude de cas Réalisations'],
  ['/guides/', 'un guide'],
  ['/blog/', 'un article du blog'],
  ['/produits/', 'une fiche produit'],
];

/**
 * Libellé FR lisible pour un chemin de page (racine, SANS préfixe de locale —
 * appelant strippe via `stripLocale` avant d'appeler cette fonction). Ne
 * fabrique jamais un chemin technique brut : retombe sur `DEFAULT_PAGE_LABEL`.
 */
export function pageLabelFr(rootPath: string): string {
  const clean = (rootPath || '/').split(/[?#]/)[0].replace(/\/+$/, '') || '/';
  if (PAGE_LABELS_FR[clean]) return PAGE_LABELS_FR[clean];
  for (const [prefix, label] of PAGE_LABEL_PREFIXES) {
    if (clean.startsWith(prefix)) return label;
  }
  return DEFAULT_PAGE_LABEL;
}

/**
 * WJ50 — message pré-rempli des CTA WhatsApp SITE-WIDE génériques (bandeau
 * collant `StickyCta`, pied de page `Footer`) : toujours complet, jamais de
 * blanc à éditer, et cite la page pour que l'équipe ouvre le chat déjà
 * informée + que chaque point d'entrée reste distinguable dans le CRM.
 * Reste volontairement DISTINCT de `captureWhatsappText` (parcours devis,
 * avec estimation) : ici on n'a ni nom ni estimation, seulement la page.
 */
export function pageContextWhatsappText(rootPath: string, locale: Locale = 'fr'): string {
  if (locale === 'en') {
    return `Hello, I am writing from ${pageLabelLocale(rootPath, 'en')} on taqinor.ma and I would like a study for a solar installation.`;
  }
  if (locale === 'ar') {
    // Fus'ha d'abord (registre du site), puis UNE ligne darija (AGW402, relue par Reda — D-AGR-11).
    return (
      `مرحباً، أكتب إليكم من ${pageLabelLocale(rootPath, 'ar')} على taqinor.ma وأرغب في دراسة لتركيب نظام للطاقة الشمسية. ` +
      'عافاك تواصلو معايا.'
    );
  }
  return `Bonjour, je vous écris depuis ${pageLabelFr(rootPath)} sur taqinor.ma et je souhaite une étude pour une installation solaire.`;
}

/**
 * WAUD10 (D-WAUD-3=a) — libellés de page EN et AR : le message pré-rempli part
 * dans la langue de la page (l'équipe lit AR et EN), et chaque point d'entrée
 * reste distinguable dans le CRM comme en FR. Même clé (chemin racine) que
 * `PAGE_LABELS_FR` ; une page absente retombe sur un libellé neutre de la locale.
 */
const PAGE_LABELS_LOC: Record<'en' | 'ar', Record<string, string>> = {
  en: {
    '/': 'the home page',
    '/résidentiel': 'the Residential page',
    '/professionnel': 'the Business page',
    '/pompage-solaire': 'the Solar pumping page',
    '/batteries-stockage': 'the Batteries & storage page',
    '/maintenance-monitoring': 'the Maintenance & monitoring page',
    '/recharge-voiture-electrique-solaire': 'the EV charging page',
    '/regularization-article-33': 'the Law 82-21 regularisation page',
    '/loi-82-21': 'the Law 82-21 explained page',
    '/réalisations': 'the Projects page',
    '/realisations': 'the Projects page',
    '/équipement': 'the Equipment page',
    '/guides': 'the Guides page',
    '/faq': 'the FAQ page',
    '/pourquoi-taqinor': 'the Why Taqinor page',
    '/financement': 'the Financing & payback page',
    '/marocains-du-monde': 'the Moroccans abroad page',
    '/à-propos': 'the About page',
    '/contact': 'the Contact page',
    '/garanties': 'the Warranties page',
    '/nos-solutions': 'the Our solutions page',
    '/impact-taqinor': 'the Taqinor impact page',
    '/production-mesuree': 'the Measured production page',
    '/ensoleillement-maroc': 'the Sunshine in Morocco page',
    '/parrainage': 'the Referral page',
    '/prix-panneaux-solaires-maroc': 'the Solar panel prices in Morocco page',
    '/methodologie-estimation': 'the Estimation methodology page',
    '/blog': 'the blog',
    '/produits': 'the Products page',
    '/devis/mon-toit': 'the “My roof” quote journey',
  },
  ar: {
    '/': 'الصفحة الرئيسية',
    '/résidentiel': 'صفحة السكني',
    '/professionnel': 'صفحة المهنيين',
    '/pompage-solaire': 'صفحة الضخ الشمسي',
    '/batteries-stockage': 'صفحة البطاريات والتخزين',
    '/maintenance-monitoring': 'صفحة الصيانة والمراقبة',
    '/recharge-voiture-electrique-solaire': 'صفحة شحن السيارة الكهربائية',
    '/regularization-article-33': 'صفحة تسوية القانون 82-21',
    '/loi-82-21': 'صفحة شرح القانون 82-21',
    '/réalisations': 'صفحة الإنجازات',
    '/realisations': 'صفحة الإنجازات',
    '/équipement': 'صفحة المعدات',
    '/guides': 'صفحة الأدلة',
    '/faq': 'صفحة الأسئلة الشائعة',
    '/pourquoi-taqinor': 'صفحة لماذا تاكينور',
    '/financement': 'صفحة التمويل والمردودية',
    '/marocains-du-monde': 'صفحة مغاربة العالم',
    '/à-propos': 'صفحة من نحن',
    '/contact': 'صفحة الاتصال',
    '/garanties': 'صفحة الضمانات',
    '/nos-solutions': 'صفحة حلولنا',
    '/impact-taqinor': 'صفحة أثر تاكينور',
    '/production-mesuree': 'صفحة الإنتاج المقيس',
    '/ensoleillement-maroc': 'صفحة الإشعاع الشمسي في المغرب',
    '/parrainage': 'صفحة الإحالة',
    '/prix-panneaux-solaires-maroc': 'صفحة أسعار الألواح الشمسية في المغرب',
    '/methodologie-estimation': 'صفحة منهجية التقدير',
    '/blog': 'المدونة',
    '/produits': 'صفحة المنتجات',
    '/devis/mon-toit': 'مسار عرض السعر « سطحي »',
  },
};

const PAGE_LABEL_PREFIXES_LOC: Record<'en' | 'ar', readonly [string, string][]> = {
  en: [
    ['/installation-solaire-', 'a city installation page'],
    ['/realisations/', 'a project case study'],
    ['/réalisations/', 'a project case study'],
    ['/guides/', 'a guide'],
    ['/blog/', 'a blog article'],
    ['/produits/', 'a product sheet'],
  ],
  ar: [
    ['/installation-solaire-', 'صفحة تركيب في مدينة'],
    ['/realisations/', 'دراسة حالة من الإنجازات'],
    ['/réalisations/', 'دراسة حالة من الإنجازات'],
    ['/guides/', 'دليل'],
    ['/blog/', 'مقال من المدونة'],
    ['/produits/', 'بطاقة منتج'],
  ],
};

const DEFAULT_PAGE_LABEL_LOC: Record<'en' | 'ar', string> = { en: 'the website', ar: 'الموقع' };

/** Libellé de page dans la locale (FR : `pageLabelFr`, inchangé). */
export function pageLabelLocale(rootPath: string, locale: Locale): string {
  if (locale === 'fr') return pageLabelFr(rootPath);
  const clean = (rootPath || '/').split(/[?#]/)[0].replace(/\/+$/, '') || '/';
  const table = PAGE_LABELS_LOC[locale];
  if (table[clean]) return table[clean];
  for (const [prefix, label] of PAGE_LABEL_PREFIXES_LOC[locale]) {
    if (clean.startsWith(prefix)) return label;
  }
  return DEFAULT_PAGE_LABEL_LOC[locale];
}
