/**
 * NAP canonique (Name / Address / Phone) — source unique de vérité.
 * Toute mention du nom, du téléphone, de l'email ou de l'URL sur le site
 * DOIT passer par cette constante (cohérence Google Business Profile).
 *
 * Valeurs réelles confirmées par Reda (2026-06-12) — phoneDisplay reste
 * caractère pour caractère identique à l'affichage GBP : « 0661850410 ».
 *
 * W298 (2026-07-03) — réconciliation byte-for-byte avec la fiche Google
 * Business Profile évaluée : EN ATTENTE de WG5 (confirmation GBP), non
 * résolue ici. Aucune valeur ci-dessous n'a été modifiée par cette tâche.
 */
export const NAP = {
  name: 'Taqinor', // pas de suffixe SARL — aligné GBP
  url: 'https://taqinor.ma',
  phone: '+212661850410', // NAP_PHONE : JSON-LD, liens tel: — PERMANENT (GBP), jamais reformaté
  phoneDisplay: '0661850410', // format GBP exact (pages contact / mentions légales) — ne pas reformater
  phoneDisplayIntl: '+212 6 61 85 04 10', // affichage lisible en-tête + pied de page (W10) ; même numéro, lien tel: inchangé
  email: 'contact@taqinor.ma', // 17/10/2026 : taqinor.com n'existe pas (NXDOMAIN) — boîte M365 réelle ; aligner la fiche GBP à la main
  // Zone de service (pas d'adresse postale physique — mode service-area)
  serviceArea: ['Casablanca', 'Rabat', 'Marrakech', 'Tanger', 'Agadir', 'Maroc'],
  // Liste de services — doit correspondre EXACTEMENT au Google Business Profile
  services: [
    'Installation solaire résidentielle',
    'Installation solaire industrielle',
    'Batteries de stockage',
    'Étude et dimensionnement',
    'Monitoring',
    'Régularisation Loi 82-21 — Article 33',
  ],
} as const;

/**
 * Identité légale publiée — MÊME source pour /mentions-legales et pour la page
 * de proposition (PREVIEW v2, fondateur Reda 2026-09-16). Les checklists
 * anti-arnaque marocaines demandent toutes la même chose avant de signer : une
 * raison sociale, un RC, un ICE — vérifiables au registre. Ces valeurs sont
 * celles du dossier d'entreprise déjà publiées sur /mentions-legales ; elles
 * sont DÉPLACÉES ici, pas réécrites, pour qu'aucune page ne puisse en publier
 * une variante. Pas d'adresse postale : décision propriétaire (zone de service).
 * Le gérant N'EST PAS repris dans cette constante — il reste sur la page
 * légale, et aucun prénom ne doit apparaître dans un gabarit client.
 */
export const LEGAL_IDENTITY = {
  raisonSociale: 'TAQINOR Solutions SARLAU',
  formeJuridique: 'Société à responsabilité limitée à associé unique',
  rc: 'RC 691213 — Tribunal de Commerce de Casablanca',
  rcCourt: 'RC 691213 Casablanca',
  ice: '003799642000067',
  capital: '100 000,00 MAD',
  gerant: 'M. Reda Kasri',
} as const;

/** APDF107 — titre « Qui est … ? » de la marque (clé `emetteur` absente, ou `nom` vide). */
const TITRE_TAQINOR = { fr: 'Qui est Taqinor ?', en: 'Who is Taqinor?', ar: 'من هي تاقينور؟' };

/**
 * APDF107 (C-APDF-VER-007) — l'identité du bloc « Qui est … ? » de la proposition :
 * celle de la société ÉMETTRICE servie avec elle (`emetteur`, APDF110, lu par
 * `company_identity` côté serveur). Clé ABSENTE (ancien backend) ⇒ LEGAL_IDENTITY,
 * le rendu d'aujourd'hui ; `nom` vide ⇒ `bloc: null` (carte omise, jamais la
 * constante). Ligne légale en trois langues, parts vides omises ; RC/ICE sont des
 * sigles ; le montant arabe est enfermé dans un ISOLAT bidi (U+2066 … U+2069) :
 * sans lui, « رأس المال 100 000,00 MAD » se rendait « 000,00 100 رأس المال MAD »
 * dans le paragraphe `dir="ltr"` (constaté au rendu, PREVIEW-V3-FIX audit C4).
 */
export function identiteEmetteur(servie: unknown) {
  const brut = (servie && typeof servie === 'object' ? servie : {}) as Record<string, unknown>;
  const lu = (cle: string) => (typeof brut[cle] === 'string' ? (brut[cle] as string).trim() : '');
  const ligne = (rc: string, ice: string, capital: string) => {
    const joindre = (cap: string) => [rc, ice && `ICE ${ice}`, capital && cap].filter(Boolean).join(' · ');
    return { fr: joindre(`Capital ${capital}`), en: joindre(`Share capital ${capital}`), ar: joindre(`رأس المال \u2066${capital}\u2069`) };
  };
  const { raisonSociale, rcCourt, ice, capital } = LEGAL_IDENTITY;
  if (servie === undefined) return { titre: TITRE_TAQINOR, bloc: { raisonSociale, ligne: ligne(rcCourt, ice, capital) } };
  const nom = lu('nom'), forme = lu('forme_juridique');
  if (!nom) return { titre: TITRE_TAQINOR, bloc: null };
  return {
    titre: { fr: `Qui est ${nom} ?`, en: `Who is ${nom}?`, ar: `من هي \u2066${nom}\u2069؟` },
    bloc: {
      raisonSociale: forme && !nom.toUpperCase().includes(forme.toUpperCase()) ? `${nom} ${forme}` : nom,
      ligne: ligne(lu('rc') && `RC ${lu('rc')}`, lu('ice'), lu('capital_social')),
    },
  };
}

/**
 * W288 — URLs d'entité (`sameAs`) pour le JSON-LD LocalBusiness : fiche Google
 * Business Profile + profils sociaux actifs. LIVRÉ VIDE (même règle
 * d'intégrité que testimonials.ts) — tant que WG5 (GBP) / WG8 (réseaux
 * sociaux) ne fournissent pas de vraies URLs, `Layout.astro` n'émet aucun
 * `sameAs`. Ne jamais fabriquer de placeholder ici.
 */
export const SAME_AS: readonly string[] = [];

/**
 * Cible des deeplinks wa.me et de la remise d'étude du diagnostic —
 * DISTINCTE du téléphone NAP : aujourd'hui le même numéro, demain la
 * ligne de Meryem. Chiffres uniquement, avec indicatif pays.
 * (Surchargable au déploiement via l'env WHATSAPP_NUMBER du Worker.)
 */
export const WHATSAPP_LEADS = '212661850410';

/**
 * W340 — Espace client réel : le portail public Deye Cloud (login), la même
 * plateforme de monitoring déjà nommée sur /maintenance-monitoring et
 * /équipement (« accès Deye Cloud personnel »). Aucun portail client Taqinor
 * maison n'existe : ceci EST l'accès réel remis à chaque client à la mise en
 * service — pas un placeholder, pas une page fabriquée.
 */
export const DEYE_CLOUD_URL = 'https://www.deyecloud.com/login';
