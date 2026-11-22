import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ACAL719 — l'heure légale à côté de l'heure solaire (écart servi par `soleil-legal/`, ACAL730). */
const soleilLegal = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { soleilLegal: (...a) => soleilLegal(...a) } },
}))

const { default: HeureLegale, viderCacheHeureLegale, formaterHeureLegale } = await import('./HeureLegale')
const SERVI = exempleContrat('calepinage', 'calepinage_soleil_legal')
const SANS_FUSEAU = exempleContrat('calepinage', 'calepinage_soleil_legal', 'exemple_sans_fuseau')

beforeEach(() => {
  vi.clearAllMocks()
  viderCacheHeureLegale()
  document.body.innerHTML = ''
})
afterEach(() => { cleanup() })

function barre({ heure = '12', date = '2028-02-11' } = {}) {
  const hote = document.createElement('div')
  hote.id = 'rp9-sun-controls'
  hote.innerHTML = `<input id="rp9-sun-hour" type="range" value="${heure}" /><input id="rp9-sun-date" type="date" value="${date}" />`
  document.body.appendChild(hote)
  return { heure: hote.querySelector('#rp9-sun-hour'), date: hote.querySelector('#rp9-sun-date') }
}

const rendre = () => render(<MemoryRouter initialEntries={['/calepinage/7']}><HeureLegale /></MemoryRouter>)

describe('ACAL719 — HeureLegale', () => {
  it('curseur 12 h ⇒ 13 h 45 heure légale d’après l’échantillon, l’heure solaire toujours nommée', async () => {
    soleilLegal.mockResolvedValue({ data: SERVI })
    barre()
    rendre()
    const ligne = await screen.findByText(/13 h 45 heure légale/)
    expect(ligne.closest('#rp9-sun-legal')).toHaveTextContent('12 h solaire (13 h 45 heure légale)')
    expect(ligne.closest('#rp9-sun-legal')).toHaveTextContent('heure solaire vraie')
    expect(screen.getByText('solaire')).toHaveAttribute('title', 'heure vraie du lieu : midi = soleil au plus haut')
    expect(soleilLegal).toHaveBeenCalledWith('7', { date: `${new Date().getFullYear()}-02-11` })
  })

  it('un seul appel pour deux changements d’heure ; la ligne suit le curseur', async () => {
    soleilLegal.mockResolvedValue({ data: SERVI })
    const { heure } = barre()
    rendre()
    await screen.findByText(/13 h 45 heure légale/)
    fireEvent.input(Object.assign(heure, { value: '14' }))
    expect(await screen.findByText(/15 h 45 heure légale/)).toBeInTheDocument()
    fireEvent.input(Object.assign(heure, { value: '9' }))
    expect(await screen.findByText(/10 h 45 heure légale/)).toBeInTheDocument()
    expect(soleilLegal).toHaveBeenCalledTimes(1)
  })

  it('409 (fuseau non saisi) : le motif et le lien vers les réglages, aucune heure légale', async () => {
    soleilLegal.mockRejectedValue({ response: { status: 409, data: SANS_FUSEAU } })
    barre()
    rendre()
    const ligne = await waitFor(() => {
      const l = document.getElementById('rp9-sun-legal')
      expect(l).toHaveTextContent('heure légale non calculée : fuseau du site non renseigné')
      return l
    })
    expect(ligne).not.toHaveTextContent('13 h')
    expect(screen.getByRole('link', { name: /Réglages › site/ })).toHaveAttribute('href', '/calepinage/reglages')
  })

  it('hors d’un calepinage (pas d’identifiant), rien ne s’affiche', () => {
    barre()
    render(<MemoryRouter initialEntries={['/ventes/devis/3']}><HeureLegale /></MemoryRouter>)
    expect(document.getElementById('rp9-sun-legal')).toBeNull()
    expect(soleilLegal).not.toHaveBeenCalled()
  })

  it('formaterHeureLegale : l’heure solaire plus l’écart servi, à la minute près', () => {
    expect(formaterHeureLegale(12, 104.6)).toBe('13 h 45')
    expect(formaterHeureLegale(12, 60)).toBe('13 h 00')
    expect(formaterHeureLegale(23, 120)).toBe('1 h 00')
  })
})
