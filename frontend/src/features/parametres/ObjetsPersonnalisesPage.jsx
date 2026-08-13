// PACT140 — Écran Paramètres → Objets métier personnalisés (XPLT16 / NTEXT2-3).
//
// Définit SANS CODE un objet métier (code, libellé, icône) et ses champs, puis
// renvoie vers l'écran générique qui liste et édite ses enregistrements.
//
// RÉUTILISATION, PAS UN SECOND MOTEUR DE CHAMPS. Les champs d'un objet
// personnalisé sont des `CustomFieldDef` ORDINAIRES posés sous
// `module = 'custom:<code>'` — la propriété `field_module` déjà prévue par le
// modèle. Cet écran appelle donc le MÊME `customFieldsApi` que les modules
// natifs (leads, clients, produits…) : mêmes types, même validation, même
// journal d'audit. Aucun second éditeur de champs n'est écrit ici.
//
// Multi-tenant : `company` n'est JAMAIS envoyée — imposée côté serveur
// (TenantMixin). Écriture réservée à l'administrateur (le SERVEUR re-vérifie :
// IsAdminRole sur les objets comme sur les définitions de champs).
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, Plus, Trash2, ArrowRight } from 'lucide-react'
import api from '../../api/axios'
import customFieldsApi from '../../api/customFieldsApi'
import { toast } from '../../ui/confirm'
import {
  Button, IconButton, Input, Badge, Spinner, EmptyState, Card, CardContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// Types de champ supportés par le moteur EXISTANT (CustomFieldDef.type).
const TYPES_CHAMP = [
  ['text', 'Texte'],
  ['number', 'Nombre'],
  ['date', 'Date'],
  ['boolean', 'Oui / Non'],
  ['choice', 'Liste de choix'],
]

// Même règle de slug que l'éditeur de champs existant (Paramètres → Avancé).
function slugify(s) {
  return (s || '').trim().toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50)
}

// Message d'erreur serveur lisible (detail, ou première erreur de champ).
function messageErreur(e, fallback) {
  const d = e?.response?.data
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (d.detail) return d.detail
  const first = Object.values(d)[0]
  return Array.isArray(first) ? first[0] : (first || fallback)
}

export default function ObjetsPersonnalisesPage() {
  const [objets, setObjets] = useState([])
  const [loading, setLoading] = useState(true)
  const [selection, setSelection] = useState(null)
  const [champs, setChamps] = useState([])
  const [busy, setBusy] = useState(false)

  const [draftObjet, setDraftObjet] = useState({ libelle: '', code: '', icone: '' })
  const [draftChamp, setDraftChamp] = useState({
    libelle: '', type: 'text', options: '', obligatoire: false, visible_liste: true,
  })

  const charger = useCallback(() => api.get('/custom-fields/objects/')
    .then((res) => setObjets(res.data?.results ?? res.data ?? []))
    .catch(() => toast.error('Impossible de charger les objets personnalisés.'))
    .finally(() => setLoading(false)), [])

  useEffect(() => { charger() }, [charger])

  // Champs de l'objet choisi — MÊME endpoint que les modules natifs.
  const chargerChamps = useCallback((objet) => {
    if (!objet) { setChamps([]); return Promise.resolve() }
    return customFieldsApi.getDefs(`custom:${objet.code}`)
      .then((res) => setChamps(res.data?.results ?? res.data ?? []))
      .catch(() => setChamps([]))
  }, [])

  const choisir = (objet) => {
    setSelection(objet)
    chargerChamps(objet)
  }

  const creerObjet = async () => {
    const libelle = draftObjet.libelle.trim()
    const code = slugify(draftObjet.code || libelle)
    if (!libelle || !code) return
    setBusy(true)
    try {
      const res = await api.post('/custom-fields/objects/', {
        code, libelle, icone: draftObjet.icone.trim(), actif: true,
      })
      setDraftObjet({ libelle: '', code: '', icone: '' })
      await charger()
      if (res.data?.id) choisir(res.data)
    } catch (e) {
      toast.error(messageErreur(e, "Création de l'objet impossible."))
    } finally { setBusy(false) }
  }

  const basculerObjet = async (objet) => {
    try {
      await api.patch(`/custom-fields/objects/${objet.id}/`, { actif: !objet.actif })
      charger()
    } catch (e) { toast.error(messageErreur(e, 'Modification impossible.')) }
  }

  const supprimerObjet = async (objet) => {
    if (!window.confirm(`Supprimer l'objet « ${objet.libelle} » et ses enregistrements ?`)) return
    try {
      await api.delete(`/custom-fields/objects/${objet.id}/`)
      if (selection?.id === objet.id) { setSelection(null); setChamps([]) }
      charger()
    } catch (e) { toast.error(messageErreur(e, 'Suppression impossible.')) }
  }

  const ajouterChamp = async () => {
    const libelle = draftChamp.libelle.trim()
    if (!libelle || !selection) return
    setBusy(true)
    try {
      await customFieldsApi.saveDef(null, {
        module: `custom:${selection.code}`,
        code: slugify(libelle),
        libelle,
        type: draftChamp.type,
        obligatoire: draftChamp.obligatoire,
        visible_liste: draftChamp.visible_liste,
        options: draftChamp.type === 'choice'
          ? draftChamp.options.split(',').map((o) => o.trim()).filter(Boolean)
          : null,
      })
      setDraftChamp({
        libelle: '', type: 'text', options: '', obligatoire: false,
        visible_liste: true,
      })
      chargerChamps(selection)
    } catch (e) { toast.error(messageErreur(e, 'Ajout du champ impossible.')) }
    finally { setBusy(false) }
  }

  const supprimerChamp = async (champ) => {
    if (!window.confirm(`Supprimer le champ « ${champ.libelle} » ?`)) return
    try {
      await customFieldsApi.deleteDef(champ.id)
      chargerChamps(selection)
    } catch (e) { toast.error(messageErreur(e, 'Suppression impossible.')) }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[1100px] p-6">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-4 p-6">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Objets métier personnalisés
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Créez un objet métier sans code (registre de clés, visiteurs, matériel
          prêté…), ajoutez-lui des champs avec l'éditeur habituel, puis saisissez
          ses enregistrements sur un écran généré automatiquement.
        </p>
      </div>

      {/* ── Les objets de la société ─────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          {objets.length === 0 && (
            <EmptyState icon={Boxes} title="Aucun objet personnalisé"
              description="Créez votre premier objet métier ci-dessous."
              className="py-6" />
          )}

          <div className="flex flex-col gap-1.5">
            {objets.map((objet) => (
              <div key={objet.id} data-testid={`objet-${objet.code}`}
                className={['flex flex-wrap items-center gap-1.5 rounded-lg border p-3',
                  selection?.id === objet.id ? 'border-primary' : 'border-border'].join(' ')}>
                <button type="button"
                  className="min-w-[140px] flex-[1_1_140px] text-left text-sm font-medium"
                  onClick={() => choisir(objet)}>
                  {objet.icone ? `${objet.icone} ` : ''}{objet.libelle}
                </button>
                <Badge tone="neutral">{objet.code}</Badge>
                <div className="ml-auto flex items-center gap-1">
                  <Button asChild size="sm" variant="outline">
                    <Link to={`/objets/${objet.code}`}>
                      Enregistrements
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                  </Button>
                  <Button type="button" size="sm"
                    variant={objet.actif ? 'success' : 'secondary'}
                    onClick={() => basculerObjet(objet)}>
                    {objet.actif ? 'Actif' : 'Inactif'}
                  </Button>
                  <IconButton size="sm" variant="outline" label="Supprimer l'objet"
                    className="text-destructive hover:text-destructive"
                    onClick={() => supprimerObjet(objet)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 rounded-lg border border-dashed border-border p-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <Input className="min-w-[180px] flex-[2_1_180px]"
                placeholder="Libellé de l'objet (ex. Registre de clés)"
                value={draftObjet.libelle}
                onChange={(e) => setDraftObjet((d) => ({ ...d, libelle: e.target.value }))} />
              <Input className="min-w-[140px] flex-[1_1_140px]"
                placeholder="Code (auto si vide)"
                value={draftObjet.code}
                onChange={(e) => setDraftObjet((d) => ({ ...d, code: e.target.value }))} />
              <Input className="w-[90px]" placeholder="Icône"
                maxLength={8}
                value={draftObjet.icone}
                onChange={(e) => setDraftObjet((d) => ({ ...d, icone: e.target.value }))} />
              <Button type="button" onClick={creerObjet} disabled={busy}>
                <Plus className="size-4" aria-hidden="true" /> Créer l'objet
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Champs de l'objet choisi (éditeur EXISTANT, pointé sur l'objet) ─ */}
      {selection && (
        <Card>
          <CardContent className="pt-4 sm:pt-5">
            <h3 className="mb-1 text-sm font-semibold tracking-tight text-foreground">
              Champs de « {selection.libelle} »
            </h3>
            <p className="mb-3 text-[11.5px] text-muted-foreground">
              Ces champs sont gérés par le même mécanisme que les champs
              personnalisés des fiches natives (module{' '}
              <code>custom:{selection.code}</code>) : mêmes types, même
              validation côté serveur. Les champs marqués « visible en liste »
              deviennent des colonnes de l'écran des enregistrements.
            </p>

            {champs.length === 0 && (
              <EmptyState title="Aucun champ pour cet objet"
                description="Ajoutez un champ ci-dessous pour composer son formulaire."
                className="py-6" />
            )}

            <div className="flex flex-col gap-1.5">
              {champs.map((champ) => (
                <div key={champ.id} data-testid={`champ-${champ.code}`}
                  className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border p-3">
                  <span className="min-w-[140px] flex-[1_1_140px] text-sm font-medium">
                    {champ.libelle}
                  </span>
                  <Badge tone="neutral">{champ.code}</Badge>
                  <Badge tone="info">
                    {TYPES_CHAMP.find(([v]) => v === champ.type)?.[1] ?? champ.type}
                  </Badge>
                  {champ.obligatoire && <Badge tone="warning">Obligatoire</Badge>}
                  {champ.visible_liste && <Badge tone="success">En liste</Badge>}
                  <div className="ml-auto flex items-center gap-1">
                    <IconButton size="sm" variant="outline" label="Supprimer le champ"
                      className="text-destructive hover:text-destructive"
                      onClick={() => supprimerChamp(champ)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 rounded-lg border border-dashed border-border p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <Input className="min-w-[160px] flex-[2_1_160px]"
                  placeholder="Libellé du champ"
                  value={draftChamp.libelle}
                  onChange={(e) => setDraftChamp((c) => ({ ...c, libelle: e.target.value }))} />
                <div className="min-w-[140px] flex-1">
                  <Select value={draftChamp.type}
                    onValueChange={(v) => setDraftChamp((c) => ({ ...c, type: v }))}>
                    <SelectTrigger aria-label="Type du champ"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TYPES_CHAMP.map(([v, label]) => (
                        <SelectItem key={v} value={v}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {draftChamp.type === 'choice' && (
                  <Input className="min-w-[160px] flex-[1_1_160px]"
                    placeholder="Options séparées par des virgules"
                    value={draftChamp.options}
                    onChange={(e) => setDraftChamp((c) => ({ ...c, options: e.target.value }))} />
                )}
                <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <input type="checkbox" checked={draftChamp.obligatoire}
                    onChange={(e) => setDraftChamp((c) => ({ ...c, obligatoire: e.target.checked }))} />
                  Obligatoire
                </label>
                <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <input type="checkbox" checked={draftChamp.visible_liste}
                    onChange={(e) => setDraftChamp((c) => ({ ...c, visible_liste: e.target.checked }))} />
                  Visible en liste
                </label>
                <Button type="button" onClick={ajouterChamp} disabled={busy}>
                  <Plus className="size-4" aria-hidden="true" /> Ajouter le champ
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
