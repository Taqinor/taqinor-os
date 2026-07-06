import { useEffect, useState } from 'react'
import { Plus, Archive, ArchiveRestore } from 'lucide-react'
import { Button, Input, EmptyState, Skeleton, toast } from '../../ui'

/**
 * Éditeur générique liste simple nom/libellé + archiver/désarchiver, pour les
 * référentiels SAV plats (causes/remèdes de panne XSAV14, catégories de
 * ticket ZSAV2). Cette page n'est montée que sous /sav/parametres (gardée
 * responsable/admin par la route) — l'écriture reste de toute façon gardée
 * responsable/admin côté serveur (403 sinon).
 *
 * `nameField` = clé du libellé ('nom' ou 'libelle').
 * `isArchived(row)` / `archivePayload(row)` / `unarchivePayload(row)` isolent
 * la sémantique du champ d'archivage propre à chaque modèle (`archived` bool
 * pour causes/remèdes, `actif` inversé pour les catégories de ticket) — le
 * composant générique ne suppose jamais un nom de champ fixe.
 * `emptyLabel` = texte complet de l'état vide (accorde le genre de `label`,
 * ex. « Aucune catégorie » vs « Aucun remède ») ; par défaut `Aucun ${label}`.
 */
export default function SimpleRefListEditor({
  loadFn, saveFn, nameField = 'nom', label = 'élément', emptyLabel,
  isArchived, archivePayload, unarchivePayload,
}) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => loadFn()
    .then((r) => setRows(r.data.results ?? r.data ?? []))
    .catch(() => {})
    .finally(() => setLoading(false))

  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const add = async () => {
    const nom = newName.trim()
    if (!nom) return
    setBusy(true)
    try {
      await saveFn(null, { [nameField]: nom })
      setNewName('')
      toast.success(`${label} ajouté(e)`)
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Ajout impossible.')
    } finally { setBusy(false) }
  }

  const toggleArchive = async (row) => {
    try {
      await saveFn(row.id, isArchived(row) ? unarchivePayload(row) : archivePayload(row))
      charger()
    } catch { toast.error('Bascule impossible.') }
  }

  if (loading) return <Skeleton className="h-24 w-full" />

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Input placeholder={`Nouveau ${label}…`} value={newName}
               onChange={(e) => setNewName(e.target.value)}
               onKeyDown={(e) => { if (e.key === 'Enter') add() }} />
        <Button type="button" size="sm" loading={busy} onClick={add}>
          <Plus /> Ajouter
        </Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title={emptyLabel ?? `Aucun ${label}`} />
      ) : (
        <ul className="flex flex-col gap-1.5">
          {rows.map((r) => (
            <li key={r.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm">
              <span>{r[nameField]}</span>
              <Button type="button" size="sm" variant="ghost" onClick={() => toggleArchive(r)}>
                {isArchived(r) ? <><ArchiveRestore /> Réactiver</> : <><Archive /> Archiver</>}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
