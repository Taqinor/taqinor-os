/* Atelier Doublons (FEATURE 1) — scanne TOUS les leads de la société, les
   regroupe en clusters (téléphone / email / nom normalisé), et permet de
   choisir le survivant puis « Fusionner le groupe » SANS perte (le moteur
   serveur réutilise merge_leads : devis/activités/chantiers déplacés, absorbés
   archivés et réversibles). Modal autonome ouvert depuis le pipeline. */
import { useEffect, useState } from 'react'
import { CheckCircle2, GitMerge, Users } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import { STAGE_LABELS } from '../../../features/crm/stages'
import {
  Button, Spinner, Checkbox, RadioGroup, RadioGroupItem, Badge, EmptyState,
} from '../../../ui'

// Libellé FR de la clé de rapprochement (POURQUOI le groupe existe).
const MATCH_KEY_LABELS = {
  telephone: 'même téléphone',
  email: 'même email',
  nom: 'même nom',
}

function ClusterCard({ cluster, onMerged }) {
  // Survivant initial : la suggestion serveur, sauf si elle est archivée alors
  // qu'un membre actif existe (on ne garde jamais un archivé face à un actif).
  const initialSurvivor = (() => {
    const sug = cluster.members.find(m => m.id === cluster.suggested_survivor_id)
    const active = cluster.members.filter(m => !m.is_archived)
    if (active.length && sug?.is_archived) return active[0].id
    return cluster.suggested_survivor_id
  })()
  const [survivor, setSurvivor] = useState(initialSurvivor)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const otherMembers = cluster.members.filter(m => m.id !== survivor)
  const others = otherMembers.map(m => m.id)
  // Au moins un membre actif (non archivé) dans le groupe → on interdit de
  // choisir un membre archivé comme survivant (absorber des actifs dans un
  // archivé serait une régression). Sinon (tous archivés) : choix libre.
  const hasActive = cluster.members.some(m => !m.is_archived)
  // Aperçu de fusion calculé pour le survivant CHOISI (devis/activités migrés
  // depuis les autres). Les champs comblés viennent du serveur (indicatif).
  const devisMigres = otherMembers.reduce((s, m) => s + (m.nb_devis ?? 0), 0)
  const activitesMigrees = otherMembers.reduce(
    (s, m) => s + (m.nb_activites ?? 0), 0)
  const champsCombles = cluster.merge_preview?.champs_combles ?? []
  const matchKeys = cluster.match_keys ?? []

  const doMerge = async () => {
    if (!others.length) return
    const survName = cluster.members.find(m => m.id === survivor)
    if (!window.confirm(
      `Fusionner ${others.length} doublon(s) dans « ${survName?.nom} `
      + `${survName?.prenom || ''} » ? Les autres fiches seront ARCHIVÉES `
      + `(jamais supprimées) et tout (devis, activités, historique) sera `
      + `rattaché au survivant.`)) return
    setBusy(true)
    setError(null)
    try {
      await crmApi.mergeLeads(survivor, others)
      setDone(true)
      onMerged?.()
    } catch {
      setError('La fusion a échoué — réessayez.')
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="dbl-cluster dbl-cluster-done">
        <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
        Groupe fusionné — {others.length} fiche(s) archivée(s).
      </div>
    )
  }

  return (
    <div className="dbl-cluster">
      {matchKeys.length > 0 && (
        <div className="dbl-match-keys">
          Regroupés par :{' '}
          {matchKeys.map((k, i) => (
            <span key={k}>
              {i > 0 && ', '}
              <Badge tone="neutral">{MATCH_KEY_LABELS[k] ?? k}</Badge>
            </span>
          ))}
        </div>
      )}
      <RadioGroup
        value={String(survivor)}
        onValueChange={(v) => setSurvivor(Number(v))}
        className="dbl-cluster-grid"
      >
        {cluster.members.map(m => {
          // Un membre archivé ne peut pas être survivant tant qu'un actif existe.
          const disabledKeep = hasActive && m.is_archived && m.id !== survivor
          return (
          <label
            key={m.id}
            className={`dbl-member${m.id === survivor ? ' dbl-member-keep' : ''}`}
          >
            <div className="dbl-member-head">
              <RadioGroupItem
                value={String(m.id)}
                disabled={disabledKeep}
                title={disabledKeep
                  ? 'Un lead archivé ne peut pas être le survivant tant '
                    + "qu'un lead actif est présent"
                  : undefined}
              />
              <strong>{m.nom} {m.prenom || ''}</strong>
              {m.id === survivor && <Badge tone="primary" className="dbl-keep-tag">à garder</Badge>}
              {m.is_archived && <Badge tone="warning" className="dbl-arch-tag">archivé</Badge>}
            </div>
            <div className="dbl-member-fields">
              {m.societe && <div>🏢 {m.societe}</div>}
              <div>📞 {m.telephone || '—'}</div>
              <div>✉️ {m.email || '—'}</div>
              <div>📍 {m.ville || '—'}</div>
              <div>📊 {STAGE_LABELS[m.stage] ?? m.stage}</div>
              <div>📄 {m.nb_devis} devis · {m.nb_activites ?? 0} activités · {m.completeness} champs</div>
            </div>
          </label>
          )
        })}
      </RadioGroup>
      {others.length > 0 && (
        <div className="dbl-merge-preview" role="status">
          Aperçu : {devisMigres} devis et {activitesMigrees} activité(s)
          seront déplacés vers le survivant ; {others.length} fiche(s)
          archivée(s).
          {champsCombles.length > 0 && (
            <> Champs comblés : {champsCombles.join(', ')}.</>
          )}
        </div>
      )}
      {error && <div className="form-error-box">{error}</div>}
      <div className="dbl-cluster-actions">
        <Button
          type="button"
          size="sm"
          onClick={doMerge}
          loading={busy}
          disabled={busy || !others.length}
        >
          {!busy && <GitMerge />}
          {busy ? 'Fusion…' : `Fusionner le groupe (${cluster.members.length} → 1)`}
        </Button>
      </div>
    </div>
  )
}

export default function DoublonsPanel({ onClose, onAnyMerge }) {
  const [clusters, setClusters] = useState(null)
  const [error, setError] = useState(null)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const reload = () => setReloadKey(k => k + 1)

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClusters(null)
    setError(null)
    crmApi.getDoublons(includeArchived ? { archived: 1 } : {})
      .then(r => { if (!cancelled) setClusters(r.data) })
      .catch(() => { if (!cancelled) setError('Impossible de charger les doublons.') })
    return () => { cancelled = true }
  }, [includeArchived, reloadKey])

  return (
    <div className="dbl-overlay" onClick={onClose}>
      <div className="dbl-panel" onClick={e => e.stopPropagation()}>
        <div className="dbl-header">
          <h3>🔀 Doublons{clusters ? ` (${clusters.length} groupe${clusters.length > 1 ? 's' : ''})` : ''}</h3>
          <label className="dbl-arch-toggle">
            <Checkbox
              checked={includeArchived}
              onCheckedChange={(v) => setIncludeArchived(!!v)}
            />
            Inclure les archivés
          </label>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="dbl-body">
          {error && <div className="form-error-box">{error}</div>}
          {!clusters && !error && (
            <div className="dbl-loading">
              <Spinner /> Analyse des leads…
            </div>
          )}
          {clusters && clusters.length === 0 && (
            <EmptyState
              icon={Users}
              title="Aucun doublon détecté"
              description="Toutes les fiches de la société sont uniques (téléphone, email et nom)."
            />
          )}
          {clusters && clusters.map((c, i) => (
            <ClusterCard
              key={c.members.map(m => m.id).join('-') + i}
              cluster={c}
              onMerged={() => { onAnyMerge?.(); reload() }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
