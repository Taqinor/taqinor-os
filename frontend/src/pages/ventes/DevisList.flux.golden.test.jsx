import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, within, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { toast } from 'sonner'

/* SPL192 — GOLDEN des FLUX de la liste des devis (aucun déplacement).

   Un DOM statique ne voit pas un handler déplacé qui passe d'autres arguments,
   saute un nettoyage ou change l'ordre de ses effets. Ce test pilote chaque
   flux que SPL204 (PDF) et SPL205 (envoi) déplacent, sur le code ACTUEL, et
   commit le journal ORDONNÉ des appels sortants (ventesApi.*, dispatch, toast,
   navigate, window.open, URL.createObjectURL, presse-papier, partage natif)
   dans devisList/__golden__/devisList.flux.json.

   Les déplacements doivent le laisser IDENTIQUE :
   `CI=true npx vitest run src/pages/ventes/DevisList.flux.golden.test.jsx`
   (sous CI, Vitest n'écrit aucun snapshot) + `git diff --exit-code` sur le JSON.

   Règle #4 : seul /proposal est exercé (genererUnPdf → genererPdfDevis), aucun
   nouveau chemin de PDF client. Dates figées (vi.setSystemTime), seul le
   sondage PDF (setTimeout 2 s de l'écran) tourne en temps réel. */

const journal = vi.hoisted(() => {
  vi.setSystemTime(new Date('2026-08-20T10:00:00Z'))
  return []
})

// Sérialisation stable des arguments (Blob/File/fonctions).
function ser(v) {
  return JSON.parse(JSON.stringify(v === undefined ? null : v, (_k, x) => {
    if (typeof File !== 'undefined' && x instanceof File) return `File(${x.name}, ${x.type})`
    if (typeof Blob !== 'undefined' && x instanceof Blob) return `Blob(${x.type})`
    if (typeof x === 'function') return '[fn]'
    if (x === undefined) return '[undefined]'
    return x
  }))
}
const noter = (quoi, args) => { journal.push([quoi, ...args.map(ser)]) }

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: vi.fn(() => ({ type: 'ventes/fetchDevis/noop' })),
    genererPdfDevis: (...args) => {
      journal.push(['genererPdfDevis', ...JSON.parse(JSON.stringify(args))])
      const action = { type: 'ventes/genererPdfDevis/noop' }
      action.unwrap = () => Promise.resolve()
      return action
    },
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
})

// Réponses de ventesApi (mêmes valeurs que DevisList.test.jsx:31-77) ; TOUTE
// méthode de ventesApi est journalisée (réponse vide par défaut, jamais réseau).
const REPONSES = vi.hoisted(() => ({
  refuserDevis: () => ({ data: { statut: 'refuse' } }),
  getDevisById: () => ({ data: { fichier_pdf: '/media/devis/DEV-PDF-AUTO.pdf' } }),
  etatPdfDevis: () => ({
    data: { devis: 99, statut: 'pret', fichier_pdf: true, erreur: null, date: null },
  }),
  getVariantes: () => ({ data: [] }),
  historiqueDevis: () => ({ data: [] }),
  noterDevis: () => ({ data: { id: 1 } }),
  accepterDevis: () => ({ data: {} }),
  telechargerPdfDevis: () => ({
    data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }), headers: {},
  }),
  getProformaPdf: () => ({ data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }), headers: {} }),
  getBonCommandePdf: () => ({ data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }), headers: {} }),
  getProposalPdf: () => ({ data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }), headers: {} }),
  getVarianteConfig: () => ({ data: { variante_pct: '25.00' } }),
  dupliquerVariante: () => ({ data: [] }),
  shareLinkDevis: () => ({
    data: { token: 'tok123', path: '/proposition/tok123', path_interne: '/proposition/int456' },
  }),
  whatsappPreviewDevis: () => ({ data: { wa_url: 'https://wa.me/212600000000', message: 'Bonjour' } }),
  whatsappDevis: () => ({ data: { statut: 'envoye' } }),
  partagePdfDevis: () => ({ data: { devis_statut: 'envoye' } }),
  envoyerEmailDevis: () => ({ data: { ok: true } }),
  contacterSuperieur: () => ({ data: { ok: true } }),
  superiorContactStatus: () => ({ data: { requested: true, seen: true, seen_by: 'Chef' } }),
  patchDevis: () => ({ data: {} }),
}))

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  const espion = {}
  for (const nom of Object.keys(actual.default)) {
    espion[nom] = vi.fn((...args) => {
      noter(`ventesApi.${nom}`, args)
      return Promise.resolve(REPONSES[nom] ? REPONSES[nom]() : { data: {} })
    })
  }
  return { ...actual, default: espion }
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

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useNavigate: () => (...args) => { journal.push(['navigate', ...args.map(ser)]) },
  }
})

import DevisList from './DevisList'
import ventesApi from '../../api/ventesApi'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const BROUILLON = {
  id: 101, reference: 'DEV-F-BROUILLON', client_nom: 'ACME', client_email: 'acme@exemple.ma',
  statut: 'brouillon', date_creation: '2026-08-01', total_ttc: 42000, nb_options: 1,
  version: 1, is_active: true, fichier_pdf: '/media/devis/f1.pdf',
}
const ENVOYE = {
  id: 102, reference: 'DEV-F-ENVOYE', client_nom: 'Beta SARL', statut: 'envoye',
  date_creation: '2026-07-01', total_ttc: 61000, nb_options: 1, version: 1,
  is_active: true, fichier_pdf: '/media/devis/f2.pdf',
}
const ACCEPTE = {
  id: 103, reference: 'DEV-F-ACCEPTE', client_nom: 'Gamma', statut: 'accepte',
  date_creation: '2026-06-15', total_ttc: 80000, nb_options: 1, version: 1, is_active: true,
  bon_commande_etat: { exists: true, id: 7, reference: 'BC-F-0007', statut: 'confirme', mismatch: false },
}

function renderList(url = '/ventes/devis') {
  const espionDispatch = () => (next) => (action) => {
    journal.push(['dispatch', typeof action === 'function' ? '[thunk]' : action.type])
    return next(action)
  }
  const store = configureStore({
    reducer: {
      ventes: (s = { devis: [BROUILLON, ENVOYE, ACCEPTE], loading: false, error: null }) => s,
      auth: (s = {
        role: 'admin', role_nom: 'Directeur', permissions: ['ventes_valider'],
      }) => s,
    },
    middleware: (gDM) => gDM({ serializableCheck: false }).concat(espionDispatch),
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[url]}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const FLUX = {}
const repos = (ms = 120) => new Promise((r) => setTimeout(r, ms))
const ligne = (reference) => screen.getByText(reference).closest('tr')
async function menu(user, reference, item) {
  await user.click(within(ligne(reference)).getByRole('button', { name: /Plus d'actions/ }))
  await user.click(await screen.findByRole('menuitem', { name: item }))
}
// Après userEvent.setup() (qui installe son propre presse-papier factice).
function installerPressePapier() {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: (...a) => { noter('clipboard.writeText', a); return Promise.resolve() } },
    configurable: true, writable: true,
  })
}
const appele = (nom) => journal.some(([q]) => q === nom)

let canShareAvant
let shareAvant
beforeEach(() => {
  journal.length = 0
  canShareAvant = navigator.canShare
  shareAvant = navigator.share
  vi.spyOn(window, 'open').mockImplementation((...a) => { noter('window.open', a); return null })
  URL.createObjectURL = (...a) => { noter('URL.createObjectURL', a); return 'blob:flux' }
  URL.revokeObjectURL = () => {}
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function clic() {
    noter('a.click', [{ href: this.getAttribute('href'), download: this.getAttribute('download') }])
  })
  for (const m of ['success', 'error', 'warning', 'info', 'message']) {
    vi.spyOn(toast, m).mockImplementation((...a) => { noter(`toast.${m}`, a); return 1 })
  }
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  navigator.canShare = canShareAvant
  navigator.share = shareAvant
})

describe('SPL192 — golden des flux de DevisList (code actuel)', () => {
  it('PDF complet (génération + sondage + ouverture auto)', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(within(ligne('DEV-F-BROUILLON')).getByTitle('Générer le PDF (choix du format)'))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('radio', { name: /Devis premium/ }))
    await user.click(within(dialog).getByRole('button', { name: /Générer/ }))
    await waitFor(() => expect(appele('ventesApi.telechargerPdfDevis')).toBe(true), { timeout: 8000 })
    await repos()
    FLUX.pdf_complet = [...journal]
  }, 20000)

  it('PDF une page', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(within(ligne('DEV-F-BROUILLON')).getByTitle('Générer le PDF (choix du format)'))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('radio', { name: /Devis une page/ }))
    await user.click(within(dialog).getByRole('button', { name: /Générer/ }))
    await waitFor(() => expect(appele('ventesApi.telechargerPdfDevis')).toBe(true), { timeout: 8000 })
    await repos()
    FLUX.pdf_onepage = [...journal]
  }, 20000)

  it('PDF par lot (sans ouverture auto)', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(screen.getByRole('checkbox', { name: 'Sélectionner DEV-F-BROUILLON' }))
    await user.click(screen.getByRole('checkbox', { name: 'Sélectionner DEV-F-ENVOYE' }))
    await user.click(screen.getByRole('button', { name: /Générer les PDF/ }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /Générer/ }))
    await waitFor(() => expect(
      journal.filter(([q]) => q === 'ventesApi.etatPdfDevis').length,
    ).toBe(2), { timeout: 8000 })
    await repos()
    FLUX.pdf_lot = [...journal]
  }, 20000)

  it('proforma et bon de commande (PDF)', async () => {
    const user = userEvent.setup()
    renderList()
    await menu(user, 'DEV-F-ACCEPTE', /Proforma \(PDF\)/)
    await waitFor(() => expect(appele('ventesApi.getProformaPdf')).toBe(true))
    await repos()
    journal.push(['--- bon de commande ---'])
    await menu(user, 'DEV-F-ACCEPTE', /Bon de commande \(PDF\)/)
    await waitFor(() => expect(appele('ventesApi.getBonCommandePdf')).toBe(true))
    await repos()
    FLUX.pdf_proforma_bc = [...journal]
  })

  it('partager le PDF (feuille native résolue = envoi)', async () => {
    const user = userEvent.setup()
    navigator.canShare = (...a) => { noter('navigator.canShare', a); return true }
    navigator.share = (...a) => { noter('navigator.share', a); return Promise.resolve() }
    renderList()
    await menu(user, 'DEV-F-BROUILLON', /Partager le PDF/)
    await waitFor(() => expect(appele('ventesApi.partagePdfDevis')).toBe(true))
    await repos()
    FLUX.partage_pdf = [...journal]
  })

  it('email', async () => {
    const user = userEvent.setup()
    renderList()
    await menu(user, 'DEV-F-BROUILLON', /Envoyer par email/)
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /^Envoyer$/ }))
    await waitFor(() => expect(appele('ventesApi.envoyerEmailDevis')).toBe(true))
    await repos()
    FLUX.email = [...journal]
  })

  it('WhatsApp (envoi normal)', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(within(ligne('DEV-F-BROUILLON')).getByRole('button', { name: /^Envoyer$/ }))
    await user.click(await screen.findByRole('button', { name: /Ouvrir WhatsApp/ }))
    await waitFor(() => expect(appele('ventesApi.whatsappDevis')).toBe(true))
    await repos()
    FLUX.whatsapp = [...journal]
  })

  it('WhatsApp (relance)', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(within(ligne('DEV-F-ENVOYE')).getByRole('button', { name: /Relancer/ }))
    await user.click(await screen.findByRole('button', { name: /Ouvrir WhatsApp/ }))
    await waitFor(() => expect(appele('ventesApi.noterDevis')).toBe(true))
    await repos()
    FLUX.whatsapp_relance = [...journal]
  })

  it('copie des liens (interne, proposition, aperçu interne)', async () => {
    const user = userEvent.setup()
    installerPressePapier()
    renderList()
    await menu(user, 'DEV-F-ENVOYE', /Lien interne/)
    await waitFor(() => expect(appele('toast.success')).toBe(true))
    await repos()
    journal.push(['--- lien proposition ---'])
    await menu(user, 'DEV-F-ENVOYE', /Copier le lien de la proposition/)
    await waitFor(() => expect(journal.filter(([q]) => q === 'toast.success').length).toBe(2))
    await repos()
    journal.push(['--- aperçu interne ---'])
    await menu(user, 'DEV-F-ENVOYE', /Copier l.aperçu interne/)
    await waitFor(() => expect(journal.filter(([q]) => q === 'toast.success').length).toBe(3))
    await repos()
    FLUX.copie_liens = [...journal]
  })

  it('contacter le supérieur', async () => {
    const user = userEvent.setup()
    renderList()
    await menu(user, 'DEV-F-BROUILLON', /Contacter mon supérieur/)
    await waitFor(() => expect(appele('ventesApi.superiorContactStatus')).toBe(true))
    await repos()
    FLUX.contacter_superieur = [...journal]
  })

  it('deep-link ?envoyer=1', async () => {
    renderList('/ventes/devis?devis=101&envoyer=1')
    await screen.findByRole('button', { name: /Ouvrir WhatsApp/ })
    await repos()
    FLUX.deep_link_envoyer = [...journal]
  })

  it('deep-link ?apercu=1', async () => {
    renderList('/ventes/devis?devis=101&apercu=1')
    await waitFor(() => expect(appele('ventesApi.getProposalPdf')).toBe(true))
    await repos()
    FLUX.deep_link_apercu = [...journal]
  })

  it('démontage PENDANT un sondage PDF : minuteurs annulés, plus aucun appel', async () => {
    const user = userEvent.setup()
    ventesApi.etatPdfDevis.mockImplementation((...args) => {
      noter('ventesApi.etatPdfDevis', args)
      return Promise.resolve({
        data: { devis: 101, statut: 'en_cours', fichier_pdf: false, erreur: null, date: null },
      })
    })
    const { unmount } = renderList()
    await user.click(within(ligne('DEV-F-BROUILLON')).getByTitle('Générer le PDF (choix du format)'))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /Générer/ }))
    await waitFor(() => expect(appele('ventesApi.etatPdfDevis')).toBe(true), { timeout: 8000 })
    await repos(50)
    unmount()
    journal.push(['--- démontage ---'])
    await repos(4500)
    FLUX.demontage_pendant_sondage = [...journal]
    expect(journal[journal.length - 1]).toEqual(['--- démontage ---'])
  }, 20000)

  it('journal complet identique au golden', async () => {
    await expect(`${JSON.stringify(FLUX, null, 2)}\n`)
      .toMatchFileSnapshot('./devisList/__golden__/devisList.flux.json')
  })
})
