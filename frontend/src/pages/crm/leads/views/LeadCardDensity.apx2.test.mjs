// APX2 — Carte lead au REPOS : 3 lignes, budget de signaux FERMÉ.
// ----------------------------------------------------------------------------
// Le contrat LB13 « 4 zones » est explicitement remplacé par un contrat à
// 3 lignes (L1 nom+société / L2 montant+signaux / L3 points de tags+âge+avatar),
// tout le reste étant CONDENSÉ dans une zone révélée — jamais supprimé.
// La MESURE en pixels (≤76 px au repos, ≥7 cartes/colonne) appartient à la
// gate e2e APX8 ; ce fichier verrouille les INVARIANTS de structure que la
// mesure présuppose, et il tourne sans navigateur (pas de node_modules dans
// cette lane).
//   node --test src/pages/crm/leads/views/LeadCardDensity.apx2.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')
const CSS = readFileSync(join(HERE, '../../../../index.css'), 'utf8')

const reveal = () => {
  const start = SRC.indexOf('<div className="kb-card-reveal">')
  assert.ok(start > -1, 'kb-card-reveal introuvable')
  return SRC.slice(start)
}
const restingFoot = () => {
  const start = SRC.indexOf('<div className="kb-card-foot">')
  const end = SRC.indexOf('{/* ── ZONE RÉVÉLÉE', start)
  assert.ok(end > start, 'pied de repos introuvable')
  return SRC.slice(start, end)
}

test('APX2 : la densité est SCOPÉE au lead (.kb-card--lead), jamais au .kb-card partagé', () => {
  // `.kb-card` est aussi porté par le kanban Installations et StatusAccentCard
  // (autres lanes) : aucune règle de densité APX2 ne doit les atteindre.
  assert.match(SRC, /'kb-card--lead',/)
  const bloc = CSS.slice(CSS.indexOf('APX2 — LA CARTE LEAD AU REPOS'))
  assert.ok(bloc.length > 0, 'bloc CSS APX2 introuvable')
  for (const ligne of bloc.split('\n')) {
    // Un sélecteur qui commence par `.kb-card` DOIT être `.kb-card--lead`.
    if (/^\s*\.kb-card[^-]/.test(ligne)) {
      assert.fail(`règle APX2 non scopée au lead : ${ligne.trim()}`)
    }
  }
})

test('APX2 : L1 = nom + société tronqués sur une seule ligne', () => {
  assert.match(SRC, /const societeLabel = lead\.societe && lead\.societe !== nomComplet \? lead\.societe : null/)
  assert.match(SRC, /\{societeLabel && <span className="kb-card-societe">\{societeLabel\}<\/span>\}/)
  // Troncature CSS (jamais un slice JS qui casserait la recherche/le titre).
  const bloc = CSS.slice(CSS.indexOf('.kb-card--lead .kb-card-name {'))
  assert.match(bloc.slice(0, 400), /white-space: nowrap/)
  assert.match(bloc.slice(0, 400), /text-overflow: ellipsis/)
})

test('APX2 : L2 porte le BUDGET DE SIGNAUX complet — icône d\'action + score + rotting', () => {
  const start = SRC.indexOf('<div className="kb-card-value">')
  const end = SRC.indexOf('{/* ── L3 / PIED', start)
  assert.ok(end > start, 'zone valeur introuvable')
  const value = SRC.slice(start, end)
  assert.match(value, /className="kb-card-montant num"/)
  assert.match(value, /className=\{`kb-card-signal kb-signal-\$\{signal\.tone\}`\}/)
  assert.match(value, /className="kb-card-score-micro"/)
  assert.match(value, /className="kb-rot-dot"/)
})

test('APX2 : l\'icône d\'action dérive de la MÊME précédence que le texte révélé', () => {
  // Une seule source de vérité : impossible que l'icône au repos et le texte
  // révélé racontent deux histoires différentes.
  assert.match(SRC, /function signalFor\(/)
  for (const cle of ['perdu', 'relanceEnRetard', 'rappelDemande', 'dernierDevisExpire', 'factureManquante']) {
    assert.match(SRC, new RegExp(`if \\(${cle}\\)|${cle},`), `précédence ${cle} absente de signalFor`)
  }
  // Le SLA premier-contact (QX31) et l'activité planifiée en font partie.
  assert.match(SRC, /slaMinutes: minutesNouveau/)
  assert.match(SRC, /nextActivityState: lead\.next_activity\?\.state \?\? null/)
})

test('APX2 : le signal d\'action n\'est JAMAIS supprimé au repos (il n\'est pas dans la zone révélée)', () => {
  const revealed = reveal()
  assert.doesNotMatch(revealed, /kb-card-signal kb-signal-/)
  // …et il porte un nom accessible (lecteur d'écran) en plus de la couleur :
  // la distinction ne repose donc jamais sur la seule couleur.
  assert.match(SRC, /aria-label=\{signal\.label\}/)
})

test('APX2 : L3 = points de tags (3 + n) · âge · avatar 16', () => {
  const foot = restingFoot()
  assert.match(foot, /className="kb-tag-dots"/)
  assert.match(foot, /className="kb-tag-dot"/)
  assert.match(foot, /kb-tag-dots-more/)
  assert.match(foot, /className="kb-age-pill"/)
  assert.match(foot, /size=\{16\}/)
  assert.match(SRC, /const TAG_DOTS_VISIBLE = 3/)
  // Les points portent un nom accessible listant TOUS les tags.
  assert.match(foot, /aria-label=\{`Étiquettes : \$\{tags\.join\(', '\)\}`\}/)
})

test('APX2 : tout ce qui quitte le repos est CONDENSÉ dans la zone révélée, jamais supprimé', () => {
  const revealed = reveal()
  assert.match(revealed, /className="kb-card-type"/)          // chip type d'installation
  assert.match(revealed, /kb-card-actionline/)                 // texte de la ligne d'action
  assert.match(revealed, /className="kb-foot-meta"/)           // canal · ville
  assert.match(revealed, /className="kb-readi"/)               // readiness
  assert.match(revealed, /className="kb-tags"/)                // libellés de tags en clair
  // APX7 — les actions rapides ont quitté la zone révélée pour la ligne du
  // montant (L2) : au TOUCHER, la zone révélée est fermée, et c'est justement
  // là que tel/WhatsApp doivent rester atteignables sans survol (VX68).
  const valueStart = SRC.indexOf('<div className="kb-card-value">')
  const valueEnd = SRC.indexOf('{/* ── L3 / PIED', valueStart)
  assert.match(SRC.slice(valueStart, valueEnd), /className="kb-quick"/)
})

test('APX2 : la zone révélée est le DERNIER enfant en flux (elle ne pousse rien sous le curseur)', () => {
  const iValue = SRC.indexOf('<div className="kb-card-value">')
  const iFoot = SRC.indexOf('<div className="kb-card-foot">')
  const iReveal = SRC.indexOf('<div className="kb-card-reveal">')
  assert.ok(iValue < iFoot, 'L2 doit précéder L3')
  assert.ok(iFoot < iReveal, 'la zone révélée doit venir APRÈS les 3 lignes de repos')
})

test('APX2 : révélation par (hover:hover) OU :focus-within — jamais par une largeur d\'écran', () => {
  const bloc = CSS.slice(CSS.indexOf('APX2 — LA CARTE LEAD AU REPOS'))
  assert.match(bloc, /@media \(hover: hover\) \{\s*\n\s*\.kb-card--lead:hover > \.kb-card-reveal/)
  assert.match(bloc, /\.kb-card--lead:focus-within > \.kb-card-reveal \{/)
  assert.match(bloc, /@media \(hover: none\) \{/)
  // Aucun seuil de largeur ne pilote la révélation (l'iPad hover:none hérite
  // de l'anatomie tactile, jamais d'un breakpoint).
  const regles = bloc.split('@media').filter((m) => /kb-card-reveal/.test(m))
  for (const m of regles) {
    assert.doesNotMatch(m.split('{')[0], /width/, 'la révélation ne doit pas dépendre d\'une largeur')
  }
})

test('APX2 : :focus-within DÉPLIE réellement (pas de visibility:hidden qui bloquerait le focus)', () => {
  const bloc = CSS.slice(CSS.indexOf('APX2 — LA CARTE LEAD AU REPOS'))
  const collapse = bloc.slice(bloc.indexOf('.kb-card--lead .kb-card-reveal {'))
  assert.doesNotMatch(collapse.slice(0, 500), /visibility:\s*hidden/)
  assert.match(collapse.slice(0, 500), /max-height: 0/)
})

test('APX2 : mouvement réduit respecté (dépliage instantané, jamais supprimé)', () => {
  const bloc = CSS.slice(CSS.indexOf('APX2 — LA CARTE LEAD AU REPOS'))
  assert.match(bloc, /@media \(prefers-reduced-motion: reduce\) \{\s*\n\s*\.kb-card--lead \.kb-card-reveal \{ transition: none; \}/)
})

test('APX2 : le clic « n\'importe où » ouvre toujours la fiche (contrat LB préservé)', () => {
  assert.match(SRC, /onClick=\{onOpen \? \(\) => onOpen\(lead\) : undefined\}/)
})

test('APX2 : les tons de signaux réutilisent les tokens sémantiques (AA clair ET sombre)', () => {
  const bloc = CSS.slice(CSS.indexOf('APX2 — LA CARTE LEAD AU REPOS'))
  assert.match(bloc, /\.kb-signal-danger \{ color: var\(--destructive\); \}|\.kb-signal-danger \{ color: var\(--destructive\); \}/)
  assert.match(bloc, /\.kb-signal-warning \{ color: var\(--warning-text\); \}/)
  assert.match(bloc, /\.kb-signal-info \{ color: var\(--info\); \}/)
  assert.match(bloc, /\.kb-signal-success \{ color: var\(--success\); \}/)
  assert.match(bloc, /\.kb-signal-muted \{ color: var\(--muted-foreground\); \}/)
  // Aucun hex en dur dans le bloc APX2.
  assert.doesNotMatch(bloc, /#[0-9a-fA-F]{3,8}\b/)
})
