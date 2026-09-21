import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { MessageSquarePlus, Hash, User } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Input, Label, Segmented, MultiSelect, Avatar, AvatarFallback, initials,
} from '../../ui'
import messagesApi from '../../api/messagesApi'
import { toastError } from '../../lib/toast'
import { upsertConversation, setActiveConversation } from './store/messagingSlice'
import { displayName } from './time'

/* S20 — Flux de création : démarrer un DM ou créer un canal nommé avec membres.
   Construit sur Dialog + Segmented + MultiSelect (@/ui). Aucune dépendance
   nouvelle. À la création, la conversation est insérée dans le store et activée
   (onCreated remonte l'id au parent pour ouvrir le fil). */
export default function NewConversation({ open, onOpenChange, onCreated }) {
  const dispatch = useDispatch()
  const [kind, setKind] = useState('dm')
  const [members, setMembers] = useState([]) // ids
  const [dmTarget, setDmTarget] = useState('')
  const [name, setName] = useState('')
  const [options, setOptions] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    let alive = true
    messagesApi.listCompanyMembers()
      .then((r) => {
        if (!alive) return
        const users = r.data?.results ?? r.data ?? []
        setOptions(users.map((u) => ({ value: String(u.id), label: displayName(u) || `#${u.id}` })))
      })
      .catch(() => { if (alive) setOptions([]) })
    return () => { alive = false }
  }, [open])

  const reset = () => {
    setKind('dm'); setMembers([]); setDmTarget(''); setName('')
  }

  const close = (v) => {
    if (!v) reset()
    onOpenChange?.(v)
  }

  const submit = async () => {
    setSaving(true)
    try {
      let payload
      if (kind === 'dm') {
        if (!dmTarget) { setSaving(false); return }
        payload = { kind: 'dm', member_ids: [Number(dmTarget)] }
      } else {
        if (!name.trim()) { setSaving(false); return }
        payload = { kind: 'channel', name: name.trim(), member_ids: members.map(Number) }
      }
      const res = await messagesApi.createConversation(payload)
      const conv = res.data
      dispatch(upsertConversation(conv))
      if (conv?.id != null) {
        dispatch(setActiveConversation(conv.id))
        onCreated?.(conv.id)
      }
      reset()
      onOpenChange?.(false)
    } catch (err) {
      toastError(err.response?.data?.detail || 'Création impossible')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <MessageSquarePlus aria-hidden="true" className="inline size-5 align-text-bottom" />{' '}
            Nouvelle conversation
          </DialogTitle>
          <DialogDescription>
            Démarrez une discussion privée ou créez un canal d’équipe.
          </DialogDescription>
        </DialogHeader>

        <Segmented
          value={kind}
          onChange={setKind}
          options={[
            { value: 'dm', label: 'Message privé', icon: User },
            { value: 'channel', label: 'Canal', icon: Hash },
          ]}
          aria-label="Type de conversation"
        />

        {kind === 'dm' ? (
          <div className="grid gap-1.5">
            <Label htmlFor="msg-dm-target">Destinataire</Label>
            <MultiSelect
              id="msg-dm-target"
              options={options}
              value={dmTarget ? [dmTarget] : []}
              onChange={(vals) => setDmTarget(vals[vals.length - 1] || '')}
              maxTokens={1}
              placeholder="Choisir un collègue…"
            />
          </div>
        ) : (
          <>
            <div className="grid gap-1.5">
              <Label htmlFor="msg-channel-name">Nom du canal</Label>
              <Input
                id="msg-channel-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ex. Chantiers Casablanca"
                leading={<Hash aria-hidden="true" />}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="msg-channel-members">Membres</Label>
              <MultiSelect
                id="msg-channel-members"
                options={options}
                value={members}
                onChange={setMembers}
                placeholder="Ajouter des membres…"
              />
            </div>
            {members.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {members.map((id) => {
                  const opt = options.find((o) => o.value === id)
                  return (
                    <Avatar key={id} className="size-6" title={opt?.label}>
                      <AvatarFallback>{initials(opt?.label) || '?'}</AvatarFallback>
                    </Avatar>
                  )
                })}
              </div>
            )}
          </>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => close(false)}>Annuler</Button>
          <Button
            onClick={submit}
            loading={saving}
            disabled={kind === 'dm' ? !dmTarget : !name.trim()}
          >
            {kind === 'dm' ? 'Démarrer' : 'Créer le canal'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
