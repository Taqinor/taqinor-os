// APX4 — Les 6 etapes du funnel visibles : colonnes fluides 204 px + plein
// ecran board.
// ----------------------------------------------------------------------------
// La MESURE (« 6/6 colonnes sans scroll horizontal en 1440x900 sidebar repliee
// ET 1920x1080 depliee ») appartient a la gate e2e APX8 — jsdom ne calcule
// aucune largeur. Ce fichier verrouille ce qui rendrait cette mesure fausse ou
// dangereuse : le nombre d'etapes vient de STAGES.py (regle #2), le scope ne
// deborde pas sur les boards voisins, la colonne repliee LB10 garde son rail,
// et le plein ecran ne touche PAS la preference globale de sidebar.
//   node --test src/pages/crm/leads/LeadsBoardColumns.apx4.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const CSS = lf(readFileSync(join(HERE, '../../../index.css'), 'utf8'))
const LEADS = lf(readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8'))
const STAGES = lf(readFileSync(join(HERE, '../../../../../STAGES.py'), 'utf8'))

const bloc = () => {
  const i = CSS.indexOf('APX4 — LES 6 ETAPES DU FUNNEL VISIBLES')
  assert.ok(i > -1, 'bloc CSS APX4 introuvable')
  const debut = CSS.lastIndexOf('/*', i)
  const suivant = CSS.indexOf('/* ====', i)
  return suivant > -1 ? CSS.slice(debut, suivant) : CSS.slice(debut)
}

test('APX4 : le « 6 » du dimensionnement est bien le nombre d\'etapes de STAGES.py (regle #2)', () => {
  // Le calcul de seuil (6 x 204 + 5 x 12) n'a de sens que si le funnel compte
  // 6 etapes — et cette verite vit dans STAGES.py, jamais dans une liste ecrite
  // a la main quelque part dans le front.
  const cles = STAGES.match(/^\s*(NEW|CONTACTED|QUOTE_SENT|FOLLOW_UP|SIGNED|COLD)\s*=/gm) ?? []
  assert.equal(new Set(cles.map((c) => c.trim())).size, 6)
  // Le board ne code AUCUNE liste d'etapes : il consomme features/crm/stages.
  assert.doesNotMatch(LEADS, /\['NEW',\s*'CONTACTED'/)
})

test('APX4 : minmax(204px, 1fr) — l\'equivalent flex exact, scope au board leads', () => {
  const b = bloc()
  assert.match(b, /\.lp-page\[data-view\] \.kb-col:not\(\.kb-col-collapsed\) \{\s*\n\s*flex: 1 1 204px;\s*\n\s*min-width: 204px;/)
  // `.kb-col` est partage avec Installations/Interventions : toute regle du
  // bloc DOIT porter le discriminant, sauf le bouton et le calque plein ecran
  // (classes creees par cette tache, inexistantes ailleurs).
  const propres = ['.lp-fullscreen-btn', '.lp-page--fullscreen']
  for (const ligne of b.split('\n')) {
    const t = ligne.trim()
    if (!/^\.[\w.[\]='"()>\s:-]+[,{]\s*$/.test(t)) continue
    if (propres.some((c) => t.startsWith(c))) continue
    assert.ok(t.includes('[data-view]'), `regle APX4 non scopee au board leads : ${t}`)
  }
})

test('APX4 : la colonne repliee (LB10) garde son rail de 44 px', () => {
  // `:not(.kb-col-collapsed)` est ce qui l'en preserve — sans lui, une colonne
  // repliee se remettrait a 204 px et LB10 serait mort sans bruit.
  assert.match(bloc(), /:not\(\.kb-col-collapsed\)/)
  assert.match(CSS, /\.kb-col-collapsed \{\s*\n\s*flex: 0 0 44px;/)
})

test('APX4 : sous le seuil, le comportement actuel est preserve (palier iPad VX183a)', () => {
  const b = bloc()
  assert.match(b, /@media \(max-width: 1024px\) and \(min-width: 900px\)/)
  // Le scroll horizontal + drag-to-pan LB11 restent la voie de secours : APX4
  // ne redefinit AUCUN overflow sur le board ni sur les colonnes, et
  // `.kb-board { overflow: auto }` reste en place.
  const reglesColonnes = b.slice(0, b.indexOf('.lp-fullscreen-btn'))
  assert.doesNotMatch(reglesColonnes.replace(/\/\*[\s\S]*?\*\//g, ''), /overflow/)
  assert.match(CSS, /\.kb-board \{[^}]*overflow: auto;/s)
  assert.match(LEADS, /usePanScroll|<KanbanView/)
})

test('APX4 : le bouton plein ecran existe, est accessible et masque au telephone', () => {
  assert.match(LEADS, /className="lp-fullscreen-btn"/)
  assert.match(LEADS, /aria-pressed=\{boardFullscreen\}/)
  assert.match(LEADS, /\{!isMobile && \(\s*\n\s*<button/)
  // Libelle ET titre en francais, avec le rappel du raccourci de sortie.
  assert.match(LEADS, /Quitter le plein écran \(Échap\)/)
})

test('APX4 : le plein ecran ne touche JAMAIS la preference globale de sidebar', () => {
  // `taqinor.sidebar.collapsed` appartient a Layout.jsx (autre lane) et vaut
  // pour TOUT l'ERP : le mode plein ecran des leads a sa propre cle, locale.
  assert.doesNotMatch(LEADS, /taqinor\.sidebar\.collapsed/)
  assert.match(LEADS, /const BOARD_FULLSCREEN_KEY = 'taqinor\.leads\.boardFullscreen'/)
})

test('APX4 : Echap sort du plein ecran, et l\'ecouteur n\'est monte QUE dans ce mode', () => {
  const i = LEADS.indexOf('if (!boardFullscreen) return undefined')
  assert.ok(i > -1, 'garde de montage de l\'ecouteur Echap introuvable')
  const effet = LEADS.slice(i, i + 600)
  assert.match(effet, /e\.key === 'Escape'/)
  assert.match(effet, /window\.addEventListener\('keydown', onKey\)/)
  assert.match(effet, /return \(\) => window\.removeEventListener\('keydown', onKey\)/)
})

test('APX4 : le calque plein ecran couvre le shell sans casser le bornage de hauteur', () => {
  const b = bloc()
  assert.match(b, /\.lp-page--fullscreen \{[^}]*position: fixed;[^}]*inset: 0;/s)
  // La chaine de hauteur LB33 reste la source du bornage : le calque ne
  // redefinit pas `height` sur `.lp-page` (qui vaut deja 100%).
  const regle = b.slice(b.indexOf('.lp-page--fullscreen {'))
  assert.doesNotMatch(regle.slice(0, regle.indexOf('}')), /height:/)
})

test('APX4 : aucun hex en dur (tokens semantiques uniquement)', () => {
  assert.doesNotMatch(bloc().replace(/\/\*[\s\S]*?\*\//g, ''), /#[0-9a-fA-F]{3,8}\b/)
})
