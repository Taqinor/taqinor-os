import { useEffect, useRef, useState } from 'react'
import { Network, Plus, Download, Upload, History } from 'lucide-react'
import entitesApi from './entitesApi'
import AssistantEntite from './AssistantEntite'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Badge, Card, EmptyState, Spinner } from '../../ui'
import { toastError, toastSuccess } from '../../lib/toast'
import { downloadXlsx } from '../../api/importApi'

/* ============================================================================
   NTADM4 — Écran Paramètres → Entités : arbre hiérarchique indenté (liste,
   pas de drag), création/renommage/désactivation sans reload.
   ========================================================================== */

function TreeNode({ node, depth, onRename, onDesactiver, onHistory }) {
  return (
    <>
      <div
        className="flex items-center justify-between border-b py-2"
        style={{ paddingLeft: `${depth * 24 + 8}px` }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">{node.code}</span>
          <span>{node.nom}</span>
          {!node.actif && <Badge variant="outline">Inactive</Badge>}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={() => onHistory(node)}>
            <History size={14} /> Historique
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onRename(node)}>
            Renommer
          </Button>
          {node.actif && (
            <Button size="sm" variant="ghost" onClick={() => onDesactiver(node)}>
              Désactiver
            </Button>
          )}
        </div>
      </div>
      {node.enfants?.map((child) => (
        <TreeNode
          key={child.id}
          node={child}
          depth={depth + 1}
          onRename={onRename}
          onDesactiver={onDesactiver}
          onHistory={onHistory}
        />
      ))}
    </>
  )
}

function HistoriquePanel({ entite, onClose }) {
  const [entries, setEntries] = useState(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    entitesApi.historique(entite.id)
      .then((res) => setEntries(Array.isArray(res.data) ? res.data : []))
      .catch(() => { setEntries([]); toastError("Impossible de charger l'historique.") })
  }

  useEffect(load, [entite.id])

  const submitNote = async () => {
    if (!note.trim()) return
    setBusy(true)
    try {
      await entitesApi.noter(entite.id, note.trim())
      setNote('')
      toastSuccess('Note ajoutée.')
      load()
    } catch {
      toastError("La note n'a pas pu être ajoutée.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="mt-4 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-medium">Historique — {entite.nom}</h3>
        <Button size="sm" variant="ghost" onClick={onClose}>Fermer</Button>
      </div>
      <div className="mb-3 flex gap-2">
        <input
          className="form-control flex-1"
          aria-label="Ajouter une note"
          placeholder="Ajouter une note…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <Button size="sm" disabled={busy || !note.trim()} onClick={submitNote}>
          Noter
        </Button>
      </div>
      {entries === null ? (
        <Spinner />
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune activité pour le moment.</p>
      ) : (
        <ul className="space-y-2">
          {entries.map((a) => (
            <li key={a.id} className="border-b py-1 text-sm">
              <span className="text-muted-foreground">
                {a.created_by || 'système'} · {a.kind}
              </span>
              <div>
                {a.body || (a.field_label
                  ? `${a.field_label} : ${a.old_value ?? ''} → ${a.new_value ?? ''}`
                  : '')}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function EntitesPage() {
  const [tree, setTree] = useState([])
  const [flat, setFlat] = useState([])
  const [loading, setLoading] = useState(true)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [historyNode, setHistoryNode] = useState(null)
  const fileInputRef = useRef(null)

  const load = () => {
    setLoading(true)
    Promise.all([entitesApi.tree(), entitesApi.list()])
      .then(([treeRes, listRes]) => {
        setTree(Array.isArray(treeRes.data) ? treeRes.data : [])
        setFlat(listRes.data?.results ?? listRes.data ?? [])
      })
      .catch(() => toastError('Impossible de charger les entités.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(load, [])

  const handleRename = async (node) => {
    const nom = window.prompt('Nouveau nom :', node.nom)
    if (!nom || nom === node.nom) return
    try {
      await entitesApi.update(node.id, { nom })
      toastSuccess('Entité renommée.')
      load()
    } catch {
      toastError('Renommage impossible.')
    }
  }

  const handleDesactiver = async (node) => {
    if (!window.confirm(`Désactiver l'entité « ${node.nom} » ?`)) return
    try {
      await entitesApi.desactiver(node.id)
      toastSuccess('Entité désactivée.')
      load()
    } catch {
      toastError('Désactivation impossible.')
    }
  }

  const handleExport = async () => {
    try {
      const res = await entitesApi.export()
      downloadXlsx(res.data, 'entites.xlsx')
    } catch {
      toastError("L'export a échoué.")
    }
  }

  const handleImportFile = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = '' // permet de re-sélectionner le même fichier
    if (!file) return
    try {
      const dry = await entitesApi.importer(file, false)
      const { crees = 0, mis_a_jour = 0, erreurs = [] } = dry.data ?? {}
      const resume = `Import : ${crees} création(s), ${mis_a_jour} mise(s) à jour`
        + (erreurs.length ? `, ${erreurs.length} erreur(s)` : '')
        + '. Confirmer l\'import ?'
      if (!window.confirm(resume)) return
      await entitesApi.importer(file, true)
      toastSuccess('Import effectué.')
      load()
    } catch {
      toastError("L'import a échoué (format CSV attendu : code, nom, code_parent).")
    }
  }

  return (
    <div>
      <PageHeader
        title="Entités"
        subtitle="Structure organisationnelle (holding, filiales, agences)"
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleExport}>
              <Download size={16} /> Exporter
            </Button>
            <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
              <Upload size={16} /> Importer
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              aria-label="Importer un fichier CSV d'entités"
              onChange={handleImportFile}
            />
            <Button onClick={() => setAssistantOpen(true)}>
              <Plus size={16} /> Ajouter une entité
            </Button>
          </div>
        }
      />
      <Card className="mt-4 p-4">
        {loading ? (
          <Spinner />
        ) : tree.length === 0 ? (
          <EmptyState
            icon={Network}
            title="Aucune entité"
            description="Créez votre première entité pour structurer votre organisation."
          />
        ) : (
          tree.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              depth={0}
              onRename={handleRename}
              onDesactiver={handleDesactiver}
              onHistory={setHistoryNode}
            />
          ))
        )}
      </Card>
      {historyNode && (
        <HistoriquePanel
          entite={historyNode}
          onClose={() => setHistoryNode(null)}
        />
      )}
      <AssistantEntite
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        entites={flat}
        onCreated={() => {
          setAssistantOpen(false)
          load()
        }}
      />
    </div>
  )
}
