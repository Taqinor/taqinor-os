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
})
