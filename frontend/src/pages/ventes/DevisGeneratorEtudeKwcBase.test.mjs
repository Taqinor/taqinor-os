// CIQ126 (remplace QJR579) — `etude_kwc_base` était le kWc pour lequel
// l'écran avait calculé SON étude C&I locale. L'étude est désormais calculée
// et écrite par le serveur (`etude_ci`, propriétaire `moteur_ci`) : le
// navigateur n'écrit plus jamais `etude_kwc_base` (contrat
// `etude_ci_preview.json`, `a_retirer_v1`), ni l'Édition complète ni le devis
// automatique (même projection partagée QJR542).
// Run : node --test src/pages/ventes/DevisGeneratorEtudeKwcBase.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { projeterEtudeMarche } from '../../features/ventes/quote/etudeMarcheBloc.js'
import { documentContrat } from '../../test/fixtures/contractSamples.js'

const A_RETIRER = documentContrat('ventes', 'etude_ci_preview').cles_etude_params_ci_v2.a_retirer_v1

for (const mode of ['industriel', 'commercial']) {
  test(`${mode} : aucune clé v1 (dont etude_kwc_base) dans le bloc etude-params`, () => {
    assert.ok(A_RETIRER.includes('etude_kwc_base'))
    const bloc = projeterEtudeMarche(mode, { choix: {}, entrees: {}, ciEntrees: { mode } })
    for (const k of A_RETIRER) assert.equal(k in bloc, false, k)
  })
}

test('agricole / résidentiel : aucune clé etude_kwc_base', () => {
  assert.ok(!('etude_kwc_base' in projeterEtudeMarche('agricole', { choix: {}, entrees: {} })))
  assert.equal(projeterEtudeMarche('residentiel', { choix: {}, entrees: {} }), null)
})
