import { useEffect, useState } from 'react'
import { Network, Plus } from 'lucide-react'
import entitesApi from './entitesApi'
import AssistantEntite from './AssistantEntite'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Badge, Card, EmptyState, Spinner } from '../../ui'
import { toastError, toastSuccess } from '../../lib/toast'

/* ============================================================================
   NTADM4 — Écran Paramètres → Entités : arbre hiérarchique indenté (liste,
   pas de drag), création/renommage/désactivation sans reload.
   ========================================================================== */

function TreeNode({ node, depth, onRename, onDesactiver }) {
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
        />
      ))}
    </>
  )
}

export default function EntitesPage() {
  const [tree, setTree] = useState([])
  const [flat, setFlat] = useState([])
  const [loading, setLoading] = useState(true)
  const [assistantOpen, setAssistantOpen] = useState(false)

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

  return (
    <div>
      <PageHeader
        title="Entités"
        subtitle="Structure organisationnelle (holding, filiales, agences)"
        actions={
          <Button onClick={() => setAssistantOpen(true)}>
            <Plus size={16} /> Ajouter une entité
          </Button>
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
            />
          ))
        )}
      </Card>
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
