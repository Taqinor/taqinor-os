import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { LayoutDashboard } from 'lucide-react'
import { Badge } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import ChantierSelect from './ChantierSelect'
import { formatMontant } from './planningLots.utils'

/* ============================================================================
   NTCON21 — Tableau de bord BTP par chantier.
   ----------------------------------------------------------------------------
   SIX blocs en un écran, tous en LECTURE SEULE et tous alimentés par des
   endpoints DÉJÀ construits — aucune nouvelle logique backend, aucun chiffre
   recalculé côté client :
     1. Lots + avancement (NTCON14, `planning-lots`)
     2. Réserves ouvertes / levées (NTCON1, `reserves-chantier`)
     3. RFI en attente (NTCON3, `rfi?statut=ouvert`)
     4. Visas en cours (NTCON5, `visas`)
     5. Déboursé vs facturé (NTCON11, `debourse-vs-facture`) — donnée INTERNE :
        le serveur exige `btp_gerer` même en lecture, un 403 masque le bloc
        proprement (jamais un coût affiché à qui n'y a pas droit).
     6. Dernier journal de chantier (NTCON6, `journal-chantier`)

   Responsive « mobile chantier » : grille auto-fit, aucune largeur fixe.
   ========================================================================== */

const STATUTS_VISA_EN_COURS = ['soumis', 'en_revue']

function Bloc({ titre, children }) {
  return (
    <section
      aria-label={titre}
      style={{
        border: '1px solid #e2e8f0', borderRadius: 8, padding: 12,
        background: 'rgba(148,163,184,0.05)',
      }}
    >
      <h2 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 8px' }}>{titre}</h2>
      {children}
    </section>
  )
}

export default function ChantierBtpCockpit() {
  const params = useParams()
  const [chantierId, setChantierId] = useState(params.chantierId || '')
  const [etat, setEtat] = useState({
    lots: [], reserves: [], rfis: [], visas: [], journal: null,
    debourse: null, debourseInterdit: false,
  })
  const [loading, setLoading] = useState(false)

  const charger = useCallback(() => {
    if (!chantierId) return undefined
    let cancelled = false
    setLoading(true)
    const rows = (res) => {
      const payload = res?.data
      if (Array.isArray(payload)) return payload
      if (Array.isArray(payload?.results)) return payload.results
      return []
    }
    Promise.all([
      btpChantierApi.planningLots(chantierId).then(rows).catch(() => []),
      btpChantierApi.reserves.list({ chantier: chantierId }).then(rows)
        .catch(() => []),
      btpChantierApi.rfi.list({ chantier: chantierId, statut: 'ouvert' })
        .then(rows).catch(() => []),
      btpChantierApi.visas.list({ chantier: chantierId }).then(rows)
        .catch(() => []),
      btpChantierApi.journal.list({ chantier: chantierId }).then(rows)
        .catch(() => []),
      btpChantierApi.debourseVsFacture(chantierId)
        .then((res) => ({ data: res?.data || null, interdit: false }))
        .catch((err) => ({
          data: null, interdit: err?.response?.status === 403,
        })),
    ]).then(([lots, reserves, rfis, visas, journaux, debourse]) => {
      if (cancelled) return
      setEtat({
        lots,
        reserves,
        rfis,
        visas: visas.filter((v) => STATUTS_VISA_EN_COURS.includes(v.statut)),
        journal: journaux[0] || null,
        debourse: debourse.data,
        debourseInterdit: debourse.interdit,
      })
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [chantierId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement
  useEffect(() => charger(), [charger])

  const reservesOuvertes = etat.reserves.filter(
    (r) => r.statut === 'ouverte' || r.statut === 'en_cours')
  const reservesLevees = etat.reserves.filter((r) => r.statut === 'levee')

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <LayoutDashboard size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          Tableau de bord BTP du chantier
        </h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <ChantierSelect
          value={chantierId}
          onChange={setChantierId}
          label="Chantier du tableau de bord"
        />
      </div>

      {!chantierId && <p>Choisissez un chantier pour afficher son tableau de bord.</p>}
      {loading && <p>Chargement…</p>}

      {chantierId && !loading && (
        <div
          data-testid="btp-cockpit"
          style={{
            display: 'grid', gap: 12,
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          }}
        >
          <Bloc titre="Lots et avancement">
            {etat.lots.length === 0 && <p>Aucun lot.</p>}
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {etat.lots.map((lot) => (
                <li key={lot.id}>
                  <span style={{ color: lot.couleur }}>■</span>{' '}
                  {lot.nom} — {lot.avancement_pct}%
                  {lot.en_retard && (
                    <Badge tone="danger" style={{ marginLeft: 6 }}>En retard</Badge>
                  )}
                </li>
              ))}
            </ul>
          </Bloc>

          <Bloc titre="Réserves">
            <p data-testid="btp-cockpit-reserves">
              {reservesOuvertes.length} ouverte(s) · {reservesLevees.length} levée(s)
            </p>
          </Bloc>

          <Bloc titre="RFI en attente">
            <p data-testid="btp-cockpit-rfi">{etat.rfis.length} RFI ouvert(s)</p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {etat.rfis.slice(0, 5).map((rfi) => (
                <li key={rfi.id}>
                  N° {rfi.numero} — {rfi.question}
                  {rfi.en_retard && (
                    <Badge tone="danger" style={{ marginLeft: 6 }}>En retard</Badge>
                  )}
                </li>
              ))}
            </ul>
          </Bloc>

          <Bloc titre="Visas en cours">
            <p data-testid="btp-cockpit-visas">{etat.visas.length} visa(s) en cours</p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {etat.visas.slice(0, 5).map((visa) => (
                <li key={visa.id}>{visa.reference}</li>
              ))}
            </ul>
          </Bloc>

          <Bloc titre="Déboursé vs facturé">
            {etat.debourseInterdit && (
              <p>Réservé aux responsables (donnée interne).</p>
            )}
            {!etat.debourseInterdit && !etat.debourse && <p>Indisponible.</p>}
            {!etat.debourseInterdit && etat.debourse && (
              <p data-testid="btp-cockpit-debourse">
                Déboursé {formatMontant(etat.debourse.debourse_sec_total)} ·
                Facturé {formatMontant(etat.debourse.facture_total)} ·
                Marge {formatMontant(etat.debourse.marge)}
              </p>
            )}
          </Bloc>

          <Bloc titre="Dernier journal de chantier">
            {!etat.journal && <p>Aucune entrée de journal.</p>}
            {etat.journal && (
              <p data-testid="btp-cockpit-journal">
                {etat.journal.date} — {etat.journal.evenements || 'Sans événement noté'}
              </p>
            )}
          </Bloc>
        </div>
      )}
    </div>
  )
}
