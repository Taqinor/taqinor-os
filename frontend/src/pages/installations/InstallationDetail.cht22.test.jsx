import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'
import userEvent from '@testing-library/user-event'

/* ============================================================================
   CHT22 — Un seul niveau de qualité pour changer le statut.
   ----------------------------------------------------------------------------
   Le Select legacy ±1 (onglet Aperçu, section « Chantier ») ignorait les
   gates CH2 : une transition bloquée finissait en message d'erreur brut au
   save, alors que le stepper CH6 (ChantierGateTimeline, onglet Jalons &
   gates) affiche la liste à puces des raisons (`data-testid=
   "ch6-blocked-reasons"`, déjà couvert par ChantierGateTimeline.test.jsx).
   Ce test verrouille le SECOND chemin : la même 400 `{statut: [...]}`
   (`views/installation.py` -> `TransitionRefusee`) rend désormais le MÊME
   format, jamais un message brut sérialisé.

   Patron établi (WIR243/PaieParametres.test.jsx) : Radix Select ne s'ouvre
   pas de façon fiable sous jsdom (portail + pointer events) — remplacer les
   primitives Select par un <select> natif, le reste de `../../ui` reste réel.
   Le `id` porté par `SelectTrigger` (association label <-> champ, ex.
   "ch-statut") est reporté sur le <select> natif rendu par le mock.
   ========================================================================== */

beforeAll(polyfillResizeObserver)

vi.mock('../../ui', async (importActual) => (await import('../../test/selectNatif'))
  .avecSelectNatifSimple(await importActual(), { role: 'combobox', idDuTrigger: true }))

const RAISON = "Le pack de remise client n'est pas complet."

vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
    updateInstallation: vi.fn(() => Promise.reject({
      response: { data: { statut: [RAISON] } },
    })),
  },
}))

vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)

vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)

vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

import InstallationDetail from './InstallationDetail'
import installationsApi from '../../api/installationsApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — statut bloqué : raisons visibles (CHT22)', () => {
  it('affiche la liste à puces des raisons (format ch6-blocked-reasons) au lieu d\'un message brut', async () => {
    const user = userEvent.setup()
    renderInstallationDetail({
      id: 801, reference: 'CH-CHT22-801', statut: 'signe', annule: false,
    })

    const select = await screen.findByLabelText('Statut')
    await user.selectOptions(select, 'materiel_commande')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    const bloc = await screen.findByTestId('ch6-blocked-reasons')
    expect(bloc).toHaveTextContent(RAISON)
    // Jamais le message brut générique EN PLUS du format à puces.
    expect(screen.queryByText('Enregistrement impossible.')).toBeNull()
  })
})

/* AGR604 — régime « Déclaration hors réseau (loi 82-21, art. 3) » et champ
   « Raccordement au réseau » de la section 82-21 (même mock Select natif). */
describe('InstallationDetail — AGR604 hors réseau', () => {
  const enregistrerSansToucher = async (user, chantier) => {
    installationsApi.updateInstallation.mockResolvedValueOnce({ data: { id: chantier.id } })
    const rendu = renderInstallationDetail(chantier)
    await screen.findByLabelText('Régime')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(installationsApi.updateInstallation).toHaveBeenCalled())
    return rendu
  }

  it('offre le régime hors réseau et le raccordement, envoyés au PATCH', async () => {
    installationsApi.updateInstallation.mockResolvedValueOnce({ data: { id: 901 } })
    const user = userEvent.setup()
    renderInstallationDetail({ id: 901, reference: 'CH-901', statut: 'signe', annule: false })

    const regime = await screen.findByLabelText('Régime')
    expect(screen.getByRole('option', {
      name: 'Déclaration hors réseau (loi 82-21, art. 3)',
    })).toBeInTheDocument()
    await user.selectOptions(regime, 'declaration_hors_reseau')
    await user.selectOptions(screen.getByLabelText('Raccordement au réseau'), 'hors_reseau')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(installationsApi.updateInstallation).toHaveBeenCalledTimes(1))
    const [id, data] = installationsApi.updateInstallation.mock.calls[0]
    expect(id).toBe(901)
    expect(data.regime_8221).toBe('declaration_hors_reseau')
    expect(data.raccordement_reseau).toBe('hors_reseau')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', async () => {
    const user = userEvent.setup()
    const chantier = {
      id: 902, reference: 'CH-902', statut: 'signe', annule: false,
      regime_8221: 'declaration_hors_reseau', raccordement_reseau: 'hors_reseau',
    }
    const premier = await enregistrerSansToucher(user, chantier)
    premier.unmount()
    await enregistrerSansToucher(user, chantier)
    expect(installationsApi.updateInstallation).toHaveBeenCalledTimes(2)
    expect(installationsApi.updateInstallation.mock.calls[1])
      .toEqual(installationsApi.updateInstallation.mock.calls[0])
  })

  it('raccordement non renseigné et non touché n’est pas renvoyé (ACHT57)', async () => {
    const user = userEvent.setup()
    await enregistrerSansToucher(user, { id: 903, reference: 'CH-903', statut: 'signe', annule: false })
    expect(installationsApi.updateInstallation.mock.calls[0][1]).not.toHaveProperty('raccordement_reseau')
  })
})
