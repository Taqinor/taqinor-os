import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as axeMatchers from 'vitest-axe/matchers'
import { initState } from '../draftCore'
import SectionContact from './SectionContact'
import SectionPipeline from './SectionPipeline'
import SectionEnergie, { SectionPompage } from './SectionEnergie'
import SectionSite from './SectionSite'
import SectionVisite from './SectionVisite'
import SectionDivers, { SectionOrigine } from './SectionDivers'
import SectionsPane from '../SectionsPane'

expect.extend(axeMatchers)

/* LW11 — rendu des 6 fichiers de sections. On neutralise les dépendances qui
   feraient un appel réseau au montage (doublons live, canaux, champs perso,
   AppointmentBooker) : ce test vérifie le PORT DES CHAMPS, pas ces satellites. */
vi.mock('../../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => <div data-testid="booker" /> }))

// Le repli des sections est PERSISTÉ (localStorage `taqinor.lw.collapsed`) et
// les choix de l'utilisatrice priment sur le repli automatique : sans ce
// nettoyage, un test qui replie une section dicterait l'état d'ouverture de
// tous les suivants.
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  try { localStorage.clear() } catch { /* noop */ }
})

const base = {
  setField: vi.fn(),
  errors: {},
  mode: 'create',
  refData: { users: [], tagOptions: [], motifOptions: [] },
}
const createState = () => initState({ mode: 'create', currentUserId: 1 })

describe('LW11 — rendu des sections (port 1:1 des champs)', () => {
  it('SectionContact rend #lf-nom, tel, whatsapp, ville, email, GPS', () => {
    render(<SectionContact state={createState()} {...base} />)
    expect(document.querySelector('#lf-nom')).toBeInTheDocument()
    expect(document.querySelector('#lf-telephone')).toBeInTheDocument()
    expect(document.querySelector('#lf-whatsapp')).toBeInTheDocument()
    expect(document.querySelector('#lf-ville')).toBeInTheDocument()
    expect(document.querySelector('#lf-email')).toBeInTheDocument()
    expect(document.querySelector('#lf-gps-lat')).toBeInTheDocument()
  })

  it('SectionPipeline rend type/priorité/canal/tags SANS select d\'étape', () => {
    render(<SectionPipeline state={createState()} {...base} />)
    expect(document.querySelector('#lf-type-installation')).toBeInTheDocument()
    expect(document.querySelector('#lf-priorite')).toBeInTheDocument()
    expect(document.querySelector('#lf-canal')).toBeInTheDocument()
    expect(document.querySelector('#lf-tags')).toBeInTheDocument()
    // L'étape est déléguée au StageControl (LW16) — jamais un select ici.
    expect(document.querySelector('#lf-stage')).toBeNull()
  })

  it('SectionEnergie rend la facture (placeholder e2e « ex: 650 ») + raccordement', () => {
    render(<SectionEnergie state={createState()} {...base} />)
    const hiver = document.querySelector('#lf-facture-hiver')
    expect(hiver).toBeInTheDocument()
    expect(hiver.getAttribute('placeholder')).toBe('ex: 650')
    expect(document.querySelector('#lf-raccordement')).toBeInTheDocument()
  })

  it('SectionPompage rend les 3 champs pompage', () => {
    render(<SectionPompage state={createState()} {...base} />)
    expect(document.querySelector('#lf-pompe-cv')).toBeInTheDocument()
    expect(document.querySelector('#lf-pompe-hmt')).toBeInTheDocument()
    expect(document.querySelector('#lf-pompe-debit')).toBeInTheDocument()
  })

  it('SectionSite rend toiture/surface/orientation/étages', () => {
    render(<SectionSite state={createState()} {...base} />)
    expect(document.querySelector('#lf-type-toiture')).toBeInTheDocument()
    expect(document.querySelector('#lf-surface-toiture')).toBeInTheDocument()
    expect(document.querySelector('#lf-orientation')).toBeInTheDocument()
    expect(document.querySelector('#lf-nb-etages')).toBeInTheDocument()
  })

  it('SectionVisite rend les champs visite (booker masqué en création)', () => {
    render(<SectionVisite state={createState()} {...base} />)
    expect(document.querySelector('#lf-visite-prevue')).toBeInTheDocument()
    expect(document.querySelector('#lf-visite-notes')).toBeInTheDocument()
    expect(screen.queryByTestId('booker')).toBeNull()
  })

  it('SectionDivers rend la note générale', () => {
    render(<SectionDivers state={createState()} {...base} />)
    expect(document.querySelector('#lf-note')).toBeInTheDocument()
  })

  it('SectionOrigine rend les champs web capturés en lecture seule', () => {
    const state = initState({ lead: { id: 1, utm_source: 'meta', roi_band: 'haut' }, mode: 'edit' })
    render(<SectionOrigine state={state} />)
    expect(screen.getByText('UTM source')).toBeInTheDocument()
    expect(screen.getByText('meta')).toBeInTheDocument()
  })
})

/* LW35 — passe a11y axe-core sur SectionsPane MONTÉ (le vrai centre : nav-chips
   de scroll-spy + accordéon de sections, pas les sections isolées ci-dessus).
   `aria-current` sur le chip actif (grep DoD) + boutons repliables natifs
   (aria-expanded déjà posé par WorkspaceSection) : on vérifie qu'aucune
   régression de balisage ne s'y est glissée. */
describe('LW35 — SectionsPane (nav de sections) : axe-core, aucune violation critique', () => {
  it('le centre en édition (nav-chips + sections repliables) n\'a aucune violation axe', async () => {
    const state = initState({ lead: { id: 1, nom: 'Test' }, mode: 'edit' })
    const { container } = render(
      <SectionsPane
        state={state}
        setField={vi.fn()}
        errors={{}}
        mode="edit"
        formId="lw-test-form"
        onSubmit={vi.fn()}
        refData={{ users: [], tagOptions: [], motifOptions: [] }}
      />,
    )
    expect(container.querySelector('.lw-secnav-chip[aria-current="true"]')).toBeInTheDocument()
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})

/* ROUND 5 — BANDEAU « À COMPLÉTER » + REPLI AUTOMATIQUE À L'OUVERTURE.
   ---------------------------------------------------------------------------
   Le verdict de la recherche design : l'ORDRE des sections ne bouge JAMAIS
   (Salesforce Path, HubSpot required-per-stage, et la littérature
   anti-réordonnancement d'Office 2000 à NN/g — un formulaire qui se réorganise
   détruit la mémoire spatiale). L'intuition fondateur « voir d'abord ce qui
   manque selon l'étape » se livre par un bandeau qui POINTE et par un repli
   qui met de côté ce qui est fini. Ces tests protègent exactement ça, plus la
   règle d'or : rien ne se replie PENDANT la session. */
// L'en-tête d'une section, ciblé par son ancre de registre : le libellé seul
// est AMBIGU (le rail de navigation porte les mêmes mots, ce sont aussi des
// boutons) — on vise la vraie tête d'accordéon.
const tete = (container, id) => container.querySelector(`[data-nav-id="${id}"] .lw-section-head`)

function monter(lead, extra = {}) {
  return render(
    <SectionsPane
      state={initState({ lead, mode: 'edit' })}
      setField={vi.fn()}
      errors={{}}
      mode="edit"
      refData={{ users: [], tagOptions: [], motifOptions: [] }}
      {...extra}
    />,
  )
}

const LEAD_COMPLET = {
  id: 1, nom: 'Test', stage: 'NEW',
  telephone: '0600000000', ville: 'Marrakech',
  facture_hiver: 800,
  surface_toiture_m2: 90, orientation: 'sud', type_toiture: 'terrasse',
  devis_auto: { pret: true, manquants: [] },
}

describe('ROUND 5 — bandeau « À compléter »', () => {
  it('ABSENT quand rien ne manque : zéro chrome quand tout va bien', () => {
    const { container } = monter(LEAD_COMPLET)
    expect(container.querySelector('.lw-todo')).toBeNull()
    // Pas non plus de boîte « tout est complet ✓ » : elle occuperait la place
    // à chaque ouverture pour ne rien apprendre (leçon de la « case grise »).
    expect(screen.queryByLabelText('Informations à compléter')).toBeNull()
  })

  it('une chip par manquant du devis, plus la relance attendue par l’ÉTAPE', () => {
    monter({
      ...LEAD_COMPLET,
      stage: 'FOLLOW_UP',
      facture_hiver: null,
      relance_date: null,
      devis_auto: { pret: false, manquants: ['facture hiver'] },
    })
    const bandeau = screen.getByLabelText('Informations à compléter')
    expect(bandeau).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compléter : facture hiver' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compléter : Relance non planifiée' })).toBeInTheDocument()
  })

  it('chips exactes en AGRICOLE (pompage) — les libellés serveur trouvent leur champ', () => {
    monter({
      ...LEAD_COMPLET,
      type_installation: 'agricole',
      devis_auto: { pret: false, manquants: ['pompe (CV)', 'HMT', 'débit souhaité'] },
    })
    for (const l of ['pompe (CV)', 'HMT', 'débit souhaité']) {
      expect(screen.getByRole('button', { name: `Compléter : ${l}` })).toBeInTheDocument()
    }
  })

  it('cliquer une chip DÉPLIE la section cible puis focalise le champ', async () => {
    const { container } = monter({
      ...LEAD_COMPLET,
      facture_hiver: null,
      devis_auto: { pret: false, manquants: ['facture hiver'] },
    })
    // « Énergie » porte un manquant : elle ne s'est donc PAS auto-repliée.
    // On la replie à la main pour vérifier que la chip la rouvre.
    fireEvent.click(tete(container, 'energie'))
    expect(document.getElementById('lf-facture-hiver')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Compléter : facture hiver' }))
    await waitFor(() => expect(document.getElementById('lf-facture-hiver')).toBeInTheDocument())
    await waitFor(() => expect(document.activeElement?.id).toBe('lf-facture-hiver'))
  })
})

describe('ROUND 5 — repli automatique À L’OUVERTURE (jamais pendant la session)', () => {
  it('une section COMPLÈTE s’ouvre repliée, avec une coche discrète', () => {
    const { container } = monter(LEAD_COMPLET)
    // Contact : téléphone + ville renseignés.
    const contact = tete(container, 'contact')
    expect(contact).toHaveAttribute('aria-expanded', 'false')
    expect(contact).toHaveTextContent('✓')
    expect(document.getElementById('lf-telephone')).toBeNull()
  })

  it('une section VIDE sans cœur (Visite) s’ouvre repliée ; la zone de TRAVAIL jamais', () => {
    const { container } = monter(LEAD_COMPLET)
    expect(tete(container, 'visite')).toHaveAttribute('aria-expanded', 'false')
    // Le pipeline est l'outil qu'on a en main : il reste ouvert, complet ou non.
    expect(tete(container, 'pipeline')).toHaveAttribute('aria-expanded', 'true')
  })

  it('une section POINTÉE par le bandeau reste OUVERTE (jamais se contredire)', () => {
    const { container } = monter({
      ...LEAD_COMPLET,
      facture_hiver: 800, // cœur complet…
      devis_auto: { pret: false, manquants: ['facture hiver'] }, // …mais pointée
    })
    expect(tete(container, 'energie')).toHaveAttribute('aria-expanded', 'true')
  })

  it('RIEN ne se replie pendant la session : remplir le dernier champ ne referme pas la section', () => {
    // La stabilité est la règle d'or — l'automatisme n'a droit qu'à l'instant
    // zéro. Ici « Visite » s'ouvre OUVERTE (elle porte une note) ; on vide le
    // lead en re-rendant avec un état complet : elle doit RESTER ouverte.
    const { rerender, container } = render(
      <SectionsPane
        state={initState({ lead: { ...LEAD_COMPLET, telephone: '', ville: '' }, mode: 'edit' })}
        setField={vi.fn()} errors={{}} mode="edit"
        refData={{ users: [], tagOptions: [], motifOptions: [] }}
      />,
    )
    // Contact incomplet → ouverte.
    expect(tete(container, 'contact')).toHaveAttribute('aria-expanded', 'true')
    rerender(
      <SectionsPane
        state={initState({ lead: LEAD_COMPLET, mode: 'edit' })}
        setField={vi.fn()} errors={{}} mode="edit"
        refData={{ users: [], tagOptions: [], motifOptions: [] }}
      />,
    )
    // Le cœur est maintenant complet — et pourtant elle reste OUVERTE.
    expect(tete(container, 'contact')).toHaveAttribute('aria-expanded', 'true')
  })

  it('en CRÉATION, aucun repli automatique : tout est à saisir', () => {
    const { container } = render(
      <SectionsPane
        state={initState({ lead: null, mode: 'create' })}
        setField={vi.fn()} errors={{}} mode="create"
        formId="lw-create" onSubmit={vi.fn()}
        refData={{ users: [], tagOptions: [], motifOptions: [] }}
      />,
    )
    expect(tete(container, 'visite')).toHaveAttribute('aria-expanded', 'true')
    // Le bandeau non plus n'a rien à faire dans un formulaire vierge.
    expect(screen.queryByLabelText('Informations à compléter')).toBeNull()
  })
})
