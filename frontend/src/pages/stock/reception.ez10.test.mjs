// EZ10 — Réception sans surprise : défauts + recherche + « Ranger maintenant ».
// État d'avant : la date valait '' ; le sélecteur de bon de commande était le
// Select sans recherche ; la quantité reçue n'était pas pré-remplie (le
// magasinier retapait la commande ligne par ligne) ; et la bannière de succès
// n'offrait AUCUNE suite — réception (Stock) et rangement (Magasin) étaient
// deux navigations sans lien.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = readFileSync(path.join(__dirname, 'ReceptionsFournisseur.jsx'), 'utf8')

test('la date de réception vaut AUJOURD’HUI par défaut', () => {
  assert.match(src, /useState\(\(\) => new Date\(\)\.toISOString\(\)\.slice\(0, 10\)\)/)
  assert.doesNotMatch(src, /const \[dateReception, setDateReception\] = useState\(''\)/)
})

test('la quantité reçue est pré-remplie au RESTE commandé', () => {
  // Le pré-remplissage se fait au chargement du détail du BCF, à partir du
  // reste réellement dû (jamais au-delà).
  assert.match(src, /const prefill = \{\}/)
  assert.match(src, /const reste = resteLigne\(l\)/)
  assert.match(src, /if \(reste > 0\) prefill\[l\.id\] = String\(reste\)/)
  assert.match(src, /setSaisies\(prefill\)/)
  // Et plus l'ancien reset à vide.
  assert.doesNotMatch(src, /setBon\(r\.data\); setSaisies\(\{\}\)/)
})

test('le bon de commande se CHERCHE (Combobox du kit, zéro composant nouveau)', () => {
  assert.match(src, /<Combobox\r?\n\s+id="rec-bon"/)
  assert.match(src, /searchPlaceholder="Référence ou fournisseur…"/)
  // Le Select sans recherche a disparu de l'écran.
  assert.doesNotMatch(src, /<SelectTrigger id="rec-bon"/)
  assert.doesNotMatch(src, /\n\s+Select, SelectTrigger/)
})

test('la bannière de succès offre la SUITE : « Ranger maintenant »', () => {
  assert.match(src, /data-testid="reception-succes"/)
  assert.match(src, /data-testid="reception-ranger"/)
  assert.match(src, /<Link to="\/magasin\/rangement">Ranger maintenant/)
})

test('le deep-link reste HONNÊTE : aucun pré-filtre promis', () => {
  // Ni l'écran de rangement ni `PutAwayViewSet` ne supportent un pré-filtre :
  // on ne met donc AUCUN paramètre dans le lien.
  assert.doesNotMatch(src, /\/magasin\/rangement\?/)
})

test('budget : une réception conforme ne demande AUCUNE saisie de quantité', () => {
  // Choisir le BCF (1) → Confirmer (1) ; la date et les quantités sont déjà
  // justes. Une saisie ne reste nécessaire QUE sur les lignes en écart.
  assert.match(src, /Confirmer la réception/)
  assert.match(src, /value=\{saisies\[l\.id\] \?\? ''\}/)
})
