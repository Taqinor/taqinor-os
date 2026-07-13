import { useEffect, useMemo, useState } from 'react'
import {
  Card, Badge, Checkbox, Button, Segmented, EmptyState, Input, Label,
} from '../../ui'
import { ListShell } from '../../ui/module'
import installationsApi from '../../api/installationsApi'
import { formatDate, formatNumber } from '../../lib/format'
import useStockFlags from '../parametres/useStockFlags'
import useMagasinResource from './useMagasinResource'
import { colisProgress } from './magasin'
import { ColisStatutPill } from './statusPills'

/* ============================================================================
   XSTK1 — Colisage (`/magasin/colisage`).
   ----------------------------------------------------------------------------
   Étape colisage (FG322) : après le prélèvement, les articles sont emballés
   dans un `Colis` — contenu (`ColisLigne`) contrôlé ligne par ligne puis le
   colis passe contrôlé → expédié. Aucun coût/prix d'achat ici (le serializer
   `ColisLigneSerializer` n'expose que produit/désignation/quantité/contrôle).
   ========================================================================== */

const STATUT_FILTERS = [
  { value: '', label: 'Tous statuts' },
  { value: 'preparation', label: 'En préparation' },
  { value: 'controle', label: 'Contrôlé' },
  { value: 'expedie', label: 'Expédié' },
]

function ColisDetail({ colis, onClose, onChanged }) {
  const [lignes, setLignes] = useState(colis.lignes || [])
  const [busyLigneId, setBusyLigneId] = useState(null)
  const [designation, setDesignation] = useState('')
  const [quantite, setQuantite] = useState('')
  // XSTK1 — `ColisDetail` n'est pas remonté (pas de `key`) quand `selected`
  // change de colis : on resynchronise `lignes` PENDANT le rendu (au lieu
  // d'un effect qui déclenche un second rendu en cascade) en comparant le
  // colis affiché au colis reçu — pattern recommandé par React pour "ajuster
  // un state quand une prop change".
  const [prevColis, setPrevColis] = useState(colis)
  if (prevColis !== colis) {
    setPrevColis(colis)
    setLignes(colis.lignes || [])
  }

  const progress = colisProgress(lignes)

  const toggleControle = async (ligne) => {
    setBusyLigneId(ligne.id)
    try {
      const res = await installationsApi.updateColisLigne(ligne.id, {
        controle_ok: !ligne.controle_ok,
      })
      setLignes((prev) => prev.map((l) => (l.id === ligne.id ? res.data : l)))
    } finally {
      setBusyLigneId(null)
    }
  }

  const ajouterLigne = async (e) => {
    e.preventDefault()
    const qte = Number(quantite)
    if (!designation.trim() || !qte) return
    const res = await installationsApi.createColisLigne({
      colis: colis.id,
      designation: designation.trim(),
      quantite: qte,
    })
    setLignes((prev) => [...prev, res.data])
    setDesignation('')
    setQuantite('')
  }

  const controler = async () => {
    await installationsApi.controlerColis(colis.id)
    onChanged?.()
  }
  const expedier = async () => {
    await installationsApi.expedierColis(colis.id)
    onChanged?.()
  }

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-base font-semibold tracking-tight">
            {colis.reference}
          </h3>
          <p className="text-sm text-muted-foreground">
            {progress.done}/{progress.total} ligne(s) contrôlée(s) ({progress.pct}%)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ColisStatutPill status={colis.statut} />
          {colis.statut === 'preparation' && (
            <Button size="sm" onClick={controler}>Contrôler</Button>
          )}
          {colis.statut === 'controle' && (
            <Button size="sm" onClick={expedier}>Expédier</Button>
          )}
          <Button size="sm" variant="outline" onClick={onClose}>Fermer</Button>
        </div>
      </div>

      {lignes.length === 0 ? (
        <EmptyState title="Colis vide" description="Aucun article n'est encore emballé dans ce colis." />
      ) : (
        <ul className="mb-3 flex flex-col divide-y divide-border">
          {lignes.map((ligne) => (
            <li key={ligne.id} className="flex items-center gap-3 py-2">
              <Checkbox
                checked={Boolean(ligne.controle_ok)}
                disabled={busyLigneId === ligne.id}
                onCheckedChange={() => toggleControle(ligne)}
                aria-label={`Contrôlé : ${ligne.designation || ligne.produit_nom || ''}`}
              />
              <span className="flex-1 text-sm">
                {ligne.produit_nom || ligne.designation || `Produit ${ligne.produit}`}
              </span>
              <span className="text-sm text-muted-foreground">× {ligne.quantite}</span>
            </li>
          ))}
        </ul>
      )}

      {colis.statut === 'preparation' && (
        <form onSubmit={ajouterLigne} noValidate className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="colis-designation">Désignation</Label>
            <Input
              id="colis-designation"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              placeholder="Article à emballer"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="colis-quantite">Quantité</Label>
            <Input
              id="colis-quantite"
              type="number"
              step="any"
              value={quantite}
              onChange={(e) => setQuantite(e.target.value)}
              className="w-24"
            />
          </div>
          <Button type="submit" size="sm">Ajouter</Button>
        </form>
      )}
    </Card>
  )
}

export default function ColisageScreen() {
  // ZSTK13 — capacité colisage : True par défaut = comportement inchangé.
  const { stock_colisage_actif: colisageActif } = useStockFlags()
  const [statut, setStatut] = useState('')
  const [selected, setSelected] = useState(null)

  const params = useMemo(() => (statut ? { statut } : {}), [statut])

  const { data, loading, error, reload } = useMagasinResource(
    installationsApi.getColisList, params, [statut],
  )

  useEffect(() => {
    if (!selected) return
    const fresh = data.find((c) => c.id === selected.id)
    // XSTK1 — resynchronise le colis ouvert après un `reload()` de la liste
    // (ex: changement de statut ailleurs). `data` vient de la liste (léger,
    // externe) alors que `selected` vient de `getColis` (détail complet avec
    // `lignes`) : un vrai refactor "render-time" perdrait les `lignes` déjà
    // chargées, donc on garde l'effect + un disable ciblé plutôt que de
    // changer ce comportement.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (fresh) setSelected(fresh)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const openDetail = async (row) => {
    const res = await installationsApi.getColis(row.id)
    setSelected(res.data)
  }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', width: 160, accessor: (r) => r.reference, cell: (v) => <span className="font-mono">{v}</span> },
    {
      id: 'installation',
      header: 'Chantier',
      width: 220,
      accessor: (r) => r.installation_nom || r.installation,
      cell: (v) => v || '—',
    },
    {
      id: 'lignes',
      header: 'Articles',
      align: 'right',
      width: 90,
      accessor: (r) => (Array.isArray(r.lignes) ? r.lignes.length : 0),
      cell: (v) => <Badge tone="neutral">{v}</Badge>,
    },
    {
      id: 'poids_kg',
      header: 'Poids',
      align: 'right',
      numeric: true,
      width: 100,
      accessor: (r) => Number(r.poids_kg ?? 0),
      cell: (v) => (v ? `${formatNumber(v, { decimals: 2 })} kg` : '—'),
    },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut, cell: (v) => <ColisStatutPill status={v} /> },
    { id: 'date_creation', header: 'Créé le', width: 120, accessor: (r) => r.date_creation, cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const filters = (
    <Segmented options={STATUT_FILTERS} value={statut} onChange={setStatut} aria-label="Filtrer par statut" />
  )

  // ZSTK13 — écran désactivé pour cette société (Paramètres → Stock) : les
  // colis existants ne sont ni supprimés ni modifiés, seul l'affichage est
  // masqué (réversible).
  if (!colisageActif) {
    return (
      <div className="page flex flex-col gap-4">
        <EmptyState
          title="Colisage désactivé"
          description="Cette capacité est désactivée pour votre société (Paramètres → Stock)."
        />
      </div>
    )
  }

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Colisage"
        subtitle="Préparation & contrôle des colis avant expédition vers le chantier."
        filters={filters}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        onRowClick={openDetail}
        exportName="colis"
        emptyTitle="Aucun colis"
        emptyDescription="Aucun colis de préparation pour ce filtre."
      />

      {selected && (
        <ColisDetail
          colis={selected}
          onClose={() => setSelected(null)}
          onChanged={reload}
        />
      )}
    </div>
  )
}
