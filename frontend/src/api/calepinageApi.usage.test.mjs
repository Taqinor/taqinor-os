import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, sep } from 'node:path'

/* ============================================================================
   CALX382 — aucune clé de `calepinageApi.js` ne reste jamais appelée.
   ----------------------------------------------------------------------------
   Le test jumeau `calepinageApi.test.mjs` relit chaque CHEMIN à sa source
   (échantillons de contrat puis `urls.py`) mais ne regarde jamais si une CLÉ
   DE MÉTHODE est appelée quelque part — une porte ouverte que personne ne
   franchit y reste verte. Ce fichier ferme ce trou : zéro dépendance
   (`node:test` + `node:fs`), aucun réseau, aucun graphe ESM (le module
   `./axios` porte des effets de bord que ce test n'a aucune raison de
   déclencher — même principe que le test jumeau).

   MESURE DU JOUR (23/09/2026, CALX382) : la tâche PLAN2 citait 4 clés sans
   appelant sur 28 constatées à l'écriture du lot ; le fichier a grandi depuis
   (lots M1-M4 en parallèle) — mesuré à l'exécution : 70 clés, 5 sans appelant.
   La liste ci-dessous est celle du jour, pas celle du lot : elle ne peut que
   RÉTRÉCIR (voir la garde « exception périmée » en fin de fichier).
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))
const API_PATH = join(here, 'calepinageApi.js')
const FRONT_SRC = dirname(here) // frontend/src

// Les commentaires du client ET des écrans CITENT des chemins/noms de clés
// pour expliquer une décision (ex. « sorties() ci-dessus ») : ils ne doivent
// jamais être lus comme un appel réel. Même dépouillement que le test jumeau.
function sansCommentaires(texte) {
  return texte.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

/* ── 1. Extraction des clés de méthode de `calepinageApi.js` ────────────────
   Le fichier est un objet à DEUX niveaux : `{ calepinages: {...}, moteur:
   {...}, parametres: {...} }`. Une « clé » est une propriété de FEUILLE dont
   la valeur est une fonction (fléchée, éventuellement `async`) — les
   namespaces eux-mêmes (`calepinages: {`) ne sont pas des clés. Le nom de
   feuille N'EST PAS unique entre espaces (`resultat` existe à la fois sous
   `calepinages` ET sous `moteur`) : chaque clé est donc identifiée par
   `namespace.cle`, jamais par le seul nom court. Analyse par comptage de
   profondeur d'accolades, ligne par ligne — le même degré de rusticité que
   les autres contrats de source du dépôt (`e2eHooks.test.mjs`,
   `calepinageApi.test.mjs`) : suffisant pour UN fichier au format connu et
   stable, jamais un vrai parseur JS. */
const RE_OUVERTURE_NAMESPACE = /^\s*([A-Za-z_$][\w$]*)\s*:\s*\{\s*$/
const RE_CLE_FONCTION = /^\s*([A-Za-z_$][\w$]*)\s*:\s*(async\s*)?\(/

export function extraireCles(code) {
  const lignes = code.split('\n')
  let profondeur = 0
  let dansObjetRacine = false
  let namespaceCourant = null
  let profondeurNamespace = null
  const cles = []

  for (const ligne of lignes) {
    if (!dansObjetRacine) {
      if (/const\s+calepinageApi\s*=\s*\{/.test(ligne)) {
        dansObjetRacine = true
        profondeur = 1
      }
      continue
    }
    const mNamespace = RE_OUVERTURE_NAMESPACE.exec(ligne)
    if (mNamespace && profondeur === 1) {
      namespaceCourant = mNamespace[1]
      profondeurNamespace = profondeur + 1
    } else if (namespaceCourant && profondeur === profondeurNamespace) {
      const mCle = RE_CLE_FONCTION.exec(ligne)
      if (mCle) cles.push({ namespace: namespaceCourant, cle: mCle[1] })
    }
    for (const car of ligne) {
      if (car === '{') profondeur += 1
      if (car === '}') {
        profondeur -= 1
        if (namespaceCourant && profondeur < profondeurNamespace) namespaceCourant = null
      }
    }
  }
  return cles
}

/* ── 2. Un appelant existe-t-il, quelque part dans `frontend/src` ? ─────────
   Le motif tolère le CHAÎNAGE multi-ligne (`calepinageApi.calepinages\n
   .enregistrerRaccordement(...)`, mesuré dans `Raccordement.jsx`),
   l'ENCHAÎNEMENT OPTIONNEL (`calepinageApi.parametres?.suggererPentesIGN?.()`,
   mesuré dans `SaisiePente.jsx`), et la RÉFÉRENCE SANS APPEL IMMÉDIAT
   (`calepinageApi.calepinages.demarquerModele` affecté à une variable puis
   invoqué plus loin, mesuré dans `FicheCalepinage.jsx`) — un regex ancré sur
   `.namespace.cle(` en un seul bloc de texte a produit 3 faux positifs
   vérifiés sur ces trois écrans avant ce correctif ; une garde qui « crie au
   loup » se fait désactiver dans la semaine (voir l'en-tête de
   `check_services_appeles.py`). Il n'exige PAS de parenthèse d'appel :
   mentionner la clé suffit, sous-détection délibérée plutôt que
   sur-détection. */
export function estAppelee(namespace, cle, texte) {
  const motif = new RegExp(`\\b${namespace}\\s*\\??\\.\\s*${cle}\\b`)
  return motif.test(texte)
}

/* ── 3. Le verdict — pure, testable sans toucher le disque ───────────────── */
export function verifier(cles, texteAppelants, exceptions) {
  const nouvellesSansAppelant = []
  const exceptionsPerimees = []
  for (const { namespace, cle } of cles) {
    const id = `${namespace}.${cle}`
    const appelee = estAppelee(namespace, cle, texteAppelants)
    if (Object.prototype.hasOwnProperty.call(exceptions, id)) {
      if (appelee) exceptionsPerimees.push(id)
    } else if (!appelee) {
      nouvellesSansAppelant.push(id)
    }
  }
  return { nouvellesSansAppelant, exceptionsPerimees }
}

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) walk(full, out)
    else if (/\.(jsx?|mjs)$/.test(entry)) out.push(full)
  }
  return out
}

function texteAppelantsReel() {
  let tout = ''
  for (const fichier of walk(FRONT_SRC)) {
    if (fichier === API_PATH) continue
    const nom = fichier.split(sep).pop()
    if (/\.test\.|\.spec\./.test(nom)) continue
    tout += sansCommentaires(readFileSync(fichier, 'utf8')) + '\n'
  }
  return tout
}

/* ── 4. Le passif figé — DATÉ, UNE raison par clé, NE PEUT QUE RÉTRÉCIR. ────
   Mesuré le 23/09/2026 (CALX382). Chaque entrée sort de cette liste quand un
   écran l'appelle enfin, ou quand la méthode morte est supprimée du client —
   jamais en élargissant la garde. */
export const EXCEPTIONS_SANS_APPELANT = {
  'calepinages.sorties': "23/09/2026 — inventaire remplacé par documents() (CALX320, PanneauDocuments.jsx) ; sorties/ reste servi pour compat mais aucun écran ne le lit plus directement",
  'calepinages.telechargerSortie': '23/09/2026 — même remplacement que sorties() ci-dessus : PanneauDocuments.jsx télécharge désormais via telechargerDocument()',
  'calepinages.composerPackTechnique': "23/09/2026 — la porte HTTP existe (CALX24) mais aucun écran ne compose encore le dossier technique depuis l'atelier",
  'calepinages.variantes': "23/09/2026 — la liste des variantes se lit via le comparatif comparer() ; l'endpoint brut n'a plus de consommateur direct",
  'calepinages.releve': "23/09/2026 — le relevé se lit désormais via l'historique servi par enregistrerReleve()/PanneauReleve.jsx ; la lecture seule releve() n'a plus d'appelant direct",
}

/* ============================================================================
   Tests SYNTHÉTIQUES — la garde elle-même, sur des entrées fabriquées.
   ========================================================================== */

test("CALX382 — une clé neuve sans appelant est detectee, en la NOMMANT", () => {
  const cles = [{ namespace: 'x', cle: 'sansAppelant' }]
  const { nouvellesSansAppelant } = verifier(cles, '', {})
  assert.deepEqual(nouvellesSansAppelant, ['x.sansAppelant'])
})

test('CALX382 — la MÊME clé, appelée depuis un faux composant, ne rougit pas', () => {
  const cles = [{ namespace: 'x', cle: 'appelee' }]
  const fauxComposant = "export function Ecran() {\n  return api.x.appelee()\n}\n"
  const { nouvellesSansAppelant } = verifier(cles, fauxComposant, {})
  assert.deepEqual(nouvellesSansAppelant, [])
})

test('CALX382 — le chainage multi-ligne et le chainage optionnel comptent comme un appel', () => {
  const cles = [
    { namespace: 'calepinages', cle: 'enregistrerRaccordement' },
    { namespace: 'parametres', cle: 'suggererPentesIGN' },
  ]
  const texte = 'api.calepinages\n  .enregistrerRaccordement(id)\n'
    + 'api.parametres?.suggererPentesIGN?.(layout)\n'
  const { nouvellesSansAppelant } = verifier(cles, texte, {})
  assert.deepEqual(nouvellesSansAppelant, [])
})

test("CALX382 — une exception PÉRIMÉE (la clé a désormais un appelant) rougit en NOMMANT la clé a retirer", () => {
  const cles = [{ namespace: 'x', cle: 'redevenueAppelee' }]
  const exceptions = { 'x.redevenueAppelee': 'ancienne raison, 01/01/2026' }
  const texte = 'api.x.redevenueAppelee()\n'
  const { exceptionsPerimees } = verifier(cles, texte, exceptions)
  assert.deepEqual(exceptionsPerimees, ['x.redevenueAppelee'])
})

test('CALX382 — une exception encore valide (aucun appelant) ne rougit pas', () => {
  const cles = [{ namespace: 'x', cle: 'toujoursSansAppelant' }]
  const exceptions = { 'x.toujoursSansAppelant': 'raison, 23/09/2026' }
  const { nouvellesSansAppelant, exceptionsPerimees } = verifier(cles, '', exceptions)
  assert.deepEqual(nouvellesSansAppelant, [])
  assert.deepEqual(exceptionsPerimees, [])
})

test("CALX382 — extraireCles distingue deux clés HOMONYMES de namespaces differents", () => {
  const code = [
    'const calepinageApi = {',
    '  calepinages: {',
    '    resultat: (id) => api.get(`${pivot(id)}resultat/`),',
    '  },',
    '  moteur: {',
    '    resultat: (jobId) => api.get(`/calepinage/moteur/resultat/${jobId}/`),',
    '  },',
    '}',
  ].join('\n')
  const cles = extraireCles(code)
  assert.deepEqual(
    cles.map((c) => `${c.namespace}.${c.cle}`).sort(),
    ['calepinages.resultat', 'moteur.resultat'],
  )
})

test('CALX382 — un namespace ne fuit pas sur le namespace suivant', () => {
  const code = [
    'const calepinageApi = {',
    '  calepinages: {',
    '    layout: (id) => api.get(`${pivot(id)}layout/`),',
    '  },',
    '  moteur: {',
    '    calculer: (corps) => api.post("/calepinage/moteur/calculer/", corps),',
    '  },',
    '}',
  ].join('\n')
  const cles = extraireCles(code)
  assert.deepEqual(
    cles.map((c) => `${c.namespace}.${c.cle}`).sort(),
    ['calepinages.layout', 'moteur.calculer'],
  )
})

/* ============================================================================
   La GARDE réelle — sur le vrai `calepinageApi.js` et le vrai `frontend/src`.
   ========================================================================== */

test('GARDE — aucune clé de calepinageApi.js hors de EXCEPTIONS_SANS_APPELANT ne reste sans appelant', () => {
  const codeApi = sansCommentaires(readFileSync(API_PATH, 'utf8'))
  const cles = extraireCles(codeApi)
  assert.ok(cles.length > 0, 'aucune clé extraite — le format de calepinageApi.js a-t-il changé ?')

  const texte = texteAppelantsReel()
  const { nouvellesSansAppelant } = verifier(cles, texte, EXCEPTIONS_SANS_APPELANT)
  assert.deepEqual(
    nouvellesSansAppelant, [],
    'clé(s) neuve(s) sans appelant (hors EXCEPTIONS_SANS_APPELANT) : '
    + `${nouvellesSansAppelant.join(', ')} — branchez-la(les) sur un écran ou `
    + 'ajoutez une entrée datée et motivée dans EXCEPTIONS_SANS_APPELANT.',
  )
})

test('GARDE — EXCEPTIONS_SANS_APPELANT ne peut que RÉTRÉCIR (aucune entrée périmée)', () => {
  const codeApi = sansCommentaires(readFileSync(API_PATH, 'utf8'))
  const cles = extraireCles(codeApi)
  const texte = texteAppelantsReel()
  const { exceptionsPerimees } = verifier(cles, texte, EXCEPTIONS_SANS_APPELANT)
  assert.deepEqual(
    exceptionsPerimees, [],
    `clé(s) désormais appelée(s) — retirer de EXCEPTIONS_SANS_APPELANT : ${exceptionsPerimees.join(', ')}`,
  )
})

test('GARDE — toute clé de EXCEPTIONS_SANS_APPELANT existe encore dans calepinageApi.js', () => {
  const codeApi = sansCommentaires(readFileSync(API_PATH, 'utf8'))
  const cles = new Set(extraireCles(codeApi).map((c) => `${c.namespace}.${c.cle}`))
  const fantomes = Object.keys(EXCEPTIONS_SANS_APPELANT).filter((id) => !cles.has(id))
  assert.deepEqual(
    fantomes, [],
    `exception(s) référençant une clé disparue — retirer de EXCEPTIONS_SANS_APPELANT : ${fantomes.join(', ')}`,
  )
})

test('GARDE — chaque raison de EXCEPTIONS_SANS_APPELANT est datée et non vide', () => {
  for (const [id, raison] of Object.entries(EXCEPTIONS_SANS_APPELANT)) {
    assert.ok(raison && raison.length > 10, `${id} : raison vide ou trop courte`)
    assert.match(raison, /\d{2}\/\d{2}\/\d{4}/, `${id} : raison non datée (jj/mm/aaaa)`)
  }
})
