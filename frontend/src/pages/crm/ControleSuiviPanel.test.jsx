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

// « Anciens leads à placer » : l'aide sous « Dossiers sans prochaine étape » ne se montre
// qu'au responsable / à l'admin (le hook lit le rôle dans le store Redux).
const estResponsable = vi.fn(() => true)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => estResponsable(),
}))

import crmApi from '../../api/crmApi'
import ControleSuiviPanel from './ControleSuiviPanel'

beforeEach(() => {
  estResponsable.mockReturnValue(true)
  crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi'))
  crmApi.getRelanceEtapesSuivi.mockResolvedValue(reponseContrat('crm', 'relance_etapes_suivi'))
})
afterEach(() => { cleanup(); vi.clearAllMocks(); window.localStorage.clear() })

// La préférence « détail déplié » du navigateur (clé posée par le composant).
const CLE_DETAIL = 'crm.cockpit.controle.detail'

/** Le rendu seul, sans toucher à la préférence : un montage de plus dans le MÊME navigateur. */
function rendre() {
  return render(
    <MemoryRouter>
      <ControleSuiviPanel />
    </MemoryRouter>,
  )
}

/** Monte le bloc. Le détail est REPLIÉ par défaut (préférence absente), mais presque
 *  tous les tests lisent son contenu : ils le montent déplié, comme un utilisateur qui
 *  l'a déjà ouvert une fois (préférence mémorisée). `{ detail: null }` = première visite
 *  (aucune préférence) ; `{ detail: false }` = replié explicitement. */
function monter({ detail = true } = {}) {
  if (detail === null) window.localStorage.removeItem(CLE_DETAIL)
  else window.localStorage.setItem(CLE_DETAIL, JSON.stringify(detail))
  return rendre()
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
      '2 étapes en retard, 1 tâche en attente depuis 4 jours ouvrés, '
      + '1 étape reportée plusieurs fois, 1 premier contact hors délai.')
  })

  it('« alerte » (exemple_alerte du contrat) : ▲ rouge, « Action requise », les cinq listes dans la phrase', async () => {
    crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
    monter()
    const verdict = await attendreVerdict()
    expect(verdict).toHaveAttribute('data-niveau', 'alerte')
    expect(verdict).toHaveTextContent('▲')
    // Le mot du niveau n'est plus « En retard » : le niveau peut venir d'un dossier
    // sans prochaine étape ou d'un premier contact hors délai. Les autres mots restent.
    expect(verdict).toHaveTextContent('Action requise')
    expect(verdict.querySelector('span')).toHaveTextContent(/^▲Action requise$/)
    // Le dossier sorti du suivi entre dans la phrase, à sa place (avant le premier contact).
    expect(verdict).toHaveTextContent(
      '2 étapes en retard, 1 tâche en attente depuis 4 jours ouvrés, 1 étape reportée plusieurs fois, '
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

  it('la phrase de période reprend les compteurs du serveur, pourcentage arrondi, avec les reportées', async () => {
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-phrase-periode')).toHaveTextContent(
      'Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %), '
      + '3 traitées en retard, 1 sautée, 2 toujours en retard — dont 6 reportées au moins une fois.')
  })

  it('aucune reportée : la phrase de période s\'arrête à « toujours en retard », sans « dont »', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      verdict: verdictAvec({ reportees: 0 }),
    }))
    monter()
    await attendreVerdict()
    const phrase = screen.getByTestId('controle-phrase-periode')
    expect(phrase).toHaveTextContent('2 toujours en retard.')
    expect(phrase).not.toHaveTextContent('dont')
    expect(phrase).not.toHaveTextContent('reportée')
  })

  it('une seule reportée : « dont 1 reportée au moins une fois » (singulier)', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      verdict: verdictAvec({ reportees: 1 }),
    }))
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-phrase-periode'))
      .toHaveTextContent('2 toujours en retard — dont 1 reportée au moins une fois.')
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
      name: 'vendredi 18 septembre : 4 dues, 3 à temps, 1 traitée en retard',
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
    // Règle du retard en JOURS OUVRÉS : rouge = il en reste EN RETARD, en cours =
    // encore dans les temps (aujourd'hui, ou un jour sans jour ouvré écoulé depuis).
    expect(legende).toHaveTextContent('il en reste en retard')
    expect(legende).toHaveTextContent('encore dans les temps')
    expect(legende).not.toHaveTextContent('journée en cours')
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

  describe('étapes « annulée » (retirées du plan par le moteur)', () => {
    // Le même exemple du contrat, auquel on ajoute des touches `annulee` : la liste
    // du jour n'en montre AUCUNE ligne (autant de lignes que le `du` de la case) et
    // dit en une phrase discrète combien ont été mises de côté.
    const annulee = (id) => ({
      ...SUIVI.results[0], id, statut: 'annulee', statut_libelle: 'Annulée (moteur)',
      libelle: `Touche retirée ${id}`, traite_le: null, traite_par_nom: '',
    })
    const servir = (results) => crmApi.getRelanceEtapesSuivi
      .mockResolvedValue({ data: { ...SUIVI, count: results.length, results } })
    const ouvrirLeJour = async () => {
      monter()
      await attendreVerdict()
      fireEvent.click(screen.getByTestId('controle-jour-2026-09-29'))
      return screen.findByTestId('controle-jour-liste')
    }

    it('aucune ligne pour une annulée ; une phrase discrète dit combien (singulier)', async () => {
      servir([...SUIVI.results, annulee(900)])
      const liste = await ouvrirLeJour()
      const lignes = await within(liste).findAllByTestId('controle-jour-ligne')
      expect(lignes).toHaveLength(SUIVI.results.length)
      expect(liste).not.toHaveTextContent('Touche retirée 900')
      expect(liste).not.toHaveTextContent('Annulée (moteur)')
      expect(within(liste).getByTestId('controle-jour-annulees'))
        .toHaveTextContent('1 étape annulée par le moteur — hors compte')
    })

    it('plusieurs annulées : accord au pluriel, toujours aucune ligne pour elles', async () => {
      servir([annulee(901), ...SUIVI.results, annulee(902)])
      const liste = await ouvrirLeJour()
      expect(await within(liste).findAllByTestId('controle-jour-ligne')).toHaveLength(SUIVI.results.length)
      expect(within(liste).getByTestId('controle-jour-annulees'))
        .toHaveTextContent('2 étapes annulées par le moteur — hors compte')
    })

    it('rien que des annulées : « aucune étape n\'était due » + la phrase discrète', async () => {
      servir([annulee(903)])
      const liste = await ouvrirLeJour()
      expect(await within(liste).findByText('Aucune étape n\'était due ce jour-là.')).toBeInTheDocument()
      expect(within(liste).queryByTestId('controle-jour-ligne')).not.toBeInTheDocument()
      expect(within(liste).getByTestId('controle-jour-annulees'))
        .toHaveTextContent('1 étape annulée par le moteur — hors compte')
    })

    it('aucune annulée : pas de phrase (jamais « 0 étape annulée »)', async () => {
      const liste = await ouvrirLeJour()
      await within(liste).findAllByTestId('controle-jour-ligne')
      expect(within(liste).queryByTestId('controle-jour-annulees')).not.toBeInTheDocument()
      expect(liste).not.toHaveTextContent('annulée')
    })
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
      taches_en_attente: ['Tâches en attente depuis 2 jours ouvrés ou plus', '1'],
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

  it('« En retard » : nom du lead (lien), libellé, type lu dans la table, « en retard de N jour(s) ouvré(s) », responsable', async () => {
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
    // `jours_de_retard` est en JOURS OUVRÉS (contrat `notes.retard`) : la ligne le dit.
    expect(ligne).toHaveTextContent('en retard de 1 jour ouvré')
    expect(ligne).not.toHaveTextContent('depuis 1 jour')
    // `nb_reports` = 0 dans l'exemple : rien à dire sur un report.
    expect(ligne).not.toHaveTextContent('reportée')
    expect(ligne).toHaveTextContent('Responsable : commerciale')
  })

  it('« Tâches en attente » : « posée il y a N jours ouvrés », « reportée N fois », type lu dans la table', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('taches_en_attente')).getByTestId('controle-exception-ligne')
    expect(within(ligne).getByRole('link', { name: 'Youssef Bennani' }))
      .toHaveAttribute('href', '/crm/leads?lead=1502')
    expect(ligne).toHaveTextContent('posée il y a 4 jours ouvrés')
    // La tâche a été repoussée deux fois : la ligne le dit (aussi sur les tâches en attente).
    expect(ligne).toHaveTextContent('reportée 2 fois')
    expect(ligne).toHaveTextContent(PARCOURS.etapes.find((t) => t.id === 'devis').nom)
    // Dans la liste des tâches, « Tâche » irait de soi : pas de pastille redondante.
    expect(within(ligne).queryByText('Tâche')).not.toBeInTheDocument()
  })

  it('« reportée N fois » sur une étape en retard reportée au moins une fois (nb_reports servi)', async () => {
    const ligneRetard = CONTROLE.exceptions.en_retard.lignes[0]
    crmApi.getControleSuivi.mockResolvedValue(variante({
      exceptions: {
        ...CONTROLE.exceptions,
        en_retard: { ...CONTROLE.exceptions.en_retard, lignes: [{ ...ligneRetard, nb_reports: 1 }] },
      },
    }))
    monter()
    await attendreVerdict()
    const ligne = within(bloc('en_retard')).getByTestId('controle-exception-ligne')
    expect(ligne).toHaveTextContent('en retard de 1 jour ouvré · reportée 1 fois · Responsable : commerciale')
  })

  it('la liste « Reportées plusieurs fois » garde SA phrase (pas de « reportée N fois » en double)', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('reports')).getByTestId('controle-exception-ligne')
    expect(ligne).toHaveTextContent('2 reports — prévue à l\'origine le 27/09')
    expect(ligne).not.toHaveTextContent('reportée 2 fois')
  })

  it('« Reportées plusieurs fois » : « N reports — prévue à l\'origine le JJ/MM »', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('reports')).getByTestId('controle-exception-ligne')
    expect(ligne).toHaveTextContent('2 reports — prévue à l\'origine le 27/09')
    // Une TÂCHE dans une autre liste que « Tâches en attente » porte sa pastille.
    expect(within(ligne).getByText('Tâche')).toBeInTheDocument()
  })

  it('« Premier contact hors délai » : « attend depuis N h » sous 48 h (décimale française)', async () => {
    monter()
    await attendreVerdict()
    const ligne = within(bloc('premier_contact_hors_delai')).getByTestId('controle-exception-ligne')
    expect(within(ligne).getByRole('link', { name: 'Karim El Fassi' }))
      .toHaveAttribute('href', '/crm/leads?lead=1511')
    expect(ligne).toHaveTextContent('attend depuis 27,5 h')
    expect(ligne).toHaveTextContent('Responsable : commerciale')
  })

  it('« Premier contact hors délai » : à partir de 48 h, « attend depuis 4 jours ouvrés » (99,1 h, arrondi vers le bas)', async () => {
    const ligneServie = CONTROLE.exceptions.premier_contact_hors_delai.lignes[0]
    const avecAttente = (heures) => variante({
      exceptions: {
        ...CONTROLE.exceptions,
        premier_contact_hors_delai: {
          total: 1, lignes: [{ ...ligneServie, attend_depuis_heures: heures }],
        },
      },
    })
    crmApi.getControleSuivi.mockResolvedValue(avecAttente(99.1))
    const { unmount } = monter()
    await attendreVerdict()
    const ligne = within(bloc('premier_contact_hors_delai')).getByTestId('controle-exception-ligne')
    expect(ligne).toHaveTextContent('attend depuis 4 jours ouvrés')
    expect(ligne).not.toHaveTextContent('99')
    expect(ligne.textContent).not.toMatch(/\d\s*h\b/)
    unmount()
    // La frontière : 47,9 h reste en heures, 48 h passe en jours ouvrés.
    crmApi.getControleSuivi.mockResolvedValue(avecAttente(47.9))
    const second = monter()
    await attendreVerdict()
    expect(within(bloc('premier_contact_hors_delai')).getByTestId('controle-exception-ligne'))
      .toHaveTextContent('attend depuis 47,9 h')
    second.unmount()
    crmApi.getControleSuivi.mockResolvedValue(avecAttente(48))
    monter()
    await attendreVerdict()
    expect(within(bloc('premier_contact_hors_delai')).getByTestId('controle-exception-ligne'))
      .toHaveTextContent('attend depuis 2 jours ouvrés')
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

    it('responsable / admin : une aide sous la liste renvoie à la carte « Anciens leads à placer »', async () => {
      estResponsable.mockReturnValue(true)
      crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
      monter()
      await attendreVerdict()
      const aide = within(bloc('sans_prochaine_etape')).getByTestId('controle-aide-sans_prochaine_etape')
      expect(aide).toHaveTextContent(
        'Pour les remettre dans une cadence : carte « Anciens leads à placer », plus bas.')
      // Sous la liste des dossiers, jamais avant elle.
      const liste = within(bloc('sans_prochaine_etape')).getByRole('list')
      expect(liste.compareDocumentPosition(aide) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('un rôle « normal » (commerciale) ne voit PAS cette aide : la carte visée ne lui est pas montrée', async () => {
      estResponsable.mockReturnValue(false)
      crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
      monter()
      await attendreVerdict()
      expect(bloc('sans_prochaine_etape')).toBeInTheDocument()
      expect(screen.queryByTestId('controle-aide-sans_prochaine_etape')).not.toBeInTheDocument()
      expect(screen.getByTestId('controle-suivi-panel')).not.toHaveTextContent('Anciens leads à placer')
    })

    it('cette aide n\'est que pour cette liste (pas sous « En retard » ni les autres)', async () => {
      estResponsable.mockReturnValue(true)
      crmApi.getControleSuivi.mockResolvedValue({ data: ALERTE })
      monter()
      await attendreVerdict()
      expect(screen.getAllByText(/Anciens leads à placer/)).toHaveLength(1)
      expect(within(bloc('en_retard')).queryByText(/Anciens leads à placer/)).not.toBeInTheDocument()
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

  it('la règle des jours ouvrés ne s\'affiche que devant une liste de retard ou d\'attente', async () => {
    // Ni « En retard » ni « Tâches en attente » : seules restent reports et premier contact.
    crmApi.getControleSuivi.mockResolvedValue(variante({
      exceptions: {
        ...VIDE.exceptions,
        reports: CONTROLE.exceptions.reports,
        premier_contact_hors_delai: CONTROLE.exceptions.premier_contact_hors_delai,
      },
    }))
    monter()
    await attendreVerdict()
    const note = screen.getByTestId('controle-seuils')
    expect(note).toHaveTextContent('Alerte dès 2 jours ouvrés de retard.')
    expect(note).not.toHaveTextContent('Week-ends')
  })

  it('dit le seuil d\'alerte servi par le serveur (les trois autres sont dans les titres)', async () => {
    monter()
    await attendreVerdict()
    expect(CONTROLE.seuils.retard_alerte_jours).toBe(2)
    expect(screen.getByTestId('controle-seuils')).toHaveTextContent(
      'Alerte dès 2 jours ouvrés de retard. Week-ends, jours fériés et absences déclarées ne comptent pas.')
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
      expect(titreDe('taches_en_attente')).toHaveTextContent('Tâches en attente depuis 7 jours ouvrés ou plus')
      expect(titreDe('reports')).toHaveTextContent('Reportées 4 fois ou plus')
      expect(titreDe('premier_contact_hors_delai')).toHaveTextContent('Premier contact hors délai (48 h)')
      expect(titreDe('en_retard')).toHaveTextContent('En retard')
      expect(screen.getByTestId('controle-seuils')).toHaveTextContent('Alerte dès 5 jours ouvrés de retard.')
      // Aucun des nombres de l'exemple ne survit dans les libellés.
      const section = screen.getByTestId('controle-exceptions')
      expect(section).not.toHaveTextContent('depuis 2 jours ouvrés ou plus')
      expect(section).not.toHaveTextContent('2 fois ou plus')
      expect(section).not.toHaveTextContent('(24 h)')
      expect(section).not.toHaveTextContent('Alerte dès 2 jours')
    })

    it('les accords suivent le seuil : « 1 jour ouvré ou plus », heures décimales', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecSeuils({
        retard_alerte_jours: 1, tache_attente_jours: 1, reports_min: 1, premier_contact_heures: 1.5,
      }))
      monter()
      await attendreVerdict()
      const section = screen.getByTestId('controle-exceptions')
      expect(section).toHaveTextContent('Tâches en attente depuis 1 jour ouvré ou plus')
      expect(section).not.toHaveTextContent('1 jours')
      expect(section).not.toHaveTextContent('1 jour ouvrés')
      expect(section).toHaveTextContent('Reportées 1 fois ou plus')
      expect(section).toHaveTextContent('Premier contact hors délai (1,5 h)')
      expect(screen.getByTestId('controle-seuils')).toHaveTextContent('Alerte dès 1 jour ouvré de retard.')
    })

    it('sans bloc `seuils` : titres génériques, aucun nombre inventé, la règle des jours ouvrés seule', async () => {
      const sansSeuils = { ...CONTROLE }
      delete sansSeuils.seuils
      crmApi.getControleSuivi.mockResolvedValue({ data: sansSeuils })
      monter()
      await attendreVerdict()
      const titreDe = (cle) => within(bloc(cle)).getByRole('button', { expanded: true })
      expect(titreDe('taches_en_attente')).toHaveTextContent(/^Tâches en attente\s*1$/)
      expect(titreDe('reports')).toHaveTextContent(/^Reportées plusieurs fois\s*1$/)
      expect(titreDe('premier_contact_hors_delai')).toHaveTextContent(/^Premier contact hors délai\s*1$/)
      // Seuil d'alerte non servi : pas de « Alerte dès … » ; la règle, elle, ne porte aucun nombre.
      const note = screen.getByTestId('controle-seuils')
      expect(note).toHaveTextContent(/^Week-ends, jours fériés et absences déclarées ne comptent pas\.$/)
      expect(note).not.toHaveTextContent('Alerte dès')
      expect(note.textContent).not.toMatch(/\d/)
    })

    it('un seuil manquant ne rend générique que SA liste', async () => {
      crmApi.getControleSuivi.mockResolvedValue(avecSeuils({
        retard_alerte_jours: 2, tache_attente_jours: 9, premier_contact_heures: 12,
      }))
      monter()
      await attendreVerdict()
      const titreDe = (cle) => within(bloc(cle)).getByRole('button', { expanded: true })
      expect(titreDe('taches_en_attente')).toHaveTextContent('Tâches en attente depuis 9 jours ouvrés ou plus')
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

  it('une ligne par type, nommée d\'après la TABLE du parcours, avec ses six compteurs', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const contact = screen.getByTestId('controle-type-contact_appel')
    const nom = PARCOURS.etapes.find((t) => t.id === 'contact_appel').nom
    expect(within(contact).getByRole('rowheader')).toHaveTextContent(nom)
    // La première ligne du type porte ses six compteurs (dues, à temps, traitées
    // en retard, sautées, toujours en retard, reportées) ; la seconde, ses réponses.
    const [chiffres] = within(contact).getAllByRole('row')
    expect(within(chiffres).getAllByRole('cell').map((c) => c.textContent))
      .toEqual(['14', '12', '1', '1', '0', '2'])
    expect(within(contact).queryByText('Tâche')).not.toBeInTheDocument()

    const devis = screen.getByTestId('controle-type-devis')
    expect(within(devis).getByRole('rowheader'))
      .toHaveTextContent(PARCOURS.etapes.find((t) => t.id === 'devis').nom)
    expect(within(devis).getByText('Tâche')).toBeInTheDocument()
    expect(within(within(devis).getAllByRole('row')[0]).getAllByRole('cell').map((c) => c.textContent))
      .toEqual(['5', '3', '1', '0', '1', '1'])
  })

  it('les colonnes portent les six mesures du contrat, dans l\'ordre', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const entetes = within(screen.getByRole('table')).getAllByRole('columnheader')
      .map((th) => th.textContent)
    expect(entetes).toEqual([
      'Étape', 'Dues', 'À temps', 'Traitées en retard', 'Sautées', 'Toujours en retard', 'Reportées',
    ])
  })

  it('la ligne des réponses couvre les sept colonnes, et la note du tableau tient en une phrase', async () => {
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const contact = within(screen.getByTestId('controle-type-contact_appel'))
    const reponses = contact.getAllByRole('row')[1]
    expect(within(reponses).getAllByRole('cell')[0]).toHaveAttribute('colspan', '7')
    const note = within(screen.getByTestId('controle-detail')).getByText(/Traitées en retard : /)
    expect(note.textContent).toBe(
      'Traitées en retard : faites après leur jour ; toujours en retard : pas encore faites alors que '
      + 'leur jour est passé ; reportées : décalées au moins une fois.')
    // Une seule phrase : un seul point, à la fin.
    expect(note.textContent.match(/\./g)).toHaveLength(1)
  })

  it('un type sans `reportees` servi affiche « — » (jamais un 0 inventé)', async () => {
    const { reportees: _omis, ...sansReportees } = CONTROLE.par_type[0]
    crmApi.getControleSuivi.mockResolvedValue(variante({ par_type: [sansReportees] }))
    monter()
    await attendreVerdict()
    fireEvent.click(screen.getByRole('button', { name: 'Détail par étape' }))
    const contact = screen.getByTestId('controle-type-contact_appel')
    expect(within(within(contact).getAllByRole('row')[0]).getAllByRole('cell').map((c) => c.textContent))
      .toEqual(['14', '12', '1', '1', '0', '—'])
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
  it('premier contact : « 8 sur 9 contactés dans le délai (24 h) · délai médian 42 min (heures ouvrées) · plus longue attente : 27,5 h »', async () => {
    monter()
    await attendreVerdict()
    const carte = screen.getByTestId('controle-premier-contact')
    expect(carte).toHaveTextContent('Premier contact')
    expect(carte).toHaveTextContent(
      '8 sur 9 contactés dans le délai (24 h) · délai médian 42 min (heures ouvrées) · plus longue attente : 27,5 h')
  })

  it('premier contact : une attente de 48 h et plus se dit en jours ouvrés entiers', async () => {
    crmApi.getControleSuivi.mockResolvedValue(variante({
      premier_contact: {
        nouveaux: 23, dans_le_delai: 19, delai_heures: 24, mediane_minutes: 71, plus_longue_attente_heures: 99.1,
      },
    }))
    monter()
    await attendreVerdict()
    expect(screen.getByTestId('controle-premier-contact')).toHaveTextContent(
      '19 sur 23 contactés dans le délai (24 h) · délai médian 1 h 11 (heures ouvrées) · plus longue attente : 4 jours ouvrés')
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
      '8 sur 9 contactés dans le délai (24 h) · délai médian — · aucun lead en attente')
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

describe('ControleSuiviPanel — détail repliable (replié par défaut, mémorisé par navigateur)', () => {
  // Tout ce qui est DERRIÈRE le bouton : sélecteurs, comparaison, frise, listes
  // d'exceptions, détail par étape, premier contact, résultats.
  const DU_DETAIL = [
    'controle-selecteurs', 'controle-comparaison', 'controle-frise', 'controle-exceptions',
    'controle-detail', 'controle-premier-contact', 'controle-resultats',
  ]
  const bouton = (nom) => screen.getByRole('button', { name: nom })

  it('première visite : replié — le titre, le bandeau du verdict, la phrase de la période et le bouton seulement', async () => {
    monter({ detail: null })
    const verdict = await attendreVerdict()
    expect(screen.getByRole('heading', { name: /Contrôle du suivi/ })).toBeInTheDocument()
    expect(verdict).toHaveAttribute('data-niveau', 'attention')
    expect(verdict).toHaveTextContent('À surveiller')
    expect(screen.getByTestId('controle-phrase-periode'))
      .toHaveTextContent('Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %)')
    expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
    for (const id of DU_DETAIL) expect(screen.queryByTestId(id)).not.toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: 'Période' })).not.toBeInTheDocument()
    expect(screen.queryByTestId('controle-detail-corps')).not.toBeInTheDocument()
  })

  it('la requête part au montage même replié (période par défaut), et déplier ne la relance pas', async () => {
    monter({ detail: null })
    await attendreVerdict()
    expect(crmApi.getControleSuivi).toHaveBeenCalledTimes(1)
    expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 14 })
    expect(crmApi.getRelanceEtapesSuivi).not.toHaveBeenCalled()
    fireEvent.click(bouton('Voir le détail'))
    fireEvent.click(bouton('Masquer le détail'))
    expect(crmApi.getControleSuivi).toHaveBeenCalledTimes(1)
  })

  it('« Voir le détail » déplie (aria-expanded, aria-controls), « Masquer le détail » replie', async () => {
    monter({ detail: null })
    await attendreVerdict()
    fireEvent.click(bouton('Voir le détail'))
    const masquer = bouton('Masquer le détail')
    expect(masquer).toHaveAttribute('aria-expanded', 'true')
    const corps = screen.getByTestId('controle-detail-corps')
    expect(corps.id).not.toBe('')
    expect(masquer.getAttribute('aria-controls')).toBe(corps.id)
    for (const id of DU_DETAIL) expect(within(corps).getByTestId(id)).toBeInTheDocument()
    // Le bandeau reste AU-DESSUS du bouton : il n'est pas dans le détail.
    expect(within(corps).queryByTestId('controle-verdict')).not.toBeInTheDocument()
    expect(within(corps).queryByTestId('controle-phrase-periode')).not.toBeInTheDocument()
    expect(screen.getByTestId('controle-verdict')).toBeInTheDocument()

    fireEvent.click(masquer)
    expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
    for (const id of DU_DETAIL) expect(screen.queryByTestId(id)).not.toBeInTheDocument()
    expect(screen.getByTestId('controle-verdict')).toBeInTheDocument()
  })

  it('le bouton se manœuvre au clavier (Entrée)', async () => {
    const user = userEvent.setup()
    monter({ detail: null })
    await attendreVerdict()
    bouton('Voir le détail').focus()
    await user.keyboard('{Enter}')
    expect(bouton('Masquer le détail')).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Enter}')
    expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
  })

  it('mémorisé par navigateur : déplié une fois, il reste déplié au montage suivant', async () => {
    const { unmount } = monter({ detail: null })
    await attendreVerdict()
    fireEvent.click(bouton('Voir le détail'))
    expect(window.localStorage.getItem(CLE_DETAIL)).toBe('true')
    unmount()
    rendre()
    await attendreVerdict()
    expect(bouton('Masquer le détail')).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('controle-frise')).toBeInTheDocument()
  })

  it('replié à nouveau : le choix inverse est mémorisé lui aussi', async () => {
    const { unmount } = monter({ detail: true })
    await attendreVerdict()
    fireEvent.click(bouton('Masquer le détail'))
    expect(window.localStorage.getItem(CLE_DETAIL)).toBe('false')
    unmount()
    rendre()
    await attendreVerdict()
    expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('controle-frise')).not.toBeInTheDocument()
  })

  it('jamais par rôle : une seule clé, même comportement pour un responsable et pour une commerciale', async () => {
    for (const responsable of [true, false]) {
      estResponsable.mockReturnValue(responsable)
      window.localStorage.clear()
      const { unmount } = monter({ detail: null })
      await attendreVerdict()
      expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
      fireEvent.click(bouton('Voir le détail'))
      expect(bouton('Masquer le détail')).toHaveAttribute('aria-expanded', 'true')
      expect(window.localStorage).toHaveLength(1)
      expect(window.localStorage.key(0)).toBe(CLE_DETAIL)
      unmount()
    }
  })

  it('préférence illisible ou inattendue : replié (le défaut), jamais une erreur', async () => {
    for (const brut of ['pas du json', '"oui"', '1', 'null']) {
      window.localStorage.setItem(CLE_DETAIL, brut)
      const { unmount } = rendre()
      await attendreVerdict()
      expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
      unmount()
    }
  })

  it('stockage indisponible : replié, et le bouton fonctionne quand même (sans mémoire)', async () => {
    const lecture = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('refusé') })
    const ecriture = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('refusé') })
    try {
      rendre()
      await attendreVerdict()
      expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
      fireEvent.click(bouton('Voir le détail'))
      expect(bouton('Masquer le détail')).toHaveAttribute('aria-expanded', 'true')
      expect(screen.getByTestId('controle-frise')).toBeInTheDocument()
      // Le stockage a bien été SOLLICITÉ (et a refusé) : le test n'est pas à vide.
      expect(lecture).toHaveBeenCalledWith(CLE_DETAIL)
      expect(ecriture).toHaveBeenCalled()
    } finally {
      lecture.mockRestore()
      ecriture.mockRestore()
    }
  })

  it('un refus 400 qui nomme un champ déplie le détail pour montrer le message sous ce champ', async () => {
    const message = '« jours » doit valoir 7, 14 ou 30.'
    crmApi.getControleSuivi.mockRejectedValueOnce({
      response: { status: 400, data: { erreurs: { jours: message } } },
    })
    monter({ detail: null })
    const alerte = await screen.findByTestId('controle-erreur-jours')
    expect(alerte).toHaveTextContent(message)
    expect(alerte).toHaveAttribute('role', 'alert')
    expect(bouton('Masquer le détail')).toHaveAttribute('aria-expanded', 'true')
    expect(within(screen.getByTestId('controle-detail-corps')).getByRole('radiogroup', { name: 'Période' }))
      .toBeInTheDocument()
    // Ouverture forcée par l'erreur, pas un choix : rien n'est mémorisé.
    expect(window.localStorage.getItem(CLE_DETAIL)).toBeNull()
  })

  it('serveur indisponible, détail replié : le message et « Réessayer » restent visibles', async () => {
    crmApi.getControleSuivi.mockRejectedValueOnce(new Error('boom'))
    monter({ detail: null })
    expect(await screen.findByTestId('controle-panne')).toHaveTextContent('Indisponible pour le moment.')
    expect(bouton('Voir le détail')).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await attendreVerdict()
    expect(screen.queryByTestId('controle-panne')).not.toBeInTheDocument()
  })

  it('premier chargement : le squelette du bandeau seul quand replié, avec celui du détail quand déplié', async () => {
    crmApi.getControleSuivi.mockReturnValue(new Promise(() => {}))
    const replie = monter({ detail: null })
    expect(screen.getByTestId('controle-squelette')).toBeInTheDocument()
    expect(screen.queryByTestId('controle-squelette-detail')).not.toBeInTheDocument()
    expect(bouton('Voir le détail')).toBeInTheDocument()
    replie.unmount()

    monter({ detail: true })
    expect(screen.getByTestId('controle-squelette')).toBeInTheDocument()
    expect(screen.getByTestId('controle-squelette-detail')).toBeInTheDocument()
    // Les sélecteurs sont déjà là pendant le chargement.
    expect(screen.getByRole('radiogroup', { name: 'Période' })).toBeInTheDocument()
  })

  it('un commercial choisi reste dit près du titre quand le détail (donc le sélecteur) est replié', async () => {
    const user = userEvent.setup()
    monter({ detail: true })
    await attendreVerdict()
    expect(screen.queryByTestId('controle-commercial-actif')).not.toBeInTheDocument()
    await user.click(screen.getByRole('combobox', { name: 'Commercial' }))
    await user.click(await screen.findByRole('option', { name: CONTROLE.commerciaux[0].nom }))
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenLastCalledWith(
      { jours: 14, owner: CONTROLE.commerciaux[0].id }))
    fireEvent.click(bouton('Masquer le détail'))
    expect(screen.getByTestId('controle-commercial-actif'))
      .toHaveTextContent(`Commercial : ${CONTROLE.commerciaux[0].nom}`)
    // Le filtre survit au repli : redéplié, le sélecteur le montre encore.
    fireEvent.click(bouton('Voir le détail'))
    expect(screen.getByRole('combobox', { name: 'Commercial' }))
      .toHaveTextContent(CONTROLE.commerciaux[0].nom)
    // « Toute l'équipe » : plus de mention.
    await user.click(screen.getByRole('combobox', { name: 'Commercial' }))
    await user.click(await screen.findByRole('option', { name: 'Toute l\'équipe' }))
    await waitFor(() => expect(screen.queryByTestId('controle-commercial-actif')).not.toBeInTheDocument())
  })
})
