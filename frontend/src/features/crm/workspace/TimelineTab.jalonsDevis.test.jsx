import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ChatterTimeline from '../../../components/ChatterTimeline'
import { matchesTimelineFilter, TIMELINE_FILTERS } from './TimelineTab'

/* CRX37 — les jalons devis entrent dans l'historique du lead.

   `apps.ventes.selectors.devis_events_for_lead` (QX32be) avait été écrit POUR
   cette fusion et n'avait AUCUN appelant. Côté écran tout était déjà prêt
   depuis QX32 — `ChatterTimeline` rend les quatre `kind` (📤 👁️ ✅ ❌) et
   `matchesTimelineFilter` expose le filtre « Devis » — il ne manquait que la
   SOURCE. Ce test IMPORTE le contrat committé côté serveur
   (`apps/crm/contract_samples/lead_jalons_devis.json`), le même que le test
   backend affirme : aucune forme n'est recopiée à la main ici, donc les deux
   moitiés ne peuvent plus diverger en silence (PACT10). */

const here = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  here, '..', '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'crm',
  'contract_samples', 'lead_jalons_devis.json'), 'utf8'))
const JALONS = CONTRAT.exemple.results

afterEach(cleanup)

describe('CRX37 — jalons devis dans la timeline du lead', () => {
  it('le contrat committé porte bien des jalons à rendre', () => {
    expect(JALONS.length).toBeGreaterThan(0)
  })

  it('chaque jalon du contrat tombe dans le filtre « Devis »', () => {
    expect(TIMELINE_FILTERS.map((f) => f.key)).toContain('devis')
    for (const jalon of JALONS) {
      expect(matchesTimelineFilter(jalon.kind, 'devis')).toBe(true)
      expect(matchesTimelineFilter(jalon.kind, 'tous')).toBe(true)
    }
  })

  it("un jalon n'apparaît pas dans les filtres notes / appels / e-mails / système", () => {
    for (const jalon of JALONS) {
      for (const autre of ['notes', 'appels', 'emails', 'systeme']) {
        expect(matchesTimelineFilter(jalon.kind, autre)).toBe(false)
      }
    }
  })

  it('ChatterTimeline rend chaque jalon du contrat avec son libellé FR', () => {
    render(<ChatterTimeline entries={JALONS} />)
    const libelles = {
      devis_sent: 'Devis envoyé',
      devis_opened: 'Proposition ouverte',
      devis_signed: 'Devis signé',
      devis_refused: 'Devis refusé',
    }
    for (const jalon of JALONS) {
      expect(screen.getByText(libelles[jalon.kind])).toBeTruthy()
    }
  })

  it('la référence du devis est visible sur la ligne rendue', () => {
    render(<ChatterTimeline entries={JALONS} />)
    for (const jalon of JALONS) {
      expect(screen.getAllByText(new RegExp(jalon.reference)).length)
        .toBeGreaterThan(0)
    }
  })
})
