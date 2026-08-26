// TAILLES (fondateur 26/08/2026) — garde comportementale de l'écran vendeur
// Éco/Recommandé/Max. Complète DevisOffresTailles.test.mjs (source-pattern,
// même patron que DevisGeneratorRecalculerDimensionnement{,Guard}) : lui seul
// aurait intercepté un couplage réel entre cartes (un test purement
// source-pattern passe même si deux cartes partagent un état par erreur, tant
// que le texte attendu apparaît quelque part dans le fichier).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/ventesApi', () => ({
  default: {
    getOffresTaillesDevis: vi.fn(),
    patchOffreTailleConfig: vi.fn(),
    regenererOffreTaille: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import DevisOffresTailles from './DevisOffresTailles'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // Hors ConfirmProvider (rendu isolé, pas toute la page), useConfirm() replie
  // sur window.confirm — stub systématique en « oui » pour ne pas bloquer les
  // tests de régénération sur une boîte native jsdom.
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

// Fixture MIROIR du contrat (apps/ventes/contract_samples/offres_tailles.json,
// exemple principal) — deux tailles (Éco/Recommandé) suffisent pour prouver
// l'indépendance des cartes ; Max ajouté dans le test de régénération.
function offre(overrides) {
  return {
    cle: 'eco', titre: 'Éco', recommande: false, est_le_devis: false, ajuste: false,
    config: { nb_panneaux: 14, batterie_nb_modules: 0, batterie_module_kwh: 5.0 },
    sans: {
      nb_panneaux: 14, puissance_kwc: 7.7, prix_ttc: 71400.0,
      economie_annuelle_mad: 9840.0, payback_annees: 7.26, couverture_pct: 48.2,
      production_annuelle_kwh: 12180.0,
      materiel: [{ role: 'panneau', famille: 'panneau', marque: 'Longi', modele: 'Panneau 550 W' }],
      toit_ok: true,
    },
    avec: {
      nb_panneaux: 16, puissance_kwc: 8.8, prix_ttc: 96200.0,
      economie_annuelle_mad: 12360.0, payback_annees: 7.78, couverture_pct: 63.5,
      production_annuelle_kwh: 13920.0,
      batterie: { nb_modules: 2, module_kwh: 5.0, capacite_utile_kwh: 9.0, remplissage_ok: true },
      materiel: [
        { role: 'panneau', famille: 'panneau', marque: 'Longi', modele: 'Panneau 550 W' },
        { role: 'batterie', famille: 'batterie', marque: 'Deye', modele: 'Batterie 5 kWh LFP' },
      ],
      toit_ok: true,
    },
    ...overrides,
  }
}

const OFFRE_RECOMMANDE = offre({
  cle: 'recommande', titre: 'Recommandé', recommande: true, est_le_devis: true,
  config: { nb_panneaux: 22, batterie_nb_modules: 3, batterie_module_kwh: 5.0 },
  sans: {
    nb_panneaux: 22, puissance_kwc: 12.1, prix_ttc: 108900.0,
    economie_annuelle_mad: 13260.0, payback_annees: 8.21, couverture_pct: 61.0,
    production_annuelle_kwh: 19140.0,
    materiel: [{ role: 'panneau', famille: 'panneau', marque: 'Longi', modele: 'Panneau 550 W' }],
    toit_ok: true,
  },
  avec: {
    nb_panneaux: 22, puissance_kwc: 12.1, prix_ttc: 142700.0,
    economie_annuelle_mad: 17880.0, payback_annees: 7.98, couverture_pct: 79.4,
    production_annuelle_kwh: 19140.0,
    batterie: { nb_modules: 3, module_kwh: 5.0, capacite_utile_kwh: 13.5, remplissage_ok: true },
    materiel: [
      { role: 'panneau', famille: 'panneau', marque: 'Longi', modele: 'Panneau 550 W' },
      { role: 'batterie', famille: 'batterie', marque: 'Deye', modele: 'Batterie 5 kWh LFP' },
    ],
    toit_ok: true,
  },
})

const BLOC_DEUX_TAILLES = {
  editable: true,
  offres_tailles: {
    avec_servable: true,
    module_batterie_kwh: 5.0,
    offres: [offre(), OFFRE_RECOMMANDE],
  },
}

const PRODUITS = [
  { id: 41, nom: 'Panneau Longi 610W', marque: 'Longi', prix_vente: 1400, prix_achat: 1000 },
  { id: 205, nom: 'Batterie 10 kWh LFP', marque: 'Deye', prix_vente: 25000, prix_achat: 18000 },
]

function renderSection(props = {}) {
  return render(
    <DevisOffresTailles devisId={42} modeInstallation="residentiel" produits={PRODUITS} {...props} />,
  )
}

describe('DevisOffresTailles — garde-fous de montage', () => {
  it('ne rend rien sans devis enregistré (editId absent) — aucun appel réseau', () => {
    const { container } = render(
      <DevisOffresTailles devisId={null} modeInstallation="residentiel" produits={PRODUITS} />,
    )
    expect(container).toBeEmptyDOMElement()
    expect(ventesApi.getOffresTaillesDevis).not.toHaveBeenCalled()
  })

  it('ne rend rien hors marché résidentiel (agricole/industriel)', () => {
    const { container } = render(
      <DevisOffresTailles devisId={42} modeInstallation="agricole" produits={PRODUITS} />,
    )
    expect(container).toBeEmptyDOMElement()
    expect(ventesApi.getOffresTaillesDevis).not.toHaveBeenCalled()
  })

  it('affiche la raison en clair quand le devis n\'est pas dérivable (editable: false)', async () => {
    ventesApi.getOffresTaillesDevis.mockResolvedValue({
      data: { editable: false, raison_non_editable: 'Ce devis ne permet pas encore de dériver des tailles.' },
    })
    renderSection()
    await waitFor(() => screen.getByTestId('offres-tailles-non-editable'))
    expect(screen.getByTestId('offres-tailles-non-editable').textContent)
      .toMatch(/ne permet pas encore de dériver/)
    expect(screen.queryByTestId('offres-tailles-cartes')).toBeNull()
  })
})

describe('DevisOffresTailles — indépendance des cartes', () => {
  it('éditer la taille Éco laisse les chiffres de la taille Recommandé bit-à-bit inchangés à l\'écran', async () => {
    const user = userEvent.setup()
    ventesApi.getOffresTaillesDevis.mockResolvedValue({ data: BLOC_DEUX_TAILLES })
    renderSection()
    await waitFor(() => screen.getByTestId('offres-tailles-cartes'))

    const carteRecommandeAvant = screen.getByTestId('offre-taille-recommande').textContent

    // Réponse serveur réaliste : SEULE la taille 'eco' change (nb_panneaux
    // 14→15, prix recalculé), 'recommande' revient BIT-À-BIT identique —
    // exactement la garantie documentée par le contrat
    // (`_offres_tailles_reponse` : « les deux autres tailles ne sont pas
    // touchées »).
    const blocApresPatch = {
      editable: true,
      offres_tailles: {
        ...BLOC_DEUX_TAILLES.offres_tailles,
        offres: [
          offre({ config: { nb_panneaux: 15, batterie_nb_modules: 0, batterie_module_kwh: 5.0 },
            sans: { ...offre().sans, nb_panneaux: 15, prix_ttc: 76500.0 } }),
          OFFRE_RECOMMANDE,
        ],
      },
    }
    ventesApi.patchOffreTailleConfig.mockResolvedValue({ data: blocApresPatch })

    const carteEco = screen.getByTestId('offre-taille-eco')
    await user.click(within(within(carteEco).getByTestId('offre-taille-eco-stepper-panneaux'))
      .getByRole('button', { name: 'Panneaux : plus' }))
    await user.click(within(carteEco).getByTestId('offre-taille-eco-appliquer'))

    await waitFor(() => expect(ventesApi.patchOffreTailleConfig).toHaveBeenCalledTimes(1))
    expect(ventesApi.patchOffreTailleConfig).toHaveBeenCalledWith(42, 'eco', { nb_panneaux: 15 })

    await waitFor(() => {
      expect(within(screen.getByTestId('offre-taille-eco')).getByText(/76 500/)).toBeTruthy()
    })
    // La carte Recommandé n'a JAMAIS bougé : ni avant, ni après le PATCH sur Éco.
    expect(screen.getByTestId('offre-taille-recommande').textContent).toBe(carteRecommandeAvant)
  })

  it('régénérer une taille ne touche que sa propre carte', async () => {
    const user = userEvent.setup()
    const offreMax = offre({
      cle: 'max', titre: 'Max', ajuste: true,
      config: { nb_panneaux: 34, batterie_nb_modules: 6, batterie_module_kwh: 5.0 },
    })
    const blocInitial = {
      editable: true,
      offres_tailles: {
        avec_servable: true, module_batterie_kwh: 5.0,
        offres: [offre(), OFFRE_RECOMMANDE, offreMax],
      },
    }
    ventesApi.getOffresTaillesDevis.mockResolvedValue({ data: blocInitial })
    renderSection()
    await waitFor(() => screen.getByTestId('offres-tailles-cartes'))

    const carteEcoAvant = screen.getByTestId('offre-taille-eco').textContent
    const carteRecommandeAvant = screen.getByTestId('offre-taille-recommande').textContent
    expect(screen.getByTestId('offre-taille-max-ajuste')).toBeTruthy()

    const offreMaxRegeneree = offre({ cle: 'max', titre: 'Max', ajuste: false,
      config: { nb_panneaux: 30, batterie_nb_modules: 0, batterie_module_kwh: 5.0 } })
    ventesApi.regenererOffreTaille.mockResolvedValue({
      data: {
        editable: true,
        offres_tailles: { avec_servable: true, module_batterie_kwh: 5.0,
          offres: [offre(), OFFRE_RECOMMANDE, offreMaxRegeneree] },
      },
    })

    await user.click(within(screen.getByTestId('offre-taille-max')).getByTestId('offre-taille-max-regenerer'))
    await waitFor(() => expect(ventesApi.regenererOffreTaille).toHaveBeenCalledWith(42, 'max'))

    await waitFor(() => {
      expect(screen.queryByTestId('offre-taille-max-ajuste')).toBeNull()
    })
    expect(screen.getByTestId('offre-taille-eco').textContent).toBe(carteEcoAvant)
    expect(screen.getByTestId('offre-taille-recommande').textContent).toBe(carteRecommandeAvant)
  })
})

describe('DevisOffresTailles — refus serveur (zéro chiffre inventé)', () => {
  it('un PATCH refusé par le serveur affiche SON message, en français, sur la carte concernée', async () => {
    const user = userEvent.setup()
    ventesApi.getOffresTaillesDevis.mockResolvedValue({ data: BLOC_DEUX_TAILLES })
    renderSection()
    await waitFor(() => screen.getByTestId('offres-tailles-cartes'))

    // Forme RÉELLE d'un refus DRF sur ce endpoint (OffreTailleConfigSerializer) :
    // {config: {nb_panneaux: ['message FR']}} — le composant ne doit ni la
    // masquer, ni la reformuler, ni afficher du JSON brut.
    ventesApi.patchOffreTailleConfig.mockRejectedValue({
      response: {
        status: 400,
        data: { config: { nb_panneaux: ['Le nombre de panneaux dépasse la limite acceptée.'] } },
      },
    })

    const carteRecommande = screen.getByTestId('offre-taille-recommande')
    await user.click(within(within(carteRecommande).getByTestId('offre-taille-recommande-stepper-panneaux'))
      .getByRole('button', { name: 'Panneaux : plus' }))
    await user.click(within(carteRecommande).getByTestId('offre-taille-recommande-appliquer'))

    await waitFor(() => {
      expect(within(carteRecommande).getByText('Le nombre de panneaux dépasse la limite acceptée.')).toBeTruthy()
    })
    // Jamais de JSON brut affiché.
    expect(carteRecommande.textContent).not.toMatch(/[{[]"/)
  })
})

describe('DevisOffresTailles — mono-option (pas de batterie servable)', () => {
  it('sans avec_servable : aucune bascule, aucun stepper batterie, uniquement la colonne "sans"', async () => {
    ventesApi.getOffresTaillesDevis.mockResolvedValue({
      data: {
        editable: true,
        offres_tailles: {
          avec_servable: false,
          offres: [
            { cle: 'eco', titre: 'Éco', recommande: false, est_le_devis: false, ajuste: false,
              config: { nb_panneaux: 10 },
              sans: { nb_panneaux: 10, puissance_kwc: 5.5, prix_ttc: 52800.0,
                economie_annuelle_mad: 7080.0, payback_annees: 7.46,
                materiel: [{ role: 'panneau', famille: 'panneau' }] } },
            { cle: 'recommande', titre: 'Recommandé', recommande: true, est_le_devis: true, ajuste: false,
              config: { nb_panneaux: 14 },
              sans: { nb_panneaux: 14, puissance_kwc: 7.7, prix_ttc: 71400.0,
                economie_annuelle_mad: 9840.0, payback_annees: 7.26,
                materiel: [{ role: 'panneau', famille: 'panneau' }] } },
          ],
        },
      },
    })
    renderSection()
    await waitFor(() => screen.getByTestId('offres-tailles-cartes'))

    expect(screen.queryByTestId('offres-tailles-variante-switch')).toBeNull()
    expect(screen.queryByTestId('offre-taille-eco-stepper-batterie')).toBeNull()
    expect(screen.queryByTestId('offre-taille-recommande-stepper-batterie')).toBeNull()
    // Les prix affichés sont ceux de la variante 'sans' — jamais 'avec' (absente ici).
    expect(within(screen.getByTestId('offre-taille-eco')).getByText(/52 800/)).toBeTruthy()
    expect(within(screen.getByTestId('offre-taille-recommande')).getByText(/71 400/)).toBeTruthy()
  })
})
