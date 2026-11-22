/* ACAL559 — l'écran Réglages « Systèmes de fixation ».

   Réponses tirées de l'échantillon COMMITTÉ
   `contract_samples/calepinage_systemes_fixation.json` (liste, vide, 201,
   refus 400 nommé) — jamais une charge écrite à la main. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render as renderBrut, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ConfirmProvider } from '../../../providers/ConfirmProvider'

const espions = vi.hoisted(() => ({
  liste: vi.fn(), creer: vi.fn(), modifier: vi.fn(), supprimer: vi.fn(),
  hasPermission: vi.fn(),
}))
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    systemesFixation: Object.fromEntries(['liste', 'creer', 'modifier', 'supprimer']
      .map((methode) => [methode, (...a) => espions[methode](...a)])),
  },
}))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => espions.hasPermission(code),
}))

const { default: ReglagesFixation } = await import('./ReglagesFixation')

const render = (ui) => renderBrut(<ConfirmProvider>{ui}</ConfirmProvider>)
const contrat = (variante) => exempleContrat('calepinage', 'calepinage_systemes_fixation', variante)
const LISTE = contrat('exemple')
const VIDE = contrat('exemple_vide')
const CREATION = contrat('exemple_creation')
const REFUS = contrat('exemple_refus')

const saisir = (id, valeur) => fireEvent.change(document.getElementById(id), { target: { value: valeur } })

beforeEach(() => {
  vi.clearAllMocks()
  espions.hasPermission.mockReturnValue(true)
})
afterEach(() => { cleanup() })

describe('ReglagesFixation (ACAL559)', () => {
  it('catalogue vide : le dit, aucune ligne pré-remplie', async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    render(<ReglagesFixation />)
    expect(await screen.findByTestId('acal559-vide')).toHaveTextContent(
      'Aucun système de fixation : la nomenclature n’est pas calculée tant qu’aucun n’est saisi.')
    expect(document.getElementById('acal559-code').value).toBe('')
    expect(document.getElementById('acal559-provenance').value).toBe('')
  })

  it('création 201 ⇒ le corps porte les champs saisis et la liste est relue', async () => {
    espions.liste
      .mockResolvedValueOnce({ data: VIDE })
      .mockResolvedValueOnce({ data: { systemes: [CREATION.reponse.systeme] } })
    espions.creer.mockResolvedValue({ data: CREATION.reponse })
    render(<ReglagesFixation />)
    await screen.findByTestId('acal559-vide')

    const corps = CREATION.corps
    saisir('acal559-code', corps.code)
    saisir('acal559-libelle', corps.libelle)
    saisir('acal559-fabricant', corps.fabricant)
    saisir('acal559-mode-pose', corps.mode_pose)
    saisir('acal559-provenance', corps.provenance)
    const [rail, lest] = corps.composants
    saisir('acal559-c0-libelle', rail.libelle)
    saisir('acal559-c0-unite', rail.unite)
    saisir('acal559-c0-source', rail.source)
    saisir('acal559-c0-base', rail.regle.base)
    saisir('acal559-c0-facteur', '2')
    saisir('acal559-c0-libelle-facteur', rail.regle.libelle_facteur)
    fireEvent.click(screen.getByText('Ajouter un composant'))
    saisir('acal559-c1-role', lest.role)
    saisir('acal559-c1-libelle', lest.libelle)
    saisir('acal559-c1-unite', lest.unite)
    saisir('acal559-c1-source', lest.source)
    saisir('acal559-c1-base', lest.regle.base)
    saisir('acal559-c1-libelle-facteur', lest.regle.libelle_facteur)
    fireEvent.click(screen.getByTestId('acal559-enregistrer'))

    await waitFor(() => expect(espions.creer).toHaveBeenCalledTimes(1))
    const [envoye] = espions.creer.mock.calls[0]
    expect(envoye.provenance).toBe(corps.provenance)
    expect(envoye.mode_pose).toBe('toit_plat_leste')
    expect(envoye.composants[0]).toMatchObject({ role: 'rail', produit_id: null,
      regle: { base: 'longueur_rangees_m', facteur: 2, libelle_facteur: 'rails par rangée' } })
    // Facteur déclaré (libellé) mais non saisi : `null`, jamais un nombre de repli.
    expect(envoye.composants[1].regle).toEqual({ base: 'modules', facteur: null, libelle_facteur: 'plaques par module' })
    expect(envoye).not.toHaveProperty('company')
    expect(await screen.findByTestId(`acal559-systeme-${CREATION.reponse.systeme.id}`))
      .toHaveTextContent(CREATION.reponse.systeme.libelle)
  })

  it('un 400 se pose sous le champ nommé (provenance, composants[1].source)', async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    espions.creer.mockRejectedValue({ response: { status: 400, data: REFUS.corps } })
    render(<ReglagesFixation />)
    await screen.findByTestId('acal559-vide')
    fireEvent.click(screen.getByText('Ajouter un composant'))
    fireEvent.click(screen.getByTestId('acal559-enregistrer'))

    expect(await screen.findByTestId('acal559-erreur-provenance')).toHaveTextContent(REFUS.corps.provenance[0])
    expect(screen.getByTestId('acal559-erreur-composants[1].source')).toHaveTextContent(REFUS.corps['composants[1].source'][0])
    expect(screen.getByTestId('acal559-erreur-composants[0].regle')).toHaveTextContent('surface')
  })

  it('lecture seule sans calepinage_gerer : la liste, aucun formulaire ni bouton', async () => {
    espions.hasPermission.mockReturnValue(false)
    espions.liste.mockResolvedValue({ data: LISTE })
    render(<ReglagesFixation />)
    const systeme = LISTE.systemes[0]
    expect(await screen.findByTestId(`acal559-systeme-${systeme.id}`)).toHaveTextContent(systeme.libelle)
    expect(screen.queryByTestId('acal559-formulaire')).toBeNull()
    expect(screen.queryByTestId(`acal559-basculer-${systeme.id}`)).toBeNull()
  })

  it('« Désactiver » passe actif à faux', async () => {
    espions.liste.mockResolvedValue({ data: LISTE })
    espions.modifier.mockResolvedValue({ data: {} })
    render(<ReglagesFixation />)
    const systeme = LISTE.systemes[0]
    fireEvent.click(await screen.findByTestId(`acal559-basculer-${systeme.id}`))
    await waitFor(() => expect(espions.modifier).toHaveBeenCalledWith(systeme.id, { actif: false }))
  })

  it('les nombres de la règle se saisissent en step="any", formulaire noValidate', async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    render(<ReglagesFixation />)
    await screen.findByTestId('acal559-vide')
    expect(screen.getByTestId('acal559-formulaire')).toHaveAttribute('novalidate')
    for (const id of ['acal559-c0-facteur', 'acal559-c0-diviseur', 'acal559-c0-produit']) {
      expect(document.getElementById(id)).toHaveAttribute('step', 'any')
    }
  })

  it('« Grandeur de base » propose les quatre bases d’orientation (ACAL569)', async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    render(<ReglagesFixation />)
    await screen.findByTestId('acal559-vide')
    const options = Object.fromEntries([...document.getElementById('acal559-c0-base').options]
      .map((o) => [o.value, o.textContent]))
    expect(options).toMatchObject({
      modules_portrait: 'modules en portrait', modules_paysage: 'modules en paysage',
      rangees_portrait: 'rangées en portrait', rangees_paysage: 'rangées en paysage',
    })
  })

  it('propose le rôle « Échafaudage » et les bases d’ACAL578 / ACAL598 (REP-fixation-ecran)', async () => {
    espions.liste.mockResolvedValue({ data: VIDE })
    render(<ReglagesFixation />)
    await screen.findByTestId('acal559-vide')
    const roles = [...document.getElementById('acal559-c0-role').options].map((o) => o.value)
    expect(roles).toContain('echafaudage')
    const bases = [...document.getElementById('acal559-c0-base').options].map((o) => o.value)
    for (const base of ['tables', 'poteaux', 'pieds', 'longueur_egouts_m', 'facade_egouts_m2',
      'role:echafaudage']) {
      expect(bases).toContain(base)
    }
  })
})
