// TAILLES (fondateur 26/08/2026) — même patron que les tests voisins
// (DevisGeneratorRecalculerDimensionnement.test.mjs) : lecture du SOURCE,
// preuves structurelles que DevisOffresTailles.test.jsx (comportemental,
// rendu React réel) ne peut pas exprimer aussi directement — notamment
// « aucun champ dérivé n'est un chemin d'écriture possible », vérifiable en
// lisant le code plutôt qu'en essayant (en vain) de taper dans un champ qui
// n'existe pas.
//
// Run : node --test src/pages/ventes/DevisOffresTailles.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const COMPOSANT = readFileSync(join(HERE, 'DevisOffresTailles.jsx'), 'utf8')
const GENERATEUR = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// Les mêmes noms que backend/django_core/apps/ventes/offres_tailles.py::CHAMPS_DERIVES
// (miroir manuel — aucun import cross-stack possible, même discipline que
// ROLES_AUTO_COMPOSITION/PRODUCT_CATEGORIES). Si un jour un de ces noms
// apparaît comme CLEF ÉCRITE dans `pending`/`config`, c'est la règle « zéro
// chiffre inventé » qui casse : le composant serait en train de préparer un
// corps de PATCH que le serveur refuserait en 400.
const CHAMPS_DERIVES = [
  'prix_ttc', 'prix_par_kwc_ttc', 'economie_annuelle_mad', 'payback_annees',
  'couverture_pct', 'taux_autoconsommation_pct', 'production_annuelle_kwh',
  'economies_cumulees_25_ans_mad', 'puissance_kwc', 'capacite_utile_kwh',
]

test('aucun champ DÉRIVÉ n\'est jamais posé dans `pending` (setPendingField/setPendingEquipement) — seuls nb_panneaux/batterie_nb_modules/equipements le sont', () => {
  // Les deux SEULS points d'écriture de `pending` dans tout le fichier.
  const appelsSetPendingField = [...COMPOSANT.matchAll(/setPendingField\(([^)]*)\)/g)]
  assert.ok(appelsSetPendingField.length > 0, 'setPendingField introuvable')
  for (const m of appelsSetPendingField) {
    const args = m[1]
    for (const champ of CHAMPS_DERIVES) {
      assert.doesNotMatch(args, new RegExp(`'${champ}'`),
        `setPendingField ne doit JAMAIS écrire le champ dérivé « ${champ} »`)
    }
  }
})

test('le corps du PATCH (`appliquer`) n\'assemble QUE nb_panneaux / batterie_nb_modules / equipements — jamais un champ dérivé', () => {
  const start = COMPOSANT.indexOf('const appliquer = async (offre) => {')
  assert.ok(start > -1, 'fonction appliquer introuvable')
  const end = COMPOSANT.indexOf('const regenerer = async (offre) => {', start)
  assert.ok(end > -1)
  const corps = COMPOSANT.slice(start, end)
  // Les trois seules affectations `config.xxx =` autorisées.
  const affectations = [...corps.matchAll(/config\.(\w+) =/g)].map(m => m[1])
  assert.deepEqual(new Set(affectations),
    new Set(['nb_panneaux', 'batterie_nb_modules', 'equipements']),
    'le corps envoyé au serveur ne doit contenir QUE ces trois clés — tout le reste est dérivé, donc refusé en 400 côté serveur')
  for (const champ of CHAMPS_DERIVES) {
    assert.doesNotMatch(corps, new RegExp(`config\\.${champ}\\s*=`),
      `« ${champ} » est un champ dérivé — il ne doit jamais être assigné dans le corps du PATCH`)
  }
})

test('`appliquer`/`regenerer` scopent TOUJOURS l\'appel réseau à `offre.cle` — jamais une écriture qui toucherait les deux autres tailles', () => {
  assert.match(COMPOSANT, /patchOffreTailleConfig\(devisId, cle, config\)/)
  assert.match(COMPOSANT, /regenererOffreTaille\(devisId, offre\.cle\)/)
})

test('après un PATCH/une régénération réussis, `pending[cle]` est vidé — jamais laissé à rejouer sur la carte suivante', () => {
  const start = COMPOSANT.indexOf('const appliquer = async (offre) => {')
  const end = COMPOSANT.indexOf('const regenerer = async (offre) => {', start)
  const corpsAppliquer = COMPOSANT.slice(start, end)
  assert.match(corpsAppliquer, /setPending\(p => \(\{ \.\.\.p, \[cle\]: \{\} \}\)\)/)
})

test('DevisGenerator.jsx monte <DevisOffresTailles> UNE fois, avec editId/modeInstallation/produits — jamais un id ou un marché codé en dur', () => {
  const idx = GENERATEUR.indexOf('<DevisOffresTailles')
  assert.ok(idx > -1, 'point de montage introuvable dans DevisGenerator.jsx')
  const secondIdx = GENERATEUR.indexOf('<DevisOffresTailles', idx + 1)
  assert.equal(secondIdx, -1, 'DevisOffresTailles ne doit être monté qu\'UNE seule fois')
  const ligne = GENERATEUR.slice(idx, GENERATEUR.indexOf('/>', idx))
  assert.match(ligne, /devisId=\{editId\}/)
  assert.match(ligne, /modeInstallation=\{modeInstallation\}/)
  assert.match(ligne, /produits=\{produits\}/)
})

test('le composant reste SOUS le montage recalcDim/Aperçu — coordination avec la lane du bouton « Recalculer le dimensionnement » (correction #5), jamais entrelacé', () => {
  const idxAppercu = GENERATEUR.indexOf('Aperçu de la Simulation')
  const idxTailles = GENERATEUR.indexOf('<DevisOffresTailles')
  // QJR100 — la carte « Lignes de Produits » est montée par `<LigneTable/>`
  // (son titre vit dans `generator/LigneTable.jsx`) : l'ancre d'ordre suit le
  // point de montage, la contrainte de position est inchangée.
  const idxLignes = GENERATEUR.indexOf('<LigneTable')
  assert.ok(idxAppercu > -1 && idxTailles > -1 && idxLignes > -1)
  assert.ok(idxAppercu < idxTailles && idxTailles < idxLignes,
    'DevisOffresTailles doit être monté ENTRE la carte Aperçu de la Simulation et la carte Lignes de Produits')
})
