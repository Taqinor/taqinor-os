import { useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, FileText } from 'lucide-react'
import { Card, Spinner } from '../../ui'
import { cn } from '../../lib/cn'
import kbApi from '../../api/kbApi'

/* ============================================================================
   XKB8 — Arbre des articles (parent/ordre). Panneau replié par défaut, ouvert
   à la demande (aucun impact sur les écrans qui n'utilisent pas encore la
   hiérarchie). Un clic sur un nœud ouvre le détail de l'article via
   ``onSelect``. Lecture seule ici — le réordonnancement/déplacement se fait
   depuis les actions de ligne (``deplacer``/``dupliquer``, KbPage).
   ========================================================================== */

function Node({ node, depth, onSelect }) {
  const [open, setOpen] = useState(depth < 1)
  const hasChildren = node.enfants?.length > 0
  return (
    <li>
      <div
        className="flex items-center gap-1 rounded px-1.5 py-1 text-sm hover:bg-muted/60"
        style={{ paddingInlineStart: depth * 16 }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? 'Réduire' : 'Développer'}
            className="flex size-4 items-center justify-center text-muted-foreground"
          >
            {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </button>
        ) : (
          <span className="inline-block size-4" />
        )}
        <button
          type="button"
          onClick={() => onSelect?.(node)}
          className="flex items-center gap-1.5 truncate text-left text-foreground hover:underline"
        >
          <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="truncate">{node.titre}</span>
        </button>
      </div>
      {hasChildren && open && (
        <ul>
          {node.enfants.map((e) => (
            <Node key={e.id} node={e} depth={depth + 1} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function ArticleTree({ onSelect, collapsedByDefault = true }) {
  const [expanded, setExpanded] = useState(!collapsedByDefault)
  const [tree, setTree] = useState([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!expanded || loaded) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-expand
    setLoading(true)
    kbApi.arbre()
      .then((res) => setTree(Array.isArray(res.data) ? res.data : []))
      .catch(() => setTree([]))
      .finally(() => { setLoading(false); setLoaded(true) })
  }, [expanded, loaded])

  return (
    <Card className="p-3 sm:p-4">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          'flex w-full items-center justify-between text-sm font-medium text-foreground',
        )}
        aria-expanded={expanded}
      >
        <span>Arborescence des articles</span>
        {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
      </button>
      {expanded && (
        <div className="mt-2">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner className="size-4" /> Chargement…
            </div>
          )}
          {!loading && tree.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun article hiérarchisé.</p>
          )}
          {!loading && tree.length > 0 && (
            <ul className="flex flex-col gap-0.5">
              {tree.map((n) => <Node key={n.id} node={n} depth={0} onSelect={onSelect} />)}
            </ul>
          )}
        </div>
      )}
    </Card>
  )
}
