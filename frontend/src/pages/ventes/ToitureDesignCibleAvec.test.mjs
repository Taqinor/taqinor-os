// QJR40 (audit L3 29/08/2026, décision fondateur D8, jumelle backend = QJR25)
// — `selectors.contexte_conception_devis` calcule `cible_avec` exprès pour
// que l'écran 3D connaisse l'option 2 (« Avec batterie ») d'un devis
// « Les deux » (CTX3D, 25/08) — mais `ToitureDesign.jsx`, son unique
// consommateur, ne la lisait JAMAIS : la cible 3D ciblait toujours l'option
// SANS (celle de `contexte.cible`), à l'opposé de la politique AVEC-d'abord
// d'`electrical_service._option_choisie`/`_lignes_option_choisie` pour le
// MÊME devis (QJR25). Décision fondateur D8 du 29/08 : « Les deux »
// mono-config = AVEC partout, cible 3D comprise.
//
// SPL213 : les mappeurs purs vivent désormais dans
// `features/calepinage/atelier/contexteAtelier.js` (sans dépendance, chargeable
// par `node --test`) : les tests 1, 2 et 4 IMPORTENT et EXÉCUTENT les vraies
// fonctions ; seul le test 3 (garde d'enregistrerConception, JSX) lit encore
// le SOURCE de ToitureDesign.jsx.
//
// Run : node --test src/pages/ventes/ToitureDesignCibleAvec.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  cibleActiveDuContexte,
  contexteCalepinageVersPayload,
  contexteToDevisPayload,
  reglagesAtelierDesParametres,
  phraseCalepinageCharge,
  phraseToitureLead,
  siteLocaliseInitial, phraseSiteNonLocalise, // T4-U4-013
} from '../../features/calepinage/atelier/contexteAtelier.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ToitureDesign.jsx'), 'utf8')

test('QJR40 — cibleActiveDuContexte lit cible_avec en priorité sur cible', () => {
  assert.deepEqual(
    cibleActiveDuContexte({ cible: { panneaux: 12 }, cible_avec: { panneaux: 17 } }),
    { panneaux: 17 },
    'cible_avec doit primer sur cible')
  assert.deepEqual(
    cibleActiveDuContexte({ cible: { panneaux: 12 } }),
    { panneaux: 12 },
    'sans cible_avec, repli sur cible')
  assert.deepEqual(cibleActiveDuContexte({}), {}, 'ni l\'une ni l\'autre : {}')
})

test('QJR40 — contexteToDevisPayload (mode devis, hydrate.devis du builder 3D) cible via cibleActiveDuContexte', () => {
  const base = {
    devis: { id: 7, reference: 'DEV-7' },
    cible: { panneaux: 12, panel_watt: 550, scenario: 'injection_reseau' },
  }
  const sansAvec = contexteToDevisPayload(base)
  const avecAvec = contexteToDevisPayload({
    ...base,
    cible_avec: { panneaux: 17, panel_watt: 550, scenario: 'avec_batterie' },
  })
  // Le payload hydrate.devis doit changer dès que cible_avec est servable :
  // la cible 3D suit l'option AVEC (jamais l'option SANS figée).
  assert.notDeepEqual(avecAvec, sansAvec,
    'cible_avec doit modifier la cible hydratée (plus jamais contexte.cible seul)')
  assert.ok(JSON.stringify(avecAvec).includes('17'),
    'le payload doit porter le compte de panneaux AVEC (17)')
  assert.ok(!JSON.stringify(avecAvec).includes('"scenario":"injection_reseau"'),
    'le payload AVEC ne doit pas porter le scénario SANS')
})

test('QJR40 — aucun compte de panneaux du devis lu sur contexte.cible seul (garde de divergence retirée avec l\'écrivain du mode devis, ACAL37)', () => {
  // ACAL37 (D-ACAL-1) a SUPPRIMÉ l'écrivain du mode devis (enregistrerConception
  // + son dialogue de divergence) : l'écran enregistre le calepinage lié puis
  // sync-devis. L'invariant QJR40 reste : si une comparaison au devis revient,
  // elle passe par cibleActiveDuContexte, jamais par contexte.cible seul.
  assert.equal(SRC.includes('const panneauxPoses = Number(layout?.result?.panels) || 0'), false,
    'la garde de divergence du mode devis est revenue : la relire via cibleActiveDuContexte')
  assert.doesNotMatch(SRC, /contexte\??\.cible\??\.panneaux/,
    'un compte de panneaux lu sur contexte.cible seul recrée la divergence SANS/AVEC (QJR40)')
})

test('QJR40 — rejoué : devis « Les deux » divergents → la cible 3D cible AVEC, la MÊME option que le SLD (QJR25)', () => {
  // Devis « Les deux » divergents (le cas qui révélait le bug) : l'option
  // SANS (cible) et l'option AVEC (cible_avec) ne portent PAS le même compte
  // de panneaux ni le même scénario — exactement comme un devis réel où les
  // deux options ne couvrent pas la même surface de toit.
  const contexteLesDeux = {
    cible: { panneaux: 12, panel_watt: 550, scenario: 'injection_reseau' },
    cible_avec: { panneaux: 17, panel_watt: 550, scenario: 'avec_batterie', kwc: 9.35, batterie: 15.4 },
  }
  const cibleEcran3D = cibleActiveDuContexte(contexteLesDeux)
  // La MÊME option que celle que le SLD retient pour ce devis (QJR25,
  // `electrical_service._option_choisie` : AVEC servable l'emporte toujours).
  assert.equal(cibleEcran3D.panneaux, 17, 'la cible 3D doit cibler le compte AVEC (17), pas SANS (12)')
  assert.equal(cibleEcran3D.scenario, 'avec_batterie', 'la cible 3D doit cibler le scénario AVEC')

  // Devis mono-option (aucune option AVEC servable) : cible_avec est absente
  // — comportement STRICTEMENT inchangé, la cible reste l'unique option vendue.
  const contexteMonoOption = { cible: { panneaux: 9, panel_watt: 610, scenario: 'injection_reseau' } }
  const cibleMonoOption = cibleActiveDuContexte(contexteMonoOption)
  assert.equal(cibleMonoOption.panneaux, 9, 'un devis mono-option garde sa cible inchangée')
  assert.equal(cibleMonoOption.scenario, 'injection_reseau')

  // Contexte absent (garde `?.`) : jamais un crash, jamais une valeur inventée.
  assert.deepEqual(cibleActiveDuContexte(null), {})
  assert.deepEqual(cibleActiveDuContexte(undefined), {})
})

test('ACAL985 (K-SAISIE-PERDUE) — ligne facture × colonne lead : le payload porte la consommation du lead, jamais inventée', () => {
  // Le lead à 900 MAD/mois (ACAL776) : la facture servie atteint le payload de l'atelier.
  const avec = contexteCalepinageVersPayload({
    calepinage: { titre: 'Villa' },
    consommation_lead: { facture_mensuelle_mad: 900 },
    cible: { panneaux: 4, source: 'lead' },
  })
  assert.equal(avec.factureMensuelleMad, 900, 'ligne facture × colonne lead : la facture du lead est perdue en route')
  assert.equal(avec.cible.panneaux, 4, 'ligne cible × colonne lead : la cible du lead est perdue en route')
  // Sans facture servie : null (rien d'inventé), pas 0.
  const sans = contexteCalepinageVersPayload({ calepinage: { titre: 'Villa' }, cible: {} })
  assert.equal(sans.factureMensuelleMad, null, 'ligne facture × colonne lead : sans facture servie, null — jamais 0')
})

test('ACAL962 — reglagesAtelierDesParametres garde le pays réglé (imagerie.pays), null sinon, jamais supposé', () => {
  const avec = reglagesAtelierDesParametres({ imagerie: { pays: ' ma ' }, degagements: { allees_circulation: [] } })
  assert.equal(avec.pays, 'ma', 'le pays réglé de la société doit atteindre l’atelier')
  assert.deepEqual(avec.degagements, { allees_circulation: [] })
  assert.equal(reglagesAtelierDesParametres({ imagerie: {} }).pays, null, 'rien de réglé : null, jamais un pays par défaut')
  assert.equal(reglagesAtelierDesParametres({}).pays, null)
  assert.equal(reglagesAtelierDesParametres(null), null)
})

test('ACAL967 — phraseCalepinageCharge n’ajoute « Calepinage » que si le titre ne commence pas par ce mot', () => {
  assert.equal(phraseCalepinageCharge('Calepinage (copie)', 5, true),
    'Calepinage (copie) chargé. Ajustez la conception, puis « Enregistrer le calepinage ».')
  assert.ok(phraseCalepinageCharge('Toiture — bâtiment A', 5, true).startsWith('Calepinage Toiture — bâtiment A chargé.'))
  assert.equal(phraseCalepinageCharge('Calepinage (copie)', 5, false),
    'Calepinage (copie) en lecture seule — consultation de la conception.')
  assert.ok(phraseCalepinageCharge('  ', 7, true).startsWith('Calepinage 7 chargé.'), 'sans titre : le numéro')
})

test('R2-15 / R2-01 — phraseToitureLead redit ce que le lead déclare (contrat), rien quand il ne dit rien', () => {
  const contrat = JSON.parse(readFileSync(join(HERE, '../../../../backend/django_core/apps/calepinage/contract_samples/calepinage_design_context.json'), 'utf8'))
  assert.equal(phraseToitureLead(contrat.exemple.toiture_lead),
    'Le lead déclare : toiture · tuiles · 60 m² disponibles · pente 25° · sud-ouest · ombrage partiel (palmier côté ouest) · 2 étages')
  assert.equal(phraseToitureLead(contrat.exemple_sans_devis.toiture_lead), 'Le lead déclare : terrasse béton · sud')
  assert.equal(phraseToitureLead({ ombrage_notes: 'antenne', roof_age: 15, structure_pref: 'Acier' }),
    'Le lead déclare : ombrage : antenne · toiture de 15 ans · structure acier')
  assert.equal(phraseToitureLead(contrat.exemple_vide.toiture_lead), null, 'tout nul : aucune ligne')
  assert.equal(phraseToitureLead(undefined), null, 'contexte sans la clé (mode devis) : aucune ligne')
})

test('T4-U4-013 — siteLocaliseInitial : provenance relue, document ancien, repère du lead, sinon non localisé', () => {
  assert.equal(siteLocaliseInitial({ siteLocalise: 'adresse', pin: { lat: 31.6, lng: -7.3 } }, null), 'adresse')
  assert.equal(siteLocaliseInitial({ siteLocalise: null, pin: { lat: 31.6, lng: -7.3 } }, 'gps'), null)
  assert.equal(siteLocaliseInitial({ version: 2, pin: { lat: 31.6, lng: -7.3 } }, null), undefined, 'document ancien : règle du serveur')
  assert.equal(siteLocaliseInitial({ version: 2, zones: [] }, 'gps'), 'lead')
  assert.equal(siteLocaliseInitial(null, null), null, 'client sans adresse, sans lead : non localisé')
})

test('T4-U4-013 — phraseSiteNonLocalise : le geste, et ce que fait le calcul sans lui', () => {
  assert.equal(phraseSiteNonLocalise('Marrakech'),
    'Site non localisé — carte au niveau Maroc. Cherchez l’adresse du client puis « Localiser », ou zoomez jusqu’au toit avant de le tracer : sinon le calcul se fait sur la ville de la fiche (Marrakech).')
  assert.ok(phraseSiteNonLocalise('').endsWith('sinon le calcul est refusé.'))
})
