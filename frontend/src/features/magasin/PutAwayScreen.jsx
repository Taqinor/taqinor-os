import { useMemo, useState } from 'react'
import {
  Segmented, Button, Combobox,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../ui'
import { ListShell } from '../../ui/module'
import installationsApi from '../../api/installationsApi'
import { formatDate, formatNumber } from '../../lib/format'
import useMagasinResource from './useMagasinResource'
import { PutAwayStatutPill } from './statusPills'

/* ============================================================================
   XSTK1 — Rangement guidé / put-away (`/magasin/rangement`).
   ----------------------------------------------------------------------------
   Liste des opérations de put-away (FG320) : à la confirmation d'une
   réception, le backend suggère un casier (`bin_suggere`) ; le magasinier
   confirme (éventuellement vers un autre casier) via l'action `ranger`.

   EZ11 — LE CASIER EFFECTIF REDEVENAIT FAUX EN SILENCE. L'écran appelait
   `rangerPutAway(row.id)` SANS casier, alors que TOUT existait déjà :
   `installationsApi.rangerPutAway(id, binId)` envoie `{bin}`,
   `PutAwayViewSet.ranger` valide un `bin` optionnel borné société et pose
   `bin_effectif`, et `getBinLocations` liste les casiers — le paramètre
   n'avait simplement jamais été branché (la docstring de l'écran promettait
   pourtant « éventuellement vers un autre casier »). Ranger ailleurs
   enregistrait donc le casier SUGGÉRÉ, pas le vrai. 100 % frontend.

   Le chemin par défaut reste À UN TAP : « Ranger » confirme le casier
   suggéré, exactement comme avant ; « Ranger ailleurs… » est l'action
   supplémentaire, pas un détour imposé.
   ========================================================================== */

const STATUT_FILTERS = [
  { value: '', label: 'Tous statuts' },
  { value: 'a_ranger', label: 'À ranger' },
  { value: 'range', label: 'Rangé' },
]

export default function PutAwayScreen() {
  const [statut, setStatut] = useState('a_ranger')
  const [busyId, setBusyId] = useState(null)
  const [feedback, setFeedback] = useState(null)

  const params = useMemo(() => (statut ? { statut } : {}), [statut])

  const { data, loading, error, reload, setData } = useMagasinResource(
    installationsApi.getPutAways, params, [statut],
  )

  // `binId` absent = casier SUGGÉRÉ (le serveur retombe dessus) : le chemin
  // par défaut est strictement inchangé.
  const ranger = async (row, binId) => {
    setBusyId(row.id)
    setFeedback(null)
    try {
      const res = await installationsApi.rangerPutAway(row.id, binId)
      setData((prev) => prev.map((r) => (r.id === row.id ? res.data : r)))
      const casier = res.data?.bin_effectif_code
      setFeedback({
        tone: 'success',
        message: `Rangement confirmé pour ${row.produit_nom || 'ce produit'}`
          + (casier ? ` — casier ${casier}.` : '.'),
      })
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err?.response?.data?.bin || err?.response?.data?.detail || 'Rangement impossible.',
      })
    } finally {
      setBusyId(null)
      reload()
    }
  }

  // EZ11 — choix explicite du casier effectif. `getBinLocations` est déjà
  // exposée et bornée société côté serveur : aucun endpoint nouveau.
  const [choixCasier, setChoixCasier] = useState(null) // { row }
  const [binChoisi, setBinChoisi] = useState(null)
  const [bins, setBins] = useState([])
  const ouvrirChoixCasier = (row) => {
    setChoixCasier({ row })
    // Le casier suggéré est PRÉ-CHOISI : confirmer sans rien changer donne
    // exactement le même résultat qu'avant.
    setBinChoisi(row.bin_suggere ? String(row.bin_suggere) : null)
    installationsApi.getBinLocations({ archived: '0' })
      .then((res) => setBins(res.data?.results ?? res.data ?? []))
      .catch(() => setBins([]))
  }
  const confirmerCasier = async () => {
    const row = choixCasier?.row
    setChoixCasier(null)
    if (row) await ranger(row, binChoisi ? Number(binChoisi) : undefined)
  }

  const columns = useMemo(() => [
    {
      id: 'produit',
      header: 'Produit',
      width: 220,
      accessor: (r) => r.produit_nom || `Produit ${r.produit}`,
      cell: (v) => v || '—',
    },
    {
      id: 'quantite',
      header: 'Qté',
      align: 'right',
      numeric: true,
      width: 90,
      accessor: (r) => Number(r.quantite ?? 0),
      cell: (v) => formatNumber(v),
    },
    {
      id: 'bin_suggere',
      header: 'Casier suggéré',
      width: 150,
      accessor: (r) => r.bin_suggere_code,
      cell: (v) => (v ? <span className="font-mono">{v}</span> : '—'),
    },
    {
      id: 'bin_effectif',
      header: 'Casier effectif',
      width: 150,
      accessor: (r) => r.bin_effectif_code,
      cell: (v) => (v ? <span className="font-mono">{v}</span> : '—'),
    },
    {
      id: 'reference_reception',
      header: 'Réception',
      width: 150,
      accessor: (r) => r.reference_reception,
      cell: (v) => v || '—',
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (r) => r.statut,
      cell: (v) => <PutAwayStatutPill status={v} />,
    },
    {
      id: 'date_creation',
      header: 'Créé le',
      width: 120,
      accessor: (r) => r.date_creation,
      cell: (v) => (v ? formatDate(v) : '—'),
    },
  ], [])

  const rowActions = useMemo(() => (row) => {
    if (row.statut !== 'a_ranger') return []
    return [
      {
        // Chemin par défaut : UN tap, casier suggéré (inchangé).
        id: 'ranger',
        label: busyId === row.id ? 'Rangement…' : 'Ranger',
        onClick: () => ranger(row),
      },
      {
        // EZ11 — ranger AILLEURS enregistre enfin le casier réel.
        id: 'ranger-ailleurs',
        label: 'Ranger ailleurs…',
        onClick: () => ouvrirChoixCasier(row),
      },
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busyId])

  const filters = (
    <Segmented options={STATUT_FILTERS} value={statut} onChange={setStatut} aria-label="Filtrer par statut" />
  )

  return (
    <div className="page flex flex-col gap-3">
      {feedback && (
        <p
          role="status"
          className={feedback.tone === 'error' ? 'text-sm text-destructive' : 'text-sm text-success'}
        >
          {feedback.message}
        </p>
      )}
      <ListShell
        title="Rangement guidé (put-away)"
        subtitle="Suggestion de casier à la réception — confirmer le rangement effectif."
        filters={filters}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="putaways"
        emptyTitle="Aucun rangement"
        emptyDescription="Aucune opération de rangement pour ce filtre."
      />
      {/* EZ11 — le casier EFFECTIF, enfin enregistré pour de vrai. */}
      <Dialog open={!!choixCasier} onOpenChange={(o) => { if (!o) setChoixCasier(null) }}>
        <DialogContent data-testid="putaway-casier-dialog">
          <DialogHeader>
            <DialogTitle>Ranger — casier effectif</DialogTitle>
            <DialogDescription>
              Le casier suggéré est pré-choisi. Changez-le seulement si le
              produit part ailleurs — c'est CE casier qui sera enregistré.
            </DialogDescription>
          </DialogHeader>
          <Combobox
            id="putaway-bin"
            options={bins.map((b) => ({
              value: String(b.id),
              label: b.code || `Casier ${b.id}`,
              description: b.zone_nom || b.zone || undefined,
            }))}
            value={binChoisi}
            onChange={setBinChoisi}
            placeholder="— Choisir un casier —"
            searchPlaceholder="Code ou zone…"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setChoixCasier(null)}>Annuler</Button>
            <Button onClick={confirmerCasier} data-testid="putaway-casier-confirmer">
              Confirmer le rangement
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
