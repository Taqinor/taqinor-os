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
 * relues le 07/10/2026 au commit ci-dessous.
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

const SHA = '595d068b92dcf9eeff7f00e0fe916238d110fb1a';
const PLAN = 'docs/plans/PLAN_YANBOW_WEB.md';
/** Preuves des affirmations ajoutées avec les pages (YBW61-66), relues le 09/10/2026 à ce commit. */
const SHA_PAGES = 'd0cd0400aabc4086488b6e95afb1fbc6ea2016b8';

export const AFFIRMATIONS: Affirmation[] = [
  // ── SolarBow — parties prêtes pour la France (D-YBW-8) ─────────────────────
  {
    id: 'SB-CRM',
    produit: 'solarbow',
    texte_fr: 'Un CRM pensé pour les installateurs solaires : fiches prospects complètes, pipeline et relances planifiées.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/crm/models.py:520', 'backend/django_core/apps/crm/models.py:1156'],
    verifie_a_sha: SHA,
  },
  {
    id: 'SB-CALEPINAGE-3D',
    produit: 'solarbow',
    texte_fr: 'Un calepinage de toiture en vue 3D et en plan 2D.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['frontend/src/features/calepinage/atelier/OutilsVue.jsx:46', 'backend/django_core/apps/calepinage/models.py:41'],
    verifie_a_sha: SHA,
  },
  {
    id: 'SB-PENTE-IGN',
    produit: 'solarbow',
    texte_fr: 'Pour une toiture en France, une suggestion de pente tirée des données altimétriques de l’IGN.',
    statut: 'construit',
    france: 'oui',
    publiable: true,
    preuves: ['backend/django_core/apps/calepinage/services/lidar_ign.py:61', 'backend/django_core/apps/calepinage/services/lidar_ign.py:127'],
    verifie_a_sha: SHA,
  },
  {
    id: 'SB-PACKS-FR',
    produit: 'solarbow',
    texte_fr: 'Les dossiers déclaration préalable, Enedis et Consuel composés à partir des modèles de l’installateur.',
    statut: 'construit',
    france: 'oui',
    publiable: true,
    preuves: ['backend/django_core/apps/calepinage/services/reglementaire.py:643', 'backend/django_core/apps/calepinage/services/reglementaire.py:247'],
    verifie_a_sha: SHA,
  },
  {
    id: 'SB-DEVIS-PDF',
    produit: 'solarbow',
    texte_fr: 'Des devis et une proposition commerciale en PDF générés depuis l’étude.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py:49'],
    verifie_a_sha: SHA,
  },
  {
    id: 'SB-ENTREPRISE-REELLE',
    produit: 'solarbow',
    texte_fr: 'Construit au sein d’une vraie entreprise d’installation.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:63`],
    verifie_a_sha: SHA,
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
    verifie_a_sha: SHA,
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
    verifie_a_sha: SHA,
  },
  // ── MarketingBow — moteur de campagnes seulement (D-YBW-7) ─────────────────
  {
    id: 'MB-CREATION-EN-PAUSE',
    produit: 'marketingbow',
    texte_fr: 'Campagnes, ensembles et publicités sont toujours créés en pause ; une personne les active.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/meta_client.py:32', 'backend/django_core/apps/adsengine/meta_client.py:695'],
    verifie_a_sha: SHA,
  },
  {
    id: 'MB-PROPOSE-APPROUVE',
    produit: 'marketingbow',
    texte_fr: 'Chaque changement est d’abord proposé, puis approuvé par une personne, avant d’être appliqué.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/models.py:714', 'backend/django_core/apps/adsengine/services.py:206'],
    verifie_a_sha: SHA,
  },
  {
    id: 'MB-COUPE-CIRCUIT',
    produit: 'marketingbow',
    texte_fr: 'Des garde-fous et un coupe-circuit global qui met tout en pause.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: ['backend/django_core/apps/adsengine/flightrunner.py:204'],
    verifie_a_sha: SHA,
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
    verifie_a_sha: SHA,
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
    verifie_a_sha: SHA,
  },
  // ── Sur mesure (YBW64) ──────────────────────────────────────────────────────
  {
    id: 'SM-OFFRE',
    produit: 'sur_mesure',
    texte_fr: 'Au-delà de nos deux produits, nous construisons des logiciels sur mesure pour les entreprises.',
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
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:43`, 'backend/django_core/apps/adsengine/meta_client.py:695', 'backend/django_core/apps/crm/models.py:520'],
    verifie_a_sha: SHA_PAGES,
  },
  {
    id: 'YB-REPONSE-HUMAINE',
    produit: 'yanbow',
    texte_fr: 'Une personne de l’équipe lit votre demande et vous répond.',
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
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:42`, `${PLAN}:54`],
    verifie_a_sha: SHA_PAGES,
  },
  // ── YanBow — le nom ─────────────────────────────────────────────────────────
  {
    id: 'YB-NOM-SOURCE',
    produit: 'yanbow',
    texte_fr: 'YanBow vient de ينبوع, la source.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:193`],
    sources_externes: [{ url: 'https://en.wiktionary.org/wiki/ينبوع', releve: 'ينبوع (yanbūʕ) : « spring, creek, fountain »', lu_le: '2026-10-07' }],
    verifie_a_sha: SHA,
  },
  {
    id: 'YB-NOM-YAN',
    produit: 'yanbow',
    texte_fr: '« Yan » signifie « un » en amazigh.',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:193`],
    sources_externes: [{ url: 'https://en.wiktionary.org/wiki/yan', releve: 'tachelhit : yan (ⵢⴰⵏ, يان) « one »', lu_le: '2026-10-07' }],
    verifie_a_sha: SHA,
  },
  {
    id: 'YB-SLOGAN',
    produit: 'yanbow',
    texte_fr: 'Your Arrow Needs 1Bow',
    statut: 'construit',
    france: 'neutre',
    publiable: true,
    preuves: [`${PLAN}:72`],
    verifie_a_sha: SHA,
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
