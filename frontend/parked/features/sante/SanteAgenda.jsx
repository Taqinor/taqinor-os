import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, GripVertical } from 'lucide-react'
import { Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'
import api from '../../api/axios'

/* ============================================================================
   NTSAN4 — Agenda multi-praticiens (type Doctolib) : vue jour, colonnes =
   praticiens, chaque rendez-vous glissable (drag natif HTML5) vers la colonne
   d'un autre praticien pour le replanifier. Le serveur reste la seule source
   de vérité de la non-double-réservation (NTSAN2/NTSAN4) : un dépôt refusé
   (409/400) restaure l'affichage et montre le message serveur.

   PACT115 — la vue `disponibilites` (NTSAN29, `GET /sante/disponibilites/
   ?praticien=&date=`) calculait déjà les créneaux libres d'UN praticien pour
   UN jour, mais aucun écran ne l'appelait : la création d'un rendez-vous se
   faisait à l'aveugle (heure saisie à la main, cf. `ReceptionScreen.jsx`).
   Le panneau « Nouveau rendez-vous » ci-dessous recharge les créneaux DEPUIS
   LE SERVEUR à chaque changement de praticien OU de date — jamais un calcul
   de disponibilité côté client.
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

  // PACT115 — panneau de création : praticien + date recharge les créneaux
  // depuis le serveur (jamais un calcul local).
  const [nouveauPraticien, setNouveauPraticien] = useState('')
  const [nouveauPatient, setNouveauPatient] = useState('')
  const [creneaux, setCreneaux] = useState([])
  const [creneauChoisi, setCreneauChoisi] = useState('')
  const [chargementCreneaux, setChargementCreneaux] = useState(false)
  const [creationEnCours, setCreationEnCours] = useState(false)

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date])

  // PACT115 — changer le praticien OU la date recharge les créneaux DEPUIS
  // LE SERVEUR (`disponibilites/?praticien=&date=`), jamais un calcul local.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset du créneau choisi au changement de praticien/date
    setCreneauChoisi('')
    // eslint-disable-next-line react-hooks/set-state-in-effect -- pas de praticien choisi = pas de créneaux
    if (!nouveauPraticien) { setCreneaux([]); return }
    let active = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicateur de chargement des créneaux
    setChargementCreneaux(true)
    api.get('/sante/disponibilites/', { params: { praticien: nouveauPraticien, date } })
      .then((res) => { if (active) setCreneaux(res.data?.creneaux ?? []) })
      .catch(() => { if (active) { setCreneaux([]); toast.error('Impossible de charger les créneaux disponibles.') } })
      .finally(() => { if (active) setChargementCreneaux(false) })
    return () => { active = false }
  }, [nouveauPraticien, date])

  const creerRendezVous = async (e) => {
    e.preventDefault()
    if (!nouveauPatient || !nouveauPraticien || !creneauChoisi) return
    setCreationEnCours(true)
    try {
      await santeApi.rendezvous.create({
        patient: Number(nouveauPatient),
        praticien: Number(nouveauPraticien),
        date_heure_debut: creneauChoisi,
      })
      toast.success('Rendez-vous planifié.')
      setNouveauPatient('')
      setCreneauChoisi('')
      load()
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(detail || 'Créneau indisponible.')
    } finally {
      setCreationEnCours(false)
    }
  }

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

  // WIR53 — annulation depuis l'agenda (NTSAN37) : délai + pénalité éventuelle
  // sont calculés côté serveur, jamais ici. Annulation déclenchée depuis
  // l'écran interne = à l'initiative de la clinique.
  const annuler = async (rdv) => {
    if (!window.confirm('Annuler ce rendez-vous ?')) return
    try {
      const res = await santeApi.rendezvous.annuler(rdv.id, 'clinique')
      toast[res.data?.penalite_applicable ? 'error' : 'success'](
        res.data?.penalite_applicable
          ? 'Rendez-vous annulé — pénalité applicable (délai dépassé).'
          : 'Rendez-vous annulé.')
      load()
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(detail || "Impossible d'annuler ce rendez-vous.")
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

      <form
        onSubmit={creerRendezVous}
        style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}
      >
        <span style={{ fontSize: 13, fontWeight: 600 }}>Nouveau rendez-vous</span>
        <input
          placeholder="ID patient"
          value={nouveauPatient}
          onChange={(e) => setNouveauPatient(e.target.value)}
          aria-label="Patient (ID)"
        />
        <select
          value={nouveauPraticien}
          onChange={(e) => setNouveauPraticien(e.target.value)}
          aria-label="Praticien du nouveau rendez-vous"
        >
          <option value="">Praticien…</option>
          {praticiens.map((p) => (
            <option key={p.id} value={p.id}>{p.nom}</option>
          ))}
        </select>
        <select
          value={creneauChoisi}
          onChange={(e) => setCreneauChoisi(e.target.value)}
          aria-label="Créneau disponible"
          disabled={!nouveauPraticien || chargementCreneaux}
        >
          <option value="">
            {chargementCreneaux ? 'Chargement des créneaux…' : (creneaux.length === 0 ? 'Aucun créneau' : 'Créneau…')}
          </option>
          {creneaux.map((c) => (
            <option key={c} value={c}>{formatHeure(c)}</option>
          ))}
        </select>
        <Button type="submit" disabled={creationEnCours || !creneauChoisi}>
          Planifier
        </Button>
      </form>

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
                  {rdv.statut !== 'annule' && rdv.statut !== 'termine' && (
                    <Button
                      variant="ghost" size="sm"
                      onClick={() => annuler(rdv)}
                      aria-label="Annuler ce rendez-vous"
                    >
                      Annuler
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
