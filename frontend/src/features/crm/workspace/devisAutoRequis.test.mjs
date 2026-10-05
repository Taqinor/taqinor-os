/* QJR601 — la section Énergie et les puces « manquant » LISENT la règle
   servie (contrat devis_auto_pret.json, QJR509/QJR600) : aucune recopie
   locale de apps/crm/devis_auto.py, aucune résolution par libellé.
     node --test src/features/crm/workspace/devisAutoRequis.test.mjs */
import test from 'node:test'
import assert from 'node:assert/strict'
import { exempleContrat } from '../../../test/fixtures/contractSamples.js'
import { chipsAComplete, missingFieldTarget } from './missingFields.js'
import { sectionAutoRepliee, sectionCoeurKeys } from './draftCore.js'
import { PIPELINE_STAGES } from '../stages.js'

const etat = (server = {}, draft = {}) => ({ server, draft, mode: 'edit' })

test('lead C&I avec bill_kwh SEUL → section Énergie complète et repliée', () => {
  // Groupe « l'un des » servi pour le C&I : conso OU kWh du site (CAD166).
  const { requis } = exempleContrat('crm', 'devis_auto_pret').devis_auto
  const s = etat({
    type_installation: 'industriel', bill_kwh: '500', conso_mensuelle_kwh: null,
    devis_auto: { pret: true, manquants: [], manquants_detail: [], requis },
  })
  assert.equal(sectionAutoRepliee(s, 'energie'), true)
})

test('facture d’hiver à 0 → section Énergie NON complète (vide du serveur)', () => {
  const { requis } = exempleContrat('crm', 'devis_auto_pret', 'exemple_pret').devis_auto
  const zero = etat({ facture_hiver: '0', devis_auto: { requis } })
  assert.equal(sectionAutoRepliee(zero, 'energie'), false)
  const rempli = etat({ facture_hiver: '650', devis_auto: { requis } })
  assert.equal(sectionAutoRepliee(rempli, 'energie'), true)
})

test('agricole : les champs requis vivent dans « Pompage », pas dans l’énergie', () => {
  const { requis } = exempleContrat('crm', 'devis_auto_pret', 'exemple_agricole').devis_auto
  assert.deepEqual(sectionCoeurKeys(etat({ devis_auto: { requis } }), 'energie'), [])
})

test('un libellé RENOMMÉ laisse la puce cliquable sur le bon champ', () => {
  const bloc = exempleContrat('crm', 'devis_auto_pret').devis_auto
  const renomme = bloc.manquants_detail.map((e) => ({ ...e, label: `${e.label} (renommé)` }))
  const chips = chipsAComplete(etat({
    stage: PIPELINE_STAGES[0], devis_auto: { ...bloc, manquants_detail: renomme },
  }))
  const chip = chips.find((c) => c.id.startsWith('devis:'))
  assert.equal(chip.label, renomme[0].label)
  assert.deepEqual({ field: chip.field, section: chip.section }, missingFieldTarget(renomme[0].champ))
  assert.equal(chip.field, 'lf-conso-mensuelle')
  assert.equal(chip.section, 'energie')
})

test('agricole : chaque puce vise son champ de pompage', () => {
  const bloc = exempleContrat('crm', 'devis_auto_pret', 'exemple_agricole').devis_auto
  const chips = chipsAComplete(etat({ stage: PIPELINE_STAGES[0], devis_auto: bloc }))
  // AGR403 — le CV (pompe ACTUELLE) n'est plus requis : deux groupes hydrauliques.
  assert.deepEqual(chips.map((c) => c.field), ['lf-pompe-hmt', 'lf-pompe-debit'])
})

test('AGR415 — agricole : le cœur « Pompage » LIT les groupes servis (nouveau devis_auto_pret.json)', () => {
  const { requis } = exempleContrat('crm', 'devis_auto_pret', 'exemple_agricole').devis_auto
  assert.deepEqual(sectionCoeurKeys(etat({ devis_auto: { requis } }), 'pompage'), requis.flat())
  // Sans règle servie (création) : repli sur HMT + débit, jamais le CV.
  assert.deepEqual(sectionCoeurKeys(etat({}), 'pompage'), ['pompe_hmt_m', 'pompe_debit_m3h'])
})
