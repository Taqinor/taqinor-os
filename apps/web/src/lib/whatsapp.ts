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
}): string {
  const name = p.fullName.trim() || 'un visiteur';
  const city = p.city.trim();
  const parts: string[] = [
    `Bonjour, je suis ${name}${city ? ` (${city})` : ''}.`,
    "Je souhaite recevoir mon estimation solaire de taqinor.ma.",
  ];
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

/**
 * W350 — message pré-rempli PAR INSTALLATION pour le bouton WhatsApp d'une
 * étude de cas (/realisations/[slug]) : cite la ville + la puissance + la
 * référence EXACTES de l'étude que le visiteur est en train de lire, pour
 * qu'un partage réseaux sociaux (bio Instagram/TikTok → réalisation →
 * WhatsApp) arrive déjà contextualisé côté équipe. Aucun chiffre inventé :
 * les trois champs viennent tels quels de `Realisation` (lib/realisations.ts).
 */
export function caseStudyWhatsappText(p: { ville: string; kwc: string; ref: string }): string {
  return (
    `Bonjour, j'ai vu l'installation de ${p.kwc} à ${p.ville} (réf. ${p.ref}) sur taqinor.ma ` +
    `et je souhaite une étude similaire pour mon propre projet.`
  );
}

/**
 * Message pré-rempli pour la régularisation Article 33 — TOUJOURS complet,
 * jamais de blancs « ___ » à éditer par le client. Les champs viennent du
 * mini-formulaire de la page Régularisation ; sans eux, le message reste
 * naturel et complet.
 */
export function regularizationWhatsappText(p?: { kwc?: string; ville?: string }): string {
  const kwc = p?.kwc?.trim();
  const ville = p?.ville?.trim();
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
export function pageContextWhatsappText(rootPath: string): string {
  return `Bonjour, je vous écris depuis ${pageLabelFr(rootPath)} sur taqinor.ma et je souhaite une étude pour une installation solaire.`;
}
