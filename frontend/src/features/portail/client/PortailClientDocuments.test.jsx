import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import {
  documentContrat, exempleContrat, reponseContrat,
} from '../../../test/fixtures/contractSamples'
import { formatDate } from '../../../lib/format'

/* ADOC135 — « Mes documents » : version + date en vigueur (contrat
   mes_documents.json), téléchargement, dépôt multipart, refus lecture seule. */

vi.mock('../../../api/portailApi', () => ({
  default: {
    documents: {
      liste: vi.fn(),
      deposer: vi.fn(),
      telechargerUrl: (id) => `/api/django/portail/mes-documents/${id}/telecharger/`,
    },
  },
}))

import portailApi from '../../../api/portailApi'
import PortailClientDocuments from './PortailClientDocuments.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const contrat = documentContrat('portail', 'mes_documents')

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PortailClientDocuments /></ThemeProvider></MemoryRouter>,
  )
}

function choisirFichier() {
  const f = new File(['%PDF-1.4'], 'justif.pdf', { type: 'application/pdf' })
  fireEvent.change(screen.getByLabelText('Fichier'), { target: { files: [f] } })
  return f
}

describe('PortailClientDocuments — ADOC135', () => {
  it('affiche version et date de VERSION, et le lien de téléchargement', async () => {
    portailApi.documents.liste.mockResolvedValue(reponseContrat('portail', 'mes_documents'))
    const doc = exempleContrat('portail', 'mes_documents').results[0]
    renderPage()
    await screen.findByText(doc.nom)
    expect(screen.getByTestId(`document-version-${doc.id}`).textContent)
      .toBe(`Version ${doc.version_numero} — mis à jour le ${formatDate(doc.version_date)}`)
    expect(screen.getByRole('link', { name: 'Télécharger' }).getAttribute('href'))
      .toBe(`/api/django/portail/mes-documents/${doc.id}/telecharger/`)
  })

  it('un document sans version n’affiche aucune ligne de version', async () => {
    portailApi.documents.liste.mockResolvedValue(
      reponseContrat('portail', 'mes_documents', 'exemple_sans_version'))
    renderPage()
    await screen.findByText('Plan de toiture')
    expect(screen.queryByTestId('document-version-78')).toBeNull()
  })

  it('dépose un justificatif en multipart puis recharge la liste', async () => {
    portailApi.documents.liste.mockResolvedValue(reponseContrat('portail', 'mes_documents'))
    portailApi.documents.deposer.mockResolvedValue({ data: contrat.depot.reponses['201'] })
    renderPage()
    await screen.findByText('Facture ONEE septembre')
    const f = choisirFichier()
    fireEvent.click(screen.getByRole('button', { name: 'Déposer' }))
    await waitFor(() => expect(portailApi.documents.deposer).toHaveBeenCalledTimes(1))
    const corps = portailApi.documents.deposer.mock.calls[0][0]
    expect(corps).toBeInstanceOf(FormData)
    expect(corps.get('fichier')).toBeInstanceOf(File)
    expect(corps.get('fichier').name).toBe(f.name)
    expect(corps.get('type_document')).toBe('autre')
    expect(await screen.findByText(/Justificatif déposé/)).toBeTruthy()
    await waitFor(() => expect(portailApi.documents.liste).toHaveBeenCalledTimes(2))
  })

  it('un compte lecture seule voit le refus du serveur', async () => {
    portailApi.documents.liste.mockResolvedValue(reponseContrat('portail', 'mes_documents'))
    portailApi.documents.deposer.mockRejectedValue({
      response: { status: 403, data: contrat.depot.reponses['403'] },
    })
    renderPage()
    await screen.findByText('Facture ONEE septembre')
    choisirFichier()
    fireEvent.click(screen.getByRole('button', { name: 'Déposer' }))
    expect(await screen.findByText(contrat.depot.reponses['403'].detail)).toBeTruthy()
  })
})
