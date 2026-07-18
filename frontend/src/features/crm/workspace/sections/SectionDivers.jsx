import { DefinitionList } from '../../../../ui'
import { getField } from '../draftCore'
import CustomFieldsInput from '../../../../components/CustomFieldsInput'

// Champs d'origine web (taqinor.ma) en LECTURE SEULE : capturés par le site,
// jamais édités ici. La section est masquée si tous sont vides (SectionsPane).
export const WEB_ORIGIN_FIELDS = [
  'bill_range_bucket', 'roi_band', 'utm_source', 'utm_medium', 'utm_campaign', 'fbclid',
]
const WEB_ORIGIN_LABELS = {
  bill_range_bucket: 'Tranche de facture (site)',
  roi_band: 'Estimation ROI (site)',
  utm_source: 'UTM source',
  utm_medium: 'UTM medium',
  utm_campaign: 'UTM campagne',
  fbclid: 'fbclid',
}

// LW11 — Origine web : DefinitionList en lecture seule (repliée par défaut,
// géré par SectionsPane). Remplace les <input readOnly disabled> bruts.
export function SectionOrigine({ state }) {
  const server = state.server || {}
  const items = WEB_ORIGIN_FIELDS
    .map((k) => {
      const raw = server[k]
      const val = raw === undefined || raw === null || raw === '' ? '' : String(raw)
      return val ? { term: WEB_ORIGIN_LABELS[k], description: val } : null
    })
    .filter(Boolean)
  if (!items.length) return null
  return <DefinitionList items={items} />
}

// LW11 — Compléments : Note générale + Champs personnalisés — ENFIN dans la nav
// (orphelins du scroll-spy avant, recon 01 §6.9).
export default function SectionDivers({ state, setField }) {
  const note = getField(state, 'note') ?? ''
  const customData = getField(state, 'custom_data') || {}
  return (
    <>
      <div className="form-group">
        <label className="form-label" htmlFor="lf-note">Note générale</label>
        <textarea
          id="lf-note" className="form-control" rows={2}
          value={note} onChange={(e) => setField('note', e.target.value)}
        />
      </div>
      <CustomFieldsInput
        module="lead"
        value={customData}
        onChange={(obj) => setField('custom_data', obj)}
      />
    </>
  )
}
