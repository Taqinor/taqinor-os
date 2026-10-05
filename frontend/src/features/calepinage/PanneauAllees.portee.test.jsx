import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ACAL258 — DEUX PORTÉES : l'allée « gratuite » du moteur est un paramètre de CE calepinage
   (le DOCUMENT), le défaut société se règle à part, nommé et confirmé.
   Les réponses suivent les contrats committés (`moteur_calculer.json`,
   `parametres_calepinage.json`), jamais un objet tapé à la main.
   ========================================================================== */

const RESULTAT = exempleContrat('calepinage', 'moteur_calculer')
const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')

const getParametres = vi.fn()
const updateParametres = vi.fn()
const calculer = vi.fn()
const enregistrerLayout = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: {
    parametres: { get: (...a) => getParametres(...a), update: (...a) => updateParametres(...a) },
    moteur: { calculer: (...a) => calculer(...a) },
    calepinages: { enregistrerLayoutCalepinage: (...a) => enregistrerLayout(...a) },
  },
}))

const { default: PanneauAllees } = await import('./PanneauAllees')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const ENTREE = { surfaces: [{ id: 'PAN-A' }] }
const ALLEE = RESULTAT.suggestions.find((s) => s.code === 'ALLEE_GRATUITE').action.patch.allee_m

function builder() {
  const document = {}
  return {
    document,
    appliquerSection: vi.fn((cle, valeur) => { document[cle] = valeur }),
    serializeLayout: vi.fn(() => ({ version: 2, ...document })),
  }
}

async function suggerer(props) {
  getParametres.mockResolvedValue({ data: REGLAGES })
  calculer.mockResolvedValue({ data: RESULTAT })
  render(<PanneauAllees entree={ENTREE} calepinageId={9} {...props} />)
  await screen.findByTestId('cal-panneau-allees')
  fireEvent.click(screen.getByTestId('cal-allees-rechercher'))
  await screen.findByTestId('cal-allees-suggestion')
  fireEvent.click(screen.getByTestId('cal-allees-appliquer-suggestion'))
}

describe('ACAL258 — la suggestion s’enregistre dans le document, pas dans la société', () => {
  it('la suggestion s’enregistre dans le document, pas dans la société', async () => {
    const b = builder()
    enregistrerLayout.mockResolvedValue({ data: { inchange: false, version: 3 } })
    await suggerer({ builderApi: b })

    fireEvent.click(screen.getByTestId('cal-allees-enregistrer-calepinage'))

    await waitFor(() => expect(enregistrerLayout).toHaveBeenCalledTimes(1))
    // Le corps POSTÉ porte l'allée de CE calepinage, avec sa source…
    const [id, corps] = enregistrerLayout.mock.calls[0]
    expect(id).toBe(9)
    expect(corps.alleeTechnique).toEqual({ largeurM: ALLEE, source: 'suggestion_moteur' })
    // …et la société n'est JAMAIS écrite.
    expect(updateParametres).not.toHaveBeenCalled()
    expect(await screen.findByTestId('cal-allees-message-calepinage'))
      .toHaveTextContent('pour ce calepinage')
    expect(screen.queryByTestId('cal-allees-message')).toBeNull()
  })

  it('une allée tapée à la main porte la source « saisie »', async () => {
    const b = builder()
    enregistrerLayout.mockResolvedValue({ data: {} })
    await suggerer({ builderApi: b })

    fireEvent.change(document.getElementById('cal-allees-largeur-calepinage'), { target: { value: '0.9' } })
    fireEvent.click(screen.getByTestId('cal-allees-enregistrer-calepinage'))

    await waitFor(() => expect(b.appliquerSection).toHaveBeenCalledWith('alleeTechnique', { largeurM: 0.9, source: 'saisie' }))
  })

  it('un refus 409 du serveur s’affiche, mot pour mot', async () => {
    const b = builder()
    enregistrerLayout.mockRejectedValue({ response: { status: 409, data: { roof_layout: ['Le devis lié est accepté.'] } } })
    await suggerer({ builderApi: b })

    fireEvent.click(screen.getByTestId('cal-allees-enregistrer-calepinage'))

    expect(await screen.findByTestId('cal-allees-message-calepinage')).toHaveTextContent('Le devis lié est accepté.')
  })

  it('sans atelier prêt, le DIT et n’écrit rien', async () => {
    await suggerer({ builderApi: null })

    fireEvent.click(screen.getByTestId('cal-allees-enregistrer-calepinage'))

    expect(await screen.findByTestId('cal-allees-message-calepinage')).toHaveTextContent('pas prêt')
    expect(enregistrerLayout).not.toHaveBeenCalled()
    expect(updateParametres).not.toHaveBeenCalled()
  })
})

describe('ACAL258 — le défaut de la société, nommé et confirmé', () => {
  it('édite les allées de circulation et préserve le reste de la section, après confirmation', async () => {
    getParametres.mockResolvedValue({ data: { degagements: { retrait_rive_m: 0.5, source: 'devis technique' } } })
    updateParametres.mockResolvedValue({ data: { degagements: {} } })
    render(<PanneauAllees entree={ENTREE} calepinageId={9} builderApi={builder()} />)
    await screen.findByTestId('cal-panneau-allees')

    fireEvent.click(screen.getByTestId('cal-allees-circulation-ajouter'))
    for (const [cle, v] of [['pays', 'MA'], ['largeur_m', '1.2'], ['source', 'Arrêté (essai)'], ['reference', 'art. 3']]) {
      fireEvent.change(document.getElementById(`cal-allees-circulation-0-${cle}`), { target: { value: v } })
    }
    expect(screen.getByTestId('cal-allees-enregistrer')).toBeDisabled()
    fireEvent.click(screen.getByTestId('cal-allees-confirmer-societe'))
    fireEvent.click(screen.getByTestId('cal-allees-enregistrer'))

    await waitFor(() => expect(updateParametres).toHaveBeenCalledTimes(1))
    const [corps] = updateParametres.mock.calls[0]
    expect(corps.degagements.allees_circulation).toEqual([
      { pays: 'ma', largeur_m: 1.2, source: 'Arrêté (essai)', reference: 'art. 3' },
    ])
    expect(corps.degagements.retrait_rive_m).toBe(0.5)
    expect(await screen.findByTestId('cal-allees-message')).toHaveTextContent('tous vos calepinages')
    expect(enregistrerLayout).not.toHaveBeenCalled()
  })
})
