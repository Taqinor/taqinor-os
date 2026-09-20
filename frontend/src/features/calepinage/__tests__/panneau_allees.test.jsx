import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CAL70 — « NE JAMAIS PUBLIER L'ALLÉE MINIMALE QUAND UNE ALLÉE LARGE EST
   GRATUITE » (règle produit AOF50), VÉRIFIÉE À L'ÉCRAN.
   ----------------------------------------------------------------------------
   La charge utile de la recherche vient du contrat COMMITTÉ
   `moteur_calculer.json` (PACT10) — le même exemple que `RemplissageProuve`
   affirme déjà, et qui porte EFFECTIVEMENT une suggestion `ALLEE_GRATUITE`
   dans `suggestions[]` : ce test ne l'invente pas, il la relit.
   ========================================================================== */

const RESULTAT_AVEC_PLATEAU = exempleContrat('calepinage', 'moteur_calculer')
const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')

const getParametres = vi.fn()
const updateParametres = vi.fn()
const calculer = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    parametres: {
      get: (...a) => getParametres(...a),
      update: (...a) => updateParametres(...a),
    },
    moteur: {
      calculer: (...a) => calculer(...a),
    },
  },
}))

const {
  default: PanneauAllees, suggestionAlleeGratuite,
} = await import('../PanneauAllees')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const ENTREE = { surfaces: [{ id: 'PAN-A' }] }

/* ── 1. LA LECTURE, PURE ──────────────────────────────────────────────── */

describe('CAL70 — suggestionAlleeGratuite : lit ce que le moteur a DÉJÀ publié', () => {
  it('le contrat committé porte bien une suggestion ALLEE_GRATUITE exploitable', () => {
    const suggestion = suggestionAlleeGratuite(RESULTAT_AVEC_PLATEAU)
    expect(suggestion).toBeTruthy()
    expect(suggestion.alleeM).toBe(
      RESULTAT_AVEC_PLATEAU.suggestions.find((s) => s.code === 'ALLEE_GRATUITE')
        .action.patch.allee_m)
  })

  it('sans suggestion ALLEE_GRATUITE, rend null — jamais une valeur inventée', () => {
    expect(suggestionAlleeGratuite({ suggestions: [] })).toBeNull()
    expect(suggestionAlleeGratuite({
      suggestions: [{ code: 'AUTRE_CHOSE', action: { patch: {} } }],
    })).toBeNull()
    expect(suggestionAlleeGratuite(null)).toBeNull()
    expect(suggestionAlleeGratuite({})).toBeNull()
  })

  it('une suggestion sans `allee_m` exploitable ne compte pas', () => {
    expect(suggestionAlleeGratuite({
      suggestions: [{ code: 'ALLEE_GRATUITE', action: { patch: {} } }],
    })).toBeNull()
  })
})

/* ── 2. L'ÉCRAN ────────────────────────────────────────────────────────── */

const rendre = (props = {}) => render(<PanneauAllees entree={ENTREE} {...props} />)

describe('CAL70 — l’écran lit le réglage société et le plateau du moteur', () => {
  it('sans allée réglée, le DIT au lieu d’inventer un défaut', async () => {
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    rendre()
    expect(await screen.findByTestId('cal-allees-non-reglee')).toBeInTheDocument()
    expect(screen.getByTestId('cal-allees-actuelle')).toHaveTextContent('—')
  })

  it('affiche l’allée réglée par la société, lue du contrat committé', async () => {
    getParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    const attendu = String(REGLAGES.degagements.allee_technique_m)
    expect(await screen.findByTestId('cal-allees-actuelle'))
      .toHaveTextContent(attendu)
  })

  it('cherche l’allée gratuite via la porte moteur CAL22, et affiche le plateau SANS perte', async () => {
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    calculer.mockResolvedValue({ data: RESULTAT_AVEC_PLATEAU })
    rendre()
    await screen.findByTestId('cal-panneau-allees')

    fireEvent.click(screen.getByTestId('cal-allees-rechercher'))
    expect(calculer).toHaveBeenCalledWith(ENTREE)

    const suggestion = await screen.findByTestId('cal-allees-suggestion')
    expect(suggestion).toHaveTextContent('perdre aucun module')
    const attendue = RESULTAT_AVEC_PLATEAU.suggestions
      .find((s) => s.code === 'ALLEE_GRATUITE').action.patch.allee_m
    expect(suggestion).toHaveTextContent(String(attendue))
  })

  it('sans plateau publié par le moteur, le DIT plutôt que d’afficher un vide muet', async () => {
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    calculer.mockResolvedValue({ data: { ...RESULTAT_AVEC_PLATEAU, suggestions: [] } })
    rendre()
    await screen.findByTestId('cal-panneau-allees')

    fireEvent.click(screen.getByTestId('cal-allees-rechercher'))
    expect(await screen.findByTestId('cal-allees-sans-plateau')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-allees-suggestion')).toBeNull()
  })

  it('reprendre le plateau REMPLIT le champ, sans écrire tout seul', async () => {
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    calculer.mockResolvedValue({ data: RESULTAT_AVEC_PLATEAU })
    rendre()
    await screen.findByTestId('cal-panneau-allees')
    fireEvent.click(screen.getByTestId('cal-allees-rechercher'))
    await screen.findByTestId('cal-allees-suggestion')

    fireEvent.click(screen.getByTestId('cal-allees-appliquer-suggestion'))
    const attendue = RESULTAT_AVEC_PLATEAU.suggestions
      .find((s) => s.code === 'ALLEE_GRATUITE').action.patch.allee_m
    expect(document.getElementById('cal-allees-largeur')).toHaveValue(attendue)
    // Rien n'est encore enregistré : c'est un geste EXPLICITE.
    expect(updateParametres).not.toHaveBeenCalled()
  })

  it('enregistre la section dégagements — PRÉSERVE le reste de la section', async () => {
    getParametres.mockResolvedValue({
      data: { degagements: { retrait_rive_m: 0.5, source: 'devis technique' } },
    })
    updateParametres.mockResolvedValue({ data: { degagements: {} } })
    rendre()
    await screen.findByTestId('cal-panneau-allees')

    fireEvent.change(document.getElementById('cal-allees-largeur'),
      { target: { value: '1.2' } })
    fireEvent.click(screen.getByTestId('cal-allees-enregistrer'))

    await waitFor(() => expect(updateParametres).toHaveBeenCalledTimes(1))
    const [corps] = updateParametres.mock.calls[0]
    expect(corps.degagements.allee_technique_m).toBe(1.2)
    expect(corps.degagements.retrait_rive_m).toBe(0.5)
    expect(corps.degagements.source).toBe('devis technique')
    expect(await screen.findByTestId('cal-allees-message'))
      .toHaveTextContent('enregistrée')
  })

  it('sans surface à analyser, le DIT plutôt que d’interroger le moteur', async () => {
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    render(<PanneauAllees entree={null} />)
    await screen.findByTestId('cal-panneau-allees')

    fireEvent.click(screen.getByTestId('cal-allees-rechercher'))
    expect(await screen.findByTestId('cal-allees-refus'))
      .toHaveTextContent('Aucune surface')
    expect(calculer).not.toHaveBeenCalled()
  })

  it('lecture seule : ni champ, ni bouton d’écriture', async () => {
    getParametres.mockResolvedValue({ data: REGLAGES })
    rendre({ lectureSeule: true })
    await screen.findByTestId('cal-panneau-allees')

    expect(screen.queryByTestId('cal-allees-champ')).toBeNull()
    expect(screen.queryByTestId('cal-allees-enregistrer')).toBeNull()
    expect(screen.queryByTestId('cal-allees-rechercher')).toBeNull()
  })
})
