import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* VEIL31 — Liste des annonceurs groupée par classe. Charges utiles = contrats
   committés veille_annonceur.json et veille_verdict.json (PACT13). */

const ANNONCEUR = documentContrat('adsengine', 'veille_annonceur').exemple
const APRES_VERDICT = documentContrat('adsengine', 'veille_verdict').exemple

// Variantes d'ÉTAT du même contrat (même forme, autre annonceur).
const DROP = { ...ANNONCEUR, id: 904, page_name: 'Trendy Shop', dropshipper: { ...ANNONCEUR.dropshipper, probable: 'oui' } }
const GEANT = { ...ANNONCEUR, id: 905, page_name: 'SHEIN', classe: 'place_de_marche' }
const INCERTAIN = { ...ANNONCEUR, id: 906, page_name: 'Noir Total', classe: 'incertain', verdict: null }

const mocks = vi.hoisted(() => ({ annonceurs: vi.fn(), verdict: vi.fn(), exportCsv: vi.fn() }))
vi.mock('./adsengineApi', () => ({ default: { veille: mocks } }))

import VeilleAnnonceurs from './VeilleAnnonceurs'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.annonceurs.mockResolvedValue({ data: { count: 4, results: [ANNONCEUR, DROP, GEANT, INCERTAIN] } })
  mocks.verdict.mockResolvedValue({ data: APRES_VERDICT })
})

describe('VeilleAnnonceurs', () => {
  it('groupes lus dans classes_disponibles : vendeurs, bruit, incertains ; géants à part', async () => {
    render(<VeilleAnnonceurs decouverteId={17} />)
    const vendeurs = await screen.findByTestId('ae-veille-groupe-vendeur')
    expect(mocks.annonceurs).toHaveBeenCalledWith({ page_size: 200, decouverte: 17 })
    expect(within(vendeurs).getByText('Maison Lilas')).toBeTruthy()
    expect(vendeurs.textContent).toContain(ANNONCEUR.classes_disponibles[0].libelle_fr)
    expect(within(screen.getByTestId('ae-veille-groupe-incertain')).getByText('Noir Total')).toBeTruthy()
    expect(screen.queryByTestId('ae-veille-groupe-place_de_marche')).toBeNull()
    fireEvent.click(screen.getByTestId('ae-veille-annonceurs-vue-places'))
    expect(within(screen.getByTestId('ae-veille-annonceurs-places')).getByText('SHEIN')).toBeTruthy()
  })

  it('étiquette « dropshipper probable » visible et filtre « dropshippers seulement »', async () => {
    render(<VeilleAnnonceurs />)
    expect(await screen.findByTestId('ae-veille-annonceur-dropshipper-904')).toBeTruthy()
    fireEvent.click(screen.getByTestId('ae-veille-filtre-dropshippers'))
    const vendeurs = screen.getByTestId('ae-veille-groupe-vendeur')
    expect(within(vendeurs).queryByText('Maison Lilas')).toBeNull()
    expect(within(vendeurs).getByText('Trendy Shop')).toBeTruthy()
  })

  it('motif, preuves et lien bibliothèque (clic humain, noopener) ; aucun access_token', async () => {
    const { container } = render(<VeilleAnnonceurs />)
    const lien = await screen.findByTestId('ae-veille-annonceur-lien-903')
    expect(lien.getAttribute('target')).toBe('_blank')
    expect(lien.getAttribute('rel')).toBe('noopener noreferrer')
    expect(screen.getByTestId('ae-veille-annonceur-motif-903').textContent).toContain(ANNONCEUR.verdict.motif_fr)
    expect(screen.getByTestId('ae-veille-annonceur-preuves-903')).toBeTruthy()
    expect(container.innerHTML).not.toMatch(/access_token/i)
  })

  it('« C’est du bruit » : classe à choisir (aucune par défaut), relecture serveur et historique', async () => {
    render(<VeilleAnnonceurs />)
    fireEvent.click(await screen.findByTestId('ae-veille-annonceur-bruit-903'))
    const choix = screen.getByTestId('ae-veille-annonceur-classe-bruit-903')
    expect(choix.value).toBe('')
    expect(screen.getByTestId('ae-veille-annonceur-confirmer-bruit-903').disabled).toBe(true)
    fireEvent.change(choix, { target: { value: 'place_de_marche' } })
    fireEvent.click(screen.getByTestId('ae-veille-annonceur-confirmer-bruit-903'))
    await waitFor(() => expect(mocks.verdict).toHaveBeenCalledWith(903, { classe: 'place_de_marche' }))
    fireEvent.click(screen.getByTestId('ae-veille-annonceurs-vue-places'))
    const decide = await screen.findByTestId('ae-veille-annonceur-decide-903')
    expect(decide.textContent).toContain('humain')
    expect(screen.getByTestId('ae-veille-annonceur-historique-903').textContent).toContain('règle')
  })

  it('erreur réseau : message sous le bouton, la liste reste affichée', async () => {
    mocks.verdict.mockRejectedValue(new Error('réseau'))
    render(<VeilleAnnonceurs />)
    fireEvent.click(await screen.findByTestId('ae-veille-annonceur-drop-oui-903'))
    expect(await screen.findByTestId('ae-veille-annonceur-erreur-903')).toBeTruthy()
    expect(mocks.verdict).toHaveBeenCalledWith(903, { classe: 'vendeur', dropshipper: 'oui' })
    expect(screen.getByText('Maison Lilas')).toBeTruthy()
  })

  it('bouton « Exporter en CSV »', async () => {
    mocks.exportCsv.mockRejectedValue({ response: { status: 403 } })
    render(<VeilleAnnonceurs />)
    fireEvent.click(await screen.findByTestId('ae-veille-annonceurs-export'))
    expect((await screen.findByTestId('ae-veille-annonceurs-erreur')).textContent).toContain('gestionnaire')
  })
})
