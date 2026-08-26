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
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))

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

  it('saisie + resultat=conforme → PATCH de la fiche, badge « Conforme »', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)

    await user.selectOptions(screen.getByLabelText('Dossier as-built présent'), 'true')
    await user.selectOptions(screen.getByLabelText('Structure'), 'true')
    await user.selectOptions(screen.getByLabelText('Continuité de terre'), 'true')
    const isolement = screen.getByLabelText('Résistance d’isolement (MΩ)')
    await user.clear(isolement)
    await user.type(isolement, '12.75')
    await user.selectOptions(screen.getByLabelText('Résultat'), 'conforme')

    // Après l'écriture, le serveur sert la fiche À PLAT (forme réelle du GET).
    api.getRecette.mockResolvedValue({ data: FICHE_CONFORME })
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))

    // La fiche est créée À LA SAUVEGARDE, puis remplie par un PATCH.
    await waitFor(() => expect(api.ouvrirRecette).toHaveBeenCalledWith(1))
    await waitFor(() => expect(api.updateRecette).toHaveBeenCalledTimes(1))
    const [id, payload] = api.updateRecette.mock.calls[0]
    expect(id).toBe(9)
    expect(payload.resultat).toBe('conforme')
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
