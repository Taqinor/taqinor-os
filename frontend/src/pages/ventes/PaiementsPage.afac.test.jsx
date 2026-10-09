import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* AFAC7 — écran d'import de relevé : toutes les lignes, 9 statuts nommés,
   avertissement « déjà importé », choix du candidat, lignes cochées/résolues
   transmises au commit, bilan par ligne. Les réponses simulées sont LUES dans
   les contrats serveur (jamais une forme recopiée). */

vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksVentesEcrans.js')).ventesApiPaiements())
vi.mock('../../hooks/useHasPermission', async () => ({ ...(await import('../../test/mocksVentesEcrans.js')).permissionsRefusees() }))

import ventesApi from '../../api/ventesApi'
import PaiementsPage from './PaiementsPage'

const ICI = dirname(fileURLToPath(import.meta.url))
const contrat = (nom) => JSON.parse(readFileSync(join(
  ICI, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'facturation',
  'contract_samples', nom), 'utf8'))

const DRY = contrat('releve_import_dry_run.json')
const COMMIT = contrat('releve_import_commit.json')

const fichier = () => new File(['a;b'], 'releve.csv', { type: 'text/csv' })

async function ouvrirApercu(apercu) {
  ventesApi.importReleveDryRun.mockResolvedValue({ data: apercu })
  render(<MemoryRouter initialEntries={['/ventes/paiements/import-releve']}><PaiementsPage /></MemoryRouter>)
  const dialog = await screen.findByRole('dialog')
  fireEvent.change(within(dialog).getByLabelText('Fichier du relevé'), { target: { files: [fichier()] } })
  fireEvent.click(within(dialog).getByRole('button', { name: /Aperçu/ }))
  await within(dialog).findByLabelText('Importer la ligne 2')
  return dialog
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getPaiements.mockResolvedValue({ data: [] })
})

describe('PaiementsPage — AFAC7 : import de relevé (revue, 9 statuts, sélection)', () => {
  it('nomme les 9 statuts du contrat : aucun statut brut affiché', async () => {
    const preview = DRY.statuts_ligne.map((statut, i) => ({
      ligne: i + 2, date: '2026-06-20', reference: 'R', libelle: 'L', montant: '10.00',
      statut, facture_id: null, facture_reference: null, candidats: [],
    }))
    const dialog = await ouvrirApercu({ ...DRY.exemple, preview, revue: [], total_rows: 9 })
    for (const brut of DRY.statuts_ligne) {
      expect(within(dialog).queryByText(brut)).toBeNull()
    }
    expect(within(dialog).getAllByRole('checkbox')).toHaveLength(9)
  })

  it('rend TOUTES les lignes (pagination au-delà de 50)', async () => {
    const preview = Array.from({ length: 120 }, (_, i) => ({
      ligne: i + 2, date: '2026-06-20', reference: 'R', montant: '1.00',
      statut: 'a_importer', facture_reference: 'FAC-1', candidats: [],
    }))
    const dialog = await ouvrirApercu({ ...DRY.exemple, preview, total_rows: 120 })
    expect(within(dialog).getAllByRole('checkbox')).toHaveLength(50)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Suivant' }))
    expect(within(dialog).getByLabelText('Importer la ligne 52')).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Suivant' }))
    expect(within(dialog).getByLabelText('Importer la ligne 121')).toBeInTheDocument()
  })

  it('le bandeau « déjà importé » s’affiche si deja_importe', async () => {
    const dialog = await ouvrirApercu({ ...DRY.exemple, deja_importe: true })
    expect(within(dialog).getByText(/déjà été importé/)).toBeInTheDocument()
  })

  it('doublon_import est décoché et non cochable', async () => {
    const preview = [
      { ligne: 2, statut: 'a_importer', montant: '1.00', facture_reference: 'FAC-1', candidats: [] },
      { ligne: 3, statut: 'doublon_import', montant: '1.00', facture_reference: null, candidats: [] },
    ]
    const dialog = await ouvrirApercu({ ...DRY.exemple, preview })
    expect(within(dialog).getByLabelText('Importer la ligne 2')).toBeChecked()
    const dup = within(dialog).getByLabelText('Importer la ligne 3')
    expect(dup).not.toBeChecked()
    expect(dup).toBeDisabled()
  })

  it('transmet la sélection : numéros cochés + ligne ambiguë résolue', async () => {
    ventesApi.importReleveCommit.mockResolvedValue({ data: COMMIT.exemple })
    const dialog = await ouvrirApercu(DRY.exemple)
    // La ligne ambiguë (3) n'est cochable qu'après le choix d'un candidat.
    expect(within(dialog).getByLabelText('Importer la ligne 3')).toBeDisabled()
    fireEvent.change(within(dialog).getByLabelText('Facture de la ligne 3'),
      { target: { value: 'FAC-2026-06-0014' } })
    expect(within(dialog).getByLabelText('Importer la ligne 3')).toBeChecked()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Importer' }))
    await waitFor(() => expect(ventesApi.importReleveCommit).toHaveBeenCalled())
    expect(ventesApi.importReleveCommit).toHaveBeenCalledWith(
      DRY.exemple.token,
      COMMIT.requete.lignes, // [2, {ligne: 3, facture_reference: 'FAC-2026-06-0014'}]
    )
  })

  it('le bilan liste chaque ligne ignorée avec sa raison nommée', async () => {
    ventesApi.importReleveCommit.mockResolvedValue({ data: COMMIT.exemple })
    const dialog = await ouvrirApercu(DRY.exemple)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Importer' }))
    const liste = await within(dialog).findByLabelText('Lignes ignorées')
    expect(within(liste).getByText(/Ligne 4 : Date illisible/)).toBeInTheDocument()
  })
})
