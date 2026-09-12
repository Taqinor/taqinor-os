/* VTA12 — « Ma journée », l'accueil de l'app Visites.

   Les charges de test COPIENT le contrat committé
   `backend/django_core/apps/visites/contract_samples/ma_journee.json` à la clé
   près (PACT10 : deux moitiés qui inventent chacune leur forme, c'est l'écran
   mort du 03/08/2026). Si le contrat bouge, ce fichier doit bouger avec lui.

   Ce qui est vérifié ici :
     1. le rendu de la journée (cartes, ville/adresse, badge de complétude
        SERVEUR, bandeau de retard depuis `en_retard_count`) ;
     2. la PROGRESSION : « En route » puis « Arrivé » appellent les BONNES
        actions et l'écran affiche les horodatages RENVOYÉS PAR LE SERVEUR ;
     3. la portée : l'écran ne demande aucun filtre « toutes » — la portée est
        imposée serveur (VTA6), il ne voit donc que SES visites ;
     4. l'état vide honnête.
*/
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const getMaJournee = vi.fn()
const demarrerRouteVisite = vi.fn()
const arriverVisite = vi.fn()

vi.mock('../../api/visitesApi', () => ({
  default: {
    getMaJournee: (...a) => getMaJournee(...a),
    demarrerRouteVisite: (...a) => demarrerRouteVisite(...a),
    arriverVisite: (...a) => arriverVisite(...a),
  },
}))

import MaJourneePage from './MaJourneePage'

// ── LE contrat `ma_journee.json`, LU et non recopié (PACT10) ───────────────
// Une charge recopiée est une DEUXIÈME source de vérité : c'est exactement ce
// qui a laissé passer l'écran AO mort du 03/08/2026 (test vert, écran vide).
// Ici la fixture vient du fichier que le backend affirme ; si le serveur change
// de forme, ce test casse tout seul.
const JOURNEE = exempleContrat('visites', 'ma_journee')

const rendre = () => render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

describe('MaJourneePage — VTA9/VTA12', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getMaJournee.mockResolvedValue(reponseContrat('visites', 'ma_journee'))
  })

  it('rend la journée : client, ville/adresse, complétude serveur, retard', async () => {
    rendre()
    expect(await screen.findByText('Client Démo')).toBeInTheDocument()
    expect(screen.getByText(/Quartier Démo, Bouskoura/)).toBeInTheDocument()
    // `manquants_count` vient du serveur — l'écran l'affiche, il ne le calcule pas.
    expect(screen.getByText('3 manquant(s)')).toBeInTheDocument()
    expect(screen.getByText(/1 visite en retard/)).toBeInTheDocument()
  })

  it('ne demande QUE ma journée : aucun filtre d’équipe passé au serveur', async () => {
    rendre()
    await screen.findByText('Client Démo')
    expect(getMaJournee).toHaveBeenCalledTimes(1)
    // Aucun `?tous=1` : la portée est imposée SERVEUR (VTA6), pas négociée ici.
    const args = getMaJournee.mock.calls[0]
    expect(args[0] ?? undefined).toBeUndefined()
  })

  it('propose un lien de navigation quand le lead a des coordonnées', async () => {
    rendre()
    await screen.findByText('Client Démo')
    const geo = screen.getByRole('link', { name: /Y aller/i })
    expect(geo).toHaveAttribute('href', expect.stringContaining('geo:33.4589,-7.6528'))
    expect(screen.getByRole('link', { name: /Google Maps/i }))
      .toHaveAttribute('href', expect.stringContaining('33.4589,-7.6528'))
  })

  it('progression : « En route » puis « Arrivé », horodatages SERVEUR affichés', async () => {
    const user = userEvent.setup()
    demarrerRouteVisite.mockResolvedValue({
      data: { ...JOURNEE.visites[0], en_route_le: '2026-09-14T08:12:00Z' },
    })
    arriverVisite.mockResolvedValue({
      data: {
        ...JOURNEE.visites[0],
        en_route_le: '2026-09-14T08:12:00Z',
        arrivee_le: '2026-09-14T08:41:00Z',
      },
    })
    rendre()
    await screen.findByText('Client Démo')

    await user.click(screen.getByRole('button', { name: 'En route' }))
    await waitFor(() => expect(demarrerRouteVisite).toHaveBeenCalledWith(7))
    // L'heure vient de la RÉPONSE serveur, jamais d'une horloge locale.
    expect(await screen.findByText(/En route à/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Arrivé' }))
    await waitFor(() => expect(arriverVisite).toHaveBeenCalledWith(7))
    expect(await screen.findByText(/Arrivé à/)).toBeInTheDocument()
    // Une fois arrivé, plus de bouton de progression : il reste la visite.
    expect(screen.queryByRole('button', { name: 'En route' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Arrivé' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ouvrir la visite/ })).toBeInTheDocument()
  })

  it('état vide HONNÊTE quand rien n’est planifié', async () => {
    // Autre ÉTAT du serveur, jamais une autre FORME : on part du contrat.
    getMaJournee.mockResolvedValue({ data: { ...JOURNEE, en_retard_count: 0, visites: [] } })
    rendre()
    expect(await screen.findByText(/Aucune visite aujourd/)).toBeInTheDocument()
    expect(screen.queryByText(/en retard/)).not.toBeInTheDocument()
  })

  it('erreur de chargement : message explicite, jamais une journée vide silencieuse', async () => {
    getMaJournee.mockRejectedValue(new Error('boom'))
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent(/journée impossible/i)
  })
})
