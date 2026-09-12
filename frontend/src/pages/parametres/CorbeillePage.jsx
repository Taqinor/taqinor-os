// NTUX7 — Corbeille transverse 30 jours : écran /parametres/corbeille
// (Directeur/Admin, reflète `IsAdminOrResponsableTier` côté serveur — backend
// `apps/trash` déjà complet : modèle, restauration par registre, purge
// planifiée NTUX29). Cet écran est la MOITIÉ FRONTEND qui manquait.
import { useCallback, useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import trashApi from '../../api/trashApi'
import {
  Card, CardContent, Button, Input, Label, EmptyState, Spinner, Badge, Switch,
} from '../../ui'
import { useConfirmDialog, toast } from '../../ui/confirm'
// VX75 — tout horodatage passe par lib/format.js (jamais un toLocaleString nu).
import { formatDateTime } from '../../lib/format'

const FILTRES_VIDES = { type: '', depuis: '', jusqua: '' }
const PAGE_SIZE = 50

export default function CorbeillePage() {
  const { confirm } = useConfirmDialog()
  // `saisie` = ce que l'utilisateur tape ; `filtres` = ce qui a été appliqué —
  // sans cette séparation, chaque frappe déclencherait une requête (patron
  // PiecesJointesPage.jsx, WIR270).
  const [saisie, setSaisie] = useState(FILTRES_VIDES)
  const [filtres, setFiltres] = useState(FILTRES_VIDES)
  // NTUX24 (round 2) réutilisera ce même toggle pour le journal d'audit
  // exportable — posé ici pour ne pas dupliquer le filtre serveur `?restaures=`.
  const [inclureRestaures, setInclureRestaures] = useState(false)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)
  const [restaurationEnCours, setRestaurationEnCours] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setErreur(null)
    const params = { page }
    if (filtres.type) params.type = filtres.type
    if (filtres.depuis) params.depuis = filtres.depuis
    if (filtres.jusqua) params.jusqua = filtres.jusqua
    if (inclureRestaures) params.restaures = 1

    trashApi.listCorbeille(params)
      .then((r) => {
        const data = r.data ?? {}
        setItems(Array.isArray(data) ? data : (data.results ?? []))
        setTotal(Array.isArray(data) ? data.length : (data.count ?? 0))
      })
      .catch(() => setErreur('Corbeille indisponible.'))
      .finally(() => setLoading(false))
  }, [filtres, inclureRestaures, page])

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

  const restaurer = async (element) => {
    const ok = await confirm({
      title: `Restaurer « ${element.libelle_snapshot || element.type_libelle} » ?`,
      description: 'L\'élément redevient actif dans son écran d\'origine.',
      confirmLabel: 'Restaurer',
    })
    if (!ok) return
    setRestaurationEnCours(element.id)
    trashApi.restaurer(element.id)
      .then((res) => {
        toast.success('Élément restauré.')
        // Met à jour la ligne EN PLACE (restaure_le posé) plutôt que de
        // recharger toute la page — l'élément reste visible (audit) si
        // « Inclure les éléments restaurés » est actif, sinon `charger()`
        // le retirerait de toute façon au prochain rechargement.
        const restaure = res.data?.element
        setItems((prev) => prev.map((it) => (
          it.id === element.id ? { ...it, ...(restaure || { restaure_le: new Date().toISOString() }) } : it
        )))
        // NE PAS recharger ici : ça écraserait l'affichage « Restauré » qu'on
        // vient de poser en place par le filtre serveur (qui exclurait déjà
        // l'élément si « Inclure les éléments restaurés » est décoché). Le
        // prochain rechargement naturel (filtre, pagination, toggle) le
        // retirera de toute façon si besoin.
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail
        toast.error(detail || 'Restauration impossible.')
      })
      .finally(() => setRestaurationEnCours(null))
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="page flex flex-col gap-4">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Trash2 className="size-5" aria-hidden="true" />
          Corbeille
          <Badge tone="neutral">{total}</Badge>
        </h1>
        <p className="page-subtitle">
          Éléments supprimés de toute l'application, conservés 30 jours et
          restaurables à tout moment avant purge automatique.
        </p>
      </div>

      <Card>
        <CardContent className="p-4">
          <form noValidate className="flex flex-wrap items-end gap-2" onSubmit={appliquer}>
            <div className="flex w-40 flex-col gap-1.5">
              <Label htmlFor="cb-type">Type</Label>
              <Input id="cb-type" value={saisie.type} onChange={set('type')} placeholder="Devis, Lead…" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cb-depuis">Supprimé depuis le</Label>
              <Input id="cb-depuis" type="date" value={saisie.depuis} onChange={set('depuis')} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cb-jusqua">Jusqu'au</Label>
              <Input id="cb-jusqua" type="date" value={saisie.jusqua} onChange={set('jusqua')} />
            </div>
            <Button type="submit" size="sm">Filtrer</Button>
            <Button type="button" size="sm" variant="outline" onClick={reinitialiser}>
              Réinitialiser
            </Button>
            <div className="ml-auto flex items-center gap-2">
              <Switch
                id="cb-inclure-restaures"
                checked={inclureRestaures}
                onCheckedChange={(v) => { setPage(1); setInclureRestaures(v) }}
              />
              <Label htmlFor="cb-inclure-restaures" className="text-sm font-normal">
                Inclure les éléments déjà restaurés
              </Label>
            </div>
          </form>
        </CardContent>
      </Card>

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement de la corbeille…
        </p>
      ) : erreur ? (
        <EmptyState title="Corbeille indisponible" description={erreur} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Corbeille vide"
          description="Aucun élément supprimé ne correspond à ces filtres."
          icon={Trash2}
        />
      ) : (
        <>
          <table className="data-table" data-testid="corbeille-table">
            <thead>
              <tr>
                <th>Type</th><th>Libellé</th><th>Supprimé par</th>
                <th>Supprimé le</th><th>Expire le</th><th>Restauré le</th><th />
              </tr>
            </thead>
            <tbody>
              {items.map((el) => (
                <tr key={el.id} data-testid="corbeille-row">
                  <td>{el.type_libelle || '—'}</td>
                  <td>{el.libelle_snapshot || '—'}</td>
                  <td>{el.supprime_par_nom || '—'}</td>
                  <td>{formatDateTime(el.supprime_le)}</td>
                  <td>{formatDateTime(el.expire_le)}</td>
                  <td>{el.restaure_le ? formatDateTime(el.restaure_le) : '—'}</td>
                  <td>
                    {el.restaure_le ? (
                      <Badge tone="success">Restauré</Badge>
                    ) : (
                      <Button
                        type="button" size="sm" variant="outline"
                        loading={restaurationEnCours === el.id}
                        onClick={() => restaurer(el)}
                      >
                        Restaurer
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Button type="button" size="sm" variant="outline"
                    disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Précédent
            </Button>
            <span data-testid="corbeille-pagination">
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
