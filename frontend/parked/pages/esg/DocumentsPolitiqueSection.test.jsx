import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../api/esgApi', () => ({
  default: {
    documentsPolitique: {
      list: vi.fn(() => Promise.resolve({ data: [
        { id: 1, libelle: 'Charte éthique 2026', type_document: 'charte_ethique', type_document_display: 'Charte éthique', statut: 'brouillon', statut_display: 'Brouillon' },
      ] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
    },
  },
}))
vi.mock('../../api/recordsApi', () => ({
  default: { uploadAttachment: vi.fn(() => Promise.resolve({ data: { id: 9 } })) },
}))

import esgApi from '../../api/esgApi'
import recordsApi from '../../api/recordsApi'
import DocumentsPolitiqueSection from './DocumentsPolitiqueSection'

describe('DocumentsPolitiqueSection (WIR130)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les politiques déposées', async () => {
    render(<DocumentsPolitiqueSection />)
    expect(await screen.findByText('Charte éthique 2026')).toBeInTheDocument()
  })

  it('dépose une politique avec fichier (métadonnées + records.Attachment)', async () => {
    render(<DocumentsPolitiqueSection />)
    await screen.findByText('Charte éthique 2026')
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Politique diversité' } })
    const file = new File(['contenu'], 'politique.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('Fichier de politique'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: /Déposer/ }))
    await waitFor(() => expect(esgApi.documentsPolitique.create).toHaveBeenCalledWith({
      libelle: 'Politique diversité', type_document: 'charte_ethique',
    }))
    await waitFor(() => expect(recordsApi.uploadAttachment).toHaveBeenCalledWith(
      'esg.documentpolitiqueesg', 2, file))
  })
})
