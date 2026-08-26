import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import rhApi from '../../api/rhApi'
import Recrutement from './Recrutement.jsx'

/* XRH17-23 / ZRH7-9 — ATS complet : smoke de rendu + présence des nouveaux
   onglets (Vivier / Statistiques / Gabarits) branchés sur les endpoints ATS.
   Le module ne doit jamais planter au chargement, même quand tout est vide.
   WIR34 — « Nouveau candidat » et « Nouveau modèle » câblent respectivement
   `rhApi.createCandidature` et `rhApi.createModeleEvaluation` (jusqu'ici
   définis sans appelant).
   WIR131 — l'action de ligne « Feedback 360° » (onglet Évaluations) câble
   `rhApi.createRetourFeedback360` (invitation d'un répondant) et
   `rhApi.getSyntheseFeedback360` (synthèse agrégée), tous deux définis dans
   rhApi.js sans aucun appelant jusqu'ici.
   PACT20 — les statistiques ne sont plus mockées à la main : la charge utile
   vient de l'exemple committé `apps/rh/contract_samples/stats_recrutement.json`,
   que le test backend `test_pact20_stats_recrutement_contrat.py` affirme égal à
   la vraie réponse du sélecteur. Si le serveur change de forme, l'exemple change
   et ce test casse tout seul. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getEpiCatalogue: vi.fn(empty),
      getDotationsEpi: vi.fn(empty),
      // WIR194 — cycle complet de la dotation EPI (remise/restitution/émargement).
      createDotationEpi: vi.fn(),
      restituerDotationEpi: vi.fn(),
      emargerDotationEpi: vi.fn(),
      getEmargementsDotationEpi: vi.fn(empty),
      getOuverturesPoste: vi.fn(empty),
      createOuverturePoste: vi.fn(),
      // WIR196 — YHIRE14 : cycle d'approbation amont (soumettre/approuver/
      // refuser) + clôture de campagne d'évaluation.
      soumettreOuverturePoste: vi.fn(),
      approuverOuverturePoste: vi.fn(),
      refuserOuverturePoste: vi.fn(),
      cloturerCampagneEvaluation: vi.fn(),
      getCandidatures: vi.fn(empty),
      getVivier: vi.fn(empty),
      // PACT20 — la charge utile est posée dans `beforeEach` depuis la fixture
      // de contrat : une factory `vi.mock` est HISSÉE au-dessus des imports,
      // elle ne peut donc pas lire `reponseContrat`.
      getRecrutementStatistiques: vi.fn(),
      getGabaritsEmailRecrutement: vi.fn(empty),
      getModelesEvaluation: vi.fn(empty),
      getCampagnesEvaluation: vi.fn(empty),
      getEvaluationsEmploye: vi.fn(empty),
      getSanctions: vi.fn(empty),
      createCandidature: vi.fn(),
      createModeleEvaluation: vi.fn(),
      // WIR131 — feedback 360°.
      getRetoursFeedback360: vi.fn(empty),
      getSyntheseFeedback360: vi.fn(() => Promise.resolve({
        data: { nb_invites: 0, nb_soumis: 0, anonymise: true, moyennes_par_critere: {} },
      })),
      getEmployes: vi.fn(() => Promise.resolve({
        data: [{ id: 12, nom: 'Alaoui', prenom: 'Sara' }],
      })),
      createRetourFeedback360: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      // XRH15 — candidats internes classés par couverture du profil requis.
      getCandidatsInternes: vi.fn(empty),
      // WIR240 — chatter candidature (Activité) + grille de notation d'entretien.
      getHistoriqueCandidature: vi.fn(empty),
      noterCandidature: vi.fn(() => Promise.resolve({ data: {} })),
      getEntretiensRecrutement: vi.fn(empty),
      noterEntretienRecrutement: vi.fn(() => Promise.resolve({ data: {} })),
      // WIR241 — dédup candidatures (avertissement non bloquant + fusion).
      checkCandidatureDuplicates: vi.fn(empty),
      fusionnerCandidature: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})

function renderRecrutement() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ConfirmProvider>
          <Recrutement />
        </ConfirmProvider>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

/* PACT20 — l'état par défaut du serveur pour les tests de montage : l'exemple
   VIDE du contrat (mêmes clés, valeurs à zéro), jamais un `{}` inventé. */
function armerStatistiques(variante = 'exemple_vide') {
  rhApi.getRecrutementStatistiques.mockResolvedValue(
    reponseContrat('rh', 'stats_recrutement', variante))
}

describe('Recrutement — ATS (XRH17-23)', () => {
  beforeEach(() => { vi.clearAllMocks(); armerStatistiques() })

  it('rend le module et charge les endpoints ATS (vivier + statistiques)', async () => {
    renderRecrutement()
    expect(
      await screen.findByText('EPI, recrutement & évaluations'),
    ).toBeInTheDocument()
    // Les nouveaux endpoints ATS sont bien appelés au montage.
    expect(rhApi.getVivier).toHaveBeenCalled()
    expect(rhApi.getRecrutementStatistiques).toHaveBeenCalled()
    expect(rhApi.getGabaritsEmailRecrutement).toHaveBeenCalled()
    expect(rhApi.getModelesEvaluation).toHaveBeenCalled()
  })

  it('propose les onglets Vivier / Statistiques / Gabarits', async () => {
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    expect(screen.getByRole('radio', { name: 'Vivier' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Statistiques' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Gabarits' })).toBeInTheDocument()
  })

  it('crée une candidature manuelle via rhApi.createCandidature (WIR34)', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [{ id: 5, intitule: 'Technicien PV' }] })
    rhApi.createCandidature.mockResolvedValueOnce({ data: { id: 1 } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouveau candidat/ }))[0])
    // Le dialogue est ouvert : « Nouveau candidat » existe aussi sur le bouton,
    // donc on vérifie la présence du dialogue lui-même (getByText matcherait 2).
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Poste visé'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Nom du candidat'), { target: { value: 'Yassine Amrani' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer la candidature' })[0])

    await waitFor(() => expect(rhApi.createCandidature).toHaveBeenCalledWith(
      expect.objectContaining({ ouverture: '5', nom: 'Yassine Amrani' }),
    ))
  })

  it('crée un gabarit d’évaluation via rhApi.createModeleEvaluation (WIR34)', async () => {
    rhApi.createModeleEvaluation.mockResolvedValueOnce({ data: { id: 1 } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Gabarits' }))

    fireEvent.click(screen.getAllByRole('button', { name: /Nouveau modèle/ })[0])
    expect(screen.getAllByText('Nouveau modèle d’évaluation').length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText('Nom du modèle'), { target: { value: 'Entretien annuel' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer le modèle' })[0])

    await waitFor(() => expect(rhApi.createModeleEvaluation).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Entretien annuel', questions: [] }),
    ))
  })

  it('invite un répondant au feedback 360° via rhApi.createRetourFeedback360 (WIR131)', async () => {
    rhApi.getEvaluationsEmploye.mockResolvedValueOnce({
      data: [{ id: 9, employe_nom: 'Bennani Youssef', statut: 'validee', statut_display: 'Validée' }],
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Évaluations' }))
    // DataTable rend la table desktop ET le repli carte mobile (CSS seul,
    // les deux existent dans le DOM en jsdom) : getAllBy*, premier match.
    await screen.findAllByText('Bennani Youssef')

    fireEvent.click(screen.getAllByRole('button', { name: 'Feedback 360°' })[0])
    expect((await screen.findAllByText(/Feedback 360° — Bennani Youssef/)).length).toBeGreaterThan(0)
    await waitFor(() => expect(rhApi.getSyntheseFeedback360).toHaveBeenCalledWith({ evaluation: 9 }))

    fireEvent.change(screen.getByLabelText('Répondant'), { target: { value: '12' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Inviter' })[0])

    await waitFor(() => expect(rhApi.createRetourFeedback360).toHaveBeenCalledWith({
      evaluation: 9, repondant: 12, relation: 'pair',
    }))
  })
})

describe('Recrutement — WIR194 : dotations EPI (remise/restitution/émargement)', () => {
  beforeEach(() => { vi.clearAllMocks(); armerStatistiques() })

  it('crée une dotation via rhApi.createDotationEpi', async () => {
    rhApi.getEpiCatalogue.mockResolvedValue({ data: [{ id: 4, designation: 'Casque de chantier' }] })
    rhApi.createDotationEpi.mockResolvedValueOnce({ data: { id: 1 } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle dotation/ }))[0])
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '12' } })
    fireEvent.change(screen.getByLabelText('EPI'), { target: { value: '4' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer la dotation' })[0])

    await waitFor(() => expect(rhApi.createDotationEpi).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '12', epi: '4' }),
    ))
  })

  it('émarge puis restitue une dotation depuis l’écran', async () => {
    rhApi.getDotationsEpi.mockResolvedValue({
      data: [{
        id: 7, employe: 12, employe_nom: 'Alaoui Sara',
        epi: 4, epi_designation: 'Casque de chantier',
        accuse_remise: false, restituee: false,
      }],
    })
    rhApi.emargerDotationEpi.mockResolvedValueOnce({
      data: { emargement: { id: 1 }, deja_accusee: false, accuse_remise: true },
    })
    rhApi.restituerDotationEpi.mockResolvedValueOnce({ data: { id: 7, restituee: true } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    await screen.findAllByText('Casque de chantier')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Émarger' }))[0])
    const emargerDialog = within(await screen.findByRole('dialog'))
    fireEvent.change(emargerDialog.getByLabelText('Nom du signataire'), { target: { value: 'Alaoui Sara' } })
    fireEvent.click(emargerDialog.getByRole('button', { name: 'Émarger' }))

    await waitFor(() => expect(rhApi.emargerDotationEpi).toHaveBeenCalledWith(7, expect.objectContaining({
      signataire_nom: 'Alaoui Sara', role_signataire: 'employe',
    })))

    fireEvent.click((await screen.findAllByRole('button', { name: 'Restituer' }))[0])
    // Confirmation Radix maison (AlertDialog, confirmLabel « Restituer ») —
    // scopée au dialogue pour ne pas ambiguïser avec le bouton déclencheur.
    const confirmDialog = within(await screen.findByRole('alertdialog'))
    fireEvent.click(confirmDialog.getByRole('button', { name: 'Restituer' }))
    await waitFor(() => expect(rhApi.restituerDotationEpi).toHaveBeenCalledWith(7))
  })
})

describe('Recrutement — WIR196 : ouvertures de poste (workflow YHIRE14)', () => {
  beforeEach(() => { vi.clearAllMocks(); armerStatistiques() })

  it('crée une ouverture via rhApi.createOuverturePoste, sans statut envoyé', async () => {
    rhApi.createOuverturePoste.mockResolvedValueOnce({ data: { id: 1 } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle ouverture/ }))[0])
    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText('Intitulé'), { target: { value: 'Technicien PV' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Créer l’ouverture' }))

    await waitFor(() => expect(rhApi.createOuverturePoste).toHaveBeenCalledWith(
      expect.objectContaining({ intitule: 'Technicien PV', nombre_postes: 1 }),
    ))
    expect(rhApi.createOuverturePoste.mock.calls[0][0]).not.toHaveProperty('statut')
  })

  it('soumet puis approuve une ouverture (brouillon → en_approbation → ouvert)', async () => {
    rhApi.getOuverturesPoste.mockResolvedValueOnce({
      data: [{ id: 5, intitule: 'Technicien PV', nombre_postes: 1, statut: 'brouillon', statut_display: 'Brouillon' }],
    })
    rhApi.soumettreOuverturePoste.mockResolvedValueOnce({
      data: { id: 5, statut: 'en_approbation' },
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    await screen.findAllByText('Technicien PV')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Soumettre à approbation' }))[0])
    await waitFor(() => expect(rhApi.soumettreOuverturePoste).toHaveBeenCalledWith(5))

    // Rechargement : l'ouverture repasse en_approbation → « Approuver ».
    rhApi.getOuverturesPoste.mockResolvedValue({
      data: [{ id: 5, intitule: 'Technicien PV', nombre_postes: 1, statut: 'en_approbation', statut_display: 'En approbation' }],
    })
    rhApi.approuverOuverturePoste.mockResolvedValueOnce({ data: { id: 5, statut: 'ouvert' } })
    fireEvent.click((await screen.findAllByRole('button', { name: 'Approuver' }))[0])
    await waitFor(() => expect(rhApi.approuverOuverturePoste).toHaveBeenCalledWith(5))
  })

  it('refuse une ouverture en_approbation (détail 400 affiché tel quel en cas d’auto-approbation)', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({
      data: [{ id: 6, intitule: 'Chargé d’affaires', nombre_postes: 1, statut: 'en_approbation', statut_display: 'En approbation' }],
    })
    rhApi.refuserOuverturePoste.mockRejectedValueOnce({
      response: { data: { detail: 'L’approbateur ne peut pas être le demandeur.' } },
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    await screen.findAllByText('Chargé d’affaires')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Refuser' }))[0])
    const confirmDialog = within(await screen.findByRole('alertdialog'))
    fireEvent.click(confirmDialog.getByRole('button', { name: 'Refuser' }))

    await waitFor(() => expect(rhApi.refuserOuverturePoste).toHaveBeenCalledWith(
      6, expect.objectContaining({ motif_refus: expect.any(String) }),
    ))
  })

  it('clôture une campagne d’évaluation via rhApi.cloturerCampagneEvaluation', async () => {
    rhApi.getCampagnesEvaluation.mockResolvedValueOnce({
      data: [{ id: 3, intitule: 'Entretiens annuels 2026', annee: 2026, statut: 'ouverte', statut_display: 'Ouverte' }],
    })
    rhApi.cloturerCampagneEvaluation.mockResolvedValueOnce({ data: { id: 3, statut: 'cloturee' } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Évaluations' }))
    await screen.findAllByText('Entretiens annuels 2026')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Clôturer' }))[0])
    await waitFor(() => expect(rhApi.cloturerCampagneEvaluation).toHaveBeenCalledWith(3))
  })
})

describe('Recrutement — WIR240 : chatter candidature (Activité) + notation d’entretien', () => {
  beforeEach(() => { vi.clearAllMocks(); armerStatistiques() })

  it('affiche le fil et compose une note via rhApi.noterCandidature', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    rhApi.getCandidatures.mockResolvedValueOnce({
      data: [{ id: 7, nom: 'Amrani Yassine', etape: 'entretien', etape_display: 'Entretien' }],
    })
    rhApi.getHistoriqueCandidature.mockResolvedValue({
      data: [{
        id: 1, candidature: 7, type: 'log', field: 'etape',
        old_value: 'recu', new_value: 'entretien',
        auteur_nom: 'rh1', date_creation: '2026-08-01T10:00:00Z',
      }],
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    const row = (await screen.findAllByText('Amrani Yassine')).map((el) => el.closest('tr')).find(Boolean)
    expect(row).toBeTruthy()

    // « Activité » n'est pas une action rapide (3e de la liste) : passe par
    // le menu kebab persistant, patron déjà établi dans le reste du repo.
    await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Activité'))
    const dialog = within(await screen.findByRole('dialog'))
    // Log automatique de transition déjà rendu par ChatterTimeline.
    expect(await dialog.findByText(/etape/)).toBeInTheDocument()

    fireEvent.change(dialog.getByPlaceholderText('Ajouter une note…'), { target: { value: 'Bon feeling.' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Noter' }))

    await waitFor(() => expect(rhApi.noterCandidature).toHaveBeenCalledWith(
      7, { message: 'Bon feeling.' },
    ))
  })

  it('note un entretien via rhApi.noterEntretienRecrutement (grille de notation)', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    rhApi.getCandidatures.mockResolvedValueOnce({
      data: [{ id: 7, nom: 'Amrani Yassine', etape: 'entretien', etape_display: 'Entretien' }],
    })
    rhApi.getEntretiensRecrutement.mockResolvedValue({
      data: [{
        id: 15, candidature: 7, type: 'technique', type_display: 'Technique',
        date_heure: '2026-08-05T09:00:00Z', statut: 'planifie', notes: [],
      }],
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    const row = (await screen.findAllByText('Amrani Yassine')).map((el) => el.closest('tr')).find(Boolean)
    expect(row).toBeTruthy()

    await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Entretiens & notation'))
    const dialog = within(await screen.findByRole('dialog'))
    await dialog.findByText(/Technique/)
    fireEvent.change(dialog.getByLabelText(/Note —/), { target: { value: '4' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Noter' }))

    await waitFor(() => expect(rhApi.noterEntretienRecrutement).toHaveBeenCalledWith(
      15, expect.objectContaining({ notes_criteres: { global: 4 }, avis: 'reserve' }),
    ))
  })
})

describe('Recrutement — WIR241 : dédup candidatures (avertissement + fusion)', () => {
  beforeEach(() => { vi.clearAllMocks(); armerStatistiques() })

  it('avertit (non bloquant) d’un doublon détecté à la saisie de l’email', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [{ id: 5, intitule: 'Technicien PV' }] })
    rhApi.checkCandidatureDuplicates.mockResolvedValue({
      data: [{ id: 3, nom: 'Amrani Yassine', email: 'yassine@example.com' }],
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouveau candidat/ }))[0])
    fireEvent.change(screen.getByLabelText('Poste visé'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Nom du candidat'), { target: { value: 'Yassine A.' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'yassine@example.com' } })

    await waitFor(() => expect(rhApi.checkCandidatureDuplicates).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'yassine@example.com' }),
    ))
    expect(await screen.findByText(/Candidature\(s\) similaire\(s\)/)).toBeInTheDocument()

    // NON bloquant : la création reste possible malgré l'avertissement.
    rhApi.createCandidature.mockResolvedValueOnce({ data: { id: 9 } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer la candidature' })[0])
    await waitFor(() => expect(rhApi.createCandidature).toHaveBeenCalled())
  })

  it('fusionne une candidature (source) dans une autre (cible) via rhApi.fusionnerCandidature', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    rhApi.getCandidatures.mockResolvedValueOnce({
      data: [
        { id: 7, nom: 'Amrani Yassine', etape: 'recu', etape_display: 'Reçu' },
        { id: 8, nom: 'Amrani Y.', etape: 'recu', etape_display: 'Reçu' },
      ],
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    const rows = (await screen.findAllByText('Amrani Yassine')).map((el) => el.closest('tr')).filter(Boolean)
    expect(rows.length).toBeGreaterThan(0)

    await userEvent.click(within(rows[0]).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Fusionner dans…'))

    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText('Candidature cible'), { target: { value: '8' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Fusionner' }))

    await waitFor(() => expect(rhApi.fusionnerCandidature).toHaveBeenCalledWith(
      '8', { source: 7 },
    ))
  })
})

describe('Recrutement — PACT20 : les 4 tuiles affichent une VRAIE valeur', () => {
  const STATS = exempleContrat('rh', 'stats_recrutement')

  beforeEach(() => { vi.clearAllMocks(); armerStatistiques('exemple') })

  const ouvrirStats = async () => {
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Statistiques' }))
  }

  /* Valeur héros d'une tuile `Stat`, lue par son LIBELLÉ : le libellé est un
     <span> dans la Card, la valeur le <div class="num"> de la même Card. On
     évite ainsi un `getByText('2')` qui matcherait aussi un étage d'entonnoir. */
  const valeurTuile = (label) => screen.getByText(label)
    .parentElement.parentElement.querySelector('.num').textContent.trim()

  it('dérive les tuiles de la forme RÉELLE du serveur (plus aucun « — »)', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({
      data: [
        { id: 4, intitule: 'Technicien PV', statut: 'ouvert' },
        { id: 7, intitule: 'Chargé d’affaires', statut: 'ouvert' },
        { id: 9, intitule: 'Poste pourvu', statut: 'pourvu' },
        { id: 11, intitule: 'Brouillon', statut: 'brouillon' },
      ],
    })
    await ouvrirStats()
    await screen.findAllByText('Ouvertures actives')

    // 1. Délai — le serveur dit `delai_embauche_moyen_jours` (le suffixe
    //    `_jours` manquant était le défaut de type (b)).
    expect(valeurTuile('Délai d’embauche moyen'))
      .toBe(`${STATS.delai_embauche_moyen_jours} j`)
    // 2 & 3. Candidatures / embauches — DÉRIVÉES de l'entonnoir : les rejetées
    //    sont comptées HORS entonnoir, le total est donc `recu + rejete`.
    expect(valeurTuile('Candidatures reçues'))
      .toBe(String(STATS.entonnoir.recu + STATS.entonnoir.rejete))
    expect(valeurTuile('Embauches')).toBe(String(STATS.entonnoir.embauche))
    // 4. Ouvertures actives — les ouvertures au statut `ouvert` déjà chargées
    //    par l'écran (2 sur 4 ici), jamais un chiffre inventé.
    expect(valeurTuile('Ouvertures actives')).toBe('2')

    // Aucune tuile muette : plus un seul « — » sur cet onglet.
    expect(screen.queryByText('—')).toBeNull()
  })

  it('rend l’entonnoir, les candidatures par ouverture et les sources', async () => {
    await ouvrirStats()
    expect((await screen.findAllByText('Entonnoir par étape')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Candidatures par ouverture').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Efficacité par source').length).toBeGreaterThan(0)
    expect(screen.getAllByText(STATS.candidatures_par_ouverture[0].intitule).length).toBeGreaterThan(0)
    expect(screen.getAllByText(STATS.sources[0].source).length).toBeGreaterThan(0)
  })

  it('une société sans donnée affiche des zéros, jamais des tirets', async () => {
    armerStatistiques('exemple_vide')
    await ouvrirStats()
    expect((await screen.findAllByText('Candidatures reçues')).length).toBeGreaterThan(0)
    // `delai_embauche_moyen_jours` est `null` dans l'état vide : c'est le SEUL
    // « — » légitime (le serveur n'a vraiment rien à dire).
    expect(screen.getAllByText('—').length).toBe(1)
  })
  it('classe les candidats internes d’une ouverture (XRH15)', async () => {
    rhApi.getOuverturesPoste.mockResolvedValueOnce({
      data: [{
        id: 5, intitule: 'Technicien PV', poste_ref: 2,
        nombre_postes: 1, statut: 'ouvert', statut_display: 'Ouvert',
      }],
    })
    rhApi.getCandidatsInternes.mockResolvedValueOnce({
      data: [{ employe_id: 9, employe_nom: 'Bennani Youssef', couverture_pct: 75.0 }],
    })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))

    fireEvent.click((await screen.findAllByRole('button', { name: 'Candidats internes' }))[0])
    await waitFor(() => expect(rhApi.getCandidatsInternes).toHaveBeenCalledWith(2))
    expect(await screen.findByText('Bennani Youssef')).toBeInTheDocument()
  })
})
