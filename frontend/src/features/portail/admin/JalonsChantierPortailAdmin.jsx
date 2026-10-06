// PACT100 — Jalons de chantier (portail). `apps.portail.JalonChantierPortail`
// trace une timeline de jalons par chantier (étude → commande → livraison →
// installation → mise en service → réception), vue par le client.
// ADOC129 (D-ADOC-3) — la timeline client a UNE source : les jalons
// SYNCHRONISÉS du chantier (CHT11, `upsert_jalon_chantier`). Cet écran ne
// CRÉE plus de jalon (le serveur répond 405) : il CORRIGE un jalon existant
// (libellé, date, atteint — correction tracée au Journal côté serveur) et ne
// supprime que les jalons HÉRITÉS sans clé de phase (409 sinon).
import { useEffect, useState } from 'react'
import { Check, Milestone, Pencil, Trash2, Undo2, X } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'
import {
  Button, Card, EmptyState, Skeleton, StatusPill, Input, Switch, DataTable, toast,
} from '../../../ui'

const formatDate = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')

const toutesLesLignes = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

export default function JalonsChantierPortailAdmin() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [edit, setEdit] = useState(null) // { id, libelle, date_jalon, atteint }

  // ADOC32 — toutes les pages de l'enveloppe DRF, jamais la seule page 1.
  const fetchJalons = () => fetchAllPages(
    (page) => portailApi.admin.jalonsChantier.liste({ page }).then((r) => r.data),
  )
    .then((data) => setRows(toutesLesLignes(data)))
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return fetchJalons()
  }

  useEffect(() => { fetchJalons() }, [])

  const agir = async (row, appel, succes, echec) => {
    setBusyId(row.id)
    try {
      await appel()
      toast.success(succes)
      load()
      return true
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? echec)
      return false
    } finally {
      setBusyId(null)
    }
  }

  const marquerAtteint = (row) => agir(
    row, () => portailApi.admin.jalonsChantier.marquerAtteint(row.id),
    'Jalon marqué atteint', 'Marquage impossible.')

  const marquerNonAtteint = (row) => agir(
    row, () => portailApi.admin.jalonsChantier.marquerNonAtteint(row.id),
    'Jalon marqué non atteint', 'Marquage impossible.')

  const supprimer = (row) => agir(
    row, () => portailApi.admin.jalonsChantier.supprimer(row.id),
    'Jalon hérité supprimé', 'Suppression impossible.')

  const enregistrer = async (row) => {
    if (!edit?.libelle?.trim()) return
    const ok = await agir(
      row, () => portailApi.admin.jalonsChantier.patch(row.id, {
        libelle: edit.libelle.trim(),
        date_jalon: edit.date_jalon || null,
        atteint: !!edit.atteint,
      }),
      'Jalon corrigé', 'Correction impossible.')
    if (ok) setEdit(null)
  }

  const enEdition = (row) => edit?.id === row.id

  const columns = [
    { id: 'chantier', header: 'Chantier', width: 110, accessor: (r) => (r.chantier_id ? `#${r.chantier_id}` : '—') },
    {
      id: 'libelle', header: 'Jalon', width: 200, accessor: (r) => r.libelle,
      cell: (_v, row) => (enEdition(row) ? (
        <Input aria-label={`Libellé du jalon ${row.libelle}`} className="h-8" value={edit.libelle}
               onChange={(e) => setEdit((s) => ({ ...s, libelle: e.target.value }))} />
      ) : row.libelle),
    },
    { id: 'ordre', header: 'Ordre', width: 70, accessor: (r) => r.ordre },
    {
      id: 'atteint', header: 'Statut', width: 130, sortable: false,
      cell: (_v, row) => (enEdition(row) ? (
        <Switch checked={!!edit.atteint} aria-label={`Atteint — ${row.libelle}`}
                onCheckedChange={(v) => setEdit((s) => ({ ...s, atteint: v }))} />
      ) : (
        <StatusPill tone={row.atteint ? 'success' : 'neutral'}
                    label={row.atteint ? 'Atteint' : 'Non atteint'} />
      )),
      exportValue: (row) => (row.atteint ? 'Atteint' : 'Non atteint'),
    },
    {
      id: 'date_jalon', header: 'Date du jalon', width: 150, accessor: (r) => formatDate(r.date_jalon),
      cell: (_v, row) => (enEdition(row) ? (
        <Input type="date" aria-label={`Date du jalon ${row.libelle}`} className="h-8"
               value={edit.date_jalon || ''}
               onChange={(e) => setEdit((s) => ({ ...s, date_jalon: e.target.value }))} />
      ) : formatDate(row.date_jalon)),
    },
    {
      id: 'origine', header: 'Origine', width: 110, sortable: false,
      accessor: (r) => (r.cle_phase ? 'Chantier' : 'Hérité'),
    },
    {
      id: 'actions', header: '', width: 320, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => {
        if (enEdition(row)) {
          return (
            <span className="flex items-center gap-1.5">
              <Button size="sm" variant="outline" disabled={busyId === row.id || !edit.libelle?.trim()}
                      onClick={() => enregistrer(row)}>
                <Check /> Enregistrer
              </Button>
              <Button size="sm" variant="ghost" aria-label="Annuler" onClick={() => setEdit(null)}><X /></Button>
            </span>
          )
        }
        return (
          <span className="flex flex-wrap items-center gap-1.5">
            <Button variant="outline" size="sm" disabled={busyId === row.id}
                    onClick={() => setEdit({
                      id: row.id, libelle: row.libelle ?? '', date_jalon: row.date_jalon ?? '', atteint: !!row.atteint,
                    })}>
              <Pencil /> Corriger
            </Button>
            {row.atteint ? (
              <Button variant="ghost" size="sm" disabled={busyId === row.id}
                      onClick={() => marquerNonAtteint(row)}>
                <Undo2 /> Marquer non atteint
              </Button>
            ) : (
              <Button variant="outline" size="sm" disabled={busyId === row.id}
                      onClick={() => marquerAtteint(row)}>
                <Check /> Marquer atteint
              </Button>
            )}
            {!row.cle_phase && (
              <Button variant="ghost" size="sm" disabled={busyId === row.id}
                      onClick={() => supprimer(row)}>
                <Trash2 /> Supprimer
              </Button>
            )}
          </span>
        )
      },
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Timeline d'avancement vue par le client, synchronisée depuis le
        chantier. Les jalons ne se créent pas ici : « Corriger » rectifie un
        libellé, une date ou le statut (correction tracée au Journal) ;
        seuls les jalons hérités, saisis à la main avant la synchronisation,
        peuvent être supprimés.
      </p>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les jalons n'ont pas pu être chargés. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState icon={Milestone} title="Aucun jalon"
                    description="Les jalons apparaissent ici dès que le chantier avance." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="jalons-chantier-portail"
                   emptyTitle="Aucun jalon" />
      )}
    </div>
  )
}
