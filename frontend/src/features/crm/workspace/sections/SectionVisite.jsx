import { FormField, Input } from '../../../../ui'
import { getField } from '../draftCore'
import AppointmentBooker from '../../../../pages/crm/leads/AppointmentBooker'

// LW11 — Visite technique : port 1:1 + AppointmentBooker embarqué (satellite
// conservé en place), édition uniquement.
export default function SectionVisite({ state, setField, mode, refData = {} }) {
  const v = (k) => getField(state, k) ?? ''
  const visiteEffectuee = !!getField(state, 'visite_effectuee')
  const { leadId } = refData
  return (
    <>
      <div className="form-row">
        <FormField label="Visite prévue le" htmlFor="lf-visite-prevue">
          <Input id="lf-visite-prevue" type="date" value={v('visite_prevue_le')} onChange={(e) => setField('visite_prevue_le', e.target.value)} />
        </FormField>
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input
              type="checkbox" checked={visiteEffectuee}
              onChange={(e) => setField('visite_effectuee', e.target.checked)}
            />
            <span>Visite effectuée</span>
          </label>
        </div>
        <div className="form-group fg-grow">
          <FormField label="Notes de visite" htmlFor="lf-visite-notes">
            <Input id="lf-visite-notes" value={v('visite_notes')} onChange={(e) => setField('visite_notes', e.target.value)} />
          </FormField>
        </div>
      </div>
      {/* QJ20 — Planifier une visite (inline, édition seulement). */}
      {mode === 'edit' && leadId != null && <AppointmentBooker leadId={leadId} />}
    </>
  )
}
