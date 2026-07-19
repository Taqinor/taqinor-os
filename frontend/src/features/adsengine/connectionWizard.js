/* ============================================================================
   PUB46 — Assistant de connexion guidé (contenu STATIQUE, sans JSX).
   ----------------------------------------------------------------------------
   ``ConnectionScreen`` n'était que 6 champs de jetons bruts sans aide — plus
   technique qu'Ads Manager lui-même. Ce fichier porte le contenu FR pas-à-pas
   (créer l'app Meta, le System User, générer le jeton, trouver l'ID du compte
   publicitaire) + la remédiation par item de la checklist de santé (ENG12).
   AUCUNE dépendance nouvelle, AUCUN appel réseau ici (données pures) — la
   « vérification » de chaque étape réutilise l'endpoint ``connection.health``
   déjà construit (jamais un nouveau contrat backend pour ce ticket).
   ========================================================================== */

// Chaque étape : ``statutCles`` = les clés de ``connection.health().statuses``
// qui, toutes vertes, confirment que l'étape est bouclée (liste vide = étape
// préparatoire, sans statut backend dédié — ex. créer le System User lui-même).
export const WIZARD_STEPS = [
  {
    key: 'app',
    numero: 1,
    titre: 'Créer une app Meta',
    description:
      "Rendez-vous sur Meta for Developers, créez une app de type « Entreprise », "
      + "puis notez l'App ID et l'App Secret affichés dans Paramètres → Basique.",
    lienLabel: 'Ouvrir Meta for Developers',
    lien: 'https://developers.facebook.com/apps/',
    champs: ['app_id', 'app_secret'],
    statutCles: [],
  },
  {
    key: 'system_user',
    numero: 2,
    titre: 'Créer un System User',
    description:
      "Dans Meta Business Suite → Paramètres de l'entreprise → Utilisateurs → "
      + 'Utilisateurs système, créez un utilisateur système avec le rôle Admin, '
      + 'puis assignez-lui le compte publicitaire ET la Page (une tâche fréquemment '
      + 'oubliée qui bloque la synchronisation des posts).',
    lienLabel: 'Ouvrir les paramètres Business',
    lien: 'https://business.facebook.com/settings/system-users',
    champs: [],
    statutCles: [],
  },
  {
    key: 'token',
    numero: 3,
    titre: "Générer le jeton d'accès",
    description:
      "Depuis l'utilisateur système créé à l'étape précédente, générez un nouveau "
      + 'jeton avec les autorisations ads_management, ads_read, '
      + 'pages_read_engagement et business_management, puis collez-le ci-dessous.',
    lienLabel: 'Générer un jeton système',
    lien: 'https://business.facebook.com/settings/system-users',
    champs: ['access_token'],
    statutCles: ['token'],
  },
  {
    key: 'ad_account',
    numero: 4,
    titre: "Trouver l'ID du compte publicitaire",
    description:
      "Dans Meta Ads Manager → Paramètres du compte, copiez l'identifiant "
      + "(préfixé « act_ »), puis renseignez-le ci-dessous.",
    lienLabel: 'Ouvrir Ads Manager',
    lien: 'https://adsmanager.facebook.com/',
    champs: ['ad_account_id'],
    statutCles: ['ad_account'],
  },
  {
    key: 'page_pixel',
    numero: 5,
    titre: 'Renseigner la Page et le Pixel (optionnel)',
    description:
      "L'ID de Page se trouve dans Meta Business Suite → Paramètres de "
      + "l'entreprise → Pages ; l'ID de Pixel dans Meta Events Manager. Utile pour "
      + 'les publications organiques et la synchronisation Pixel/CAPI.',
    lienLabel: 'Ouvrir Meta Events Manager',
    lien: 'https://business.facebook.com/events_manager2/',
    champs: ['page_id', 'pixel_id'],
    statutCles: ['page', 'pixel'],
  },
]

// Remédiation FR par clé de statut (ENG12) — renvoie vers le NUMÉRO d'étape à
// reprendre. Complète (n'écrase JAMAIS) le ``detail`` déjà renvoyé par le
// backend, affiché tel quel juste à côté (contrat existant de l'écran).
export const HEALTH_REMEDIATIONS = {
  token: {
    message: "Aucun jeton valide enregistré.",
    etape: 3,
  },
  ad_account: {
    message: "Aucun identifiant de compte publicitaire renseigné.",
    etape: 4,
  },
  page: {
    message: 'Aucune Page Facebook renseignée (optionnel, requis pour les publications organiques).',
    etape: 5,
  },
  pixel: {
    message: 'Aucun Pixel renseigné (optionnel, requis pour la synchronisation Pixel/CAPI).',
    etape: 5,
  },
  capi: {
    message: 'Clé serveur CAPI absente — coordonnée technique à demander au fondateur/l’équipe technique (hors de ce formulaire).',
    etape: null,
  },
}

// Une étape est « bouclée » si TOUTES ses ``statutCles`` sont vertes dans le
// dernier ``connection.health()`` connu. Une étape sans statut backend dédié
// (``statutCles`` vide) reste « à confirmer soi-même » — jamais fabriquée verte.
export function stepStatus(step, healthByKey) {
  if (!step.statutCles || step.statutCles.length === 0) return 'manuel'
  const known = step.statutCles.map(k => healthByKey?.[k])
  if (known.some(v => v === undefined)) return 'inconnu'
  return known.every(v => v === true) ? 'ok' : 'a_faire'
}
