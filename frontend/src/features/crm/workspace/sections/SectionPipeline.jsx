import { useState } from 'react'
import { Button, FormField, Input } from '../../../../ui'
import AssigneePicker from '../../../../components/AssigneePicker'
import crmApi from '../../../../api/crmApi'
import { toastPromise } from '../../../../ui/confirm'
import useCanaux from '../../useCanaux'
import { TYPE_INSTALLATION_LABELS, PRIORITE_LABELS } from '../../stages'
import { getField, isSuggested } from '../draftCore'
import CadenceFrise from './CadenceFrise'

// Les trois cadences nommées du gabarit (MRY4) — jamais un libellé inventé.
const CADENCE_CHOICES = [
  { value: 'contact', label: 'Contact' },
  { value: 'apres_devis', label: 'Après devis' },
  { value: 'reveil', label: 'Réveil' },
]

// MRY15 — remplace l'ancien « Initialiser le plan de relance » (fondation
// relance du 24/08/2026, revue Fable finale) : le moteur démarre maintenant
// SEUL à l'arrivée d'un lead vivant (MRY6) — ce contrôle sert à RELANCER une
// cadence manuellement (choix contact/après devis/réveil, appel IDEMPOTENT
// par cadence, `apps/crm/views.py initialiser_relance`) ou à L'ARRÊTER
// (motif obligatoire, `arreter_relance` — MRY9). `onChanged` fait recharger
// la frise juste en dessous (CadenceFrise) sans dupliquer sa logique réseau.
function RelanceCadenceControls({ leadId, onChanged }) {
  const [cadence, setCadence] = useState('contact')
  const [busy, setBusy] = useState(false)
  const [arretOpen, setArretOpen] = useState(false)
  const [motif, setMotif] = useState('')

  if (leadId == null) return null

  const relancer = async () => {
    setBusy(true)
    try {
      await toastPromise(crmApi.initialiserRelance(leadId, { cadence }), {
        loading: 'Relance de la cadence…',
        success: 'Cadence relancée.',
        error: 'Relance de la cadence impossible.',
      })
      onChanged?.()
    } catch {
      // toastPromise a déjà affiché l'erreur — rien de plus à faire ici.
    } finally {
      setBusy(false)
    }
  }

  const arreter = async () => {
    const m = motif.trim()
    if (!m) return
    setBusy(true)
    try {
      await toastPromise(crmApi.arreterCadence(leadId, { motif: m }), {
        loading: 'Arrêt de la cadence…',
        success: 'Cadence arrêtée.',
        error: 'Arrêt de la cadence impossible.',
      })
      setArretOpen(false)
      setMotif('')
      onChanged?.()
    } catch {
      // toastPromise a déjà affiché l'erreur — rien de plus à faire ici.
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-1.5 flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <select
          className="form-select" aria-label="Cadence à relancer" value={cadence}
          onChange={(e) => setCadence(e.target.value)} disabled={busy}
        >
          {CADENCE_CHOICES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <Button
          type="button" size="sm" variant="outline" disabled={busy}
          data-testid="lf-relance-cadence" onClick={relancer}
        >
          Relancer la cadence
        </Button>
        <Button
          type="button" size="sm" variant="outline" disabled={busy}
          data-testid="lf-arreter-cadence" onClick={() => setArretOpen((o) => !o)}
        >
          Arrêter la cadence
        </Button>
      </div>
      {arretOpen && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Input
            placeholder="Motif d'arrêt (obligatoire)" value={motif}
            onChange={(e) => setMotif(e.target.value)}
            data-testid="lf-arreter-cadence-motif"
          />
          <Button
            type="button" size="sm" variant="outline" disabled={busy}
            onClick={() => { setArretOpen(false); setMotif('') }}
          >
            Annuler
          </Button>
          <Button type="button" size="sm" disabled={busy || !motif.trim()} onClick={arreter}>
            Confirmer
          </Button>
        </div>
      )}
    </div>
  )
}

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
  // F4 — `relanceVersion` (LeadWorkspace, bumpé par les raccourcis « ⋯ » du
  // rail identité — hors de cette section) est COMBINÉ au compteur local
  // `friseReload` ci-dessous (propres boutons Relancer/Arrêter de CETTE
  // section) : les deux sources de rechargement de la frise coexistent sans
  // jamais s'écraser l'une l'autre.
  const { users = [], tagOptions = [], motifOptions = [], relanceVersion = 0 } = refData
  const { labels: canalLabels } = useCanaux()
  const perdu = !!getField(state, 'perdu')
  const neplusContacter = !!getField(state, 'ne_plus_contacter')
  const ownerSuggested = isSuggested(state, 'owner')
  // MRY15 — bumped après « Relancer »/« Arrêter la cadence » pour forcer
  // CadenceFrise à recharger, sans dupliquer sa logique réseau ici.
  const [friseReload, setFriseReload] = useState(0)

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
        <div className="form-group">
          <FormField label="Relance le" htmlFor="lf-relance-date">
            <Input id="lf-relance-date" type="date" value={v('relance_date')} onChange={(e) => setField('relance_date', e.target.value)} />
          </FormField>
          {state.mode === 'edit' && (
            <>
              <RelanceCadenceControls
                leadId={state.leadId}
                onChanged={() => setFriseReload((n) => n + 1)}
              />
              <div className="mt-1.5">
                <CadenceFrise leadId={state.leadId} reloadToken={friseReload + relanceVersion} />
              </div>
            </>
          )}
        </div>
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
        {/* MRY9/MRY15 — distinct de `perdu` : une demande explicite de la
            personne, jamais une conséquence automatique d'un statut. Bloque
            tout futur démarrage/relance de cadence (garde MRY6/MRY9). */}
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input
              type="checkbox" checked={neplusContacter}
              onChange={(e) => setField('ne_plus_contacter', e.target.checked)}
            />
            <span>Ne plus contacter</span>
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
