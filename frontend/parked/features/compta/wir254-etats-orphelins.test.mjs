// WIR254 — ~15 états d'analyse d'EtatsComptablesViewSet jusqu'ici orphelins
// (aucun client comptaApi, aucun écran) : SIMPL-IS/loi-69-21 mis à part
// (WIR180, déjà couverts par leur propre test), tout le reste (référentiel
// parallèle/analytique, budget vs engagements, cockpit de clôture,
// immobilisations avancées, IFRS 15, frais bancaires, rapprochements
// auxiliaires) a désormais un wrapper `comptaApi.etats.*` — rendu sur le
// tableau générique d'EtatsPage ou sur l'écran hôte dédié
// (Budgets/Cloture/Immobilisations avancées/RevenuIfrs15/Trésorerie/
// Référentiels analytiques). Ce test SOURCE (comme wir180.test.mjs) est la
// garde : « actions GET d'EtatsComptablesViewSet − API-only ⊆ clés
// comptaApi.etats » — un futur `@action` sans wrapper rougit ici, sans
// attendre qu'un écran retombe en silence sur des tirets.
//   node --test src/features/compta/wir254-etats-orphelins.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const VIEWS_SRC = readFileSync(
  join(HERE, '../../../../backend/django_core/apps/compta/views.py'), 'utf8')
const API_SRC = readFileSync(join(HERE, '../../api/comptaApi.js'), 'utf8')

// API-only volontaire (patron WIR107) : aucune @action GET de
// EtatsComptablesViewSet n'est dans ce cas aujourd'hui — chaque état a un
// écran (voir l'en-tête ci-dessus) — mais l'ensemble reste déclaré ici pour
// que la garde continue de composer si une future action rejoint ce choix
// délibéré sans écran dédié.
const API_ONLY = new Set([])

// ── Masquage JS : neutralise commentaires ET chaînes AVANT tout comptage de
// profondeur / découpage par virgule. SANS CECI, une virgule dans un simple
// commentaire (ex. « PACT18 — SOULIGNÉ, pas tiret ») casse le découpage —
// mesuré : ça ferait manquer jusqu'à `grandLivre` lui-même, le tout premier
// wrapper du fichier. Les longueurs sont préservées (remplacement caractère
// par caractère) pour que les index restent valides sur le texte original.
function masquerJs(src) {
  let out = ''
  let i = 0
  while (i < src.length) {
    const c = src[i]
    const deux = src.slice(i, i + 2)
    if (deux === '//') {
      let fin = src.indexOf('\n', i)
      if (fin === -1) fin = src.length
      out += ' '.repeat(fin - i)
      i = fin
      continue
    }
    if (deux === '/*') {
      let fin = src.indexOf('*/', i + 2)
      fin = fin === -1 ? src.length : fin + 2
      out += src.slice(i, fin).replace(/[^\n]/g, ' ')
      i = fin
      continue
    }
    if (c === "'" || c === '"' || c === '`') {
      let j = i + 1
      while (j < src.length && src[j] !== c) {
        j += (src[j] === '\\' ? 2 : 1)
      }
      j = Math.min(j + 1, src.length)              // inclut le guillemet fermant
      out += c + 'x'.repeat(Math.max(0, j - i - 2)) + src.slice(i + 1, j).slice(-1)
      i = j
      continue
    }
    out += c
    i += 1
  }
  return out
}

function extraireClasse(source, nomClasse) {
  const debut = source.indexOf(`class ${nomClasse}(`)
  assert.notEqual(debut, -1, `classe ${nomClasse} introuvable dans views.py`)
  const suite = source.indexOf('\nclass ', debut + 1)
  return suite === -1 ? source.slice(debut) : source.slice(debut, suite)
}

// snake_case (nom de méthode Python) -> camelCase (convention de comptaApi.js).
function versCamel(nom) {
  return nom.replace(/_([a-zA-Z0-9])/g, (_, c) => c.toUpperCase())
}

// [nom] — chaque @action GET `detail=False` de la classe, en appariant le
// DERNIER `@action(` avant un `def xxx(self, request` (les parenthèses sont
// comptées à la main : un `url_path` regex, comme celui de
// `releve_fournisseur`, contient lui-même des parenthèses littérales — les
// docstrings ne sont JAMAIS traversées, la recherche s'arrête au `def`).
function actionsGetDetailFalse(classeSrc) {
  const actions = []
  const defRe = /\n {4}def (\w+)\(self, request/g
  let m
  while ((m = defRe.exec(classeSrc))) {
    const nom = m[1]
    const avant = classeSrc.slice(0, m.index)
    const dernierDef = avant.lastIndexOf('\n    def ')
    const zone = avant.slice(dernierDef + 1)
    const idxAction = zone.lastIndexOf('@action(')
    if (idxAction === -1) continue          // pas une @action (helper privé)
    let profondeur = 1
    let i = idxAction + '@action('.length
    while (profondeur > 0 && i < zone.length) {
      if (zone[i] === '(') profondeur += 1
      else if (zone[i] === ')') profondeur -= 1
      i += 1
    }
    const decorateur = zone.slice(idxAction, i)
    if (!/detail=False/.test(decorateur)) continue
    if (!/methods=\[\s*['"]get['"]\s*\]/.test(decorateur)) continue
    actions.push(nom)
  }
  return actions
}

// Bornes {debut, fin} du corps `{ ... }` qui suit `étiquette:` dans le texte
// MASQUÉ (compte uniquement les accolades — chaînes/commentaires neutralisés).
function bornesCorpsObjet(masque, depuisIndex) {
  const debutAccolade = masque.indexOf('{', depuisIndex)
  assert.notEqual(debutAccolade, -1, 'accolade ouvrante introuvable')
  let profondeur = 0
  for (let i = debutAccolade; i < masque.length; i += 1) {
    if (masque[i] === '{') profondeur += 1
    else if (masque[i] === '}') {
      profondeur -= 1
      if (profondeur === 0) return { debut: debutAccolade + 1, fin: i }
    }
  }
  throw new Error('accolade non refermée')
}

// Clés du PREMIER niveau d'un objet JS littéral : découpe le corps MASQUÉ par
// virgule de profondeur 0 (accolades/crochets/parenthèses comptés), PUIS
// capture le nom de clé en tête de chaque morceau — sur le texte MASQUÉ, pas
// l'original : un commentaire multi-lignes précédant une clé (ex. PACT18 sur
// `grandLivre`, WIR180 sur `exportSimplIs`) reste du texte non-blanc dans
// l'original (le `^\s*` de la regex ne peut pas le franchir, donc ÉCHOUE),
// alors qu'il redevient une pure série d'espaces après masquage — franchissable.
function clesPremierNiveau(masque, debut, fin) {
  const corpsMasque = masque.slice(debut, fin)
  const morceaux = []
  let profondeur = 0
  let debutMorceau = 0
  for (let i = 0; i < corpsMasque.length; i += 1) {
    const c = corpsMasque[i]
    if ('{[('.includes(c)) profondeur += 1
    else if ('}])'.includes(c)) profondeur -= 1
    else if (c === ',' && profondeur === 0) {
      morceaux.push([debutMorceau, i])
      debutMorceau = i + 1
    }
  }
  morceaux.push([debutMorceau, corpsMasque.length])
  const cles = []
  for (const [a, b] of morceaux) {
    const mc = corpsMasque.slice(a, b).match(/^\s*(\w+)\s*:/)
    if (mc) cles.push(mc[1])
  }
  return cles
}

function clesEtats() {
  const masque = masquerJs(API_SRC)
  const idx = masque.indexOf('etats:')
  assert.notEqual(idx, -1, "clé `etats:` introuvable dans comptaApi.js")
  const { debut, fin } = bornesCorpsObjet(masque, idx)
  return new Set(clesPremierNiveau(masque, debut, fin))
}

test('sanité du masquage : une virgule DANS un commentaire ne casse plus le découpage', () => {
  // Piège mesuré : le tout premier commentaire du bloc `etats` (« PACT18 —
  // SOULIGNÉ, pas tiret ») porte une virgule AVANT `grandLivre:` lui-même —
  // sans masquage, ce test échoue en pratique (grandLivre disparaît).
  const cles = clesEtats()
  assert.ok(cles.has('grandLivre'), 'grandLivre absent — le masquage a régressé')
  assert.ok(cles.has('exportSimplIs'),
    'exportSimplIs absent — virgule de commentaire WIR180 non masquée')
})

test('EtatsComptablesViewSet : chaque @action GET a un wrapper comptaApi.etats (ou est API-only)', () => {
  const classeSrc = extraireClasse(VIEWS_SRC, 'EtatsComptablesViewSet')
  const actions = actionsGetDetailFalse(classeSrc)
  assert.ok(actions.length >= 30, `attendu au moins 30 @action GET, trouvé ${actions.length}`)

  const cles = clesEtats()
  const manquantes = actions
    .filter((nom) => !API_ONLY.has(nom))
    .map((nom) => [nom, versCamel(nom)])
    .filter(([, camel]) => !cles.has(camel))

  assert.deepEqual(manquantes, [],
    '@action GET sans wrapper comptaApi.etats (WIR254 — patron WIR107, '
    + 'ajouter le wrapper OU le déclarer API_ONLY) : '
    + manquantes.map(([nom, camel]) => `${nom} (attendu etats.${camel})`).join(', '))
})

test('WIR254 — les 16 états jusqu’ici orphelins ont bien rejoint comptaApi.etats', () => {
  const cles = clesEtats()
  const attendues = [
    'balanceReferentiel', 'balanceAnalytique', 'resultatAnalytique',
    'executionBudgetaire', 'analyseVariation', 'anomaliesEcritures',
    'cockpitCloture', 'pretACloturer', 'rapprochementsEnRetard',
    'registreImmobilisations', 'projectionDotations', 'positionsContratRevenu',
    'fraisBancaires', 'provisions', 'rapprochementClients',
    'rapprochementFournisseurs',
  ]
  for (const cle of attendues) {
    assert.ok(cles.has(cle), `comptaApi.etats.${cle} manquant`)
  }
})
