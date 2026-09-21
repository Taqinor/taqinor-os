import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL35 — la liste `/calepinage`, prouvée sur les VRAIS filtres.
   ----------------------------------------------------------------------------
   Deux invariants, exactement ceux du « Done » de la tâche :
     1. CHAQUE filtre déclenche l'appel serveur correspondant — la leçon PV22
        est qu'un filtre ignoré fait ouvrir le mauvais objet ;
     2. une vignette SANS image rend le repli, jamais une balise cassée.

   Les lignes viennent de l'échantillon de contrat committé
   (`apps/calepinage/contract_samples/calepinage_detail.json`, PACT10) et non
   d'un PAYLOAD écrit à la main : un mock maison est une DEUXIÈME source de
   vérité, et c'est elle qui a fait passer l'écran AO Tableau de bord en
   production le 03/08/2026 avec zéro clé sur six concordante.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  getLeads: vi.fn(),
  searchClients: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { list: mocks.list } },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getLeads: mocks.getLeads, searchClients: mocks.searchClients },
}))

import CalepinageList from './CalepinageList'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// L'exemple du contrat = un calepinage AVEC aperçu ; `exemple_vide` = un
// calepinage neuf dont `image.url` vaut `null` (et non `0`, ni clé absente).
const AVEC_IMAGE = exempleContrat('calepinage', 'calepinage_detail')
const SANS_IMAGE = exempleContrat('calepinage', 'calepinage_detail', 'exemple_vide')

const rendre = () => render(
  <MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>,
)

const derniersParams = () => mocks.list.mock.calls.at(-1)?.[0] ?? {}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: { count: 2, next: null, previous: null, results: [AVEC_IMAGE, SANS_IMAGE] },
  })
  mocks.getLeads.mockResolvedValue({ data: [] })
  mocks.searchClients.mockResolvedValue({ data: [] })
})

describe('CalepinageList (CAL35)', () => {
  it('charge la liste au montage, SANS filtre inventé', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(derniersParams()).toEqual({})
  })

  it('rend une vignette par calepinage, avec sa référence', async () => {
    rendre()
    expect(await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)).toBeInTheDocument()
    expect(screen.getByTestId(`cal-vignette-${SANS_IMAGE.id}`)).toBeInTheDocument()
    // La référence et le rattachement vivent dans la même ligne de texte :
    // on interroge la vignette, pas un nœud de texte isolé.
    expect(screen.getByTestId(`cal-vignette-${AVEC_IMAGE.id}`))
      .toHaveTextContent(AVEC_IMAGE.reference)
  })

  it('une vignette SANS image rend le repli — jamais une balise cassée', async () => {
    rendre()
    await screen.findByTestId(`cal-vignette-${SANS_IMAGE.id}`)

    // Le calepinage neuf du contrat a `image.url === null` : aucune `<img>` ne
    // doit être émise pour lui (une `src` vide affiche l'icône cassée).
    expect(SANS_IMAGE.image.url).toBeNull()
    expect(screen.getByTestId('cal-vignette-sans-image')).toBeInTheDocument()
    const images = screen.getAllByTestId('cal-vignette-image')
    expect(images).toHaveLength(1)
    expect(images[0]).toHaveAttribute('src', AVEC_IMAGE.image.url)
    for (const img of document.querySelectorAll('img')) {
      expect(img.getAttribute('src')).toBeTruthy()
    }
  })

  it('la vignette mène à l’atelier du calepinage', async () => {
    rendre()
    const vignette = await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    expect(vignette).toHaveAttribute('href', `/calepinage/${AVEC_IMAGE.id}`)
  })

  it('la RECHERCHE part en `?q=` — le filtre servi par CAL16', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Recherche'), { target: { value: 'toiture' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'toiture' }))
  })

  it('la DATE part en `?depuis=`', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Modifié depuis le'), { target: { value: '2026-09-01' } })
    await waitFor(() => expect(derniersParams()).toEqual({ depuis: '2026-09-01' }))
  })

  it('les filtres se CUMULENT dans une seule requête', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Recherche'), { target: { value: 'hangar' } })
    fireEvent.change(screen.getByLabelText('Modifié depuis le'), { target: { value: '2026-09-10' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'hangar', depuis: '2026-09-10' }))
  })

  it('un filtre VIDÉ disparaît de la requête (jamais `?q=` vide)', async () => {
    rendre()
    const champ = screen.getByLabelText('Recherche')
    fireEvent.change(champ, { target: { value: 'hangar' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'hangar' }))
    fireEvent.change(champ, { target: { value: '' } })
    await waitFor(() => expect(derniersParams()).toEqual({}))
  })

  it('le filtre LEAD cherche CÔTÉ SERVEUR (bornage société), jamais dans une liste locale', async () => {
    mocks.getLeads.mockResolvedValue({ data: [{ id: 4, nom: 'Lead d’essai', ville: 'Casablanca' }] })
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('combobox', { name: 'Lead' }))
    // Une liste pré-chargée côté écran ne peut pas être bornée société : la
    // recherche DOIT partir au serveur.
    await waitFor(() => expect(mocks.getLeads).toHaveBeenCalled())
    expect(await screen.findByText('Lead d’essai')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Lead d’essai'))
    await waitFor(() => expect(derniersParams()).toEqual({ lead: '4' }))
  })

  it('le filtre CLIENT cherche CÔTÉ SERVEUR et part en `?client=`', async () => {
    mocks.searchClients.mockResolvedValue({ data: [{ id: 9, nom: 'Client d’essai' }] })
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('combobox', { name: 'Client' }))
    await waitFor(() => expect(mocks.searchClients).toHaveBeenCalled())
    fireEvent.click(await screen.findByText('Client d’essai'))
    await waitFor(() => expect(derniersParams()).toEqual({ client: '9' }))
  })

  it('les options de STATUT sont celles des lignes reçues — aucune liste recopiée', async () => {
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    // Le libellé affiché est TOUJOURS celui du serveur (`statut_libelle`).
    expect(screen.getByText(AVEC_IMAGE.statut_libelle)).toBeInTheDocument()
    expect(screen.getByText(SANS_IMAGE.statut_libelle)).toBeInTheDocument()
  })

  it('état vide : il EXPLIQUE le geste de création', async () => {
    mocks.list.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } })
    rendre()
    expect(await screen.findByText(/Aucun calepinage pour l’instant/)).toBeInTheDocument()
    expect(screen.getByText(/part d’un lead ou d’un client/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Créer un calepinage/ }))
    expect(mocks.navigate).toHaveBeenCalledWith('/calepinage/nouveau')
  })

  it('état vide SOUS FILTRE : il propose de réinitialiser, pas de créer', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    mocks.list.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } })
    fireEvent.change(screen.getByLabelText('Recherche'), { target: { value: 'introuvable' } })
    expect(await screen.findByText(/Aucun calepinage ne correspond à ces filtres/)).toBeInTheDocument()
  })

  it('la PAGINATION suit le serveur : « Suivant » n’est actif que s’il y a une page suivante', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 3, next: 'http://x/?page=2', previous: null, results: [AVEC_IMAGE] },
    })
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    const suivant = screen.getByRole('button', { name: 'Suivant' })
    expect(suivant).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled()
    fireEvent.click(suivant)
    await waitFor(() => expect(derniersParams()).toEqual({ page: 2 }))
  })

  it('changer un filtre REVIENT à la page 1 (sinon la page 3 d’une autre liste s’affiche vide)', async () => {
    mocks.list.mockResolvedValue({
      data: { count: 9, next: 'http://x/?page=2', previous: null, results: [AVEC_IMAGE] },
    })
    rendre()
    await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(derniersParams()).toEqual({ page: 2 }))
    fireEvent.change(screen.getByLabelText('Recherche'), { target: { value: 'toit' } })
    await waitFor(() => expect(derniersParams()).toEqual({ q: 'toit' }))
  })

  it('une erreur serveur s’affiche telle quelle, jamais un texte fabriqué', async () => {
    mocks.list.mockRejectedValue({ response: { data: { detail: 'Accès refusé à ce module.' } } })
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent('Accès refusé à ce module.')
  })

  // CALX32 — le sélecteur de tri, limité aux 4 champs de `ordering_fields`
  // (`views/calepinages.py:173-174`) : created_at, updated_at, statut, titre.
  describe('CALX32 — le tri', () => {
    it('le sélecteur ne propose QUE les 4 champs réellement servis', async () => {
      rendre()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getByRole('combobox', { name: 'Tri' }))
      await screen.findByRole('listbox')
      for (const libelle of ['Date de création', 'Date de modification', 'Statut', 'Titre']) {
        expect(screen.getByRole('option', { name: libelle })).toBeInTheDocument()
      }
      // Rien d'autre n'est inventé : ces 4 + le repli « Tri par défaut ».
      expect(screen.getAllByRole('option')).toHaveLength(5)
    })

    it('changer le tri relance la requête avec `ordering=` et remet la page à 1', async () => {
      mocks.list.mockResolvedValue({
        data: { count: 9, next: 'http://x/?page=2', previous: null, results: [AVEC_IMAGE] },
      })
      rendre()
      await screen.findByTestId(`cal-vignette-${AVEC_IMAGE.id}`)
      fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
      await waitFor(() => expect(derniersParams()).toEqual({ page: 2 }))

      fireEvent.click(screen.getByRole('combobox', { name: 'Tri' }))
      fireEvent.click(await screen.findByRole('option', { name: 'Titre' }))
      // `ordering=` part, et la page est revenue à 1 (absente des params).
      await waitFor(() => expect(derniersParams()).toEqual({ ordering: 'titre' }))
    })

    it('le sens croissant/décroissant inverse le préfixe `-` de `ordering=`', async () => {
      rendre()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getByRole('combobox', { name: 'Tri' }))
      fireEvent.click(await screen.findByRole('option', { name: 'Statut' }))
      await waitFor(() => expect(derniersParams()).toEqual({ ordering: 'statut' }))

      fireEvent.click(screen.getByRole('combobox', { name: 'Ordre' }))
      fireEvent.click(await screen.findByRole('option', { name: 'Décroissant' }))
      await waitFor(() => expect(derniersParams()).toEqual({ ordering: '-statut' }))
    })
  })
})
