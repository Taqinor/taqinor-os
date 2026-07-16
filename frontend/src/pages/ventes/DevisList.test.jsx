import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within, act, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

// J141 — la liste des devis ne doit toucher aucun réseau pendant le test : on
// neutralise le thunk de chargement (le composant le dispatche au montage).
// QG1 — genererPdfDevis renvoie une action « thunk-like » : dispatch(...) doit
// rester chaînable en .unwrap() (comme le vrai createAsyncThunk) pour que
// genererUnPdf() poursuive jusqu'au polling dans le test dédié plus bas.
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
    genererPdfDevis: () => {
      const action = { type: 'ventes/genererPdfDevis/noop' }
      action.unwrap = () => Promise.resolve()
      return action
    },
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
})

// WR1 — espionne l'appel réseau du refus dédié (jamais un PATCH statut direct).
// QG1 — espionne getDevisById (polling) + telechargerPdfDevis (ouverture auto).
// QG10 — getVarianteConfig (pré-remplit le %) + dupliquerVariante (création).
// WR2 — shareLinkDevis (« Copier le lien proposition »).
// QX22 — whatsappPreviewDevis (aperçu lecture seule) + whatsappDevis (envoi réel).
vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      refuserDevis: vi.fn(() => Promise.resolve({ data: { statut: 'refuse' } })),
      getDevisById: vi.fn(() => Promise.resolve({ data: { fichier_pdf: '/media/devis/DEV-PDF-AUTO.pdf' } })),
      telechargerPdfDevis: vi.fn(() => Promise.resolve({
        data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: {},
      })),
      getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '25.00' } })),
      dupliquerVariante: vi.fn(() => Promise.resolve({ data: [] })),
      shareLinkDevis: vi.fn(() => Promise.resolve({ data: { token: 'tok123', path: '/proposition/tok123' } })),
      whatsappPreviewDevis: vi.fn(() => Promise.resolve({ data: { wa_url: 'https://wa.me/212600000000', message: 'Bonjour' } })),
      whatsappDevis: vi.fn(() => Promise.resolve({ data: { statut: 'envoye' } })),
      // VX216(a) — « Réviser (nouvelle version) », mocké pour ne jamais
      // toucher le réseau réel dans le test du toast.warning associé.
      reviserDevis: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})

// QX26 — motifs de perte (taxonomie CRM, endpoint company-scoped existant).
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getMotifsPerte: vi.fn(() => Promise.resolve({
        data: [{ id: 5, nom: 'Trop cher' }, { id: 6, nom: 'Choisi un concurrent' }],
      })),
    },
  }
})

import DevisList from './DevisList'
import ventesApi from '../../api/ventesApi'
import crmApi from '../../api/crmApi'
import { toast } from '../../ui'
// ARC49 — DevisList rend désormais son tableau via le moteur `ui/datatable`, qui
// lit la densité via useDensity() et EXIGE donc un <ThemeProvider> dans l'arbre
// (comme en production, où <Layout> l'enveloppe). Ajout de wrapper de HARNAIS
// uniquement — aucune assertion n'est modifiée.
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// Réducteurs minimaux : seules les tranches lues par l'écran (ventes + auth).
// QG10 — l'écran lit aussi auth.role_nom + auth.permissions (useHasPermission).
function makeStore({
  devis = [], loading = false, error = null, role = 'admin',
  role_nom = 'Directeur', permissions = [],
} = {}) {
  return configureStore({
    reducer: {
      ventes: (state = { devis, loading, error }) => state,
      auth: (state = { role, role_nom, permissions }) => state,
    },
  })
}

function renderList(opts, initialEntries = ['/ventes/devis']) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={initialEntries}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('DevisList — états de chargement (J141)', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers() })

  it('garde l\'en-tête « Devis » visible pendant le chargement (pas de spinner plein écran)', () => {
    renderList({ loading: true })
    // L'en-tête de page reste présent — la mise en page ne saute pas au retour des données.
    expect(screen.getByRole('heading', { name: 'Devis' })).toBeVisible()
  })

  it('affiche un squelette de tableau (et non les vraies lignes) après le seuil', () => {
    renderList({ loading: true })
    // useDelayedLoading bascule sur le squelette à 500 ms (act() flush React).
    act(() => { vi.advanceTimersByTime(600) })
    const table = document.querySelector('table.data-table')
    expect(table).not.toBeNull()
    // Des cellules squelette sont rendues (placeholders animés), aucune vraie référence.
    // VX132 — le pulse Tailwind a été remplacé par le balayage CSS `.skeleton-shimmer`.
    expect(table.querySelector('.skeleton-shimmer, [class*="skeleton-shimmer"]')).not.toBeNull()
  })
})

describe('DevisList — rendu des données (J141)', () => {
  it('rend les vraies lignes avec une pastille de statut quand le chargement est terminé', () => {
    renderList({
      loading: false,
      devis: [{
        id: 1, reference: 'DEV-2026-07-0001', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 12000, nb_options: 1, version: 1,
      }],
    })
    const cell = screen.getByText('DEV-2026-07-0001')
    expect(cell).toBeVisible()
    // La pastille de statut (StatusPill) restitue le libellé français dans la
    // ligne du tableau (le libellé apparaît aussi dans les cartes de résumé).
    const row = cell.closest('tr')
    expect(within(row).getByText('Envoyé')).toBeVisible()
  })
})

describe('DevisList — U5 : factures + bon de commande générés', () => {
  it('affiche des chips facture (réf + statut) et bon de commande dans la ligne', () => {
    renderList({
      loading: false,
      devis: [{
        id: 7, reference: 'DEV-2026-07-0007', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 50000, nb_options: 1, version: 1,
        factures_liees: [
          { id: 11, reference: 'FAC-2026-07-0011', statut: 'emise', statut_display: 'Émise', type_facture: 'acompte' },
        ],
        bon_commande_etat: { exists: true, id: 5, reference: 'BC-2026-07-0005', statut: 'confirme', statut_display: 'Confirmé', mismatch: false },
      }],
    })
    const row = screen.getByText('DEV-2026-07-0007').closest('tr')
    // La facture liée apparaît avec sa référence et son libellé de statut.
    expect(within(row).getByText(/FAC-2026-07-0011/)).toBeVisible()
    expect(within(row).getByText(/Émise/)).toBeVisible()
    // Le bon de commande lié apparaît aussi.
    expect(within(row).getByText('BC-2026-07-0005')).toBeVisible()
  })

  it('n\'affiche aucune chip document quand le devis n\'a ni facture ni BC', () => {
    renderList({
      loading: false,
      devis: [{
        id: 8, reference: 'DEV-2026-07-0008', client_nom: 'ACME', statut: 'brouillon',
        date_creation: '2026-07-01', total_ttc: 1000, nb_options: 1, version: 1,
        factures_liees: [], bon_commande_etat: { exists: false, mismatch: false },
      }],
    })
    const row = screen.getByText('DEV-2026-07-0008').closest('tr')
    expect(within(row).queryByText(/FAC-/)).toBeNull()
    expect(within(row).queryByText(/^BC-/)).toBeNull()
  })
})

describe('DevisList — U7 : révisions remplacées masquées par défaut', () => {
  const data = () => ([
    {
      id: 1, reference: 'DEV-V1', client_nom: 'ACME', statut: 'envoye',
      date_creation: '2026-07-01', total_ttc: 1000, nb_options: 1, version: 1,
      is_active: false, superseded_by_ref: 'DEV-V2',
    },
    {
      id: 2, reference: 'DEV-V2', client_nom: 'ACME', statut: 'envoye',
      date_creation: '2026-07-02', total_ttc: 1200, nb_options: 1, version: 2,
      is_active: true, version_parent_ref: 'DEV-V1',
    },
  ])

  it('masque la révision remplacée (is_active=false) par défaut', () => {
    renderList({ loading: false, devis: data() })
    // La version courante est visible…
    expect(screen.getByText('DEV-V2')).toBeVisible()
    // …mais la version remplacée n'apparaît pas comme une ligne « vivante ».
    expect(screen.queryByText('DEV-V1')).toBeNull()
  })

  it('réaffiche la révision remplacée, badgée « Remplacé », via la bascule', () => {
    renderList({ loading: false, devis: data() })
    const toggle = screen.getByRole('button', { name: /Voir les versions remplacées \(1\)/ })
    fireEvent.click(toggle)
    const row = screen.getByText('DEV-V1').closest('tr')
    expect(within(row).getByText('Remplacé')).toBeVisible()
    // Le lien « remplacé par DEV-V2 » est présent dans la ligne remplacée.
    expect(within(row).getByText('DEV-V2')).toBeVisible()
  })
})

describe('DevisList — WR1/QX26 : refus passe par l\'action dédiée refuser() avec motif obligatoire', () => {
  it('ouvre une modale de motif obligatoire (jamais un window.prompt optionnel)', async () => {
    renderList({
      loading: false,
      permissions: ['ventes_valider'],
      devis: [{
        id: 42, reference: 'DEV-REFUS', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 1,
      }],
    })
    const row = screen.getByText('DEV-REFUS').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Refuser/ }))
    await waitFor(() => {
      expect(screen.getByText(/Refuser le devis — DEV-REFUS/)).toBeVisible()
    })
    // Le bouton de confirmation reste désactivé sans motif choisi.
    expect(screen.getByRole('button', { name: /Confirmer le refus/ })).toBeDisabled()
  })

  it('appelle ventesApi.refuserDevis avec le motif choisi (jamais un PATCH statut direct)', async () => {
    const user = userEvent.setup()
    renderList({
      loading: false,
      permissions: ['ventes_valider'],
      devis: [{
        id: 42, reference: 'DEV-REFUS', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 1,
      }],
    })
    const row = screen.getByText('DEV-REFUS').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Refuser/ }))
    await waitFor(() => expect(crmApi.getMotifsPerte).toHaveBeenCalled())
    await user.click(screen.getByRole('combobox'))
    await waitFor(() => expect(screen.getByText('Trop cher')).toBeVisible())
    await user.click(screen.getByText('Trop cher'))
    await user.click(screen.getByRole('button', { name: /Confirmer le refus/ }))
    await waitFor(() => {
      expect(ventesApi.refuserDevis).toHaveBeenCalledWith(42, { motif_perte: '5', motif: undefined })
    })
  })
})

describe('DevisList — QG1 : ouverture automatique du PDF après « Générer »', () => {
  it('ouvre le PDF tout seul dès que le polling détecte fichier_pdf (pas de second clic)', async () => {
    // jsdom n'implémente pas createObjectURL/revokeObjectURL par défaut.
    const createObjectURL = vi.fn(() => 'blob:mock-url')
    const revokeObjectURL = vi.fn()
    URL.createObjectURL = createObjectURL
    URL.revokeObjectURL = revokeObjectURL
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    renderList({
      loading: false,
      devis: [{
        id: 99, reference: 'DEV-PDF-AUTO', client_nom: 'ACME', statut: 'brouillon',
        date_creation: '2026-07-01', total_ttc: 3000, nb_options: 1, version: 1,
      }],
    })

    const row = screen.getByText('DEV-PDF-AUTO').closest('tr')
    fireEvent.click(within(row).getByTitle('Générer le PDF (choix du format)'))

    // La modale de format s'ouvre — on lance la génération.
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Générer/ }))

    // Le polling (setTimeout réel 2s) voit fichier_pdf prêt et télécharge
    // automatiquement le PDF sans action supplémentaire de l'utilisateur.
    await waitFor(() => {
      expect(ventesApi.telechargerPdfDevis).toHaveBeenCalledWith(99)
    }, { timeout: 8000 })
    await waitFor(() => { expect(clickSpy).toHaveBeenCalled() })

    clickSpy.mockRestore()
  }, 15000)
})

describe('DevisList — U8 : état du bon de commande + incohérence', () => {
  it('affiche le statut du BC et avertit quand un devis accepté a un BC annulé', () => {
    renderList({
      loading: false,
      devis: [{
        id: 3, reference: 'DEV-BC-ANN', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
        bon_commande_etat: { exists: true, id: 9, reference: 'BC-9', statut: 'annule', statut_display: 'Annulé', mismatch: true },
      }],
    })
    const row = screen.getByText('DEV-BC-ANN').closest('tr')
    expect(within(row).getByText(/BC : Annulé/)).toBeVisible()
    expect(within(row).getByText('Devis accepté mais BC annulé')).toBeVisible()
  })

  it('avertit quand un devis accepté n\'a aucun bon de commande', () => {
    renderList({
      loading: false,
      devis: [{
        id: 4, reference: 'DEV-BC-NONE', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
        bon_commande_etat: { exists: false, reference: null, statut: null, statut_display: null, mismatch: true },
      }],
    })
    const row = screen.getByText('DEV-BC-NONE').closest('tr')
    expect(within(row).getByText('Devis accepté sans bon de commande')).toBeVisible()
  })

  it('n\'avertit pas quand le BC est confirmé sur un devis accepté', () => {
    renderList({
      loading: false,
      devis: [{
        id: 5, reference: 'DEV-BC-OK', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
        bon_commande_etat: { exists: true, id: 10, reference: 'BC-10', statut: 'confirme', statut_display: 'Confirmé', mismatch: false },
      }],
    })
    const row = screen.getByText('DEV-BC-OK').closest('tr')
    expect(within(row).getByText(/BC : Confirmé/)).toBeVisible()
    expect(within(row).queryByText(/BC annulé|sans bon de commande/)).toBeNull()
  })
})

describe('DevisList — QG10 : modale « Variante » (% + navigation comparaison)', () => {
  const draft = () => ([{
    id: 20, reference: 'DEV-VAR', client_nom: 'ACME', statut: 'brouillon',
    date_creation: '2026-07-01', total_ttc: 4000, nb_options: 1, version: 1,
  }])

  it('ouvre une modale pré-remplie depuis la config société (variante_pct)', async () => {
    const user = userEvent.setup()
    renderList({ loading: false, devis: draft(), role_nom: 'Directeur' })
    const row = screen.getByText('DEV-VAR').closest('tr')
    // VX20 — « Variante » vit désormais dans le menu « Plus d'actions ».
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Variante/ }))
    // La config est lue (GET variante-config) et le % pré-rempli à 25.
    await waitFor(() => {
      expect(ventesApi.getVarianteConfig).toHaveBeenCalled()
    })
    const input = await screen.findByLabelText(/Pourcentage de variation/)
    await waitFor(() => { expect(input.value).toBe('25') })
    // Le champ est éditable pour le Directeur (pas readOnly).
    expect(input).not.toHaveAttribute('readonly')
  })

  it('crée les variantes avec le % puis ouvre la comparaison (panneau versions)', async () => {
    const user = userEvent.setup()
    renderList({ loading: false, devis: draft(), role_nom: 'Commercial responsable' })
    const row = screen.getByText('DEV-VAR').closest('tr')
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Variante/ }))
    await screen.findByLabelText(/Pourcentage de variation/)
    fireEvent.click(screen.getByRole('button', { name: /Créer les variantes/ }))
    await waitFor(() => {
      // Le % (25) est transmis en override de requête.
      expect(ventesApi.dupliquerVariante).toHaveBeenCalledWith(20, { variante_pct: 25 })
    })
    // La comparaison s'ouvre : le panneau « Historique des versions » apparaît.
    await waitFor(() => {
      expect(screen.getByText('Historique des versions')).toBeTruthy()
    })
  })

  it('rend le champ % en lecture seule pour un rôle non autorisé', async () => {
    const user = userEvent.setup()
    renderList({ loading: false, devis: draft(), role: 'commercial', role_nom: 'Commercial' })
    const row = screen.getByText('DEV-VAR').closest('tr')
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Variante/ }))
    const input = await screen.findByLabelText(/Pourcentage de variation/)
    expect(input).toHaveAttribute('readonly')
  })
})

describe('DevisList — QG11/QG12 : design 3D (roof_layout) lecture seule', () => {
  const withRoof = () => ([{
    id: 30, reference: 'DEV-ROOF', client_nom: 'ACME', statut: 'envoye',
    date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
    roof_layout: {
      version: 1, zones: [{
        id: 'z1', label: 'Toit', roofType: 'flat', pitchDeg: 15,
        facingAzimuthDeg: 180, neededPanels: 10,
        vertices: [[-7.60, 33.50], [-7.599, 33.50], [-7.599, 33.501], [-7.60, 33.501]],
        obstacles: [],
      }],
    },
  }])

  it('affiche l\'action « Design 3D » dans le menu « Plus » et ouvre le panneau en lecture seule', async () => {
    const user = userEvent.setup()
    renderList({ loading: false, devis: withRoof() })
    const row = screen.getByText('DEV-ROOF').closest('tr')
    // VX20 — « Design 3D » vit désormais dans le menu « Plus d'actions ».
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /^Design 3D$/ }))
    // Le plan SVG (RoofViewer) apparaît dans le détail.
    expect(screen.getByTestId('roofviewer-svg')).toBeTruthy()
    expect(screen.getByText(/Design 3D de la toiture — DEV-ROOF/)).toBeTruthy()
  })

  it('n\'affiche AUCUNE action design 3D quand le devis n\'a pas de roof_layout', async () => {
    const user = userEvent.setup()
    renderList({
      loading: false,
      devis: [{
        id: 31, reference: 'DEV-NOROOF', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
      }],
    })
    const row = screen.getByText('DEV-NOROOF').closest('tr')
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    expect(await screen.findByRole('menu')).toBeTruthy()
    expect(screen.queryByRole('menuitem', { name: /Design 3D/ })).toBeNull()
  })

  it('ouvre la fenêtre plein écran (/ventes/devis/:id/3d) via l\'affordance', async () => {
    const user = userEvent.setup()
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    renderList({ loading: false, devis: withRoof() })
    const row = screen.getByText('DEV-ROOF').closest('tr')
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole(
      'menuitem', { name: /Ouvrir le design 3D de DEV-ROOF dans une fenêtre/ },
    ))
    expect(openSpy).toHaveBeenCalledWith('/ventes/devis/30/3d', '_blank', 'noopener')
    openSpy.mockRestore()
  })
})

describe('DevisList — WR2 : copier le lien de proposition (share_link)', () => {
  it('appelle shareLinkDevis et copie l\'URL publique au presse-papier', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn(() => Promise.resolve())
    // navigator.clipboard peut être un getter en lecture seule selon la version
    // de jsdom → defineProperty (configurable) au lieu d'Object.assign qui jette.
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText }, configurable: true, writable: true,
    })
    renderList({
      loading: false,
      devis: [{
        id: 40, reference: 'DEV-SHARE', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 7000, nb_options: 1, version: 1,
      }],
    })
    const row = screen.getByText('DEV-SHARE').closest('tr')
    // VX20 — « Copier le lien de la proposition » vit désormais dans le menu
    // « Plus d'actions ».
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Copier le lien de la proposition/ }))
    await waitFor(() => {
      expect(ventesApi.shareLinkDevis).toHaveBeenCalledWith(40)
    })
    await waitFor(() => {
      // L'URL complète est reconstruite depuis le path renvoyé (/proposition/<token>).
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('/proposition/tok123'))
    })
  })
})

describe('DevisList — XSAL16 : résumé d\'engagement par section', () => {
  it('affiche le temps passé par section quand engagement est renseigné', () => {
    renderList({
      loading: false,
      devis: [{
        id: 50, reference: 'DEV-ENGAGE', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
        engagement: { prix: { seconds: 120, hits: 4 }, etude: { seconds: 15, hits: 1 } },
      }],
    })
    const row = screen.getByText('DEV-ENGAGE').closest('tr')
    // Section la plus engagée (prix, 120s → 2 min) en premier.
    expect(within(row).getByText(/2 min sur prix/)).toBeVisible()
    expect(within(row).getByText(/15 s sur étude/)).toBeVisible()
  })

  it('n\'affiche aucun résumé sans beacon (engagement vide)', () => {
    renderList({
      loading: false,
      devis: [{
        id: 51, reference: 'DEV-NOENGAGE', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 9000, nb_options: 1, version: 1,
        engagement: {},
      }],
    })
    const row = screen.getByText('DEV-NOENGAGE').closest('tr')
    expect(within(row).queryByText(/sur prix|sur étude/)).toBeNull()
  })
})

describe('DevisList — VX216(a) : seam devis↔chantier visible côté vendeur', () => {
  it('badge « Chantier en cours (compo gelée) » quand le chantier lié n\'est ni réceptionné ni clôturé', () => {
    renderList({
      loading: false,
      devis: [{
        id: 70, reference: 'DEV-VX216-A', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 20000, nb_options: 1, version: 1,
        chantier: { id: 5, reference: 'CH-2026-07-0005', statut: 'en_cours' },
      }],
    })
    const row = screen.getByText('DEV-VX216-A').closest('tr')
    expect(within(row).getByText('Chantier en cours (compo gelée)')).toBeVisible()
  })

  it('aucun badge quand le chantier est réceptionné/clôturé (composition plus « engagée »)', () => {
    renderList({
      loading: false,
      devis: [{
        id: 71, reference: 'DEV-VX216-B', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 20000, nb_options: 1, version: 1,
        chantier: { id: 6, reference: 'CH-2026-07-0006', statut: 'cloture' },
      }],
    })
    const row = screen.getByText('DEV-VX216-B').closest('tr')
    expect(within(row).queryByText('Chantier en cours (compo gelée)')).toBeNull()
  })

  it('« Réviser (nouvelle version) » avertit (toast.warning) quand un chantier en cours est lié', async () => {
    const user = userEvent.setup()
    const warnSpy = vi.spyOn(toast, 'warning')
    renderList({
      loading: false,
      devis: [{
        id: 72, reference: 'DEV-VX216-C', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 20000, nb_options: 1, version: 1,
        is_active: true,
        chantier: { id: 7, reference: 'CH-2026-07-0007', statut: 'planifie' },
      }],
    })
    const row = screen.getByText('DEV-VX216-C').closest('tr')
    await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
    await user.click(screen.getByRole('menuitem', { name: /Réviser/ }))
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('CH-2026-07-0007'))
  })
})

describe('DevisList — VX140 : ≤5 boutons d\'action visibles + menu, cellule Référence à 2 niveaux', () => {
  it('un devis brouillon montre au plus 5 boutons visibles + le menu « Plus d\'actions »', () => {
    renderList({
      loading: false,
      devis: [{
        id: 60, reference: 'DEV-VX140-A', client_nom: 'ACME', statut: 'brouillon',
        date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 1,
      }],
    })
    const row = screen.getByText('DEV-VX140-A').closest('tr')
    const actionsCell = row.cells[row.cells.length - 1]
    const buttons = within(actionsCell).getAllByRole('button')
    // PDF, Envoyer, Générer facture (désactivé), Plus d'actions = 4 boutons visibles.
    expect(buttons.length).toBeLessThanOrEqual(5)
    expect(within(actionsCell).getByRole('button', { name: /Plus d'actions/ })).toBeVisible()
  })

  it('un devis envoyé montre au plus 5 boutons visibles + le menu « Plus d\'actions »', () => {
    renderList({
      loading: false,
      devis: [{
        id: 61, reference: 'DEV-VX140-B', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 1,
      }],
    })
    const row = screen.getByText('DEV-VX140-B').closest('tr')
    const actionsCell = row.cells[row.cells.length - 1]
    const buttons = within(actionsCell).getAllByRole('button')
    // PDF, Accepter, Refuser, Générer facture (désactivé), Plus d'actions = 5 boutons visibles.
    expect(buttons.length).toBeLessThanOrEqual(5)
  })

  it('la cellule Référence rend la référence + badges en ligne 1, métadonnées compactes en ligne 2', () => {
    renderList({
      loading: false,
      devis: [{
        id: 62, reference: 'DEV-VX140-C', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 2,
        version_parent_ref: 'DEV-VX140-B0', deja_consulte: true, nombre_vues: 3,
      }],
    })
    const refCell = screen.getByTestId('ref-cell-62')
    // Ligne 1 : référence + badge de version, en gras.
    const line1 = refCell.firstElementChild
    expect(line1.className).toMatch(/font-semibold/)
    expect(within(line1).getByText('DEV-VX140-C')).toBeVisible()
    expect(within(line1).getByText('v2')).toBeVisible()
    // Ligne 2 : métadonnées muted, text-xs, séparées par « · ».
    const line2 = line1.nextElementSibling
    expect(line2.className).toMatch(/text-xs/)
    expect(line2.className).toMatch(/text-muted-foreground/)
    expect(within(line2).getByText(/Voir les versions/)).toBeVisible()
    expect(within(line2).getByText(/Consulté ×3/)).toBeVisible()
  })

  it('la cellule Référence ne rend pas de ligne 2 quand il n\'y a aucune métadonnée', () => {
    renderList({
      loading: false,
      devis: [{
        id: 63, reference: 'DEV-VX140-D', client_nom: 'ACME', statut: 'brouillon',
        date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 1,
      }],
    })
    const refCell = screen.getByTestId('ref-cell-63')
    // Seule la ligne 1 (référence) est présente — pas de deuxième div de métadonnées.
    expect(refCell.children.length).toBe(1)
  })
})

describe('DevisList — VX82 : titre d’onglet dédié', () => {
  const originalTitle = document.title
  afterEach(() => { document.title = originalTitle })

  it('monter DevisList met à jour document.title', () => {
    document.title = 'TAQINOR'
    renderList({ loading: false, devis: [] })
    expect(document.title).toBe('Devis')
  })
})
