import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'
import resultatReel from './resultatReel.fixture'

/* ============================================================================
   AOF94 — `useCalepinage`, recâblé sur les ROUTES RÉELLES (03/08/2026).
   ----------------------------------------------------------------------------
   Ces tests mockent le CLIENT AXIOS, pas `aoApi` : c'est le seul niveau où
   l'URL RÉELLEMENT appelée est observable. Le bug qu'on répare était
   précisément une URL — `/ao/calepinages/<id>/` — que le serveur n'a jamais
   servie ; un mock de `aoApi` l'aurait laissée passer.

   Les charges utiles viennent de `resultatReel.fixture.js`, capturé en
   exécutant le moteur du dépôt (voir l'en-tête de la fixture) — jamais écrit
   à la main.
   ========================================================================== */

const axiosMock = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
}))
vi.mock('../../../api/axios', () => ({ default: axiosMock }))

import useCalepinage from './useCalepinage'

const CALCULER = '/ao/calepinage/calculer/'
const LANCER = '/ao/calepinage/lancer/'
const RESULTAT = '/ao/calepinage/resultat/42/'

// Réponse 200 de `CalculerCalepinageView` : le résultat + `depuis_cache`.
const ok = (surcharge = {}) => ({
  status: 200,
  data: { ...resultatReel, depuis_cache: false, ...surcharge },
})

// Réponse 202 : le travail dépasse le budget synchrone (corps littéral de
// `CalculerCalepinageView.post`).
const horsBudget = () => ({
  status: 202,
  data: {
    detail: 'Ce calepinage dépasse le budget de calcul synchrone : lancez-le en '
      + 'tâche de fond via /api/django/ao/calepinage/lancer/, puis suivez-le sur '
      + '/api/django/ao/calepinage/resultat/<job_id>/.',
    cout_estime: { positions: 1200, kits: 1, appels: 1200, millisecondes: 4200.0, motif: 'positions' },
    asynchrone: '/api/django/ao/calepinage/lancer/',
  },
})

// Réponse 202 de `LancerCalepinageView` puis 200 de `ResultatCalepinageView`
// (corps littéraux de ces deux vues ; statuts de `core.models.BackgroundJob`).
const jobLance = () => ({
  status: 202,
  data: { id: 42, kind: 'ao_calepinage', statut: 'queued', progress_pct: 0, message_erreur: '', resultat: null, variante: null },
})
const jobSuivi = (statut, pct, extra = {}) => ({
  status: 200,
  data: { id: 42, kind: 'ao_calepinage', statut, progress_pct: pct, message_erreur: '', resultat: null, variante: null, ...extra },
})

const P0 = { allee_min_m: 0.6 }
const P1 = { allee_min_m: 1.9 }
const P2 = { allee_min_m: 1.94 }

const monter = (initial = null, options = {}) => renderHook(
  ({ p }) => useCalepinage(7, p, { delai: 0, sondage: 0, ...options }),
  { initialProps: { p: initial } },
)

beforeEach(() => {
  vi.clearAllMocks()
  axiosMock.post.mockResolvedValue(ok())
  axiosMock.get.mockResolvedValue(jobSuivi('done', 100))
})

describe('useCalepinage — les ROUTES réellement appelées', () => {
  it("appelle /ao/calepinage/calculer/ et JAMAIS /ao/calepinages/…", async () => {
    const { result } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())

    expect(axiosMock.post).toHaveBeenCalledWith(CALCULER, { toiture: 7 })
    const urls = [...axiosMock.post.mock.calls, ...axiosMock.get.mock.calls].map(([url]) => url)
    expect(urls.some((url) => url.includes('/ao/calepinages'))).toBe(false)
  })

  it("n'envoie JAMAIS `company` (le serveur la résout depuis l'utilisateur)", async () => {
    const { result } = monter(P0)
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    for (const [, corps] of axiosMock.post.mock.calls) {
      expect(JSON.stringify(corps ?? {})).not.toContain('company')
    }
  })

  it('publie le résultat SERVEUR tel quel (aucun chiffre recomposé)', async () => {
    const { result } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    expect(result.current.resultat.total_modules).toBe(resultatReel.total_modules)
    expect(result.current.resultat.kwc).toBe(resultatReel.kwc)
    expect(result.current.resultat.preuve.libelle).toBe(resultatReel.preuve.libelle)
    expect(result.current.perime).toBe(false)
  })

  it('envoie `params` dès qu’un tiroir pilote des paramètres', async () => {
    const { result, rerender } = monter(P0)
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    expect(axiosMock.post).toHaveBeenCalledWith(CALCULER, { toiture: 7, params: P0 })

    rerender({ p: P1 })
    await waitFor(() => expect(axiosMock.post).toHaveBeenCalledWith(CALCULER, { toiture: 7, params: P1 }))
  })
})

describe('useCalepinage — le 202 est une CONSIGNE, pas une erreur', () => {
  it('bascule sur lancer + resultat/<job>/ et publie la progression du JOB', async () => {
    axiosMock.post
      .mockResolvedValueOnce(horsBudget())
      .mockResolvedValueOnce(jobLance())
    axiosMock.get
      .mockResolvedValueOnce(jobSuivi('running', 25))
      .mockResolvedValueOnce(jobSuivi('done', 100, { resultat: { ...resultatReel } }))

    const { result } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())

    expect(axiosMock.post).toHaveBeenNthCalledWith(1, CALCULER, { toiture: 7 })
    expect(axiosMock.post).toHaveBeenNthCalledWith(2, LANCER, { toiture: 7 })
    expect(axiosMock.get).toHaveBeenCalledWith(RESULTAT)
    expect(result.current.resultat.total_modules).toBe(resultatReel.total_modules)
    expect(result.current.erreur).toBeNull()
  })

  it("un job en ÉCHEC affiche le motif du serveur, jamais un écran blanc", async () => {
    axiosMock.post
      .mockResolvedValueOnce(horsBudget())
      .mockResolvedValueOnce(jobLance())
    axiosMock.get.mockResolvedValueOnce(
      jobSuivi('failed', 40, { message_erreur: "L'enveloppe de la toiture est vide : au moins 3 sommets sont nécessaires pour calepiner." }),
    )

    const { result } = monter()
    await waitFor(() => expect(result.current.erreur).toBe(
      "L'enveloppe de la toiture est vide : au moins 3 sommets sont nécessaires pour calepiner.",
    ))
    expect(result.current.resultat).toBeNull()
  })
})

describe('useCalepinage — les erreurs serveur s’affichent TELLES QUELLES', () => {
  it('400 NOMMÉ : le champ fautif est conservé (`{entree: [...]}`)', async () => {
    axiosMock.post.mockRejectedValueOnce({
      response: { status: 400, data: { entree: ["Aucun kit de calepinage actif n'est disponible pour cette toiture : le calcul n'a rien à poser."] } },
    })
    const { result } = monter()
    await waitFor(() => expect(result.current.erreur).toBe(
      "entree : Aucun kit de calepinage actif n'est disponible pour cette toiture : le calcul n'a rien à poser.",
    ))
  })

  it('404 : le `detail` de DRF est affiché mot pour mot', async () => {
    axiosMock.post.mockRejectedValueOnce({
      response: { status: 404, data: { detail: 'Toiture introuvable dans cette société.' } },
    })
    const { result } = monter()
    await waitFor(() => expect(result.current.erreur).toBe('Toiture introuvable dans cette société.'))
  })

  it("l'erreur ne détruit pas le résultat précédent, qui reste marqué PÉRIMÉ", async () => {
    const { result, rerender } = monter(P0)
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    axiosMock.post.mockRejectedValueOnce({
      response: { status: 400, data: { calepinage: ['Contrôle « rive_laterale » en échec.'], controle: 'rive_laterale', repere: '05H' } },
    })
    rerender({ p: P1 })
    await waitFor(() => expect(result.current.erreur).toContain('rive_laterale'))
    expect(result.current.resultat.total_modules).toBe(resultatReel.total_modules)
    expect(result.current.perime).toBe(true)
  })
})

describe('useCalepinage — aucun chiffre fantôme', () => {
  it('PÉRIMÉ dès la frappe : le chiffre affiché n’est jamais présenté comme courant', async () => {
    const { result, rerender } = monter(P0)
    await waitFor(() => expect(result.current.perime).toBe(false))
    rerender({ p: P1 })
    expect(result.current.perime).toBe(true)
    await waitFor(() => expect(result.current.perime).toBe(false))
  })

  it('ne recalcule pas quand les paramètres reviennent à leur valeur affichée', async () => {
    const { result, rerender } = monter(P0)
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    expect(axiosMock.post).toHaveBeenCalledTimes(1)
    rerender({ p: { allee_min_m: 0.6 } }) // objet neuf, MÊME valeur
    await waitFor(() => expect(result.current.perime).toBe(false))
    expect(axiosMock.post).toHaveBeenCalledTimes(1)
  })

  it('une réponse DOUBLÉE en vol est ignorée', async () => {
    let resoudre1
    axiosMock.post
      .mockResolvedValueOnce(ok())
      .mockImplementationOnce(() => new Promise((resolve) => { resoudre1 = resolve }))
      .mockImplementationOnce(() => Promise.resolve(ok({ total_modules: 322 })))

    const { result, rerender } = monter(P0)
    await waitFor(() => expect(result.current.resultat).toBeTruthy())

    rerender({ p: P1 })
    await waitFor(() => expect(axiosMock.post).toHaveBeenCalledTimes(2))
    rerender({ p: P2 })
    await waitFor(() => expect(axiosMock.post).toHaveBeenCalledTimes(3))
    await waitFor(() => expect(result.current.resultat.total_modules).toBe(322))

    resoudre1(ok({ total_modules: 999 }))
    await new Promise((resolve) => { setTimeout(resolve, 0) })
    expect(result.current.resultat.total_modules).toBe(322)
    expect(result.current.perime).toBe(false)
  })

  it('une réponse qui arrive après le démontage ne provoque aucune mise à jour', async () => {
    let resoudre
    axiosMock.post.mockImplementationOnce(() => new Promise((resolve) => { resoudre = resolve }))
    const { result, unmount } = monter()
    unmount()
    resoudre(ok())
    await new Promise((resolve) => { setTimeout(resolve, 0) })
    expect(result.current.resultat).toBeNull()
  })
})

/* ==========================================================================
   GARDE DE CODE — « aucun chiffre métier calculé côté front » (AOF94).
   --------------------------------------------------------------------------
   Sans elle la règle n'est qu'un vœu : le premier développeur qui veut « juste
   un aperçu réactif » ajoute un compteur local et l'écran se remet à mentir.
   La garde lit le CODE de `features/ao/**` (commentaires et chaînes retirés)
   et refuse trois formes d'arithmétique de comptage.
   ========================================================================== */

const RACINE_AO = join(dirname(fileURLToPath(import.meta.url)), '..')

// Grandeurs MÉTIER : celles qui doivent venir du moteur, jamais d'un calcul
// local. (Les grandeurs de GÉOMÉTRIE D'AFFICHAGE — viewBox, pixels, largeurs
// de colonne — n'en font pas partie : ce ne sont pas des chiffres métier.)
const GRANDEURS = [
  'nb_modules', 'nbModules', 'modules',
  'nb_tables', 'nbTables', 'tables',
  'nb_rangees', 'nbRangees', 'rangees',
  'nb_chaines', 'nbChaines', 'chaines',
  'nb_onduleurs', 'nbOnduleurs', 'onduleurs',
  'kwc', 'kWc', 'puissance_kwc',
  'marge', 'engagement', 'compte', 'comptes', 'reste',
]
const MOTIF = GRANDEURS.join('|')

// Retire commentaires, littéraux de chaîne et noms d'attributs JSX pour ne
// garder QUE du code. Les guillemets sont traités LIGNE PAR LIGNE : une
// apostrophe française isolée dans un texte JSX (« l'atelier ») ne peut alors
// avaler que sa propre ligne, jamais la suite du fichier.
function codeNu(src) {
  const sansBlocs = src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/`(?:\\.|[^`\\])*`/g, (bloc) => (bloc.match(/\$\{[^{}]*\}/g) || []).join(' '))
  return sansBlocs
    .split('\n')
    .map((ligne) => ligne
      .replace(/(^|[^:])\/\/.*$/, '$1')
      .replace(/'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"/g, '""')
      .replace(/\b(?:data|aria)-[a-z0-9-]+/g, ' '))
    .join('\n')
}

const REGLES = [
  {
    nom: 'une grandeur métier reçoit le résultat d\'un calcul local',
    re: new RegExp(`\\b(?:const|let|var)\\s+(?:${MOTIF})\\s*=[^=][^;\\n]*(?:[-+*/%]|\\.reduce\\(|\\.length)`, 'gi'),
  },
  {
    nom: 'un opérateur arithmétique porte directement sur une grandeur métier',
    re: new RegExp(`(\\b(?:${MOTIF})\\b\\s*[-+*/%]\\s*[\\w$([])|([\\w$)\\]]\\s*[-+*/%]\\s*\\b(?:${MOTIF})\\b)`, 'g'),
  },
  {
    nom: 'une grandeur métier est comptée localement (.length / .reduce)',
    re: new RegExp(`\\b(?:${MOTIF})\\b\\s*(?:\\?\\.|\\.)\\s*(?:length|reduce)\\b`, 'g'),
  },
]

function fichiersSources(dir, out = []) {
  for (const entree of readdirSync(dir)) {
    const complet = join(dir, entree)
    if (statSync(complet).isDirectory()) fichiersSources(complet, out)
    else if (/\.jsx?$/.test(entree) && !/\.test\.jsx?$/.test(entree)) out.push(complet)
  }
  return out
}

describe('garde de code AOF94 — aucun compte dérivé côté client dans features/ao/', () => {
  it('scanne réellement des fichiers (la garde ne peut pas être vide)', () => {
    expect(fichiersSources(RACINE_AO).length).toBeGreaterThan(0)
  })

  it('aucun fichier de features/ao/ ne dérive une grandeur métier', () => {
    const infractions = []
    for (const fichier of fichiersSources(RACINE_AO)) {
      const nu = codeNu(readFileSync(fichier, 'utf8'))
      for (const regle of REGLES) {
        regle.re.lastIndex = 0
        const trouve = nu.match(regle.re)
        if (trouve) infractions.push(`${relative(RACINE_AO, fichier)} → ${regle.nom} : ${trouve.join(' / ')}`)
      }
    }
    expect(infractions, [
      'Un chiffre métier (modules, kWc, marge, chaînes, onduleurs…) doit VENIR DU MOTEUR :',
      'affichez le texte renvoyé par le serveur au lieu de le recalculer ici.',
      infractions.join('\n'),
    ].join('\n')).toEqual([])
  })

  it('la garde détecte bien une infraction (test de la garde elle-même)', () => {
    const fautif = codeNu('const modules = rangees.length * 2 // aperçu local\n')
    const touchees = REGLES.filter((regle) => {
      regle.re.lastIndex = 0
      return regle.re.test(fautif)
    })
    expect(touchees.length).toBeGreaterThan(0)
  })
})
