// VT10 — l'écran wizard affiche les manquants EXACTEMENT comme le serveur
// les liste (jamais une re-dérivation locale), la tuile « à refaire » montre
// le motif serveur, « Terminer » reste désactivé tant que la visite est
// incomplète, et le panneau devis n'affiche jamais `prix_achat`. Le fixture
// ci-dessous copie la forme du contrat committé
// `apps/crm/contract_samples/visite_terrain.json` (PACT10).
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const VISITE_INCOMPLETE = {
  id: 7, lead: 118, statut: 'en_cours', date_prevue: '2026-09-15', date_realisee: null,
  notes: '', modifiable: true, raison_lecture_seule: '',
  photo_toit: { assemblage_etat: 'aucun', assemblage_erreur: '', url: null, texture_calage: null },
  checklist: [
    {
      categorie: 'toiture', libelle: 'Toiture',
      slots: [
        {
          code: 'toiture_vue_generale', libelle: 'Vue générale du toit',
          guide: 'Cadrer tout le pan de toit utile.', requis: true, min_photos: 2, etat: 'ok',
          photos: [{ id: 31, url: '/media/toit-1.jpg', filename: 'toit-1.jpg', gps_lat: 33.5, gps_lng: -7.5, commentaire: '', a_refaire: false, motif_refaire: '' }],
        },
        {
          code: 'toiture_obstacles', libelle: 'Obstacles et ombrages',
          guide: 'Cheminées, antennes, arbres.', requis: true, min_photos: 1, etat: 'a_refaire',
          photos: [{ id: 32, url: '/media/obstacle-1.jpg', filename: 'obstacle-1.jpg', gps_lat: null, gps_lng: null, commentaire: '', a_refaire: true, motif_refaire: 'Photo floue — reprendre l’antenne côté est.' }],
        },
      ],
    },
    {
      categorie: 'tableau', libelle: 'Tableau électrique',
      slots: [{ code: 'tableau_ouvert', libelle: 'Tableau ouvert (disjoncteurs visibles)', guide: 'Capot ouvert.', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
    },
    {
      categorie: 'local_onduleur', libelle: 'Emplacement onduleur',
      slots: [{ code: 'onduleur_mur', libelle: 'Mur d’installation prévu', guide: '', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
    },
    {
      categorie: 'cheminement', libelle: 'Cheminement des câbles',
      slots: [{ code: 'cheminement_parcours', libelle: 'Parcours toit → onduleur', guide: '', requis: false, min_photos: 1, etat: 'manquant', photos: [] }],
    },
    {
      categorie: 'general', libelle: 'Général',
      slots: [{ code: 'general_facade', libelle: 'Façade du bâtiment', guide: '', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
    },
  ],
  mesures: {
    toiture: { longueur_m: 12.5, largeur_m: 8.0, pente_deg: 15.0, toit_plat: false, orientation: 'sud', type_couverture: 'tuile', etat_couverture: 'bon', obstacles_notes: '' },
    tableau: { calibre_disjoncteur_a: 63, type_alimentation: 'mono', emplacements_libres: 4 },
    local_onduleur: { largeur_mur_cm: null, hauteur_mur_cm: null, profondeur_degagement_cm: null, distance_tableau_m: null, local_abrite: null, local_ventile: null },
    cheminement: { longueur_estimee_m: null },
  },
  completude: {
    complet: false,
    manquants: [
      { type: 'photo', categorie: 'tableau', code: 'tableau_ouvert', libelle: 'Tableau ouvert (disjoncteurs visibles)' },
      { type: 'photo_a_refaire', categorie: 'toiture', code: 'toiture_obstacles', libelle: 'Obstacles et ombrages' },
      { type: 'mesure', categorie: 'local_onduleur', code: 'largeur_mur_cm', libelle: 'Largeur du mur libre (cm)' },
    ],
  },
  client_panel: {
    lead_nom: 'Client Démo', telephone: '+212600000000', whatsapp: '+212600000000',
    adresse: 'Quartier Démo, Bouskoura', ville: 'Bouskoura', gps_lat: 33.4589, gps_lng: -7.6528,
  },
  devis: [
    {
      id: 214, numero: 'DEV-202609-0012', statut: 'envoye', date: '2026-09-02', total_ttc: '84500.00',
      lignes: [{ designation: 'Panneau 550 Wc', quantite: '12.000', prix_unitaire_ttc: '1850.00', total_ttc: '22200.00' }],
    },
  ],
}

const { getVisite, terminerVisite } = vi.hoisted(() => ({
  getVisite: vi.fn(),
  terminerVisite: vi.fn(),
}))

vi.mock('../../api/visitesApi', () => ({
  default: {
    getVisite: (...a) => getVisite(...a),
    terminerVisite: (...a) => terminerVisite(...a),
    uploadVisitePhoto: vi.fn(),
    deleteVisitePhoto: vi.fn(),
    patchVisiteMesures: vi.fn(),
    // VTA11 — l'historique des visites du même lead (panneau en lecture seule
    // monté par le wizard). Liste vide ici : ces cas testent le wizard.
    getVisites: vi.fn(async () => ({ data: [] })),
  },
}))

import VisiteWizardPage from './VisiteWizardPage'

function withProviders() {
  return render(
    <MemoryRouter initialEntries={['/visites/7']}>
      <Routes>
        <Route path="/visites/:id" element={<VisiteWizardPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getVisite.mockResolvedValue({ data: VISITE_INCOMPLETE })
})

describe('VisiteWizardPage — VT10', () => {
  it('affiche les manquants EXACTEMENT comme le serveur les liste (mêmes libellés, jamais reformulés)', async () => {
    withProviders()
    const bloc = await screen.findByTestId('visite-manquants')
    expect(bloc).toHaveTextContent('Tableau ouvert (disjoncteurs visibles)')
    expect(bloc).toHaveTextContent('Obstacles et ombrages')
    expect(bloc).toHaveTextContent('Largeur du mur libre (cm)')
  })

  it('la tuile « à refaire » montre le motif serveur', async () => {
    withProviders()
    expect(await screen.findByText('Photo floue — reprendre l’antenne côté est.')).toBeInTheDocument()
  })

  it('« Terminer » reste désactivé tant que la visite est incomplète (completude.complet=false)', async () => {
    withProviders()
    const bouton = await screen.findByRole('button', { name: /il manque des éléments/i })
    expect(bouton).toBeDisabled()
    expect(terminerVisite).not.toHaveBeenCalled()
  })

  it('« Terminer » est activé quand completude.complet=true', async () => {
    getVisite.mockResolvedValue({
      data: { ...VISITE_INCOMPLETE, completude: { complet: true, manquants: [] } },
    })
    withProviders()
    const bouton = await screen.findByRole('button', { name: /terminer la visite/i })
    expect(bouton).not.toBeDisabled()
  })

  it('le panneau devis n’affiche jamais prix_achat (le serveur ne l’envoie pas, l’écran n’en ajoute pas)', async () => {
    withProviders()
    const panneau = await screen.findByTestId('visite-client-devis-panel')
    expect(panneau.textContent).not.toMatch(/prix.?achat/i)
    expect(panneau).toHaveTextContent('DEV-202609-0012')
  })

  it('le formulaire mesures : inputs numériques step="any" + form noValidate (aucun nombre tapé avalé/rejeté)', async () => {
    withProviders()
    await screen.findByTestId('visite-mesures-toiture')
    const input = screen.getByLabelText(/Longueur de la zone utile/i)
    expect(input).toHaveAttribute('step', 'any')
    expect(input.closest('form')).toHaveAttribute('novalidate')
  })

  it('affiche le panneau client (VT7) avec le lien WhatsApp et sans invention', async () => {
    withProviders()
    const panneau = await screen.findByTestId('visite-client-devis-panel')
    expect(panneau).toHaveTextContent('Client Démo')
    const wa = screen.getByRole('link', { name: /whatsapp/i })
    expect(wa).toHaveAttribute('href', 'https://wa.me/212600000000')
  })
})
