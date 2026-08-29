// QJR65 (audit L3 du 29/08/2026, décision fondateur D12) — UN PRIX TAPÉ À LA
// MAIN NE DOIT PLUS ÊTRE ÉCRASÉ EN SILENCE À LA RÉOUVERTURE D'UN BROUILLON.
//
// LE BUG. Le drapeau `prixManuel` (N2) protégeait bien la SESSION en cours,
// mais le mappeur de lignes `?edit=` mappait produit / designation / quantite /
// prix_unit_ttc / taux_tva / optionnelle / typeLigne / variante et RIEN
// D'AUTRE : `prixManuel` revenait `undefined → false`. L'effet listes-de-prix
// ([clientId, lines.length]) relançait alors `refreshTarif` pour CHAQUE ligne
// au montage, et le tarif catalogue remplaçait le prix négocié que le vendeur
// avait tapé et ENREGISTRÉ.
//
// LE CORRECTIF (deux moitiés, les deux testées ici) :
//   • la LECTURE — le mappeur `?edit=` repose `prixManuel: !!l.prix_manuel`
//     (champ servi par la ligne depuis QJR59) ;
//   • l'ÉCRITURE — `lignesPayload` renvoie `prix_manuel` à la sauvegarde, sans
//     quoi le marqueur serait remis à `False` au premier enregistrement.
// La GARDE elle-même ne bouge pas : elle vit dans `refreshTarif`
// (`!l.prixManuel`), et l'effet déclencheur reste inchangé (cf.
// DevisGeneratorPrixManuel.test.mjs).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE, même
// patron que DevisGeneratorPrixManuel.test.mjs / DevisGeneratorOrdreLignes.
//
// Run : node --test src/pages/ventes/DevisGeneratorPrixManuelEdit.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// Le mappeur `?edit=` : de `ventesApi.getDevisById(editId)` jusqu'à `setLines`.
function mappeurEdit() {
  const start = DG.indexOf('ventesApi.getDevisById(editId).then(({ data: d }) => {')
  assert.ok(start > -1, "le chargement ?edit= (getDevisById) est introuvable")
  const end = DG.indexOf('setLines(withKeys(rows))', start)
  assert.ok(end > start, "la pose des lignes (setLines(withKeys(rows))) est introuvable")
  return DG.slice(start, end)
}

// La construction de `lignesPayload` dans `persisterDevis`.
function lignesPayload() {
  const start = DG.indexOf('const lignesPayload = keptLines.map((l, idx) => {')
  assert.ok(start > -1, 'lignesPayload introuvable')
  const end = DG.indexOf('let devisId', start)
  assert.ok(end > start, 'la fin de lignesPayload est introuvable')
  return DG.slice(start, end)
}

test('LECTURE — le mappeur ?edit= restaure prixManuel depuis le champ prix_manuel de la ligne', () => {
  assert.match(mappeurEdit(), /prixManuel:\s*!!l\.prix_manuel/)
})

test('LECTURE — le mappeur ?edit= restaure aussi les champs voisins (aucune régression du round-trip)', () => {
  const bloc = mappeurEdit()
  for (const attendu of [
    /optionnelle:\s*!!l\.optionnelle/,
    /typeLigne:\s*l\.type_ligne/,
    /variante:\s*l\.variante/,
  ]) assert.match(bloc, attendu)
})

test('ÉCRITURE — lignesPayload renvoie prix_manuel au serveur', () => {
  assert.match(lignesPayload(), /prix_manuel:\s*!!l\.prixManuel/)
})

test("ÉCRITURE — le marqueur ne part QUE sur les lignes produit (une section/note n'a ni prix ni marqueur)", () => {
  const bloc = lignesPayload()
  const structure = bloc.slice(bloc.indexOf('if (isStructure(l)) {'),
                               bloc.indexOf('return {', bloc.indexOf('if (isStructure(l)) {') + 20))
  assert.ok(structure.length > 0, 'la branche section/note est introuvable')
  assert.ok(!/prix_manuel/.test(structure),
            'une ligne de section/note ne doit jamais porter prix_manuel')
})

test('GARDE — refreshTarif protège toujours un prix manuel (la garde ne bouge pas, elle devient seulement atteignable après ?edit=)', () => {
  const start = DG.indexOf('const refreshTarif = useCallback(async (key, produitId, quantite) => {')
  assert.ok(start > -1, 'refreshTarif introuvable')
  assert.match(DG.slice(start, start + 1200), /\(l\._key === key && !l\.prixManuel\)/)
})
