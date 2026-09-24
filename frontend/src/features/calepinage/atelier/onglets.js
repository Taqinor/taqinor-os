import { lazy } from 'react'

/* ============================================================================
   CALX1 — LE REGISTRE DÉCLARATIF DES ONGLETS DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. `module.config.jsx` déclarait treize chemins
   profonds (`/calepinage/:id/fiches`, `.../pompage`, `.../plan`…) qu'AUCUN
   `Link` ni `navigate` du dépôt ne visait : treize écrans livrés, servis par le
   routeur, et introuvables par un utilisateur. L'atelier, lui, n'offrait que
   deux liens écrits en dur (variantes, photos). Un écran qu'on ne peut pas
   ouvrir n'existe pas — c'est exactement l'incident du 03/08/2026 que garde
   `scripts/check_ecrans_atteignables.py`.

   SURFACE APPEND-ONLY (décision D-CALX 13, déclarée dans
   `scripts/plan_lanes.py::_APPEND_ONLY_SUFFIXES` par CALX2). Un panneau neuf
   s'AJOUTE **en fin** du tableau `ONGLETS`, sur UNE ligne, terminée par son
   commentaire `// CALX<id>`. Jamais une réécriture, jamais un tri, jamais une
   insertion au milieu : deux lanes qui réordonnent ce fichier se fondent en une
   seule (mesuré : 13 des 16 fusions du groupe CALX venaient de ces surfaces) et
   le conflit de fold est garanti. L'ORDRE D'AFFICHAGE est porté par le champ
   `ordre` — pas par la position dans le tableau —, ce qui permet d'insérer un
   onglet entre deux autres (pas de 10) sans toucher une ligne existante.

   FORME D'UNE ENTRÉE, stable (les lanes suivantes s'y conforment) :
     { cle, libelle, groupe, ordre, composant }
       cle       — segment d'URL, EXACTEMENT celui de la route profonde
                   `/calepinage/:id/<cle>` de `module.config.jsx`, et valeur du
                   paramètre `?onglet=<cle>` de l'atelier ;
       libelle   — le texte affiché sur l'onglet, EN FRANÇAIS (D-CALX 10) ;
       groupe    — l'intertitre sous lequel l'onglet se range dans le rail ;
       ordre     — entier croissant (pas de 10) ; il seul décide de la place ;
       composant — `lazy(() => import('<chemin littéral>'))`. Le chemin reste
                   LITTÉRAL : c'est ce que suit l'analyse statique de
                   `check_ecrans_atteignables.py` (et le découpage de Vite).

   CE FICHIER NE REND RIEN et ne décide de rien d'autre : `atelier/Rail.jsx` le
   lit, l'affiche et monte le composant de l'onglet actif. Les treize routes
   profondes RESTENT servies telles quelles — elles sont les liens profonds qui
   ouvrent le même onglet.
   ========================================================================== */

/** Nom du paramètre d'URL qui pilote l'onglet actif de l'atelier. */
export const PARAM_ONGLET = 'onglet'

/* APPEND-ONLY : on ajoute EN FIN, une ligne par panneau, `// CALX<id>` compris. */
export const ONGLETS = [
  { cle: 'plan', libelle: 'Plan importé', groupe: 'Site', ordre: 10, composant: lazy(() => import('../PlanImporteCalage')) }, // CALX1
  { cle: 'pente', libelle: 'Pente', groupe: 'Site', ordre: 20, composant: lazy(() => import('../SaisiePente')) }, // CALX1
  { cle: 'terrain', libelle: 'Terrain', groupe: 'Site', ordre: 30, composant: lazy(() => import('../ModeTerrain')) }, // CALX1
  { cle: 'ombriere', libelle: 'Ombrière', groupe: 'Site', ordre: 40, composant: lazy(() => import('../Ombriere')) }, // CALX1
  { cle: 'horizon', libelle: 'Horizon lointain', groupe: 'Site', ordre: 50, composant: lazy(() => import('../HorizonPanel')) }, // CALX1
  { cle: 'course-soleil', libelle: 'Course du soleil', groupe: 'Site', ordre: 60, composant: lazy(() => import('../CourseSoleil')) }, // CALX1
  { cle: 'fiches', libelle: 'Fiches équipements', groupe: 'Système', ordre: 70, composant: lazy(() => import('../equipements/FichesIncompletes')) }, // CALX1
  { cle: 'affectation', libelle: 'Affectation des chaînes', groupe: 'Système', ordre: 80, composant: lazy(() => import('../plan/AffectationChaines')) }, // CALX1
  { cle: 'schema', libelle: 'Schéma unifilaire', groupe: 'Système', ordre: 90, composant: lazy(() => import('../SchemaUnifilairePanel')) }, // CALX1
  { cle: 'pompage', libelle: 'Pompage', groupe: 'Système', ordre: 100, composant: lazy(() => import('../pompage/PompagePanel')) }, // CALX1
  { cle: 'production', libelle: 'Production', groupe: 'Résultats', ordre: 110, composant: lazy(() => import('../production/PanneauProduction')) }, // CALX1
  { cle: 'pertes', libelle: 'Pertes', groupe: 'Résultats', ordre: 120, composant: lazy(() => import('../production/DiagrammePertes')) }, // CALX1
  { cle: 'dossiers', libelle: 'Dossiers réglementaires', groupe: 'Dossiers', ordre: 130, composant: lazy(() => import('../DossiersReglementaires')) }, // CALX1
  { cle: 'documents', libelle: 'Documents', groupe: 'Dossiers', ordre: 140, composant: lazy(() => import('../documents/PanneauDocuments')) }, // CALX19

  { cle: 'postes-pertes', libelle: 'Postes de pertes', groupe: 'Résultats', ordre: 150, composant: lazy(() => import('./PanneauPertes')) }, // CALX18
  { cle: 'releve', libelle: 'Relevé terrain', groupe: 'Site', ordre: 160, composant: lazy(() => import('./PanneauReleve')) }, // CALX25

  { cle: 'activite', libelle: 'Activité', groupe: 'Dossiers', ordre: 170, composant: lazy(() => import('./PanneauActivite')) }, // CALX31
  { cle: 'versions', libelle: 'Versions', groupe: 'Dossiers', ordre: 180, composant: lazy(() => import('./PanneauVersions')) }, // CALX36

  { cle: 'masse-lestage', libelle: 'Masse & lestage', groupe: 'Système', ordre: 190, composant: lazy(() => import('./PanneauMasseLestage')) }, // CALX17

  { cle: 'series', libelle: 'Séries', groupe: 'Résultats', ordre: 200, composant: lazy(() => import('./PanneauSeries')) }, // CALX6

  { cle: 'batterie', libelle: 'Batterie', groupe: 'Résultats', ordre: 210, composant: lazy(() => import('./PanneauBatterie')) }, // CALX14

  { cle: 'equipements-electriques', libelle: 'Équipements électriques', groupe: 'Système', ordre: 220, composant: lazy(() => import('../electrique/EquipementsElectriques')) }, // CALX222
  { cle: 'cheminement-cables', libelle: 'Cheminement & câbles', groupe: 'Système', ordre: 230, composant: lazy(() => import('../electrique/CheminementCables')) }, // CALX229
  { cle: 'raccordement', libelle: 'Raccordement réseau', groupe: 'Système', ordre: 240, composant: lazy(() => import('../electrique/Raccordement')) }, // CALX244

  { cle: 'coupe', libelle: 'Coupe', groupe: 'Site', ordre: 65, composant: lazy(() => import('./OngletCoupeRangees')) }, // CALX121

  { cle: 'verdict-electrique', libelle: 'Verdict électrique', groupe: 'Système', ordre: 250, composant: lazy(() => import('../electrique/VerdictElectrique')) }, // CALX249

  { cle: 'economie', libelle: 'Économie', groupe: 'Résultats', ordre: 260, composant: lazy(() => import('../economie/PanneauEconomie')) }, // CALX289
  { cle: 'reprise-visite', libelle: 'Reprise de la visite', groupe: 'Site', ordre: 165, composant: lazy(() => import('./RepriseVisite')) }, // CALX365
  { cle: 'pose-reelle', libelle: 'Pose réelle', groupe: 'Dossiers', ordre: 185, composant: lazy(() => import('./PoseReelle')) }, // CALX367
]

/**
 * Les onglets dans leur ORDRE D'AFFICHAGE (champ `ordre`, jamais la position
 * dans le tableau : un onglet ajouté en fin peut se placer n'importe où).
 * Renvoie une COPIE — le registre lui-même n'est jamais trié en place.
 */
export function ongletsTries() {
  return [...ONGLETS].sort((a, b) => a.ordre - b.ordre)
}

/** L'onglet portant cette clé, ou `null` — jamais une devinette. */
export function ongletParCle(cle) {
  if (!cle) return null
  return ONGLETS.find((o) => o.cle === cle) ?? null
}

/**
 * L'onglet actif pour une valeur de `?onglet=` :
 *   - absente (ou vide)  → `null` : l'atelier reste EXACTEMENT ce qu'il est
 *     aujourd'hui, le rail est visible et aucun panneau n'est ouvert ;
 *   - connue             → son onglet ;
 *   - INCONNUE           → le PREMIER onglet du rail. Une clé fautive (lien
 *     périmé, faute de frappe) ouvre donc un vrai panneau, jamais un écran
 *     blanc qui laisserait croire que l'atelier est cassé.
 */
export function resoudreOnglet(valeur) {
  if (valeur === null || valeur === undefined || valeur === '') return null
  return ongletParCle(valeur) ?? ongletsTries()[0] ?? null
}

/**
 * Les onglets regroupés pour l'affichage : `[{ groupe, onglets: [...] }]`,
 * groupes et onglets dans l'ordre du champ `ordre`.
 */
export function groupesOnglets() {
  const groupes = []
  for (const onglet of ongletsTries()) {
    const dernier = groupes[groupes.length - 1]
    if (dernier && dernier.groupe === onglet.groupe) dernier.onglets.push(onglet)
    else groupes.push({ groupe: onglet.groupe, onglets: [onglet] })
  }
  return groupes
}

/**
 * CALX55 — l'onglet que DÉSIGNE un chemin profond `/calepinage/<id>/<cle>`.
 *
 * Les treize panneaux du registre sont servis à deux adresses : l'onglet de
 * l'atelier (`?onglet=<cle>`) et la route profonde historique, dont le DERNIER
 * segment vaut exactement la clé. C'est ce que lit `atelier/RetourAtelier.jsx`
 * pour savoir d'où l'on revient, sans qu'aucun panneau ait à se nommer.
 *
 * Rend `null` — jamais un onglet par défaut — quand le chemin est l'atelier
 * lui-même (`/calepinage/<id>`) ou quand le dernier segment n'est pas une clé
 * du registre : un fil d'Ariane qui renverrait vers un AUTRE panneau que celui
 * qu'on lit mentirait, et ne rien afficher vaut mieux.
 */
export function ongletParChemin(chemin) { // CALX55
  if (!chemin) return null
  const segments = String(chemin).split('#')[0].split('?')[0].split('/').filter(Boolean)
  if (segments.length < 3) return null
  return ongletParCle(segments[segments.length - 1])
}
