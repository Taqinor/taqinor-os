import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* ACAL893 — le défaut de la société (allée technique, allées de circulation) s'écrit depuis les Réglages,
   avec confirmation, par la MÊME écriture qu'avant (`parametres.update({ degagements })`). */
const getParametres = vi.fn()
const updateParametres = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { parametres: { get: (...a) => getParametres(...a), update: (...a) => updateParametres(...a) } },
}))
const peutGerer = vi.hoisted(() => ({ valeur: true }))
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => peutGerer.valeur }))

const { default: ReglagesAllees } = await import('./ReglagesAllees')

beforeEach(() => { vi.clearAllMocks(); peutGerer.valeur = true })
afterEach(() => { cleanup() })

describe('ACAL893 — Réglages › Allées', () => {
  it('le défaut s’écrit depuis les Réglages avec confirmation, le reste de la section est préservé', async () => {
    getParametres.mockResolvedValue({ data: { degagements: { retrait_rive_m: 0.5, source: 'devis technique' } } })
    updateParametres.mockResolvedValue({ data: { degagements: {} } })
    render(<ReglagesAllees />)
    await waitFor(() => expect(getParametres).toHaveBeenCalled())

    fireEvent.change(document.getElementById('cal-allees-largeur'), { target: { value: '1.2' } })
    fireEvent.click(screen.getByTestId('cal-allees-circulation-ajouter'))
    for (const [cle, v] of [['pays', 'MA'], ['largeur_m', '1.2'], ['source', 'Arrêté (essai)'], ['reference', 'art. 3']]) {
      fireEvent.change(document.getElementById(`cal-allees-circulation-0-${cle}`), { target: { value: v } })
    }
    expect(screen.getByTestId('cal-allees-enregistrer')).toBeDisabled() // pas de confirmation, pas d'écriture
    fireEvent.click(screen.getByTestId('cal-allees-confirmer-societe'))
    fireEvent.click(screen.getByTestId('cal-allees-enregistrer'))

    await waitFor(() => expect(updateParametres).toHaveBeenCalledTimes(1))
    const [corps] = updateParametres.mock.calls[0]
    expect(corps.degagements.allee_technique_m).toBe(1.2)
    expect(corps.degagements.allees_circulation).toEqual([
      { pays: 'ma', largeur_m: 1.2, source: 'Arrêté (essai)', reference: 'art. 3' },
    ])
    expect(corps.degagements.retrait_rive_m).toBe(0.5)
    expect(corps.degagements.source).toBe('devis technique')
    expect(await screen.findByTestId('cal-allees-message')).toHaveTextContent('tous vos calepinages')
  })

  it('un nombre illisible n’est pas écrit et le champ fautif est nommé', async () => {
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    render(<ReglagesAllees />)
    await waitFor(() => expect(getParametres).toHaveBeenCalled())
    fireEvent.change(document.getElementById('cal-allees-largeur'), { target: { value: '' } })
    fireEvent.click(screen.getByTestId('cal-allees-confirmer-societe'))
    fireEvent.click(screen.getByTestId('cal-allees-enregistrer'))
    await waitFor(() => expect(updateParametres).toHaveBeenCalledTimes(1)) // vide ⇒ clé retirée, c'est permis
    expect(updateParametres.mock.calls[0][0].degagements.allee_technique_m).toBeUndefined()
  })

  it('sans le droit de gérer, le bouton d’écriture reste éteint', async () => {
    peutGerer.valeur = false
    getParametres.mockResolvedValue({ data: { degagements: {} } })
    render(<ReglagesAllees />)
    await waitFor(() => expect(getParametres).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-allees-confirmer-societe'))
    expect(screen.getByTestId('cal-allees-enregistrer')).toBeDisabled()
  })
})
