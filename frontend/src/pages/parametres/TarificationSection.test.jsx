import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import process from 'node:process'

/* CALX72 — l'écran Réglages → Tarification saisit TOUS les réglages du lot 5
   (CALX274 → CALX284). Ce module verrouille :
     * chaque champ SERVI par le sérialiseur (`CHAMPS_LOT5` de
       `apps/parametres/serializers_tariff.py`, lu ici — jamais une liste
       recopiée) a sa porte de saisie `#tarif-<champ>` à l'écran ;
     * société vierge : chaque bloc rend ses champs VIDES (aucune valeur
       préremplie par l'écran) ;
     * un tarif horaire saisi sans `tou_source` est refusé AVANT envoi, le
       refus sous le champ ;
     * le refus 400 du serveur (`{champ: [message]}`) atterrit sous le bon
       champ, et le bandeau le nomme. */

const { getTariffSettings, updateTariffSettings } = vi.hoisted(() => ({
  getTariffSettings: vi.fn(),
  updateTariffSettings: vi.fn(),
}))

vi.mock('../../api/parametresApi', () => ({
  default: { getTariffSettings, updateTariffSettings },
}))

vi.mock('../../ui/confirm', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

import TarificationSection from './TarificationSection'

function racineDepot() {
  let dossier = resolve(process.cwd())
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`)
}

// Les champs du lot 5 que le serveur SERT — lus dans le sérialiseur.
function champsServis() {
  const source = readFileSync(join(racineDepot(), 'backend', 'django_core',
    'apps', 'parametres', 'serializers_tariff.py'), 'utf8')
  const bloc = source.match(/CHAMPS_LOT5 = \[([\s\S]*?)\]/)
  if (!bloc) throw new Error('CHAMPS_LOT5 introuvable dans serializers_tariff.py')
  return [...bloc[1].matchAll(/'([a-z0-9_]+)'/g)].map(m => m[1])
}

const CHAMPS_LOT5 = champsServis()

// Société VIERGE : les défauts du modèle (vides ; les deux déclarations
// d'aujourd'hui — structure « tranches » et prix TTC — sont servies telles
// quelles, jamais inventées par l'écran).
const DEFAUTS_MODELE = {
  tou_heures: null, tou_tarifs: null, tou_source: '', tou_date_source: null,
  mecanisme_compensation: '', report_periode: null, plafond_annuel_kwh: null,
  ratio_compensation: null, structure_tarif: 'tranches', pays_tarif: '',
  prix_unique_kwh: null, poste_haut: null, poste_bas: null,
  prix_incluent_taxes: true, taxes: null, charge_minimale_mad_jour: null,
  indexation_tarif_pct_an: null, indexation_source: '',
  taux_imposition_pct: null, amortissement_mode: 'aucun',
  amortissement_duree_ans: null, amortissement_coefficient: null,
  fiscalite_source: '',
}

const VIERGE = {
  residential_tiers: null, tolerance_kwh: 10, selective_threshold_kwh: 150,
  force_motrice_prix_kwh_ttc: '0.9500', surplus_injecte_compense: false,
  surplus_prix_kwh_ttc: '0.0000', autoconsommation_pct_defaut: '70.00',
  pertes_systeme_pct: '20.00', pvgis_actif: true,
  productible_manuel_kwh_kwc: '1500.0', inclinaison_defaut_deg: 30,
  azimut_defaut_deg: 0, version: 1, date_modification: null,
  ...Object.fromEntries(CHAMPS_LOT5.map(c => [c, DEFAUTS_MODELE[c]])),
}

const champ = (nom) => document.getElementById(`tarif-${nom}`)

async function rendreVierge() {
  getTariffSettings.mockResolvedValue({ data: { ...VIERGE } })
  render(<TarificationSection />)
  await waitFor(() => expect(champ('tou_source')).not.toBeNull())
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CALX72 — chaque réglage servi a sa porte de saisie', () => {
  it('lit la liste servie par le sérialiseur (lot 5 complet)', () => {
    expect(CHAMPS_LOT5).toEqual(expect.arrayContaining([
      'tou_heures', 'tou_tarifs', 'tou_source', 'tou_date_source',
      'mecanisme_compensation', 'structure_tarif', 'taxes',
      'prix_incluent_taxes', 'indexation_tarif_pct_an',
      'taux_imposition_pct', 'amortissement_mode', 'fiscalite_source',
    ]))
    for (const c of CHAMPS_LOT5) expect(c in DEFAUTS_MODELE).toBe(true)
  })

  it('rend un champ #tarif-<champ> pour CHAQUE champ servi', async () => {
    await rendreVierge()
    for (const c of CHAMPS_LOT5) expect(champ(c), c).not.toBeNull()
  })
})

describe('CALX72 — société vierge : chaque bloc rend ses champs vides', () => {
  it('aucune valeur préremplie par l’écran', async () => {
    await rendreVierge()
    for (const titre of [
      'Tranches horaires et leurs tarifs', 'Mécanisme de compensation du surplus',
      'Structure du tarif', 'Taxes et charge minimale',
      'Indexation annuelle du tarif', 'Fiscalité et amortissement',
    ]) expect(screen.getAllByText(titre).length).toBeGreaterThan(0)

    for (const c of [
      'tou_source', 'tou_date_source', 'mecanisme_compensation',
      'report_periode', 'plafond_annuel_kwh', 'ratio_compensation',
      'pays_tarif', 'prix_unique_kwh', 'poste_haut', 'poste_bas',
      'charge_minimale_mad_jour', 'indexation_tarif_pct_an',
      'indexation_source', 'taux_imposition_pct', 'amortissement_duree_ans',
      'amortissement_coefficient', 'fiscalite_source',
    ]) expect(champ(c).value, c).toBe('')

    // Les 24 heures du découpage : vides ; aucun tarif ni aucune taxe.
    const heures = champ('tou_heures').querySelectorAll('input')
    expect(heures).toHaveLength(24)
    for (const cellule of heures) expect(cellule.value).toBe('')
    expect(champ('tou_tarifs').querySelectorAll('input')).toHaveLength(0)
    expect(champ('taxes').querySelectorAll('input')).toHaveLength(0)

    // Les choix servis sont ceux du serveur, rien de plus.
    expect(champ('structure_tarif').value).toBe('tranches')
    expect(champ('amortissement_mode').value).toBe('aucun')
    expect(champ('prix_incluent_taxes')).toHaveAttribute('aria-checked', 'true')
  })
})

describe('CALX72 — refus avant envoi et refus du serveur sous le bon champ', () => {
  it('un tarif horaire saisi sans tou_source est refusé AVANT envoi', async () => {
    const user = userEvent.setup()
    await rendreVierge()
    await user.type(screen.getByLabelText('Tranche Toute l’année 00 h'), 'pleine')
    const tarif = await screen.findByLabelText('Tarif de la tranche pleine')
    await user.type(tarif, '2')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    expect(updateTariffSettings).not.toHaveBeenCalled()
    const refus = screen.getByTestId('erreur-tou_source')
    expect(refus).toHaveTextContent('tou_source')
    expect(champ('tou_source')).toHaveAttribute('aria-invalid', 'true')
    expect(champ('tou_source')).toHaveAttribute(
      'aria-describedby', 'tarif-tou_source-erreur')
    expect(screen.getByTestId('tarif-erreurs'))
      .toHaveTextContent('Source des tarifs horaires')
  })

  it('le refus 400 du serveur atterrit sous le champ qu’il nomme', async () => {
    const user = userEvent.setup()
    const message = 'amortissement_coefficient : obligatoire pour '
      + 'l’amortissement dégressif — aucun coefficient n’est supposé.'
    updateTariffSettings.mockRejectedValue({
      response: { status: 400, data: { amortissement_coefficient: [message] } },
    })
    await rendreVierge()
    await user.selectOptions(champ('amortissement_mode'), 'degressif')
    await user.type(champ('amortissement_duree_ans'), '5')
    await user.type(champ('fiscalite_source'), 'CGI')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(updateTariffSettings).toHaveBeenCalledTimes(1))
    const envoye = updateTariffSettings.mock.calls[0][0]
    expect(envoye.amortissement_mode).toBe('degressif')
    expect(envoye.amortissement_duree_ans).toBe('5')
    expect(envoye.amortissement_coefficient).toBeNull()

    const refus = await screen.findByTestId('erreur-amortissement_coefficient')
    expect(refus).toHaveTextContent(message)
    expect(champ('amortissement_coefficient'))
      .toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByTestId('tarif-erreurs'))
      .toHaveTextContent('Coefficient dégressif')

    // Corriger le champ efface son refus.
    await user.type(champ('amortissement_coefficient'), '2')
    expect(screen.queryByTestId('erreur-amortissement_coefficient')).toBeNull()
  })
})
