import { useEffect, useState } from 'react'
import {
  Pencil, Send, CheckCircle2, Trash2, Plus, Share2, Copy,
  ShieldCheck, Lock, Unlock, Star,
} from 'lucide-react'
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
  const [partages, setPartages] = useState([])
  const [loading, setLoading] = useState(true)
  const [aclDraft, setAclDraft] = useState({ role: 'normal', niveau: 'lecture' })
  const [favori, setFavori] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      kbApi.getArticle(articleId),
      kbApi.listVersions({ article: articleId }),
      kbApi.resumeLecture(articleId),
      canEdit ? kbApi.listAcls({ article: articleId }) : Promise.resolve(null),
      canEdit ? kbApi.listPartages({ article: articleId }) : Promise.resolve(null),
      kbApi.listFavoris({ article: articleId }),
    ])
      .then(([a, v, r, acl, part, fav]) => {
        setArticle(a.data)
        setVersions(Array.isArray(v.data) ? v.data : (v.data?.results ?? []))
        setResume(r.data)
        if (acl) setAcls(Array.isArray(acl.data) ? acl.data : (acl.data?.results ?? []))
        if (part) setPartages(Array.isArray(part.data) ? part.data : (part.data?.results ?? []))
        const favRows = Array.isArray(fav.data) ? fav.data : (fav.data?.results ?? [])
        setFavori(favRows.length > 0)
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

  // ── XKB19 — Partager sur le web (lien public tokenisé) ──
  const partagerSurLeWeb = async () => {
    try {
      await kbApi.createPartage({ article: articleId })
      toast.success('Lien public créé.')
      load()
    } catch { toast.error('Création du lien impossible.') }
  }

  const depublierPartage = async (id) => {
    try {
      await kbApi.depublierPartage(id)
      toast.success('Lien dépublié.')
      load()
    } catch { toast.error('Dépublication impossible.') }
  }

  const copierLien = (token) => {
    const url = `${window.location.origin}/kb/public/${token}`
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url)
      toast.success('Lien copié.')
    } else {
      toast.info(url)
    }
  }

  // ── XKB14 — vérification / verrouillage ──
  const marquerVerifie = async () => {
    try {
      await kbApi.verifier(articleId, 90)
      toast.success('Article marqué vérifié.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  const toggleVerrou = async () => {
    try {
      if (article.est_verrouille) {
        await kbApi.deverrouiller(articleId)
        toast.success('Article déverrouillé.')
      } else {
        await kbApi.verrouiller(articleId)
        toast.success('Article verrouillé.')
      }
      load()
    } catch { toast.error('Action impossible (droit d’édition requis).') }
  }

  // ── XKB15 — favori ──
  const toggleFavori = async () => {
    try {
      const res = await kbApi.togglerFavori(articleId)
      setFavori(res.data?.favori)
      toast.success(res.data?.favori ? 'Ajouté aux favoris.' : 'Retiré des favoris.')
    } catch { toast.error('Action impossible.') }
  }

  if (loading || !article) {
    return (
      <div className="page flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }

  const tags = splitTags(article.tags)
  // XKB14 — « vérifié » = verifie_jusqua posé ET pas encore dépassé (dérivé
  // côté client, aucun champ booléen dédié côté serveur).
  const estVerifie = !!article.verifie_jusqua
    && new Date(article.verifie_jusqua) > new Date()

  // ── Onglet Contenu ──
  const contenuTab = (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        {article.categorie && <Badge tone="info">{article.categorie}</Badge>}
        {tags.map((t) => <Badge key={t} tone="neutral">{t}</Badge>)}
        {estVerifie && (
          <Badge tone="success">
            <ShieldCheck className="size-3.5" aria-hidden="true" /> Vérifié
          </Badge>
        )}
        {article.est_verrouille && (
          <Badge tone="warning">
            <Lock className="size-3.5" aria-hidden="true" /> Verrouillé
          </Badge>
        )}
        <span>· Auteur : {article.auteur_nom || '—'}</span>
        <span>· Modifié : {formatDateTime(article.date_modification)}</span>
      </div>
      <article className="whitespace-pre-wrap text-sm leading-relaxed">
        {article.corps || <span className="text-muted-foreground">(Aucun contenu)</span>}
      </article>
    </div>
  )

  // ── Onglet Partage public (XKB19) ──
  const partageTab = (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Génère un lien public (sans login) pour consulter cet article — utile pour
        un client ou un sous-traitant sans compte ERP.
      </p>
      <Button type="button" variant="outline" onClick={partagerSurLeWeb} className="w-fit">
        <Share2 /> Partager sur le web
      </Button>
      {partages.length ? (
        <ul className="flex flex-col gap-1.5">
          {partages.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <Badge tone={p.actif ? 'success' : 'neutral'}>
                  {p.actif ? 'Actif' : 'Dépublié'}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {p.consultations ?? 0} consultation(s)
                </span>
              </span>
              <span className="flex items-center gap-1.5">
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => copierLien(p.token)}
                  aria-label="Copier le lien"
                >
                  <Copy />
                </Button>
                {p.actif && (
                  <Button
                    type="button" variant="ghost" size="sm"
                    onClick={() => depublierPartage(p.id)}
                    aria-label="Dépublier ce lien"
                  >
                    Dépublier
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="Aucun lien public" description="Cet article n’a pas encore été partagé." />
      )}
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
    tabs.push({ value: 'partage', label: 'Partage public', count: partages.length, content: partageTab })
  }

  const actions = (
    <>
      <Button
        type="button" variant="outline" onClick={toggleFavori}
        aria-pressed={favori}
        aria-label={favori ? 'Retirer des favoris' : 'Ajouter aux favoris'}
      >
        <Star className={favori ? 'fill-current' : ''} />
      </Button>
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
          <Button type="button" variant="outline" onClick={marquerVerifie}>
            <ShieldCheck /> Marquer vérifié
          </Button>
          <Button type="button" variant="outline" onClick={toggleVerrou}>
            {article.est_verrouille ? <Unlock /> : <Lock />}
            {article.est_verrouille ? 'Déverrouiller' : 'Verrouiller'}
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
