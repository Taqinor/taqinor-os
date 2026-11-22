import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* Écran neuf « Montrer au client » au téléphone (maquette TelephoneClient) : le toit
   ENREGISTRÉ dessiné (jamais une image d'exemple), les tuiles dans l'ordre de la maquette
   et seulement avec des données servies, le partage désactivé AVEC sa raison, aucun montant. */

const ZONE = {
  id: 'z1', label: 'Pan sud',
  vertices: [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5001], [-7.6, 33.5001]],
  geometry: { origin: [-7.5999, 33.50005], panels: [{ cx: -1, cy: 0 }, { cx: 1, cy: 0 }], tiltDeg: 20, azimuthDeg: 180 },
}
const RESULTAT = {
  simule: true, simulation_perimee: false,
  pose: { total_modules: 2, kwc: 1.1 },
  production: { total: { p50_kwh: 11480.4 } },
  autoconsommation: { taux_couverture: 0.82 },
}

const api = { layout: vi.fn(), designContext: vi.fn(), resultat: vi.fn() }
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: new Proxy({}, { get: (_, nom) => (...a) => api[nom](...a) }) },
}))

const { default: VueClient } = await import('./VueClient')

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/7/client']}>
    <Routes><Route path="/calepinage/:id/client" element={<VueClient />} /></Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  api.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE], activeAreaId: 'z1' }, empreinte_document: 'e' } })
  api.designContext.mockResolvedValue({ data: { calepinage: { titre: 'Villa Bennani', client_ville: 'Casablanca' } } })
  api.resultat.mockResolvedValue({ data: RESULTAT })
})
afterEach(() => { cleanup() })

describe('Montrer au client — la maquette, avec les seules données servies', () => {
  it('toit enregistré dessiné, puce du projet, trois tuiles dans l’ordre (la médiane marine), pied', async () => {
    rendre()
    const plan = await screen.findByTestId('client-plan')
    expect(plan.querySelectorAll('.cal-client-pan')).toHaveLength(1)
    expect(plan.querySelectorAll('.cal-client-module')).toHaveLength(2)
    expect(await screen.findByTestId('client-projet')).toHaveTextContent('Villa Bennani')
    expect(screen.getByTestId('client-projet')).toHaveTextContent('Casablanca · Pan sud')
    await waitFor(() => expect(screen.getByTestId('client-tuiles').children).toHaveLength(3))
    const tuiles = [...screen.getByTestId('client-tuiles').children]
    expect(tuiles.map((t) => t.dataset.testid)).toEqual(['client-tuile-panneaux', 'client-tuile-kwh', 'client-tuile-couverture'])
    expect(tuiles[0]).toHaveTextContent('2panneaux')
    expect(tuiles[1].textContent.replace(/\s/g, ' ')).toMatch(/^11.480kWh par an · estimation$/)
    expect(tuiles[1].className).toContain('cal-client-tuile-marine')
    expect(tuiles[2]).toHaveTextContent('82 %')
    expect(screen.getByText('Estimation pour une année moyenne à Casablanca. Les montants figurent dans le devis.')).toBeInTheDocument()
    expect(screen.getByTestId('client-retour-releve')).toHaveTextContent('Retour au relevé')
    expect(screen.getByTestId('client-retour-releve').getAttribute('href')).toBe('/calepinage/7/releve')
    expect(screen.getByTestId('cal-vue-client').textContent).not.toMatch(/MAD|DH|prix|marge/i)
  })

  it('« Envoyer le lien » est désactivé et dit pourquoi, en français', async () => {
    rendre()
    const bouton = await screen.findByTestId('client-envoyer-lien')
    expect(bouton).toHaveTextContent('Envoyer le lien')
    expect(bouton).toBeDisabled()
    expect(bouton.getAttribute('aria-describedby')).toBe('client-lien-raison')
    expect(screen.getByTestId('client-lien-raison')).toHaveTextContent('« Envoyer au client »')
  })

  it('une simulation périmée retire les tuiles servies par elle ; sans toit, rien n’est dessiné', async () => {
    api.resultat.mockResolvedValue({ data: { ...RESULTAT, simulation_perimee: true } })
    api.layout.mockResolvedValue({ data: { roof_layout: {}, empreinte_document: '' } })
    rendre()
    expect(await screen.findByTestId('client-sans-toit')).toHaveTextContent('Aucun toit enregistré pour ce calepinage.')
    await waitFor(() => expect(api.resultat).toHaveBeenCalled())
    expect(screen.queryByTestId('client-tuiles')).toBeNull()
    expect(screen.queryByTestId('client-plan')).toBeNull()
  })
})
