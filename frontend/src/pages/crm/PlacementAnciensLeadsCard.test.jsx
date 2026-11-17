import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* MRY33 — carte Cockpit « Anciens leads à placer dans les cadences ». Charge
   utile venant de l'exemple COMMITTÉ
   (`apps/crm/contract_samples/placement_anciens_leads.json`, PACT10), jamais
   un objet retapé à la main : c'est cette deuxième source de vérité qui
   avait laissé passer l'écran AO mort du 03/08/2026 (test vert, écran mort).
   Si le serveur change de forme, l'exemple change et ce test casse tout
   seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const DONNEES = exempleContrat('crm', 'placement_anciens_leads')

// Même patron que `IdentityRail.test.jsx` : le hook de rôle est mocké plutôt
// qu'un vrai Provider redux — réassignable par test.
const isAdminOrResponsableMock = vi.fn(() => true)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    placerAnciensLeads: vi.fn(),
    getListeFroide: vi.fn(),
    prendreListeFroide: vi.fn(),
  },
}))

// Même patron que `ClientForm.test.jsx` : confirmation/toast mockés (le
// composant réel `ui/confirm` n'est pas ce qu'on vérifie ici).
const confirmMock = vi.fn(() => Promise.resolve(true))
vi.mock('../../ui/confirm', () => ({
  useConfirmDialog: () => ({ confirm: (...args) => confirmMock(...args), confirmDelete: vi.fn() }),
  toast: { success: vi.fn(), error: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import { toast } from '../../ui/confirm'
import PlacementAnciensLeadsCard from './PlacementAnciensLeadsCard'
import ListeFroideCard from './ListeFroideCard'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(true)
  confirmMock.mockResolvedValue(true)
  // Aperçu → l'exemple du contrat (restants == a_placer) ; application → tout
  // placé en un lot (applique = a_placer, restants 0). Le contrat ne porte
  // qu'un exemple d'aperçu : une réponse d'application se dérive de lui.
  crmApi.placerAnciensLeads.mockImplementation((body) => Promise.resolve(
    body?.apply
      ? { data: { ...DONNEES, apply: true, applique: DONNEES.a_placer, restants: 0 } }
      : reponseContrat('crm', 'placement_anciens_leads'),
  ))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlacementAnciensLeadsCard (MRY33)', () => {
  it('masquée pour un rôle normal (aucun appel réseau)', () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    const { container } = render(<PlacementAnciensLeadsCard />)
    expect(container).toBeEmptyDOMElement()
    expect(crmApi.placerAnciensLeads).not.toHaveBeenCalled()
  })

  it('le nombre d\'appels promis est celui du rapport, jamais un chiffre figé', async () => {
    render(<PlacementAnciensLeadsCard />)
    const carte = screen.getByTestId('placement-anciens-leads-card')
    expect(carte.textContent).not.toMatch(/six appels|appel\(s\)/)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    const attendu = `compte ${DONNEES.appels_contact} appel(s)`
    await waitFor(() => expect(carte.textContent).toContain(attendu))
    expect(carte.textContent).not.toMatch(/six appels/)
  })

  it('« Aperçu » affiche les cinq lignes par étape et le total à placer', async () => {
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(crmApi.placerAnciensLeads).toHaveBeenCalledWith({ apply: false }))
    await waitFor(() => {
      for (const etape of DONNEES.par_etape) {
        expect(screen.getByText(etape.libelle)).toBeInTheDocument()
      }
    })
    expect(screen.getAllByText(new RegExp(String(DONNEES.a_placer))).length).toBeGreaterThan(0)
    expect(screen.getAllByText(new RegExp(String(DONNEES.total_candidats))).length).toBeGreaterThan(0)
    // Le premier lead de l'aperçu (contrat) est bien listé.
    expect(screen.getByText(DONNEES.apercu[0].nom)).toBeInTheDocument()
  })

  it("ACRM73 — un badge par clé de ignores servie sur l'exemple committé", async () => {
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    const { ignores } = DONNEES
    expect(await screen.findByText(`Déjà en cadence : ${ignores.deja_en_cadence}`)).toBeInTheDocument()
    expect(screen.getByText(`Devis accepté non signé : ${ignores.devis_accepte_non_signe}`)).toBeInTheDocument()
    expect(screen.getByText(`Rappel manuel à venir : ${ignores.rappel_manuel_a_venir}`)).toBeInTheDocument()
  })

  it("ACRM73 — une clé inconnue s'affiche sous son nom brut, une clé à 0 ne s'affiche pas", async () => {
    crmApi.placerAnciensLeads.mockResolvedValueOnce({
      data: { ...DONNEES, ignores: { ...DONNEES.ignores, cle_future: 5, deja_en_cadence: 0 } },
    })
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    expect(await screen.findByText('cle_future : 5')).toBeInTheDocument()
    expect(screen.queryByText(/Déjà en cadence/)).not.toBeInTheDocument()
  })

  it("ACRM73 — l'exemple du contrat est cohérent : total = a_placer + ignorés, Σ par_etape = a_placer", () => {
    const somme = (valeurs) => valeurs.reduce((s, v) => s + v, 0)
    expect(DONNEES.total_candidats)
      .toBe(DONNEES.a_placer + somme(Object.values(DONNEES.ignores)))
    expect(somme(DONNEES.par_etape.map((e) => e.nombre))).toBe(DONNEES.a_placer)
  })

  it('« Appliquer » est désactivé avant tout aperçu, puis ouvre la confirmation et appelle l\'API avec apply=true, limite=40', async () => {
    render(<PlacementAnciensLeadsCard />)
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    // Le choix du volume (décision fondateur 07/09/2026) est proposé à UN lot
    // par défaut — jamais les 270 d'un coup dans la file de Meryem.
    expect(screen.getByLabelText('Nombre à placer')).toHaveValue(40)

    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    // Placement PARTIEL (40 sur 270) : la confirmation dit les deux nombres
    // et ne promet AUCUN décompte Froid (le moteur décide lead par lead —
    // un chiffre exact n'existe que sur un placement complet).
    const [options] = confirmMock.mock.calls[0]
    expect(options.description).toContain('40')
    expect(options.description).toContain(String(DONNEES.a_placer))
    expect(options.description).not.toContain('208')

    // Le premier lot est envoyé avec `limite: 40` (jamais un unique appel
    // sans borne — PERFORMANCE, incident du 07/09).
    await waitFor(() => expect(crmApi.placerAnciensLeads)
      .toHaveBeenCalledWith({ apply: true, limite: 40 }))
    await waitFor(() => expect(toast.success).toHaveBeenCalled())
  })

  it('placer TOUT (nombre = a_placer) garde la confirmation complète avec le décompte Froid', async () => {
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    fireEvent.change(screen.getByLabelText('Nombre à placer'), {
      target: { value: String(DONNEES.a_placer) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    // M = somme des codes dormant_* (150 + 58 = 208 sur le contrat).
    const [options] = confirmMock.mock.calls[0]
    expect(options.description).toContain(String(DONNEES.a_placer))
    expect(options.description).toContain('208')
  })

  it('« Appliquer » boucle par lots dans la limite du nombre choisi puis recharge l\'aperçu', async () => {
    crmApi.placerAnciensLeads
      .mockResolvedValueOnce(reponseContrat('crm', 'placement_anciens_leads')) // Aperçu initial
      .mockResolvedValueOnce({ data: { ...DONNEES, apply: true, applique: 40, restants: 230 } }) // lot 1
      .mockResolvedValueOnce({ data: { ...DONNEES, apply: true, applique: 10, restants: 220 } }) // lot 2
      .mockResolvedValueOnce(reponseContrat('crm', 'placement_anciens_leads')) // aperçu rechargé

    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    // Meryem/Reda choisit 50 : un lot plein de 40, puis un lot de 10 —
    // jamais un 3ᵉ lot même s'il reste 220 leads côté serveur.
    fireEvent.change(screen.getByLabelText('Nombre à placer'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())

    await waitFor(() => expect(crmApi.placerAnciensLeads.mock.calls.length).toBe(4))
    expect(crmApi.placerAnciensLeads.mock.calls[0][0]).toEqual({ apply: false })
    expect(crmApi.placerAnciensLeads.mock.calls[1][0]).toEqual({ apply: true, limite: 40 })
    expect(crmApi.placerAnciensLeads.mock.calls[2][0]).toEqual({ apply: true, limite: 10 })
    expect(crmApi.placerAnciensLeads.mock.calls[3][0]).toEqual({ apply: false })

    // Le toast final annonce le CUMUL des deux lots (40 + 10 = 50) ET les
    // restants côté serveur — deux chiffres lus sur la réponse.
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('50')))
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('220'))
  })

  it('un lot qui ne place plus personne arrête la boucle et affiche « Reprendre »', async () => {
    crmApi.placerAnciensLeads
      .mockResolvedValueOnce(reponseContrat('crm', 'placement_anciens_leads')) // Aperçu initial
      .mockResolvedValueOnce({ data: { ...DONNEES, apply: true, applique: 0, restants: 5 } })

    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())

    expect(await screen.findByRole('button', { name: 'Reprendre' })).toBeInTheDocument()
    // Une seule tentative : la boucle s'arrête dès qu'un lot ne place plus
    // personne, même s'il en reste (jamais un bouclage sans fin).
    expect(crmApi.placerAnciensLeads.mock.calls.filter(([body]) => body.apply === true)).toHaveLength(1)
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('Annuler la confirmation n\'appelle jamais l\'API avec apply=true', async () => {
    confirmMock.mockResolvedValueOnce(false)
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    expect(crmApi.placerAnciensLeads).not.toHaveBeenCalledWith({ apply: true })
  })

  it('aucun ancien lead à placer : message et repli, la carte se replie', async () => {
    crmApi.placerAnciensLeads.mockResolvedValue(
      reponseContrat('crm', 'placement_anciens_leads', 'exemple_vide'))
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    expect(await screen.findByText(/Aucun ancien lead à placer/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()
  })
})

/* Liste froide (fondateur, 17/11/2026) — la carte sœur, pour les leads au Froid :
   la commerciale PREND ses appels. Charges utiles = les exemples COMMITTÉS de
   `apps/crm/contract_samples/liste_froide.json` (PACT10) ; chaque chiffre de la
   carte vient du GET, jamais d'un recompte écran. */
describe('ListeFroideCard (liste froide, 17/11/2026)', () => {
  it('se tait quand le vivier est vide et qu’aucun appel n’est ouvert', async () => {
    crmApi.getListeFroide.mockResolvedValue(reponseContrat('crm', 'liste_froide', 'exemple_vide'))
    const { container } = render(<ListeFroideCard />)
    await waitFor(() => expect(crmApi.getListeFroide).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('se tait aussi quand la lecture échoue', async () => {
    crmApi.getListeFroide.mockRejectedValue(new Error('network'))
    const { container } = render(<ListeFroideCard />)
    await waitFor(() => expect(crmApi.getListeFroide).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('dit le vivier et les appels ouverts avec les chiffres du serveur', async () => {
    const etat = exempleContrat('crm', 'liste_froide', 'exemple_apercu')
    crmApi.getListeFroide.mockResolvedValue({ data: etat })
    render(<ListeFroideCard />)
    expect(await screen.findByTestId('liste-froide-vivier')).toHaveTextContent(
      `${etat.dossiers_chiffres} dossiers déjà chiffrés et ${etat.demandes_sans_reponse} `
      + 'demandes sans réponse attendent un appel.')
    expect(screen.getByTestId('liste-froide-ouverts'))
      .toHaveTextContent(`${etat.appels_ouverts} / ${etat.plafond_appels_ouverts}`)
    expect(screen.getByRole('button', { name: `Prendre ${etat.prise_max} dossiers` })).not.toBeDisabled()
  })

  it('bouton désactivé avec la raison du serveur quand la prise est refusée', async () => {
    const etat = exempleContrat('crm', 'liste_froide')
    crmApi.getListeFroide.mockResolvedValue({ data: etat })
    render(<ListeFroideCard />)
    const bouton = await screen.findByRole('button', { name: 'Prendre des dossiers' })
    expect(bouton).toBeDisabled()
    expect(bouton).toHaveAttribute('aria-describedby', 'liste-froide-motif')
    expect(screen.getByText(etat.raison)).toHaveAttribute('id', 'liste-froide-motif')
  })

  it('une prise réussie dit combien d’appels sont ajoutés et prévient la page', async () => {
    const etat = exempleContrat('crm', 'liste_froide', 'exemple_apercu')
    const prise = { ...exempleContrat('crm', 'liste_froide'), du_jour: true }
    crmApi.getListeFroide.mockResolvedValue({ data: etat })
    crmApi.prendreListeFroide.mockResolvedValue({ data: prise })
    const onPris = vi.fn()
    render(<ListeFroideCard onPris={onPris} />)
    fireEvent.click(await screen.findByRole('button', { name: `Prendre ${etat.prise_max} dossiers` }))
    expect(await screen.findByTestId('liste-froide-succes'))
      .toHaveTextContent(`${prise.nombre_places} appels ajoutés à vos étapes du jour.`)
    expect(crmApi.prendreListeFroide).toHaveBeenCalledWith(etat.prise_max)
    expect(onPris).toHaveBeenCalledWith(prise)
    // L'état servi par le POST remplace celui du GET (plafond atteint : bouton désactivé).
    expect(screen.getByRole('button', { name: 'Prendre des dossiers' })).toBeDisabled()
  })

  it('un refus du serveur s’affiche SOUS le bouton qui l’a causé', async () => {
    const etat = exempleContrat('crm', 'liste_froide', 'exemple_apercu')
    const refus = exempleContrat('crm', 'liste_froide', 'exemple_refus')
    crmApi.getListeFroide.mockResolvedValue({ data: etat })
    crmApi.prendreListeFroide.mockRejectedValue({ response: { status: 409, data: refus } })
    render(<ListeFroideCard />)
    fireEvent.click(await screen.findByRole('button', { name: `Prendre ${etat.prise_max} dossiers` }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(refus.detail)
    expect(alerte).toHaveAttribute('id', 'liste-froide-motif')
    expect(screen.getByRole('button', { name: `Prendre ${etat.prise_max} dossiers` }))
      .toHaveAttribute('aria-describedby', 'liste-froide-motif')
  })
})
