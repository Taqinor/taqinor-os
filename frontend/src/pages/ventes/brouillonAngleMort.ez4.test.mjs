// EZ4 — Le brouillon n'a plus d'angle mort (les LIGNES n'étaient pas couvertes).
// Le prédicat `dirty` de l'autosave VX62 ignorait `lines`, `discountPct`,
// `tauxTva` et `villaGroups` — alors que ces quatre champs étaient DÉJÀ dans
// `draftSnapshot`. Un utilisateur qui n'avait fait qu'ajouter des LIGNES (le
// cœur du devis) n'était donc ni sauvegardé ni protégé par la garde de
// fermeture d'onglet. Seul le prédicat était à corriger.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const gen = readFileSync(path.join(__dirname, 'DevisGenerator.jsx'), 'utf8')
const hook = readFileSync(path.join(__dirname, '..', '..', 'ui', 'useDraftAutosave.js'), 'utf8')

const dirtyBloc = gen.slice(gen.indexOf('const lignesSaisies'), gen.indexOf('useDirtyGuard(dirty)'))

test('les 4 champs de l’angle mort entrent dans le prédicat `dirty`', () => {
  for (const signal of ['lignesSaisies', 'remiseSaisie', 'tvaModifiee', 'villasSaisies']) {
    assert.ok(dirtyBloc.includes(signal), `${signal} absent du prédicat`)
  }
  // Une LIGNE compte dès qu'elle porte un produit, une désignation ou un prix.
  assert.match(dirtyBloc, /lines\.some\(/)
  assert.match(dirtyBloc, /l\.produit \|\| \(l\.designation \|\| ''\)\.trim\(\) \|\| parseFloat\(l\.prix_unit_ttc\) > 0/)
})

test('les signaux restent HONNÊTES : aucun défaut ne rend le formulaire sale', () => {
  // `villaGroups` porte des libellés PAR DÉFAUT : le signal utile est le mode
  // multi-propriétés (défaut 'none'), sinon tout formulaire vierge serait sale.
  assert.match(dirtyBloc, /const villasSaisies = multiMode !== 'none'/)
  // La TVA ne compte que si elle diffère du taux standard.
  assert.match(dirtyBloc, /parseFloat\(tauxTva\) !== TVA_STANDARD_DEFAUT/)
  // La remise ne compte qu'au-dessus de zéro.
  assert.match(dirtyBloc, /parseFloat\(discountPct\) > 0/)
})

test('le snapshot lui-même n’a pas bougé (il portait déjà les 4 champs)', () => {
  const snap = gen.slice(gen.indexOf('const draftSnapshot = useMemo'), gen.indexOf('], [\r\n    leadId'))
  for (const champ of ['lines', 'tauxTva', 'discountPct', 'villaGroups']) {
    assert.ok(snap.includes(champ), `${champ} absent du snapshot`)
  }
})

test('la continuité est VISIBLE : « Brouillon enregistré à HH:MM »', () => {
  assert.match(gen, /data-testid="draft-saved-indicator"/)
  assert.match(gen, /Brouillon enregistré à/)
  // L'horodatage vient du hook (ajout purement additif : les consommateurs
  // existants continuent d'ignorer ce champ de retour).
  assert.match(hook, /return \{ restored, restore, discard, clear, savedAt \}/)
  assert.match(hook, /setSavedAt\(stamp\)/)
  // Purger le brouillon (succès de soumission) efface aussi l'indicateur.
  assert.match(hook, /setSavedAt\(null\)/)
})
