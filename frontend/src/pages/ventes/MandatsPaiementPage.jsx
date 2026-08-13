import { useEffect, useMemo, useState } from 'react'
import { CreditCard, ShieldCheck } from 'lucide-react'
import api from '../../api/axios'
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'
import {
  Badge, Button, Card, EmptyState, Segmented, Skeleton,
} from '../../ui'
import { Table } from '../reporting/Table'
import { formatDateTime } from '../../lib/format'
import { toast, useConfirmDialog } from '../../ui/confirm'

/* ============================================================================
   PACT43 — Mandats de paiement récurrents (carte TOKENISÉE), vue INTERNE.
   ----------------------------------------------------------------------------
   Le client tokenise sa carte depuis son portail (flux XCTR14, hors ERP). Cet
   écran est la moitié qui manquait : lister les mandats actifs / expirés /
   révoqués par client, et RÉVOQUER — un mandat révoqué fait repasser le client
   sur encaissement manuel.

   RÈGLE ABSOLUE (rappelée à l'écran) : AUCUNE donnée de carte n'est jamais
   saisie ni stockée dans l'ERP. Le serveur n'expose qu'un jeton OPAQUE (jamais
   rendu ici) et les 4 DERNIERS CHIFFRES + le mois d'expiration, pour que
   l'opérateur reconnaisse la carte. Cet écran ne rend donc AUCUN champ de
   saisie — c'est une vue de lecture + révocation, verrouillée par son test.

   Endpoints (apps/ventes/views/mandat_paiement.py, IsResponsableOrAdmin) :
     GET  /ventes/mandats-paiement/               liste (scopée société)
     POST /ventes/mandats-paiement/{id}/revoquer/ révocation immédiate
   ========================================================================== */

const FILTRES = [
  { value: 'tous', label: 'Tous' },
  { value: 'actif', label: 'Actifs' },
  { value: 'expire', label: 'Expirés' },
  { value: 'revoque', label: 'Révoqués' },
]

const TONE_STATUT = { actif: 'success', expire: 'warning', revoque: 'danger' }
const LIBELLE_STATUT = { actif: 'Actif', expire: 'Expiré', revoque: 'Révoqué' }

// Empreinte lisible d'une carte tokenisée — JAMAIS un PAN : les 4 derniers
// chiffres sont la seule donnée de carte que le serveur expose.
function empreinteCarte(m) {
  const fin = (m.derniers_chiffres || '').trim()
  return fin ? `•••• ${fin}` : 'Carte tokenisée'
}

export default function MandatsPaiementPage() {
  const { confirm } = useConfirmDialog()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [filtre, setFiltre] = useState('tous')
  const [busyId, setBusyId] = useState(null)

  const charger = () => api.get('/ventes/mandats-paiement/')
    .then((r) => {
      const data = r.data
      setRows(Array.isArray(data) ? data : (data?.results || []))
      setErreur(false)
    })
    .catch(() => { setRows([]); setErreur(true) })
    .finally(() => setLoading(false))

  // `loading`/`erreur` démarrent déjà à leurs valeurs de chargement : aucun
  // reset synchrone dans l'effet (react-hooks/set-state-in-effect).
  useEffect(() => { charger() }, [])

  const revoquer = async (m) => {
    const ok = await confirm({
      title: `Révoquer le mandat de ${m.client_nom || 'ce client'} ?`,
      description: 'Le prélèvement automatique s\'arrête immédiatement : '
        + 'ce client repasse sur encaissement manuel.',
      confirmLabel: 'Révoquer',
      destructive: true,
    })
    if (!ok) return
    setBusyId(m.id)
    try {
      await api.post(`/ventes/mandats-paiement/${m.id}/revoquer/`)
      toast.success('Mandat révoqué — encaissement manuel rétabli.')
      setLoading(true)
      await charger()
    } catch {
      toast.error('Révocation impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const affiches = useMemo(
    () => (filtre === 'tous' ? rows : rows.filter((m) => m.statut === filtre)),
    [rows, filtre],
  )

  const colonnes = [
    { key: 'client', header: 'Client', cell: (m) => m.client_nom || `#${m.client}` },
    {
      key: 'carte',
      header: 'Carte',
      cell: (m) => (
        <span className="tabular-nums">{empreinteCarte(m)}</span>
      ),
    },
    { key: 'expiration', header: 'Expiration', cell: (m) => m.expiration_mois || '—' },
    { key: 'provider', header: 'Prestataire', cell: (m) => m.provider || '—' },
    {
      key: 'statut',
      header: 'Statut',
      cell: (m) => (
        <Badge tone={TONE_STATUT[m.statut] || 'neutral'}>
          {LIBELLE_STATUT[m.statut] || m.statut}
        </Badge>
      ),
    },
    {
      key: 'consentement',
      header: 'Consentement',
      cell: (m) => (m.consentement_horodate
        ? formatDateTime(m.consentement_horodate)
        : <span className="text-muted-foreground">Non horodaté</span>),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      cell: (m) => (m.statut === 'actif' ? (
        <Button size="sm" variant="outline"
                loading={busyId === m.id}
                disabled={busyId === m.id}
                onClick={() => revoquer(m)}>
          Révoquer
        </Button>
      ) : (
        <span className="text-xs text-muted-foreground">
          {m.statut === 'revoque' ? 'Encaissement manuel' : '—'}
        </span>
      )),
    },
  ]

  return (
    <div className="page">
      <PageHeader
        style={VENTES_ACCENT_STYLE}
        className="app-accent-rail"
        icon={CreditCard}
        title="Mandats de paiement récurrents"
        subtitle="Cartes tokenisées par les clients depuis leur portail. Révoquer un mandat fait repasser le client sur encaissement manuel."
      />

      {/* Rappel de conformité — la raison d'être de cet écran : il ne demande
          RIEN, il ne fait que lire ce que le prestataire a tokenisé. */}
      <Card className="mb-4 flex items-start gap-2 p-3 text-sm">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
        <p className="m-0 text-muted-foreground">
          Aucune donnée de carte n&apos;est saisie ni stockée dans l&apos;ERP :
          seuls un jeton opaque (jamais affiché) et les 4 derniers chiffres sont
          connus du serveur.
        </p>
      </Card>

      <Segmented
        options={FILTRES}
        value={filtre}
        onChange={setFiltre}
        aria-label="Filtrer les mandats par statut"
      />

      <Card className="mt-4 overflow-hidden">
        {loading && <Skeleton className="m-4 h-24" />}
        {!loading && erreur && (
          <EmptyState
            title="Chargement impossible"
            description="Les mandats de paiement n'ont pas pu être chargés."
          />
        )}
        {!loading && !erreur && affiches.length === 0 && (
          <EmptyState
            icon={CreditCard}
            title="Aucun mandat"
            description="Aucun mandat de paiement récurrent pour ce filtre."
          />
        )}
        {!loading && !erreur && affiches.length > 0 && (
          <Table
            aria-label="Mandats de paiement récurrents"
            caption="Mandats de paiement récurrents par client"
            rows={affiches}
            getRowKey={(m) => m.id}
            columns={colonnes}
          />
        )}
      </Card>
    </div>
  )
}
