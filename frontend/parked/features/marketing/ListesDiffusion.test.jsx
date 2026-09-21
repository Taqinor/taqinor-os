import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { parseCsv, buildLignesImport } from './csvImport'

// ── Vitest ne ramasse que `*.test.jsx` (voir vitest.config.js) — la logique
// pure de `csvImport.js` est donc testée ICI plutôt que dans un fichier
// `.test.js` séparé (qui ne serait exécuté par aucun des deux runners).
describe('parseCsv (logique pure)', () => {
  it('parse un CSV simple avec en-têtes', () => {
    const { headers, rows } = parseCsv('email,nom\na@x.ma,Ahmed\nb@x.ma,Fatima')
    expect(headers).toEqual(['email', 'nom'])
    expect(rows).toEqual([['a@x.ma', 'Ahmed'], ['b@x.ma', 'Fatima']])
  })

  it('gère les champs entre guillemets contenant une virgule', () => {
    const { rows } = parseCsv('email,nom\na@x.ma,"Ahmed, fils"')
    expect(rows[0]).toEqual(['a@x.ma', 'Ahmed, fils'])
  })

  it('gère les guillemets échappés ("")', () => {
    const { rows } = parseCsv('nom\n"Le ""Grand"" Magasin"')
    expect(rows[0]).toEqual(['Le "Grand" Magasin'])
  })

  it('ignore les lignes vides et tolère CRLF', () => {
    const { headers, rows } = parseCsv('email\r\na@x.ma\r\n\r\nb@x.ma\r\n')
    expect(headers).toEqual(['email'])
    expect(rows).toEqual([['a@x.ma'], ['b@x.ma']])
  })

  it('un texte vide renvoie headers/rows vides', () => {
    expect(parseCsv('')).toEqual({ headers: [], rows: [] })
  })
})

describe('buildLignesImport (logique pure)', () => {
  const rows = [['a@x.ma', 'lead:1'], ['b@x.ma', ''], ['', 'lead:3']]

  it('projette destinataire/contact_ref selon le mapping', () => {
    const lignes = buildLignesImport(rows, { destinataire: 0, contact_ref: 1 })
    expect(lignes).toEqual([
      { destinataire: 'a@x.ma', contact_ref: 'lead:1' },
      { destinataire: 'b@x.ma', contact_ref: '' },
    ])
  })

  it('sans colonne destinataire mappée, renvoie un tableau vide', () => {
    expect(buildLignesImport(rows, { destinataire: '', contact_ref: 1 })).toEqual([])
  })

  it('contact_ref est optionnel', () => {
    const lignes = buildLignesImport(rows, { destinataire: 0, contact_ref: '' })
    expect(lignes).toEqual([
      { destinataire: 'a@x.ma', contact_ref: '' },
      { destinataire: 'b@x.ma', contact_ref: '' },
    ])
  })

  it('exclut les lignes sans destinataire', () => {
    const lignes = buildLignesImport(rows, { destinataire: 0 })
    expect(lignes.every(l => l.destinataire)).toBe(true)
    expect(lignes).toHaveLength(2)
  })
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  abonnes: vi.fn(),
  importer: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    listes: {
      list: mocks.list, create: mocks.create, abonnes: mocks.abonnes,
      importer: mocks.importer,
    },
  },
}))

import ListesDiffusion from './ListesDiffusion'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: [{ id: 1, nom: 'Prospects salon', nb_abonnes: 2 }],
  })
  mocks.abonnes.mockResolvedValue({
    data: [
      { id: 1, destinataire: 'a@x.ma', statut: 'inscrit', statut_display: 'Inscrit' },
      { id: 2, destinataire: 'b@x.ma', statut: 'desinscrit', statut_display: 'Désinscrit' },
    ],
  })
})

describe('ListesDiffusion', () => {
  it('affiche les listes et crée une nouvelle liste', async () => {
    mocks.create.mockResolvedValue({ data: {} })
    render(<ListesDiffusion />)
    expect(await screen.findByText('Prospects salon')).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('liste-nom'), { target: { value: 'Nouvelle liste' } })
    fireEvent.click(screen.getByTestId('liste-creer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      { nom: 'Nouvelle liste', description: '' }))
  })

  it('ouvrir une liste affiche ses abonnés avec leur statut', async () => {
    render(<ListesDiffusion />)
    await screen.findByText('Prospects salon')
    fireEvent.click(screen.getByTestId('liste-ouvrir'))
    await waitFor(() => expect(mocks.abonnes).toHaveBeenCalledWith(1, undefined))
    expect(await screen.findByText('a@x.ma')).toBeInTheDocument()
    expect(screen.getByText('b@x.ma')).toBeInTheDocument()
  })

  it('le filtre statut relance abonnes() avec ?statut=', async () => {
    render(<ListesDiffusion />)
    await screen.findByText('Prospects salon')
    fireEvent.click(screen.getByTestId('liste-ouvrir'))
    await screen.findByText('a@x.ma')
    fireEvent.change(screen.getByTestId('liste-filtre-statut'), { target: { value: 'inscrit' } })
    await waitFor(() => expect(mocks.abonnes).toHaveBeenCalledWith(1, { statut: 'inscrit' }))
  })

  it("importer un CSV mappé affiche le rapport ajoutés/doublons/ignorés-supprimés", async () => {
    mocks.importer.mockResolvedValue({
      data: { ajoutes: 48, doublons: 1, ignores_supprimes: 1 },
    })
    render(<ListesDiffusion />)
    await screen.findByText('Prospects salon')
    fireEvent.click(screen.getByTestId('liste-ouvrir'))
    await screen.findByText('a@x.ma')

    const file = new File(
      ['email,ref\na@x.ma,lead:1\nb@x.ma,lead:2'], 'contacts.csv', { type: 'text/csv' })
    const input = screen.getByTestId('liste-import-fichier')
    fireEvent.change(input, { target: { files: [file] } })

    const destSelect = await screen.findByTestId('liste-mapping-destinataire')
    fireEvent.change(destSelect, { target: { value: '0' } })
    const refSelect = screen.getByTestId('liste-mapping-contact-ref')
    fireEvent.change(refSelect, { target: { value: '1' } })

    fireEvent.click(screen.getByTestId('liste-lancer-import'))
    await waitFor(() => expect(mocks.importer).toHaveBeenCalledWith(1, [
      { destinataire: 'a@x.ma', contact_ref: 'lead:1' },
      { destinataire: 'b@x.ma', contact_ref: 'lead:2' },
    ]))
    const rapport = await screen.findByTestId('liste-import-rapport')
    expect(rapport).toHaveTextContent('Ajoutés : 48')
    expect(rapport).toHaveTextContent('Doublons : 1')
    expect(rapport).toHaveTextContent('Ignorés/supprimés : 1')
  })

  it("le bouton Importer reste désactivé sans colonne destinataire mappée", async () => {
    render(<ListesDiffusion />)
    await screen.findByText('Prospects salon')
    fireEvent.click(screen.getByTestId('liste-ouvrir'))
    await screen.findByText('a@x.ma')
    const file = new File(['email\na@x.ma'], 'c.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByTestId('liste-import-fichier'), { target: { files: [file] } })
    await screen.findByTestId('liste-lancer-import')
    expect(screen.getByTestId('liste-lancer-import')).toBeDisabled()
  })
})
