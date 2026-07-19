import { FormField, Input } from '../../../../ui'
import AssigneePicker from '../../../../components/AssigneePicker'
import useCanaux from '../../useCanaux'
import { TYPE_INSTALLATION_LABELS, PRIORITE_LABELS } from '../../stages'
import { getField, isSuggested } from '../draftCore'

// Langue préférée du contact — pré-sélectionne la langue du message WhatsApp.
const LANGUES_PREFEREES = { fr: 'Français', darija: 'Darija' }

const enumOptions = (labels) => [
  <option key="" value="">—</option>,
  ...Object.entries(labels).map(([k, l]) => <option key={k} value={k}>{l}</option>),
]

// LW11 — Suivi commercial SANS le select d'étape (remplacé par StageControl
// LW16, rail identité). Port 1:1 des autres champs pipeline + verrous perdu/motif.
export default function SectionPipeline({ state, setField, errors = {}, refData = {} }) {
  const v = (k) => getField(state, k) ?? ''
  const { users = [], tagOptions = [], motifOptions = [] } = refData
  const { labels: canalLabels } = useCanaux()
  const perdu = !!getField(state, 'perdu')
  const ownerSuggested = isSuggested(state, 'owner')

  return (
    <>
      <div className="form-row">
        <FormField label="Type d'installation" htmlFor="lf-type-installation">
          <select
            id="lf-type-installation" className="form-select" value={v('type_installation')}
            onChange={(e) => setField('type_installation', e.target.value)}
          >
            {enumOptions(TYPE_INSTALLATION_LABELS)}
          </select>
        </FormField>
        {/* VX249(b) — owner : champ « suggéré » à la création tant qu'il n'est
            pas touché. AssigneePicker n'expose pas de className : le contour va
            sur le wrapper (label stable pour l'e2e). */}
        <div className="form-group">
          <label className="form-label">Responsable</label>
          <div className={ownerSuggested ? 'vx-suggested-field inline-block rounded-full' : undefined}>
            <AssigneePicker
              users={users}
              value={v('owner')}
              onChange={(id) => setField('owner', id ?? '')}
            />
          </div>
          {ownerSuggested && (
            <p className="mt-1 text-xs text-muted-foreground">Suggéré — modifiable</p>
          )}
        </div>
        <FormField label="Relance le" htmlFor="lf-relance-date">
          <Input id="lf-relance-date" type="date" value={v('relance_date')} onChange={(e) => setField('relance_date', e.target.value)} />
        </FormField>
      </div>
      <div className="form-row">
        {/* XSAL7 — pipeline pondéré pré-devis. */}
        <FormField label="Montant estimé (MAD)" htmlFor="lf-montant-estime">
          <Input id="lf-montant-estime" type="number" step="any" value={v('montant_estime')} onChange={(e) => setField('montant_estime', e.target.value)} />
        </FormField>
        <FormField label="Clôture prévue le" htmlFor="lf-date-cloture">
          <Input id="lf-date-cloture" type="date" value={v('date_cloture_prevue')} onChange={(e) => setField('date_cloture_prevue', e.target.value)} />
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Priorité" htmlFor="lf-priorite">
          <select id="lf-priorite" className="form-select" value={v('priorite')} onChange={(e) => setField('priorite', e.target.value)}>
            {enumOptions(PRIORITE_LABELS)}
          </select>
        </FormField>
        <FormField label="Canal" htmlFor="lf-canal">
          <select id="lf-canal" className="form-select" value={v('canal')} onChange={(e) => setField('canal', e.target.value)}>
            {enumOptions(canalLabels)}
          </select>
        </FormField>
        <FormField label="Langue préférée" htmlFor="lf-langue-preferee">
          <select id="lf-langue-preferee" className="form-select" value={v('langue_preferee')} onChange={(e) => setField('langue_preferee', e.target.value)}>
            {enumOptions(LANGUES_PREFEREES)}
          </select>
        </FormField>
        <div className="form-group fg-grow">
          <FormField label="Tags (séparés par des virgules)" htmlFor="lf-tags">
            <Input
              id="lf-tags" value={v('tags')} onChange={(e) => setField('tags', e.target.value)}
              placeholder="ex: Régularisation 82-21, VIP" list="ld-tags"
            />
          </FormField>
          <datalist id="ld-tags">
            {tagOptions.map((t) => <option key={t.id} value={t.nom} />)}
          </datalist>
        </div>
      </div>
      {/* QW3 — préférence de contact explicite (posée par le site/webhook),
          lecture seule ici. */}
      {getField(state, 'contact_preference') === 'phone_ok' && (
        <div className="form-row">
          <span
            className="kb-badge-rappel rounded-full bg-info/15 px-1.5 py-0.5 text-info"
            title="Le client a demandé à être rappelé par téléphone"
          >
            ☎ Rappel demandé
          </span>
        </div>
      )}
      <div className="form-row">
        {/* « Perdu ? » — drapeau indépendant de l'étape (perdu à n'importe
            quelle étape). */}
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input type="checkbox" checked={perdu} onChange={(e) => setField('perdu', e.target.checked)} />
            <span>Perdu ?</span>
          </label>
        </div>
        {perdu && (
          <div className="form-group fg-grow">
            <FormField
              label="Motif de perte" required htmlFor="lf-motif-perte"
              error={errors.motif_perte} errorKind="required"
            >
              <Input
                id="lf-motif-perte" invalid={!!errors.motif_perte}
                value={v('motif_perte')} onChange={(e) => setField('motif_perte', e.target.value)}
                list="ld-motifs"
              />
              <datalist id="ld-motifs">
                {motifOptions.map((m) => <option key={m.id} value={m.nom} />)}
              </datalist>
            </FormField>
          </div>
        )}
      </div>
    </>
  )
}
