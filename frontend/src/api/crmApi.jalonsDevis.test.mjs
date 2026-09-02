// CRX37 — le client d'API expose enfin les jalons devis du lead.
//
// `apps.ventes.selectors.devis_events_for_lead` (QX32be) avait été écrit POUR
// que le CRM fusionne « devis envoyé / proposition ouverte / signé / refusé »
// dans l'historique d'un lead, et n'avait AUCUN appelant : le commercial ne
// voyait jamais le cycle de vie de ses devis dans la timeline, alors que
// `ChatterTimeline` sait rendre ces quatre `kind` depuis QX32.
//
// `crmApi.js` importe `./axios`, qui a des effets de bord réseau/globaux au
// chargement du module : comme `ventesApi.overrides.test.mjs` déjà au dépôt,
// ce test relit la SOURCE pour verrouiller URL/verbe, et il IMPORTE le contrat
// committé côté serveur (`apps/crm/contract_samples/lead_jalons_devis.json`)
// plutôt que de recopier une forme à la main — les deux moitiés ne peuvent
// plus diverger en silence (PACT10).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'crmApi.js'), 'utf8')
const CONTRAT = JSON.parse(readFileSync(join(
  here, '..', '..', '..', 'backend', 'django_core', 'apps', 'crm',
  'contract_samples', 'lead_jalons_devis.json'), 'utf8'))

test('getLeadJalonsDevis -> GET /crm/leads/<id>/jalons-devis/', () => {
  assert.match(
    src,
    /getLeadJalonsDevis: \(id\) => api\.get\(`\/crm\/leads\/\$\{id\}\/jalons-devis\/`\)/,
  )
})

test("l'URL du client correspond à l'endpoint du contrat committé", () => {
  const [verbe, chemin] = CONTRAT.endpoint.split(' ')
  assert.equal(verbe, 'GET')
  // Le contrat nomme le chemin Django complet ; le client d'API travaille sur
  // le préfixe `/api/django` posé par `axios.js`.
  assert.equal(chemin, '/api/django/crm/leads/<pk>/jalons-devis/')
  assert.ok(src.includes('/crm/leads/${id}/jalons-devis/'))
})

test("le contrat expose bien une enveloppe { results: [...] }", () => {
  assert.deepEqual(Object.keys(CONTRAT.exemple), ['results'])
  assert.ok(Array.isArray(CONTRAT.exemple.results))
  assert.ok(CONTRAT.exemple.results.length > 0)
})

test('chaque ligne du contrat porte les clés que la timeline consomme', () => {
  for (const ligne of CONTRAT.exemple.results) {
    for (const cle of ['id', 'kind', 'body', 'created_at', 'devis_id',
      'reference', 'user_nom', 'pinned']) {
      assert.ok(cle in ligne, `clé manquante : ${cle}`)
    }
    // `id` TEXTUEL : jamais en collision avec les id NUMÉRIQUES de
    // `crm.LeadActivity`, que l'écran fusionne dans la même liste.
    assert.equal(typeof ligne.id, 'string')
    assert.match(ligne.kind, /^devis_/)
  }
})
