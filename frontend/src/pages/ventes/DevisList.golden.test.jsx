import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* SPL191 — GOLDEN DOM de la liste des devis (aucun déplacement).

   Capture, sur le code ACTUEL, le DOM complet (document.body, portails Radix
   compris) des écrans de DevisList : liste, kanban, menu « Plus », panneaux de
   ligne et modales. Les déplacements SPL203 → SPL206 (DevisRow, flux PDF,
   parcours d'envoi, en-tête) doivent laisser ces fichiers IDENTIQUES : lancer
   `CI=true npx vitest run src/pages/ventes/DevisList.golden.test.jsx` (sous CI,
   Vitest n'écrit AUCUN snapshot manquant ou modifié — il échoue).

   SEULE normalisation : les identifiants React `useId` (ils changent dès qu'un
   bloc de JSX passe dans un composant enfant, sans aucun effet visible). */

// Horloge figée AVANT l'import de l'écran (dates relatives, « expire bientôt »…).
vi.hoisted(() => { vi.setSystemTime(new Date('2026-08-20T10:00:00Z')) })

// Mêmes mocks de module que DevisList.test.jsx:13-93 (ventesSlice, ventesApi,
// crmApi, uxviewsApi) — la source testée (DevisList.jsx) n'est jamais mockée.
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: vi.fn(() => ({ type: 'ventes/fetchDevis/noop' })),
    genererPdfDevis: () => {
      const action = { type: 'ventes/genererPdfDevis/noop' }
      action.unwrap = () => Promise.resolve()
      return action
    },
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
})

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      refuserDevis: vi.fn(() => Promise.resolve({ data: { statut: 'refuse' } })),
      getDevisById: vi.fn(() => Promise.resolve({ data: { fichier_pdf: '/media/devis/DEV-PDF-AUTO.pdf' } })),
      etatPdfDevis: vi.fn(() => Promise.resolve({
        data: { devis: 99, statut: 'pret', fichier_pdf: true, erreur: null, date: null },
      })),
      getVariantes: vi.fn(() => Promise.resolve({ data: [] })),
      historiqueDevis: vi.fn(() => Promise.resolve({ data: [] })),
      noterDevis: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      accepterDevis: vi.fn(() => Promise.resolve({ data: {} })),
      telechargerPdfDevis: vi.fn(() => Promise.resolve({
        data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: {},
      })),
      getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '25.00' } })),
      dupliquerVariante: vi.fn(() => Promise.resolve({ data: [] })),
      dupliquerVarianteGamme: vi.fn(() => Promise.resolve({
        data: { source: {}, gamme: {}, gammes: [] },
      })),
      shareLinkDevis: vi.fn(() => Promise.resolve({ data: { token: 'tok123', path: '/proposition/tok123' } })),
      whatsappPreviewDevis: vi.fn(() => Promise.resolve({ data: { wa_url: 'https://wa.me/212600000000', message: 'Bonjour' } })),
      whatsappDevis: vi.fn(() => Promise.resolve({ data: { statut: 'envoye' } })),
      partagePdfDevis: vi.fn(() => Promise.resolve({ data: { devis_statut: 'envoye' } })),
      reviserDevis: vi.fn(() => Promise.resolve({ data: {} })),
      patchDevis: vi.fn(() => Promise.resolve({ data: {} })),
      // Panneau « Conception électrique » : réponse vide et stable.
      getConceptionElectrique: vi.fn(() => Promise.resolve({ data: {} })),
      getSchemaUnifilaireDevis: vi.fn(() => Promise.resolve({ data: { params: {}, svg: null } })),
      superiorContactStatus: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})

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

vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: { id: 1, ecran: 'ventes.devis' } })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
}))

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup() })

const ROOF = {
  version: 1, zones: [{
    id: 'z1', label: 'Toit', roofType: 'flat', pitchDeg: 15,
    facingAzimuthDeg: 180, neededPanels: 10,
    vertices: [[-7.60, 33.50], [-7.599, 33.50], [-7.599, 33.501], [-7.60, 33.501]],
    obstacles: [],
  }],
}

// Un devis par statut (brouillon, envoyé avec variantes + expiré, accepté avec
// option retenue, refusé, remplacé is_active=false).
function jeuDeDevis() {
  return [
    {
      id: 101, reference: 'DEV-G-BROUILLON', client_nom: 'ACME', statut: 'brouillon',
      date_creation: '2026-08-01', total_ttc: 42000, nb_options: 1, version: 1,
      is_active: true, fichier_pdf: '/media/devis/g1.pdf', roof_layout: ROOF,
    },
    {
      id: 102, reference: 'DEV-G-ENVOYE', client_nom: 'Beta SARL', statut: 'envoye',
      date_creation: '2026-07-01', total_ttc: 61000, nb_options: 1, version: 1,
      is_active: true, a_variantes: true, is_expired: true,
      fichier_pdf: '/media/devis/g2.pdf',
    },
    {
      id: 103, reference: 'DEV-G-ACCEPTE', client_nom: 'Gamma', statut: 'accepte',
      date_creation: '2026-06-15', total_ttc: 80000, nb_options: 2, version: 1,
      is_active: true, option_acceptee: 'avec',
    },
    {
      id: 104, reference: 'DEV-G-REFUSE', client_nom: 'Delta', statut: 'refuse',
      date_creation: '2026-06-01', total_ttc: 15000, nb_options: 1, version: 1,
      is_active: true,
    },
    {
      id: 105, reference: 'DEV-G-REMPLACE', client_nom: 'ACME', statut: 'envoye',
      date_creation: '2026-05-01', total_ttc: 40000, nb_options: 1, version: 1,
      is_active: false, superseded_by_ref: 'DEV-G-BROUILLON',
    },
  ]
}

function renderList(devis = jeuDeDevis()) {
  const store = configureStore({
    reducer: {
      ventes: (s = { devis, loading: false, error: null }) => s,
      auth: (s = {
        role: 'admin', role_nom: 'Directeur', permissions: ['ventes_valider'],
      }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

// SEULE normalisation : les identifiants React useId (« _r_1_ » en React 19.2,
// « «r1» » / « :r1: » dans les versions précédentes).
function normaliser(html) {
  return html.replace(/_r_[0-9a-z]+_|«r[0-9a-z]+»|:r[0-9a-z]+:/g, '«id»')
}

function capture(titre) {
  return `<!-- ===== ${titre} ===== -->\n${normaliser(document.body.innerHTML)}\n`
}

const ligne = (reference) => screen.getByText(reference).closest('tr')

async function ouvrirMenu(user, reference) {
  await user.click(within(ligne(reference)).getByRole('button', { name: /Plus d'actions/ }))
  return screen.findByRole('menu')
}

async function fermer(user) {
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
}

describe('SPL191 — golden DOM de DevisList (code actuel)', () => {
  it('liste', async () => {
    renderList()
    await screen.findByTestId('uxviews-open-btn')
    const vues = capture('liste — remplacés masqués')
    fireEvent.click(screen.getByRole('button', { name: /Voir les versions remplacées/ }))
    await screen.findByText('DEV-G-REMPLACE')
    await expect(vues + capture('liste — remplacés visibles'))
      .toMatchFileSnapshot('./devisList/__golden__/devisList.liste.html')
  })

  it('kanban', async () => {
    const user = userEvent.setup()
    renderList()
    await screen.findByTestId('uxviews-open-btn')
    await user.click(screen.getByRole('button', { name: /Board/ }))
    await waitFor(() => expect(document.querySelector('table.data-table')).toBeNull())
    await expect(capture('kanban'))
      .toMatchFileSnapshot('./devisList/__golden__/devisList.kanban.html')
  })

  it('menu Plus ouvert', async () => {
    const user = userEvent.setup()
    renderList()
    await screen.findByTestId('uxviews-open-btn')
    let out = ''
    for (const ref of ['DEV-G-BROUILLON', 'DEV-G-ENVOYE', 'DEV-G-ACCEPTE', 'DEV-G-REFUSE']) {
      await ouvrirMenu(user, ref)
      out += capture(`menu Plus — ${ref}`)
      await user.keyboard('{Escape}')
      await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
    }
    await expect(out).toMatchFileSnapshot('./devisList/__golden__/devisList.menu-plus.html')
  })

  it('panneaux de ligne', async () => {
    const user = userEvent.setup()
    renderList()
    await screen.findByTestId('uxviews-open-btn')
    let out = ''

    // Versions (comparaison des variantes servie par le serveur).
    await user.click(within(ligne('DEV-G-ENVOYE')).getByRole('button', { name: /Voir les versions/ }))
    await waitFor(() => expect(document.body.textContent).toMatch(/variante/i))
    out += capture('panneau — versions')
    await user.click(within(ligne('DEV-G-ENVOYE')).getByRole('button', { name: /Voir les versions|Masquer les versions/ }))

    // Historique + compositeur de note.
    await ouvrirMenu(user, 'DEV-G-ENVOYE')
    await user.click(await screen.findByRole('menuitem', { name: /Historique des modifications/ }))
    await screen.findByRole('button', { name: 'Ajouter la note' })
    out += capture('panneau — historique + note')
    await ouvrirMenu(user, 'DEV-G-ENVOYE')
    await user.click(await screen.findByRole('menuitem', { name: /Masquer l.historique/ }))

    // Design 3D (lecture seule).
    await ouvrirMenu(user, 'DEV-G-BROUILLON')
    await user.click(await screen.findByRole('menuitem', { name: /^Design 3D$/ }))
    await screen.findByTestId('roofviewer-svg')
    out += capture('panneau — design 3D')
    await ouvrirMenu(user, 'DEV-G-BROUILLON')
    await user.click(await screen.findByRole('menuitem', { name: /Design 3D/ }))

    // Conception électrique.
    await ouvrirMenu(user, 'DEV-G-ACCEPTE')
    await user.click(await screen.findByRole('menuitem', { name: 'Conception électrique' }))
    await screen.findByText('Conception électrique — DEV-G-ACCEPTE')
    await new Promise((r) => setTimeout(r, 50))
    out += capture('panneau — conception électrique')
    await ouvrirMenu(user, 'DEV-G-ACCEPTE')
    await user.click(await screen.findByRole('menuitem', { name: 'Masquer la conception électrique' }))

    // Étude bancable.
    await ouvrirMenu(user, 'DEV-G-ACCEPTE')
    await user.click(await screen.findByRole('menuitem', { name: 'Étude bancable' }))
    await new Promise((r) => setTimeout(r, 50))
    out += capture('panneau — étude bancable')

    await expect(out).toMatchFileSnapshot('./devisList/__golden__/devisList.panneaux-ligne.html')
  })

  it('modales', async () => {
    const user = userEvent.setup()
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    URL.createObjectURL = vi.fn(() => 'blob:golden')
    URL.revokeObjectURL = vi.fn()
    renderList()
    await screen.findByTestId('uxviews-open-btn')
    let out = ''

    // PDF (choix du format).
    await user.click(within(ligne('DEV-G-BROUILLON')).getByTitle('Générer le PDF (choix du format)'))
    await screen.findByRole('dialog')
    out += capture('modale — PDF')
    await fermer(user)

    // Accepter.
    await user.click(within(ligne('DEV-G-ENVOYE')).getByRole('button', { name: /Accepter/ }))
    await screen.findByRole('dialog')
    out += capture('modale — accepter')
    await fermer(user)

    // Refuser (motifs chargés).
    await user.click(within(ligne('DEV-G-ENVOYE')).getByRole('button', { name: /Refuser/ }))
    await screen.findByRole('dialog')
    await waitFor(() => expect(screen.queryByText(/Aucun motif configuré/)).toBeNull())
    out += capture('modale — refuser')
    await fermer(user)

    // Email.
    await ouvrirMenu(user, 'DEV-G-BROUILLON')
    await user.click(await screen.findByRole('menuitem', { name: /Envoyer par email/ }))
    await screen.findByRole('dialog')
    out += capture('modale — email')
    await fermer(user)

    // WhatsApp normal.
    await user.click(within(ligne('DEV-G-BROUILLON')).getByRole('button', { name: /^Envoyer$/ }))
    await screen.findByRole('button', { name: /Ouvrir WhatsApp/ })
    out += capture('modale — WhatsApp')
    await fermer(user)

    // WhatsApp relance.
    await user.click(within(ligne('DEV-G-ENVOYE')).getByRole('button', { name: /Relancer/ }))
    await screen.findByRole('button', { name: /Ouvrir WhatsApp/ })
    out += capture('modale — WhatsApp relance')
    await fermer(user)

    // Variante.
    await ouvrirMenu(user, 'DEV-G-BROUILLON')
    await user.click(await screen.findByRole('menuitem', { name: /^Variante/ }))
    await screen.findByRole('button', { name: /Créer les variantes/ })
    await new Promise((r) => setTimeout(r, 20))
    out += capture('modale — variante')
    await fermer(user)

    // Gamme.
    await ouvrirMenu(user, 'DEV-G-BROUILLON')
    await user.click(await screen.findByRole('menuitem', { name: /Créer une variante de gamme/ }))
    await screen.findByRole('button', { name: /Créer la gamme/ })
    out += capture('modale — gamme')
    await fermer(user)

    // PdfPreviewSheet (aperçu du PDF).
    await ouvrirMenu(user, 'DEV-G-BROUILLON')
    await user.click(await screen.findByRole('menuitem', { name: /Aperçu du PDF/ }))
    await screen.findByRole('dialog')
    await new Promise((r) => setTimeout(r, 50))
    out += capture('feuille — aperçu PDF')

    openSpy.mockRestore()
    await expect(out).toMatchFileSnapshot('./devisList/__golden__/devisList.modales.html')
  })
})
