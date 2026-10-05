import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import ClientForm from './ClientForm'
import { exempleContrat } from '../../test/fixtures/contractSamples'

// CIQ422 — les PATCH envoyés par le formulaire, capturés (aucun réseau).
const envois = vi.hoisted(() => ({ liste: [], rejet: null }))
vi.mock('../../features/crm/store/crmSlice', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    updateClient: (args) => () => {
      envois.liste.push(args)
      return { unwrap: () => (envois.rejet ? Promise.reject(envois.rejet) : Promise.resolve({})) }
    },
  }
})

/* J139 — ClientForm rendu dans une ResponsiveDialog (modale ≥768 px / tiroir bas
   <768 px). On vérifie que le formulaire s'ouvre dans un [role="dialog"] avec le
   bon titre et le bon bouton de soumission, aux deux points de rupture. */

// VX170 — ClientForm compose désormais useFormSafety → useNavigationGuard →
// useConfirmDialog() ; le mock doit exposer ce hook (sinon la garde plante au
// montage). Repli neutre : aucune confirmation réelle n'est déclenchée ici.
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({ confirm: vi.fn(), confirmDelete: vi.fn() }),
}))
vi.mock('../../components/AttachmentsPanel', () => ({ default: () => null }))

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia(false) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderForm = (props = {}) => {
  const store = configureStore({ reducer: { crm: crmReducer } })
  return render(
    <Provider store={store}>
      <ClientForm onClose={vi.fn()} {...props} />
    </Provider>,
  )
}

describe('ClientForm (J139 — ResponsiveDialog)', () => {
  it('ouvre la modale « Nouveau client » sur bureau', () => {
    mockMatchMedia(false)
    renderForm()
    expect(document.querySelector('[role="dialog"]')).toBeInTheDocument()
    expect(screen.getByText('Nouveau client')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Créer le client' })).toBeInTheDocument()
  })

  it('rend le tiroir bas (Sheet) sous 768 px', () => {
    mockMatchMedia(true)
    renderForm()
    expect(document.querySelector('[role="dialog"]')).toBeInTheDocument()
    expect(screen.getByText('Nouveau client')).toBeInTheDocument()
  })

  it('affiche « Mettre à jour » en édition', () => {
    mockMatchMedia(false)
    renderForm({ client: { id: 9, nom: 'Dupont', type_client: 'particulier' } })
    expect(screen.getByText('Éditer le client')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mettre à jour' })).toBeInTheDocument()
  })
})

/* CIQ422 — l'identité d'une ENTREPRISE (siège, à l'attention de, TVA
   récupérable) et ce qui manque, sur les fixtures du contrat partagé
   `client_entreprise.json` (CIQ402) — aucun mock inventé. */
describe('CIQ422 — ClientForm : identité d’une entreprise', () => {
  const entreprise = exempleContrat('crm', 'client_entreprise')
  const nomPropre = exempleContrat('crm', 'client_entreprise', 'exemple_nom_propre')
  const conflit = exempleContrat('crm', 'client_entreprise', 'exemple_conflit')

  afterEach(() => { envois.liste = []; envois.rejet = null })

  it('les champs de l’entreprise sont rendus avec les valeurs servies', () => {
    mockMatchMedia(false)
    renderForm({ client: entreprise })
    expect(document.getElementById('cf-contact-nom').value).toBe('Karim Exemple')
    expect(document.getElementById('cf-contact-fonction').value).toBe('Directeur')
    expect(document.getElementById('cf-tva-recuperable').value).toBe('oui')
    expect(document.getElementById('cf-adresse-siege')).toBeInTheDocument()
  })

  it('entreprise sans ICE → bandeau non bloquant tiré d’identite_entreprise', () => {
    mockMatchMedia(false)
    renderForm({ client: nomPropre })
    expect(screen.getByTestId('cf-ice-manquant').textContent).toBe(
      'ICE manquant — demandé au devis, obligatoire à l’acceptation en ligne et à la facture.')
    cleanup()
    renderForm({ client: entreprise })
    expect(screen.queryByTestId('cf-ice-manquant')).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher : même objet envoyé', async () => {
    mockMatchMedia(false)
    renderForm({ client: entreprise })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(envois.liste).toHaveLength(1))
    const premier = envois.liste[0].data
    expect(premier).toMatchObject({
      contact_nom: 'Karim Exemple', contact_fonction: 'Directeur', tva_recuperable: 'oui',
      adresse_siege: null, ice: '000000000000000',
    })
    cleanup()
    renderForm({ client: { ...entreprise, ...premier } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(envois.liste).toHaveLength(2))
    expect(envois.liste[1].data).toEqual(premier)
  })

  it('le conflit d’identité s’affiche sous le champ ICE', async () => {
    mockMatchMedia(false)
    envois.rejet = conflit
    renderForm({ client: entreprise })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    expect(await screen.findByTestId('cf-ice-conflit')).toHaveTextContent(conflit.message)
  })

  it('un particulier est rendu à l’identique (aucun champ ni clé ajoutés)', async () => {
    mockMatchMedia(false)
    renderForm({ client: { id: 9, nom: 'Dupont', type_client: 'particulier' } })
    expect(document.getElementById('cf-contact-nom')).toBeNull()
    expect(document.getElementById('cf-tva-recuperable')).toBeNull()
    expect(screen.queryByTestId('cf-ice-manquant')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(envois.liste).toHaveLength(1))
    for (const cle of ['adresse_siege', 'contact_nom', 'contact_fonction', 'tva_recuperable']) {
      expect(envois.liste[0].data).not.toHaveProperty(cle)
    }
  })
})
