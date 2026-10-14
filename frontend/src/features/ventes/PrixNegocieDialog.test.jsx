import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* VNT73 — « Prix négocié ». Toutes les réponses serveur viennent du contrat
   committé `apps/ventes/contract_samples/devis_prix_negocie.json`. */

vi.mock('../../api/axios', () => ({ default: { post: vi.fn() } }))

import api from '../../api/axios'
import PrixNegocieDialog from './PrixNegocieDialog'

const CONTRAT = documentContrat('ventes', 'devis_prix_negocie')
const APERCU = CONTRAT.reponse_apercu_200
const APPLIQUE = CONTRAT.reponse_appliquer_201
const SIGNATURE = CONTRAT.demander_signature.exemple
const DEVIS = { id: 318, total_ttc: '54500.00' }

const erreur400 = (code) => Object.assign(new Error('400'), {
  response: { status: 400, data: CONTRAT.erreurs_400[code] },
})

function serveur() {
  api.post.mockImplementation((url, body) => {
    if (url.endsWith('/avenant/demander-signature/')) return Promise.resolve({ data: SIGNATURE })
    return Promise.resolve({ data: body.mode === 'apercu' ? APERCU : APPLIQUE })
  })
}

const rendre = (props = {}) => render(
  <PrixNegocieDialog devis={DEVIS} open onOpenChange={() => {}} {...props} />,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('PrixNegocieDialog (VNT73)', () => {
  it('taper 49 000 sur 54 500 : aperçu serveur (10,00 %, factures annulées) puis application', async () => {
    serveur()
    const user = userEvent.setup()
    const onApplied = vi.fn()
    rendre({ onApplied })
    const champ = screen.getByLabelText(/Nouveau prix TTC/)
    expect(champ).toHaveAttribute('step', 'any')
    await user.type(champ, '49000')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))

    const effets = await screen.findByLabelText(/Effets du prix négocié/)
    expect(api.post).toHaveBeenCalledWith('/ventes/devis/318/prix-negocie/',
      { prix_ttc: '49000', mode: 'apercu' })
    expect(effets).toHaveTextContent('10,00 %')
    expect(effets).toHaveTextContent(APERCU.factures_annulees[0].reference)
    expect(effets).toHaveTextContent(/49\D?000/)

    await user.click(screen.getByRole('button', { name: /Appliquer le prix négocié/ }))
    await waitFor(() => expect(onApplied).toHaveBeenCalledWith(APPLIQUE))
    expect(await screen.findByText(/Version 2 créée/)).toHaveTextContent(APPLIQUE.devis_v2.reference)
  })

  it('une remise en MAD est envoyée comme prix_ttc', async () => {
    serveur()
    const user = userEvent.setup()
    rendre()
    await user.type(screen.getByLabelText(/Remise \(MAD/), '5500')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    await screen.findByLabelText(/Effets du prix négocié/)
    expect(api.post.mock.calls[0][1]).toEqual({ prix_ttc: '49000.00', mode: 'apercu' })
  })

  it('deux champs remplis : refus nommé sous le champ, aucun appel réseau', async () => {
    const user = userEvent.setup()
    rendre()
    await user.type(screen.getByLabelText(/Nouveau prix TTC/), '49000')
    await user.type(screen.getByLabelText(/Remise \(%\)/), '10')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent(CONTRAT.erreurs_400.saisie_double.detail)
    expect(api.post).not.toHaveBeenCalled()
  })

  it('prix_inatteignable : message sous le champ et voisins proposés en boutons', async () => {
    api.post.mockRejectedValueOnce(erreur400('prix_inatteignable'))
    const user = userEvent.setup()
    rendre()
    await user.type(screen.getByLabelText(/Nouveau prix TTC/), '49000.5')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    const [bas, haut] = CONTRAT.erreurs_400.prix_inatteignable.prix_atteignables
    expect(await screen.findByText(CONTRAT.erreurs_400.prix_inatteignable.detail)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: bas }))
    expect(screen.getByLabelText(/Nouveau prix TTC/)).toHaveValue(Number(bas))
    expect(screen.queryByRole('button', { name: haut })).not.toBeInTheDocument()
  })

  it('avoir_a_confirmer : bandeau + case, la confirmation repart avec la requête', async () => {
    api.post.mockRejectedValueOnce(erreur400('avoir_a_confirmer'))
    api.post.mockResolvedValue({ data: APERCU })
    const user = userEvent.setup()
    rendre()
    await user.type(screen.getByLabelText(/Nouveau prix TTC/), '49000')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    expect(await screen.findByText(CONTRAT.erreurs_400.avoir_a_confirmer.detail)).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /confirme l'émission de l'avoir/ }))
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    await screen.findByLabelText(/Effets du prix négocié/)
    expect(api.post.mock.calls[1][1]).toMatchObject({ confirmer_avoir: true })
  })

  it('« Faire signer l\'avenant » copie le lien et ne fait qu\'UN appel', async () => {
    serveur()
    const user = userEvent.setup()
    const ecrireCopie = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined)
    rendre()
    await user.type(screen.getByLabelText(/Nouveau prix TTC/), '49000')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    await screen.findByLabelText(/Effets du prix négocié/)
    await user.click(screen.getByRole('button', { name: /Appliquer le prix négocié/ }))
    const bouton = await screen.findByRole('button', { name: /Faire signer l'avenant/ })
    await user.click(bouton)
    await user.click(bouton)
    expect(await screen.findByTestId('lien-avenant')).toHaveTextContent(SIGNATURE.share_link)
    await waitFor(() => expect(ecrireCopie).toHaveBeenCalledWith(SIGNATURE.share_link))
    const appels = api.post.mock.calls.filter(([u]) => u.includes('/avenant/demander-signature/'))
    expect(appels).toHaveLength(1)
    expect(appels[0][0]).toBe(`/ventes/devis/${APPLIQUE.devis_v2.id}/avenant/demander-signature/`)
  })
})

// VNT78 — monté depuis le panneau de vente : le bouton suit `vente.peut.prix_negocie`
// (exemples committés de vente_etat.json) ; l'application relit le lead.
describe('PrixNegocieDialog — VNT78 : monté dans le panneau de vente', () => {
  const panneau = async (variante, props = {}) => {
    const { exempleContrat } = await import('../../test/fixtures/contractSamples')
    const { default: PanneauVente } = await import('./vente/PanneauVente')
    const vente = exempleContrat('ventes', 'vente_etat', variante).vente
    return render(<PanneauVente devis={{ ...DEVIS, reference: 'DEV-318', vente }} {...props} />)
  }

  it('tête acceptée : « Prix négocié » ouvre le dialogue ; appliquer rafraîchit', async () => {
    serveur()
    const onRafraichir = vi.fn()
    const user = userEvent.setup()
    await panneau('exemple_acompte_paye_solde_a_faire', { onRafraichir })
    await user.click(screen.getByRole('button', { name: 'Prix négocié' }))
    await user.type(screen.getByLabelText(/Nouveau prix TTC/), '49000')
    await user.click(screen.getByRole('button', { name: /Voir les effets/ }))
    await screen.findByLabelText(/Effets du prix négocié/)
    await user.click(screen.getByRole('button', { name: /Appliquer le prix négocié/ }))
    await waitFor(() => expect(onRafraichir).toHaveBeenCalled())
  })

  it('version remplacée : aucun bouton « Prix négocié »', async () => {
    await panneau('exemple_version_remplacee')
    expect(screen.queryByRole('button', { name: 'Prix négocié' })).toBeNull()
  })
})
