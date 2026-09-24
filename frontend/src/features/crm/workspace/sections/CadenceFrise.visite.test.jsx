// VISCAD1 — « la visite technique devient une étape du suivi commercial » :
// la frise MÊLE désormais les touches de relance ET les visites techniques
// dans une seule chronologie. FIXED API CONTRACT (backend construit en
// parallèle sur EXACTEMENT cette forme) :
//   GET /api/django/crm/leads/<id>/visites/
//   -> {visites: [{id, statut, statut_libelle, date_prevue, date_realisee,
//                  commercial_nom, notes, retour_disponible}, ...]}
import {
  describe, it, expect, vi, beforeEach, afterEach,
} from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results

vi.mock('../../../../api/crmApi', () => ({
  default: {
    getRelanceEtapesLead: vi.fn(),
    getLeadVisites: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))
vi.mock('../../../../lib/toast', () => ({ toastError: vi.fn() }))

import crmApi from '../../../../api/crmApi'
import CadenceFrise from './CadenceFrise'

// Les deux touches du contrat committé : id412 due 2026-09-05T13:00Z (à
// faire, en retard), id418 due 2026-09-06T09:33Z (à faire) — VOIR
// `relance_etape_v2.json` (l'ordre exact des deux résultats importe pour
// « prochaine touche »).
beforeEach(() => {
  crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: ETAPES.length, results: ETAPES } })
  crmApi.getLeadVisites.mockResolvedValue({ data: { visites: [] } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

// VISCAD6-B (E4, fondateur 24/09/2026) — le lien « Ouvrir le retour » (vers
// `/visites/:id`) exige le contexte Router (`react-router-dom` `<Link>`,
// invariant "useHref() may be used only in the context of a <Router>") : TOUS
// les rendus de la frise en ont désormais besoin, pas seulement celui qui
// affiche un retour disponible — un `<MemoryRouter>` neutre ne change rien
// aux assertions existantes.
function renderFrise(props = {}) {
  return render(<CadenceFrise leadId={1489} {...props} />, { wrapper: MemoryRouter })
}

describe('VISCAD1 CadenceFrise — visites mêlées à la frise', () => {
  it('une visite se positionne CHRONOLOGIQUEMENT parmi les touches (jamais après, même si servie après)', async () => {
    crmApi.getLeadVisites.mockResolvedValue({
      data: {
        visites: [{
          id: 90, statut: 'brouillon', statut_libelle: 'Planifiée',
          // Antérieure aux deux touches du contrat (2026-09-05/06) : doit
          // apparaître EN PREMIER dans la frise.
          date_prevue: '2026-09-01', date_realisee: null,
          commercial_nom: 'Karim', notes: '', retour_disponible: false,
        }],
      },
    })
    renderFrise()
    // Attend les DEUX chargements (touches ET visites — deux effets
    // indépendants) avant de lire l'ordre final, jamais une lecture qui
    // devancerait le second fetch.
    await screen.findByText(/Visite technique/)
    await waitFor(() => expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2))
    const ol = screen.getByTestId('cadence-frise')
    const ordre = Array.from(
      ol.querySelectorAll('[data-testid="cadence-frise-etape"], [data-testid="cadence-frise-visite"]'),
    ).map((el) => el.getAttribute('data-testid'))
    expect(ordre).toEqual(['cadence-frise-visite', 'cadence-frise-etape', 'cadence-frise-etape'])
    expect(screen.getByText(/Visite technique/)).toBeInTheDocument()
  })

  it('statut chip : le libellé SERVEUR (statut_libelle) est affiché, jamais réinventé', async () => {
    crmApi.getLeadVisites.mockResolvedValue({
      data: {
        visites: [{
          id: 91, statut: 'en_cours', statut_libelle: 'En cours',
          date_prevue: '2026-09-01', commercial_nom: '', notes: '', retour_disponible: false,
        }],
      },
    })
    renderFrise()
    expect(await screen.findByText('En cours')).toBeInTheDocument()
  })

  it('retour terrain disponible : affiché SEULEMENT quand le serveur le signale, avec l\'extrait de notes', async () => {
    crmApi.getLeadVisites.mockResolvedValue({
      data: {
        visites: [{
          id: 92, statut: 'validee', statut_libelle: 'Validée',
          date_prevue: '2026-09-01', commercial_nom: 'Commercial Terrain',
          notes: 'Toiture terrasse, aucune ombre.', retour_disponible: true,
        }],
      },
    })
    renderFrise()
    expect(await screen.findByText(/Retour terrain disponible/)).toBeInTheDocument()
    expect(screen.getByText(/Toiture terrasse, aucune ombre\./)).toBeInTheDocument()
    // VISCAD6-B (E4, fondateur 24/09/2026) — le texte n'est plus inerte : un
    // lien ouvre l'écran Visites (même route que `VisiteTab.jsx`).
    expect(screen.getByRole('link', { name: 'Ouvrir le retour' })).toHaveAttribute('href', '/visites/92')
  })

  it('une visite SANS retour_disponible ne montre AUCUNE mention "retour terrain" ni le lien "Ouvrir le retour"', async () => {
    crmApi.getLeadVisites.mockResolvedValue({
      data: {
        visites: [{
          id: 93, statut: 'brouillon', statut_libelle: 'Planifiée',
          date_prevue: '2026-09-01', commercial_nom: '', notes: '', retour_disponible: false,
        }],
      },
    })
    renderFrise()
    await screen.findByText(/Visite technique/)
    expect(screen.queryByText(/Retour terrain disponible/)).toBeNull()
    expect(screen.queryByRole('link', { name: 'Ouvrir le retour' })).not.toBeInTheDocument()
  })

  it('échec du chargement des visites : la frise des touches reste INCHANGÉE (aucun plantage, jamais un message d\'erreur pour les visites)', async () => {
    crmApi.getLeadVisites.mockRejectedValue(new Error('boom'))
    renderFrise()
    expect(await screen.findByText(ETAPES[0].libelle)).toBeInTheDocument()
    expect(screen.getByText(ETAPES[1].libelle)).toBeInTheDocument()
    expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2)
    expect(screen.queryByTestId('cadence-frise-visite')).toBeNull()
    expect(screen.queryByText(/Frise de cadence indisponible/)).toBeNull()
  })

  it('crmApi.getLeadVisites absente du mock (suites existantes non mises à jour) : repli identique, jamais un plantage', async () => {
    // Simule les mocks crmApi PARTIELS des suites existantes
    // (SectionPipeline.relance.test.jsx, LeadWorkspace*.test.jsx…) qui ne
    // connaissent pas encore `getLeadVisites` — la garde défensive de
    // CadenceFrise.jsx doit rendre la frise À L'IDENTIQUE, jamais une
    // TypeError.
    const original = crmApi.getLeadVisites
    delete crmApi.getLeadVisites
    renderFrise()
    expect(await screen.findByText(ETAPES[0].libelle)).toBeInTheDocument()
    expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2)
    crmApi.getLeadVisites = original
  })

  it('une visite terminée/validée SANS retour disponible se replie avec l\'historique', async () => {
    // Avec un retour terrain disponible, la visite reste VISIBLE même
    // terminée/validée (c'est l'info que le closing lit avant de rappeler —
    // testé plus haut) ; seul le cas SANS retour suit le repli de
    // l'historique.
    crmApi.getLeadVisites.mockResolvedValue({
      data: {
        visites: [{
          id: 94, statut: 'validee', statut_libelle: 'Validée',
          date_prevue: '2026-09-01', commercial_nom: '', notes: '', retour_disponible: false,
        }],
      },
    })
    renderFrise()
    await waitFor(() => expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2))
    // Repliée par défaut : ni la ligne visite, ni son texte ne sont visibles
    // avant d'ouvrir l'historique.
    expect(screen.queryByTestId('cadence-frise-visite')).toBeNull()
    const toggle = screen.getByRole('button', { name: /touche\(s\) passée\(s\)/ })
    toggle.click()
    expect(await screen.findByTestId('cadence-frise-visite')).toBeInTheDocument()
  })
})
