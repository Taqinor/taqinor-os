import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { OPTIONS_TELECHARGEMENT } from '../documents/telechargement'

/* ============================================================================
   CALX371 — export/import du PROJET COMPLET, prouvés SUR LE CONTRAT.
   ----------------------------------------------------------------------------
   AUCUN MOCK ÉCRIT À LA MAIN (PACT13) pour les FORMES échangées : le fichier
   projet et la réponse d'import sont ceux des contrats committés
   `export_projet.json` (CALX312/CALX370) et `calepinage_projet_json.json`
   (CALX370) — les mêmes que le test backend affirme. Les invariants durs du
   « Done » :
     1. rien n'est écrit avant confirmation explicite (`apercu: true` d'abord,
        `apercu: false` seulement au clic « Confirmer l'import ») ;
     2. un refus serveur NOMME le chemin du champ fautif, sous le champ de
        dépôt ;
     3. l'export télécharge TEL QUEL le document du contrat.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  get: vi.fn(), exporterProjet: vi.fn(), importerProjet: vi.fn(), downloadBlob: vi.fn(),
}))

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      get: mocks.get,
      exporterProjet: mocks.exporterProjet,
      importerProjet: mocks.importerProjet,
    },
  },
}))

vi.mock('../../../utils/downloadBlob', () => ({ downloadBlob: mocks.downloadBlob }))

const { default: Projet } = await import('./PanneauProjet')
const { documentContrat, exempleContrat } = await import('../../../test/fixtures/contractSamples')

const EXPORT_EXEMPLE = exempleContrat('calepinage', 'export_projet')
const IMPORT_DOC = documentContrat('calepinage', 'calepinage_projet_json')
const IMPORT_EXEMPLE = exempleContrat('calepinage', 'calepinage_projet_json')
const IMPORT_APERCU = exempleContrat('calepinage', 'calepinage_projet_json', 'exemple_apercu')
const REFUS_CHAMP = IMPORT_DOC.exemple_refus_champ

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: { lead: { id: 12 }, client: null } })
})
afterEach(() => cleanup())

const rendre = (props = {}) => render(
  <MemoryRouter><Projet calepinageId={7} {...props} /></MemoryRouter>,
)

const fichierProjet = (contenu = EXPORT_EXEMPLE) =>
  new File([JSON.stringify(contenu)], 'projet.json', { type: 'application/json' })

describe('Projet — export (CALX371)', () => {
  it('télécharge TEL QUEL le document du contrat `export_projet.json`', async () => {
    const blob = new Blob([JSON.stringify(EXPORT_EXEMPLE)], { type: 'application/json' })
    mocks.exporterProjet.mockResolvedValue({ data: blob })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-projet-telecharger'))

    await waitFor(() => expect(mocks.downloadBlob).toHaveBeenCalledTimes(1))
    expect(mocks.exporterProjet).toHaveBeenCalledWith(7, OPTIONS_TELECHARGEMENT)
    expect(mocks.downloadBlob.mock.calls[0][0]).toBe(blob)
    expect(mocks.downloadBlob.mock.calls[0][1]).toBe('calepinage-7-projet.json')
  })

  it('un export trop long dit le délai en français (R3)', async () => {
    mocks.exporterProjet.mockRejectedValue({ code: 'ECONNABORTED' })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-projet-telecharger'))
    expect(await screen.findByTestId('cal-projet-export-erreur')).toHaveTextContent("Le serveur n'a pas fini de préparer ce document en 2 minutes.")
  })

  it('un refus d’export affiche son motif (corps BLOB relu)', async () => {
    mocks.exporterProjet.mockRejectedValue({
      response: { data: new Blob([JSON.stringify({ resultat: 'Aucun résultat à exporter.' })]) },
    })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-projet-telecharger'))
    expect(await screen.findByTestId('cal-projet-export-erreur'))
      .toHaveTextContent('Aucun résultat à exporter.')
  })
})

describe('Projet — import, un APERÇU avant toute écriture (CALX371)', () => {
  it('choisir un fichier envoie `apercu: true`, rattaché au LEAD du calepinage ouvert, et n’écrit rien', async () => {
    mocks.importerProjet.mockResolvedValue({ data: IMPORT_APERCU })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(7))

    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())

    await waitFor(() => expect(mocks.importerProjet).toHaveBeenCalledTimes(1))
    expect(mocks.importerProjet).toHaveBeenCalledWith({
      projet: EXPORT_EXEMPLE, lead: 12, apercu: true,
    })
    expect(await screen.findByTestId('cal-projet-apercu')).toBeInTheDocument()
    expect(screen.getByTestId('cal-projet-apercu-modules'))
      .toHaveTextContent(String(IMPORT_APERCU.modules))
    expect(screen.getByTestId('cal-projet-apercu-variantes'))
      .toHaveTextContent(IMPORT_APERCU.variante_retenue)
    expect(screen.getByTestId('cal-projet-apercu-repris')).toHaveTextContent('Conception (roof_layout)')
    // Écrit false : aucun résultat affiché, et le serveur n'a reçu qu'UN appel.
    expect(screen.queryByTestId('cal-projet-resultat')).toBeNull()
    expect(mocks.importerProjet).toHaveBeenCalledTimes(1)
  })

  it('rattache au CLIENT quand le calepinage ouvert n’a pas de lead', async () => {
    mocks.get.mockResolvedValue({ data: { lead: null, client: { id: 41 } } })
    mocks.importerProjet.mockResolvedValue({ data: IMPORT_APERCU })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(7))

    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())

    await waitFor(() => expect(mocks.importerProjet).toHaveBeenCalledWith({
      projet: EXPORT_EXEMPLE, client: 41, apercu: true,
    }))
  })

  it('confirmer renvoie `apercu: false` et affiche le calepinage CRÉÉ', async () => {
    mocks.importerProjet
      .mockResolvedValueOnce({ data: IMPORT_APERCU })
      .mockResolvedValueOnce({ data: IMPORT_EXEMPLE })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())
    await screen.findByTestId('cal-projet-apercu')

    fireEvent.click(screen.getByTestId('cal-projet-confirmer'))

    await waitFor(() => expect(mocks.importerProjet).toHaveBeenCalledTimes(2))
    expect(mocks.importerProjet).toHaveBeenNthCalledWith(2, {
      projet: EXPORT_EXEMPLE, lead: 12, apercu: false,
    })
    expect(await screen.findByTestId('cal-projet-resultat'))
      .toHaveTextContent(`calepinage n° ${IMPORT_EXEMPLE.calepinage}`)
    expect(screen.queryByTestId('cal-projet-apercu')).toBeNull()
  })

  it('affiche les saisies reprises et les produits ignores (ACAL244)', async () => {
    mocks.importerProjet.mockResolvedValue({ data: IMPORT_APERCU })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())
    await screen.findByTestId('cal-projet-apercu')
    expect(screen.getByTestId('cal-projet-apercu-repris')).toHaveTextContent('Saisies électriques')
    for (const item of IMPORT_APERCU.ignores) {
      expect(screen.getByTestId('cal-projet-apercu-ignores')).toHaveTextContent(item.motif)
    }
    expect(screen.getByTestId('cal-projet-apercu-clone')).toHaveTextContent('pas un clone identique')
  })

  it('T4-X5-016 — l’aperçu d’un lead qui a déjà son calepinage ouvert est atteint et dit d’avance le refus', async () => {
    const avis = 'Confirmer l’import sera refusé : Ce lead a déjà un calepinage ouvert (#7) : ouvrez-le, ou créez '
      + 'une variante. Pour reprendre ce fichier, ouvrez ce calepinage et créez-y une variante, ou importez-le '
      + 'depuis un calepinage rattaché à un client.'
    mocks.importerProjet.mockResolvedValue({ data: { ...IMPORT_APERCU, avertissements: [avis] } })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())
    await screen.findByTestId('cal-projet-apercu')
    expect(screen.getByTestId('cal-projet-apercu-avertissements')).toHaveTextContent(avis)
  })

  it('propose Ouvrir le calepinage apres import (ACAL244)', async () => {
    mocks.importerProjet
      .mockResolvedValueOnce({ data: IMPORT_APERCU })
      .mockResolvedValueOnce({ data: IMPORT_EXEMPLE })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())
    await screen.findByTestId('cal-projet-apercu')
    fireEvent.click(screen.getByTestId('cal-projet-confirmer'))
    const lien = await screen.findByTestId('cal-projet-ouvrir')
    expect(lien).toHaveAttribute('href', `/calepinage/${IMPORT_EXEMPLE.calepinage}`)
  })

  it('annuler efface l’aperçu SANS jamais appeler le serveur en écriture', async () => {
    mocks.importerProjet.mockResolvedValue({ data: IMPORT_APERCU })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())
    await screen.findByTestId('cal-projet-apercu')

    fireEvent.click(screen.getByTestId('cal-projet-annuler'))

    expect(screen.queryByTestId('cal-projet-apercu')).toBeNull()
    expect(mocks.importerProjet).toHaveBeenCalledTimes(1) // le seul appel reste l'aperçu
  })

  it('un refus serveur NOMME le chemin du champ fautif, sous le champ de dépôt', async () => {
    mocks.importerProjet.mockRejectedValue({ response: { data: REFUS_CHAMP } })
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())

    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichierProjet())

    const [champ, motif] = Object.entries(REFUS_CHAMP)[0]
    const erreur = await screen.findByTestId('cal-projet-erreur')
    expect(erreur).toHaveTextContent(champ)
    expect(erreur).toHaveTextContent(motif)
  })

  it('un JSON illisible est refusé AVANT tout appel serveur', async () => {
    const utilisateur = userEvent.setup()
    rendre()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    const fichier = new File(['{ceci n\'est pas du JSON'], 'projet.json', { type: 'application/json' })

    await utilisateur.upload(await screen.findByTestId('cal-projet-fichier'), fichier)

    expect(await screen.findByTestId('cal-projet-erreur')).toHaveTextContent('JSON valide')
    expect(mocks.importerProjet).not.toHaveBeenCalled()
  })
})
