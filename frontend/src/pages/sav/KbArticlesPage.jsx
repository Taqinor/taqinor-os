// FG87 — Base de connaissances SAV : playbooks de résolution (codes erreur
// onduleur, pannes de strings, problèmes terrain récurrents). Cherchable par
// texte libre + filtrable par catégorie. Lecture tout rôle, écriture
// responsable/admin (gardée côté serveur).
import { useEffect, useState } from 'react'
import { Plus, Pencil, Check, X, BookOpen, Search } from 'lucide-react'
import savApi from '../../api/savApi'
import {
  TooltipProvider, Card, Button, Input, Textarea, EmptyState, Skeleton,
  Badge, toast,
} from '../../ui'

export default function KbArticlesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({ titre: '', corps: '', categorie: '', tags: '' })
  const [creating, setCreating] = useState(false)
  const [edit, setEdit] = useState(null)

  const load = () => {
    setLoading(true)
    savApi.getKbArticles(search ? { search } : {})
      .then((r) => setRows(r.data.results ?? r.data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { load() }, [search])

  const create = async () => {
    if (!form.titre.trim() || !form.corps.trim()) return
    setCreating(true)
    try {
      const tags = form.tags.split(',').map((t) => t.trim()).filter(Boolean)
      await savApi.saveKbArticle(null, {
        titre: form.titre, corps: form.corps,
        categorie: form.categorie, tags,
      })
      setForm({ titre: '', corps: '', categorie: '', tags: '' })
      toast.success('Article ajouté')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Ajout impossible.')
    } finally { setCreating(false) }
  }

  const startEdit = (a) => setEdit({
    id: a.id, titre: a.titre, corps: a.corps, categorie: a.categorie ?? '',
    tags: (a.tags ?? []).join(', '),
  })
  const saveEdit = async () => {
    try {
      const tags = edit.tags.split(',').map((t) => t.trim()).filter(Boolean)
      await savApi.saveKbArticle(edit.id, {
        titre: edit.titre, corps: edit.corps, categorie: edit.categorie, tags,
      })
      setEdit(null)
      toast.success('Article mis à jour')
      load()
    } catch { toast.error('Mise à jour impossible.') }
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-4xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Base de connaissances SAV</h1>
            <p className="text-sm text-muted-foreground">
              {rows.length} article{rows.length > 1 ? 's' : ''}
            </p>
          </div>
          <Input leading={<Search />} placeholder="Rechercher…" value={search}
                 onChange={(e) => setSearch(e.target.value)} className="w-64" />
        </header>

        <Card className="flex flex-col gap-2 p-4">
          <Input placeholder="Titre" value={form.titre}
                 onChange={(e) => setForm((f) => ({ ...f, titre: e.target.value }))} />
          <Textarea rows={4} placeholder="Corps de l'article (playbook de résolution)"
                    value={form.corps}
                    onChange={(e) => setForm((f) => ({ ...f, corps: e.target.value }))} />
          <div className="flex gap-2">
            <Input placeholder="Catégorie (ex. Onduleur)" value={form.categorie}
                   onChange={(e) => setForm((f) => ({ ...f, categorie: e.target.value }))} />
            <Input placeholder="Tags séparés par des virgules" value={form.tags}
                   onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))} />
          </div>
          <Button type="button" size="sm" className="self-start" loading={creating} onClick={create}>
            <Plus /> Ajouter
          </Button>
        </Card>

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : rows.length === 0 ? (
          <EmptyState icon={BookOpen} title="Aucun article"
                      description="Ajoutez un article ci-dessus pour capitaliser une résolution." />
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((a) => (
              <li key={a.id} className="rounded-lg border border-border bg-card p-3 text-sm">
                {edit?.id === a.id ? (
                  <div className="flex flex-col gap-2">
                    <Input value={edit.titre} onChange={(e) => setEdit((s) => ({ ...s, titre: e.target.value }))} />
                    <Textarea rows={4} value={edit.corps} onChange={(e) => setEdit((s) => ({ ...s, corps: e.target.value }))} />
                    <div className="flex gap-2">
                      <Input placeholder="Catégorie" value={edit.categorie}
                             onChange={(e) => setEdit((s) => ({ ...s, categorie: e.target.value }))} />
                      <Input placeholder="Tags" value={edit.tags}
                             onChange={(e) => setEdit((s) => ({ ...s, tags: e.target.value }))} />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={saveEdit}><Check /> Enregistrer</Button>
                      <Button size="sm" variant="ghost" onClick={() => setEdit(null)}><X /></Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{a.titre}</p>
                      {a.categorie && <Badge tone="neutral">{a.categorie}</Badge>}
                      <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{a.corps}</p>
                      {(a.tags ?? []).length > 0 && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {a.tags.join(' · ')}
                        </p>
                      )}
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => startEdit(a)}><Pencil /></Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </TooltipProvider>
  )
}
