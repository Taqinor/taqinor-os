/* ACAL242 — l'écran de dépôt des gabarits (Réglages › Calepinage › Gabarits).

   Réponses tirées de l'échantillon COMMITTÉ
   `contract_samples/gabarits_dossier_reglementaire.json` (liste, 201, refus
   400 nommé, 409) — jamais une charge écrite à la main. */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render as renderBrut, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ConfirmProvider } from '../../../providers/ConfirmProvider'

const espions = vi.hoisted(() => ({
  liste: vi.fn(), creer: vi.fn(), modifier: vi.fn(), supprimer: vi.fn(),
  hasPermission: vi.fn(),
}))
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    gabarits: {
      liste: (...a) => espions.liste(...a),
      creer: (...a) => espions.creer(...a),
      modifier: (...a) => espions.modifier(...a),
      supprimer: (...a) => espions.supprimer(...a),
    },
  },
}))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => espions.hasPermission(code),
}))

const { default: ReglagesGabarits } = await import('./ReglagesGabarits')

const render = (ui) => renderBrut(<ConfirmProvider>{ui}</ConfirmProvider>)

const LISTE = exempleContrat('calepinage', 'gabarits_dossier_reglementaire')
const VIDE = exempleContrat('calepinage', 'gabarits_dossier_reglementaire', 'exemple_vide')
const CREE = exempleContrat('calepinage', 'gabarits_dossier_reglementaire', 'exemple_post_201')
const REFUS = exempleContrat('calepinage', 'gabarits_dossier_reglementaire', 'refus_400')
const DELETE = exempleContrat('calepinage', 'gabarits_dossier_reglementaire', 'delete')

beforeEach(() => {
  vi.clearAllMocks()
  espions.hasPermission.mockReturnValue(true)
})
afterEach(() => { cleanup() })

describe('ReglagesGabarits (ACAL242)', () => {
  it('liste les gabarits avec fichier présent ou manquant', async () => {
    const sansFichier = { ...LISTE.gabarits[0], id: 4, code: 'dp', fichiers: null }
    espions.liste.mockResolvedValue({ data: { gabarits: [...LISTE.gabarits, sansFichier] } })
    render(<ReglagesGabarits />)

    const premier = LISTE.gabarits[0]
    expect(await screen.findByTestId(`acal242-gabarit-${premier.id}`)).toHaveTextContent(premier.intitule)
    expect(screen.getByTestId(`acal242-fichier-${premier.id}`)).toHaveTextContent('fichier présent')
    expect(screen.getByTestId('acal242-fichier-4')).toHaveTextContent('fichier manquant')
  })

  it('cree un gabarit et affiche l\'erreur 400 sous le champ nomme', async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    espions.creer
      .mockRejectedValueOnce({ response: { status: 400, data: REFUS } })
      .mockResolvedValueOnce({ data: CREE })
    render(<ReglagesGabarits />)
    await screen.findByTestId('acal242-vide')

    await userEvent.selectOptions(document.getElementById('acal242-pays'), 'ma')
    await userEvent.type(document.getElementById('acal242-code'), 'raccordement_bt')
    await userEvent.type(document.getElementById('acal242-intitule'), 'Dossier de raccordement BT')
    await userEvent.type(document.getElementById('acal242-piece-0-code'), 'plan_masse')
    await userEvent.type(document.getElementById('acal242-piece-0-intitule'), 'Plan de masse')
    await userEvent.type(document.getElementById('acal242-piece-0-reference'), 'Cahier des charges')
    // Le serveur lit les OCTETS (PDF ou non) : son refus est servi tel quel.
    const fichier = new File(['PK'], 'gabarit.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByTestId('acal242-fichier'), fichier)
    await userEvent.click(screen.getByTestId('acal242-deposer'))

    // Le refus 400 est rendu SOUS le champ qu'il nomme (`fichier`).
    expect(await screen.findByTestId('acal242-erreur-fichier')).toHaveTextContent(REFUS.fichier)
    const [corps] = espions.creer.mock.calls[0]
    expect(corps.get('pays')).toBe('ma')
    expect(corps.get('code')).toBe('raccordement_bt')
    expect(JSON.parse(corps.get('pieces_attendues'))).toEqual([{
      code: 'plan_masse', intitule: 'Plan de masse',
      source_reference: 'Cahier des charges', obligatoire: true,
    }])
    expect(corps.get('fichier')).toBeInstanceOf(File)

    // Second envoi accepté : la liste est relue.
    espions.liste.mockResolvedValue({ data: LISTE })
    await userEvent.click(screen.getByTestId('acal242-deposer'))
    await waitFor(() => expect(espions.creer).toHaveBeenCalledTimes(2))
    expect(await screen.findByTestId(`acal242-gabarit-${LISTE.gabarits[0].id}`)).toBeInTheDocument()
  })

  it('un gabarit utilisé : le 409 nommé est rendu sur sa ligne', async () => {
    espions.liste.mockResolvedValue({ data: LISTE })
    espions.supprimer.mockRejectedValue({ response: { status: 409, data: DELETE.refus_409 } })
    render(<ReglagesGabarits />)
    const premier = LISTE.gabarits[0]
    await screen.findByTestId(`acal242-gabarit-${premier.id}`)

    await userEvent.click(screen.getByTestId(`acal242-supprimer-${premier.id}`))
    // AERR114 — boîte maison qui nomme le gabarit ; rien n'est supprimé avant.
    let boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent(premier.intitule)
    await userEvent.click(within(boite).getByRole('button', { name: 'Annuler' }))
    expect(espions.supprimer).not.toHaveBeenCalled()
    // CAD177 — le verrou anti-double-clic du Button tombe après 400 ms sans
    // rendu du bouton (Annuler ne le re-rend pas).
    await new Promise((r) => setTimeout(r, 450))
    await userEvent.click(screen.getByTestId(`acal242-supprimer-${premier.id}`))
    boite = await screen.findByRole('alertdialog')
    await userEvent.click(within(boite).getByRole('button', { name: 'Supprimer' }))

    expect(await screen.findByTestId(`acal242-erreur-gabarit-${premier.id}`))
      .toHaveTextContent(DELETE.refus_409.detail)
  })

  it('désactiver envoie actif: false puis relit la liste', async () => {
    espions.liste.mockResolvedValue({ data: LISTE })
    espions.modifier.mockResolvedValue({ data: {} })
    render(<ReglagesGabarits />)
    const premier = LISTE.gabarits[0]
    await screen.findByTestId(`acal242-gabarit-${premier.id}`)

    await userEvent.click(screen.getByTestId(`acal242-basculer-${premier.id}`))

    await waitFor(() => expect(espions.modifier).toHaveBeenCalledWith(premier.id, { actif: false }))
    await waitFor(() => expect(espions.liste).toHaveBeenCalledTimes(2))
  })

  it('sans calepinage_gerer : lecture seule, aucun formulaire', async () => {
    espions.hasPermission.mockReturnValue(false)
    espions.liste.mockResolvedValue({ data: LISTE })
    render(<ReglagesGabarits />)
    await screen.findByTestId(`acal242-gabarit-${LISTE.gabarits[0].id}`)
    expect(screen.queryByTestId('acal242-formulaire')).toBeNull()
    expect(screen.queryByTestId(`acal242-supprimer-${LISTE.gabarits[0].id}`)).toBeNull()
  })
})

describe('ReglagesGabarits (ACAL971) — des mots, un bouton en français', () => {
  const ouvrir = async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    render(<ReglagesGabarits />)
    await screen.findByTestId('acal242-vide')
  }

  it('le genre et le pays sont des listes ; plus de champ texte ni de code brut', async () => {
    await ouvrir()
    const genre = document.getElementById('acal242-genre')
    const pays = document.getElementById('acal242-pays')
    expect(genre.tagName).toBe('SELECT')
    expect(pays.tagName).toBe('SELECT')
    expect(screen.queryByText(/dp_mairie, enedis/)).toBeNull()
    expect(screen.queryByText(/code à deux lettres/)).toBeNull()
    expect(within(genre).getByRole('option', { name: 'Déclaration préalable en mairie' })).toBeInTheDocument()
    expect(within(pays).getByRole('option', { name: 'Maroc' })).toBeInTheDocument()
  })

  it('les genres de la liste sont ceux de GENRES_FRANCE (relus à la source)', async () => {
    const source = readFileSync(resolve(
      import.meta.dirname, '../../../../../backend/django_core/apps/calepinage/services/reglementaire.py',
    ), 'utf8')
    const bloc = source.split('GENRES_FRANCE = (')[1].split(/\)\r?\n\r?\n/)[0]
    const cles = [...bloc.matchAll(/\('([a-z_]+)',/g)].map((m) => m[1])
    await ouvrir()
    const valeurs = [...document.getElementById('acal242-genre').options]
      .map((o) => o.value).filter((v) => v && v !== '__autre')
    expect(valeurs).toEqual(cles)
  })

  it('le slug du genre part au serveur ; « Autre dossier… » ouvre « Nom du dossier »', async () => {
    await ouvrir()
    espions.creer.mockResolvedValue({ data: CREE })
    await userEvent.selectOptions(document.getElementById('acal242-genre'), 'dp_mairie')
    await userEvent.click(screen.getByTestId('acal242-deposer'))
    expect(espions.creer.mock.calls[0][0].get('genre')).toBe('dp_mairie')

    await userEvent.selectOptions(document.getElementById('acal242-genre'), '__autre')
    await userEvent.type(screen.getByLabelText('Nom du dossier'), 'Dépôt Société Générale')
    await userEvent.click(screen.getByTestId('acal242-deposer'))
    expect(espions.creer.mock.calls[1][0].get('genre')).toBe('depot_societe_generale')
  })

  it('le sélecteur de fichier est un bouton français relié à l’input masqué', async () => {
    await ouvrir()
    expect(document.querySelector('input[type="file"]')).toHaveAttribute('data-testid', 'acal242-fichier')
    expect(screen.queryByText('Choose File')).toBeNull()
    expect(screen.getByText('Choisir un fichier')).toHaveAttribute('for', 'acal242-fichier')
    expect(screen.getByText('Aucun fichier choisi')).toBeInTheDocument()
    await userEvent.upload(screen.getByTestId('acal242-fichier'),
      new File(['PK'], 'gabarit.pdf', { type: 'application/pdf' }))
    expect(screen.getByText('gabarit.pdf')).toBeInTheDocument()
  })
})
