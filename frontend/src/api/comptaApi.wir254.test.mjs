import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

/* WIR254 — ~15 @action de `EtatsComptablesViewSet` (NTFIN14-49) étaient
   servies par le serveur sans le moindre client : `comptaApi.etats` ne portait
   AUCUNE des clés balanceReferentiel/balanceAnalytique/executionBudgetaire/
   anomaliesEcritures/cockpitCloture/pretACloturer/rapprochementsEnRetard/
   registreImmobilisations/projectionDotations/positionsContratRevenu/
   fraisBancaires/provisions — chaque état était donc INATTEIGNABLE depuis
   l'écran, curl seul pouvait les lire.

   Cette garde relit les DEUX sources (client + serveur, pas d'appel réseau,
   pas de mock du graphe ESM — `comptaApi.js` importe `./axios`, à effets de
   bord) et vérifie que chaque `@action` de ce lot a bien une clé
   `comptaApi.etats` correspondante, SAUF les deux marquées « API-only
   volontaire » (patron WIR107) : `resultat-analytique` (exige un code d'axe
   choisi par l'utilisateur) et `analyse-variation` (exige deux périodes A/B).
   Ces deux gardent quand même leur wrapper client (juste non rendu à
   l'écran) — la garde vérifie donc qu'ELLES AUSSI ont une clé, pas qu'elles
   en sont dispensées. */

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'comptaApi.js'), 'utf8')

function racineDepot() {
  let dossier = resolve(here)
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du dépôt introuvable depuis ${here}`)
}

const vuesCompta = readFileSync(
  join(racineDepot(), 'backend', 'django_core', 'apps', 'compta', 'views.py'),
  'utf8',
)

// Le lot WIR254 : slug d'URL (tel que déclaré côté serveur) → API-only ou non.
const LOT_WIR254 = [
  ['balance-referentiel', false],
  ['balance-analytique', false],
  ['resultat-analytique', true],
  ['execution-budgetaire', false],
  ['analyse-variation', true],
  ['anomalies-ecritures', false],
  ['cockpit-cloture', false],
  ['pret-a-cloturer', false],
  ['rapprochements-en-retard', false],
  ['registre-immobilisations', false],
  ['projection-dotations', false],
  ['positions-contrat-revenu', false],
  ['frais-bancaires', false],
  ['provisions', false],
]

for (const [slug, apiOnly] of LOT_WIR254) {
  test(`@action url_path='${slug}' existe toujours côté serveur`, () => {
    assert.match(
      vuesCompta, new RegExp(`url_path=['"]${slug}['"]`),
      `apps/compta/views.py ne déclare plus '${slug}' — mettre à jour ce test `
      + 'ET comptaApi.js dans le même commit si le endpoint a été renommé/retiré.',
    )
  })

  test(`comptaApi.etats porte une clé pour '${slug}' (/compta/etats/${slug}/)`
    + (apiOnly ? ' [API-only volontaire]' : ''), () => {
    assert.match(
      src, new RegExp(`/compta/etats/${slug}/`),
      `comptaApi.etats n'appelle jamais /compta/etats/${slug}/ — le client `
      + `n'a pas de wrapper pour cette @action (WIR254 régresse).`,
    )
  })
}

test('les deux API-only volontaires restent EXACTEMENT resultat-analytique et analyse-variation', () => {
  // Garde-fou anti-dérive : si un jour quelqu'un ajoute un 3e « API-only » à
  // ce lot sans y réfléchir, ce test échoue et force une décision explicite.
  const apiOnly = LOT_WIR254.filter(([, v]) => v).map(([s]) => s)
  assert.deepEqual(apiOnly.sort(), ['analyse-variation', 'resultat-analytique'])
})
