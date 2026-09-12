import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, HardDriveDownload } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { formatDateTime } from '../../lib/format'
import {
  Badge, Button, Card, CardContent, Spinner, toast,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel,
  AlertDialogAction,
} from '../../ui'

/* ============================================================================
   NTOBS7 — Paramètres → Fiabilité → Export de réversibilité. Complète NTOBS6
   (POST /core/export-reversibilite/, GET .../historique/) : bouton « Exporter
   toutes mes données » (confirm dialog), liste des exports précédents avec
   statut/taille/lien, toast quand un export bascule `pret`.
   ========================================================================== */

const POLL_INTERVAL_MS = 5000

const STATUT_LABEL = {
  en_cours: 'En cours',
  pret: 'Prêt',
  expire: 'Expiré',
  echec: 'Échec',
}
const STATUT_TONE = {
  en_cours: 'info',
  pret: 'success',
  expire: 'neutral',
  echec: 'danger',
}

// VX75 — jamais un formatage de date natif hors lib/format.js : la locale et
// le fuseau société passent par le point unique formatDateTime.
function formatDate(iso) {
  if (!iso) return ''
  return formatDateTime(iso, { long: true })
}

function formatTaille(octets) {
  if (octets == null) return ''
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`
}

export default function ExportReversibilitePage() {
  const [historique, setHistorique] = useState([])
  const [loading, setLoading] = useState(true)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [lancement, setLancement] = useState(false)
  const previousStatuts = useRef({})

  const charger = useCallback(() => {
    return parametresApi.getHistoriqueExportReversibilite()
      .then((r) => {
        const rows = r.data ?? []
        // Un run qui bascule `pret` depuis un état précédent différent -> toast.
        rows.forEach((run) => {
          const avant = previousStatuts.current[run.id]
          if (avant && avant !== 'pret' && run.statut === 'pret') {
            toast.success('Votre export de données est prêt.')
          }
          previousStatuts.current[run.id] = run.statut
        })
        setHistorique(rows)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    charger().finally(() => { if (active) setLoading(false) })
    const interval = setInterval(() => { if (active) charger() }, POLL_INTERVAL_MS)
    return () => { active = false; clearInterval(interval) }
  }, [charger])

  const lancerExport = () => {
    setLancement(true)
    parametresApi.declencherExportReversibilite()
      .then(() => {
        toast.success("Export lancé — vous serez notifié quand il sera prêt.")
        setConfirmOpen(false)
        charger()
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail
        toast.error(detail || "Impossible de lancer l'export.")
      })
      .finally(() => setLancement(false))
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h1 className="text-xl font-semibold">Export de réversibilité</h1>
      <p className="text-sm text-muted-foreground">
        Exportez toutes les données de votre société (leads, clients, devis, factures,
        chantiers, tickets, employés, documents…) en CSV, plus les fichiers déjà stockés,
        dans une archive ZIP téléchargeable pendant 7 jours.
      </p>

      <Button onClick={() => setConfirmOpen(true)} disabled={lancement}>
        <HardDriveDownload className="mr-2 h-4 w-4" aria-hidden="true" />
        Exporter toutes mes données
      </Button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Lancer un export complet ?</AlertDialogTitle>
            <AlertDialogDescription>
              Un fichier ZIP contenant un CSV par entité (leads, clients, devis, factures,
              chantiers, tickets, employés, documents) et les fichiers déjà stockés sera
              préparé en arrière-plan. Vous serez notifié dès qu'il sera prêt ; le lien de
              téléchargement expire au bout de 7 jours.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={lancerExport} disabled={lancement}>
              {lancement ? <Spinner className="mr-2 h-4 w-4" /> : null}
              Lancer l'export
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <h2 className="mt-8 text-lg font-medium">Exports précédents</h2>
      {loading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : historique.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun export lancé pour le moment.</p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {historique.map((run) => (
            <li key={run.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="text-sm">{formatDate(run.created_at)}</p>
                <p className="text-xs text-muted-foreground">
                  {formatTaille(run.taille_octets)}
                  {run.expire_le ? ` — expire le ${formatDate(run.expire_le)}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={STATUT_TONE[run.statut] || 'neutral'}>
                  {STATUT_LABEL[run.statut] || run.statut}
                </Badge>
                {run.statut === 'pret' && run.token && (
                  <a
                    href={`/api/django/core/export-reversibilite/telecharger/${run.token}/`}
                    className="inline-flex items-center gap-1 text-sm text-primary underline"
                  >
                    <Download className="h-4 w-4" aria-hidden="true" />
                    Télécharger
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
