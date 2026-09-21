import { useEffect, useState } from 'react'
import { Clock, ShieldCheck, MessageSquare, Download, Star, Plus, Trash2 } from 'lucide-react'
import gedApi from '../../api/gedApi'
import rolesApi from '../../api/rolesApi'
import ChatterWidget from '../../components/ChatterWidget'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Button, Badge, Spinner, EmptyState, Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Switch, toast,
} from '../../ui'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR70 — Panneau « Détails » d'un document GED : timeline + rapport ACL.
   ----------------------------------------------------------------------------
   Surface deux backends déjà exposés mais sans écran :
   • Timeline (XGED15) — journal chronologique du document.
   • « Qui voit ce document et pourquoi » (XGED22) — niveau effectif par
     utilisateur/rôle + la source de résolution, exportable en CSV.
   Inclut aussi l'étoile favori personnel (ZGED7).

   WIR163 — l'onglet « Accès » gagne un formulaire de GESTION (miroir
   kb.KbArticleAcl) : accorder/révoquer une entrée AclGed directement sur ce
   document (utilisateur OU rôle, niveau lecture/écriture/gestion, propagation
   aux sous-éléments). Écriture réservée responsable/admin CÔTÉ BACKEND (403 →
   toast, comme partout dans l'ERP) — aucun gating de rôle ajouté ici. Poser
   une entrée a un effet IMMÉDIAT (aucun cache) : on recharge le rapport « qui
   voit » après chaque ajout/retrait.
   ========================================================================== */

const NIVEAU_OPTIONS = [
  { value: 'lecture', label: 'Lecture' },
  { value: 'ecriture', label: 'Écriture' },
  { value: 'gestion', label: 'Gestion' },
]

export default function GedDocumentInsights({ document, onClose }) {
  const [timeline, setTimeline] = useState(null)
  const [acl, setAcl] = useState(null)
  const [entries, setEntries] = useState(null)
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [favori, setFavori] = useState(!!document?.favori)
  const [draft, setDraft] = useState({
    principalType: 'utilisateur', principalId: '', niveau: 'lecture',
    herite: true,
  })

  const reloadAcl = () => {
    if (!document) return
    gedApi.getPermissionsEffectives(document.id)
      .then((r) => setAcl(r.data?.results ?? r.data ?? []))
      .catch(() => setAcl([]))
    gedApi.getAcls({ document: document.id })
      .then((r) => setEntries(r.data?.results ?? r.data ?? []))
      .catch(() => setEntries([]))
  }

  useEffect(() => {
    if (!document) return
    gedApi.getTimeline(document.id)
      .then((r) => setTimeline(r.data?.results ?? r.data ?? []))
      .catch(() => setTimeline([]))
    reloadAcl()
    gedApi.getUsers().then((r) => setUsers(r.data?.results ?? r.data ?? []))
      .catch(() => setUsers([]))
    rolesApi.getRoles().then((r) => setRoles(r.data?.results ?? r.data ?? []))
      .catch(() => setRoles([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document])

  const addAcl = async () => {
    if (!draft.principalId) {
      toast.error('Choisissez un utilisateur ou un rôle.')
      return
    }
    try {
      await gedApi.createAcl({
        document: document.id,
        [draft.principalType]: Number(draft.principalId),
        niveau: draft.niveau,
        herite: draft.herite,
      })
      toast.success('Droit d’accès ajouté.')
      setDraft((d) => ({ ...d, principalId: '' }))
      reloadAcl()
    } catch { toast.error('Ajout impossible (doublon ?).') }
  }

  const removeAcl = async (id) => {
    try {
      await gedApi.deleteAcl(id)
      toast.success('Droit d’accès retiré.')
      reloadAcl()
    } catch { toast.error('Suppression impossible.') }
  }

  const exportCsv = async () => {
    try {
      const res = await gedApi.exportPermissionsEffectivesCsv(document.id)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }))
      const a = window.document.createElement('a')
      a.href = url
      a.download = `acl-document-${document.id}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Export impossible.') }
  }

  const toggleFavori = async () => {
    try {
      const r = await gedApi.toggleFavoriDocument(document.id, !favori)
      setFavori(!!r.data?.favori)
    } catch { toast.error('Action impossible.') }
  }

  if (!document) return null
  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <SheetContent side="right" className="w-full max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {document.nom}
            <Button size="sm" variant="ghost" onClick={toggleFavori}
              aria-label={favori ? 'Retirer des favoris' : 'Ajouter aux favoris'}>
              <Star size={16} className={favori ? 'fill-amber-400 text-amber-400' : ''} />
            </Button>
          </SheetTitle>
        </SheetHeader>
        <Tabs defaultValue="timeline" className="mt-3">
          <TabsList>
            <TabsTrigger value="timeline"><Clock size={14} /> Timeline</TabsTrigger>
            <TabsTrigger value="chatter"><MessageSquare size={14} /> Notes</TabsTrigger>
            <TabsTrigger value="acl"><ShieldCheck size={14} /> Accès</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline">
            {timeline === null ? <Spinner /> : timeline.length === 0 ? (
              <EmptyState title="Aucune activité" className="py-6" />
            ) : (
              <ul className="flex flex-col gap-2" data-testid="ged-timeline">
                {timeline.map((e, i) => (
                  <li key={i} className="rounded-md border px-3 py-2 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Badge tone="info">{e.evenement || e.type}</Badge>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {formatDate(e.created_at)}
                      </span>
                    </div>
                    <div className="mt-1 text-muted-foreground">{e.message}</div>
                    {e.utilisateur && (
                      <div className="text-xs text-muted-foreground">par {e.utilisateur}</div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>

          {/* XGED15 — chatter documentaire générique (notes + @mentions),
              réutilise le composant FG7 déjà branché sur kb/veille_ao (aucun
              système parallèle) ; le backend expose `('ged', 'document')`
              dans `records.ALLOWED_TARGETS` (voir apps/ged/platform.py). */}
          <TabsContent value="chatter">
            <ChatterWidget model="ged.document" id={document.id} />
          </TabsContent>

          <TabsContent value="acl">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Qui voit ce document et pourquoi.</p>
              <Button size="sm" variant="secondary" onClick={exportCsv}>
                <Download size={14} /> CSV
              </Button>
            </div>
            {acl === null ? <Spinner /> : acl.length === 0 ? (
              <EmptyState title="Aucune règle d'accès" className="py-6" />
            ) : (
              <ul className="flex flex-col gap-1.5" data-testid="ged-acl">
                {acl.map((l, i) => (
                  <li key={i} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="font-medium">{l.label}</span>
                    <Badge tone={l.niveau && l.niveau !== 'aucune' ? 'success' : 'neutral'}>
                      {l.niveau || 'aucune'}
                    </Badge>
                    <span className="ml-auto text-xs text-muted-foreground">{l.source}</span>
                  </li>
                ))}
              </ul>
            )}

            {/* WIR163 — accorder/révoquer un droit d'accès direct sur ce
                document (miroir kb.KbArticleAcl). Écriture réservée
                responsable/admin côté backend (403 → toast). */}
            <div className="mt-4 border-t pt-3">
              <p className="mb-2 text-sm font-medium">Gérer les droits d’accès</p>
              <div className="flex flex-wrap items-end gap-2">
                <Select value={draft.principalType}
                  onValueChange={(v) => setDraft((d) => (
                    { ...d, principalType: v, principalId: '' }))}>
                  <SelectTrigger aria-label="Type de principal" className="w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="utilisateur">Utilisateur</SelectItem>
                    <SelectItem value="role">Rôle</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={draft.principalId}
                  onValueChange={(v) => setDraft((d) => ({ ...d, principalId: v }))}>
                  <SelectTrigger aria-label={
                    draft.principalType === 'role' ? 'Choisir un rôle' : 'Choisir un utilisateur'
                  } className="w-44">
                    <SelectValue placeholder={
                      draft.principalType === 'role' ? 'Rôle…' : 'Utilisateur…'
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    {(draft.principalType === 'role' ? roles : users).map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.nom || p.username || p.email}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={draft.niveau}
                  onValueChange={(v) => setDraft((d) => ({ ...d, niveau: v }))}>
                  <SelectTrigger aria-label="Niveau d’accès" className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {NIVEAU_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Switch checked={draft.herite}
                    onCheckedChange={(v) => setDraft((d) => ({ ...d, herite: v }))}
                    aria-label="Hérité vers les sous-éléments" />
                  Hérité
                </label>
                <Button type="button" variant="outline" size="sm" onClick={addAcl}>
                  <Plus size={14} /> Ajouter
                </Button>
              </div>
              {entries === null ? <Spinner /> : entries.length === 0 ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  Aucun droit posé directement sur ce document.
                </p>
              ) : (
                <ul className="mt-2 flex flex-col gap-1.5" data-testid="ged-acl-entries">
                  {entries.map((e) => (
                    <li key={e.id} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm">
                      <span className="flex items-center gap-2">
                        <Badge tone="neutral">
                          {e.utilisateur_nom || e.role_nom || '—'}
                        </Badge>
                        <Badge tone="info">{e.niveau}</Badge>
                      </span>
                      <Button
                        type="button" variant="ghost" size="sm"
                        onClick={() => removeAcl(e.id)}
                        aria-label="Retirer ce droit"
                      >
                        <Trash2 size={14} />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}
