import { useEffect, useState } from 'react'
import {
  Pencil, Send, CheckCircle2, Trash2, Plus, Share2, Copy,
  ShieldCheck, Lock, Unlock, Star, Languages, Download, LayoutTemplate,
  Image as ImageIcon,
} from 'lucide-react'
import { DetailShell } from '../../ui/module'
import { Button, Badge, EmptyState, Spinner, toast, buttonVariants } from '../../ui'
import { formatDateTime } from '../../lib/format'
import kbApi from '../../api/kbApi'
import { StatutArticlePill, splitTags } from './kbStatus'
import FilterSelect from './FilterSelect'
import ChatterWidget from '../../components/ChatterWidget'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import ItemsCollectionView from './ItemsCollectionView'
import { KbMarkdownBody, extractHeadings } from './kbMarkdown'

// XKB18 — langues supportées (mêmes clés que ``KbArticle.LANGUE_CHOICES``
// côté backend). L'arabe est RTL — le corps de l'article bascule ``dir``.
const LANGUE_LABELS = { fr: 'Français', ar: 'العربية', en: 'English' }
const RTL_LANGUES = new Set(['ar'])

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

export default function ArticleDetail({
  articleId, canEdit, onBack, onEdit, onChanged, onOpenArticle,
}) {
  const [article, setArticle] = useState(null)
  const [versions, setVersions] = useState([])
  const [resume, setResume] = useState(null)
  const [acls, setAcls] = useState([])
  const [partages, setPartages] = useState([])
  const [loading, setLoading] = useState(true)
  const [aclDraft, setAclDraft] = useState({ role: 'normal', niveau: 'lecture' })
  const [favori, setFavori] = useState(false)
  const [retroliens, setRetroliens] = useState([])
  // WIR71 — lectures obligatoires (XKB7) assignées sur cet article.
  const [lecturesObl, setLecturesObl] = useState([])
  const [oblDraft, setOblDraft] = useState({ role_cible: 'normal', echeance: '' })

  const load = () => {
    setLoading(true)
    Promise.all([
      kbApi.getArticle(articleId),
      kbApi.listVersions({ article: articleId }),
      kbApi.resumeLecture(articleId),
      canEdit ? kbApi.listAcls({ article: articleId }) : Promise.resolve(null),
      canEdit ? kbApi.listPartages({ article: articleId }) : Promise.resolve(null),
      kbApi.listFavoris({ article: articleId }),
      kbApi.retroliens(articleId),
      kbApi.listLecturesObligatoires({ article: articleId })
        .catch(() => ({ data: [] })),
    ])
      .then(([a, v, r, acl, part, fav, retro, obl]) => {
        setArticle(a.data)
        setVersions(Array.isArray(v.data) ? v.data : (v.data?.results ?? []))
        setResume(r.data)
        if (acl) setAcls(Array.isArray(acl.data) ? acl.data : (acl.data?.results ?? []))
        if (part) setPartages(Array.isArray(part.data) ? part.data : (part.data?.results ?? []))
        const favRows = Array.isArray(fav.data) ? fav.data : (fav.data?.results ?? [])
        setFavori(favRows.length > 0)
        setRetroliens(Array.isArray(retro.data) ? retro.data : (retro.data?.results ?? []))
        setLecturesObl(Array.isArray(obl.data) ? obl.data : (obl.data?.results ?? []))
      })
      .catch(() => toast.error('Impossible de charger l’article.'))
      .finally(() => setLoading(false))
  }

  // WIR71 — assignation d'une lecture obligatoire (managers) + retrait.
  const assignerLectureObl = async () => {
    try {
      await kbApi.createLectureObligatoire({
        article: articleId,
        role_cible: oblDraft.role_cible,
        echeance: oblDraft.echeance || null,
      })
      toast.success('Lecture obligatoire assignée.')
      setOblDraft({ role_cible: 'normal', echeance: '' })
      load()
    } catch { toast.error('Assignation impossible (doublon ?).') }
  }

  const retirerLectureObl = async (id) => {
    try {
      await kbApi.removeLectureObligatoire(id)
      toast.success('Lecture obligatoire retirée.')
      load()
    } catch { toast.error('Suppression impossible.') }
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

  // ── XKB18 — traduire vers une langue absente parmi celles supportées ──
  const traduire = async (langue) => {
    try {
      await kbApi.traduire(articleId, langue)
      toast.success(`Traduction ${LANGUE_LABELS[langue]} créée (brouillon).`)
      onChanged?.()
    } catch { toast.error('Traduction impossible.') }
  }

  // ── XKB12 — enregistrer comme gabarit réutilisable ──
  const enregistrerCommeGabarit = async () => {
    try {
      await kbApi.enregistrerCommeGabarit(articleId)
      toast.success('Article enregistré comme gabarit.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  // ── ZGED10 — image de couverture ──
  const changerCouverture = async (e) => {
    const fichier = e.target.files?.[0]
    e.target.value = ''
    if (!fichier) return
    try {
      await kbApi.uploadCouverture(articleId, fichier)
      toast.success('Couverture mise à jour.')
      load()
    } catch { toast.error('Téléversement impossible.') }
  }

  const retirerCouverture = async () => {
    try {
      await kbApi.removeCouverture(articleId)
      toast.success('Couverture retirée.')
      load()
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

  // XKB10 — sommaire dérivé du corps Markdown (vide pour un article texte
  // brut ou sans titres ATX).
  const estMarkdown = article.corps_format === 'markdown'
  const sommaire = estMarkdown ? extractHeadings(article.corps) : []
  // XKB18 — langue de CET article + RTL si arabe.
  const langue = article.langue || 'fr'
  const estRtl = RTL_LANGUES.has(langue)
  const languesManquantes = Object.keys(LANGUE_LABELS).filter((l) => l !== langue)

  // ── Onglet Contenu ──
  const contenuTab = (
    <div className="flex flex-col gap-4">
      {article.has_couverture && (
        <img
          src={kbApi.couvertureImageUrl(articleId)}
          alt=""
          loading="lazy"
          className="h-40 w-full rounded-lg object-cover"
        />
      )}
      {canEdit && (
        <div className="flex items-center gap-2">
          <label className={`${buttonVariants({ variant: 'outline', size: 'sm' })} cursor-pointer`}>
            <ImageIcon /> {article.has_couverture ? 'Changer la couverture' : 'Ajouter une couverture'}
            <input
              type="file" accept="image/*" className="hidden"
              onChange={changerCouverture}
            />
          </label>
          {article.has_couverture && (
            <Button type="button" variant="ghost" size="sm" onClick={retirerCouverture}>
              Retirer
            </Button>
          )}
        </div>
      )}
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
        <Badge tone="neutral">{LANGUE_LABELS[langue] || langue}</Badge>
        {article.traduction_perimee && (
          <Badge tone="warning">Traduction périmée</Badge>
        )}
        {/* WIR71 — badge « Lecture obligatoire » quand une assignation XKB7
            porte sur cet article (avec l'échéance la plus proche si fournie). */}
        {lecturesObl.length > 0 && (
          <Badge tone="warning">
            Lecture obligatoire
            {(() => {
              const echeances = lecturesObl.map((o) => o.echeance).filter(Boolean).sort()
              return echeances.length > 0 ? ` · avant le ${echeances[0]}` : ''
            })()}
          </Badge>
        )}
        <span>· Auteur : {article.auteur_nom || '—'}</span>
        <span>· Modifié : {formatDateTime(article.date_modification)}</span>
      </div>

      {canEdit && (
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          <Languages className="size-4 text-muted-foreground" aria-hidden="true" />
          <span className="text-muted-foreground">Traduire vers :</span>
          {languesManquantes.map((l) => (
            <Button key={l} type="button" variant="outline" size="sm" onClick={() => traduire(l)}>
              {LANGUE_LABELS[l]}
            </Button>
          ))}
        </div>
      )}

      {sommaire.length > 0 && (
        <nav aria-label="Sommaire" className="rounded-lg border border-border px-3 py-2 text-sm">
          <p className="mb-1 font-medium">Sommaire</p>
          <ul className="flex flex-col gap-0.5">
            {sommaire.map((h) => (
              <li key={h.slug} style={{ paddingInlineStart: (h.niveau - 1) * 12 }}>
                <a href={`#${h.slug}`} className="text-muted-foreground hover:text-foreground hover:underline">
                  {h.texte}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {/* VX122 — max-w-prose : une ligne de lecture bornée (~65ch), le confort
          de lecture standard pour un article long (jusqu'ici 0 max-w — le
          texte s'étirait sur toute la largeur du panneau). */}
      <article
        dir={estRtl ? 'rtl' : 'ltr'}
        className={
          estMarkdown ? 'max-w-prose text-sm' : 'max-w-prose whitespace-pre-wrap text-sm leading-relaxed'
        }
      >
        {!article.corps && <span className="text-muted-foreground">(Aucun contenu)</span>}
        {article.corps && (estMarkdown
          ? <KbMarkdownBody corps={article.corps} />
          : article.corps)}
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

  // ── Onglet Rétroliens (XKB11) — articles qui pointent vers celui-ci ──
  const retroliensTab = retroliens.length ? (
    <ul className="flex flex-col gap-2">
      {retroliens.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
          <button
            type="button"
            onClick={() => onOpenArticle?.(r.id)}
            className="font-medium text-left hover:underline disabled:no-underline disabled:cursor-default"
            disabled={!onOpenArticle}
          >
            {r.titre}
          </button>
          <StatutArticlePill status={r.statut} />
        </li>
      ))}
    </ul>
  ) : (
    <EmptyState title="Aucun rétrolien" description="Aucun article ne pointe encore vers celui-ci." />
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

      {/* WIR71 — lectures obligatoires (XKB7) : un manager assigne cet article
          à un palier de rôle (avec échéance optionnelle) ; l'utilisateur ciblé
          voit alors le badge « Lecture obligatoire » sur l'article. */}
      <div className="mt-2 border-t border-border pt-4">
        <h4 className="mb-1 text-sm font-semibold">Lecture obligatoire</h4>
        <p className="mb-2 text-sm text-muted-foreground">
          Rendez cet article obligatoire pour un palier de rôle. La complétion
          s’appuie sur le suivi de lecture existant (« Marquer comme lu »).
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <FilterSelect
            value={oblDraft.role_cible}
            onChange={(role_cible) => setOblDraft((d) => ({ ...d, role_cible }))}
            options={ROLE_OPTIONS}
            aria-label="Palier de rôle ciblé"
          />
          <input
            type="date"
            value={oblDraft.echeance}
            onChange={(e) => setOblDraft((d) => ({ ...d, echeance: e.target.value }))}
            aria-label="Échéance (optionnelle)"
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
          />
          <Button type="button" variant="outline" onClick={assignerLectureObl}>
            <Plus /> Assigner
          </Button>
        </div>
        {lecturesObl.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1.5">
            {lecturesObl.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
                <span className="flex items-center gap-2">
                  <Badge tone="info">{o.utilisateur_nom || o.role_cible || '—'}</Badge>
                  {o.echeance && <Badge tone="neutral">avant le {o.echeance}</Badge>}
                </span>
                <Button
                  type="button" variant="ghost" size="sm"
                  onClick={() => retirerLectureObl(o.id)}
                  aria-label="Retirer cette lecture obligatoire"
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )

  // ── Onglet Commentaires (chatter, XKB13) ──
  const commentairesTab = (
    <ChatterWidget model="kb.kbarticle" id={articleId} />
  )

  // ── Onglet Pièces jointes (XKB10) ──
  const piecesJointesTab = (
    <AttachmentsPanel model="kb.kbarticle" id={articleId} />
  )

  // ── Onglet Sous-articles (ZGED11 — vues liste/cartes/kanban/calendrier) ──
  const sousArticlesTab = (
    <ItemsCollectionView articleId={articleId} onSelect={(item) => onOpenArticle?.(item.id)} />
  )

  const tabs = [
    { value: 'contenu', label: 'Contenu', content: contenuTab },
    { value: 'pieces-jointes', label: 'Pièces jointes', content: piecesJointesTab },
    { value: 'sous-articles', label: 'Sous-articles', content: sousArticlesTab },
    { value: 'versions', label: 'Versions', count: versions.length, content: versionsTab },
    { value: 'retroliens', label: 'Rétroliens', count: retroliens.length, content: retroliensTab },
    { value: 'lecteurs', label: 'Lecteurs', count: resume?.nombre ?? 0, content: lecteursTab },
    { value: 'commentaires', label: 'Commentaires', content: commentairesTab },
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
      {/* Liens de téléchargement stylés comme des boutons — pas de
          Button asChild (Slot Radix exige un unique enfant, incompatible
          avec icône + libellé ici). */}
      <a href={kbApi.exportPdfUrl(articleId)} download className={buttonVariants({ variant: 'outline' })}>
        <Download /> PDF
      </a>
      <a href={kbApi.exportMarkdownUrl(articleId)} download className={buttonVariants({ variant: 'outline' })}>
        <Download /> Markdown
      </a>
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
          {!article.est_gabarit && (
            <Button type="button" variant="outline" onClick={enregistrerCommeGabarit}>
              <LayoutTemplate /> Enregistrer comme gabarit
            </Button>
          )}
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
        title={article.emoji ? `${article.emoji} ${article.titre}` : article.titre}
        status={article.statut}
        statusPill={StatutArticlePill}
        actions={actions}
        tabs={tabs}
      />
    </div>
  )
}
