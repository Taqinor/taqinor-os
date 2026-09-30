import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  render, screen, cleanup, waitFor, fireEvent, within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* COCKPIT-CONTRÔLE (30/09/2026) — le bloc « Contrôle du suivi ». Charge utile =
   l'exemple COMMITTÉ (`apps/crm/contract_samples/controle_suivi.json`, PACT10),
   jamais un objet retapé à la main : une autre situation du serveur (`ok`,
   `alerte`, `vide`…) est ce même exemple dont on ne change QUE le champ qui la
   distingue — jamais la forme. Si le serveur change de forme, l'exemple change
   et ces tests cassent tout seuls. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { PARCOURS } from '../../features/crm/relances/parcours'
import { STAGE_LABELS } from '../../features/crm/stages'

const CONTROLE = exempleContrat('crm', 'controle_suivi')
const VIDE = exempleContrat('crm', 'controle_suivi', 'exemple_vide')
// `exemple_alerte` : le serveur en niveau « alerte », avec la ligne d'un dossier
// sans prochaine étape (stage, derniere_etape_le, depuis_jours).
const ALERTE = exempleContrat('crm', 'controle_suivi', 'exemple_alerte')
const SUIVI = exempleContrat('crm', 'relance_etapes_suivi')

const naviguer = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => naviguer,
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getControleSuivi: vi.fn(),
    getRelanceEtapesSuivi: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import ControleSuiviPanel from './ControleSuiviPanel'

beforeEach(() => {
  crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi'))
  crmApi.getRelanceEtapesSuivi.mockResolvedValue(reponseContrat('crm', 'relance_etapes_suivi'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function monter() {
  return render(
    <MemoryRouter>
      <ControleSuiviPanel />
    </MemoryRouter>,
  )
}

/** Le même exemple de contrat, dont on remplace des blocs entiers. */
const variante = (changements) => ({ data: { ...CONTROLE, ...changements } })
const verdictAvec = (champs) => ({ ...CONTROLE.verdict, ...champs })

async function attendreVerdict() {
  return screen.findByTestId('controle-verdict')
}

describe('ControleSuiviPanel — en-tête et chargement', () => {
  it('appelle le serveur avec la période par défaut (14 jours), sans commercial', async () => {
    monter()
    await attendreVerdict()
    expect(crmApi.getControleSuivi).toHaveBeenCalledTimes(1)
    expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 14 })
    expect(screen.getByRole('heading', { name: /Contrôle du suivi/ })).toBeInTheDocument()
  })

  it('affiche un squelette pendant le chargement, puis le contenu', async () => {
    let servir
    crmApi.getControleSuivi.mockReturnValue(new Promise((resolve) => { servir = resolve }))
    monter()
    expect(screen.getByTestId('controle-squelette')).toBeInTheDocument()
    expect(screen.queryByTestId('controle-verdict')).not.toBeInTheDocument()
    servir(reponseContrat('crm', 'controle_suivi'))
    await attendreVerdict()
    expect(screen.queryByTestId('controle-squelette')).not.toBeInTheDocument()
  })

  it('erreur réseau : « Indisponible pour le moment. » + Réessayer, qui relit le serveur', async () => {
    crmApi.getControleSuivi.mockRejectedValueOnce(new Error('boom'))
    monter()
    expect(await screen.findByText('Indisponible pour le moment.')).toBeInTheDocument()
    expect(screen.queryByTestId('controle-verdict')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await attendreVerdict()
    expect(crmApi.getControleSuivi).toHaveBeenCalledTimes(2)
    expect(screen.queryByText('Indisponible pour le moment.')).not.toBeInTheDocument()
  })
})

describe('ControleSuiviPanel — verdict', () => {
  it('« attention » : ◆ orange, « À surveiller », UNE phrase construite depuis les cinq listes', async () => {
    monter()
    const verdict = await attendreVerdict()
    expect(verdict).toHaveAttribute('role', 'status')
    expect(verdict).toHaveAttribute('data-niveau', 'attention')
    expect(verdict).toHaveTextContent('◆')
    expect(verdict).toHaveTextContent('À surveiller')
    expect(verdict).toHaveTextContent(
      '2 étapes en retard, 1 tâche en attente depuis 4 jours, '
      + '1 étape reportée plusieurs fois, 1 premier contact hors délai.')
  })

  it('« alerte » (exemple_alerte du contrat) : ▲ rouge, « En retard », les cinq listes dans la phrase', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
    monter()
    const verdict = await attendreVerdict()
    expect(verdict).toHaveAttribute('data-niveau', 'alerte')
    expect(verdict).toHaveTextContent('▲')
    expect(verdict).toHaveTextContent('En retard')
    // Le dossier sorti du suivi entre dans la phrase, à sa place (avant le premier contact).
    expect(verdict).toHaveTextContent(
      '2 étapes en retard, 1 tâche en attente depuis 4 jours, 1 étape reportée plusieurs fois, '
      + '1 dossier sans prochaine étape, 1 premier contact hors délai.')
  })

  it('« ok » : ● vert, « Tout est à jour » — la phrase dit que rien n\'est en retard', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      verdict: verdictAvec({ niveau: 'ok', en_retard: 0, ouvert: 0 }),
      exceptions: VIDE.exceptions,
    }))
    monter()
    const verdict = await attendreVerdict()
    expect(verdict).toHaveAttribute('data-niveau', 'ok')
    expect(verdict).toHaveTextContent('●')
    expect(verdict).toHaveTextContent('Tout est à jour')
    expect(verdict).toHaveTextContent('Rien n\'est en retard ni en attente.')
  })

  it('« vide » (exemple_vide) : – gris, « Pas encore de données », jamais un 0 % inventé', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: VIDE })
    monter()
    const verdict = await attendreVerdict()
    expect(verdict).toHaveAttribute('data-niveau', 'vide')
    expect(verdict).toHaveTextContent('–')
    expect(verdict).toHaveTextContent('Pas encore de données')
    expect(screen.getByTestId('controle-phrase-periode'))
      .toHaveTextContent('Sur 14 jours : aucune étape n\'était due.')
    expect(screen.getByTestId('controle-suivi-panel')).not.toHaveTextContent(/0\s?%/)
    expect(screen.queryByTestId('controle-comparaison')).not.toBeInTheDocument()
  })

  it('la phrase de période reprend les compteurs du serveur, pourcentage arrondi', async () => {
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-phrase-periode')).toHaveTextContent(
      'Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %), '
      + '3 rattrapées en retard, 1 sautée, 2 encore ouvertes.')
  })

  it('compare à la période précédente : ↑ n points (85,7 % contre 78 %)', async () => {
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-comparaison')).toHaveTextContent(
      '↑ 8 points par rapport à la période précédente (78 %)')
  })

  it('↓ quand la période précédente était meilleure', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      verdict: verdictAvec({ precedent_a_temps_pct: 91.2 }),
    }))
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-comparaison')).toHaveTextContent(
      '↓ 5 points par rapport à la période précédente (91 %)')
  })

  it('pourcentage null → « — » dans la phrase, aucune comparaison inventée', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      verdict: verdictAvec({ a_temps_pct: null, precedent_a_temps_pct: null }),
    }))
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-phrase-periode')).toHaveTextContent('traitées à temps (—)')
    expect(screen.getByTestId('controle-phrase-periode')).not.toHaveTextContent('0 %')
    expect(screen.queryByTestId('controle-comparaison')).not.toBeInTheDocument()
  })

  it('pas de comparaison quand seule la période précédente est vide (null)', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      verdict: verdictAvec({ precedent_a_temps_pct: null }),
    }))
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-phrase-periode')).toHaveTextContent('(86 %)')
    expect(screen.queryByTestId('controle-comparaison')).not.toBeInTheDocument()
  })

  it('un niveau inconnu du serveur est dit tel quel, jamais rabattu sur « Tout est à jour »', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({ verdict: verdictAvec({ niveau: 'nouveau_niveau' }) }))
    monter()
    const verdict = await attendreVerdict()
    expect(verdict).toHaveTextContent('nouveau_niveau')
    expect(verdict).not.toHaveTextContent('Tout est à jour')
  })
})

describe('ControleSuiviPanel — frise', () => {
  it('une case par jour servi, du plus ancien à aujourd\'hui, avec un nom accessible complet', async () => {
    monter()
    await attendreVerdict()
    const frise = screen.getByTestId('controle-frise')
    const cases = within(frise).getAllByRole('button')
    expect(cases).toHaveLength(CONTROLE.jours.length)
    expect(cases.map((c) => c.getAttribute('data-testid'))).toEqual(
      CONTROLE.jours.map((j) => `controle-jour-${j.date}`))
    // 29/09/2026 est un mardi ; les compteurs nuls (0 en retard, 0 sautée) sont omis.
    expect(within(frise).getByRole('button', {
      name: 'mardi 29 septembre : 6 dues, 4 à temps, 2 encore ouvertes',
    })).toBeInTheDocument()
    expect(within(frise).getByRole('button', {
      name: 'vendredi 18 septembre : 4 dues, 3 à temps, 1 rattrapée en retard',
    })).toBeInTheDocument()
  })

  it('la forme de chaque état : ● vert, ◆ orange, ▲ rouge, ◔ en cours (aujourd\'hui), – vide', async () => {
    monter()
    await attendreVerdict()
    const glyphe = (date) => screen.getByTestId(`controle-jour-${date}`)
    expect(glyphe('2026-09-17')).toHaveAttribute('data-etat', 'vert')
    expect(glyphe('2026-09-17')).toHaveTextContent('●')
    expect(glyphe('2026-09-18')).toHaveAttribute('data-etat', 'orange')
    expect(glyphe('2026-09-18')).toHaveTextContent('◆')
    expect(glyphe('2026-09-29')).toHaveAttribute('data-etat', 'rouge')
    expect(glyphe('2026-09-29')).toHaveTextContent('▲')
    expect(glyphe('2026-09-30')).toHaveAttribute('data-etat', 'en_cours')
    expect(glyphe('2026-09-30')).toHaveTextContent('◔')
    expect(glyphe('2026-09-20')).toHaveAttribute('data-etat', 'vide')
    expect(glyphe('2026-09-20')).toHaveTextContent('–')
  })

  it('les jours non ouvrés sont estompés, aujourd\'hui est cerclé et le dit', async () => {
    monter()
    await attendreVerdict()
    const dimanche = screen.getByTestId('controle-jour-2026-09-20')
    expect(dimanche).toHaveClass('opacity-50')
    expect(dimanche).toHaveAccessibleName('dimanche 20 septembre (jour non ouvré) : rien de dû')
    const aujourdhui = screen.getByTestId('controle-jour-2026-09-30')
    expect(aujourdhui).toHaveClass('ring-2')
    expect(aujourdhui).not.toHaveClass('opacity-50')
    expect(aujourdhui).toHaveAccessibleName(
      'mercredi 30 septembre (aujourd\'hui) : 7 dues, 3 à temps, 4 encore ouvertes')
  })

  it('la légende dit la forme ET le sens de chaque état', async () => {
    monter()
    await attendreVerdict()
    const legende = screen.getByTestId('controle-legende')
    expect(legende).toHaveTextContent('tout traité le jour même')
    expect(legende).toHaveTextContent('traité en retard ou sauté')
    expect(legende).toHaveTextContent('journée en cours')
    expect(legende).toHaveTextContent('rien de dû')
  })

  it('un clic sur une case ouvre la liste de CE jour (période = ce seul jour), un re-clic la referme', async () => {
    monter()
    await attendreVerdict()
    const jour = screen.getByTestId('controle-jour-2026-09-29')
    expect(jour).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(jour)
    expect(jour).toHaveAttribute('aria-expanded', 'true')
    const liste = await screen.findByTestId('controle-jour-liste')
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith(
      { date_debut: '2026-09-29', date_fin: '2026-09-29' })
    // Les lignes viennent du contrat `relance_etapes_suivi` : nom du lead en lien
    // vers sa fiche, libellé, statut, heure (Casablanca), qui l'a traitée.
    const lignes = await within(liste).findAllByTestId('controle-jour-ligne')
    expect(lignes).toHaveLength(SUIVI.results.length)
    const [fait, aFaire] = lignes
    expect(within(fait).getByRole('link', { name: 'Aziz Benali' }))
      .toHaveAttribute('href', '/crm/leads?lead=1489')
    expect(fait).toHaveTextContent('Message d\'identité')
    expect(fait).toHaveTextContent('Fait')
    expect(fait).toHaveTextContent('traitée à 08:32')
    expect(fait).toHaveTextContent(`par ${SUIVI.results[0].traite_par_nom}`)
    expect(aFaire).toHaveTextContent('Appel d\'ouverture')
    expect(aFaire).toHaveTextContent('À faire')
    expect(aFaire).toHaveTextContent('prévue à 08:33')
    expect(aFaire).not.toHaveTextContent('par ')
    fireEvent.click(jour)
    expect(jour).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('controle-jour-liste')).not.toBeInTheDocument()
  })

  it('un clic sur le nom d\'un lead de la liste navigue vers sa fiche', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByTestId('controle-jour-2026-09-29'))
    const liste = await screen.findByTestId('controle-jour-liste')
    fireEvent.click((await within(liste).findAllByRole('link', { name: 'Aziz Benali' }))[0])
    expect(naviguer).toHaveBeenCalledWith('/crm/leads?lead=1489')
  })

  it('clavier : Entrée ouvre la liste du jour, un second Entrée la referme', async () => {
    const user = userEvent.setup()
    monter()
    await attendreVerdict()
    const aujourdhui = screen.getByTestId('controle-jour-2026-09-30')
    aujourdhui.focus()
    await user.keyboard('{Enter}')
    expect(await screen.findByTestId('controle-jour-liste')).toBeInTheDocument()
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith(
      { date_debut: '2026-09-30', date_fin: '2026-09-30' })
    await user.keyboard('{Enter}')
    expect(screen.queryByTestId('controle-jour-liste')).not.toBeInTheDocument()
  })

  it('clavier : la frise est UN arrêt de tabulation, les flèches / Début / Fin la parcourent', async () => {
    const user = userEvent.setup()
    monter()
    await attendreVerdict()
    const cases = within(screen.getByTestId('controle-frise')).getAllByRole('button')
    // Un seul arrêt de tabulation : la dernière case (aujourd'hui).
    expect(cases.filter((c) => c.tabIndex === 0)).toEqual([cases[cases.length - 1]])
    cases[cases.length - 1].focus()
    await user.keyboard('{ArrowLeft}')
    expect(cases[cases.length - 2]).toHaveFocus()
    expect(cases[cases.length - 2].tabIndex).toBe(0)
    await user.keyboard('{Home}')
    expect(cases[0]).toHaveFocus()
    await user.keyboard('{ArrowLeft}')
    expect(cases[0]).toHaveFocus()
    await user.keyboard('{End}')
    expect(cases[cases.length - 1]).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(cases[cases.length - 1]).toHaveFocus()
  })

  it('jour sans étape : le dit (rien n\'était dû)', async () => {
    crmApi.getRelanceEtapesSuivi.mockResolvedValue(reponseContrat('crm', 'relance_etapes_suivi', 'exemple_vide'))
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByTestId('controle-jour-2026-09-20'))
    expect(await screen.findByText('Aucune étape n\'était due ce jour-là.')).toBeInTheDocument()
  })

  it('liste du jour indisponible : message + Réessayer', async () => {
    crmApi.getRelanceEtapesSuivi.mockRejectedValueOnce(new Error('boom'))
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByTestId('controle-jour-2026-09-29'))
    const liste = await screen.findByTestId('controle-jour-liste')
    expect(await within(liste).findByText('Indisponible pour le moment.')).toBeInTheDocument()
    fireEvent.click(within(liste).getByRole('button', { name: 'Réessayer' }))
    expect(await within(liste).findAllByTestId('controle-jour-ligne')).toHaveLength(SUIVI.results.length)
  })

  it('rien à dessiner sans jour servi (exemple_vide) : pas de frise', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: VIDE })
    monter()
    await attendreVerdict()
    expect(screen.queryByTestId('controle-frise')).not.toBeInTheDocument()
  })
})

describe('ControleSuiviPanel — « À traiter en priorité »', () => {
  const bloc = (cle) => screen.getByTestId(`controle-exception-${cle}`)

  it('chaque liste non vide : titre + compteur du serveur, ouverte par défaut', async () => {
    monter()
    await attendreVerdict()
    expect(screen.getByRole('heading', { name: 'À traiter en priorité' })).toBeInTheDocument()
    // Les seuils de l'exemple du contrat : 2 jours d'attente, 2 reports, 24 h.
    expect(CONTROLE.seuils).toMatchObject({
      tache_attente_jours: 2, reports_min: 2, premier_contact_heures: 24,
    })
    const attendu = {
      en_retard: ['En retard', '2'],
      taches_en_attente: ['Tâches en attente depuis 2 jours ou plus', '1'],
      reports: ['Reportées 2 fois ou plus', '1'],
      premier_contact_hors_delai: ['Premier contact hors délai (24 h)', '1'],
    }
    Object.entries(attendu).forEach(([cle, [titre, total]]) => {
      const entete = within(bloc(cle)).getByRole('button', { expanded: true })
      expect(entete).toHaveTextContent(titre)
      expect(screen.getByTestId(`controle-total-${cle}`)).toHaveTextContent(total)
    })
  })

  it('une liste vide (total 0) est masquée', async () => {
    monter()
    await attendreVerdict()
    expect(screen.queryByTestId('controle-exception-sans_prochaine_etape')).not.toBeInTheDocument()
    expect(screen.queryByText('Aucune exception')).not.toBeInTheDocument()
  })

  it('« En retard » : nom du lead (lien), libellé, type lu dans la table, responsable, « depuis N jour »', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('en_retard')).getByTestId('controle-exception-ligne')
    expect(within(ligne).getByRole('link', { name: 'Salma Idrissi' }))
      .toHaveAttribute('href', '/crm/leads?lead=1490')
    expect(ligne).toHaveTextContent('Appel de suivi')
    // Le type vient de la table du parcours (`suivi_appel`), pas du code.
    const nomTable = PARCOURS.etapes.find((t) => t.id === 'suivi_appel').nom
    expect(nomTable).toBe('Appel de suivi de la proposition')
    expect(ligne).toHaveTextContent(nomTable)
    expect(ligne).toHaveTextContent('depuis 1 jour')
    expect(ligne).toHaveTextContent('Responsable : commerciale')
  })

  it('« Tâches en attente » : « posée il y a N jours », type lu dans la table', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('taches_en_attente')).getByTestId('controle-exception-ligne')
    expect(within(ligne).getByRole('link', { name: 'Youssef Bennani' }))
      .toHaveAttribute('href', '/crm/leads?lead=1502')
    expect(ligne).toHaveTextContent('posée il y a 4 jours')
    expect(ligne).toHaveTextContent(PARCOURS.etapes.find((t) => t.id === 'devis').nom)
    // Dans la liste des tâches, « Tâche » irait de soi : pas de pastille redondante.
    expect(within(ligne).queryByText('Tâche')).not.toBeInTheDocument()
  })

  it('« Reportées plusieurs fois » : « N reports — prévue à l\'origine le JJ/MM »', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('reports')).getByTestId('controle-exception-ligne')
    expect(ligne).toHaveTextContent('2 reports — prévue à l\'origine le 27/09')
    // Une TÂCHE dans une autre liste que « Tâches en attente » porte sa pastille.
    expect(within(ligne).getByText('Tâche')).toBeInTheDocument()
  })

  it('« Premier contact hors délai » : « attend depuis N h » (décimale française)', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('premier_contact_hors_delai')).getByTestId('controle-exception-ligne')
    expect(within(ligne).getByRole('link', { name: 'Karim El Fassi' }))
      .toHaveAttribute('href', '/crm/leads?lead=1511')
    expect(ligne).toHaveTextContent('attend depuis 27,5 h')
    expect(ligne).toHaveTextContent('Responsable : commerciale')
  })

  describe('« Dossiers sans prochaine étape » (ligne fixée par exemple_alerte)', () => {
    const LIGNE = ALERTE.exceptions.sans_prochaine_etape.lignes[0]

    /** L'exemple d'alerte dont on ne change que la ligne du dossier sans étape. */
    const avecLigne = (surcharge) => ({
      data: {
        ...ALERTE,
        exceptions: {
          ...ALERTE.exceptions,
          sans_prochaine_etape: { total: 1, lignes: [{ ...LIGNE, ...surcharge }] },
        },
      },
    })

    it('la liste s\'ouvre avec la ligne du contrat : nom (lien fiche), étape du pipeline en français, ancienneté, responsable', async () => {
      crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
      monter()
      await attendreVerdict()
      expect(screen.getByTestId('controle-total-sans_prochaine_etape')).toHaveTextContent('1')
      const ligne = within(bloc('sans_prochaine_etape')).getByTestId('controle-exception-ligne')
      expect(within(ligne).getByRole('link', { name: LIGNE.lead_nom }))
        .toHaveAttribute('href', `/crm/leads?lead=${LIGNE.lead}`)
      // `stage` est une clé de STAGES.py : la ligne dit le libellé FR des
      // constantes du frontend, jamais la clé.
      expect(STAGE_LABELS[LIGNE.stage]).toBeTruthy()
      expect(within(ligne).getByTestId('controle-ligne-etiquette')).toHaveTextContent(STAGE_LABELS[LIGNE.stage])
      expect(ligne).not.toHaveTextContent(LIGNE.stage)
      expect(ligne).toHaveTextContent(`sans étape depuis ${LIGNE.depuis_jours} jours`)
      expect(ligne).toHaveTextContent(`Responsable : ${LIGNE.owner_nom}`)
    })

    it('chaque clé de STAGES.py servie se dit avec son libellé français', async () => {
      // Une clé après l'autre, par construction : la liste vient des constantes.
      for (const [stage, libelle] of Object.entries(STAGE_LABELS)) {
        crmApi.getControleSuivi.mockResolvedValue(avecLigne({ stage }))
        const rendu = monter()
        await attendreVerdict()
        expect(within(bloc('sans_prochaine_etape')).getByTestId('controle-ligne-etiquette'))
          .toHaveTextContent(libelle)
        rendu.unmount()
      }
    })

    it('une clé que les constantes du frontend ne connaissent pas s\'affiche telle quelle', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecLigne({ stage: 'ETAPE_INCONNUE' }))
      monter()
      await attendreVerdict()
      expect(within(bloc('sans_prochaine_etape')).getByTestId('controle-ligne-etiquette'))
        .toHaveTextContent('ETAPE_INCONNUE')
    })

    it('l\'ancienneté s\'accorde : « depuis 1 jour », « depuis aujourd\'hui »', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecLigne({ depuis_jours: 1 }))
      const { unmount } = monter()
      await attendreVerdict()
      expect(bloc('sans_prochaine_etape')).toHaveTextContent('sans étape depuis 1 jour')
      expect(bloc('sans_prochaine_etape')).not.toHaveTextContent('depuis 1 jours')
      unmount()
      crmApi.getControleSuivi.mockResolvedValue(avecLigne({ depuis_jours: 0 }))
      monter()
      await attendreVerdict()
      expect(bloc('sans_prochaine_etape')).toHaveTextContent('sans étape depuis aujourd\'hui')
    })

    it('une ligne sans `stage` ni `depuis_jours` (serveur plus ancien) reste lisible : nom et responsable', async () => {
      crmApi.getControleSuivi.mockResolvedValue({
        data: {
          ...ALERTE,
          exceptions: {
            ...ALERTE.exceptions,
            sans_prochaine_etape: {
              total: 1,
              lignes: [{ lead: LIGNE.lead, lead_nom: LIGNE.lead_nom, owner_nom: LIGNE.owner_nom }],
            },
          },
        },
      })
      monter()
      await attendreVerdict()
      const ligne = within(bloc('sans_prochaine_etape')).getByTestId('controle-exception-ligne')
      expect(within(ligne).getByRole('link', { name: LIGNE.lead_nom })).toBeInTheDocument()
      expect(within(ligne).queryByTestId('controle-ligne-etiquette')).not.toBeInTheDocument()
      expect(ligne).toHaveTextContent(`Responsable : ${LIGNE.owner_nom}`)
      expect(ligne).not.toHaveTextContent('sans étape depuis')
    })

    it('le verdict « alerte » de l\'exemple compte ce dossier dans sa phrase', async () => {
      crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
      monter()
      const verdict = await attendreVerdict()
      expect(verdict).toHaveAttribute('data-niveau', 'alerte')
      expect(verdict).toHaveTextContent('1 dossier sans prochaine étape')
    })
  })

  it('« et N autres » quand le total dépasse les lignes servies, avec un lien vers /crm/relances', async () => {
    monter()
    await attendreVerdict()
    // en_retard : total 2, 1 ligne servie → « et 1 autre ».
    const reste = within(bloc('en_retard')).getByTestId('controle-reste-en_retard')
    const lien = within(reste).getByRole('link', { name: 'et 1 autre' })
    expect(lien).toHaveAttribute('href', '/crm/relances')
    // taches_en_attente : total === lignes servies → rien.
    expect(screen.queryByTestId('controle-reste-taches_en_attente')).not.toBeInTheDocument()
  })

  it('« et N autres » au pluriel', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      exceptions: {
        ...CONTROLE.exceptions,
        en_retard: { ...CONTROLE.exceptions.en_retard, total: 14 },
      },
    }))
    monter()
    await attendreVerdict()
    expect(within(screen.getByTestId('controle-reste-en_retard'))
      .getByRole('link', { name: 'et 13 autres' })).toHaveAttribute('href', '/crm/relances')
  })

  it('un clic sur l\'en-tête referme (puis rouvre) une liste', async () => {
    monter()
    await attendreVerdict()
    const entete = within(bloc('en_retard')).getByRole('button', { expanded: true })
    fireEvent.click(entete)
    expect(entete).toHaveAttribute('aria-expanded', 'false')
    expect(within(bloc('en_retard')).queryByTestId('controle-exception-ligne')).not.toBeInTheDocument()
    // Le compteur reste visible même repliée.
    expect(screen.getByTestId('controle-total-en_retard')).toHaveTextContent('2')
    fireEvent.click(entete)
    expect(within(bloc('en_retard')).getByTestId('controle-exception-ligne')).toBeInTheDocument()
  })

  it('les cinq listes vides : UNE seule ligne rassurante « Aucune exception »', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: VIDE })
    monter()
    await attendreVerdict()
    expect(screen.getByText('Aucune exception')).toBeInTheDocument()
    expect(screen.queryByTestId('controle-exception-en_retard')).not.toBeInTheDocument()
    expect(screen.queryByTestId('controle-seuils')).not.toBeInTheDocument()
  })

  it('dit le seuil d\'alerte servi par le serveur (les trois autres sont dans les titres)', async () => {
    monter()
    await attendreVerdict()
    expect(CONTROLE.seuils.retard_alerte_jours).toBe(2)
    expect(screen.getByTestId('controle-seuils')).toHaveTextContent('Alerte dès 2 jours de retard.')
  })

  describe('seuils lisibles : les libellés suivent les seuils SERVIS, jamais un nombre écrit dans le code', () => {
    /** L'exemple du contrat dont on ne change QUE les seuils. */
    const avecSeuils = (seuils) => variante({ seuils })

    it('un seuil modifié change les titres et la note d\'alerte', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecSeuils({
        retard_alerte_jours: 5, tache_attente_jours: 7, reports_min: 4, premier_contact_heures: 48,
      }))
      monter()
      await attendreVerdict()
      const titreDe = (cle) => within(bloc(cle)).getByRole('button', { expanded: true })
      expect(titreDe('taches_en_attente')).toHaveTextContent('Tâches en attente depuis 7 jours ou plus')
      expect(titreDe('reports')).toHaveTextContent('Reportées 4 fois ou plus')
      expect(titreDe('premier_contact_hors_delai')).toHaveTextContent('Premier contact hors délai (48 h)')
      expect(titreDe('en_retard')).toHaveTextContent('En retard')
      expect(screen.getByTestId('controle-seuils')).toHaveTextContent('Alerte dès 5 jours de retard.')
      // Aucun des nombres de l'exemple ne survit dans les libellés.
      const section = screen.getByTestId('controle-exceptions')
      expect(section).not.toHaveTextContent('depuis 2 jours ou plus')
      expect(section).not.toHaveTextContent('2 fois ou plus')
      expect(section).not.toHaveTextContent('(24 h)')
      expect(section).not.toHaveTextContent('Alerte dès 2 jours')
    })

    it('les accords suivent le seuil : « 1 jour ou plus », heures décimales', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecSeuils({
        retard_alerte_jours: 1, tache_attente_jours: 1, reports_min: 1, premier_contact_heures: 1.5,
      }))
      monter()
      await attendreVerdict()
      const section = screen.getByTestId('controle-exceptions')
      expect(section).toHaveTextContent('Tâches en attente depuis 1 jour ou plus')
      expect(section).not.toHaveTextContent('1 jours')
      expect(section).toHaveTextContent('Reportées 1 fois ou plus')
      expect(section).toHaveTextContent('Premier contact hors délai (1,5 h)')
      expect(screen.getByTestId('controle-seuils')).toHaveTextContent('Alerte dès 1 jour de retard.')
    })

    it('sans bloc `seuils` : titres génériques, aucun nombre inventé, pas de note', async () => {
      const sansSeuils = { ...CONTROLE }
      delete sansSeuils.seuils
      crmApi.getControleSuivi.mockResolvedValue({ data: sansSeuils })
      monter()
      await attendreVerdict()
      const titreDe = (cle) => within(bloc(cle)).getByRole('button', { expanded: true })
      expect(titreDe('taches_en_attente')).toHaveTextContent(/^Tâches en attente\s*1$/)
      expect(titreDe('reports')).toHaveTextContent(/^Reportées plusieurs fois\s*1$/)
      expect(titreDe('premier_contact_hors_delai')).toHaveTextContent(/^Premier contact hors délai\s*1$/)
      expect(screen.queryByTestId('controle-seuils')).not.toBeInTheDocument()
    })

    it('un seuil manquant ne rend générique que SA liste', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecSeuils({
        retard_alerte_jours: 2, tache_attente_jours: 9, premier_contact_heures: 12,
      }))
      monter()
      await attendreVerdict()
      const titreDe = (cle) => within(bloc(cle)).getByRole('button', { expanded: true })
      expect(titreDe('taches_en_attente')).toHaveTextContent('Tâches en attente depuis 9 jours ou plus')
      expect(titreDe('reports')).toHaveTextContent(/^Reportées plusieurs fois\s*1$/)
      expect(titreDe('premier_contact_hors_delai')).toHaveTextContent('Premier contact hors délai (12 h)')
    })
  })
})

describe('ControleSuiviPanel — détail par étape', () => {
  it('replié par défaut ; le clic déploie le tableau', async () => {
    monter()
    await attendreVerdict()
    const detail = screen.getByTestId('controle-detail')
    expect(within(detail).queryByRole('table')).not.toBeInTheDocument()
    const bouton = within(detail).getByRole('button', { name: 'Détail par étape' })
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(bouton)
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    expect(within(detail).getByRole('table')).toBeInTheDocument()
  })

  it('une ligne par type, nommée d\'après la TABLE du parcours, avec ses cinq compteurs', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const contact = screen.getByTestId('controle-type-contact_appel')
    const nom = PARCOURS.etapes.find((t) => t.id === 'contact_appel').nom
    expect(within(contact).getByRole('rowheader')).toHaveTextContent(nom)
    // La première ligne du type porte ses cinq compteurs (dues, à temps, en
    // retard, sautées, encore ouvertes) ; la seconde, ses réponses.
    const [chiffres] = within(contact).getAllByRole('row')
    expect(within(chiffres).getAllByRole('cell').map((c) => c.textContent))
      .toEqual(['14', '12', '1', '1', '0'])
    expect(within(contact).queryByText('Tâche')).not.toBeInTheDocument()

    const devis = screen.getByTestId('controle-type-devis')
    expect(within(devis).getByRole('rowheader'))
      .toHaveTextContent(PARCOURS.etapes.find((t) => t.id === 'devis').nom)
    expect(within(devis).getByText('Tâche')).toBeInTheDocument()
    expect(within(within(devis).getAllByRole('row')[0]).getAllByRole('cell').map((c) => c.textContent))
      .toEqual(['5', '3', '1', '0', '1'])
  })

  it('les colonnes portent les cinq mesures du contrat, dans l\'ordre', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const entetes = within(screen.getByRole('table')).getAllByRole('columnheader')
      .map((th) => th.textContent)
    expect(entetes).toEqual(['Étape', 'Dues', 'À temps', 'En retard', 'Sautées', 'Encore ouvertes'])
  })

  it('les réponses en pastilles portent le libellé de la table POUR CE TYPE (ordre du serveur)', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const contact = within(screen.getByTestId('controle-type-contact_appel'))
    // contact_appel : `non_joint` → « Pas de réponse », `joint` → « Client joint »,
    // `rappel` → « À rappeler le… » (le modèle de la table).
    const pastilles = contact.getAllByRole('listitem').map((li) => li.textContent)
    expect(pastilles).toEqual(['Pas de réponse 8', 'Client joint 4', 'À rappeler le… 1'])
    // devis : `sans_issue` → « Fait » ; `rappel` → le libellé PROPRE à ce type.
    const devis = within(screen.getByTestId('controle-type-devis'))
    expect(devis.getAllByRole('listitem').map((li) => li.textContent))
      .toEqual(['Fait 3', 'Pas encore — à rappeler le… 1'])
  })

  it('une clé de réponse inconnue de la table s\'affiche telle quelle', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      par_type: [{
        ...CONTROLE.par_type[0],
        reponses: [{ cle: 'reponse_inconnue', n: 2 }],
      }],
    }))
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    expect(within(screen.getByTestId('controle-type-contact_appel')).getByText('reponse_inconnue 2'))
      .toBeInTheDocument()
  })

  it('une clé partagée par plusieurs réponses du type (non_joint sur « generique ») dit « Pas de réponse », jamais « Répondeur »', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      par_type: [{
        type_etape: 'generique', est_tache: false, du: 6, a_temps: 5, en_retard: 1, sautees: 0, ouvert: 0,
        reponses: [{ cle: 'non_joint', n: 5 }, { cle: 'joint', n: 1 }],
      }],
    }))
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const pastilles = within(screen.getByTestId('controle-type-generique')).getAllByRole('listitem')
    expect(pastilles.map((li) => li.textContent)).toEqual(['Pas de réponse 5', 'Client joint 1'])
    expect(screen.getByTestId('controle-detail')).not.toHaveTextContent('Répondeur')
  })

  it('aucun type servi : pas de section détail', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: VIDE })
    monter()
    await attendreVerdict()
    expect(screen.queryByTestId('controle-detail')).not.toBeInTheDocument()
  })
})

describe('ControleSuiviPanel — premier contact et résultats', () => {
  it('premier contact : « 8 sur 9 dans le délai (24 h) · médiane 42 min · plus longue attente 27,5 h »', async () => {
    monter()
    await attendreVerdict()
    const carte = screen.getByTestId('controle-premier-contact')
    expect(carte).toHaveTextContent('Premier contact')
    expect(carte).toHaveTextContent(
      '8 sur 9 dans le délai (24 h) · médiane 42 min · plus longue attente 27,5 h')
  })

  it('résultats : « 3 visites planifiées · 4 devis envoyés · 1 devis accepté »', async () => {
    monter()
    await attendreVerdict()
    const carte = screen.getByTestId('controle-resultats')
    expect(carte).toHaveTextContent('Résultats de la période')
    expect(carte).toHaveTextContent('3 visites planifiées · 4 devis envoyés · 1 devis accepté')
  })

  it('état vide : pas de lead nouveau, résultats à zéro (accord au singulier)', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: VIDE })
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-premier-contact'))
      .toHaveTextContent('Aucun nouveau lead sur la période.')
    expect(screen.getByTestId('controle-resultats'))
      .toHaveTextContent('0 visite planifiée · 0 devis envoyé · 0 devis accepté')
  })

  it('aucun lead en attente / médiane inconnue : dits en clair', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      premier_contact: {
        ...CONTROLE.premier_contact, mediane_minutes: null, plus_longue_attente_heures: null,
      },
    }))
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-premier-contact')).toHaveTextContent(
      '8 sur 9 dans le délai (24 h) · médiane — · aucun lead en attente')
  })
})

describe('ControleSuiviPanel — sélecteurs', () => {
  it('le sélecteur de période envoie 7, 14 ou 30 jours (14 par défaut)', async () => {
    monter()
    await attendreVerdict()
    const periode = screen.getByRole('radiogroup', { name: 'Période' })
    expect(within(periode).getByRole('radio', { name: '14 jours' })).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(within(periode).getByRole('radio', { name: '7 jours' }))
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenLastCalledWith({ jours: 7 }))
    fireEvent.click(within(periode).getByRole('radio', { name: '30 jours' }))
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenLastCalledWith({ jours: 30 }))
    expect(within(periode).getByRole('radio', { name: '30 jours' })).toHaveAttribute('aria-checked', 'true')
  })

  it('changer de période referme la liste d\'un jour ouverte', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByTestId('controle-jour-2026-09-29'))
    await screen.findByTestId('controle-jour-liste')
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Période' })).getByRole('radio', { name: '7 jours' }))
    await waitFor(() => expect(screen.queryByTestId('controle-jour-liste')).not.toBeInTheDocument())
  })

  it('« Commercial » : visible quand le serveur sert plusieurs noms, jamais un prénom écrit dans le code', async () => {
    monter()
    await attendreVerdict()
    const selecteur = screen.getByRole('combobox', { name: 'Commercial' })
    expect(selecteur).toHaveTextContent('Toute l\'équipe')
  })

  it('« Commercial » : masqué quand le serveur ne sert personne (ou un seul nom)', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: VIDE })
    const { unmount } = monter()
    await attendreVerdict()
    expect(screen.queryByRole('combobox', { name: 'Commercial' })).not.toBeInTheDocument()
    unmount()
    crmApi.getControleSuivi.mockResolvedValue(variante({ commerciaux: [CONTROLE.commerciaux[0]] }))
    monter()
    await attendreVerdict()
    expect(screen.queryByRole('combobox', { name: 'Commercial' })).not.toBeInTheDocument()
  })

  it('choisir un commercial envoie owner=<id> (et le garde pour la liste d\'un jour)', async () => {
    const user = userEvent.setup()
    monter()
    await attendreVerdict()
    await user.click(screen.getByRole('combobox', { name: 'Commercial' }))
    await user.click(await screen.findByRole('option', { name: CONTROLE.commerciaux[0].nom }))
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenLastCalledWith(
      { jours: 14, owner: CONTROLE.commerciaux[0].id }))
    await attendreVerdict()
    fireEvent.click(screen.getByTestId('controle-jour-2026-09-29'))
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith({
      date_debut: '2026-09-29', date_fin: '2026-09-29', owner: CONTROLE.commerciaux[0].id,
    }))
    // « Toute l'équipe » retire le filtre.
    await user.click(screen.getByRole('combobox', { name: 'Commercial' }))
    await user.click(await screen.findByRole('option', { name: 'Toute l\'équipe' }))
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenLastCalledWith({ jours: 14 }))
  })

  it('400 sur « jours » : le message du serveur s\'affiche sous le sélecteur de période', async () => {
    const message = '« jours » doit valoir 7, 14 ou 30.'
    monter()
    await attendreVerdict()
    crmApi.getControleSuivi.mockRejectedValueOnce({
      response: { status: 400, data: { erreurs: { jours: message } } },
    })
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Période' })).getByRole('radio', { name: '7 jours' }))
    const alerte = await screen.findByTestId('controle-erreur-jours')
    expect(alerte).toHaveTextContent(message)
    expect(alerte).toHaveAttribute('role', 'alert')
    expect(screen.queryByText('Indisponible pour le moment.')).not.toBeInTheDocument()
  })

  it('400 sur « owner » : le message s\'affiche sous le sélecteur Commercial, qui reste là', async () => {
    const user = userEvent.setup()
    const message = 'Ce responsable est inconnu ou hors de votre portée.'
    monter()
    await attendreVerdict()
    crmApi.getControleSuivi.mockRejectedValueOnce({
      response: { status: 400, data: { erreurs: { owner: message } } },
    })
    await user.click(screen.getByRole('combobox', { name: 'Commercial' }))
    await user.click(await screen.findByRole('option', { name: CONTROLE.commerciaux[1].nom }))
    const alerte = await screen.findByTestId('controle-erreur-owner')
    expect(alerte).toHaveTextContent(message)
    expect(screen.getByRole('combobox', { name: 'Commercial' })).toBeInTheDocument()
  })
})
