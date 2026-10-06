import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* CIQ313 — Paramètres › Documents : « CGV commerciales » et « CGV
   industrielles » à côté des CGV standard (`cgv_par_mode`, CIQ218). Aucun
   texte suggéré ; variante vide = « reprend les CGV standard » ; enregistrer →
   rouvrir → enregistrer sans toucher = objet serveur identique. */

const { getDocumentTemplates, updateDocumentTemplates } = vi.hoisted(() => ({
  getDocumentTemplates: vi.fn(),
  updateDocumentTemplates: vi.fn(),
}))

vi.mock('../../api/parametresApi', () => ({
  default: { getDocumentTemplates, updateDocumentTemplates },
}))
vi.mock('../../ui/confirm', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

import DocumentsSection from './DocumentsSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Forme de `DocumentTemplatesSerializer.validate_cgv_par_mode` (CIQ218).
const CGV_SERVEUR = {
  commercial: { titre: 'Conditions commerciales', bullets: ['Réserve de propriété.', '{echeancier}'] },
  industriel: { titre: '', bullets: ['{retenue}', '{tva_note}'] },
}

async function rendre(cgvParMode = {}) {
  getDocumentTemplates.mockResolvedValue({ data: {
    cgv_titre: '', cgv_bullets: null, cgv_par_mode: cgvParMode, version: 3,
  } })
  render(<DocumentsSection />)
  await screen.findByTestId('cgv-pro')
}

describe('CIQ313 — CGV commerciales et industrielles', () => {
  it('deux éditeurs sur le même écran, vides : aucun texte suggéré', async () => {
    await rendre()
    expect(screen.getByTestId('cgv-pro-commercial')).toBeInTheDocument()
    expect(screen.getByTestId('cgv-pro-industriel')).toBeInTheDocument()
    expect(screen.queryAllByLabelText(/^Puce \d+ — CGV/)).toHaveLength(0)
    expect(screen.getByTestId('cgv-pro-commercial-vide'))
      .toHaveTextContent('reprend les CGV standard')
    expect(screen.getByTestId('cgv-pro-industriel-vide'))
      .toHaveTextContent('reprend les CGV standard')
    expect(screen.getAllByText(/\{echeancier\}/).length).toBeGreaterThan(0)
  })

  it('saisie → enregistrement : corps cgv_par_mode conforme au serveur', async () => {
    const user = userEvent.setup()
    updateDocumentTemplates.mockResolvedValue({ data: { version: 4, cgv_par_mode: {
      industriel: { titre: 'Industriel', bullets: ['Réception et réserves.'] } } } })
    await rendre()
    await user.click(screen.getByRole('button', { name: /Ajouter une puce — CGV industrielles/ }))
    await user.type(screen.getByLabelText('Puce 1 — CGV industrielles'), 'Réception et réserves.')
    await user.type(screen.getByLabelText('Titre — CGV industrielles'), 'Industriel')
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/ }))
    await waitFor(() => expect(updateDocumentTemplates).toHaveBeenCalledTimes(1))
    const corps = updateDocumentTemplates.mock.calls[0][0]
    expect(corps.cgv_par_mode).toEqual({
      industriel: { titre: 'Industriel', bullets: ['Réception et réserves.'] },
    })
    expect(corps.cgv_bullets).toBeNull()
  })

  it('variantes vides : rien n’est envoyé pour ce mode (repli sur le standard)', async () => {
    const user = userEvent.setup()
    updateDocumentTemplates.mockResolvedValue({ data: { version: 4, cgv_par_mode: {} } })
    await rendre()
    await user.click(screen.getByRole('button', { name: /Ajouter une puce — CGV commerciales/ }))
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/ }))
    await waitFor(() => expect(updateDocumentTemplates).toHaveBeenCalledTimes(1))
    expect(updateDocumentTemplates.mock.calls[0][0].cgv_par_mode).toEqual({})
  })

  it('enregistrer → rouvrir → enregistrer sans rien toucher = objet serveur identique', async () => {
    const user = userEvent.setup()
    updateDocumentTemplates.mockResolvedValue({ data: { version: 4, cgv_par_mode: CGV_SERVEUR } })
    await rendre(CGV_SERVEUR)
    expect(screen.getByLabelText('Puce 1 — CGV commerciales')).toHaveValue('Réserve de propriété.')
    expect(screen.getByLabelText('Titre — CGV commerciales')).toHaveValue('Conditions commerciales')
    expect(screen.queryByTestId('cgv-pro-commercial-vide')).toBeNull()
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/ }))
    await waitFor(() => expect(updateDocumentTemplates).toHaveBeenCalledTimes(1))
    expect(updateDocumentTemplates.mock.calls[0][0].cgv_par_mode).toEqual(CGV_SERVEUR)
    await user.click(screen.getByRole('button', { name: /Enregistr/ }))
    await waitFor(() => expect(updateDocumentTemplates).toHaveBeenCalledTimes(2))
    expect(updateDocumentTemplates.mock.calls[1][0].cgv_par_mode).toEqual(CGV_SERVEUR)
  })

  it('serveur sans cgv_par_mode : les éditeurs ne s’affichent pas', async () => {
    getDocumentTemplates.mockResolvedValue({ data: { cgv_titre: '', version: 1 } })
    render(<DocumentsSection />)
    await screen.findByLabelText('Puce 1')
    expect(screen.queryByTestId('cgv-pro')).toBeNull()
  })
})
