import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionContact from './SectionContact'
import SectionPipeline from './SectionPipeline'
import SectionEnergie, { SectionPompage } from './SectionEnergie'
import SectionSite from './SectionSite'
import SectionVisite from './SectionVisite'
import SectionDivers, { SectionOrigine } from './SectionDivers'

/* LW11 — rendu des 6 fichiers de sections. On neutralise les dépendances qui
   feraient un appel réseau au montage (doublons live, canaux, champs perso,
   AppointmentBooker) : ce test vérifie le PORT DES CHAMPS, pas ces satellites. */
vi.mock('../../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => <div data-testid="booker" /> }))

afterEach(() => { cleanup(); vi.clearAllMocks() })

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
