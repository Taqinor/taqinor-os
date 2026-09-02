import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { initState } from './draftCore'
import SectionsPane from './SectionsPane'

/* CRX36 — le repli automatique des sections est recalculé au CHANGEMENT DE
   LEAD, plus seulement au montage du composant.

   Le workspace ne se démonte PAS quand on passe d'un lead à l'autre (c'est
   tout l'intérêt du shell) : l'initialiseur paresseux de `useState` ne
   s'exécutait donc qu'une fois par session, et le deuxième lead héritait du
   repli calculé sur les données du PREMIER — une section vide restait
   dépliée, une section pleine restait repliée.

   L'oracle du test ne dépend d'AUCUN identifiant de section : on compare
   l'état d'ouverture obtenu par RE-RENDU (lead A → lead B) à celui d'un
   MONTAGE NEUF sur le lead B. Avant le correctif, les deux divergeaient. */

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: {} }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => <div data-testid="booker" /> }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // Le repli est PERSISTÉ (localStorage `taqinor.lw.collapsed`) et les choix
  // de l'utilisatrice priment sur l'auto-repli : sans ce nettoyage, un test
  // dicterait l'état d'ouverture des suivants.
  try { localStorage.clear() } catch { /* noop */ }
})

const base = {
  setField: vi.fn(),
  errors: {},
  mode: 'edit',
  refData: { users: [], tagOptions: [], motifOptions: [] },
}

// Lead A : richement renseigné. Lead B : quasi vide. Deux profils opposés,
// donc deux replis automatiques différents, quels que soient les identifiants
// de sections du registre.
const leadRempli = {
  id: 1,
  nom: 'Bennani', prenom: 'Amina',
  telephone: '0612345678', whatsapp: '0612345678',
  email: 'amina@exemple.ma', adresse: '12 rue X', ville: 'Casablanca',
  gps_lat: 33.5, gps_lng: -7.6,
  facture_hiver: 3500, tranche_onee: 'T3',
  type_toiture: 'terrasse_beton', surface_toiture_m2: 120,
  orientation: 'sud', ombrage: 'aucun',
  visite_notes: 'Toiture accessible', visite_effectuee: true,
  note: 'Client pressé',
}
const leadVide = { id: 2, nom: 'Sans données' }

const etat = (lead) => initState({ lead, mode: 'edit' })
const sectionsDepliees = () => screen
  .getAllByRole('button', { expanded: true })
  .map((b) => b.textContent)
  .sort()

describe('CRX36 — repli des sections recalculé au changement de lead', () => {
  it('les deux profils de lead ne donnent PAS le même repli (oracle du test)', () => {
    render(<SectionsPane state={etat(leadRempli)} {...base} />)
    const surRempli = sectionsDepliees()
    cleanup()
    render(<SectionsPane state={etat(leadVide)} {...base} />)
    const surVide = sectionsDepliees()
    expect(surRempli).not.toEqual(surVide)
  })

  it('changer de lead SANS démonter donne le même repli qu’un montage neuf', () => {
    const { rerender } = render(
      <SectionsPane state={etat(leadRempli)} {...base} />)
    rerender(<SectionsPane state={etat(leadVide)} {...base} />)
    const apresChangement = sectionsDepliees()

    cleanup()
    render(<SectionsPane state={etat(leadVide)} {...base} />)
    const montageNeuf = sectionsDepliees()

    expect(apresChangement).toEqual(montageNeuf)
  })

  it('un re-rendu sur le MÊME lead ne rejoue pas le repli automatique', () => {
    // Replier une section sous les doigts de l'utilisatrice reste pire que ne
    // rien faire : seul un CHANGEMENT DE LEAD recalcule.
    const state = etat(leadVide)
    const { rerender } = render(<SectionsPane state={state} {...base} />)
    const avant = sectionsDepliees()
    // Même leadId, données modifiées en cours de saisie.
    const enCoursDeSaisie = { ...state, fields: { ...state.fields, ville: 'Rabat' } }
    rerender(<SectionsPane state={enCoursDeSaisie} {...base} />)
    expect(sectionsDepliees()).toEqual(avant)
  })
})
