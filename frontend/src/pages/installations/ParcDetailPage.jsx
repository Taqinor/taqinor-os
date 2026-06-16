import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import installationsApi from '../../api/installationsApi'
import { garantieLabel, garantieColor } from '../../features/sav/equipement'

// Hub d'UN système installé (N10) — composants (équipements + n° série + N9
// saisie), garanties, tickets SAV liés, contrats de maintenance, et un
// placeholder de monitoring. Lecture des relations existantes ; la seule
// écriture est la saisie des n° de série (N9), qui ne bloque jamais rien.

const TYPE_LABELS = {
  residentiel: 'Résidentiel',
  industriel: 'Industriel / Commercial',
  agricole: 'Agricole (pompage)',
}

const TICKET_STATUT_LABELS = {
  nouveau: 'Nouveau', planifie: 'Planifié', en_cours: 'En cours',
  resolu: 'Résolu', cloture: 'Clôturé',
}

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

function GarantieBadge({ eq }) {
  return (
    <span style={{
      background: `${garantieColor(eq)}22`, color: garantieColor(eq),
      padding: '2px 8px', borderRadius: 6, fontSize: 12, whiteSpace: 'nowrap',
    }}>{garantieLabel(eq)}</span>
  )
}

export default function ParcDetailPage() {
  const { id } = useParams()
  const [hub, setHub] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // N9 — n° de série en édition locale (id équipement → valeur).
  const [serials, setSerials] = useState({})
  const [savingSerials, setSavingSerials] = useState(false)

  const load = useCallback(() => {
    installationsApi.getParcHub(id)
      .then((r) => {
        setHub(r.data)
        const init = {}
        for (const eq of (r.data.equipements ?? [])) {
          init[eq.id] = eq.numero_serie ?? ''
        }
        setSerials(init)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { load() }, [load])

  const saveSerials = async () => {
    setSavingSerials(true)
    try {
      await installationsApi.setSerials(id, serials)
      load()
    } catch { /* erreur silencieuse */ } finally { setSavingSerials(false) }
  }

  if (loading) return <div className="page"><p className="gen-hint">Chargement…</p></div>
  if (error || !hub) {
    return (
      <div className="page">
        <p className="gen-hint">Système installé introuvable.</p>
        <Link to="/parc" className="btn btn-outline btn-sm">← Parc installé</Link>
      </div>
    )
  }

  const equipements = hub.equipements ?? []
  const tickets = hub.tickets ?? []
  const contrats = hub.contrats_maintenance ?? []

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">{hub.reference}</h1>
          <div className="page-subtitle">
            {hub.client_nom ?? '—'} · {hub.site_ville ?? '—'} ·{' '}
            {TYPE_LABELS[hub.type_installation] ?? hub.type_installation ?? '—'}
          </div>
        </div>
        <Link to="/parc" className="btn btn-outline btn-sm">← Parc installé</Link>
      </div>

      {/* ── Synthèse du système ── */}
      <div className="card" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <Info label="Puissance installée"
                value={hub.puissance_installee_kwc != null
                  ? `${Number(hub.puissance_installee_kwc).toLocaleString('fr-FR')} kWc` : '—'} />
          <Info label="Mise en service" value={formatDateFR(hub.date_mise_en_service)} />
          <Info label="Réception parc" value={formatDateFR(hub.date_reception)} />
          <Info label="Technicien" value={hub.technicien_nom ?? '—'} />
          <Info label="Devis d'origine" value={hub.devis_reference ?? '—'} />
          <Info label="Adresse du site" value={hub.site_adresse ?? '—'} />
          {hub.gps_lat != null && hub.gps_lng != null && (
            <Info label="GPS" value={
              <a target="_blank" rel="noreferrer"
                 href={`https://www.openstreetmap.org/?mlat=${hub.gps_lat}&mlon=${hub.gps_lng}#map=17/${hub.gps_lat}/${hub.gps_lng}`}>
                {Number(hub.gps_lat).toFixed(5)}, {Number(hub.gps_lng).toFixed(5)} ↗
              </a>
            } />
          )}
          <Info label="Supervision (monitoring)"
                value={hub.monitoring?.statut_display ?? 'Non configuré'} />
        </div>
      </div>

      {/* ── Composants installés + n° de série (N9) + garanties ── */}
      <section style={{ marginBottom: 16 }}>
        <h2 className="form-section-title">Composants installés ({equipements.length})</h2>
        {equipements.length === 0 ? (
          <p className="gen-hint">Aucun composant. Les composants sont créés à la réception du chantier.</p>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Produit</th>
                    <th className="m-hide">Marque</th>
                    <th>N° de série</th>
                    <th className="m-hide">Pose</th>
                    <th>Garantie</th>
                  </tr>
                </thead>
                <tbody>
                  {equipements.map((eq) => (
                    <tr key={eq.id}>
                      <td>{eq.produit_nom ?? '—'}</td>
                      <td className="m-hide">{eq.produit_marque ?? '—'}</td>
                      <td>
                        <input className="form-control" style={{ minWidth: 140 }}
                               placeholder="N° de série (optionnel)"
                               value={serials[eq.id] ?? ''}
                               onChange={(e) => setSerials((s) => ({ ...s, [eq.id]: e.target.value }))} />
                      </td>
                      <td className="m-hide">{formatDateFR(eq.date_pose)}</td>
                      <td><GarantieBadge eq={eq} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
              <button type="button" className="btn btn-primary btn-sm"
                      disabled={savingSerials} onClick={saveSerials}>
                {savingSerials ? 'Enregistrement…' : 'Enregistrer les n° de série'}
              </button>
              <span className="form-hint">Un n° de série vide est autorisé — rien n'est bloqué.</span>
            </div>
          </>
        )}
      </section>

      {/* ── Tickets SAV liés ── */}
      <section style={{ marginBottom: 16 }}>
        <h2 className="form-section-title">Tickets SAV ({tickets.length})</h2>
        {tickets.length === 0 ? (
          <p className="gen-hint">Aucun ticket SAV.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Référence</th>
                  <th className="m-hide">Type</th>
                  <th>Statut</th>
                  <th className="m-hide">Ouvert le</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((t) => (
                  <tr key={t.id}>
                    <td><Link to="/sav">{t.reference}</Link></td>
                    <td className="m-hide">{t.type_display ?? t.type}</td>
                    <td>{TICKET_STATUT_LABELS[t.statut] ?? t.statut}</td>
                    <td className="m-hide">{formatDateFR(t.date_ouverture)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Contrats de maintenance ── */}
      <section style={{ marginBottom: 16 }}>
        <h2 className="form-section-title">Contrats de maintenance ({contrats.length})</h2>
        {contrats.length === 0 ? (
          <p className="gen-hint">Aucun contrat de maintenance.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Libellé</th>
                  <th className="m-hide">Début</th>
                  <th>Prochaine visite</th>
                  <th className="m-hide">Actif</th>
                </tr>
              </thead>
              <tbody>
                {contrats.map((c) => (
                  <tr key={c.id}>
                    <td><Link to="/sav/contrats">{c.libelle ?? `Contrat #${c.id}`}</Link></td>
                    <td className="m-hide">{formatDateFR(c.date_debut)}</td>
                    <td>{formatDateFR(c.prochaine_visite)}</td>
                    <td className="m-hide">{c.actif ? 'Oui' : 'Non'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 500 }}>{value}</div>
    </div>
  )
}
