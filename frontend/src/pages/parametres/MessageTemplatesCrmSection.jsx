// FG36/XSAL17 — Modèles de messages CRM (crm.MessageTemplate), distincts des
// modèles WhatsApp de relance/devis/facture (parametres.MessageTemplate, voir
// MessagesSection.jsx). Admin CRUD minimal : nom, langue, corps + aperçu.
// XSAL17 — {lien_rdv} : résolu UNIQUEMENT côté serveur (render/) quand un
// lead_id est fourni ; ici on documente juste le placeholder disponible.
import { useEffect, useState } from 'react'
import { Plus, Trash2, Archive, ArchiveRestore } from 'lucide-react'
import {
  Card, CardContent, Input, Textarea, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Button, IconButton, Spinner,
} from '../../ui'
import { SectionTitle, Field } from './peComponents'
import crmApi from '../../api/crmApi'

// Placeholders disponibles au rendu (render_template, apps/crm/views.py) :
// {prenom}/{ville}/{lien} toujours substituables ; {lien_rdv} (XSAL17) exige
// un lead_id au moment du rendu — sans lui, le placeholder disparaît (no-op).
const PLACEHOLDERS = ['{prenom}', '{ville}', '{lien}', '{lien_rdv}']

const LANGUES = [
  { value: 'fr', label: 'Français' },
  { value: 'darija', label: 'Darija' },
]

export default function MessageTemplatesCrmSection() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [newNom, setNewNom] = useState('')

  const load = () => {
    setLoading(true)
    crmApi.getMessageTemplates()
      .then((r) => setTemplates(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les modèles.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const addTemplate = async () => {
    if (!newNom.trim()) return
    try {
      await crmApi.saveMessageTemplate(null, { nom: newNom.trim(), corps: '' })
      setNewNom('')
      load()
    } catch {
      setError('La création du modèle a échoué (nom déjà utilisé ?).')
    }
  }

  const patchTemplate = async (tpl, changes) => {
    await crmApi.saveMessageTemplate(tpl.id, changes).catch(() => {})
    load()
  }

  const archiveTemplate = (tpl) => patchTemplate(tpl, { archived: !tpl.archived })

  const delTemplate = async (tpl) => {
    if (!window.confirm(`Supprimer le modèle « ${tpl.nom} » ?`)) return
    await crmApi.deleteMessageTemplate(tpl.id).catch(() => {})
    load()
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Modèles de messages CRM" icon={<><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.38 8.38 0 0 1-4-1L3 21l1-5.5a8.38 8.38 0 0 1-1-4A8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Modèles réutilisables pour vos messages WhatsApp/SMS aux leads.
          Placeholders disponibles :
          {' '}{PLACEHOLDERS.map((p) => <code key={p} className="mr-1">{p}</code>)}
          {' '}— <code>{'{lien_rdv}'}</code> insère un lien de réservation de
          visite tokenisé, résolu au moment de l'envoi (nécessite un lead).
        </p>

        {loading && (
          <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
            <Spinner className="size-3.5 text-primary" /> Chargement…
          </div>
        )}
        {error && <p className="form-error mb-2" role="alert">{error}</p>}
        {!loading && templates.length === 0 && (
          <p className="mb-3 text-xs text-muted-foreground">Aucun modèle configuré.</p>
        )}

        {!loading && templates.map((t) => (
          <div key={t.id}
               className={['mb-3 rounded-lg border border-border p-3', t.archived ? 'opacity-50' : ''].join(' ')}>
            <div className="mb-2 flex items-center gap-1.5">
              <Input key={t.nom} className="flex-1" defaultValue={t.nom}
                     onBlur={(e) => {
                       if (e.target.value.trim() && e.target.value !== t.nom) {
                         patchTemplate(t, { nom: e.target.value.trim() })
                       }
                     }} />
              <Select value={t.langue} onValueChange={(v) => patchTemplate(t, { langue: v })}>
                <SelectTrigger className="w-[130px]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {LANGUES.map((l) => (
                    <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <IconButton size="md" variant="outline"
                          label={t.archived ? 'Réactiver' : 'Archiver'}
                          onClick={() => archiveTemplate(t)}>
                {t.archived
                  ? <ArchiveRestore className="size-4" aria-hidden="true" />
                  : <Archive className="size-4" aria-hidden="true" />}
              </IconButton>
              <IconButton size="md" variant="outline" label="Supprimer le modèle"
                          className="text-destructive hover:text-destructive"
                          onClick={() => delTemplate(t)}>
                <Trash2 className="size-4" aria-hidden="true" />
              </IconButton>
            </div>
            <Field label="Corps du message" htmlFor={`mtc-corps-${t.id}`}>
              <Textarea id={`mtc-corps-${t.id}`} className="min-h-[70px] resize-y"
                        defaultValue={t.corps}
                        onBlur={(e) => {
                          if (e.target.value !== t.corps) {
                            patchTemplate(t, { corps: e.target.value })
                          }
                        }} />
            </Field>
          </div>
        ))}

        <div className="mt-1.5 flex gap-1.5">
          <Input className="flex-1" placeholder="Nouveau modèle" value={newNom}
                 onChange={(e) => setNewNom(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTemplate() } }} />
          <Button type="button" onClick={addTemplate}><Plus className="size-4" aria-hidden="true" /></Button>
        </div>
      </CardContent>
    </Card>
  )
}
