import { useEffect, useState } from 'react'
import { Pencil, Send, CheckCircle2, Trash2, Plus } from 'lucide-react'
import { DetailShell } from '../../ui/module'
import { Button, Badge, EmptyState, Spinner, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'
import kbApi from '../../api/kbApi'
import { StatutArticlePill, splitTags } from './kbStatus'
import FilterSelect from './FilterSelect'

/* ============================================================================
   UX43 — Détail d'un article : contenu, versions, suivi de lecture, ACL.
   ----------------------------------------------------------------------------
   La lecture est ouverte à tous les rôles ; « marquer comme lu » est disponible
   pour tous. Publication, nouvelle version et gestion des droits d'accès (ACL)
   sont réservées à responsable/admin (``canEdit``).
   ========================================================================== */

const ROLE_OPTIONS = [
  { value: 'normal', label: 'Utilisateur' },
  { value: 'responsable', label: 'Responsable' },
  { value: 'admin', label: 'Administrateur' },
]
const NIVEAU_OPTIONS = [
  { value: 'lecture', label: 'Lecture' },
  { value: 'edition', label: 'Édition' },
]

export default function ArticleDetail({ articleId, canEdit, onBack, onEdit, onChanged }) {
  const [article, setArticle] = useState(null)
  const [versions, setVersions] = useState([])
  const [resume, setResume] = useState(null)
  const [acls, setAcls] = useState([])
  const [loading, setLoading] = useState(true)
  const [aclDraft, setAclDraft] = useState({ role: 'normal', niveau: 'lecture' })

  const load = () => {
    setLoading(true)
    Promise.all([
      kbApi.getArticle(articleId),
      kbApi.listVersions({ article: articleId }),
      kbApi.resumeLecture(articleId),
      canEdit ? kbApi.listAcls({ article: articleId }) : Promise.resolve(null),
    ])
      .then(([a, v, r, acl]) => {
        setArticle(a.data)
        setVersions(Array.isArray(v.data) ? v.data : (v.data?.results ?? []))
        setResume(r.data)
        if (acl) setAcls(Array.isArray(acl.data) ? acl.data : (acl.data?.results ?? []))
      })
      .catch(() => toast.error('Impossible de charger l’article.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const marquerLu = async () => {
    try {
      const res = await kbApi.marquerLu(articleId)
      setResume(res.data)
      toast.success('Marqué comme lu.')
    } catch { toast.error('Action impossible.') }
  }

  const publier = async () => {
    try {
      await kbApi.publier(articleId)
      toast.success('Article publié.')
      load()
      onChanged?.()
    } catch { toast.error('Publication impossible.') }
  }

  const nouvelleVersion = async () => {
    try {
      await kbApi.nouvelleVersion(articleId)
      toast.success('Nouvelle version figée.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  const addAcl = async () => {
    try {
      await kbApi.createAcl({ article: articleId, ...aclDraft })
      toast.success('Droit d’accès ajouté.')
      load()
    } catch { toast.error('Ajout impossible (doublon ?).') }
  }

  const removeAcl = async (id) => {
    try {
      await kbApi.removeAcl(id)
      toast.success('Droit d’accès retiré.')
      load()
    } catch { toast.error('Suppression impossible.') }
  }

  if (loading || !article) {
    return (
      <div className="page flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }

  const tags = splitTags(article.tags)

  // ── Onglet Contenu ──
  const contenuTab = (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        {article.categorie && <Badge tone="info">{article.categorie}</Badge>}
        {tags.map((t) => <Badge key={t} tone="neutral">{t}</Badge>)}
        <span>· Auteur : {article.auteur_nom || '—'}</span>
        <span>· Modifié : {formatDateTime(article.date_modification)}</span>
      </div>
      <article className="whitespace-pre-wrap text-sm leading-relaxed">
        {article.corps || <span className="text-muted-foreground">(Aucun contenu)</span>}
      </article>
    </div>
  )

  // ── Onglet Versions ──
  const versionsTab = versions.length ? (
    <ul className="flex flex-col gap-2">
      {versions.map((v) => (
        <li key={v.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
          <span className="flex items-center gap-2">
            <Badge tone="neutral">v{v.version}</Badge>
            <span className="font-medium">{v.titre}</span>
          </span>
          <span className="text-xs text-muted-foreground">
            {v.auteur_nom || '—'} · {formatDateTime(v.date_creation)}
          </span>
        </li>
      ))}
    </ul>
  ) : (
    <EmptyState title="Aucune version" description="Aucun instantané n’a encore été figé." />
  )

  // ── Onglet Lecteurs (suivi de lecture) ──
  const lecteurs = resume?.lecteurs ?? []
  const lecteursTab = (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        {resume?.nombre ?? 0} lecteur(s) ont marqué cet article comme lu.
      </p>
      {lecteurs.length ? (
        <ul className="flex flex-col gap-1.5">
          {lecteurs.map((l, i) => (
            <li key={l.utilisateur ?? i} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
              <span>{l.nom || '—'}</span>
              <span className="text-xs text-muted-foreground">{formatDateTime(l.lu_le)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="Aucune lecture" description="Personne n’a encore lu cet article." />
      )}
    </div>
  )

  // ── Onglet Droits d'accès (ACL) — responsable/admin ──
  const aclTab = (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Sans aucun droit défini, l’article est visible de tous. Dès qu’un droit de
        lecture existe, seuls les paliers listés (plus l’administrateur) peuvent le lire.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <FilterSelect
          value={aclDraft.role}
          onChange={(role) => setAclDraft((d) => ({ ...d, role }))}
          options={ROLE_OPTIONS}
          aria-label="Palier de rôle"
        />
        <FilterSelect
          value={aclDraft.niveau}
          onChange={(niveau) => setAclDraft((d) => ({ ...d, niveau }))}
          options={NIVEAU_OPTIONS}
          aria-label="Niveau d’accès"
        />
        <Button type="button" variant="outline" onClick={addAcl}>
          <Plus /> Ajouter
        </Button>
      </div>
      {acls.length ? (
        <ul className="flex flex-col gap-1.5">
          {acls.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <Badge tone="info">{a.role_display || a.role}</Badge>
                <Badge tone="neutral">{a.niveau_display || a.niveau}</Badge>
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeAcl(a.id)}
                aria-label="Retirer ce droit"
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Aucun droit défini (article public).</p>
      )}
    </div>
  )

  const tabs = [
    { value: 'contenu', label: 'Contenu', content: contenuTab },
    { value: 'versions', label: 'Versions', count: versions.length, content: versionsTab },
    { value: 'lecteurs', label: 'Lecteurs', count: resume?.nombre ?? 0, content: lecteursTab },
  ]
  if (canEdit) {
    tabs.push({ value: 'acces', label: 'Droits d’accès', count: acls.length, content: aclTab })
  }

  const actions = (
    <>
      <Button type="button" variant="outline" onClick={marquerLu}>
        <CheckCircle2 /> Marquer comme lu
      </Button>
      {canEdit && (
        <>
          <Button type="button" variant="outline" onClick={onEdit}>
            <Pencil /> Éditer
          </Button>
          <Button type="button" variant="outline" onClick={nouvelleVersion}>
            Nouvelle version
          </Button>
          {article.statut !== 'publie' && (
            <Button type="button" onClick={publier}>
              <Send /> Publier
            </Button>
          )}
        </>
      )}
    </>
  )

  return (
    <div className="page flex flex-col gap-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Retour à la liste
      </button>
      <DetailShell
        title={article.titre}
        status={article.statut}
        statusPill={StatutArticlePill}
        actions={actions}
        tabs={tabs}
      />
    </div>
  )
}
