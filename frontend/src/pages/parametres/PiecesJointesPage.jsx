import { useCallback, useEffect, useState } from 'react'
import { Paperclip } from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import {
  Card, CardContent, Button, Input, Label, EmptyState, Spinner, Badge,
} from '../../ui'
// VX75 — tout horodatage passe par lib/format.js (jamais un toLocaleString nu).
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR270/FG10 — Centre de pièces jointes de la société.
   ----------------------------------------------------------------------------
   `recordsApi.getAllAttachments` était un export MORT : l'endpoint
   `records/attachments/all/` (company-scopé, paginé à 50, filtres
   mime/mime_like/phase/model/since) n'avait aucun appelant. Ce n'est PAS un
   orphelin à supprimer — c'est la seule vue transverse des fichiers de la
   société, alors que chaque écran ne montre que SES propres pièces jointes.

   Isolation : le serveur scope TOUJOURS à la société du demandeur
   (`_scoped(...)`) — aucun paramètre de société ne part d'ici. Aucune donnée
   de prix n'apparaît : ce sont des métadonnées de fichier.
   ========================================================================== */

const PHASES = [
  { value: '', label: 'Toutes les phases' },
  { value: 'avant', label: 'Avant' },
  { value: 'pendant', label: 'Pendant' },
  { value: 'apres', label: 'Après' },
  { value: '__sans__', label: 'Sans phase' },
]

const FILTRES_VIDES = {
  mime: '', mime_like: '', phase: '', model: '', since: '',
}

const PAGE_SIZE = 50

// Taille lisible — jamais un nombre d'octets brut à l'écran.
function tailleLisible(octets) {
  const n = Number(octets)
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n < 1024) return `${n} o`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} Ko`
  return `${(n / (1024 * 1024)).toFixed(1)} Mo`
}

export default function PiecesJointesPage() {
  // `saisie` = ce que l'utilisateur tape ; `filtres` = ce qui a été appliqué.
  // Sans cette séparation, chaque frappe déclencherait une requête.
  const [saisie, setSaisie] = useState(FILTRES_VIDES)
  const [filtres, setFiltres] = useState(FILTRES_VIDES)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setErreur(null)
    const params = { page }
    if (filtres.mime) params.mime = filtres.mime
    if (filtres.mime_like) params.mime_like = filtres.mime_like
    // `phase=''` est un filtre VALIDE côté serveur (pièces sans phase) : on ne
    // l'envoie que via le choix explicite « Sans phase ».
    if (filtres.phase === '__sans__') params.phase = ''
    else if (filtres.phase) params.phase = filtres.phase
    if (filtres.model) params.model = filtres.model
    if (filtres.since) params.since = filtres.since

    recordsApi.getAllAttachments(params)
      .then((r) => {
        const data = r.data ?? {}
        setItems(Array.isArray(data) ? data : (data.results ?? []))
        setTotal(Array.isArray(data) ? data.length : (data.count ?? 0))
      })
      .catch(() => setErreur('Pièces jointes indisponibles.'))
      .finally(() => setLoading(false))
  }, [filtres, page])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage / au changement de filtre
    charger()
  }, [charger])

  const appliquer = (e) => {
    e.preventDefault()
    setPage(1)
    setFiltres(saisie)
  }

  const reinitialiser = () => {
    setPage(1)
    setSaisie(FILTRES_VIDES)
    setFiltres(FILTRES_VIDES)
  }

  const set = (cle) => (e) => setSaisie((p) => ({ ...p, [cle]: e.target.value }))
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="page flex flex-col gap-4">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Paperclip className="size-5" aria-hidden="true" />
          Pièces jointes
          <Badge tone="neutral">{total}</Badge>
        </h1>
        <p className="page-subtitle">
          Tous les fichiers de la société, du plus récent au plus ancien.
          Filtrez par type, phase, objet lié ou date.
        </p>
      </div>

      <Card>
        <CardContent className="p-4">
          <form noValidate className="flex flex-wrap items-end gap-2" onSubmit={appliquer}>
            <div className="flex w-40 flex-col gap-1.5">
              <Label htmlFor="pj-mime">Type MIME exact</Label>
              <Input id="pj-mime" value={saisie.mime} onChange={set('mime')}
                     placeholder="application/pdf" />
            </div>
            <div className="flex w-36 flex-col gap-1.5">
              <Label htmlFor="pj-mime-like">Type contient</Label>
              <Input id="pj-mime-like" value={saisie.mime_like} onChange={set('mime_like')}
                     placeholder="image" />
            </div>
            <div className="flex w-40 flex-col gap-1.5">
              <Label htmlFor="pj-phase">Phase</Label>
              <select id="pj-phase" className="form-control" value={saisie.phase}
                      onChange={set('phase')}>
                {PHASES.map((p) => (
                  <option key={p.value || 'toutes'} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div className="flex w-40 flex-col gap-1.5">
              <Label htmlFor="pj-model">Objet lié</Label>
              <Input id="pj-model" value={saisie.model} onChange={set('model')}
                     placeholder="crm.lead" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pj-since">Depuis le</Label>
              <Input id="pj-since" type="date" value={saisie.since} onChange={set('since')} />
            </div>
            <Button type="submit" size="sm">Filtrer</Button>
            <Button type="button" size="sm" variant="outline" onClick={reinitialiser}>
              Réinitialiser
            </Button>
          </form>
        </CardContent>
      </Card>

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement des pièces jointes…
        </p>
      ) : erreur ? (
        <EmptyState title="Pièces jointes indisponibles" description={erreur} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Aucune pièce jointe"
          description="Aucun fichier ne correspond à ces filtres."
          icon={Paperclip}
        />
      ) : (
        <>
          <table className="data-table" data-testid="pieces-jointes-table">
            <thead>
              <tr>
                <th>Fichier</th><th>Type</th><th>Taille</th><th>Phase</th>
                <th>Déposé par</th><th>Le</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} data-testid="piece-jointe-row">
                  <td>
                    <a href={a.url} target="_blank" rel="noreferrer">{a.filename}</a>
                  </td>
                  <td>{a.mime || '—'}</td>
                  <td>{tailleLisible(a.size)}</td>
                  <td>{a.phase || '—'}</td>
                  <td>{a.uploaded_by_nom || '—'}</td>
                  <td>{formatDateTime(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Button type="button" size="sm" variant="outline"
                    disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Précédent
            </Button>
            <span data-testid="pieces-jointes-pagination">
              Page {page} / {pages}
            </span>
            <Button type="button" size="sm" variant="outline"
                    disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
              Suivant
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
