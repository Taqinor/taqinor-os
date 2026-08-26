import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   QS1 — bouton « PDF (interne) » du bon de commande fournisseur.
   Avant : tout échec (403 permission, HTML d'erreur, réseau) était avalé en
   « PDF indisponible. » et rien ne s'ouvrait. Après : le PDF s'ouvre dans un
   nouvel onglet (repli téléchargement si popup bloquée) et la VRAIE erreur
   serveur est affichée (lue depuis le Blob d'erreur DRF).

   QS2 — « + Nouveau produit » dans le BCF (réservé Directeur/Commercial
   responsable), QS4 — boutons Envoyer WhatsApp / email (grisés sans contact).
   Le BcfDetail consulte désormais le hook de rôle → Provider Redux requis.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    bcfPdf: vi.fn(),
    createProduit: vi.fn(),
    whatsappBcf: vi.fn(),
    envoyerEmailBcf: vi.fn(),
    annulerBcf: vi.fn(),
    rouvrirBcf: vi.fn(),
    dupliquerBcf: vi.fn(),
    facturerBcf: vi.fn(),
    updateBonCommandeFournisseur: vi.fn(),
    reviserBcf: vi.fn(),
    confirmerBcf: vi.fn(),
    getBcfSimilaires: vi.fn(() => Promise.resolve({ data: [] })),
    getHistoriquePrixBcf: vi.fn(),
    // WIR220 — liste par défaut (page complète).
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    getFournisseurs: vi.fn(() => Promise.resolve({ data: [] })),
    getProduits: vi.fn(() => Promise.resolve({ data: [] })),
    getBcfEnRetard: vi.fn(() => Promise.resolve({ data: [] })),
    getAchatsHorsContrat: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/messagesApi', () => ({
  default: { listCompanyMembers: vi.fn().mockResolvedValue({ data: [] }) },
}))

import stockApi from '../../api/stockApi'
import BonsCommandeFournisseur, { BcfDetail, MotifAnnulationModal } from './BonsCommandeFournisseur.jsx'
import { messageErreurBlob } from '../../utils/pdfBlob'

function makeStore({ role_nom = 'Magasinier', permissions = [] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function makeWrapper(authState) {
  return function wrapper({ children }) {
    return (
      <Provider store={makeStore(authState)}>
        <MemoryRouter>
          <ThemeProvider>{children}</ThemeProvider>
        </MemoryRouter>
      </Provider>
    )
  }
}

const bcf = {
  id: 42,
  reference: 'BCF-2026-07-0042',
  statut: 'recu',
  fournisseur: 1,
  lignes: [],
}

function renderDetail(props = {}, authState) {
  return render(
    <BcfDetail bcf={bcf} fournisseurs={[]} produits={[]}
               onClose={() => {}} onSaved={() => {}} {...props} />,
    { wrapper: makeWrapper(authState) },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  // jsdom n'implémente pas createObjectURL ; matchMedia requis par la densité.
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  URL.revokeObjectURL = vi.fn()
  window.open = vi.fn(() => ({}))
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('QS1 — PDF (interne) : ouverture', () => {
  it('ouvre le PDF dans un nouvel onglet quand le serveur renvoie un PDF', async () => {
    stockApi.bcfPdf.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    await waitFor(() => {
      expect(window.open).toHaveBeenCalledWith('blob:mock-url', '_blank', 'noopener')
    })
    expect(stockApi.bcfPdf).toHaveBeenCalledWith(42)
    // Pas de message d'erreur.
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('retombe sur un téléchargement direct si la popup est bloquée', async () => {
    stockApi.bcfPdf.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    window.open = vi.fn(() => null) // popup bloquée
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    await waitFor(() => { expect(clickSpy).toHaveBeenCalled() })
    clickSpy.mockRestore()
  })

  it('refuse honnêtement une réponse qui n\'est pas un PDF (HTML d\'erreur)', async () => {
    stockApi.bcfPdf.mockResolvedValue({
      data: new Blob(['<html>boom</html>'], { type: 'text/html' }),
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/n['’]a pas renvoyé de PDF/)
    expect(window.open).not.toHaveBeenCalled()
  })
})

describe('QS1 — PDF (interne) : la vraie erreur est affichée', () => {
  it('affiche le détail DRF lu depuis le Blob d\'erreur (plus de « PDF indisponible »)', async () => {
    stockApi.bcfPdf.mockRejectedValue({
      response: {
        status: 403,
        data: new Blob(
          [JSON.stringify({ detail: 'Réservé aux responsables et administrateurs.' })],
          { type: 'application/json' },
        ),
      },
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Réservé aux responsables et administrateurs.')
    expect(alert.textContent).not.toContain('PDF indisponible')
  })

  it('affiche un message réseau explicite quand le serveur est injoignable', async () => {
    stockApi.bcfPdf.mockRejectedValue(new Error('Network Error'))
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/injoignable/)
  })
})

describe('QS1 — messageErreurBlob (unitaire)', () => {
  it('parse un Blob JSON DRF', async () => {
    const err = {
      response: {
        status: 400,
        data: new Blob([JSON.stringify({ detail: 'Erreur métier.' })],
          { type: 'application/json' }),
      },
    }
    expect(await messageErreurBlob(err)).toBe('Erreur métier.')
  })

  it('403 sans corps lisible → message permission explicite', async () => {
    const err = {
      response: { status: 403, data: new Blob(['not json'], { type: 'text/plain' }) },
    }
    expect(await messageErreurBlob(err)).toMatch(/Accès refusé/)
  })

  it('accepte aussi une donnée déjà décodée (objet)', async () => {
    const err = { response: { status: 500, data: { detail: 'Erreur interne.' } } }
    expect(await messageErreurBlob(err)).toBe('Erreur interne.')
  })
})

// ── QS2 — « + Nouveau produit » dans le BCF (réservé Directeur/Commercial resp.) ─
const newBcf = { fournisseur: '', lignes: [{ produit: '', quantite: 1, prix_achat_unitaire: '' }] }

describe('QS2 — création produit inline dans le BCF', () => {
  it('rôle non autorisé (Magasinier) : bouton « Nouveau produit » absent', () => {
    renderDetail({ bcf: newBcf, produits: [] }, { role_nom: 'Magasinier', permissions: [] })
    expect(screen.queryByLabelText('Nouveau produit')).toBeNull()
  })

  it('rôle autorisé (Directeur) : bouton présent, crée + dépose sur la ligne avec prix d\'achat', async () => {
    stockApi.createProduit.mockResolvedValue({
      data: { id: 55, nom: 'Module test', prix_vente: 5000, prix_achat: 3200, is_archived: false },
    })
    renderDetail({ bcf: newBcf, produits: [] }, { role_nom: 'Directeur', permissions: ['stock_creer'] })
    fireEvent.click(screen.getByLabelText('Nouveau produit'))
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Module test' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    // La ligne pointe désormais sur le nouveau produit (nom affiché dans le picker).
    await waitFor(() => expect(screen.getByText('Module test')).toBeInTheDocument())
    // Prix d'achat U. (interne) pré-rempli depuis prix_achat renvoyé par le serveur.
    await waitFor(() => expect(screen.getByDisplayValue('3200')).toBeInTheDocument())
  })

  it('rôle autorisé (Commercial responsable) : bouton présent', () => {
    renderDetail({ bcf: newBcf, produits: [] },
      { role_nom: 'Commercial responsable', permissions: ['stock_creer'] })
    expect(screen.getByLabelText('Nouveau produit')).toBeInTheDocument()
  })
})

// ── QS4 — Envoyer WhatsApp / email (grisés sans contact, reflètent ENVOYE) ──
const fournisseursAvecContact = [
  { id: 1, nom: 'Fourni Plus', telephone: '+212600000001', email: 'contact@fourni.ma' },
]
const fournisseursSansContact = [{ id: 1, nom: 'Fourni Muet', telephone: '', email: '' }]

describe('QS4 — envois fournisseur WhatsApp / email', () => {
  it('fournisseur avec téléphone + email : les deux boutons sont actifs', () => {
    renderDetail({ fournisseurs: fournisseursAvecContact })
    expect(screen.getByRole('button', { name: /Envoyer par WhatsApp/ })).toBeEnabled()
    expect(screen.getByRole('button', { name: /Envoyer par email/ })).toBeEnabled()
  })

  it('fournisseur sans contact : les deux boutons sont grisés avec un tooltip', () => {
    renderDetail({ fournisseurs: fournisseursSansContact })
    const wa = screen.getByRole('button', { name: /Envoyer par WhatsApp/ })
    const mail = screen.getByRole('button', { name: /Envoyer par email/ })
    expect(wa).toBeDisabled()
    expect(mail).toBeDisabled()
    expect(wa).toHaveAttribute('title', expect.stringMatching(/pas de numéro/))
    expect(mail).toHaveAttribute('title', expect.stringMatching(/pas d['’]adresse email/))
  })

  it('WhatsApp : appelle QS3, ouvre le lien wa.me et reflète l\'état ENVOYE', async () => {
    stockApi.whatsappBcf.mockResolvedValue({
      data: { wa_url: 'https://wa.me/212600000001?text=x', statut: 'envoye' },
    })
    const onSaved = vi.fn()
    renderDetail({ fournisseurs: fournisseursAvecContact, onSaved })
    fireEvent.click(screen.getByRole('button', { name: /Envoyer par WhatsApp/ }))
    await waitFor(() => expect(stockApi.whatsappBcf).toHaveBeenCalledWith(42))
    expect(window.open).toHaveBeenCalledWith('https://wa.me/212600000001?text=x', '_blank', 'noopener')
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('email : appelle QS3 et affiche la confirmation', async () => {
    stockApi.envoyerEmailBcf.mockResolvedValue({
      data: { detail: 'Email envoyé à contact@fourni.ma.', statut: 'envoye' },
    })
    const onSaved = vi.fn()
    renderDetail({ fournisseurs: fournisseursAvecContact, onSaved })
    fireEvent.click(screen.getByRole('button', { name: /Envoyer par email/ }))
    await waitFor(() => expect(stockApi.envoyerEmailBcf).toHaveBeenCalledWith(42))
    expect(await screen.findByText(/Email envoyé à contact@fourni\.ma/)).toBeInTheDocument()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })
})

// ── ZPUR11 — annulation avec motif obligatoire + réouverture ────────────────
describe('ZPUR11 — annulation (motif obligatoire) et réouverture', () => {
  it('MotifAnnulationModal refuse un motif vide', () => {
    const onConfirm = vi.fn()
    render(<MotifAnnulationModal onClose={() => {}} onConfirm={onConfirm} busy={false} />,
      { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /Confirmer l'annulation/ }))
    expect(screen.getByRole('alert').textContent).toMatch(/motif est obligatoire/)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('MotifAnnulationModal transmet le motif saisi', () => {
    const onConfirm = vi.fn()
    render(<MotifAnnulationModal onClose={() => {}} onConfirm={onConfirm} busy={false} />,
      { wrapper: makeWrapper() })
    fireEvent.change(screen.getByLabelText('Motif'), { target: { value: 'Erreur de saisie' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmer l'annulation/ }))
    expect(onConfirm).toHaveBeenCalledWith('Erreur de saisie')
  })

  it('« Annuler le BC » ouvre la modale de motif puis appelle annulerBcf(id, motif)', async () => {
    stockApi.annulerBcf.mockResolvedValue({ data: {} })
    const onSaved = vi.fn()
    renderDetail({ bcf: { ...bcf, statut: 'brouillon' }, onSaved })
    fireEvent.click(screen.getByRole('button', { name: /Annuler le BC/ }))
    fireEvent.change(screen.getByLabelText('Motif'), { target: { value: 'Commande erronée' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmer l'annulation/ }))
    await waitFor(() => expect(stockApi.annulerBcf).toHaveBeenCalledWith(42, 'Commande erronée'))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('un BCF ANNULE affiche « Réouvrir » qui appelle rouvrirBcf', async () => {
    stockApi.rouvrirBcf.mockResolvedValue({ data: {} })
    renderDetail({ bcf: { ...bcf, statut: 'annule' } })
    fireEvent.click(screen.getByRole('button', { name: /Réouvrir/ }))
    await waitFor(() => expect(stockApi.rouvrirBcf).toHaveBeenCalledWith(42))
  })
})

// ── ZPUR4 — duplication ──────────────────────────────────────────────────────
describe('ZPUR4 — dupliquer un BCF', () => {
  it('le bouton Dupliquer appelle dupliquerBcf(id)', async () => {
    stockApi.dupliquerBcf.mockResolvedValue({ data: { id: 99 } })
    const onSaved = vi.fn()
    renderDetail({ onSaved })
    fireEvent.click(screen.getByRole('button', { name: /Dupliquer/ }))
    await waitFor(() => expect(stockApi.dupliquerBcf).toHaveBeenCalledWith(42))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })
})

// ── ZPUR1 — facturation directe (lignes « sur commande ») ───────────────────
describe('ZPUR1 — facturer directement (politique sur commande)', () => {
  it('sans ligne « sur commande » : le bouton est absent', () => {
    renderDetail({
      bcf: { ...bcf, lignes: [{ id: 1, produit: 7, quantite: 2, prix_achat_unitaire: 100 }] },
      produits: [{ id: 7, politique_facturation_achat: 'sur_reception' }],
    })
    expect(screen.queryByRole('button', { name: /Facturer \(sur commande\)/ })).toBeNull()
  })

  it('avec une ligne « sur commande » : le bouton facture directement le BCF', async () => {
    stockApi.facturerBcf.mockResolvedValue({ data: { reference: 'FF-2026-0001' } })
    renderDetail({
      bcf: { ...bcf, lignes: [{ id: 1, produit: 7, quantite: 2, prix_achat_unitaire: 100 }] },
      produits: [{ id: 7, politique_facturation_achat: 'sur_commande' }],
    })
    const btn = screen.getByRole('button', { name: /Facturer \(sur commande\)/ })
    fireEvent.click(btn)
    await waitFor(() => expect(stockApi.facturerBcf).toHaveBeenCalledWith(42))
    expect(await screen.findByText(/FF-2026-0001/)).toBeInTheDocument()
  })
})

// ── WIR191 — réviser un BCF envoyé/reçu (XPUR18), Note ne perd plus la saisie ─
describe('WIR191 — réviser un BCF déjà envoyé/reçu', () => {
  const bcfEnvoye = {
    id: 77, reference: 'BCF-2026-07-0077', statut: 'envoye', fournisseur: 1,
    date_commande: '2026-07-01', date_livraison_prevue: '2026-07-15', note: 'note initiale',
    lignes: [{ id: 501, produit: 7, produit_nom: 'Module test', quantite: 2, prix_achat_unitaire: 100, quantite_recue: 0 }],
  }

  it('« Enregistrer »/« Envoyer au fournisseur » sont absents à l\'état envoyé (seul « Réviser » est proposé)', () => {
    renderDetail({ bcf: bcfEnvoye })
    expect(screen.getByRole('button', { name: 'Réviser' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enregistrer' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Envoyer au fournisseur/ })).toBeNull()
  })

  it('la Note est verrouillée hors mode Réviser (elle ne peut plus perdre une saisie sans bouton pour l\'enregistrer)', () => {
    renderDetail({ bcf: bcfEnvoye })
    expect(screen.getByLabelText('Note')).toBeDisabled()
  })

  it('« Réviser » déverrouille lignes/dates/note et enregistre via reviserBcf — jamais updateBonCommandeFournisseur', async () => {
    stockApi.reviserBcf.mockResolvedValue({ data: { ...bcfEnvoye, revision: 1, reapprobation_requise: false } })
    const onSaved = vi.fn()
    renderDetail({ bcf: bcfEnvoye, onSaved })

    fireEvent.click(screen.getByRole('button', { name: 'Réviser' }))
    const note = screen.getByLabelText('Note')
    expect(note).toBeEnabled()
    fireEvent.change(note, { target: { value: 'note révisée' } })
    fireEvent.change(screen.getByDisplayValue('2'), { target: { value: '5' } })

    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la révision' }))
    await waitFor(() => expect(stockApi.reviserBcf).toHaveBeenCalledWith(77, expect.objectContaining({
      note: 'note révisée',
      lignes: [expect.objectContaining({ id: 501, quantite: 5 })],
    })))
    expect(stockApi.updateBonCommandeFournisseur).not.toHaveBeenCalled()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(await screen.findByText('Révision enregistrée.')).toBeInTheDocument()
  })

  it('affiche le drapeau reapprobation_requise renvoyé par le serveur', async () => {
    stockApi.reviserBcf.mockResolvedValue({ data: { ...bcfEnvoye, reapprobation_requise: true } })
    renderDetail({ bcf: bcfEnvoye })
    fireEvent.click(screen.getByRole('button', { name: 'Réviser' }))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la révision' }))
    expect(await screen.findByText(/une nouvelle approbation est requise/)).toBeInTheDocument()
  })

  it('« Annuler la révision » restaure les valeurs d\'origine sans appeler le serveur', () => {
    renderDetail({ bcf: bcfEnvoye })
    fireEvent.click(screen.getByRole('button', { name: 'Réviser' }))
    fireEvent.change(screen.getByLabelText('Note'), { target: { value: 'brouillon perdu' } })

    fireEvent.click(screen.getByRole('button', { name: 'Annuler la révision' }))
    expect(screen.getByLabelText('Note')).toHaveValue('note initiale')
    expect(screen.getByLabelText('Note')).toBeDisabled()
    expect(stockApi.reviserBcf).not.toHaveBeenCalled()
  })

  it('un BCF en brouillon ne propose pas « Réviser » (seul Enregistrer standard s\'applique)', () => {
    renderDetail({ bcf: { ...bcfEnvoye, statut: 'brouillon' } })
    expect(screen.queryByRole('button', { name: 'Réviser' })).toBeNull()
  })
})

// ── WIR220 — accusé de commande fournisseur (XPUR7) + BCF similaires/
// historique des prix (XPUR11/XPUR13) ──────────────────────────────────────
describe('WIR220 — accusé de commande fournisseur (confirmer)', () => {
  const bcfEnvoye = {
    id: 88, reference: 'BCF-2026-07-0088', statut: 'envoye', fournisseur: 1,
    date_livraison_prevue: '2026-08-01',
    lignes: [{ id: 601, produit: 7, produit_nom: 'Module test', quantite: 2, prix_achat_unitaire: 100 }],
  }

  it('sans accusé : affiche le formulaire (date + n° de confirmation)', () => {
    renderDetail({ bcf: bcfEnvoye })
    expect(screen.getByLabelText('Date confirmée')).toBeInTheDocument()
    expect(screen.getByLabelText('N° de confirmation (optionnel)')).toBeInTheDocument()
  })

  it('refuse d\'enregistrer sans date confirmée', () => {
    renderDetail({ bcf: bcfEnvoye })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer l'accusé/ }))
    expect(screen.getByRole('alert').textContent).toMatch(/date confirmée .* est requise/)
    expect(stockApi.confirmerBcf).not.toHaveBeenCalled()
  })

  it('enregistre l\'accusé sans jamais envoyer date_livraison_prevue (jamais écrasée)', async () => {
    stockApi.confirmerBcf.mockResolvedValue({
      data: { date_confirmee_fournisseur: '2026-08-05', numero_confirmation_fournisseur: 'CONF-42' },
    })
    const onSaved = vi.fn()
    renderDetail({ bcf: bcfEnvoye, onSaved })

    fireEvent.change(screen.getByLabelText('Date confirmée'), { target: { value: '2026-08-05' } })
    fireEvent.change(screen.getByLabelText('N° de confirmation (optionnel)'), { target: { value: 'CONF-42' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer l'accusé/ }))

    await waitFor(() => expect(stockApi.confirmerBcf).toHaveBeenCalledWith(88, {
      date_confirmee_fournisseur: '2026-08-05',
      numero_confirmation_fournisseur: 'CONF-42',
    }))
    expect(await screen.findByText(/Confirmé pour le/)).toBeInTheDocument()
    expect(screen.getByText(/CONF-42/)).toBeInTheDocument()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('un BCF déjà accusé affiche la date confirmée en lecture seule (jamais un second formulaire)', () => {
    renderDetail({
      bcf: { ...bcfEnvoye, date_confirmee_fournisseur: '2026-08-05', numero_confirmation_fournisseur: 'CONF-9' },
    })
    expect(screen.getByText(/Confirmé pour le/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Date confirmée')).toBeNull()
  })

  it('le bloc « Accusé de commande » n\'apparaît pas sur un BCF reçu ou brouillon', () => {
    renderDetail({ bcf: { ...bcfEnvoye, statut: 'recu' } })
    expect(screen.queryByText('Accusé de commande fournisseur')).toBeNull()
  })
})

describe('WIR220 — historique des prix (popover ligne)', () => {
  const bcfAvecLigne = {
    id: 89, reference: 'BCF-89', statut: 'recu', fournisseur: 1,
    lignes: [{ id: 701, produit: 7, produit_nom: 'Module test', quantite: 3, prix_achat_unitaire: 150 }],
  }

  it('ouvre l\'historique des prix de la ligne et affiche les achats passés', async () => {
    stockApi.getHistoriquePrixBcf.mockResolvedValue({
      data: [{ bon_commande_id: 1, reference: 'BCF-1', date: '2026-06-01T10:00:00Z', prix_achat_unitaire: 140, quantite: 5 }],
    })
    renderDetail({ bcf: bcfAvecLigne })
    fireEvent.click(screen.getByRole('button', { name: 'Historique des prix' }))
    await waitFor(() => expect(stockApi.getHistoriquePrixBcf).toHaveBeenCalledWith(7, 1))
    expect(await screen.findByText(/BCF-1/)).toBeInTheDocument()
  })

  it('affiche un état vide honnête quand il n\'y a aucun historique', async () => {
    stockApi.getHistoriquePrixBcf.mockResolvedValue({ data: [] })
    renderDetail({ bcf: bcfAvecLigne })
    fireEvent.click(screen.getByRole('button', { name: 'Historique des prix' }))
    expect(await screen.findByText(/Aucun historique d'achat/)).toBeInTheDocument()
  })
})

describe('WIR220 — BCF ouverts similaires (encart création)', () => {
  it('affiche les BCF similaires à la création une fois un fournisseur choisi', async () => {
    stockApi.getBcfSimilaires.mockResolvedValue({
      data: [{ id: 5, reference: 'BCF-5', statut: 'envoye' }],
    })
    renderDetail({
      bcf: { fournisseur: '1', lignes: [{ produit: '', quantite: 1, prix_achat_unitaire: '' }] },
      fournisseurs: [{ id: 1, nom: 'Fourni Plus' }],
    })
    await waitFor(() => expect(stockApi.getBcfSimilaires).toHaveBeenCalledWith('1', []))
    expect(await screen.findByText(/BCF-5/)).toBeInTheDocument()
  })

  it('sans fournisseur choisi : aucun appel réseau ni encart', () => {
    renderDetail({ bcf: { fournisseur: '', lignes: [{ produit: '', quantite: 1, prix_achat_unitaire: '' }] } })
    expect(stockApi.getBcfSimilaires).not.toHaveBeenCalled()
    expect(screen.queryByText(/BCF ouverts similaires/)).toBeNull()
  })
})

describe('WIR220 — dépassements listés (liste des BCF, filtre « En retard »)', () => {
  it('un filtre « En retard » apparaît quand le serveur signale des dépassements et filtre la liste', async () => {
    stockApi.getBonsCommandeFournisseur.mockResolvedValue({
      data: [
        { id: 10, reference: 'BCF-10', fournisseur_nom: 'À temps SARL', statut: 'envoye', lignes: [], total_achat: '100' },
        { id: 11, reference: 'BCF-11', fournisseur_nom: 'En retard SARL', statut: 'envoye', lignes: [], total_achat: '200' },
      ],
    })
    stockApi.getBcfEnRetard.mockResolvedValue({ data: [{ id: 11 }] })
    render(<BonsCommandeFournisseur />, { wrapper: makeWrapper() })

    const grid = await screen.findByRole('grid', { name: 'Bons de commande fournisseur' })
    await waitFor(() => expect(within(grid).getByText('BCF-10')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /En retard \(1\)/ }))
    const filtered = await screen.findByRole('grid', { name: 'Bons de commande fournisseur' })
    expect(within(filtered).getByText('BCF-11')).toBeInTheDocument()
    expect(within(filtered).queryByText('BCF-10')).toBeNull()
  })

  it('sans dépassement, aucun bouton « En retard » ne s\'affiche', async () => {
    stockApi.getBonsCommandeFournisseur.mockResolvedValue({
      data: [{ id: 10, reference: 'BCF-10', fournisseur_nom: 'À temps SARL', statut: 'envoye', lignes: [], total_achat: '100' }],
    })
    stockApi.getBcfEnRetard.mockResolvedValue({ data: [] })
    render(<BonsCommandeFournisseur />, { wrapper: makeWrapper() })

    await screen.findByRole('grid', { name: 'Bons de commande fournisseur' })
    expect(screen.queryByRole('button', { name: /En retard/ })).toBeNull()
  })
})

describe('WIR220 — rapport « Achats hors contrat »', () => {
  it('génère le rapport filtré (fournisseur + période) et liste les écarts', async () => {
    stockApi.getBonsCommandeFournisseur.mockResolvedValue({ data: [] })
    stockApi.getFournisseurs.mockResolvedValue({ data: [{ id: 1, nom: 'Fourni Plus' }] })
    stockApi.getAchatsHorsContrat.mockResolvedValue({
      data: [{
        ligne_id: 1, reference: 'BCF-1', fournisseur_nom: 'Fourni Plus', produit_nom: 'Module',
        prix_convenu: '100.00', prix_saisi: '130.00', ecart: '30.00',
      }],
    })
    render(<BonsCommandeFournisseur />, { wrapper: makeWrapper() })

    await screen.findByRole('grid', { name: 'Bons de commande fournisseur' })
    await userEvent.click(screen.getByRole('button', { name: /Achats hors contrat/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Générer' }))

    await waitFor(() => expect(stockApi.getAchatsHorsContrat).toHaveBeenCalled())
    expect(await within(dialog).findByText('Module')).toBeInTheDocument()
  })
})
