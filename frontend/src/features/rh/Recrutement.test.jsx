import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
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
      getOuverturesPoste: vi.fn(empty),
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
      // WIR194 — écriture des dotations EPI (create / restituer / emarger /
      // emargements) : quatre routes serveur jusqu'ici sans aucun appelant.
      // WIR196 — cycle d'approbation d'une ouverture de poste + clôture de
      // campagne d'évaluation (quatre @actions sans appelant).
      createOuverturePoste: vi.fn(),
      soumettreOuverturePoste: vi.fn(),
      approuverOuverturePoste: vi.fn(),
      refuserOuverturePoste: vi.fn(),
      cloturerCampagneEvaluation: vi.fn(),
      // WIR240 — chatter candidature + grille de notation d'entretien.
      getHistoriqueCandidature: vi.fn(empty),
      noterCandidature: vi.fn(),
      getEntretiensRecrutement: vi.fn(empty),
      noterEntretienRecrutement: vi.fn(),
      createDotationEpi: vi.fn(),
      restituerDotationEpi: vi.fn(),
      emargerDotationEpi: vi.fn(),
      getEmargementsDotationEpi: vi.fn(empty),
    },
  }
})

function renderRecrutement() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Recrutement />
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

/* WIR240 — le chatter d'une candidature journalisait les transitions d'étape
   sans qu'aucun écran ne les lise, et la grille de notation d'entretien
   n'avait aucun appelant (colonne Note + comparatif condamnés à rester
   vides). */
describe('Recrutement — WIR240 : chatter candidature & notation d’entretien', () => {
  const CANDIDATURE = {
    id: 7, nom: 'Yassine Amrani', email: 'y@example.ma',
    ouverture: 5, ouverture_intitule: 'Technicien PV',
    etape: 'entretien', etape_display: 'Entretien',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    armerStatistiques()
    rhApi.getCandidatures.mockResolvedValue({ data: [CANDIDATURE] })
  })

  const ouvrirActivite = async () => {
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    await screen.findAllByText('Yassine Amrani')
    fireEvent.click((await screen.findAllByRole('button', { name: 'Activité' }))[0])
  }

  it('rend le fil (transitions journalisées) et publie une note', async () => {
    rhApi.getHistoriqueCandidature.mockResolvedValue({
      data: [{
        id: 1, candidature: 7, type: 'log', type_display: 'Transition',
        field: 'etape', old_value: 'Présélection', new_value: 'Entretien',
        message: '', auteur: 2, auteur_nom: 'rh1',
        date_creation: '2026-08-12T09:00:00Z',
      }],
    })
    rhApi.noterCandidature.mockResolvedValueOnce({ data: { id: 2 } })
    await ouvrirActivite()

    await waitFor(() => expect(rhApi.getHistoriqueCandidature).toHaveBeenCalledWith(7))
    // La transition d'étape est désormais LISIBLE dans le fil.
    expect((await screen.findAllByText(/Entretien/)).length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText('Ajouter une note'), {
      target: { value: 'Bon profil, à revoir' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Publier la note' })[0])

    await waitFor(() => expect(rhApi.noterCandidature).toHaveBeenCalledWith(
      7, { message: 'Bon profil, à revoir' },
    ))
  })

  it('note un entretien via rhApi.noterEntretienRecrutement', async () => {
    rhApi.getEntretiensRecrutement.mockResolvedValue({
      data: [{
        id: 33, candidature: 7, date_heure: '2026-08-14T10:00:00Z',
        type_entretien: 'technique', type_display: 'Technique', notes: [],
      }],
    })
    rhApi.noterEntretienRecrutement.mockResolvedValueOnce({ data: { id: 4 } })
    await ouvrirActivite()

    await waitFor(() => expect(rhApi.getEntretiensRecrutement).toHaveBeenCalledWith({ candidature: 7 }))
    fireEvent.change(await screen.findByLabelText('Technique (1–5)'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Avis'), { target: { value: 'favorable' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer la notation' })[0])

    await waitFor(() => expect(rhApi.noterEntretienRecrutement).toHaveBeenCalledWith(33, {
      notes_criteres: { Technique: 4 },
      commentaire: '',
      avis: 'favorable',
    }))
  })
})

/* WIR196 — une ouverture de poste n'était créable nulle part et restait
   bloquée à vie en brouillon : le workflow d'approbation YHIRE14 (soumettre →
   approuver / refuser, séparation des tâches côté serveur) était injouable. */
describe('Recrutement — WIR196 : cycle d’approbation des ouvertures de poste', () => {
  const OUVERTURE = (statut) => ({
    id: 5, intitule: 'Technicien PV', nombre_postes: 1,
    statut, statut_display: statut,
  })

  beforeEach(() => { vi.clearAllMocks(); armerStatistiques() })

  const ouvrirRecrutement = async () => {
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))
    await screen.findAllByText('Technicien PV')
  }

  it('crée une ouverture (brouillon serveur — aucun statut envoyé)', async () => {
    rhApi.createOuverturePoste.mockResolvedValueOnce({ data: { id: 6 } })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle ouverture/ }))[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Intitulé'), { target: { value: 'Technicien PV' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer l’ouverture' })[0])

    await waitFor(() => expect(rhApi.createOuverturePoste).toHaveBeenCalledWith(
      expect.objectContaining({ intitule: 'Technicien PV', nombre_postes: 1 }),
    ))
    const corps = rhApi.createOuverturePoste.mock.calls[0][0]
    expect(corps).not.toHaveProperty('statut')
    expect(corps).not.toHaveProperty('company')
  })

  it('soumet un brouillon à approbation', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [OUVERTURE('brouillon')] })
    rhApi.soumettreOuverturePoste.mockResolvedValueOnce({ data: {} })
    await ouvrirRecrutement()

    // En brouillon : seule la soumission est offerte.
    expect(screen.queryByRole('button', { name: 'Approuver' })).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: 'Soumettre à approbation' })[0])
    await waitFor(() => expect(rhApi.soumettreOuverturePoste).toHaveBeenCalledWith(5))
  })

  it('approuve une ouverture soumise et affiche le 400 de séparation des tâches', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [OUVERTURE('en_approbation')] })
    rhApi.approuverOuverturePoste.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Le demandeur ne peut pas approuver sa propre ouverture.' } },
    })
    await ouvrirRecrutement()

    // En approbation : plus de soumission, mais Approuver / Refuser.
    expect(screen.queryByRole('button', { name: 'Soumettre à approbation' })).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: 'Approuver' })[0])

    await waitFor(() => expect(rhApi.approuverOuverturePoste).toHaveBeenCalledWith(5))
    // Le détail 400 part au toast (aucun `Toaster` monté dans ce rendu) ; la
    // preuve DOM que le détail serveur est affiché TEL QUEL est faite par le
    // dialogue de refus ci-dessous, qui le rend en ligne.
  })

  it('affiche TEL QUEL le 400 de séparation des tâches au refus', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [OUVERTURE('en_approbation')] })
    rhApi.refuserOuverturePoste.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Le demandeur ne peut pas décider de sa propre ouverture.' } },
    })
    await ouvrirRecrutement()

    fireEvent.click(screen.getAllByRole('button', { name: 'Refuser' })[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Refuser' })
      .find((b) => b.getAttribute('type') === 'submit'))

    expect(
      await screen.findByText('Le demandeur ne peut pas décider de sa propre ouverture.'),
    ).toBeInTheDocument()
  })

  it('refuse une ouverture soumise avec un motif', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [OUVERTURE('en_approbation')] })
    rhApi.refuserOuverturePoste.mockResolvedValueOnce({ data: {} })
    await ouvrirRecrutement()

    fireEvent.click(screen.getAllByRole('button', { name: 'Refuser' })[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Motif du refus'), { target: { value: 'Budget non validé' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Refuser' })
      .find((b) => b.getAttribute('type') === 'submit'))

    await waitFor(() => expect(rhApi.refuserOuverturePoste).toHaveBeenCalledWith(
      5, { motif_refus: 'Budget non validé' },
    ))
  })

  it('clôture une campagne d’évaluation encore ouverte', async () => {
    rhApi.getCampagnesEvaluation.mockResolvedValue({
      data: [{ id: 3, intitule: 'Campagne 2026', annee: 2026, statut: 'ouverte', statut_display: 'Ouverte' }],
    })
    rhApi.cloturerCampagneEvaluation.mockResolvedValueOnce({ data: {} })
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Évaluations' }))
    await screen.findAllByText('Campagne 2026')

    fireEvent.click(screen.getAllByRole('button', { name: 'Clôturer' })[0])
    await waitFor(() => expect(rhApi.cloturerCampagneEvaluation).toHaveBeenCalledWith(3))
  })
})

/* WIR194 — les dotations EPI étaient 100 % lecture seule : ni remise, ni
   restitution, ni émargement (la preuve exigible en contrôle CNSS). Les trois
   écritures sont désormais jouables depuis l'onglet EPI. */
describe('Recrutement — WIR194 : écriture des dotations EPI', () => {
  const DOTATION = {
    id: 77,
    employe: 3,
    employe_nom: 'Bennani Youssef',
    epi: 8,
    epi_designation: 'Casque de chantier',
    taille: 'L',
    date_dotation: '2026-05-04',
    accuse_remise: false,
    restituee: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    armerStatistiques()
    rhApi.getDotationsEpi.mockResolvedValue({ data: [DOTATION] })
    rhApi.getEpiCatalogue.mockResolvedValue({
      data: [{ id: 8, designation: 'Casque de chantier', actif: true }],
    })
  })

  const ouvrirEpi = async () => {
    renderRecrutement()
    await screen.findAllByText('EPI, recrutement & évaluations')
    await screen.findAllByText('Casque de chantier')
  }

  it('crée une dotation via rhApi.createDotationEpi (jamais de company au corps)', async () => {
    rhApi.createDotationEpi.mockResolvedValueOnce({ data: { id: 78 } })
    await ouvrirEpi()

    fireEvent.click(screen.getAllByRole('button', { name: /Nouvelle dotation/ })[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '12' } })
    fireEvent.change(screen.getByLabelText('EPI (catalogue)'), { target: { value: '8' } })
    fireEvent.change(screen.getByLabelText('Taille'), { target: { value: 'L' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer la dotation' })[0])

    await waitFor(() => expect(rhApi.createDotationEpi).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '12', epi: '8', taille: 'L' }),
    ))
    expect(rhApi.createDotationEpi.mock.calls[0][0]).not.toHaveProperty('company')
  })

  it('émarge la remise (nom obligatoire) via rhApi.emargerDotationEpi', async () => {
    rhApi.emargerDotationEpi.mockResolvedValueOnce({ data: { accuse_remise: true } })
    await ouvrirEpi()

    fireEvent.click(screen.getAllByRole('button', { name: 'Émarger' })[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    // Nom vide → le bouton reste désactivé : le nom dactylographié fait foi.
    const valider = screen.getAllByRole('button', { name: 'Émarger' })
      .find((b) => b.getAttribute('type') === 'submit')
    expect(valider).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Nom du signataire'), {
      target: { value: 'Bennani Youssef' },
    })
    fireEvent.click(valider)

    await waitFor(() => expect(rhApi.emargerDotationEpi).toHaveBeenCalledWith(77, {
      signataire_nom: 'Bennani Youssef',
      role_signataire: 'employe',
      methode: 'typed',
      mention: '',
    }))
  })

  it('restitue une dotation via rhApi.restituerDotationEpi', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    rhApi.restituerDotationEpi.mockResolvedValueOnce({ data: { restituee: true } })
    await ouvrirEpi()

    fireEvent.click(screen.getAllByRole('button', { name: 'Restituer' })[0])

    await waitFor(() => expect(rhApi.restituerDotationEpi).toHaveBeenCalledWith(77))
  })

  it('affiche l’historique des émargements (preuve CNSS)', async () => {
    rhApi.getEmargementsDotationEpi.mockResolvedValueOnce({
      data: [{
        id: 1, signataire_nom: 'Bennani Youssef',
        role_signataire: 'employe', role_signataire_display: 'Employé',
        date_signature: '2026-05-04',
      }],
    })
    await ouvrirEpi()

    fireEvent.click(screen.getAllByRole('button', { name: 'Historique' })[0])
    await waitFor(() => expect(rhApi.getEmargementsDotationEpi).toHaveBeenCalledWith(77))
    expect(
      (await screen.findAllByText(/Émargements — Casque de chantier/)).length,
    ).toBeGreaterThan(0)
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
