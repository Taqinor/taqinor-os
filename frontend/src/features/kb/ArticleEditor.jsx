import { useRef, useState } from 'react'
import { ArrowLeft, Save, Send } from 'lucide-react'
import { Button, Input, Textarea, Label, toast } from '../../ui'
import { isDirty } from '../../ui/form-utils'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'
import kbApi from '../../api/kbApi'
import { KB_STATUT_MAP } from './kbStatus'
import FilterSelect from './FilterSelect'
import AiWritingToolbar from './AiWritingToolbar'
import CustomFieldsInput from '../../components/CustomFieldsInput'
import BlocInsertPicker from './BlocInsertPicker'

/* ============================================================================
   UX43 — Éditeur d'article (création + édition, brouillon → publié).
   ----------------------------------------------------------------------------
   Réservé aux paliers responsable/admin (gaté en amont par KbPage). ``statut``
   est un champ éditable ; la publication passe aussi par l'action ``publier``
   (fige une version). Aucune donnée sensible : que du contenu éditorial.
   ========================================================================== */

const STATUT_OPTIONS = Object.entries(KB_STATUT_MAP).map(([value, v]) => ({
  value, label: v.label,
}))

// XKB9 — visibilité (section) de l'article. ``workspace`` = comportement
// historique (visible de tous les paliers autorisés, sous réserve des ACL).
const VISIBILITE_OPTIONS = [
  { value: 'workspace', label: 'Espace de travail' },
  { value: 'prive', label: 'Privé' },
  { value: 'partage', label: 'Partagé' },
]

export default function ArticleEditor({ article, onCancel, onSaved }) {
  const isEdit = !!article?.id
  const [form, setForm] = useState({
    titre: article?.titre ?? '',
    corps: article?.corps ?? '',
    categorie: article?.categorie ?? '',
    tags: article?.tags ?? '',
    statut: article?.statut ?? 'brouillon',
    visibilite: article?.visibilite ?? 'workspace',
    emoji: article?.emoji ?? '',
    proprietes: article?.proprietes ?? {},
  })
  const [saving, setSaving] = useState(false)
  const corpsRef = useRef(null)
  // VX169 — garde de navigation IN-APP (snapshot pris au montage).
  const [initialSnapshot] = useState(() => form)
  const dirty = isDirty(initialSnapshot, form)
  useNavigationGuard(dirty)

  const set = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e?.target ? e.target.value : e }))

  const save = async ({ publish = false } = {}) => {
    if (!form.titre.trim()) {
      toast.error('Le titre est requis.')
      return
    }
    setSaving(true)
    try {
      const payload = { ...form }
      let saved
      if (isEdit) {
        saved = (await kbApi.updateArticle(article.id, payload)).data
      } else {
        saved = (await kbApi.createArticle(payload)).data
      }
      if (publish && saved?.id && saved.statut !== 'publie') {
        await kbApi.publier(saved.id)
      }
      toast.success(publish ? 'Article publié.' : 'Article enregistré.')
      onSaved?.(saved)
    } catch {
      toast.error('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page flex flex-col gap-4">
      <button
        type="button"
        onClick={onCancel}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Retour à la liste
      </button>

      <h1 className="font-display text-xl font-semibold tracking-tight">
        {isEdit ? 'Éditer l’article' : 'Nouvel article'}
      </h1>

      <form
        noValidate
        onSubmit={(e) => { e.preventDefault(); save() }}
        className="flex max-w-3xl flex-col gap-4"
      >
        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-1.5">
            {/* ZGED10 — emoji court affiché dans l'arbre + en tête de fiche. */}
            <Label htmlFor="kb-emoji">Emoji</Label>
            <Input
              id="kb-emoji" value={form.emoji} onChange={set('emoji')}
              maxLength={8} placeholder="📘" className="w-16 text-center"
            />
          </div>
          <div className="flex flex-1 flex-col gap-1.5">
            <Label htmlFor="kb-titre">Titre</Label>
            <Input id="kb-titre" value={form.titre} onChange={set('titre')} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="kb-categorie">Catégorie</Label>
            <Input id="kb-categorie" value={form.categorie} onChange={set('categorie')} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="kb-tags">Tags (séparés par virgule)</Label>
            <Input id="kb-tags" value={form.tags} onChange={set('tags')} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="kb-statut">Statut</Label>
            <FilterSelect
              id="kb-statut"
              value={form.statut}
              onChange={set('statut')}
              options={STATUT_OPTIONS}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="kb-visibilite">Visibilité</Label>
            <FilterSelect
              id="kb-visibilite"
              value={form.visibilite}
              onChange={set('visibilite')}
              options={VISIBILITE_OPTIONS}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="kb-corps">Contenu</Label>
          {/* XKB23 — assistant IA d'écriture & résumé : générer/reformuler/
              corriger/traduire FR↔AR/résumer, key-gated (dégrade proprement
              sans clé LLM, cf. AiWritingToolbar). */}
          <AiWritingToolbar
            textareaRef={corpsRef}
            corps={form.corps}
            disabled={saving}
            onApply={(next) => setForm((f) => ({ ...f, corps: next }))}
          />
          {/* ZGED12 — insertion d'un bloc réutilisable au curseur. */}
          <BlocInsertPicker
            textareaRef={corpsRef}
            corps={form.corps}
            disabled={saving}
            onApply={(next) => setForm((f) => ({ ...f, corps: next }))}
          />
          <Textarea id="kb-corps" ref={corpsRef} rows={12} value={form.corps} onChange={set('corps')} />
        </div>

        {/* ZGED11 — propriétés personnalisées (module kb_article, hérite du
            parent — résolution côté selector, non dupliquée ici). */}
        <CustomFieldsInput
          module="kb_article"
          value={form.proprietes}
          onChange={(next) => setForm((f) => ({ ...f, proprietes: next }))}
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={saving}>
            <Save /> {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
          {form.statut !== 'publie' && (
            <Button
              type="button"
              variant="outline"
              disabled={saving}
              onClick={() => save({ publish: true })}
            >
              <Send /> Enregistrer et publier
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>
            Annuler
          </Button>
        </div>
      </form>
    </div>
  )
}
