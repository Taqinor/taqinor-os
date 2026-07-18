import { FormField, Input } from '../../../../ui'
import { getField } from '../draftCore'

const TYPES_TOITURE = {
  terrasse_beton: 'Terrasse béton', tole_metal: 'Tôle/Métal', tuiles: 'Tuiles',
  bac_acier: 'Bac acier', fibrociment: 'Fibrociment', autre: 'Autre',
}
const ORIENTATIONS = {
  sud: 'Sud', sud_est: 'Sud-Est', sud_ouest: 'Sud-Ouest',
  est: 'Est', ouest: 'Ouest', autre: 'Autre',
}
const OMBRAGES = { aucun: 'Aucun', partiel: 'Partiel', important: 'Important' }
const STRUCTURES = { acier: 'Acier', aluminium: 'Aluminium' }
const BATTERIES = { sans: 'Sans batterie', avec: 'Avec batterie', les_deux: 'Les deux options' }

const enumOptions = (labels) => [
  <option key="" value="">—</option>,
  ...Object.entries(labels).map(([k, l]) => <option key={k} value={k}>{l}</option>),
]

// LW11 — Toiture & site : port 1:1 des champs (recon 01 §2).
export default function SectionSite({ state, setField }) {
  const v = (k) => getField(state, k) ?? ''
  return (
    <>
      <div className="form-row">
        <FormField label="Type de toiture" htmlFor="lf-type-toiture">
          <select id="lf-type-toiture" className="form-select" value={v('type_toiture')} onChange={(e) => setField('type_toiture', e.target.value)}>
            {enumOptions(TYPES_TOITURE)}
          </select>
        </FormField>
        <FormField label="Surface (m²)" htmlFor="lf-surface-toiture">
          <Input id="lf-surface-toiture" type="number" step="any" value={v('surface_toiture_m2')} onChange={(e) => setField('surface_toiture_m2', e.target.value)} />
        </FormField>
        <FormField label="Taille souhaitée (kWc)" htmlFor="lf-taille-souhaitee">
          <Input id="lf-taille-souhaitee" type="number" step="any" value={v('taille_souhaitee_kwc')} onChange={(e) => setField('taille_souhaitee_kwc', e.target.value)} />
        </FormField>
        <FormField label="Batterie" htmlFor="lf-batterie">
          <select id="lf-batterie" className="form-select" value={v('batterie_souhaitee')} onChange={(e) => setField('batterie_souhaitee', e.target.value)}>
            {enumOptions(BATTERIES)}
          </select>
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Orientation" htmlFor="lf-orientation">
          <select id="lf-orientation" className="form-select" value={v('orientation')} onChange={(e) => setField('orientation', e.target.value)}>
            {enumOptions(ORIENTATIONS)}
          </select>
        </FormField>
        <FormField label="Inclinaison / pente (°)" htmlFor="lf-inclinaison">
          <Input id="lf-inclinaison" type="number" step="any" value={v('inclinaison_deg')} onChange={(e) => setField('inclinaison_deg', e.target.value)} />
        </FormField>
        <FormField label="Ombrage" htmlFor="lf-ombrage">
          <select id="lf-ombrage" className="form-select" value={v('ombrage')} onChange={(e) => setField('ombrage', e.target.value)}>
            {enumOptions(OMBRAGES)}
          </select>
        </FormField>
        <div className="form-group fg-grow">
          <FormField label="Notes ombrage" htmlFor="lf-ombrage-notes">
            <Input id="lf-ombrage-notes" value={v('ombrage_notes')} onChange={(e) => setField('ombrage_notes', e.target.value)} />
          </FormField>
        </div>
      </div>
      <div className="form-row">
        <FormField label="Structure" htmlFor="lf-structure">
          <select id="lf-structure" className="form-select" value={v('structure_pref')} onChange={(e) => setField('structure_pref', e.target.value)}>
            {enumOptions(STRUCTURES)}
          </select>
        </FormField>
        <FormField label="Étages / hauteur" htmlFor="lf-nb-etages">
          <Input id="lf-nb-etages" type="number" step="any" value={v('nb_etages')} onChange={(e) => setField('nb_etages', e.target.value)} />
        </FormField>
      </div>
    </>
  )
}
