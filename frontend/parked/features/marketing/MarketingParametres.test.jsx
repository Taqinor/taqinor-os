import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

// AUDV17 — `conformiteCndp` est appelé AU MONTAGE de l'écran : absent du
// mock, l'appel part sur `undefined` et fait planter la page entière.
const mocks = vi.hoisted(() => ({
  get: vi.fn(), maj: vi.fn(), conformiteCndp: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    parametres: { get: mocks.get, maj: mocks.maj },
    campagnes: { conformiteCndp: mocks.conformiteCndp },
  },
}))

import MarketingParametres from './MarketingParametres.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({
    data: {
      id: 1, expediteur_nom: '', expediteur_email: '', expediteur_domaine: '',
      silence_heure_debut: null, silence_heure_fin: null,
      plafond_envois_jour: null, langue_defaut_templates: 'fr',
    },
  })
  mocks.conformiteCndp.mockResolvedValue({
    data: {
      double_optin_actif: false, pied_cndp: '',
      pied_cndp_configure: false, mention_stop_sms: ' STOP au 00000',
    },
  })
})

describe('MarketingParametres (NTMKT31)', () => {
  it('charge et affiche les réglages actuels', async () => {
    render(<MarketingParametres />)
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId('marketing-parametres')).toBeInTheDocument()
  })

  it("modifier le plafond puis enregistrer appelle l'API avec la nouvelle valeur", async () => {
    mocks.maj.mockResolvedValue({
      data: { id: 1, plafond_envois_jour: 500, langue_defaut_templates: 'fr' },
    })
    render(<MarketingParametres />)
    await screen.findByTestId('marketing-parametres')

    fireEvent.change(screen.getByTestId('parametres-plafond'), { target: { value: '500' } })
    fireEvent.click(screen.getByTestId('parametres-enregistrer'))

    await waitFor(() => expect(mocks.maj).toHaveBeenCalledWith(
      expect.objectContaining({ plafond_envois_jour: 500 })))
    expect(await screen.findByText('Réglages enregistrés.')).toBeInTheDocument()
  })
})

/* AUDV17 — le toggle double opt-in, le pied de déclaration CNDP et la mention
   STOP existaient tous côté services SANS AUCUNE surface : personne, dans
   l'ERP, ne pouvait dire si les campagnes partaient conformes à la loi 09-08.
   Le cas DANGEREUX — pas de numéro de déclaration, donc des emails sans
   mention légale — doit être dit explicitement, jamais laissé au silence. */
describe('MarketingParametres — conformité CNDP (AUDV17)', () => {
  it('signale EXPLICITEMENT l’absence de numéro de déclaration', async () => {
    render(<MarketingParametres />)
    await screen.findByTestId('marketing-parametres')

    await waitFor(() => expect(mocks.conformiteCndp).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId('cndp-pied')).toHaveTextContent(
      /les emails partent sans mention légale/i)
    expect(screen.getByTestId('cndp-double-optin'))
      .toHaveTextContent(/désactivé/i)
    expect(screen.getByTestId('cndp-stop')).toHaveTextContent(/STOP/)
  })

  it('affiche le pied légal quand la déclaration est renseignée', async () => {
    mocks.conformiteCndp.mockResolvedValue({
      data: {
        double_optin_actif: true, pied_cndp: 'Déclaration CNDP n° A-GC-123',
        pied_cndp_configure: true, mention_stop_sms: ' STOP au 00000',
      },
    })
    render(<MarketingParametres />)
    await screen.findByTestId('marketing-parametres')

    expect(await screen.findByTestId('cndp-pied'))
      .toHaveTextContent('Déclaration CNDP n° A-GC-123')
    expect(screen.getByTestId('cndp-double-optin')).toHaveTextContent(/activé/i)
  })
})
