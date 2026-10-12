// VNT73 (Groupe VNT, D-VNT-2) — « Prix négocié » : taper un prix TTC (ou une
// remise) sur une vente acceptée, lire l'aperçu SERVEUR (remise, factures
// annulées / reprises, reste), appliquer, puis « Faire signer l'avenant ».
// PACT11 : toutes les charges utiles viennent du contrat committé
// `ventes/devis_prix_negocie.json` (jamais un mock écrit à la main).
// Nouveau fichier car : composant neuf, sans module de test existant.
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../test/fixtures/contractSamples.js'

const CONTRAT = documentContrat('ventes', 'devis_prix_negocie')

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: { prixNegocie: vi.fn(), demanderSignatureAvenant: vi.fn() },
}))
vi.mock('../../ui/Toaster', async (importOriginal) => ({
  ...(await importOriginal()),
  toast: { success: vi.fn(), error: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import PrixNegocieDialog from './PrixNegocieDialog'

const DEVIS = {
  id: 7, reference: 'DEV-202610-0020', client_nom: 'Mme Alaoui', total_ttc: '54500.00',
  vente: { prix_convenu_ttc: '54500.00' },
}
const clone = (o) => JSON.parse(JSON.stringify(o))
const flush = (txt) => txt.replace(/[\s\u00a0\u202f]/g, '')

const mockMatchMedia = (mobile) => vi.stubGlobal('matchMedia', (media) => ({
  matches: mobile, media, onchange: null, dispatchEvent: () => false,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
}))

function monter(props = {}) {
  return render(<PrixNegocieDialog devis={DEVIS} onOpenChange={() => {}} {...props} />)
}

beforeEach(() => {
  mockMatchMedia(false)
  ventesApi.prixNegocie.mockImplementation((id, body) => Promise.resolve({
    data: clone(body.mode === 'appliquer' ? CONTRAT.reponse_appliquer_201 : CONTRAT.reponse_apercu_200),
  }))
  ventesApi.demanderSignatureAvenant.mockResolvedValue({ data: clone(CONTRAT.demander_signature.exemple) })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

const typer = async (user, label, v) => {
  const champ = screen.getByLabelText(label)
  await user.clear(champ)
  await user.type(champ, v)
}
const refus = (data, status = 400) =>
  ventesApi.prixNegocie.mockRejectedValue({ response: { status, data } })

describe('PrixNegocieDialog (VNT73)', () => {
  it('taper 49 000 sur 54 500 : aperçu serveur (remise 10,00 %, annulées, reste), corps en TEXTE', async () => {
    const user = userEvent.setup()
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49 000')
    const apercu = await screen.findByTestId('prix-negocie-apercu')
    expect(ventesApi.prixNegocie).toHaveBeenCalledWith(7, { prix_ttc: '49000', mode: 'apercu' })
    expect(flush(within(apercu).getByTestId('prix-negocie-remise').textContent)).toBe('10,00%')
    expect(within(apercu).getByTestId('prix-negocie-annulees').textContent).toContain('BROUILLON-318')
    expect(flush(within(apercu).getByTestId('prix-negocie-reste').textContent)).toMatch(/49.?000,00MAD/)
    expect(flush(within(apercu).getByTestId('prix-negocie-ecart').textContent)).toMatch(/5.?500,00/)
    expect(screen.getByTestId('prix-negocie-actuel').textContent.replace(/\s/g, '')).toMatch(/54.?500,00/)
  })

  it('une remise en MAD est convertie en prix_ttc (centimes entiers), jamais envoyée telle quelle', async () => {
    const user = userEvent.setup()
    monter()
    await typer(user, 'Remise (MAD)', '5500')
    await screen.findByTestId('prix-negocie-apercu')
    expect(ventesApi.prixNegocie).toHaveBeenCalledWith(7, { prix_ttc: '49000.00', mode: 'apercu' })
  })

  it('une remise en % part en remise_pct ; les trois champs s\'excluent (jamais saisie_double)', async () => {
    const user = userEvent.setup()
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    await screen.findByTestId('prix-negocie-apercu')
    await typer(user, 'Remise (%)', '10')
    expect(screen.getByLabelText('Prix négocié TTC (MAD)').value).toBe('')
    await waitFor(() => expect(ventesApi.prixNegocie).toHaveBeenLastCalledWith(7, { remise_pct: '10', mode: 'apercu' }))
  })

  it('Appliquer : mode appliquer, onApplied reçoit la réponse, la V2 est affichée', async () => {
    const user = userEvent.setup()
    const onApplied = vi.fn()
    monter({ onApplied })
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    await screen.findByTestId('prix-negocie-apercu')
    await user.click(screen.getByRole('button', { name: /Appliquer le prix négocié/ }))
    await screen.findByTestId('prix-negocie-resultat')
    expect(ventesApi.prixNegocie).toHaveBeenLastCalledWith(7, { prix_ttc: '49000', mode: 'appliquer' })
    expect(onApplied).toHaveBeenCalledWith(expect.objectContaining({ devis_v2: CONTRAT.reponse_appliquer_201.devis_v2 }))
    expect(screen.getByTestId('prix-negocie-resultat').textContent).toContain('DEV-202610-0021')
  })

  it("Appliquer n'est pas offert tant que l'aperçu ne correspond pas à la saisie", async () => {
    const user = userEvent.setup()
    monter()
    expect(screen.getByRole('button', { name: /Appliquer le prix négocié/ })).toBeDisabled()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    await screen.findByTestId('prix-negocie-apercu')
    expect(screen.getByRole('button', { name: /Appliquer le prix négocié/ })).toBeEnabled()
    await user.type(screen.getByLabelText('Prix négocié TTC (MAD)'), '5')
    expect(screen.getByRole('button', { name: /Appliquer le prix négocié/ })).toBeDisabled()
  })

  it.each([
    ['prix_non_rond', "Le prix négocié doit être un montant rond."],
    ['prix_superieur', 'Le prix négocié dépasse le prix actuel du devis.'],
    ['prix_identique', 'Le prix négocié est identique au prix actuel.'],
  ])('%s : message SOUS le champ fautif + bandeau « Corrigez : »', async (code, message) => {
    const user = userEvent.setup()
    refus(clone(CONTRAT.erreurs_400[code]))
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '48950')
    const champ = screen.getByLabelText('Prix négocié TTC (MAD)')
    await waitFor(() => expect(champ).toHaveAttribute('aria-invalid', 'true'))
    const sous = document.getElementById(champ.getAttribute('aria-describedby').split(' ')[0])
    expect(sous.textContent).toContain(message)
    expect(screen.getByTestId('prix-negocie-bandeau').textContent).toBe('Corrigez : Prix négocié TTC')
    expect(screen.queryByTestId('prix-negocie-apercu')).toBeNull()
  })

  it("l'erreur d'une remise % tapée s'affiche sous « Remise (%) », pas sous le prix", async () => {
    const user = userEvent.setup()
    refus(clone(CONTRAT.erreurs_400.prix_identique))
    monter()
    await typer(user, 'Remise (%)', '0')
    await waitFor(() => expect(screen.getByLabelText('Remise (%)')).toHaveAttribute('aria-invalid', 'true'))
    expect(screen.getByLabelText('Prix négocié TTC (MAD)')).not.toHaveAttribute('aria-invalid')
  })

  it('prix_inatteignable : les prix voisins sont proposés en boutons et relancent l\'aperçu', async () => {
    const user = userEvent.setup()
    refus(clone(CONTRAT.erreurs_400.prix_inatteignable))
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    const voisin = await screen.findByRole('button', { name: /48.?999,00/ })
    expect(screen.getByRole('button', { name: /49.?001,00/ })).toBeInTheDocument()
    ventesApi.prixNegocie.mockImplementation(() => Promise.resolve({ data: clone(CONTRAT.reponse_apercu_200) }))
    await user.click(voisin)
    await screen.findByTestId('prix-negocie-apercu')
    expect(ventesApi.prixNegocie).toHaveBeenLastCalledWith(7, { prix_ttc: '48999.00', mode: 'apercu' })
    expect(screen.getByLabelText('Prix négocié TTC (MAD)').value).toBe('48999.00')
  })

  it('approbation_requise : bandeau, aucun bouton Appliquer actif', async () => {
    const user = userEvent.setup()
    refus(clone(CONTRAT.erreurs_400.approbation_requise))
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '40000')
    const bandeau = await screen.findByTestId('prix-negocie-bandeau')
    expect(bandeau).toHaveAttribute('role', 'alert')
    expect(bandeau.textContent).toContain("approbation d'un responsable")
    expect(screen.getByRole('button', { name: /Appliquer le prix négocié/ })).toBeDisabled()
  })

  it('avoir_a_confirmer : montant de l\'avoir affiché, case à cocher, aperçu relancé avec confirmer_avoir', async () => {
    const user = userEvent.setup()
    refus({ ...clone(CONTRAT.erreurs_400.avoir_a_confirmer), montant_avoir: '5500.00' })
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    const zone = await screen.findByTestId('prix-negocie-avoir')
    expect(flush(zone.textContent)).toMatch(/5.?500,00MAD/)
    ventesApi.prixNegocie.mockImplementation((id, body) => Promise.resolve({
      data: clone(body.mode === 'appliquer' ? CONTRAT.reponse_appliquer_201 : CONTRAT.reponse_apercu_200),
    }))
    await user.click(screen.getByRole('switch', { name: /Confirmer l'avoir/ }))
    await screen.findByTestId('prix-negocie-apercu')
    expect(ventesApi.prixNegocie).toHaveBeenLastCalledWith(7, { prix_ttc: '49000', mode: 'apercu', confirmer_avoir: true })
    await user.click(screen.getByRole('button', { name: /Appliquer le prix négocié/ }))
    await screen.findByTestId('prix-negocie-resultat')
    expect(ventesApi.prixNegocie).toHaveBeenLastCalledWith(7, { prix_ttc: '49000', mode: 'appliquer', confirmer_avoir: true })
  })

  it('regularisation « avoir » et factures reprises de l\'aperçu sont lues du serveur', async () => {
    const user = userEvent.setup()
    const a = clone(CONTRAT.reponse_apercu_200)
    a.factures_reprises = [{ reference: 'FAC-202610-0004', total_ttc: '15000.00' }]
    a.regularisation = { type: 'avoir', montant: '2000.00' }
    ventesApi.prixNegocie.mockResolvedValue({ data: a })
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    const apercu = await screen.findByTestId('prix-negocie-apercu')
    expect(within(apercu).getByTestId('prix-negocie-reprises').textContent).toContain('FAC-202610-0004')
    expect(flush(within(apercu).getByTestId('prix-negocie-regularisation').textContent)).toMatch(/avoir.*2.?000,00MAD/i)
  })

  it('409 version_remplacee : bandeau avec la version à jour et « Ouvrir »', async () => {
    const user = userEvent.setup()
    const onOuvrirDevis = vi.fn()
    refus(clone(CONTRAT.erreurs_409.version_remplacee), 409)
    monter({ onOuvrirDevis })
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    const bandeau = await screen.findByTestId('prix-negocie-bandeau')
    expect(bandeau.textContent).toContain('remplacée')
    await user.click(screen.getByRole('button', { name: /Ouvrir DEV-202610-0022/ }))
    expect(onOuvrirDevis).toHaveBeenCalledWith(503)
  })

  it('409 vente_active_existante : « Ouvrir <ref> » vers la vente active', async () => {
    const user = userEvent.setup()
    const onOuvrirDevis = vi.fn()
    refus(clone(CONTRAT.erreurs_409.vente_active_existante), 409)
    monter({ onOuvrirDevis })
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    await user.click(await screen.findByRole('button', { name: /Ouvrir DEV-202610-0009/ }))
    expect(onOuvrirDevis).toHaveBeenCalledWith(410)
  })

  it('403 (Commercial) : le détail serveur est affiché en bandeau', async () => {
    const user = userEvent.setup()
    refus({ detail: "Vous n'avez pas la permission." }, 403)
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    expect((await screen.findByTestId('prix-negocie-bandeau')).textContent).toContain('permission')
  })

  it('« Faire signer l\'avenant » : UN appel, lien copié et affiché, tâche posée', async () => {
    const user = userEvent.setup()
    const ecrire = vi.fn().mockResolvedValue()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: ecrire }, configurable: true })
    monter()
    await typer(user, 'Prix négocié TTC (MAD)', '49000')
    await screen.findByTestId('prix-negocie-apercu')
    await user.click(screen.getByRole('button', { name: /Appliquer le prix négocié/ }))
    await screen.findByTestId('prix-negocie-resultat')
    await user.click(screen.getByRole('button', { name: /Faire signer l'avenant/ }))
    const lien = await screen.findByTestId('avenant-lien')
    expect(lien.value || lien.textContent).toBe(CONTRAT.demander_signature.exemple.share_link)
    expect(ecrire).toHaveBeenCalledWith(CONTRAT.demander_signature.exemple.share_link)
    expect(ventesApi.demanderSignatureAvenant).toHaveBeenCalledTimes(1)
    expect(ventesApi.demanderSignatureAvenant).toHaveBeenCalledWith(502)
    expect(screen.queryByRole('button', { name: /Faire signer l'avenant/ })).toBeNull()
  })

  it('téléphone (< 768 px) : rendu en tiroir bas, mêmes champs', async () => {
    mockMatchMedia(true)
    monter()
    expect(screen.getByLabelText('Prix négocié TTC (MAD)')).toBeInTheDocument()
    expect(document.querySelector('[data-testid="prix-negocie-form"]')).not.toBeNull()
  })
})
