// PACT117 — Onglet « Modèles brandés » de la page Paramètres (FG393).
//
// `core.BrandedTemplate` et son ViewSet (`/core/branded-templates/`) sont
// exposés depuis FG393 et AUCUN fichier frontend ne les appelait : le modèle
// existait, l'écran n'existait pas. Cet onglet comble le trou.
//
// Ce que fait l'écran :
//  1. liste les modèles de la société, groupés par canal (PDF / Email /
//     WhatsApp) — LECTURE ouverte à tout utilisateur authentifié ;
//  2. crée un modèle (canal + code d'usage + nom + sujet + corps) ;
//  3. édite le modèle sélectionné (nom, sujet, corps, actif) ;
//  4. APERÇU : `POST …/branded-templates/{id}/preview/` rend le modèle sur un
//     contexte d'exemple ÉDITABLE (JSON), via le moteur SÛR `core.templating`
//     (substitution littérale, jamais d'exécution de code). L'aperçu est
//     SERVEUR : il porte donc sur le modèle tel qu'il est enregistré — un
//     modèle qui vient d'être créé ouvre automatiquement son aperçu, et le
//     bouton « Aperçu » de l'éditeur travaille sur la version enregistrée
//     (l'éditeur prévient quand des modifications ne sont pas encore
//     enregistrées).
//
// Sécurité : l'écriture est réservée au palier admin/responsable — le SERVEUR
// re-vérifie (IsAdminOrResponsableTier) ; ce contrôle UI ne fait que masquer
// les commandes. `company` n'est JAMAIS envoyée : elle est imposée côté
// serveur (TenantMixin).
import { useEffect, useMemo, useState } from 'react'
import { FileText, Mail, MessageCircle, Plus, Trash2, Eye, Save } from 'lucide-react'
import api from '../../api/axios'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { toast } from '../../ui/confirm'
import {
  Card, CardContent, Input, Textarea, Button, IconButton, Badge, Spinner,
  EmptyState, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

// Canaux du modèle (miroir de BrandedTemplate.KIND_CHOICES).
const KINDS = [
  ['email', 'Email', Mail],
  ['pdf', 'PDF', FileText],
  ['whatsapp', 'WhatsApp', MessageCircle],
]
const KIND_LABELS = Object.fromEntries(KINDS.map(([k, label]) => [k, label]))

// Contexte d'exemple par défaut : de quoi voir un rendu tout de suite, jamais
// une donnée réelle. Éditable à l'écran.
const CONTEXTE_EXEMPLE = {
  client: { nom: 'SARL Exemple' },
  devis: { numero: 'DEV-2026-0042', total_ttc: '48 500,00' },
  societe: { nom: 'TAQINOR' },
}

const VIDE = { kind: 'email', code: '', nom: '', sujet: '', corps: '' }

export default function ModelesBrandesSection() {
  const canManage = useIsAdminOrResponsable()

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)

  const [draft, setDraft] = useState(VIDE)
  const [selectedId, setSelectedId] = useState(null)
  const [edit, setEdit] = useState(null)   // copie éditable du modèle choisi
  const [dirty, setDirty] = useState(false)

  const [contexteTexte, setContexteTexte] = useState(
    () => JSON.stringify(CONTEXTE_EXEMPLE, null, 2))
  const [apercu, setApercu] = useState(null)
  const [apercuErreur, setApercuErreur] = useState('')

  const charger = () => api.get('/core/branded-templates/')
    .then((res) => {
      setRows(res.data?.results ?? res.data ?? [])
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => { charger() }, [])

  // Groupement par canal, ordre stable (email → pdf → whatsapp).
  const groupes = useMemo(() => KINDS.map(([kind, label, Icon]) => ({
    kind,
    label,
    Icon,
    items: rows.filter((r) => r.kind === kind),
  })).filter((g) => g.items.length > 0), [rows])

  const choisir = (row) => {
    setSelectedId(row.id)
    setEdit({
      nom: row.nom ?? '', sujet: row.sujet ?? '', corps: row.corps ?? '',
      actif: row.actif !== false,
    })
    setDirty(false)
    setApercu(null)
    setApercuErreur('')
  }

  const majEdit = (patch) => {
    setEdit((e) => ({ ...e, ...patch }))
    setDirty(true)
  }

  // Contexte d'exemple saisi : JSON invalide → on renvoie null (message clair,
  // jamais un plantage).
  const lireContexte = () => {
    try {
      const parsed = JSON.parse(contexteTexte || '{}')
      return (parsed && typeof parsed === 'object') ? parsed : {}
    } catch {
      return null
    }
  }

  const previsualiser = async (id) => {
    const context = lireContexte()
    if (context === null) {
      setApercu(null)
      setApercuErreur("Le contexte d'exemple n'est pas un JSON valide.")
      return
    }
    setApercuErreur('')
    try {
      const res = await api.post(`/core/branded-templates/${id}/preview/`, { context })
      setApercu(res.data ?? {})
    } catch (e) {
      setApercu(null)
      setApercuErreur(e?.response?.data?.detail ?? "Aperçu impossible.")
    }
  }

  const creer = async () => {
    const code = draft.code.trim()
    const nom = draft.nom.trim()
    if (!code || !nom) return
    setBusy(true)
    try {
      const res = await api.post('/core/branded-templates/', {
        kind: draft.kind, code, nom,
        sujet: draft.sujet, corps: draft.corps,
      })
      const cree = res.data ?? {}
      setDraft(VIDE)
      await charger()
      if (cree.id) {
        choisir(cree)
        // Le modèle vient d'être enregistré : son aperçu serveur est
        // immédiatement fidèle — on l'ouvre pour vérifier le rendu.
        previsualiser(cree.id)
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    } finally { setBusy(false) }
  }

  const enregistrer = async () => {
    if (!selectedId || !edit) return
    setBusy(true)
    try {
      await api.patch(`/core/branded-templates/${selectedId}/`, {
        nom: edit.nom, sujet: edit.sujet, corps: edit.corps, actif: edit.actif,
      })
      setDirty(false)
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }

  const supprimer = async (row) => {
    if (!window.confirm(`Supprimer le modèle « ${row.nom || row.code} » ?`)) return
    try {
      await api.delete(`/core/branded-templates/${row.id}/`)
      if (selectedId === row.id) { setSelectedId(null); setEdit(null); setApercu(null) }
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (loadError) {
    return (
      <EmptyState title="Impossible de charger les modèles brandés"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  const selection = rows.find((r) => r.id === selectedId) ?? null

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11.5px] text-muted-foreground">
        Modèles de texte brandés réutilisables (PDF, email, WhatsApp). Le corps
        accepte des variables de la forme <code>{'{{ client.nom }}'}</code> :
        elles sont remplacées littéralement au moment de l'envoi, jamais
        exécutées. L'aperçu rend le modèle enregistré sur un contexte d'exemple.
      </p>

      {/* ── Liste, groupée par canal ────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Modèles de la société"
            icon={<><path d="M4 4h16v4H4z"/><path d="M4 12h10"/><path d="M4 17h7"/></>} />

          {rows.length === 0 && (
            <EmptyState icon={FileText} title="Aucun modèle brandé"
              description="Créez votre premier modèle ci-dessous (ex. « relance de devis » par email)."
              className="py-6" />
          )}

          <div className="flex flex-col gap-3">
            {groupes.map((groupe) => (
              <div key={groupe.kind}>
                <p data-testid={`groupe-canal-${groupe.kind}`}
                  className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                  <groupe.Icon className="size-3.5" aria-hidden="true" /> {groupe.label}
                </p>
                <div className="flex flex-col gap-1.5">
                  {groupe.items.map((row) => (
                    <div key={row.id} data-testid={`modele-brande-${row.kind}-${row.code}`}
                      className={['flex flex-wrap items-center gap-1.5 rounded-lg border p-3',
                        row.id === selectedId ? 'border-primary' : 'border-border'].join(' ')}>
                      <button type="button"
                        className="min-w-[140px] flex-[1_1_140px] text-left text-sm font-medium"
                        onClick={() => choisir(row)}>
                        {row.nom || row.code}
                      </button>
                      <Badge tone="neutral">{row.code}</Badge>
                      <Badge tone={row.actif === false ? 'neutral' : 'success'}>
                        {row.actif === false ? 'Inactif' : 'Actif'}
                      </Badge>
                      <div className="ml-auto flex items-center gap-1">
                        <Button type="button" size="sm" variant="outline"
                          onClick={() => { choisir(row); previsualiser(row.id) }}>
                          <Eye className="size-4" aria-hidden="true" /> Aperçu
                        </Button>
                        {canManage && (
                          <IconButton size="sm" variant="outline" label="Supprimer le modèle"
                            className="text-destructive hover:text-destructive"
                            onClick={() => supprimer(row)}>
                            <Trash2 className="size-4" aria-hidden="true" />
                          </IconButton>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* ── Création (admin/responsable) ──────────────────────────────── */}
          {canManage && (
            <div className="mt-3 rounded-lg border border-dashed border-border p-3">
              <div className="flex flex-wrap gap-1.5">
                <div className="min-w-[140px] flex-1">
                  <Select value={draft.kind}
                    onValueChange={(v) => setDraft((d) => ({ ...d, kind: v }))}>
                    <SelectTrigger aria-label="Canal du modèle"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {KINDS.map(([k, label]) => (
                        <SelectItem key={k} value={k}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input className="min-w-[140px] flex-[1_1_140px]"
                  placeholder="Code d'usage (ex. relance_devis)"
                  value={draft.code}
                  onChange={(e) => setDraft((d) => ({ ...d, code: e.target.value }))} />
                <Input className="min-w-[160px] flex-[2_1_160px]"
                  placeholder="Nom (ex. Relance de devis)"
                  value={draft.nom}
                  onChange={(e) => setDraft((d) => ({ ...d, nom: e.target.value }))} />
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                <Input className="min-w-[200px] flex-1"
                  placeholder="Sujet / titre (variables autorisées)"
                  value={draft.sujet}
                  onChange={(e) => setDraft((d) => ({ ...d, sujet: e.target.value }))} />
              </div>
              <Textarea className="mt-1.5" rows={4}
                placeholder="Corps du message — ex. Bonjour {{ client.nom }}, votre devis {{ devis.numero }}…"
                value={draft.corps}
                onChange={(e) => setDraft((d) => ({ ...d, corps: e.target.value }))} />
              <div className="mt-1.5 flex justify-end">
                <Button type="button" onClick={creer} disabled={busy}>
                  <Plus className="size-4" aria-hidden="true" /> Créer le modèle
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Éditeur + aperçu du modèle sélectionné ──────────────────────── */}
      {selection && edit && (
        <Card>
          <CardContent className="pt-4 sm:pt-5">
            <SectionTitle label={`Modèle « ${selection.code} » (${KIND_LABELS[selection.kind] ?? selection.kind})`}
              icon={<><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></>} />

            {Array.isArray(selection.variables) && selection.variables.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {selection.variables.map((v) => (
                  <Badge key={v} tone="info">{`{{ ${v} }}`}</Badge>
                ))}
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <Input placeholder="Nom" value={edit.nom} disabled={!canManage}
                onChange={(e) => majEdit({ nom: e.target.value })} />
              <Input placeholder="Sujet / titre" value={edit.sujet} disabled={!canManage}
                onChange={(e) => majEdit({ sujet: e.target.value })} />
              <Textarea rows={6} placeholder="Corps" value={edit.corps} disabled={!canManage}
                onChange={(e) => majEdit({ corps: e.target.value })} />
            </div>

            {canManage && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <Button type="button" size="sm"
                  variant={edit.actif ? 'success' : 'secondary'}
                  onClick={() => majEdit({ actif: !edit.actif })}>
                  {edit.actif ? 'Actif' : 'Inactif'}
                </Button>
                <Button type="button" onClick={enregistrer} disabled={busy || !dirty}>
                  <Save className="size-4" aria-hidden="true" /> Enregistrer
                </Button>
              </div>
            )}

            {/* Contexte d'exemple + aperçu serveur. */}
            <div className="mt-3 rounded-lg border border-dashed border-border p-3">
              <p className="mb-1.5 text-[11.5px] text-muted-foreground">
                Contexte d'exemple (JSON) utilisé pour l'aperçu — données fictives.
              </p>
              <Textarea rows={5} value={contexteTexte} aria-label="Contexte d'exemple"
                onChange={(e) => setContexteTexte(e.target.value)} />
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Button type="button" variant="outline"
                  onClick={() => previsualiser(selection.id)}>
                  <Eye className="size-4" aria-hidden="true" /> Aperçu du rendu
                </Button>
                {dirty && (
                  <span className="text-[11.5px] text-muted-foreground">
                    L'aperçu porte sur la version enregistrée — enregistrez pour
                    voir vos modifications.
                  </span>
                )}
              </div>
              {apercuErreur && (
                <p className="mt-1.5 text-xs text-destructive">{apercuErreur}</p>
              )}
              {apercu && (
                <div className="mt-2 rounded-lg border border-border p-3" data-testid="apercu-modele">
                  {apercu.sujet && (
                    <p className="text-sm font-medium">{apercu.sujet}</p>
                  )}
                  <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
                    {apercu.corps}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
