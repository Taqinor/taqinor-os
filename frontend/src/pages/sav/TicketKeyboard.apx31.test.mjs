// APX31 — Checklist % partagee + J/K sur les tickets.
// ----------------------------------------------------------------------------
// Trois constats verifies, trois verrous :
//   1. `TicketChecklistPanel` affichait « X/Y points » en TEXTE PLAT alors que
//      `ChantierChecklist` avait deja une barre -> composant PARTAGE, adopte
//      aux DEUX endroits (jamais une 3e version) ;
//   2. `TicketWorksheetPanel` sortait du kit (form-label/form-control/checkbox
//      NATIVE) contrairement a tous ses voisins -> il rejoint le kit ;
//   3. aucune navigation clavier de liste cote SAV, alors que le patron J/K
//      existait cote leads (LW) -> memes gardes, jamais une copie de la garde.
//   node --test src/pages/sav/TicketKeyboard.apx31.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const lire = (p) => lf(readFileSync(join(HERE, p), 'utf8'))

const TICKETS = lire('TicketsPage.jsx')
const CHECKLIST_SAV = lire('TicketChecklistPanel.jsx')
const WORKSHEET = lire('TicketWorksheetPanel.jsx')
const CHECKLIST_CHANTIER = lire('../installations/ChantierChecklist.jsx')
const COMPOSANT = lire('../../ui/ChecklistProgress.jsx')
const UI_INDEX = lire('../../ui/index.js')
const RACCOURCIS = lire('../../providers/shortcuts.js')
const CHEATSHEET = lire('../../providers/ShortcutsProvider.jsx')
const LW = lire('../../features/crm/workspace/LeadWorkspace.jsx')

test('APX31 : UN composant d\'avancement, adopte par les DEUX panneaux', () => {
  assert.match(UI_INDEX, /export \* from '\.\/ChecklistProgress'/)
  assert.match(CHECKLIST_SAV, /<ChecklistProgress done=\{cochees\} total=\{items\.length\} noun="point" \/>/)
  assert.match(CHECKLIST_CHANTIER, /<ChecklistProgress percent=\{completion\} show="percent" \/>/)
  // Le texte plat a disparu cote SAV.
  assert.doesNotMatch(CHECKLIST_SAV, /point\{items\.length > 1 \? 's' : ''\} coché/)
  // ... et le chantier ne re-cable plus `Progress` a la main.
  assert.doesNotMatch(CHECKLIST_CHANTIER, /<Progress\b/)
})

test('APX31 : adopter le composant ne CHANGE PAS le nombre du chantier', () => {
  // Le serveur calcule `completion` (il peut ponderer autrement qu'un simple
  // done/total) : le composant accepte un pourcentage impose et le rend tel quel.
  assert.match(COMPOSANT, /percent: percentImpose/)
  assert.match(COMPOSANT, /percentImpose != null/)
})

test('APX31 : le composant est PUREMENT presentationnel (ni ticket, ni chantier)', () => {
  // C'est ce qui permettra a un 3e ecran de checklist de l'adopter sans le
  // deformer. On regarde le CODE, pas la prose (qui cite legitimement les deux
  // ecrans d'origine).
  const code = COMPOSANT.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  assert.doesNotMatch(code, /savApi|installationsApi|ticket|chantier/i)
  assert.doesNotMatch(code, /useEffect|useState|api\./)
  assert.match(COMPOSANT, /aria-label=\{`Avancement : \$\{compte\}`\}/)
})

test('APX31 : le worksheet rejoint le kit (Label / Input / Checkbox / Select)', () => {
  assert.match(WORKSHEET, /Badge, Button, Checkbox, Input, Label, Spinner,/)
  assert.match(WORKSHEET, /<Checkbox\s/)
  assert.match(WORKSHEET, /<Label htmlFor=\{id\}>/)
  assert.match(WORKSHEET, /<Input\s/)
  // Plus aucune classe de formulaire main-roulee ni de champ natif.
  assert.doesNotMatch(WORKSHEET, /className="form-label"/)
  assert.doesNotMatch(WORKSHEET, /className="form-control"/)
  assert.doesNotMatch(WORKSHEET, /<input id=\{id\} type="checkbox"/)
  assert.doesNotMatch(WORKSHEET, /<select id="ws-modele"/)
})

test('APX31 : J/K reutilise la garde champ-de-saisie de LW, jamais une copie locale', () => {
  assert.match(TICKETS, /import \{ isTypingTarget \} from '\.\.\/\.\.\/providers\/shortcuts'/)
  assert.match(LW, /import \{[^}]*isTypingTarget[^}]*\} from/s)
  // La garde n'est pas redefinie dans TicketsPage.
  assert.doesNotMatch(TICKETS, /function isTypingTarget/)
})

test('APX31 : J/K parcourt exactement ce que l\'oeil voit (liste filtree ET triee)', () => {
  assert.match(TICKETS, /const deplacerSelection = useCallback\(\(pas\) => \{/)
  assert.match(TICKETS, /const i = detailTicket \? rows\.findIndex\(\(r\) => r\.id === detailTicket\.id\) : -1/)
  // `rows` EST la liste filtree+triee rendue.
  assert.match(TICKETS, /const rows = useMemo\(\s*\n\s*\(\) => sortTickets\(filterTickets\(items, filters\), 'statut', 'asc'\),/)
})

test('APX31 : les 4 touches sont cablees, sans voler de modificateur', () => {
  const i = TICKETS.indexOf('const deplacerSelection')
  const bloc = TICKETS.slice(i, i + 2200)
  assert.match(bloc, /if \(e\.metaKey \|\| e\.ctrlKey \|\| e\.altKey\) return/)
  assert.match(bloc, /e\.key === 'j' \|\| e\.key === 'J'/)
  assert.match(bloc, /e\.key === 'k' \|\| e\.key === 'K'/)
  assert.match(bloc, /e\.key === 'Enter' && !detailTicket && rows\.length/)
  assert.match(bloc, /e\.key === 'Escape' && detailTicket/)
  // Effet AVEC dep array (jamais un re-abonnement a chaque rendu).
  assert.match(bloc, /return \(\) => window\.removeEventListener\('keydown', onKey\)/)
  assert.match(bloc, /\}, \[deplacerSelection, detailTicket, rows, searchParams\]\)/)
})

test('APX31 : Entree n\'est PAS volee quand un detail est deja ouvert', () => {
  // Sans cette garde, Entree sur un bouton du panneau rouvrirait le 1er ticket.
  assert.match(TICKETS, /e\.key === 'Enter' && !detailTicket/)
})

test('APX31 : l\'aide « ? » annonce les raccourcis de liste', () => {
  assert.match(RACCOURCIS, /export const LIST_SHORTCUTS = \[/)
  assert.match(RACCOURCIS, /\{ keys: 'J', label: 'Enregistrement suivant dans la liste' \}/)
  assert.match(RACCOURCIS, /\{ keys: 'K', label: 'Enregistrement précédent dans la liste' \}/)
  assert.match(CHEATSHEET, /\{ title: 'Listes', items: LIST_SHORTCUTS \}/)
})
