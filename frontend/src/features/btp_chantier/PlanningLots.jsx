import { useCallback, useEffect, useState } from 'react'
import { Layers } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'

/* ============================================================================
   NTCON14 — Planning TCE multi-lots avec jalons contractuels.
   ----------------------------------------------------------------------------
   Le Gantt est GROUPÉ PAR LOT, chaque lot portant son code couleur (celui
   choisi, sinon le repli STABLE de la palette serveur — jamais une couleur
   inventée côté client). Toutes les données (dates, avancement, retard,
   couleur) viennent de `chantiers/<id>/planning-lots/` : aucun calcul métier
   n'est refait ici.

   PÉRIMÈTRE (contrat PLAN_VERTICALS) : NTCON14 citait
   `features/gestion_projet/PlanningPage.jsx`, qui appartient à une AUTRE app.
   L'écran groupé par lot vit donc dans le vertical BTP (cette app), branché
   par `module.config.jsx` — aucune écriture hors périmètre.
   ========================================================================== */

const STATUT_LABEL = {
  planifie: 'Planifié', en_cours: 'En cours', termine: 'Terminé',
}
const STATUT_TONE = {
  planifie: 'neutral', en_cours: 'info', termine: 'success',
}

const LOTS_TYPES = [
  'Gros-œuvre', 'Électricité', 'Plomberie', 'CVC', 'Finitions',
]

/* Borne temporelle du Gantt : min des débuts / max des fins sur tout ce qui
   porte une date (lots + tâches). Renvoie null si rien n'est daté. */
export function bornesPlanning(blocs) {
  const dates = []
  for (const bloc of blocs || []) {
    for (const d of [bloc.date_debut_prevue, bloc.date_fin_prevue]) {
      if (d) dates.push(d)
    }
    for (const t of bloc.taches || []) {
      for (const d of [t.date_debut_prevue, t.date_fin_prevue]) {
        if (d) dates.push(d)
      }
    }
  }
  if (!dates.length) return null
  dates.sort()
  return { debut: dates[0], fin: dates[dates.length - 1] }
}

/* Position/largeur d'une barre en % de la fenêtre du planning. */
export function barre(bornes, debut, fin) {
  if (!bornes || !debut || !fin) return null
  const t0 = Date.parse(bornes.debut)
  const t1 = Date.parse(bornes.fin)
  const span = Math.max(t1 - t0, 1)
  const a = Math.max(Date.parse(debut) - t0, 0)
  const b = Math.min(Date.parse(fin) - t0, span)
  return {
    left: `${(a / span) * 100}%`,
    width: `${Math.max(((b - a) / span) * 100, 2)}%`,
  }
}

export default function PlanningLots() {
  const [chantierId, setChantierId] = useState('')
  const [blocs, setBlocs] = useState([])
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ nom: '', date_debut_prevue: '', date_fin_prevue: '' })
  const [saving, setSaving] = useState(false)

  const charger = useCallback(() => {
    if (!chantierId) { setBlocs([]); return undefined }
    let cancelled = false
    setLoading(true)
    btpChantierApi.planningLots(chantierId)
      .then((res) => { if (!cancelled) setBlocs(res?.data || []) })
      .catch(() => { if (!cancelled) setBlocs([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [chantierId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement
  useEffect(() => charger(), [charger])

  const creerLot = async (event) => {
    event.preventDefault()
    if (!chantierId || !form.nom) return
    setSaving(true)
    try {
      await btpChantierApi.lots.create({
        chantier: chantierId,
        nom: form.nom,
        ordre: blocs.length + 1,
        date_debut_prevue: form.date_debut_prevue || null,
        date_fin_prevue: form.date_fin_prevue || null,
      })
      toast.success('Lot créé.')
      setForm({ nom: '', date_debut_prevue: '', date_fin_prevue: '' })
      charger()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de créer ce lot.'))
    } finally {
      setSaving(false)
    }
  }

  const bornes = bornesPlanning(blocs)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Layers size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          Planning tous corps d&apos;état (par lot)
        </h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} label="Chantier du planning" />
      </div>

      <form
        onSubmit={creerLot}
        style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}
      >
        <input
          list="btp-lots-types"
          placeholder="Nom du lot"
          value={form.nom}
          onChange={(e) => setForm({ ...form, nom: e.target.value })}
          aria-label="Nom du lot"
          required
        />
        <datalist id="btp-lots-types">
          {LOTS_TYPES.map((l) => <option key={l} value={l} />)}
        </datalist>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Début prévu
          <input
            type="date"
            value={form.date_debut_prevue}
            onChange={(e) => setForm({ ...form, date_debut_prevue: e.target.value })}
            aria-label="Début prévu du lot"
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Fin prévue
          <input
            type="date"
            value={form.date_fin_prevue}
            onChange={(e) => setForm({ ...form, date_fin_prevue: e.target.value })}
            aria-label="Fin prévue du lot"
          />
        </label>
        <Button type="submit" disabled={saving || !chantierId}>
          {saving ? 'Création…' : 'Ajouter le lot'}
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && !chantierId && <p>Choisissez un chantier pour afficher son planning.</p>}
      {!loading && chantierId && blocs.length === 0 && (
        <p>Aucun lot sur ce chantier.</p>
      )}

      {!loading && blocs.map((bloc) => (
        <section
          key={bloc.id}
          aria-label={`Lot ${bloc.nom}`}
          style={{
            borderLeft: `4px solid ${bloc.couleur}`,
            padding: '8px 12px', marginBottom: 12,
            background: 'rgba(148,163,184,0.08)', borderRadius: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <strong>{bloc.nom}</strong>
            <Badge tone={STATUT_TONE[bloc.statut] || 'neutral'}>
              {STATUT_LABEL[bloc.statut] || bloc.statut}
            </Badge>
            {bloc.jalon_contractuel && <Badge tone="warning">Jalon contractuel</Badge>}
            {bloc.en_retard && <Badge tone="danger">En retard</Badge>}
            <span style={{ color: '#64748b' }}>
              {bloc.interne ? 'Interne' : (bloc.sous_traitant_nom || 'Sous-traité')}
            </span>
            <span style={{ marginLeft: 'auto' }}>{bloc.avancement_pct}%</span>
          </div>

          <div
            style={{ position: 'relative', height: 14, marginTop: 6, background: 'rgba(148,163,184,0.2)', borderRadius: 7 }}
          >
            {(() => {
              const pos = barre(bornes, bloc.date_debut_prevue, bloc.date_fin_prevue)
              return pos ? (
                <div
                  data-testid={`btp-lot-barre-${bloc.id}`}
                  style={{
                    position: 'absolute', top: 0, height: 14, borderRadius: 7,
                    background: bloc.couleur, left: pos.left, width: pos.width,
                  }}
                />
              ) : null
            })()}
          </div>

          {(bloc.taches || []).length > 0 && (
            <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
              {bloc.taches.map((t) => (
                <li key={t.id}>
                  {t.libelle}
                  {' — '}
                  {t.avancement_pct}%
                  {t.date_fin_prevue ? ` (fin ${t.date_fin_prevue})` : ''}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
