import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT7 — Détail d'un événement : liste des inscrits + check-in + QR par
   inscrit + segment « présents » en un clic.
   ----------------------------------------------------------------------------
   `marketing/inscriptions-evenement/?evenement=<id>` (statut inscrit/
   confirmé/présent/absent), action `pointer` (check-in sur place). Le
   « QR par inscrit » réutilise le badge PDF déjà généré côté serveur
   (`InscriptionEvenementViewSet.badge`, ZMKT19 — lui-même bâti sur
   `stock.labels.qr_svg`, XMKT29) plutôt que de dupliquer un rendu QR côté
   client : un badge téléchargé encode le même `qr_token` scannable qui
   compte le passage. « Créer le segment présents » (NTMKT4) pose
   `regles: {evenement_present: <id>}` — filtre déjà supporté par
   `apps.compta.services.valider_regles_segment` (XMKT28), aucun nouveau
   champ backend.
   ========================================================================== */

const STATUTS = [
  { key: '', label: 'Tous' },
  { key: 'inscrit', label: 'Inscrit' },
  { key: 'confirme', label: 'Confirmé' },
  { key: 'present', label: 'Présent' },
  { key: 'absent', label: 'Absent' },
]

export default function EvenementDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [evenement, setEvenement] = useState(null)
  const [inscriptions, setInscriptions] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [segmentMsg, setSegmentMsg] = useState('')

  const loadEvenement = useCallback(() => {
    setLoading(true)
    return marketingApi.evenements.get(id)
      .then(r => setEvenement(r.data))
      .catch(() => setErr('Événement introuvable.'))
      .finally(() => setLoading(false))
  }, [id])

  const loadInscriptions = useCallback(() => {
    return marketingApi.inscriptionsEvenement.list(
      { evenement: id, ...(statutFiltre ? { statut: statutFiltre } : {}) })
      .then(r => setInscriptions(marketingApi.unwrapList(r)))
      .catch(() => setInscriptions([]))
  }, [id, statutFiltre])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { loadEvenement() }, [loadEvenement])
  useEffect(() => { loadInscriptions() }, [loadInscriptions])

  const pointer = async (inscriptionId) => {
    setErr('')
    try {
      await marketingApi.inscriptionsEvenement.pointer(inscriptionId)
      loadInscriptions()
    } catch {
      setErr('Check-in impossible.')
    }
  }

  const telechargerBadge = async (inscriptionId, nom) => {
    setErr('')
    try {
      const r = await marketingApi.inscriptionsEvenement.badgePdf(inscriptionId)
      marketingApi.downloadBlob(r.data, `badge-${nom || inscriptionId}.pdf`)
    } catch {
      setErr('Badge indisponible.')
    }
  }

  const creerSegmentPresents = async () => {
    setSegmentMsg('')
    setErr('')
    try {
      await marketingApi.segments.create({
        nom: `Présents — ${evenement.nom}`,
        regles: { evenement_present: Number(id) },
      })
      setSegmentMsg('Segment « Présents » créé.')
    } catch {
      setErr('Création du segment impossible.')
    }
  }

  if (loading) return <div className="page"><p className="page-loading">Chargement…</p></div>
  if (!evenement) return <div className="page"><p style={{ color: '#dc2626' }}>{err || 'Introuvable.'}</p></div>

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn btn-light" onClick={() => navigate('/marketing/evenements')}>
          ← Événements
        </button>
        <h2>{evenement.nom}</h2>
        <button className="btn btn-primary" data-testid="evenement-segment-presents"
          onClick={creerSegmentPresents}>
          Créer le segment présents
        </button>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {segmentMsg && <p style={{ color: '#16a34a' }}>{segmentMsg}</p>}

      <select className="form-input" data-testid="inscriptions-filtre-statut"
        value={statutFiltre} onChange={e => setStatutFiltre(e.target.value)}
        style={{ marginBottom: 8 }}>
        {STATUTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
      </select>

      <table className="data-table" data-testid="inscriptions-table">
        <thead>
          <tr><th>Nom</th><th>Email</th><th>Statut</th><th /></tr>
        </thead>
        <tbody>
          {inscriptions.map(insc => (
            <tr key={insc.id} data-testid="inscription-row">
              <td>{insc.nom}</td>
              <td>{insc.email || '—'}</td>
              <td>{insc.statut_display || insc.statut}</td>
              <td style={{ display: 'flex', gap: 6 }}>
                {insc.statut !== 'present' && (
                  <button className="btn btn-light" type="button"
                    data-testid="inscription-pointer" onClick={() => pointer(insc.id)}>
                    Check-in
                  </button>
                )}
                <button className="btn btn-light" type="button"
                  data-testid="inscription-badge"
                  onClick={() => telechargerBadge(insc.id, insc.nom)}>
                  Badge / QR
                </button>
              </td>
            </tr>
          ))}
          {inscriptions.length === 0 && (
            <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
              Aucun inscrit
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
