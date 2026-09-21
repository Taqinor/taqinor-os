import { useEffect, useState } from 'react'
import { Search, UserPlus, CalendarPlus, LogIn } from 'lucide-react'
import { Button, Badge, toast } from '../../ui'
import santeApi from '../../api/santeApi'

/* ============================================================================
   NTSAN18 — Écran accueil « Réception » : recherche patient (nom/CIN/
   téléphone), création rapide de patient, planification du RDV du jour, et
   check-in (« Patient arrivé » → statut ``arrive``, salle d'attente NTSAN5).
   Tout tient sur UN seul écran (recherche + création + planification +
   check-in) : un agent de réception enregistre un nouveau patient et le met
   en salle d'attente sans jamais changer de page.
   ========================================================================== */

function toDateInputValue(date) {
  return date.toISOString().slice(0, 10)
}

function formatHeure(iso) {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

const PATIENT_VIDE = { nom: '', prenom: '', cin: '', telephone: '' }
const RDV_VIDE = { patient: '', praticien: '', heure: '09:00', duree_min: '30' }

export default function ReceptionScreen() {
  const [q, setQ] = useState('')
  const [resultats, setResultats] = useState([])
  const [recherche, setRecherche] = useState(false)
  const [nouveauPatient, setNouveauPatient] = useState(PATIENT_VIDE)
  const [creationEnCours, setCreationEnCours] = useState(false)

  const [praticiens, setPraticiens] = useState([])
  const [rdvsDuJour, setRdvsDuJour] = useState([])
  const [chargementRdv, setChargementRdv] = useState(true)
  const [nouveauRdv, setNouveauRdv] = useState(RDV_VIDE)

  const today = toDateInputValue(new Date())

  const chargerRdvDuJour = () => {
    setChargementRdv(true)
    Promise.all([
      santeApi.praticiens.list({ actif: true }),
      santeApi.rendezvous.list({ date_debut: today, date_fin: today }),
    ])
      .then(([pRes, rRes]) => {
        setPraticiens(pRes.data?.results ?? pRes.data ?? [])
        setRdvsDuJour(rRes.data?.results ?? rRes.data ?? [])
      })
      .catch(() => toast.error("Impossible de charger le planning du jour."))
      .finally(() => setChargementRdv(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    chargerRdvDuJour()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rechercher = async (e) => {
    e.preventDefault()
    if (!q.trim()) return
    setRecherche(true)
    try {
      const res = await santeApi.patients.list({ q })
      setResultats(res.data?.results ?? res.data ?? [])
    } catch {
      toast.error('Recherche impossible.')
    } finally {
      setRecherche(false)
    }
  }

  const creerPatient = async (e) => {
    e.preventDefault()
    if (!nouveauPatient.nom.trim()) return
    setCreationEnCours(true)
    try {
      const res = await santeApi.patients.create(nouveauPatient)
      toast.success('Patient enregistré.')
      setNouveauPatient(PATIENT_VIDE)
      setResultats((prev) => [res.data, ...prev])
      setNouveauRdv((prev) => ({ ...prev, patient: String(res.data.id) }))
    } catch {
      toast.error('Impossible d’enregistrer ce patient.')
    } finally {
      setCreationEnCours(false)
    }
  }

  const planifierRdv = async (e) => {
    e.preventDefault()
    if (!nouveauRdv.patient || !nouveauRdv.praticien) return
    try {
      await santeApi.rendezvous.create({
        patient: Number(nouveauRdv.patient),
        praticien: Number(nouveauRdv.praticien),
        date_heure_debut: `${today}T${nouveauRdv.heure}:00`,
        duree_min: Number(nouveauRdv.duree_min) || 30,
      })
      toast.success('Rendez-vous planifié.')
      setNouveauRdv(RDV_VIDE)
      chargerRdvDuJour()
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(detail || 'Créneau indisponible.')
    }
  }

  const checkin = async (rdv) => {
    try {
      await santeApi.rendezvous.checkin(rdv.id)
      toast.success('Patient en salle d’attente.')
      chargerRdvDuJour()
    } catch {
      toast.error('Check-in impossible.')
    }
  }

  // WIR53 — annulation depuis la réception (NTSAN37) : délai + pénalité
  // éventuelle sont calculés côté serveur, jamais ici.
  const annuler = async (rdv) => {
    if (!window.confirm('Annuler ce rendez-vous ?')) return
    try {
      const res = await santeApi.rendezvous.annuler(rdv.id, 'patient')
      toast[res.data?.penalite_applicable ? 'error' : 'success'](
        res.data?.penalite_applicable
          ? 'Rendez-vous annulé — pénalité applicable (délai dépassé).'
          : 'Rendez-vous annulé.')
      chargerRdvDuJour()
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(detail || "Impossible d'annuler ce rendez-vous.")
    }
  }

  return (
    <div className="sante-reception">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <UserPlus size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Réception</h1>
      </div>

      {/* Recherche patient (nom/CIN/téléphone) */}
      <form onSubmit={rechercher} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          placeholder="Nom, CIN ou téléphone"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Rechercher un patient"
        />
        <Button type="submit" disabled={recherche}>
          <Search size={16} strokeWidth={1.75} aria-hidden="true" /> Rechercher
        </Button>
      </form>

      {resultats.length > 0 && (
        <ul data-testid="reception-resultats" style={{ marginBottom: 16 }}>
          {resultats.map((p) => (
            <li key={p.id}>
              {p.nom} {p.prenom} — {p.telephone || p.cin || 'sans contact'}
            </li>
          ))}
        </ul>
      )}

      {/* Création rapide de patient */}
      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouveau patient</h2>
      <form onSubmit={creerPatient} style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <input
          placeholder="Nom"
          value={nouveauPatient.nom}
          onChange={(e) => setNouveauPatient({ ...nouveauPatient, nom: e.target.value })}
          aria-label="Nom du patient"
        />
        <input
          placeholder="Prénom"
          value={nouveauPatient.prenom}
          onChange={(e) => setNouveauPatient({ ...nouveauPatient, prenom: e.target.value })}
          aria-label="Prénom du patient"
        />
        <input
          placeholder="CIN"
          value={nouveauPatient.cin}
          onChange={(e) => setNouveauPatient({ ...nouveauPatient, cin: e.target.value })}
          aria-label="CIN du patient"
        />
        <input
          placeholder="Téléphone"
          value={nouveauPatient.telephone}
          onChange={(e) => setNouveauPatient({ ...nouveauPatient, telephone: e.target.value })}
          aria-label="Téléphone du patient"
        />
        <Button type="submit" disabled={creationEnCours}>
          <UserPlus size={16} strokeWidth={1.75} aria-hidden="true" /> Enregistrer
        </Button>
      </form>

      {/* Planification RDV du jour */}
      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Planifier un RDV aujourd'hui</h2>
      <form onSubmit={planifierRdv} style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <input
          placeholder="ID patient"
          value={nouveauRdv.patient}
          onChange={(e) => setNouveauRdv({ ...nouveauRdv, patient: e.target.value })}
          aria-label="Patient (ID)"
        />
        <select
          value={nouveauRdv.praticien}
          onChange={(e) => setNouveauRdv({ ...nouveauRdv, praticien: e.target.value })}
          aria-label="Praticien"
        >
          <option value="">Praticien…</option>
          {praticiens.map((p) => (
            <option key={p.id} value={p.id}>{p.nom}</option>
          ))}
        </select>
        <input
          type="time"
          value={nouveauRdv.heure}
          onChange={(e) => setNouveauRdv({ ...nouveauRdv, heure: e.target.value })}
          aria-label="Heure du RDV"
        />
        <Button type="submit">
          <CalendarPlus size={16} strokeWidth={1.75} aria-hidden="true" /> Planifier
        </Button>
      </form>

      {/* RDV du jour + check-in */}
      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Aujourd'hui</h2>
      {chargementRdv && <p>Chargement…</p>}
      {!chargementRdv && (
        <ul data-testid="reception-rdv-du-jour">
          {rdvsDuJour.map((rdv) => (
            <li key={rdv.id} data-testid={`reception-rdv-${rdv.id}`} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>{formatHeure(rdv.date_heure_debut)}</span>
              <span>{rdv.patient_nom || rdv.patient}</span>
              <Badge tone={rdv.statut === 'arrive' ? 'success' : 'neutral'}>
                {rdv.statut_display || rdv.statut}
              </Badge>
              {rdv.statut !== 'arrive' && rdv.statut !== 'termine' && rdv.statut !== 'annule' && (
                <Button variant="ghost" onClick={() => checkin(rdv)}>
                  <LogIn size={14} strokeWidth={1.75} aria-hidden="true" /> Patient arrivé
                </Button>
              )}
              {rdv.statut !== 'termine' && rdv.statut !== 'annule' && (
                <Button
                  variant="ghost" onClick={() => annuler(rdv)}
                  aria-label="Annuler ce rendez-vous"
                >
                  Annuler
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
