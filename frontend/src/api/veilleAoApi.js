import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   VAO32 — Client API du module Veille appels d'offres (`apps/veille_ao`).
   ----------------------------------------------------------------------------
   ARC44 — factory CRUD partagée (`api/resource.js`), jamais un `axios.get`
   direct dans `features/veille_ao/`.

   Le backend (VAO6-14, `SourceVeille`/`AvisMarche`/`MotCleVeille`/
   `RegleExclusion`, permissions `veille_ao_voir`/`veille_ao_gerer`) est bâti
   dans une lane PARALLÈLE, sur une autre branche : il n'existe pas encore dans
   CE worktree pour être relu. Les chemins ci-dessous suivent la convention de
   nommage du reste du dépôt (kebab-case, court, dérivé du nom du modèle — cf.
   `apps/contrats/urls.py`, `apps/litiges/urls.py`) et le SEUL endpoint que le
   texte de tâche fixe littéralement (`collecte.declencher`, VAO23 : « POST
   /api/django/veille_ao/collecter/ »). À RECONCILIER avec
   `apps/veille_ao/urls.py` dès que la lane backend est mergée sur `main`
   (même geste que `aoApi.js` après ODX11 — voir son en-tête).

   MISE À JOUR (lane VAO21-31) : le backend EXISTE désormais et cette liste a
   été réconciliée avec `apps/veille_ao/urls.py`. Tous les chemins ci-dessous
   sont servis, et `scripts/check_api_contract.py` le vérifie mécaniquement à
   chaque commit. Le seul appel RETIRÉ est `chargerDetail` (VAO18) : il
   appartient au collecteur portail, encore gaté (voir le commentaire dans le
   bloc `avis`).

   `sante()` est un appel AGRÉGÉ unique (même patron que `aoApi.tableauMarches`,
   AOF172/166) : dernière collecte réussie + son âge, état d'armement de la
   collecte, alarme de silence (VAO24), avis examinés hier — VAO35 (état
   d'armement) ET VAO37 (bandeau de santé) le consomment tous les deux, jamais
   un calcul dérivé côté front à partir de la liste des exécutions.
   ========================================================================== */

const crud = makeResourceFactory(api, '/veille_ao')

const veilleAoApi = {
  // ── AvisMarche — le SAS (VAO8) ──
  avis: {
    ...crud('avis'),
    // VAO14/VAO34 — les deux gestes qui comptent, chacun un appel de service
    // RÉEL (jamais une mutation de façade). `ignorer` répond avec la règle
    // D'EXCLUSION proposée (VAO10) — jamais créée sans confirmation explicite.
    retenir: (id, data) => api.post(`/veille_ao/avis/${id}/retenir/`, data),
    ignorer: (id, data) => api.post(`/veille_ao/avis/${id}/ignorer/`, data),
    // PAS de `chargerDetail` ici, et c'est VOLONTAIRE. L'enrichissement du
    // détail (VAO18) fait partie du COLLECTEUR PORTAIL (VAO15-VAO20), qui est
    // gaté derrière une action fondateur : ouvrir le compte entreprise gratuit
    // du portail et aller voir si le flux RSS authentifié existe (VAO2). Si ce
    // flux existe, le collecteur n'est même jamais construit. Publier ici un
    // appel vers une route que le backend ne sert pas est exactement le défaut
    // qui a tué l'écran « AO > Bibliothèque » en production le 03/08/2026 —
    // `scripts/check_api_contract.py` le refuse désormais. Ce bouton revient
    // avec le collecteur, jamais avant.
  },

  // ── SourceVeille — le catalogue des sources (VAO7) ──
  sources: crud('sources'),

  // ── MotCleVeille — les mots-clés, DONNÉE jamais constante (VAO9) ──
  motsCles: crud('mots-cles'),

  // ── RegleExclusion — « Ignorer » qui APPREND (VAO10) ──
  reglesExclusion: crud('regles-exclusion'),

  // ── AcheteurCible — le carnet de démarchage (VAO29) ──
  acheteursCibles: crud('acheteurs-cibles'),

  // ── ExecutionCollecte — le journal d'exécution (VAO24) ──
  executions: crud('executions'),

  // ── Déclenchement manuel (VAO23) — LE MÊME job que le beat de nuit. ──
  collecte: {
    // Chemin LITTÉRAL fixé par le texte de VAO23 : « POST
    // /api/django/veille_ao/collecter/ », gated `veille_ao_gerer` côté serveur.
    declencher: () => api.post('/veille_ao/collecter/'),
  },

  // VAO24/VAO35/VAO37 — un seul appel agrégé (santé + état d'armement).
  sante: () => api.get('/veille_ao/sante/'),

  // VAO31 — attribution : canal → avis → affaires → gagnés, calculée côté
  // serveur (jamais un agrégat client sur la liste des avis).
  attribution: () => api.get('/veille_ao/attribution/'),
}

export default veilleAoApi
