# frontend/parked/ — modules sortis du MVP solaire (SOLMVP40, 21/09/2026)

## Ce que c'est

Ce dossier contient le code frontend des **37 modules** sortis du périmètre
« un seul produit : le MVP solaire » (Groupe SOLMVP, `docs/PLAN.md`). Le
founder a tranché : ce code n'est **pas supprimé**, il est **rangé**, hors
build/lint/tests/déploiement, mais il reste visible dans le dépôt et son
historique `git` complet (via `git mv`, jamais un nouveau fichier) — n'importe
quel module peut revenir en arrière avec la recette ci-dessous.

`ged` (GED / gestion documentaire) a été évoqué puis écarté de cette liste en
cours de tâche (décision founder finale, 21/09/2026) : **il reste dans le
produit**, intact sous `frontend/src/features/ged`, `pages/ged`,
`api/gedApi.js`, avec toutes ses routes (`/ged`, `/ged/signature/:token`,
`/ged/signataire/:token`, `/ged/depot/:token`) inchangées dans le routeur.

Rien ici n'est chargé par l'application : aucun `import.meta.glob`, aucun
`import(...)` du routeur ne pointe plus vers ce dossier, et `frontend/parked/`
est explicitement exclu d'ESLint, Vitest, Docker et des scripts de vérification
du dépôt (voir « Exclusions » plus bas dans le commit SOLMVP40).

## Modules parqués et leurs anciens chemins

Pour chaque module : `frontend/src/features/<x>` (toujours),
`frontend/src/pages/<x>` (si le module avait des pages dédiées) et
`frontend/src/api/<x>Api.js` (+ tests co-localisés, si le module avait un
client API dédié) sont devenus respectivement `frontend/parked/features/<x>`,
`frontend/parked/pages/<x>`, `frontend/parked/api/<x>Api.js`.

| Module | features/ | pages/ | api/ |
|---|---|---|---|
| agriculture | oui | oui | oui (agricultureApi.js) |
| ao | oui | — | oui (aoApi.js + aoApi.test.mjs) |
| assurances | oui | — | — |
| btp_chantier | oui | oui (`pages/btp`) | oui (btpChantierApi.js) |
| compta | oui | — | oui (comptaApi.js + comptaApi.pact18.test.mjs) |
| contrats | oui | — | oui (contratsApi.js) |
| cpq | oui | — | oui (cpqApi.js) |
| credit | oui | — | oui (creditApi.js) |
| customobjects | oui | — | — |
| education | oui | oui | oui (educationApi.js) |
| esg | oui | oui | oui (esgApi.js) |
| fiscal | oui | oui | oui (fiscalApi.js) |
| flotte | oui | — | oui (flotteApi.js) |
| fpa | oui | oui | oui (fpaApi.js) |
| gestion_projet | oui | — (`pages/dossiers`, voir note) | oui (gestionProjetApi.js) |
| hospitality | oui | — | oui (hospitalityApi.js) |
| immobilier | oui | oui | oui (immobilierApi.js) |
| innovation | oui | — | oui (innovationApi.js) |
| juridique | oui | — | oui (juridiqueApi.js) |
| kb | oui | oui | oui (kbApi.js) |
| litiges | oui | — | oui (litigesApi.js) |
| logistique | oui | — | — |
| magasin | oui | — | — |
| marketing | oui | — | oui (marketingApi.js) |
| messaging | oui | oui | oui (messagesApi.js + messagesApi.test.mjs) |
| migration | oui | — | oui (migrationApi.js) |
| mrp | oui | oui | oui (mrpApi.js) |
| paie | oui | — | oui (paieApi.js + paieApi.fe1.test.mjs) |
| pos | oui | — | oui (posApi.js) |
| qhse | oui | oui | oui (qhseApi.js) |
| rh | oui | — (`pages/dispatch`, voir note) | oui (rhApi.js) |
| sante | oui | — | oui (santeApi.js) |
| scm | oui | oui | oui (scmApi.js) |
| transport | oui | oui | — |
| veille_ao | oui | — | oui (veilleAoApi.js + veilleAoApi.test.mjs) |
| voip | oui | — | oui (voipApi.js) |
| workflow | oui | — | — |

Note « pages » : `pages/dossiers` (gestion_projet) et `pages/dispatch` (rh,
son unique fichier `EquipePage.jsx` n'appelait que `rhApi`) ont suivi leur
module bien que le nom du dossier ne corresponde pas à la clé du module.

`frontend/components/agriculture/` (composant `EtapeCampagneForm`, utilisé
uniquement par `pages/agriculture`) a suivi vers
`frontend/parked/components/agriculture/`.

`btpChantierApi.js`, `gestionProjetApi.js` et `messagesApi.js` (+ son test
co-localisé) sont restés dans `frontend/src/api/` un temps (SOLMVP40) car
utilisés par des écrans CONSERVÉS (installations, ventes, CRM, SAV, stock) ;
SOLMVP41c a retiré ces derniers usages (CTA « Créer le projet de
facturation », dictée vocale terrain, sélecteur d'acheteur BCF recablé sur
`coreApi.utilisateurs.list()`) et déplacé les trois clients ici.

## Faire revenir un module

1. `git mv frontend/parked/features/<x> frontend/src/features/<x>`
   (+ `git mv frontend/parked/pages/<x> frontend/src/pages/<x>` et
   `git mv frontend/parked/api/<x>Api.js frontend/src/api/<x>Api.js` s'ils
   existent).
2. Si le module a un `module.config.jsx` : rien à faire côté
   `router/moduleRoutes.jsx` — le `import.meta.glob('../features/*/module.config.jsx')`
   le redétecte automatiquement dès que le dossier réapparaît sous
   `frontend/src/features/`.
3. Sinon (route déclarée directement dans `router/index.jsx`, cas de
   `contrats`, `kb`, `messaging`, `qhse`, `rh`) : retrouver la route et
   l'import lazy supprimés par le commit SOLMVP40 dans l'historique git
   (`git log -p -- frontend/src/router/index.jsx`, chercher le commit
   `solmvp(SOLMVP40)`) et les restaurer dans `frontend/src/router/index.jsx`.
   Restaurer aussi l'entrée correspondante dans
   `frontend/src/router/prefetchMap.js` si elle existait (`/rh`,
   `/comptabilite`, `/messages`).
4. Retirer `frontend/parked/**` des exclusions si plus aucun module n'y
   reste dans **chacun** des fichiers suivants (ne toucher que celles qui ne
   servent plus qu'à ce module) : `frontend/eslint.config.js` (`ignores`),
   `frontend/vitest.config.js` (`test.exclude`), `frontend/.dockerignore`.
5. Relancer le résolveur d'imports (voir le rapport SOLMVP40) ou simplement
   `npm run lint` + `npm test` + `vite build` pour confirmer que plus aucun
   import cassé ne subsiste.

## Ce dossier n'est PAS

- Une suppression : `git log --follow` sur n'importe quel fichier ici
  retrouve tout son historique d'avant le déplacement.
- Un fork ou une copie : c'est le même fichier, déplacé par `git mv`.
- Un module désactivable par toggle société (`ModuleToggle` / ODX6) : ces
  modules-là restent dans `frontend/src/features/` et sont juste masqués par
  rôle/société. Ici, le code est physiquement hors du build.
