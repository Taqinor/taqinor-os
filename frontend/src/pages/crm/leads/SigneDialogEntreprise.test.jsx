// CIQ324 — le dialogue « Signé » d'un lead : trois champs FACULTATIFS
// d'identité d'entreprise pour un devis commercial / industriel, corps du
// contrat partagé `acceptation_entreprise.json` ; résidentiel inchangé.
//
// Run : npx vitest run src/pages/crm/leads/SigneDialogEntreprise.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../../api/ventesApi', async (importOriginal) =>
  (await import('../../../test/etendreApi')).etendreApi(importOriginal, {
    getDevis: vi.fn(),
    accepterDevis: vi.fn(() => Promise.resolve({ data: {} })),
  }))

import SigneDialog from './SigneDialog'
import ventesApi from '../../../api/ventesApi'
import { exempleContrat, documentContrat } from '../../../test/fixtures/contractSamples'

const ERP = exempleContrat('ventes', 'acceptation_entreprise', 'exemple_erp').corps

const devis = (mode) => ({
  id: 77, reference: 'DEV-SIGNE-77', statut: 'envoye', total_ttc: 90000, nb_options: 1,
  date_creation: '2026-09-01', mode_installation: mode,
})

async function ouvrir(mode) {
  ventesApi.getDevis.mockResolvedValue({ data: { results: [devis(mode)] } })
  ventesApi.accepterDevis.mockClear()
  render(<SigneDialog lead={{ id: 5, nom: 'Exemple', prenom: 'Karim' }}
                      onClose={() => {}} onConfirmed={() => {}} />)
  await screen.findByLabelText('Devis accepté')
}

const confirmer = () => fireEvent.click(screen.getByRole('button', { name: /Confirmer|Marquer|Passer/ }))

describe('SigneDialog — ACVI68 refus serveur', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('rend la saisie au parent, puis se rouvre pré-rempli avec l\'erreur sous le champ', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: { results: [devis('residentiel')] } })
    ventesApi.accepterDevis.mockRejectedValueOnce({
      response: { status: 400, data: { nom: ['Obligatoire.'] } },
    })
    const onFailed = vi.fn()
    const lead = { id: 5, nom: 'Exemple', prenom: 'Karim' }
    const { unmount } = render(
      <SigneDialog lead={lead} onClose={() => {}} onConfirmed={() => {}} onFailed={onFailed} />)
    await screen.findByLabelText('Devis accepté')
    fireEvent.change(screen.getByLabelText(/Nom de la personne/), { target: { value: 'M. Bennani' } })
    confirmer()
    await waitFor(() => expect(onFailed).toHaveBeenCalledTimes(1))
    const { saisie, erreurs } = onFailed.mock.calls[0][0]
    expect(saisie.nom).toBe('M. Bennani')
    expect(erreurs.nom).toBe('Obligatoire.')
    unmount()
    render(<SigneDialog lead={lead} onClose={() => {}} onConfirmed={() => {}}
                        saisieInitiale={{ ...saisie, erreurs }} />)
    await screen.findByLabelText('Devis accepté')
    expect(screen.getByLabelText(/Nom de la personne/)).toHaveValue('M. Bennani')
    expect(screen.getByText('Obligatoire.')).toBeInTheDocument()
  })

  it('400 date : message sous la date', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: { results: [devis('residentiel')] } })
    ventesApi.accepterDevis.mockRejectedValueOnce({
      response: { status: 400, data: { date: ['Date invalide.'] } },
    })
    const onFailed = vi.fn()
    const lead = { id: 5, nom: 'Exemple', prenom: 'Karim' }
    const { unmount } = render(
      <SigneDialog lead={lead} onClose={() => {}} onConfirmed={() => {}} onFailed={onFailed} />)
    await screen.findByLabelText('Devis accepté')
    confirmer()
    await waitFor(() => expect(onFailed).toHaveBeenCalledTimes(1))
    const { saisie, erreurs } = onFailed.mock.calls[0][0]
    expect(erreurs.date).toBe('Date invalide.')
    // Sous son champ, jamais deux fois à l'écran.
    expect(saisie.message).toBeNull()
    unmount()
    render(<SigneDialog lead={lead} onClose={() => {}} onConfirmed={() => {}}
                        saisieInitiale={{ ...saisie, erreurs }} />)
    await screen.findByLabelText('Devis accepté')
    const sousDate = screen.getByText('Date invalide.')
    expect(screen.getByLabelText("Date d'acceptation").nextElementSibling).toBe(sousDate)
  })
})

describe('SigneDialog — CIQ324 identité d\'entreprise', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('industriel : trois champs, corps avec le bloc `entreprise`', async () => {
    await ouvrir('industriel')
    fireEvent.change(screen.getByLabelText('Raison sociale'),
      { target: { value: ERP.entreprise.raison_sociale } })
    fireEvent.change(screen.getByLabelText('Qualité du signataire'),
      { target: { value: 'Directeur général' } })
    fireEvent.change(screen.getByLabelText('ICE'), { target: { value: '000000000000000' } })
    confirmer()
    await waitFor(() => expect(ventesApi.accepterDevis).toHaveBeenCalledTimes(1))
    const [id, corps] = ventesApi.accepterDevis.mock.calls[0]
    expect(id).toBe(77)
    expect(corps.entreprise).toEqual({
      raison_sociale: ERP.entreprise.raison_sociale,
      signataire_qualite: 'Directeur général',
      ice: '000000000000000',
    })
    expect(Object.keys(corps.entreprise).sort()).toEqual(Object.keys(ERP.entreprise).sort())
  })

  it('résidentiel : aucun champ d\'entreprise, corps {nom, date, option}', async () => {
    await ouvrir('residentiel')
    expect(screen.queryByTestId('identite-entreprise')).toBeNull()
    confirmer()
    await waitFor(() => expect(ventesApi.accepterDevis).toHaveBeenCalledTimes(1))
    expect(Object.keys(ventesApi.accepterDevis.mock.calls[0][1]).sort())
      .toEqual(['date', 'nom', 'option'])
  })
})

// VNT80 — un refus qui NOMME un autre devis (exemple committé
// devis_prix_negocie.json, `vente_active`) : message nommé sous le bouton + lien.
describe('SigneDialog — VNT80 : vente active existante', () => {
  it('message serveur sous le bouton et lien « Ouvrir <réf> » vers ?devis=<id>', async () => {
    const refus = documentContrat('ventes', 'devis_prix_negocie').erreurs_409.vente_active_existante
    await ouvrir('residentiel')
    ventesApi.accepterDevis.mockRejectedValueOnce({ response: { status: 409, data: refus } })
    confirmer()
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(refus.detail)
    expect(screen.getByRole('link', { name: `Ouvrir ${refus.vente_active.reference}` }))
      .toHaveAttribute('href', `/ventes/devis?devis=${refus.vente_active.id}`)
  })
})
