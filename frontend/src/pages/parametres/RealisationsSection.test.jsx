import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

/* Onglet « Réalisations » (08/09/2026) : il se monte, liste le catalogue, et
   la création envoie EXACTEMENT les champs saisis — jamais `company` (forcée
   côté serveur), jamais une puissance ou un mois inventés quand ils sont
   laissés vides. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getRealisations: vi.fn(async () => ({
      data: [
        {
          id: 1,
          titre: 'Villa à Bouskoura',
          ville: 'Bouskoura',
          puissance_kwc: '6.60',
          mise_en_service: '2026-07-01',
          url_page: 'https://exemple.ma/realisations/villa-bouskoura/',
          lien_suivi: '',
          actif: true,
        },
        {
          id: 2,
          titre: 'Ferme à Mechraa Bel Ksiri',
          ville: 'Mechraa Bel Ksiri',
          puissance_kwc: null,
          mise_en_service: null,
          url_page: 'https://exemple.ma/realisations/ferme/',
          lien_suivi: '',
          actif: false,
        },
      ],
    })),
    createRealisation: vi.fn(async () => ({ data: {} })),
    updateRealisation: vi.fn(async () => ({ data: {} })),
    deleteRealisation: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import RealisationsSection from './RealisationsSection'
import contratRealisation from '../../../../backend/django_core/apps/parametres/contract_samples/realisation.json'

beforeEach(() => {
  parametresApi.getRealisations.mockClear()
  parametresApi.createRealisation.mockClear()
})
afterEach(() => cleanup())

const renderSection = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <RealisationsSection />
      </ThemeProvider>,
    )
  })
}

describe('RealisationsSection', () => {
  it('liste le catalogue de la société', async () => {
    await renderSection()
    await waitFor(() => expect(parametresApi.getRealisations).toHaveBeenCalled())
    expect(await screen.findByText('Villa à Bouskoura')).toBeInTheDocument()
    expect(screen.getByText('Ferme à Mechraa Bel Ksiri')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('affiche le mois en français et rien quand il est inconnu', async () => {
    await renderSection()
    await screen.findByText('Villa à Bouskoura')
    const liste = screen.getByTestId('realisations-liste')
    expect(within(liste).getByText(/juillet 2026/)).toBeInTheDocument()
    // La ligne sans mois ni puissance n'affiche que sa ville — aucun chiffre
    // par défaut ne vient boucher le trou, et surtout aucune autre date.
    expect(within(liste).getByText('Mechraa Bel Ksiri')).toBeInTheDocument()
    expect(within(liste).queryAllByText(/mise en service/)).toHaveLength(1)
    expect(within(liste).queryAllByText(/kWc/)).toHaveLength(1)
  })

  it('crée une réalisation avec les bons champs, sans company', async () => {
    await renderSection()
    await screen.findByText('Villa à Bouskoura')
    const form = screen.getByTestId('realisation-formulaire')
    fireEvent.change(within(form).getByLabelText('Titre'),
      { target: { value: 'Toiture à Settat' } })
    fireEvent.change(within(form).getByLabelText('Ville'),
      { target: { value: 'Settat' } })
    fireEvent.change(within(form).getByLabelText('Puissance en kWc'),
      { target: { value: '9.9' } })
    fireEvent.change(within(form).getByLabelText('Mois de mise en service'),
      { target: { value: '2026-05' } })
    fireEvent.change(within(form).getByLabelText('Lien de la page publique'),
      { target: { value: 'https://exemple.ma/realisations/toiture-settat/' } })
    fireEvent.click(within(form).getByRole('button', { name: /Ajouter la réalisation/ }))
    await waitFor(() =>
      expect(parametresApi.createRealisation).toHaveBeenCalledWith({
        titre: 'Toiture à Settat',
        ville: 'Settat',
        url_page: 'https://exemple.ma/realisations/toiture-settat/',
        lien_suivi: '',
        puissance_kwc: '9.9',
        mise_en_service: '2026-05-01',
      }))
    expect(Object.keys(parametresApi.createRealisation.mock.calls[0][0]))
      .not.toContain('company')
  })

  it('AGR515 — segment : rien de pré-coché, et créer avec « Agricole » l\'envoie', async () => {
    await renderSection()
    await screen.findByText('Villa à Bouskoura')
    const form = screen.getByTestId('realisation-formulaire')
    const choix = within(form).getByLabelText('Segment')
    expect(choix).toHaveValue('')
    expect(within(form).getByText(/ne sert de preuve qu'aux leads agricoles/))
      .toBeInTheDocument()
    fireEvent.change(within(form).getByLabelText('Titre'),
      { target: { value: 'Pompage à Berkane' } })
    fireEvent.change(within(form).getByLabelText('Ville'),
      { target: { value: 'Berkane' } })
    fireEvent.change(within(form).getByLabelText('Lien de la page publique'),
      { target: { value: 'https://exemple.ma/realisations/pompage-berkane/' } })
    fireEvent.change(choix, { target: { value: 'agricole' } })
    fireEvent.click(within(form).getByRole('button', { name: /Ajouter la réalisation/ }))
    await waitFor(() => expect(parametresApi.createRealisation).toHaveBeenCalled())
    expect(parametresApi.createRealisation.mock.calls[0][0].segment).toBe('agricole')
  })

  it('AGR515 — sans segment choisi, la création n\'envoie pas la clé segment', async () => {
    await renderSection()
    await screen.findByText('Villa à Bouskoura')
    const form = screen.getByTestId('realisation-formulaire')
    fireEvent.change(within(form).getByLabelText('Titre'), { target: { value: 'Hangar' } })
    fireEvent.change(within(form).getByLabelText('Ville'), { target: { value: 'Berrechid' } })
    fireEvent.change(within(form).getByLabelText('Lien de la page publique'),
      { target: { value: 'https://exemple.ma/realisations/hangar/' } })
    fireEvent.click(within(form).getByRole('button', { name: /Ajouter la réalisation/ }))
    await waitFor(() => expect(parametresApi.createRealisation).toHaveBeenCalled())
    expect(parametresApi.createRealisation.mock.calls[0][0]).not.toHaveProperty('segment')
  })

  it('AGR515 — choisir Agricole, rouvrir, ne rien toucher : même segment, aucun envoi', async () => {
    // Le « serveur » est l'échantillon de contrat, jamais un mock écrit à la main.
    let serveur = JSON.parse(JSON.stringify(contratRealisation.exemple_liste))
    parametresApi.getRealisations.mockImplementation(
      async () => ({ data: JSON.parse(JSON.stringify(serveur)) }))
    parametresApi.updateRealisation.mockImplementation(async (id, patch) => {
      serveur = serveur.map(r => (r.id === id ? { ...r, ...patch } : r))
      return { data: serveur.find(r => r.id === id) }
    })
    const premiere = render(<ThemeProvider><RealisationsSection /></ThemeProvider>)
    const ligne = await screen.findByLabelText('Segment de Ferme à Mechraa Bel Ksiri')
    expect(ligne).toHaveValue('')
    fireEvent.change(ligne, { target: { value: 'agricole' } })
    await waitFor(() => expect(parametresApi.updateRealisation)
      .toHaveBeenCalledWith(13, { segment: 'agricole' }))
    const apres = JSON.parse(JSON.stringify(serveur))
    premiere.unmount()
    parametresApi.updateRealisation.mockClear()
    render(<ThemeProvider><RealisationsSection /></ThemeProvider>)
    await waitFor(() => expect(
      screen.getByLabelText('Segment de Ferme à Mechraa Bel Ksiri'),
    ).toHaveValue('agricole'))
    expect(parametresApi.updateRealisation).not.toHaveBeenCalled()
    expect(serveur).toEqual(apres)
    expect(serveur[0].segment).toBe('residentiel')
  })

  it('n envoie ni puissance ni mois quand ils sont laissés vides', async () => {
    await renderSection()
    await screen.findByText('Villa à Bouskoura')
    const form = screen.getByTestId('realisation-formulaire')
    fireEvent.change(within(form).getByLabelText('Titre'),
      { target: { value: 'Hangar' } })
    fireEvent.change(within(form).getByLabelText('Ville'),
      { target: { value: 'Berrechid' } })
    fireEvent.change(within(form).getByLabelText('Lien de la page publique'),
      { target: { value: 'https://exemple.ma/realisations/hangar/' } })
    fireEvent.click(within(form).getByRole('button', { name: /Ajouter la réalisation/ }))
    await waitFor(() => expect(parametresApi.createRealisation).toHaveBeenCalled())
    const envoye = parametresApi.createRealisation.mock.calls[0][0]
    expect(envoye).not.toHaveProperty('puissance_kwc')
    expect(envoye).not.toHaveProperty('mise_en_service')
  })
})
