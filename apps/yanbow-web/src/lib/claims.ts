/**
 * Registre des AFFIRMATIONS publiques (YBW18) — source unique, avec preuves.
 *
 * Toute phrase publique qui affirme un fait sur YanBow, SolarBow ou
 * MarketingBow cite une affirmation d'ici via `cite('ID')` (dans un
 * dictionnaire). `cite` LÈVE si l'identifiant est inconnu ou non publiable ;
 * `scripts/check-claims.mjs` le vérifie aussi sans build.
 *
 * `preuves` = `chemin:ligne` relatifs à la RACINE DU DÉPÔT (le fichier doit
 * exister et compter au moins cette ligne). `verifie_a_sha` = le commit auquel
 * les preuves ont été relues ; `check-claims --stale` liste les affirmations
 * dont un fichier de preuve a changé depuis (bloque le lancement, YBW85) :
 * relire la preuve, corriger si besoin, puis avancer le sha.
 *
 * Amorcé depuis les « Faits établis » du plan (vérifiés le 06/10/2026), preuves
 * relues le 07/10/2026, puis TOUTES relues le 09/10/2026 (SHA_PAGES).
 */

export type Statut = 'construit' | 'construit_non_prouve' | 'prevu';
export type Produit = 'yanbow' | 'solarbow' | 'marketingbow' | 'sur_mesure';

export interface SourceExterne {
  url: string;
  /** Ce que la source dit, tel que relevé. */
  releve: string;
  lu_le: string;
}

export interface Affirmation {
  id: string;
  produit: Produit;
  texte_fr: string;
  texte_en?: string;
  statut: Statut;
  /** Pertinence pour le marché français (D-YBW-8). */
  france: 'oui' | 'neutre' | 'non';
  publiable: boolean;
  /** Obligatoire quand `publiable` est faux. */
  raison_non_publiable?: string;
  preuves: string[];
  sources_externes?: SourceExterne[];
  verifie_a_sha: string;
}

const PLAN = 'docs/plans/PLAN_YANBOW_WEB.md';
/**
 * Commit auquel TOUTES les preuves ont été relues (09/10/2026, YBW61-67 : preuves
 * déplacées par l'évolution du code re-pointées — packs France, création en
 * pause, proposer/approuver, sens du nom).
 */
const SHA_PAGES = '0588a29c87b6596918e04533c2adb4f948c9c3f5';

export const AFFIRMATIONS: Affirmation[] = [
  // ── SolarBow — parties prêtes pour la France (D-YBW-8) ─────────────────────
  {
    id: 'SB-CRM',
    produit: 'solarbow',
    texte_fr: 'Un CRM pensé pour les installateurs solaires : fiches prospects complètes, pipeline et relances planifiées.',
    texte_en: 'A CRM built for solar installers: complete prospect records, pipeline and scheduled follow-ups.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/crm/models.py:520', 'backend/django_core/apps/crm/models.py:1156'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-CALEPINAGE-3D',
    produit: 'solarbow',
    texte_fr: 'Un calepinage de toiture en vue 3D et en plan 2D.',
    texte_en: 'A roof panel layout in 3D view and 2D plan.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['frontend/src/features/calepinage/atelier/OutilsVue.jsx:46', 'backend/django_core/apps/calepinage/models.py:41'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-PENTE-IGN',
    produit: 'solarbow',
    texte_fr: 'Pour une toiture en France, une suggestion de pente tirée des données altimétriques de l’IGN.',
    texte_en: 'For a roof in France, a pitch suggestion drawn from IGN elevation data.',
    statut: 'construit',
    france: 'oui',
    publiable: true,
    preuves: ['backend/django_core/apps/calepinage/services/lidar_ign.py:61', 'backend/django_core/apps/calepinage/services/lidar_ign.py:127'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-PACKS-FR',
    produit: 'solarbow',
    texte_fr: 'Les dossiers déclaration préalable, Enedis et Consuel composés à partir des modèles de l’installateur.',
    texte_en: 'Prior declaration, Enedis and Consuel files assembled from the installer’s templates.',
    statut: 'construit',
    france: 'oui',
    publiable: true,
    preuves: ['backend/django_core/apps/calepinage/services/reglementaire.py:866', 'backend/django_core/apps/calepinage/services/reglementaire.py:918'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-DEVIS-PDF',
    produit: 'solarbow',
    texte_fr: 'Des devis et une proposition commerciale en PDF générés depuis l’étude.',
    texte_en: 'Quotes and a commercial proposal as PDFs generated from the study.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py:49'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-ENTREPRISE-REELLE',
    produit: 'solarbow',
    texte_fr: 'Construit au sein d’une vraie entreprise d’installation.',
    texte_en: 'Built inside a real installation company.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:63`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-PRET-FRANCE',
    produit: 'solarbow',
    texte_fr: 'SolarBow est prêt pour la France.',
    statut: 'construit_non_prouve',
    france: 'oui',
    publiable: false,
    raison_non_publiable: 'Interdit par D-YBW-8 : montants en MAD, aucune règle tarifaire française (TURPE, obligation d’achat, aides) dans le code.',
    preuves: [`${PLAN}:105`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-NON-PUBLIABLES',
    produit: 'solarbow',
    texte_fr: 'Signature électronique, facture électronique Factur-X, paiement en ligne, suivi de production automatique, messages WhatsApp automatiques, agent de requêtes, garanties de sécurité.',
    statut: 'prevu',
    france: 'neutre',
    publiable: false,
    raison_non_publiable: 'Non construit ou non prouvé (faits établis du 06/10 : ADOC63-68 ouverts, AANA/ADOC sécurité ouverts) ; section sécurité GATED (YBW92).',
    preuves: [`${PLAN}:105`],
    verifie_a_sha: SHA_PAGES,
  },
  // ── MarketingBow — moteur de campagnes seulement (D-YBW-7) ─────────────────
  {
    id: 'MB-CREATION-EN-PAUSE',
    produit: 'marketingbow',
    texte_fr: 'Campagnes, ensembles et publicités sont toujours créés en pause ; une personne les active.',
    texte_en: 'Campaigns, ad sets and ads are always created paused; a person activates them.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/meta_client.py:32', 'backend/django_core/apps/adsengine/meta_client.py:741'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-PROPOSE-APPROUVE',
    produit: 'marketingbow',
    texte_fr: 'Chaque changement est d’abord proposé, puis approuvé par une personne, avant d’être appliqué.',
    texte_en: 'Every change is first proposed, then approved by a person, before it is applied.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/services.py:228', 'backend/django_core/apps/adsengine/services.py:1880'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-COUPE-CIRCUIT',
    produit: 'marketingbow',
    texte_fr: 'Des garde-fous et un coupe-circuit global qui met tout en pause.',
    texte_en: 'Guardrails and a global circuit breaker that pauses everything.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/flightrunner.py:204'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-EN-SERVICE',
    produit: 'marketingbow',
    texte_fr: 'MarketingBow est en service.',
    statut: 'construit_non_prouve',
    france: 'neutre',
    publiable: false,
    raison_non_publiable: 'Jamais tourné de bout en bout en production via l’application (audit du 28/09) ; jamais dit « en service ».',
    preuves: [`${PLAN}:109`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-CREATIF-IA',
    produit: 'marketingbow',
    texte_fr: 'Génération d’images et de vidéos publicitaires par IA.',
    statut: 'construit_non_prouve',
    france: 'neutre',
    publiable: false,
    raison_non_publiable: 'Aucune clé active : jamais promise (faits établis du 06/10).',
    preuves: [`${PLAN}:110`],
    verifie_a_sha: SHA_PAGES,
  },
  // ── SolarBow — page produit (YBW62) ─────────────────────────────────────────
  {
    id: 'SB-POUR-QUI',
    produit: 'solarbow',
    texte_fr: 'Le logiciel des installateurs solaires, du premier contact à la proposition commerciale.',
    texte_en: 'The software for solar installers, from first contact to the commercial proposal.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [
      'backend/django_core/apps/crm/models.py:520',
      'backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py:49',
      `${PLAN}:60`,
    ],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-INTERFACE-FR',
    produit: 'solarbow',
    texte_fr: 'L’interface est en français.',
    texte_en: 'The interface is in French.',
    statut: 'construit',
    france: 'oui',
    publiable: true,
    preuves: [`${PLAN}:103`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SB-WHATSAPP-LIEN',
    produit: 'solarbow',
    texte_fr: 'Une relance WhatsApp s’ouvre en un clic ; c’est l’installateur qui envoie le message.',
    texte_en: 'A WhatsApp follow-up opens in one click; the installer sends the message.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['frontend/src/features/crm/relances/PanneauProposerVisite.jsx:73'],
    verifie_a_sha: SHA_PAGES,
  },
  // ── MarketingBow — page produit (YBW63) ─────────────────────────────────────
  {
    id: 'MB-POUR-QUI',
    produit: 'marketingbow',
    texte_fr: 'Un moteur de campagnes publicitaires Meta où une personne valide chaque changement.',
    texte_en: 'A Meta advertising campaign engine where a person validates every change.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/meta_client.py:741', 'backend/django_core/apps/adsengine/services.py:1880'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-OPTION',
    produit: 'marketingbow',
    texte_fr: 'Proposé en option, après une démonstration.',
    texte_en: 'Offered as an option, after a demonstration.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:59`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-PERMISSIONS',
    produit: 'marketingbow',
    texte_fr: 'Consulter, préparer et approuver sont trois droits distincts.',
    texte_en: 'Viewing, preparing and approving are three separate rights.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/views.py:166', 'backend/django_core/apps/adsengine/views.py:269', 'backend/django_core/apps/adsengine/views.py:1779'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-CHIFFRES-CITES',
    produit: 'marketingbow',
    texte_fr:
      'Un chiffre dans un texte généré doit correspondre à un fait que vous avez publié, sinon le texte est bloqué ; le texte attend ensuite une validation humaine.',
    texte_en: 'A figure in a generated text must match a fact you have published, otherwise the text is blocked; the text then waits for human validation.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/claim_check.py:8', 'backend/django_core/apps/adsengine/groundedness.py:12'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'MB-PROPRIETE',
    produit: 'marketingbow',
    texte_fr: 'Vous gardez la propriété de votre Page et de votre compte publicitaire Meta : nous y travaillons avec un accès partenaire que vous nous accordez.',
    texte_en: 'You keep ownership of your Page and your Meta ad account: we work in it with partner access that you grant us.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['docs/adsengine-tenant-onboarding.md:17', 'docs/adsengine-tenant-onboarding.md:20'],
    verifie_a_sha: SHA_PAGES,
  },
  // ── Sur mesure (YBW64) ──────────────────────────────────────────────────────
  {
    id: 'SM-OFFRE',
    produit: 'sur_mesure',
    texte_fr: 'Au-delà de nos deux produits, nous construisons des logiciels sur mesure pour les entreprises.',
    texte_en: 'Beyond our two products, we build custom software for companies.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:54`, `${PLAN}:42`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'SM-DEMARCHE',
    produit: 'sur_mesure',
    texte_fr: 'On part du besoin réel, on montre un prototype, puis on met le logiciel en service et on l’exploite avec vous.',
    texte_en: 'We start from the real need, show a prototype, then put the software into service and run it with you.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:54`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'YB-DEUX-PRODUITS',
    produit: 'yanbow',
    texte_fr: 'Nos deux produits, SolarBow et MarketingBow, sont construits.',
    texte_en: 'Our two products, SolarBow and MarketingBow, are built.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:43`, 'backend/django_core/apps/adsengine/meta_client.py:741', 'backend/django_core/apps/crm/models.py:520'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'YB-REPONSE-HUMAINE',
    produit: 'yanbow',
    texte_fr: 'Une personne de l’équipe lit votre demande et vous répond.',
    texte_en: 'A member of the team reads your request and replies.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/crm/webhooks.py:3354', `${PLAN}:56`],
    verifie_a_sha: SHA_PAGES,
  },
  // ── YanBow — la société (YBW65) ─────────────────────────────────────────────
  {
    id: 'YB-METIER',
    produit: 'yanbow',
    texte_fr: 'Nous construisons des logiciels métier pour les entreprises.',
    texte_en: 'We build business software for companies.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:42`, `${PLAN}:54`],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'YB-POSITIONNEMENT',
    produit: 'yanbow',
    texte_fr:
      'Deux produits construits, SolarBow pour les installateurs solaires et MarketingBow pour les campagnes publicitaires, et du sur-mesure pour le reste.',
    texte_en: 'Two built products, SolarBow for solar installers and MarketingBow for advertising campaigns, and custom work for the rest.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:43`, `${PLAN}:44`, `${PLAN}:54`],
    verifie_a_sha: SHA_PAGES,
  },
  // ── YanBow — le nom ─────────────────────────────────────────────────────────
  {
    id: 'YB-NOM-SOURCE',
    produit: 'yanbow',
    texte_fr: 'YanBow vient de ينبوع, la source.',
    texte_en: 'YanBow comes from ينبوع, the source.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:198`],
    sources_externes: [{ url: 'https://en.wiktionary.org/wiki/ينبوع', releve: 'ينبوع (yanbūʕ) : « spring, creek, fountain »', lu_le: '2026-10-07' }],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'YB-NOM-YAN',
    produit: 'yanbow',
    texte_fr: '« Yan » signifie « un » en amazigh.',
    texte_en: '“Yan” means “one” in Amazigh.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:198`],
    sources_externes: [{ url: 'https://en.wiktionary.org/wiki/yan', releve: 'tachelhit : yan (ⵢⴰⵏ, يان) « one »', lu_le: '2026-10-07' }],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'YB-SLOGAN',
    produit: 'yanbow',
    texte_fr: 'Your Arrow Needs 1Bow',
    texte_en: 'Your Arrow Needs 1Bow',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:72`],
    verifie_a_sha: SHA_PAGES,
  },
];

const PAR_ID = new Map(AFFIRMATIONS.map((a) => [a.id, a]));

/** L'affirmation `id`, si elle existe et est publiable ; LÈVE sinon. */
export function cite(id: string): Affirmation {
  const a = PAR_ID.get(id);
  if (!a) throw new Error(`affirmation inconnue : ${id}`);
  if (!a.publiable) throw new Error(`affirmation non publiable : ${id} — ${a.raison_non_publiable ?? ''}`);
  return a;
}
