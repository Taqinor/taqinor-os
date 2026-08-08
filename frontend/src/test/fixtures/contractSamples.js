import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import process from 'node:process'

/* ============================================================================
   PACT10 / PACT13 — LA FIXTURE PARTAGÉE : un test n'invente plus sa réponse.
   ----------------------------------------------------------------------------
   Cause racine PROUVÉE du plantage du 03/08/2026 : le test vitest de l'écran
   « Appels d'offres — Tableau de bord » déclarait à la main
   `PAYLOAD = { ao_en_cours: 7, …, echeances_dues: [ … ] }` — l'INVERSE EXACT de
   ce que le backend renvoie — et restait VERT. En face, le test backend
   affirmait `echeances_dues == 1`. Les deux suites étaient vertes et se
   contredisaient : chacune vérifiait sa propre hypothèse, personne ne vérifiait
   le lien.

   Un mock écrit à la main est une DEUXIÈME source de vérité. Ces helpers la
   suppriment : la charge utile d'un test vient de l'exemple COMMITTÉ dans
   l'app (`backend/django_core/apps/<app>/contract_samples/<nom>.json`), le même
   fichier que le backend affirme et que `scripts/check_api_shapes.py` compare
   au dictionnaire RÉELLEMENT renvoyé par la vue. Si le serveur change de forme,
   l'exemple change, et ce test casse TOUT SEUL — sans réunion, sans discipline
   humaine.

   Lecture de fichiers en Node : aucun runtime Python, aucun coût pour la CI.
   ========================================================================== */

function racineDepot() {
  let dossier = resolve(process.cwd())
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`)
}

/** Chemin de l'exemple de contrat d'un endpoint agrégé. */
export function fichierContrat(app, nom) {
  return join(racineDepot(), 'backend', 'django_core', 'apps', app,
    'contract_samples', `${nom}.json`)
}

/**
 * Le document de contrat complet : `{ endpoint, pourquoi, exemple, … }`.
 * Lève si le fichier manque — un test ne doit JAMAIS retomber en silence sur
 * une charge utile inventée, c'est précisément le défaut d'origine.
 */
export function documentContrat(app, nom) {
  const chemin = fichierContrat(app, nom)
  if (!existsSync(chemin)) {
    throw new Error(
      `Exemple de contrat introuvable : ${chemin}. Le contrat part EN PREMIER `
      + '(PACT10) — voir backend/django_core/apps/ao/contract_samples/README.md',
    )
  }
  return JSON.parse(readFileSync(chemin, 'utf8'))
}

/**
 * La charge utile d'exemple. `variante` sélectionne une clé alternative du
 * document (ex. `'exemple_vide'` pour l'état « utilisateur sans société »),
 * qui décrit un AUTRE ÉTAT DU SERVEUR — jamais une autre FORME.
 */
export function exempleContrat(app, nom, variante = 'exemple') {
  const document = documentContrat(app, nom)
  const charge = document[variante]
  if (charge === undefined) {
    throw new Error(
      `Le contrat ${app}/${nom}.json ne porte aucune variante « ${variante} ».`,
    )
  }
  return charge
}

/** Prêt pour `mockResolvedValue` : la forme axios `{ data: <exemple> }`. */
export function reponseContrat(app, nom, variante = 'exemple') {
  return { data: exempleContrat(app, nom, variante) }
}
