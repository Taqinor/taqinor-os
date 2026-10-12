// VNT45 (Groupe VNT, D-VNT-3) — « Facturer la vente » : acompte (MAD ou %),
// totalité, solde, « déjà payé », aperçu lu du serveur. PACT11 : toutes les
// charges utiles viennent du contrat committé `ventes/devis_facturer.json`
// (jamais un mock écrit à la main) ; l'état « vente neuve » en est dérivé.
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../../test/fixtures/contractSamples.js'

const CONTRAT = documentContrat('ventes', 'devis_facturer')

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
  if (typeof Element.prototype.hasPointerCapture !== 'function') {
    Element.prototype.hasPointerCapture = () => false
    Element.prototype.releasePointerCapture = () => {}
    Element.prototype.scrollIntoView = () => {}
  }
})

vi.mock('../../../api/ventesApi', () => ({
  default: {
    apercuFacturerVente: vi.fn(),
    facturerVente: vi.fn(),
    emettreFacture: vi.fn(),
    genererPdfFacture: vi.fn(),
    telechargerPdfFacture: vi.fn(),
  },
}))
vi.mock('../../../ui/Toaster', async (importOriginal) => ({
  ...(await importOriginal()),
  toast: { success: vi.fn(), error: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import { toast } from '../../../ui/Toaster'
import FacturerVenteDialog from './FacturerVenteDialog'

const DEVIS = { id: 7, reference: 'DEV-2026-10-0003', client_nom: 'Mme Alaoui', total_ttc: '49000.00' }
const clone = (o) => JSON.parse(JSON.stringify(o))

// État « vente neuve » dérivé de l'aperçu du contrat : l'acompte est encore à faire.
function apercuNeuf() {
  const a = clone(CONTRAT.apercu_get.reponse_200)
  a.plan[0] = { ...a.plan[0], statut: 'a_faire' }
  a.plan[1] = { ...a.plan[1], statut: 'a_faire' }
  a.prochaine = { cle: 'acompte', libelle: 'Acompte', montant_ttc: a.plan[0].montant_ttc }
  a.vente = {
    prix_convenu_ttc: '49000.00', emis_ttc: '0.00', brouillons_ttc: '0.00', paye_ttc: '0.00',
    reste_a_facturer_ttc: '49000.00', reste_a_payer_ttc: '49000.00',
  }
  return a
}

function monter(props = {}) {
  return render(<FacturerVenteDialog devis={DEVIS} onOpenChange={() => {}} {...props} />)
}

// ACAL345 : pas de copie du helper matchMedia des tests crm — stub global minimal.
const mockMatchMedia = (mobile) => vi.stubGlobal('matchMedia', (media) => ({
  matches: mobile, media, onchange: null, dispatchEvent: () => false,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
}))

beforeEach(() => {
  mockMatchMedia(false)
  ventesApi.apercuFacturerVente.mockResolvedValue({ data: apercuNeuf() })
  ventesApi.facturerVente.mockResolvedValue({ data: CONTRAT.exemple })
  ventesApi.emettreFacture.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const attendreApercu = async () => { await screen.findByTestId('facturer-resume') }
const typer = async (user, label, v) => {
  const champ = screen.getByLabelText(label)
  await user.clear(champ)
  await user.type(champ, v)
}
const erreurPost = (data, status = 409) =>
  ventesApi.facturerVente.mockRejectedValue({ response: { status, data } })

describe('FacturerVenteDialog (VNT45)', () => {
  it("lit l'aperçu du GET : prix convenu, reste à facturer, acompte proposé", async () => {
    monter()
    await attendreApercu()
    expect(ventesApi.apercuFacturerVente).toHaveBeenCalledWith(7)
    const resume = screen.getByTestId('facturer-resume').textContent.replace(/\s/g, '')
    expect(resume).toMatch(/49.?000/)
    const propose = screen.getByTestId('facturer-acompte-propose').textContent.replace(/\s/g, '')
    expect(propose).toMatch(/14.?700/)
  })

  it('acompte 15000 + déjà payé ⇒ corps exact du contrat', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    monter({ onDone })
    await attendreApercu()
    await typer(user, 'Montant (MAD)', '15000')
    await user.click(screen.getByRole('switch', { name: 'Déjà payé' }))
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(ventesApi.facturerVente).toHaveBeenCalled())
    const [id, body] = ventesApi.facturerVente.mock.calls[0]
    expect(id).toBe(7)
    const aujourdhui = body.paiements[0].date_paiement
    expect(aujourdhui).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(body).toEqual({
      nature: 'acompte',
      montant_ttc: '15000',
      cle_attendue: 'acompte',
      emettre: true,
      paiements: [{ montant: '15000', date_paiement: aujourdhui, mode_paiement: 'virement', reference: '' }],
    })
    // Les clés du corps sont toutes connues du contrat.
    for (const k of Object.keys(body)) expect(Object.keys(CONTRAT.requete)).toContain(k)
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(CONTRAT.exemple))
  })

  it('un pourcentage remplace le montant (XOR)', async () => {
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await typer(user, 'Montant (MAD)', '15000')
    await typer(user, 'Pourcentage (%)', '30')
    expect(screen.getByLabelText('Montant (MAD)').value).toBe('')
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(ventesApi.facturerVente).toHaveBeenCalled())
    const body = ventesApi.facturerVente.mock.calls[0][1]
    expect(body.pourcentage).toBe('30')
    expect('montant_ttc' in body).toBe(false)
    expect(body.paiements).toBeUndefined()
  })

  it('onglet Totalité ⇒ nature complete, sans montant', async () => {
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await user.click(screen.getByRole('tab', { name: 'Totalité' }))
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(ventesApi.facturerVente).toHaveBeenCalled())
    expect(ventesApi.facturerVente.mock.calls[0][1]).toEqual({ nature: 'complete', emettre: true })
  })

  it('onglet Solde ouvert seulement quand le solde est la prochaine tranche', async () => {
    const a = apercuNeuf()
    a.plan = a.plan.map((t) => (t.cle === 'solde' ? t : { ...t, statut: 'emise' }))
    a.prochaine = { cle: 'solde', libelle: 'Solde', montant_ttc: '14400.00' }
    ventesApi.apercuFacturerVente.mockResolvedValue({ data: a })
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    expect(screen.getByRole('tab', { name: 'Solde' }).disabled).toBe(false)
    expect(screen.getByRole('tab', { name: 'Acompte' }).disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(ventesApi.facturerVente).toHaveBeenCalled())
    expect(ventesApi.facturerVente.mock.calls[0][1]).toEqual({
      nature: 'solde', cle_attendue: 'solde', emettre: true,
    })
  })

  it("Solde fermé tant que la prochaine tranche n'est pas le solde", async () => {
    monter()
    await attendreApercu()
    expect(screen.getByRole('tab', { name: 'Solde' }).disabled).toBe(true)
  })

  it('montant_depasse_reste : sous le champ Montant + bandeau qui le nomme', async () => {
    erreurPost(CONTRAT.erreurs_400.montant_depasse_reste, 400)
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await typer(user, 'Montant (MAD)', '99000')
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    const champ = screen.getByLabelText('Montant (MAD)')
    const sous = await screen.findByText(CONTRAT.erreurs_400.montant_depasse_reste.detail)
    expect(sous.closest('p').id).toBe(champ.getAttribute('aria-describedby'))
    expect(screen.getByTestId('facturer-bandeau').textContent).toBe('Corrigez : Montant')
  })

  it('erreur DRF dans une ligne de paiement : sous la date du paiement', async () => {
    ventesApi.facturerVente.mockRejectedValue({
      response: { status: 400, data: { paiements: [{ date_paiement: ['La date ne peut pas être dans le futur.'] }] } },
    })
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await typer(user, 'Montant (MAD)', '15000')
    await user.click(screen.getByRole('switch', { name: 'Déjà payé' }))
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    const msg = await screen.findByText('La date ne peut pas être dans le futur.')
    expect(msg.closest('p').id).toBe(screen.getByLabelText('Date du paiement').getAttribute('aria-describedby'))
    expect(screen.getByTestId('facturer-bandeau').textContent).toBe('Corrigez : Paiement 1 — date')
  })

  it('tranche_en_brouillon : bandeau + « Émettre le brouillon » puis rechargement', async () => {
    erreurPost(CONTRAT.erreurs_409.tranche_en_brouillon)
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    const bandeau = await screen.findByTestId('facturer-bandeau')
    expect(bandeau.getAttribute('role')).toBe('alert')
    expect(bandeau.textContent).toContain(CONTRAT.erreurs_409.tranche_en_brouillon.detail)
    await user.click(screen.getByRole('button', { name: 'Émettre le brouillon' }))
    await waitFor(() => expect(ventesApi.emettreFacture).toHaveBeenCalledWith(117))
    await waitFor(() => expect(ventesApi.apercuFacturerVente).toHaveBeenCalledTimes(2))
  })

  it('brouillons_a_remplacer : confirmation listant les brouillons puis remplacer_brouillons', async () => {
    erreurPost(CONTRAT.erreurs_409.brouillons_a_remplacer)
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await user.click(screen.getByRole('tab', { name: 'Totalité' }))
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    const zone = await screen.findByTestId('facturer-remplacer')
    expect(within(zone).getByText(/BROUILLON-117/)).toBeTruthy()
    ventesApi.facturerVente.mockResolvedValue({ data: CONTRAT.exemple })
    await user.click(within(zone).getByRole('button', { name: 'Remplacer les brouillons et facturer' }))
    await waitFor(() => expect(ventesApi.facturerVente).toHaveBeenCalledTimes(2))
    expect(ventesApi.facturerVente.mock.calls[1][1]).toMatchObject({
      nature: 'complete', remplacer_brouillons: true,
    })
  })

  it.each([
    ['deja_facture', 409, 'erreurs_409'],
    ['credit_hold', 403, 'erreurs_403'],
    ['sale_warning', 403, 'erreurs_403'],
  ])('%s : bandeau role=alert avec le message du serveur', async (code, status, groupe) => {
    erreurPost(CONTRAT[groupe][code], status)
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    const bandeau = await screen.findByTestId('facturer-bandeau')
    expect(bandeau.getAttribute('role')).toBe('alert')
    expect(bandeau.textContent).toContain(CONTRAT[groupe][code].detail)
  })

  it('facture émise : toast avec « Ouvrir le PDF » ; brouillon : aucune action PDF', async () => {
    const user = userEvent.setup()
    monter()
    await attendreApercu()
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1))
    expect(toast.success.mock.calls[0][1].action.label).toBe('Ouvrir le PDF')
    cleanup()
    vi.clearAllMocks()
    ventesApi.apercuFacturerVente.mockResolvedValue({ data: apercuNeuf() })
    ventesApi.facturerVente.mockResolvedValue({
      data: { ...CONTRAT.exemple, facture: { ...CONTRAT.exemple.facture, statut: 'brouillon' } },
    })
    monter()
    await attendreApercu()
    await user.click(screen.getByRole('switch', { name: 'Émettre tout de suite' }))
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1))
    expect(toast.success.mock.calls[0][1]?.action).toBeUndefined()
    expect(ventesApi.facturerVente.mock.calls[0][1].emettre).toBe(false)
  })

  it('sur mobile (375 px) le dialogue est un tiroir bas', async () => {
    mockMatchMedia(true)
    monter()
    await attendreApercu()
    const contenu = document.querySelector('[role="dialog"]')
    expect(contenu.className).toContain('bottom-0')
    expect(contenu.className).not.toContain('-translate-y-1/2')
  })
})

/* VNT81 — « Facturer l'acompte » au téléphone : le dialogue est un TIROIR BAS
   (ResponsiveDialog, < 768 px), sur toute la largeur — pas une modale centrée. */
describe('FacturerVenteDialog — VNT81 : tiroir bas au téléphone', () => {
  it('< 768 px : tiroir bas (rounded-t-2xl), pas de modale centrée', async () => {
    mockMatchMedia(true)
    monter()
    await attendreApercu()
    const contenu = document.querySelector('[role="dialog"]')
    expect(contenu.className).toContain('rounded-t-2xl')
    expect(contenu.className).not.toContain('-translate-y-1/2')
  })

  it('≥ 768 px : modale centrée', async () => {
    mockMatchMedia(false)
    monter()
    await attendreApercu()
    const contenu = document.querySelector('[role="dialog"]')
    expect(contenu.className).toContain('-translate-y-1/2')
    expect(contenu.className).not.toContain('rounded-t-2xl')
  })
})
