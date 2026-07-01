import { useEffect, useState } from 'react'
import { CalendarDays, Receipt, FileText, Plane } from 'lucide-react'
import { Card, Stat, Segmented, Badge, EmptyState, Skeleton, toast } from '../../ui'
import { formatMAD, formatNumber, formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { StatutConge, StatutNoteFrais, StatutMission } from './constants.jsx'

/* ============================================================================
   UX28 — Portail self-service (tous rôles).
   ----------------------------------------------------------------------------
   Tableau de bord du collaborateur connecté : ses infos, ses soldes de congés,
   ses demandes de congé, ses notes de frais, ses ordres de mission, ses
   documents/bulletins. TOUT est résolu côté serveur à partir du dossier lié au
   compte appelant — un collaborateur ne voit JAMAIS les données d'un autre.
   Si aucun dossier n'est lié au compte, le portail l'indique clairement.
   ========================================================================== */

const VUES = [
  { value: 'conges', label: 'Mes congés' },
  { value: 'frais', label: 'Mes frais' },
  { value: 'missions', label: 'Mes missions' },
  { value: 'documents', label: 'Mes documents' },
]

export default function Portail() {
  const [vue, setVue] = useState('conges')
  const [infos, setInfos] = useState(null)
  const [soldes, setSoldes] = useState([])
  const [conges, setConges] = useState([])
  const [frais, setFrais] = useState([])
  const [missions, setMissions] = useState([])
  const [bulletins, setBulletins] = useState([])
  const [loading, setLoading] = useState(true)
  const [sansDossier, setSansDossier] = useState(false)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setSansDossier(false)
    rhApi.getMesInfos()
      .then((res) => { if (vivant) setInfos(res.data) })
      .catch((err) => {
        if (!vivant) return
        // 404 = aucun dossier employé lié au compte.
        if (err?.response?.status === 404) setSansDossier(true)
        else toast.error('Impossible de charger votre portail.')
      })

    Promise.allSettled([
      rhApi.getMesSoldes(),
      rhApi.getMesConges(),
      rhApi.getMesFrais(),
      rhApi.getOrdresMission(),
      rhApi.getMesBulletins(),
    ]).then((r) => {
      if (!vivant) return
      const [s, c, f, m, b] = r
      if (s.status === 'fulfilled') setSoldes(unwrap(s.value.data))
      if (c.status === 'fulfilled') setConges(unwrap(c.value.data))
      if (f.status === 'fulfilled') setFrais(unwrap(f.value.data))
      if (m.status === 'fulfilled') setMissions(unwrap(m.value.data))
      if (b.status === 'fulfilled') setBulletins(unwrap(b.value.data))
      setLoading(false)
    })
    return () => { vivant = false }
  }, [])

  if (loading) {
    return (
      <div className="page flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (sansDossier) {
    return (
      <div className="page">
        <EmptyState
          title="Aucun dossier employé lié à votre compte"
          description="Contactez les ressources humaines pour associer votre dossier à ce compte."
        />
      </div>
    )
  }

  const soldeTotal = soldes.reduce((acc, s) => acc + Number(s.disponible ?? 0), 0)
  const fraisEnCours = frais.filter((f) => f.statut === 'soumise').length

  return (
    <div className="page flex flex-col gap-6">
      <div className="page-header">
        <h2>Mon portail RH</h2>
        {infos && (
          <span className="text-sm text-muted-foreground">
            {infos.nom} {infos.prenom} · {infos.poste || '—'}
          </span>
        )}
      </div>

      {/* Bandeau KPI personnel. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4"><Stat label="Solde congés" value={`${formatNumber(soldeTotal, { decimals: 1 })} j`} hint="Disponible" icon={CalendarDays} /></Card>
        <Card className="p-4"><Stat label="Demandes en cours" value={formatNumber(conges.filter((c) => c.statut === 'soumise').length)} hint="Congés soumis" icon={CalendarDays} /></Card>
        <Card className="p-4"><Stat label="Frais soumis" value={formatNumber(fraisEnCours)} hint="En attente de remboursement" icon={Receipt} /></Card>
        <Card className="p-4"><Stat label="Bulletins" value={formatNumber(bulletins.length)} hint="Disponibles" icon={FileText} /></Card>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue portail" />

      {vue === 'conges' && (
        <PortailListe
          rows={conges}
          empty="Aucune demande de congé."
          renderRow={(c) => (
            <RowLine
              title={`${formatDate(c.date_debut)} → ${formatDate(c.date_fin)}`}
              meta={`${c.type_absence_code || ''} · ${formatNumber(c.jours ?? 0, { decimals: 1 })} j`}
              right={<StatutConge status={c.statut} label={c.statut_display} />}
            />
          )}
        />
      )}
      {vue === 'frais' && (
        <PortailListe
          rows={frais}
          empty="Aucune note de frais."
          renderRow={(f) => (
            <RowLine
              title={f.libelle || f.categorie_display || 'Note de frais'}
              meta={`${formatMAD(f.montant)}${f.date_frais ? ` · ${formatDate(f.date_frais)}` : ''}`}
              right={<StatutNoteFrais status={f.statut} label={f.statut_display} />}
            />
          )}
        />
      )}
      {vue === 'missions' && (
        <PortailListe
          rows={missions}
          empty="Aucun ordre de mission."
          renderRow={(m) => (
            <RowLine
              title={m.destination || m.reference || 'Mission'}
              meta={`${m.motif || ''}${m.date_depart ? ` · ${formatDate(m.date_depart)}` : ''}`}
              right={<StatutMission status={m.statut} label={m.statut_display} />}
              icon={Plane}
            />
          )}
        />
      )}
      {vue === 'documents' && (
        <PortailListe
          rows={bulletins}
          empty="Aucun bulletin de paie."
          renderRow={(b) => (
            <RowLine
              title={`Bulletin ${String(b.mois).padStart(2, '0')}/${b.annee}`}
              meta={b.filename || '—'}
              right={b.url
                ? <a className="link-blue text-xs" href={b.url} target="_blank" rel="noreferrer">Ouvrir</a>
                : <Badge tone="neutral">Indisponible</Badge>}
            />
          )}
        />
      )}
    </div>
  )
}

function PortailListe({ rows, empty, renderRow }) {
  if (!rows.length) {
    return <EmptyState title="Rien à afficher" description={empty} />
  }
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <li key={r.id ?? i} className="rounded-lg border border-border bg-card px-4 py-3">
          {renderRow(r)}
        </li>
      ))}
    </ul>
  )
}

function RowLine({ title, meta, right, icon: Icon }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden="true" className="text-muted-foreground" />}
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{title}</p>
          {meta && <p className="truncate text-xs text-muted-foreground">{meta}</p>}
        </div>
      </div>
      <div className="shrink-0">{right}</div>
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
