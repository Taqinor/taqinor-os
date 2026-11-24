import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* VREF-CARTE (fondateur 08/09/2026, lead « sidi hashass » sans GPS) : quand
   NI le GPS du lead, NI le gazetier, NI Nominatim ne placent le dossier, le
   dialogue affichait « Position introuvable — liste sans carte » — mais la
   liste des villes proches se calcule DEPUIS cette même position absente :
   ni carte, ni liste, Confirmer grisé — un cul-de-sac. La carte doit
   TOUJOURS s'afficher (Maroc entier par défaut) et un clic de Meryem à
   l'endroit approximatif du client relance la recherche des villes ERP
   proches par le chemin GPS existant de l'endpoint. Le point cliqué n'est
   JAMAIS écrit sur le lead (estimation humaine, pas un fait). */

vi.mock('../../../../api/crmApi', () => ({
  default: { villeStatut: vi.fn() },
}))
// MapView (Leaflet impératif) remplacé par un stub : expose le nombre de
// marqueurs et un bouton qui simule un clic sur la carte.
vi.mock('../../../../components/MapView', () => ({
  default: ({ markers, onMapClick }) => (
    <div data-testid="mapview" data-markers={markers.length}>
      <button type="button" onClick={() => onMapClick?.({ lat: 34.92, lng: -2.32 })}>
        simuler un clic sur la carte
      </button>
    </div>
  ),
}))

import crmApi from '../../../../api/crmApi'
import { reponseContrat } from '../../../../test/fixtures/contractSamples'
import VilleCheckDialog from './VilleCheckDialog'

/* T4-U3-019 — les réponses viennent du contrat committé (`lead_ville_statut.json`, PACT10) : `preselection` est la
   SEULE ville que l'écran coche d'avance ; `null` pour une ville inconnue. Seules la position et la liste des villes
   proches sont posées par cas (géographie du scénario). */
const inconnue = (sur = {}) => {
  const r = reponseContrat('crm', 'lead_ville_statut', 'exemple_inconnue')
  return { data: { ...r.data, ...sur } }
}
const SANS_POSITION = inconnue()
const AUTOUR_DE_BERKANE = inconnue({
  position: { lat: 34.92, lng: -2.32 },
  proches: [
    { ville: 'Berkane', lat: 34.9167, lng: -2.3167, distance_km: 0.4 },
    { ville: 'Oujda', lat: 34.6805, lng: -1.9076, distance_km: 46.2 },
  ],
})

afterEach(() => {
  cleanup()
  // mockReset (pas clearAllMocks) : vide aussi la file des `mockResolvedValueOnce`
  // d'un test tombé en route — sinon elle contamine le test suivant.
  crmApi.villeStatut.mockReset()
})

function renderDialog(props = {}) {
  const onChoisir = vi.fn()
  render(
    <VilleCheckDialog
      open onOpenChange={() => {}} ville="sidi hashass" gpsLat="" gpsLng=""
      onChoisir={onChoisir} {...props}
    />,
  )
  return { onChoisir }
}

describe('VilleCheckDialog — carte toujours visible, clic = position (VREF-CARTE)', () => {
  it('sans position connue, la carte est affichée avec la consigne de cliquer', async () => {
    crmApi.villeStatut.mockResolvedValue(SANS_POSITION)
    renderDialog()
    expect(await screen.findByTestId('mapview')).toBeInTheDocument()
    expect(screen.getByText(/cliquez sur la carte/i)).toBeInTheDocument()
    expect(screen.queryByText(/liste sans carte/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })

  it('un clic sur la carte relance la recherche depuis le point cliqué ; la ville se choisit (rien de coché d’avance, T4-U3-019)', async () => {
    const user = userEvent.setup()
    crmApi.villeStatut
      .mockResolvedValueOnce(SANS_POSITION)
      .mockResolvedValueOnce(AUTOUR_DE_BERKANE)
    const { onChoisir } = renderDialog()
    await user.click(await screen.findByRole('button', { name: 'simuler un clic sur la carte' }))
    await waitFor(() => expect(crmApi.villeStatut).toHaveBeenCalledTimes(2))
    expect(crmApi.villeStatut.mock.calls[1][0]).toEqual(expect.objectContaining({
      ville: 'sidi hashass', proches: true, gps_lat: 34.92, gps_lng: -2.32,
    }))
    const berkane = await screen.findByRole('radio', { name: /Berkane/ })
    expect(berkane).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
    // Repère du point cliqué + 2 villes ERP.
    expect(screen.getByTestId('mapview')).toHaveAttribute('data-markers', '3')
    await user.click(berkane)
    await user.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(onChoisir).toHaveBeenCalledWith({ mode: 'voisine', ville: 'Berkane' })
  })

  it('un clic hors du Maroc est signalé comme tel — jamais confondu avec le GPS du lead', async () => {
    const user = userEvent.setup()
    crmApi.villeStatut
      .mockResolvedValueOnce(SANS_POSITION)
      .mockResolvedValueOnce(inconnue({ gps_hors_zone: true }))
    renderDialog()
    await user.click(await screen.findByRole('button', { name: 'simuler un clic sur la carte' }))
    expect(await screen.findByText(/point cliqué est hors du Maroc/i)).toBeInTheDocument()
    expect(screen.queryByText(/repère GPS enregistré/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })

  it('avec une position connue, la carte et la liste s’affichent d’emblée ; ville inconnue = rien de coché (T4-U3-019)', async () => {
    crmApi.villeStatut.mockResolvedValue(AUTOUR_DE_BERKANE)
    renderDialog()
    expect(await screen.findByRole('radio', { name: /Berkane/ })).not.toBeChecked()
    expect(screen.getByTestId('mapview')).toHaveAttribute('data-markers', '3')
    expect(screen.queryByText(/cliquez sur la carte/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })

  it('« kech » reconnu (preselection servie « Marrakech ») : Marrakech seul coché, Confirmer actif', async () => {
    crmApi.villeStatut.mockResolvedValue(reponseContrat('crm', 'lead_ville_statut'))
    renderDialog({ ville: 'kech' })
    expect(await screen.findByRole('radio', { name: /Marrakech/ })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeEnabled()
  })
})
