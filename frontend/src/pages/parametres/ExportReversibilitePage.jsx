import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, HardDriveDownload } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import coreApi from '../../api/coreApi'
import { formatDateTime } from '../../lib/format'
import {
  Badge, Button, Card, CardContent, Spinner, toast, Checkbox,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from '../../ui'

/* ============================================================================
   NTOBS7/NTOBS20 — Paramètres → Fiabilité → Export de réversibilité. Complète
   NTOBS6 (POST /core/export-reversibilite/, GET .../historique/) : le bouton
   « Exporter toutes mes données » ouvre un assistant 2 étapes — étape 1
   sélection des jeux de données (catalogue `core.export_registry`, exposé au
   front via `core/saved-queries/datasets/`, tout coché par défaut), étape 2
   récapitulatif puis lancement. `datasets` reste OPTIONNEL côté serveur :
   tout coché envoie `undefined` (comportement par défaut inchangé, jamais un
   tableau qui dupliquerait silencieusement « tout »). Liste des exports
   précédents avec statut/taille/lien, toast quand un export bascule `pret`.
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
  const [lancement, setLancement] = useState(false)
  const previousStatuts = useRef({})

  // NTOBS20 — assistant 2 étapes. `datasets` : catalogue chargé à la première
  // ouverture (jamais rechargé ensuite, un aller-retour au clavier ne doit
  // pas réinitialiser une sélection en cours) ; `selectionnes` : tout coché
  // par défaut dès que le catalogue arrive.
  const [wizardOpen, setWizardOpen] = useState(false)
  const [etape, setEtape] = useState(1)
  const [datasets, setDatasets] = useState(null)
  const [selectionnes, setSelectionnes] = useState(new Set())

  const ouvrirAssistant = () => {
    setWizardOpen(true)
    setEtape(1)
    if (datasets === null) {
      coreApi.datasetsExplorateur.list()
        .then((r) => {
          const liste = Array.isArray(r.data) ? r.data : []
          setDatasets(liste)
          setSelectionnes(new Set(liste.map((d) => d.name)))
        })
        .catch(() => setDatasets([]))
    }
  }

  const basculerDataset = (name) => setSelectionnes((prev) => {
    const next = new Set(prev)
    if (next.has(name)) next.delete(name); else next.add(name)
    return next
  })

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
    // Tout coché → `undefined` (comportement par défaut inchangé côté
    // serveur) plutôt qu'un tableau qui listerait « tout » explicitement.
    const toutCoche = datasets && selectionnes.size === datasets.length
    const payload = toutCoche ? undefined : Array.from(selectionnes)
    setLancement(true)
    parametresApi.declencherExportReversibilite(payload)
      .then(() => {
        toast.success("Export lancé — vous serez notifié quand il sera prêt.")
        setWizardOpen(false)
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

      <Button onClick={ouvrirAssistant} disabled={lancement}>
        <HardDriveDownload className="mr-2 h-4 w-4" aria-hidden="true" />
        Exporter toutes mes données
      </Button>

      <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
        <DialogContent>
          {etape === 1 ? (
            <>
              <DialogHeader>
                <DialogTitle>Exporter mes données — étape 1/2</DialogTitle>
                <DialogDescription>
                  Choisissez les jeux de données à inclure dans l’archive ZIP. Tout est
                  coché par défaut ; décocher un jeu réduit la taille du fichier (ex.
                  exclure les documents volumineux pour ne garder que les CSV).
                </DialogDescription>
              </DialogHeader>
              {datasets === null ? (
                <div className="flex justify-center py-6"><Spinner /></div>
              ) : (
                <ul className="flex max-h-72 flex-col gap-2 overflow-y-auto py-2">
                  {datasets.map((d) => (
                    <li key={d.name}>
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={selectionnes.has(d.name)}
                          onCheckedChange={() => basculerDataset(d.name)}
                        />
                        {d.label || d.name}
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setWizardOpen(false)}>Annuler</Button>
                <Button
                  onClick={() => setEtape(2)}
                  disabled={!datasets || selectionnes.size === 0}
                >
                  Suivant
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Exporter mes données — étape 2/2</DialogTitle>
                <DialogDescription>
                  {selectionnes.size} jeu{selectionnes.size > 1 ? 'x' : ''} de données
                  sélectionné{selectionnes.size > 1 ? 's' : ''} sur {datasets?.length ?? 0}.
                  L’archive ZIP sera préparée en arrière-plan (le délai dépend du nombre de
                  jeux de données et du volume de votre société) ; vous serez notifié dès
                  qu’elle sera prête, le lien de téléchargement expire au bout de 7 jours.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setEtape(1)} disabled={lancement}>
                  Retour
                </Button>
                <Button onClick={lancerExport} disabled={lancement}>
                  {lancement ? <Spinner className="mr-2 h-4 w-4" /> : null}
                  Lancer l'export
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

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
