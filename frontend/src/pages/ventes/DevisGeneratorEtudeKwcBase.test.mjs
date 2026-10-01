// QJR579 (contrat QJR510) — le générateur enregistre, avec l'étude
// industrielle / commerciale, le kWc pour lequel il l'a calculée
// (`etude_kwc_base`) : sans lui, la garde de fraîcheur (QJR625) n'a aucune base
// pour savoir qu'une modification de ligne ultérieure a périmé taux / payback.
// Écrit par LA projection partagée (QJR542) : Édition complète ET devis
// automatique (QJR543) l'envoient à l'identique.
// Run : node --test src/pages/ventes/DevisGeneratorEtudeKwcBase.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { computeEtudeIndustrielle } from '../../features/ventes/solar.js'
import { projeterEtudeMarche } from '../../features/ventes/quote/etudeMarcheBloc.js'

const etude = computeEtudeIndustrielle({
  kwp: 42.6, consoMensuelleKwh: 9000, dayUsagePct: 80, totalTtc: 350000,
  kwhPrice: 1.2, efficiency: 0.8,
})

for (const mode of ['industriel', 'commercial']) {
  test(`${mode} : le bloc etude-params porte etude_kwc_base = kWc de l'étude`, () => {
    const bloc = projeterEtudeMarche(mode, { etude, choix: {}, entrees: {} })
    assert.equal(bloc.etude_kwc_base, etude.kwc)
    assert.equal(bloc.etude_kwc_base, 42.6)
  })
}

test('sans étude calculée : etude_kwc_base nul (jamais un kWc inventé)', () => {
  assert.equal(projeterEtudeMarche('industriel', { etude: null, choix: {}, entrees: {} }).etude_kwc_base, null)
})

test('agricole / résidentiel : aucune clé etude_kwc_base', () => {
  assert.ok(!('etude_kwc_base' in projeterEtudeMarche('agricole', { choix: {}, entrees: {} })))
  assert.equal(projeterEtudeMarche('residentiel', { choix: {}, entrees: {} }), null)
})
