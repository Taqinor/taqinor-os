import { FormField, Input } from '../../../../ui'
import { getField } from '../draftCore'
import TraceToitClient from './TraceToitClient'

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
// L-DESSIN (fondateur 25/08/2026) — en TÊTE de section, le tracé que le client
// a dessiné sur la carte du site public. `roof_point`/`roof_outline` sont des
// champs SERVEUR en lecture seule (jamais éditables ici) : on les lit donc sur
// `state.server` via getField, comme IdentityRail.
export default function SectionSite({ state, setField, errors = {} }) {
  const v = (k) => getField(state, k) ?? ''
  return (
    <>
      {/* VT13 — `leadId` (id serveur du lead, jamais un brouillon) laisse le
          bloc demander au serveur la photo réelle du toit issue de la visite
          terrain validée ; absent (création), rien ne change. */}
      <TraceToitClient
        contour={getField(state, 'roof_outline')}
        epingle={getField(state, 'roof_point')}
        leadId={state?.server?.id ?? null}
      />
      <div className="form-row">
        <FormField label="Type de toiture" htmlFor="lf-type-toiture" error={errors.type_toiture}>
          <select
            id="lf-type-toiture" className={errors.type_toiture ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.type_toiture ? true : undefined}
            value={v('type_toiture')} onChange={(e) => setField('type_toiture', e.target.value)}
          >
            {enumOptions(TYPES_TOITURE)}
          </select>
        </FormField>
        <FormField label="Surface (m²)" htmlFor="lf-surface-toiture" error={errors.surface_toiture_m2}>
          <Input
            id="lf-surface-toiture" type="number" step="any" invalid={!!errors.surface_toiture_m2}
            value={v('surface_toiture_m2')} onChange={(e) => setField('surface_toiture_m2', e.target.value)}
          />
        </FormField>
        <FormField label="Taille souhaitée (kWc)" htmlFor="lf-taille-souhaitee" error={errors.taille_souhaitee_kwc}>
          <Input
            id="lf-taille-souhaitee" type="number" step="any" invalid={!!errors.taille_souhaitee_kwc}
            value={v('taille_souhaitee_kwc')} onChange={(e) => setField('taille_souhaitee_kwc', e.target.value)}
          />
        </FormField>
        <FormField label="Batterie" htmlFor="lf-batterie" error={errors.batterie_souhaitee}>
          <select
            id="lf-batterie" className={errors.batterie_souhaitee ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.batterie_souhaitee ? true : undefined}
            value={v('batterie_souhaitee')} onChange={(e) => setField('batterie_souhaitee', e.target.value)}
          >
            {enumOptions(BATTERIES)}
          </select>
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Orientation" htmlFor="lf-orientation" error={errors.orientation}>
          <select
            id="lf-orientation" className={errors.orientation ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.orientation ? true : undefined}
            value={v('orientation')} onChange={(e) => setField('orientation', e.target.value)}
          >
            {enumOptions(ORIENTATIONS)}
          </select>
        </FormField>
        <FormField label="Inclinaison / pente (°)" htmlFor="lf-inclinaison" error={errors.inclinaison_deg}>
          <Input
            id="lf-inclinaison" type="number" step="any" invalid={!!errors.inclinaison_deg}
            value={v('inclinaison_deg')} onChange={(e) => setField('inclinaison_deg', e.target.value)}
          />
        </FormField>
        <FormField label="Ombrage" htmlFor="lf-ombrage" error={errors.ombrage}>
          <select
            id="lf-ombrage" className={errors.ombrage ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.ombrage ? true : undefined}
            value={v('ombrage')} onChange={(e) => setField('ombrage', e.target.value)}
          >
            {enumOptions(OMBRAGES)}
          </select>
        </FormField>
        <div className="form-group fg-grow">
          <FormField label="Notes ombrage" htmlFor="lf-ombrage-notes" error={errors.ombrage_notes}>
            <Input
              id="lf-ombrage-notes" invalid={!!errors.ombrage_notes}
              value={v('ombrage_notes')} onChange={(e) => setField('ombrage_notes', e.target.value)}
            />
          </FormField>
        </div>
      </div>
      <div className="form-row">
        <FormField label="Structure" htmlFor="lf-structure" error={errors.structure_pref}>
          <select
            id="lf-structure" className={errors.structure_pref ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.structure_pref ? true : undefined}
            value={v('structure_pref')} onChange={(e) => setField('structure_pref', e.target.value)}
          >
            {enumOptions(STRUCTURES)}
          </select>
        </FormField>
        <FormField label="Étages / hauteur" htmlFor="lf-nb-etages" error={errors.nb_etages}>
          <Input
            id="lf-nb-etages" type="number" step="any" invalid={!!errors.nb_etages}
            value={v('nb_etages')} onChange={(e) => setField('nb_etages', e.target.value)}
          />
        </FormField>
      </div>
    </>
  )
}
