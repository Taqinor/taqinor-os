// Onglet « Clients » de la page Paramètres.
// L791 — remplace l'ancien texte placeholder « apparaîtront ici » par une vraie
// gestion des champs personnalisés des fiches clients (module « client »).
// Manager autonome bâti sur le même customFieldsApi que la carte « Avancé » :
// lister / ajouter / activer-désactiver / supprimer les champs du module client.
// Le ré-ordonnancement et l'édition fine restent dans l'onglet Avancé (évite de
// dupliquer l'éditeur complet) — un repère le rappelle.
import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from '../../ui/confirm'
import customFieldsApi from '../../api/customFieldsApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Switch, Checkbox,
  EmptyState, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

const TYPE_LABELS = {
  text: 'Texte', number: 'Nombre', date: 'Date',
  choice: 'Choix', boolean: 'Oui/Non',
}

// Slug du code (clé JSON) — même règle que la carte Avancé (sans accents).
const slugifyCode = (s) => s.trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50)

// Message d'erreur serveur lisible (detail, ou première erreur de champ FR).
const cfErr = (e, fallback) => {
  const d = e?.response?.data
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (d.detail) return d.detail
  const first = Object.values(d)[0]
  return Array.isArray(first) ? first[0] : (first || fallback)
}

const blankDraft = () => ({
  libelle: '', type: 'text', options: '', obligatoire: false,
  visible_liste: false,
})

export default function ClientsSection() {
  const [defs, setDefs] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState(blankDraft)

  // `loading` démarre à true ; on ne (re)déclenche le spinner que sur les
  // rechargements explicites, jamais en synchrone dans l'effet (évite les
  // rendus en cascade signalés par react-hooks/set-state-in-effect).
  const load = () => {
    customFieldsApi.getDefs('client')
      .then(r => setDefs(r.data.results ?? r.data ?? []))
      .catch(() => setDefs([]))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const addCf = async () => {
    const libelle = draft.libelle.trim()
    if (!libelle) return
    setBusy(true)
    try {
      await customFieldsApi.saveDef(null, {
        module: 'client', code: slugifyCode(libelle), libelle, type: draft.type,
        obligatoire: draft.obligatoire, visible_liste: draft.visible_liste,
        options: draft.type === 'choice'
          ? draft.options.split(',').map(o => o.trim()).filter(Boolean) : null,
      })
      setDraft(blankDraft())
      load()
    } catch (e) { toast.error(cfErr(e, 'Ajout impossible.')) }
    finally { setBusy(false) }
  }

  const toggleActif = async (d) => {
    try {
      await customFieldsApi.saveDef(d.id, { actif: !d.actif })
      load()
    } catch (e) { toast.error(cfErr(e, 'Modification impossible.')) }
  }

  const delCf = async (d) => {
    if (!window.confirm(`Supprimer le champ « ${d.libelle} » ?`)) return
    try { await customFieldsApi.deleteDef(d.id); load() }
    catch (e) { toast.error(cfErr(e, 'Suppression impossible.')) }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Champs personnalisés des fiches clients" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Ajoutez vos propres champs aux fiches clients (ICE, mentions légales
          B2B, segment commercial…). Ils apparaissent dans le formulaire client ;
          rien n'est perdu si vous désactivez ou retirez un champ. Le
          ré-ordonnancement et l'édition fine se font dans l'onglet
          <strong> Avancé</strong> (module « Clients »).
        </p>

        {loading ? (
          <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
            <Spinner className="size-4 text-primary" /> Chargement…
          </div>
        ) : defs.length === 0 ? (
          <div className="mb-2">
            <EmptyState
              title="Aucun champ client pour l'instant"
              description="Ajoutez un champ ci-dessous pour l'afficher sur les fiches clients." />
          </div>
        ) : (
          <div className="mb-2">
            {defs.map((d) => (
              <div key={d.id}
                   className={`mb-1.5 flex items-center gap-1.5 ${d.actif ? '' : 'opacity-50'}`}>
                <span className="flex-1 text-sm text-foreground">
                  {d.libelle}{d.obligatoire ? ' *' : ''}
                </span>
                {d.visible_liste && <Badge tone="outline">Liste</Badge>}
                <span className="text-[11px] text-muted-foreground">
                  {TYPE_LABELS[d.type] ?? d.type}
                </span>
                <Switch checked={!!d.actif} onCheckedChange={() => toggleActif(d)}
                        aria-label={d.actif ? 'Désactiver le champ' : 'Réactiver le champ'} />
                <IconButton size="md" variant="outline" label="Supprimer le champ"
                            className="text-destructive hover:text-destructive"
                            onClick={() => delCf(d)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5">
          <Input className="min-w-[140px] flex-[1_1_140px]" placeholder="Libellé du champ"
                 value={draft.libelle}
                 onChange={e => setDraft(c => ({ ...c, libelle: e.target.value }))}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCf() } }} />
          <div className="w-[120px]">
            <Select value={draft.type}
                    onValueChange={v => setDraft(c => ({ ...c, type: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="text">Texte</SelectItem>
                <SelectItem value="number">Nombre</SelectItem>
                <SelectItem value="date">Date</SelectItem>
                <SelectItem value="choice">Choix</SelectItem>
                <SelectItem value="boolean">Oui/Non</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {draft.type === 'choice' && (
            <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Options (a, b, c)"
                   value={draft.options}
                   onChange={e => setDraft(c => ({ ...c, options: e.target.value }))} />
          )}
          <label className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <Checkbox checked={!!draft.obligatoire}
                      onCheckedChange={v => setDraft(c => ({ ...c, obligatoire: !!v }))} />
            Obligatoire
          </label>
          <label className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <Checkbox checked={!!draft.visible_liste}
                      onCheckedChange={v => setDraft(c => ({ ...c, visible_liste: !!v }))} />
            Visible en liste
          </label>
          <Button type="button" loading={busy} disabled={busy || !draft.libelle.trim()}
                  onClick={addCf}>
            <Plus className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
