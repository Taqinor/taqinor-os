import { useMemo, useState } from 'react'
import { AlertTriangle, MapPin, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import gedApi from '../../api/gedApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT62 — Réserves de chantier (punch-list géo-localisée sur plan, NTCON1/2).
   `apps/btp_chantier` n'avait AUCUN fichier client : ses 7 ressources
   étaient toutes invisibles. Done= exige une CARTE avec pastilles cliquables
   colorées par gravité — pas une liste plate : le plan (image d'un document
   GED) est affiché en fond, chaque réserve posée dessus est une pastille
   colorée cliquable ; une liste compacte reste en repli pour les réserves
   sans plan chargé (accessibilité + réserves antérieures à ce plan).
   ========================================================================== */

const GRAVITE_LABEL = { mineure: 'Mineure', majeure: 'Majeure', bloquante: 'Bloquante' }
const GRAVITE_TONE = { mineure: 'info', majeure: 'warning', bloquante: 'danger' }
const GRAVITE_COULEUR = { mineure: '#3b82f6', majeure: '#f59e0b', bloquante: '#ef4444' }
const STATUT_LABEL = { ouverte: 'Ouverte', en_cours: 'En cours', levee: 'Levée', contestee: 'Contestée' }
const STATUT_TONE = { ouverte: 'warning', en_cours: 'info', levee: 'success', contestee: 'danger' }

export default function ReservesChantier() {
  const [chantierId, setChantierId] = useState('')
  const [lot, setLot] = useState('')
  const [statut, setStatut] = useState('')
  const [gravite, setGravite] = useState('')

  const params = useMemo(() => ({
    chantier: chantierId || undefined,
    lot: lot || undefined,
    statut: statut || undefined,
    gravite: gravite || undefined,
  }), [chantierId, lot, statut, gravite])

  const { data: reserves, loading, reload } = useBtpChantierResource(
    btpChantierApi.reserves.list, params, [chantierId, lot, statut, gravite],
  )

  // ── Plan (image de fond, document GED) ──────────────────────────────────
  const [planInput, setPlanInput] = useState('')
  const [planDocId, setPlanDocId] = useState('')
  const [planUrl, setPlanUrl] = useState('')
  const [planLoading, setPlanLoading] = useState(false)

  const chargerPlan = async () => {
    if (!planInput) return
    setPlanLoading(true)
    try {
      const res = await gedApi.getVersions({ document: planInput })
      const versions = Array.isArray(res?.data) ? res.data : res?.data?.results || []
      const derniere = [...versions].sort((a, b) => (b.version || 0) - (a.version || 0))[0]
      if (!derniere) {
        toast.error('Aucune version trouvée pour ce document GED.')
        setPlanDocId('')
        setPlanUrl('')
        return
      }
      setPlanDocId(planInput)
      setPlanUrl(gedApi.apercuVersionUrl(derniere.id))
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de charger ce plan.'))
      setPlanDocId('')
      setPlanUrl('')
    } finally {
      setPlanLoading(false)
    }
  }

  // ── Placement d'une nouvelle réserve (clic sur le plan) ─────────────────
  const [placement, setPlacement] = useState(false)
  const [nouveauPoint, setNouveauPoint] = useState(null)
  const [form, setForm] = useState({ lot: '', gravite: 'mineure', description: '' })
  const [saving, setSaving] = useState(false)

  const onPlanClick = (event) => {
    if (!placement || !planDocId) return
    const rect = event.currentTarget.getBoundingClientRect()
    const largeur = rect.width || 1
    const hauteur = rect.height || 1
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / largeur))
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / hauteur))
    setNouveauPoint({ x, y })
  }

  const creerReserve = async (event) => {
    event.preventDefault()
    if (!chantierId || !nouveauPoint || !form.description) return
    setSaving(true)
    try {
      await btpChantierApi.reserves.create({
        chantier: chantierId,
        lot: form.lot,
        gravite: form.gravite,
        description: form.description,
        localisation_plan: {
          document_ged_id: Number(planDocId),
          x: nouveauPoint.x,
          y: nouveauPoint.y,
        },
      })
      toast.success('Réserve posée.')
      setNouveauPoint(null)
      setForm({ lot: '', gravite: 'mineure', description: '' })
      setPlacement(false)
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de créer la réserve.'))
    } finally {
      setSaving(false)
    }
  }

  // ── Réserve sélectionnée (détails + actions serveur) ────────────────────
  const [selectedId, setSelectedId] = useState(null)
  const selected = reserves.find((r) => r.id === selectedId) || null
  const [signataireNom, setSignataireNom] = useState('')
  const [motifContestation, setMotifContestation] = useState('')
  const [acting, setActing] = useState(false)

  const lever = async () => {
    if (!selected || !signataireNom) return
    setActing(true)
    try {
      await btpChantierApi.reserves.lever(selected.id, signataireNom)
      toast.success('Réserve levée.')
      setSignataireNom('')
      reload()
    } catch (err) {
      // Le serveur refuse sans photo « après » ou sans signataire — message
      // exact renvoyé par l'API, jamais un texte générique.
      toast.error(frenchError(err, 'Impossible de lever la réserve.'))
    } finally {
      setActing(false)
    }
  }

  const contester = async () => {
    if (!selected || !motifContestation) return
    setActing(true)
    try {
      await btpChantierApi.reserves.contester(selected.id, motifContestation)
      toast.success('Réserve contestée.')
      setMotifContestation('')
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de contester la réserve.'))
    } finally {
      setActing(false)
    }
  }

  const reservesSurPlan = reserves.filter(
    (r) => planDocId && Number(r.localisation_plan?.document_ged_id) === Number(planDocId),
  )
  const reservesHorsPlan = reserves.filter(
    (r) => !planDocId || Number(r.localisation_plan?.document_ged_id) !== Number(planDocId),
  )

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <MapPin size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Réserves de chantier</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} />
        <input
          placeholder="Lot"
          value={lot}
          onChange={(e) => setLot(e.target.value)}
          aria-label="Filtrer par lot"
        />
        <select aria-label="Filtrer par statut" value={statut} onChange={(e) => setStatut(e.target.value)}>
          <option value="">Tous statuts</option>
          {Object.entries(STATUT_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select aria-label="Filtrer par gravité" value={gravite} onChange={(e) => setGravite(e.target.value)}>
          <option value="">Toutes gravités</option>
          {Object.entries(GRAVITE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          placeholder="ID du document GED (plan)"
          value={planInput}
          onChange={(e) => setPlanInput(e.target.value)}
          aria-label="ID du document GED (plan)"
        />
        <Button type="button" variant="outline" onClick={chargerPlan} disabled={planLoading}>
          {planLoading ? 'Chargement…' : 'Charger le plan'}
        </Button>
        {planDocId && (
          <Button
            type="button"
            variant={placement ? 'default' : 'outline'}
            onClick={() => setPlacement((p) => !p)}
          >
            <Plus size={16} strokeWidth={1.75} aria-hidden="true" />
            {placement ? 'Cliquez sur le plan…' : 'Ajouter une réserve'}
          </Button>
        )}
      </div>

      {planDocId ? (
        <div
          onClick={onPlanClick}
          data-testid="plan-chantier"
          style={{
            position: 'relative', border: '1px solid #e2e8f0', borderRadius: 8,
            overflow: 'hidden', marginBottom: 16, minHeight: 240,
            cursor: placement ? 'crosshair' : 'default', background: '#f8fafc',
          }}
        >
          {planUrl && (
            <img src={planUrl} alt="Plan du chantier" style={{ width: '100%', display: 'block' }} />
          )}
          {reservesSurPlan.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={(e) => { e.stopPropagation(); setSelectedId(r.id) }}
              aria-label={`Réserve #${r.id} — ${GRAVITE_LABEL[r.gravite] || r.gravite}`}
              title={r.description}
              style={{
                position: 'absolute',
                left: `${(r.localisation_plan?.x ?? 0) * 100}%`,
                top: `${(r.localisation_plan?.y ?? 0) * 100}%`,
                transform: 'translate(-50%, -50%)',
                width: 16, height: 16, borderRadius: '50%', padding: 0,
                background: GRAVITE_COULEUR[r.gravite] || '#64748b',
                border: selectedId === r.id ? '2px solid #0f172a' : '2px solid #fff',
                boxShadow: '0 1px 3px rgba(0,0,0,.4)', cursor: 'pointer',
              }}
            />
          ))}
          {nouveauPoint && (
            <span
              aria-hidden="true"
              style={{
                position: 'absolute',
                left: `${nouveauPoint.x * 100}%`,
                top: `${nouveauPoint.y * 100}%`,
                transform: 'translate(-50%, -50%)',
                width: 16, height: 16, borderRadius: '50%',
                border: '2px dashed #0f172a',
              }}
            />
          )}
        </div>
      ) : (
        <p style={{ color: '#64748b', marginBottom: 16 }}>
          Chargez un plan (ID du document GED) pour poser des réserves dessus.
        </p>
      )}

      {nouveauPoint && (
        <form
          onSubmit={creerReserve}
          style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}
        >
          <span>Nouvelle réserve — point choisi</span>
          <input
            placeholder="Lot"
            value={form.lot}
            onChange={(e) => setForm({ ...form, lot: e.target.value })}
            aria-label="Lot de la réserve"
          />
          <select
            value={form.gravite}
            onChange={(e) => setForm({ ...form, gravite: e.target.value })}
            aria-label="Gravité de la réserve"
          >
            {Object.entries(GRAVITE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            aria-label="Description de la réserve"
            required
          />
          <Button type="submit" disabled={saving || !chantierId}>
            {saving ? 'Enregistrement…' : 'Poser la réserve'}
          </Button>
          <Button type="button" variant="ghost" onClick={() => setNouveauPoint(null)}>Annuler</Button>
        </form>
      )}

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr><th>Lot</th><th>Description</th><th>Gravité</th><th>Statut</th><th /></tr>
          </thead>
          <tbody>
            {reservesHorsPlan.map((r) => (
              <tr key={r.id}>
                <td>{r.lot || '—'}</td>
                <td>{r.description}</td>
                <td><Badge tone={GRAVITE_TONE[r.gravite] || 'neutral'}>{GRAVITE_LABEL[r.gravite] || r.gravite}</Badge></td>
                <td><Badge tone={STATUT_TONE[r.statut] || 'neutral'}>{STATUT_LABEL[r.statut] || r.statut}</Badge></td>
                <td><Button variant="ghost" onClick={() => setSelectedId(r.id)}>Détails</Button></td>
              </tr>
            ))}
            {reserves.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>Aucune réserve</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            Réserve #{selected.id}{' '}
            <Badge tone={GRAVITE_TONE[selected.gravite] || 'neutral'}>
              {GRAVITE_LABEL[selected.gravite] || selected.gravite}
            </Badge>{' '}
            <Badge tone={STATUT_TONE[selected.statut] || 'neutral'}>
              {STATUT_LABEL[selected.statut] || selected.statut}
            </Badge>
          </h2>
          <p>{selected.description}</p>
          {selected.date_limite && <p>Date limite : {selected.date_limite}</p>}
          {(selected.statut === 'ouverte' || selected.statut === 'en_cours') && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                placeholder="Nom du signataire"
                value={signataireNom}
                onChange={(e) => setSignataireNom(e.target.value)}
                aria-label="Nom du signataire (levée)"
              />
              <Button type="button" onClick={lever} disabled={acting || !signataireNom}>Lever</Button>
            </div>
          )}
          {selected.statut === 'levee' && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                placeholder="Motif de contestation"
                value={motifContestation}
                onChange={(e) => setMotifContestation(e.target.value)}
                aria-label="Motif de contestation"
              />
              <Button type="button" variant="destructive" onClick={contester} disabled={acting || !motifContestation}>
                Contester
              </Button>
            </div>
          )}
          {selected.motif_contestation && (
            <p style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={14} strokeWidth={1.75} aria-hidden="true" /> {selected.motif_contestation}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
