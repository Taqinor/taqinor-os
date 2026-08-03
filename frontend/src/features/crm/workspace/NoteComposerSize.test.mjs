// ORDRE FONDATEUR 2026-08-01 — « la zone de NOTE de la fenêtre lead est trop
// petite ». Deux choses qu'un test de rendu (TimelineTab.test.jsx, jsdom sans
// CSS) ne peut PAS attraper, et qui casseraient en silence :
//   1. les bornes de hauteur, qui vivent en CSS et en `em` ;
//   2. le couplage entre la classe du champ et le sélecteur de focus du
//      bouton « 📝 Note » du thumbbar (ContextRail) — exactement la classe de
//      bug LW44 : un querySelector qui ne matche plus rien est un no-op
//      parfaitement silencieux, aucun test de logique ne le voit.
//   node --test src/features/crm/workspace/NoteComposerSize.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const TAB = lf(readFileSync(join(HERE, 'TimelineTab.jsx'), 'utf8'))
const RAIL = lf(readFileSync(join(HERE, 'ContextRail.jsx'), 'utf8'))
// workspace → crm → features → src/index.css
const CSS = lf(readFileSync(join(HERE, '..', '..', '..', 'index.css'), 'utf8'))

test('la note s’ouvre sur 3 lignes et grandit jusqu’à 8, puis DÉFILE', () => {
  const debut = CSS.indexOf('.chatter-note-box textarea.chatter-note-input {')
  assert.ok(debut > 0, 'règle du composer de note introuvable')
  const regle = CSS.slice(debut, CSS.indexOf('}', debut))
  // Bornes en `em` : elles suivent la taille de police et le zoom du
  // navigateur — une borne en px se décale au premier réglage d'accessibilité.
  assert.match(regle, /min-height:\s*calc\(3 \* 1\.45em/)
  assert.match(regle, /max-height:\s*calc\(8 \* 1\.45em/)
  // C'est le max-height qui produit le défilement interne : aucun comptage de
  // lignes en JS.
  assert.match(regle, /overflow-y:\s*auto/)
  // La poignée de redimensionnement et l'autosize se battraient pour la même
  // propriété : la frappe suivante effacerait le réglage manuel.
  assert.match(regle, /resize:\s*none/)
})

test("les boutons du composer ne grandissent PAS avec le champ", () => {
  const debut = CSS.indexOf('.chatter-note-box {')
  const regle = CSS.slice(debut, CSS.indexOf('}', debut))
  // Sans ça, l'étirement flex par défaut donnerait un bouton « Noter » aussi
  // haut que la zone de saisie.
  // ORDRE FONDATEUR 2026-08-02 — « toute la ligne » : la boîte est une
  // COLONNE (champ pleine largeur seul sur sa rangée), les actions descendent
  // sur une rangée dédiée alignée à droite. L'ancien `align-items: flex-end`
  // (rangée champ+boutons) est le contrat inverse : il ne doit PAS revenir.
  assert.match(regle, /flex-direction:\s*column/)
  assert.match(regle, /align-items:\s*stretch/)
  assert.doesNotMatch(regle, /align-items:\s*flex-end/)
})

test("l'autosize mesure le contenu, jamais sa propre hauteur", () => {
  const debut = TAB.indexOf('const noteRef = useRef(null)')
  assert.ok(debut > 0, 'autosize introuvable')
  const corps = TAB.slice(debut, TAB.indexOf('\n  }, [composer.note])', debut))
  // Remettre à `auto` AVANT de lire scrollHeight : sinon on mesure la hauteur
  // qu'on a soi-même posée au frame précédent et le champ ne RÉTRÉCIT jamais.
  const remiseAZero = corps.indexOf("el.style.height = 'auto'")
  const mesure = corps.indexOf('el.scrollHeight')
  assert.ok(remiseAZero > 0 && mesure > remiseAZero, "la remise à 'auto' doit précéder la mesure")
  // Avant la peinture : le champ ne saute jamais.
  assert.match(TAB, /useLayoutEffect\(\(\) => \{/)
  // Les bornes ne sont PAS en JS.
  assert.doesNotMatch(corps, /Math\.min|Math\.max|maxHeight|minHeight/)
})

test('Entrée écrit une ligne ; Ctrl/⌘+Entrée envoie', () => {
  assert.match(TAB, /if \(e\.key === 'Enter' && \(e\.ctrlKey \|\| e\.metaKey\)\)/)
  // L'ancien « Entrée poste » rendait une note multiligne impossible à taper.
  assert.doesNotMatch(TAB, /if \(e\.key === 'Enter'\) \{/)
})

test("le bouton « 📝 Note » du thumbbar focalise toujours le champ (classe de bug LW44)", () => {
  // Le sélecteur de ContextRail et la classe posée par TimelineTab sont un
  // COUPLAGE inter-fichiers : c'est lui qu'on épingle, pas chacun de son côté.
  assert.match(TAB, /className="form-control chatter-note-input"/)
  assert.match(RAIL, /\.chatter-note-box textarea\.chatter-note-input/)
  // L'ancien sélecteur visait une <input> : il ne matcherait plus rien.
  assert.doesNotMatch(RAIL, /\.chatter-note-box input\.form-control/)
  // Pleine largeur réelle + rangée d'actions dédiée (contrat CSS, ordre
  // fondateur 2026-08-02 « toute la ligne »).
  assert.match(CSS, /\.chatter-note-box \.form-control \{ width: 100%; \}/)
  assert.match(CSS, /\.chatter-note-actions \{/)
})
