import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, GripVertical } from 'lucide-react'
import { Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'

/* ============================================================================
   NTSAN4 — Agenda multi-praticiens (type Doctolib) : vue jour, colonnes =
   praticiens, chaque rendez-vous glissable (drag natif HTML5) vers la colonne
   d'un autre praticien pour le replanifier. Le serveur reste la seule source
   de vérité de la non-double-réservation (NTSAN2/NTSAN4) : un dépôt refusé
   (409/400) restaure l'affichage et montre le message serveur.
   ========================================================================== */

function toDateInputValue(date) {
  return date.toISOString().slice(0, 10)
}

function formatHeure(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export default function SanteAgenda() {
  const [date, setDate] = useState(() => toDateInputValue(new Date()))
  const [praticiens, setPraticiens] = useState([])
  const [rdvs, setRdvs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [dragId, setDragId] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      santeApi.praticiens.list({ actif: true }),
      santeApi.rendezvous.list({ date_debut: date, date_fin: date }),
    ])
      .then(([pRes, rRes]) => {
        const pRows = pRes.data?.results ?? pRes.data ?? []
        const rRows = rRes.data?.results ?? rRes.data ?? []
        setPraticiens(pRows)
        setRdvs(rRows)
      })
      .catch(() => setError("Impossible de charger l'agenda."))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [date])

  const parCol = useMemo(() => {
    const map = new Map()
    for (const p of praticiens) map.set(p.id, [])
    for (const rdv of rdvs) {
      if (!map.has(rdv.praticien)) map.set(rdv.praticien, [])
      map.get(rdv.praticien).push(rdv)
    }
    for (const list of map.values()) {
      list.sort((a, b) => a.date_heure_debut.localeCompare(b.date_heure_debut))
    }
    return map
  }, [praticiens, rdvs])

  const replanifier = async (rdvId, nouveauPraticienId) => {
    try {
      await santeApi.rendezvous.update(rdvId, { praticien: nouveauPraticienId })
      toast.success('Rendez-vous replanifié.')
      load()
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(detail || 'Créneau indisponible pour ce praticien.')
    }
  }

  return (
    <div className="sante-agenda">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <CalendarDays size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Agenda</h1>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          aria-label="Date de l'agenda"
        />
        <Button onClick={load}>Actualiser</Button>
      </div>

      {loading && <p>Chargement…</p>}
      {error && <p role="alert">{error}</p>}

      {!loading && !error && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${Math.max(praticiens.length, 1)}, minmax(180px, 1fr))`,
            gap: 12,
          }}
        >
          {praticiens.map((praticien) => (
            <div
              key={praticien.id}
              data-testid={`agenda-colonne-${praticien.id}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                if (dragId != null) replanifier(dragId, praticien.id)
                setDragId(null)
              }}
              style={{
                border: '1px solid var(--border, #e5e7eb)',
                borderRadius: 8, padding: 8, minHeight: 240,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{praticien.nom}</div>
              {(parCol.get(praticien.id) || []).map((rdv) => (
                <div
                  key={rdv.id}
                  draggable
                  onDragStart={() => setDragId(rdv.id)}
                  data-testid={`rdv-${rdv.id}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    border: '1px solid var(--border, #e5e7eb)',
                    borderRadius: 6, padding: 6, marginBottom: 6,
                    cursor: 'grab', fontSize: 13,
                  }}
                >
                  <GripVertical size={14} strokeWidth={1.75} aria-hidden="true" />
                  <span>{formatHeure(rdv.date_heure_debut)}</span>
                  <span>{rdv.patient_nom || rdv.patient}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
