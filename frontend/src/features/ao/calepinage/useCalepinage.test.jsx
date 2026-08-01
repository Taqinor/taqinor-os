import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

const mocks = vi.hoisted(() => ({ get: vi.fn(), calculer: vi.fn() }))
vi.mock('../../../api/aoApi', () => ({
  default: { calepinages: { get: mocks.get, calculer: mocks.calculer } },
}))

import useCalepinage from './useCalepinage'

const charge = (texte, parametres) => ({
  data: {
    plan: { cadre: { x_min: 0, y_min: 0, largeur_m: 10, hauteur_m: 10 }, rangees: [] },
    resultat: { modules: { valeur: 1, texte }, verdict: { code: 'confirme', libelle: 'CONFIRMÉ' } },
    parametres,
  },
})

const P0 = { allee_m: 0.6 }
const P1 = { allee_m: 1.9 }
const P2 = { allee_m: 1.94 }

const monter = (initial = P0) => renderHook(
  ({ p }) => useCalepinage(7, p, { delai: 0 }),
  { initialProps: { p: initial } },
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue(charge('314 modules', P0))
  mocks.calculer.mockResolvedValue(charge('318 modules', P1))
})

describe('useCalepinage (AOF94) — cycle paramètre → recalcul serveur → résultat', () => {
  it('charge le calepinage existant, puis recalcule côté SERVEUR à chaque changement', async () => {
    const { result, rerender } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    expect(mocks.get).toHaveBeenCalledWith(7)
    expect(result.current.perime).toBe(false)

    rerender({ p: P1 })
    await waitFor(() => expect(mocks.calculer).toHaveBeenCalledWith(7, P1))
    await waitFor(() => expect(result.current.resultat.modules.texte).toBe('318 modules'))
  })

  it('PÉRIMÉ dès la frappe : le chiffre affiché n\'est jamais présenté comme courant', async () => {
    const { result, rerender } = monter()
    await waitFor(() => expect(result.current.perime).toBe(false))

    rerender({ p: P1 })
    // Sans attendre quoi que ce soit : l'ancien chiffre est DÉJÀ marqué périmé.
    expect(result.current.perime).toBe(true)
    expect(result.current.resultat.modules.texte).toBe('314 modules')

    await waitFor(() => expect(result.current.perime).toBe(false))
    expect(result.current.resultat.modules.texte).toBe('318 modules')
  })

  it('ne recalcule pas quand les paramètres reviennent à leur valeur affichée', async () => {
    const { result, rerender } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    rerender({ p: { allee_m: 0.6 } }) // objet neuf, MÊME valeur
    await waitFor(() => expect(result.current.perime).toBe(false))
    expect(mocks.calculer).not.toHaveBeenCalled()
  })

  it('une réponse DOUBLÉE en vol est ignorée — aucun chiffre fantôme', async () => {
    let resoudre1
    mocks.calculer
      .mockImplementationOnce(() => new Promise((resolve) => { resoudre1 = resolve }))
      .mockImplementationOnce(() => Promise.resolve(charge('322 modules', P2)))

    const { result, rerender } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())

    rerender({ p: P1 })                                    // requête 1 (en vol)
    await waitFor(() => expect(mocks.calculer).toHaveBeenCalledTimes(1))
    rerender({ p: P2 })                                    // requête 2 la double
    await waitFor(() => expect(mocks.calculer).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(result.current.resultat.modules.texte).toBe('322 modules'))

    // La réponse de la requête 1 arrive APRÈS : elle doit être jetée.
    resoudre1(charge('999 modules', P1))
    await new Promise((resolve) => { setTimeout(resolve, 0) })
    expect(result.current.resultat.modules.texte).toBe('322 modules')
    expect(result.current.perime).toBe(false)
  })

  it('une réponse qui arrive après le démontage ne provoque aucune mise à jour', async () => {
    let resoudre
    mocks.get.mockImplementationOnce(() => new Promise((resolve) => { resoudre = resolve }))
    const { result, unmount } = monter()
    unmount()
    resoudre(charge('314 modules', P0))
    await new Promise((resolve) => { setTimeout(resolve, 0) })
    expect(result.current.resultat).toBeNull()
  })

  it('une erreur de recalcul est signalée SANS inventer de résultat', async () => {
    mocks.calculer.mockRejectedValueOnce({ response: { data: { detail: 'Orientation refusée.' } } })
    const { result, rerender } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    rerender({ p: P1 })
    await waitFor(() => expect(result.current.erreur).toBe('Orientation refusée.'))
    // Le résultat périmé reste visible… mais reste marqué périmé.
    expect(result.current.resultat.modules.texte).toBe('314 modules')
    expect(result.current.perime).toBe(true)
  })

  it('appliquer() rejoue le patch CÔTÉ SERVEUR (jamais un gain estimé côté front)', async () => {
    const { result } = monter()
    await waitFor(() => expect(result.current.resultat).toBeTruthy())
    await result.current.appliquer({ rive_est_m: 0.5 })
    expect(mocks.calculer).toHaveBeenCalledWith(7, { allee_m: 0.6, patch_entree: { rive_est_m: 0.5 } })
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
