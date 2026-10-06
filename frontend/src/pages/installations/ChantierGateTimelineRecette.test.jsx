import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR202/CH3 — la fiche de recette IEC 62446-1 se créait VIDE et rien ne
   pouvait la remplir : le gate « Mise en service » restait bloqué à jamais.
   Ce fichier couvre le formulaire de saisie :
   (1) le bouton OUVRE le formulaire, il ne crée plus d'enregistrement ;
   (2) saisir les 4 sections + `resultat = conforme` envoie un PATCH ;
   (3) un relevé I-V part bien par `ajouter-iv` ;
   (4) une fiche déjà passée s'affiche « Conforme » (les deux formes de
       réponse du GET sont acceptées). */

const api = vi.hoisted(() => ({
  getEtapesChantier: vi.fn(),
  avancerEtape: vi.fn(),
  getRecette: vi.fn(),
  ouvrirRecette: vi.fn(),
  getRecetteRecord: vi.fn(),
  updateRecette: vi.fn(),
  ajouterReleveIv: vi.fn(),
  getPackRemise: vi.fn(),
  genererPackRemise: vi.fn(),
  getReservesChantier: vi.fn(),
  ajouterReserveChantier: vi.fn(),
  leverReserveChantier: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))

import { exempleContrat } from '../../test/fixtures/contractSamples'
import ChantierGateTimeline from './ChantierGateTimeline'

const ETAPES = {
  installation: 1,
  reference: 'CH-001',
  etape_courante: 'montage_mecanique',
  etapes: [
    {
      cle: 'montage_mecanique', libelle: 'Montage mécanique', ordre: 1,
      bloquant: true, satisfait: true, raisons: [], id: 2,
      statut_legacy: 'installe', courante: true,
    },
    {
      cle: 'mise_en_service', libelle: 'Mise en service', ordre: 2,
      bloquant: true, satisfait: false,
      raisons: ['Fiche de recette IEC 62446-1 non passée.'],
      id: 3, statut_legacy: 'mise_en_service', courante: false,
    },
  ],
}

const FICHE_CONFORME = {
  id: 9, installation: 1, resultat: 'conforme',
  resultat_display: 'Conforme', passe: true, iv_readings: [],
}

beforeEach(() => {
  api.getEtapesChantier.mockResolvedValue({ data: ETAPES })
  api.getRecette.mockResolvedValue({ data: { installation: 1, record: null } })
  api.getPackRemise.mockResolvedValue({
    data: { installation: 1, pieces: [], complet: false, persiste: false },
  })
  api.ouvrirRecette.mockResolvedValue({ data: { id: 9, installation: 1, resultat: 'en_cours' } })
  api.updateRecette.mockResolvedValue({ data: FICHE_CONFORME })
  api.ajouterReleveIv.mockResolvedValue({
    data: {
      id: 3, string_label: 'S1', voc_mesure_v: '412.5', isc_mesure_a: '9.8',
      pmax_mesure_w: '3400', ecart_pmax_pct: '-2.90', defaut_detecte: false,
    },
  })
  api.genererPackRemise.mockResolvedValue({ data: { complet: true, pieces: [] } })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

async function ouvrirFormulaire(user) {
  render(<ChantierGateTimeline installationId={1} />)
  await waitFor(() => expect(api.getRecette).toHaveBeenCalledWith(1))
  await user.click(screen.getByRole('button', { name: /Ouvrir la fiche de recette/ }))
  return screen.findByRole('dialog')
}

describe('ChantierGateTimeline — WIR202 fiche de recette IEC 62446-1', () => {
  it("le bouton OUVRE le formulaire sans créer d'enregistrement vide", async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)

    expect(api.ouvrirRecette).not.toHaveBeenCalled()
    expect(screen.getByText('Fiche de recette (IEC 62446-1)')).toBeInTheDocument()
    // Les 4 sections du sérialiseur sont là.
    expect(screen.getByText('Documentation (§4)')).toBeInTheDocument()
    expect(screen.getByText('Inspection visuelle (§5)')).toBeInTheDocument()
    expect(screen.getByText('Essais électriques (§6)')).toBeInTheDocument()
    expect(screen.getByText('Performance et sécurité (§7)')).toBeInTheDocument()
  })

  it('tous les champs numériques acceptent une valeur tapée (step="any", jamais de snap)', async () => {
    const user = userEvent.setup()
    const dialog = await ouvrirFormulaire(user)
    const nombres = dialog.querySelectorAll('input[type="number"]')
    expect(nombres.length).toBeGreaterThan(0)
    for (const input of nombres) expect(input.getAttribute('step')).toBe('any')
    // Le formulaire ne valide pas côté navigateur (aucun rejet du navigateur).
    expect(dialog.querySelector('form')).toHaveAttribute('novalidate')
  })

  it('saisie des essais → PATCH de la fiche, badge « Conforme » (calculé)', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)

    await user.selectOptions(screen.getByLabelText('Dossier as-built présent'), 'true')
    await user.selectOptions(screen.getByLabelText('Structure'), 'true')
    await user.selectOptions(screen.getByLabelText('Continuité de terre'), 'true')
    const isolement = screen.getByLabelText('Résistance d’isolement (MΩ)')
    await user.clear(isolement)
    await user.type(isolement, '12.75')

    // Après l'écriture, le serveur sert la fiche À PLAT (forme réelle du GET).
    api.getRecette.mockResolvedValue({ data: FICHE_CONFORME })
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))

    // La fiche est créée À LA SAUVEGARDE, puis remplie par un PATCH.
    await waitFor(() => expect(api.ouvrirRecette).toHaveBeenCalledWith(1))
    await waitFor(() => expect(api.updateRecette).toHaveBeenCalledTimes(1))
    const [id, payload] = api.updateRecette.mock.calls[0]
    expect(id).toBe(9)
    // CIQ636 — résultat calculé côté serveur : jamais envoyé, sauf « reserves ».
    expect(payload).not.toHaveProperty('resultat')
    expect(payload.doc_dossier_ok).toBe(true)
    expect(payload.visuel_structure_ok).toBe(true)
    expect(payload.continuite_terre_ok).toBe(true)
    // La valeur tapée part TELLE QUELLE (ni arrondie, ni rognée).
    expect(payload.isolement_mohm).toBe('12.75')
    // Un essai non renseigné n'est jamais présumé conforme.
    expect(payload.doc_schema_ok).toBeNull()

    // Le gate est relu pour que le déblocage soit visible tout de suite.
    await waitFor(() => expect(api.getEtapesChantier).toHaveBeenCalledTimes(2))
    // Le badge du gate CH3 — requête portée sur SA carte (le <select> du
    // formulaire porte les mêmes libellés).
    expect(
      await within(screen.getByTestId('ch6-recette')).findByText('Conforme'),
    ).toBeInTheDocument()
  })

  it('ajoute un relevé I-V via ajouter-iv une fois la fiche enregistrée', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))
    await waitFor(() => expect(api.updateRecette).toHaveBeenCalled())

    await user.type(await screen.findByLabelText('String'), 'S1')
    await user.type(screen.getByLabelText('Voc mesuré (V)'), '412.5')
    await user.type(screen.getByLabelText('Isc mesuré (A)'), '9.8')
    await user.type(screen.getByLabelText('Pmax mesuré (W)'), '3400')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé I-V/ }))

    await waitFor(() => expect(api.ajouterReleveIv).toHaveBeenCalledWith(9, {
      string_label: 'S1',
      voc_mesure_v: '412.5',
      isc_mesure_a: '9.8',
      pmax_mesure_w: '3400',
    }))
    expect(await screen.findByTestId('recette-releves')).toHaveTextContent('S1')
  })

  it('une fiche existante servie À PLAT par le GET est bien reconnue', async () => {
    api.getRecette.mockResolvedValue({ data: FICHE_CONFORME })
    render(<ChantierGateTimeline installationId={1} />)
    await waitFor(() => expect(api.getRecette).toHaveBeenCalledWith(1))
    expect(
      await within(screen.getByTestId('ch6-recette')).findByText('Conforme'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Modifier la fiche de recette/ })).toBeInTheDocument()
  })
})

/* CIQ636 — recette C&I : résultat AFFICHÉ (calculé par le serveur), sections
   irradiance / énergie / thermographie / terre (+ limitation d'injection et
   découplage en MT), comparaison au devis et panneau Réserves. Les charges
   utiles viennent du contrat COMMITTÉ `installations/recette_ci.json`. */
const CI = exempleContrat('installations', 'recette_ci')
const CI_MT = exempleContrat('installations', 'recette_ci', 'exemple_mt')
const ESSAIS_VRAIS = {
  doc_dossier_ok: true, doc_schema_ok: true, doc_datasheets_ok: true,
  visuel_structure_ok: true, visuel_cablage_ok: true, visuel_terre_ok: true,
  continuite_terre_ok: true, polarite_ok: true, isolement_ok: true,
  performance_ok: true, securite_coupure_ok: true,
  securite_signalisation_ok: true,
}
const CHANTIER_BT = { type_installation: 'industriel', niveau_tension: 'bt' }
const CHANTIER_MT = { type_installation: 'industriel', niveau_tension: 'mt' }

async function ouvrirModifier(user, installation, contrat, extraRecord = {}) {
  const enveloppe = {
    ...contrat,
    record: { ...contrat.record, ...extraRecord },
  }
  api.getRecette.mockResolvedValue({ data: enveloppe })
  render(<ChantierGateTimeline installationId={1} installation={installation} />)
  await waitFor(() => expect(api.getRecette).toHaveBeenCalledWith(1))
  await user.click(await screen.findByRole('button', { name: /Modifier la fiche de recette/ }))
  return screen.findByRole('dialog')
}

describe('ChantierGateTimeline — CIQ636 recette C&I', () => {
  it('le résultat est affiché, jamais modifiable', async () => {
    const user = userEvent.setup()
    const dialog = await ouvrirModifier(user, CHANTIER_BT, CI, ESSAIS_VRAIS)
    expect(within(dialog).queryByLabelText('Résultat')).toBeNull()
    expect(within(dialog).getByTestId('recette-resultat')).toHaveTextContent(
      'Conforme avec réserves')
  })

  it('« conforme avec réserves » exige tous les essais vrais ET une réserve ouverte', async () => {
    const user = userEvent.setup()
    // Aucune réserve ouverte : le choix est refusé.
    let dialog = await ouvrirModifier(
      user, CHANTIER_BT, { ...CI, reserves: [] },
      { ...ESSAIS_VRAIS, resultat: 'conforme' })
    const casse = within(dialog).getByLabelText('Conforme avec réserves')
    expect(casse).toBeDisabled()
    cleanup()

    // Réserve de recette ouverte (celle du contrat) : le choix est offert.
    dialog = await ouvrirModifier(
      user, CHANTIER_BT, CI, { ...ESSAIS_VRAIS, resultat: 'conforme' })
    expect(within(dialog).getByLabelText('Conforme avec réserves')).toBeEnabled()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', async () => {
    const user = userEvent.setup()
    let dialog = await ouvrirModifier(user, CHANTIER_BT, CI, ESSAIS_VRAIS)
    api.updateRecette.mockImplementation((id, payload) => Promise.resolve({
      data: { ...CI.record, ...ESSAIS_VRAIS, ...payload, id },
    }))
    await user.click(within(dialog).getByRole('button', { name: /Enregistrer la fiche/ }))
    await waitFor(() => expect(api.updateRecette).toHaveBeenCalledTimes(1))
    const premier = api.updateRecette.mock.calls[0][1]
    // La saisie du contrat part telle quelle (rien d'arrondi ni d'inventé).
    expect(premier.irradiance_poa_wm2).toBe(CI.record.irradiance.irradiance_poa_wm2)
    expect(premier.energie_mesuree_kwh).toBe(CI.record.energie.energie_mesuree_kwh)
    expect(premier.energie_fenetre_debut).toBe(CI.record.energie.fenetre_debut)
    expect(premier.resultat).toBe('reserves')

    // Réouverture depuis la fiche renvoyée par le serveur, sans retouche.
    api.getRecette.mockResolvedValue({
      data: { ...CI.record, ...ESSAIS_VRAIS, ...premier, id: CI.record.id },
    })
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await user.click(await screen.findByRole('button', { name: /Modifier la fiche de recette/ }))
    dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /Enregistrer la fiche/ }))
    await waitFor(() => expect(api.updateRecette).toHaveBeenCalledTimes(2))
    expect(api.updateRecette.mock.calls[1][1]).toEqual(premier)
  })

  it('tous les champs numériques C&I restent en step="any" (formulaire noValidate)', async () => {
    const user = userEvent.setup()
    const dialog = await ouvrirModifier(user, CHANTIER_MT, CI_MT, ESSAIS_VRAIS)
    const nombres = dialog.querySelectorAll('input[type="number"]')
    expect(nombres.length).toBeGreaterThan(6)
    for (const input of nombres) expect(input.getAttribute('step')).toBe('any')
    expect(dialog.querySelector('form')).toHaveAttribute('novalidate')
  })

  it('limitation d’injection et découplage ne sont proposés qu’en MT', async () => {
    const user = userEvent.setup()
    let dialog = await ouvrirModifier(user, CHANTIER_BT, CI, ESSAIS_VRAIS)
    expect(within(dialog).queryByTestId('recette-mt')).toBeNull()
    cleanup()
    dialog = await ouvrirModifier(user, CHANTIER_MT, CI_MT, ESSAIS_VRAIS)
    expect(within(dialog).getByTestId('recette-mt')).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Découplage')).toBeInTheDocument()
  })

  it('compare à la promesse figée : PR « à titre d’information », seuil non saisi', async () => {
    const user = userEvent.setup()
    const dialog = await ouvrirModifier(user, CHANTIER_BT, CI, ESSAIS_VRAIS)
    const bloc = within(dialog).getByTestId('recette-comparaison')
    expect(bloc).toHaveTextContent(
      String(CI.comparaison.promesse_figee.production_annuelle_kwh))
    expect(bloc).toHaveTextContent(CI.record.energie.libelle)
    expect(bloc).toHaveTextContent('seuil non saisi en Paramètres')
  })

  it('une fiche résidentielle garde ses champs, sans section C&I', async () => {
    const user = userEvent.setup()
    api.getRecette.mockResolvedValue({ data: FICHE_CONFORME })
    render(<ChantierGateTimeline installationId={1}
                                 installation={{ type_installation: 'residentiel' }} />)
    await user.click(await screen.findByRole('button', { name: /Modifier la fiche de recette/ }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByTestId('recette-ci')).toBeNull()
    expect(within(dialog).getByTestId('recette-resultat')).toHaveTextContent('Conforme')
  })

  it('panneau Réserves : ajouter puis lever relisent la liste du serveur', async () => {
    const user = userEvent.setup()
    const dialog = await ouvrirModifier(user, CHANTIER_BT, CI, ESSAIS_VRAIS)
    const reserve = CI.reserves[0]
    expect(within(dialog).getByText(reserve.description)).toBeInTheDocument()
    expect(within(dialog).getByText(`échéance ${reserve.date_echeance}`)).toBeInTheDocument()

    api.ajouterReserveChantier.mockResolvedValue({ data: { id: 99 } })
    api.getReservesChantier.mockResolvedValue({ data: [
      reserve,
      { ...reserve, id: 99, description: 'Peinture à reprendre', bloquante: true },
    ] })
    await user.type(within(dialog).getByLabelText('Réserve à ajouter'), 'Peinture à reprendre')
    await user.click(within(dialog).getByLabelText('Bloquante'))
    await user.click(within(dialog).getByRole('button', { name: 'Ajouter la réserve' }))
    await waitFor(() => expect(api.ajouterReserveChantier).toHaveBeenCalledWith(1, {
      description: 'Peinture à reprendre', origine: 'recette', bloquante: true,
      date_echeance: null, responsable: '',
    }))
    expect(await within(dialog).findByText('Peinture à reprendre')).toBeInTheDocument()

    api.leverReserveChantier.mockResolvedValue({ data: {} })
    api.getReservesChantier.mockResolvedValue({ data: [
      { ...reserve, statut: 'resolue' },
    ] })
    await user.click(within(dialog).getByRole('button', {
      name: `Lever la réserve ${reserve.description}` }))
    await waitFor(() => expect(api.leverReserveChantier).toHaveBeenCalledWith(1, reserve.id))
    await waitFor(() => expect(within(dialog).queryByRole('button', {
      name: `Lever la réserve ${reserve.description}` })).toBeNull())
  })

  it('une erreur 400 du serveur s’affiche sous le champ fautif', async () => {
    const user = userEvent.setup()
    const dialog = await ouvrirModifier(user, CHANTIER_BT, CI, ESSAIS_VRAIS)
    api.updateRecette.mockRejectedValue({
      response: { data: { resultat: ['Aucune réserve de recette ouverte.'] } },
    })
    await user.click(within(dialog).getByRole('button', { name: /Enregistrer la fiche/ }))
    expect(await within(dialog).findByText('Aucune réserve de recette ouverte.'))
      .toBeInTheDocument()
  })
})
