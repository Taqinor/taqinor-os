import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { Users, UserMinus, LogOut, Check, Pencil, Mail, Download } from 'lucide-react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  Button, Input, Label, MultiSelect, Avatar, AvatarFallback, initials,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import messagesApi from '../../api/messagesApi'
import { toastError, toastSuccess } from '../../lib/toast'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import { upsertConversation } from './store/messagingSlice'
import { displayName } from './time'

/* S20 — Gestion des membres d'un canal via un Sheet latéral. Un admin du canal
   peut le renommer, ajouter / retirer des membres ; tout membre peut quitter.
   `isAdmin` est fourni par l'appelant (rôle dans la conversation).

   WIR157 / XKB32/ZCTR12 — panneau de canal étendu, réservé aux admins du
   canal (`isAdmin`) : alias e-mail entrant (canal-comme-liste-de-diffusion,
   NO-OP sans clé mail configurée côté serveur — le champ reste un simple
   libellé) et export intégral de la conversation (JSON/CSV, traçabilité
   CNDP loi 09-08). */
export default function ManageMembers({ open, onOpenChange, conversation, currentUserId, isAdmin, onLeft }) {
  const dispatch = useDispatch()
  const [name, setName] = useState('')
  const [editingName, setEditingName] = useState(false)
  const [toAdd, setToAdd] = useState([])
  const [options, setOptions] = useState([])
  const [busy, setBusy] = useState(false)
  const [alias, setAlias] = useState('')
  const [editingAlias, setEditingAlias] = useState(false)
  const [aliasSaving, setAliasSaving] = useState(false)
  const [exporting, setExporting] = useState(false)

  const members = conversation?.members ?? []
  const memberIds = new Set(members.map((m) => m.id))

  useEffect(() => {
    if (!open) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialiser le formulaire à l'ouverture du Sheet
    setName(conversation?.name ?? '')
    setEditingName(false)
    setToAdd([])
    setAlias(conversation?.alias_email ?? '')
    setEditingAlias(false)
    let alive = true
    messagesApi.listCompanyMembers()
      .then((r) => {
        if (!alive) return
        const users = r.data?.results ?? r.data ?? []
        setOptions(
          users
            .filter((u) => !memberIds.has(u.id))
            .map((u) => ({ value: String(u.id), label: displayName(u) || `#${u.id}` })),
        )
      })
      .catch(() => { if (alive) setOptions([]) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, conversation?.id])

  const refresh = async () => {
    try {
      const res = await messagesApi.getConversation(conversation.id)
      dispatch(upsertConversation(res.data))
    } catch { /* le prochain poll rafraîchira */ }
  }

  const rename = async () => {
    if (!name.trim()) return
    setBusy(true)
    try {
      await messagesApi.updateConversation(conversation.id, { name: name.trim() })
      dispatch(upsertConversation({ id: conversation.id, name: name.trim() }))
      setEditingName(false)
      toastSuccess('Canal renommé')
    } catch (err) {
      toastError(err.response?.data?.detail || 'Renommage impossible')
    } finally {
      setBusy(false)
    }
  }

  const addMembers = async () => {
    if (!toAdd.length) return
    setBusy(true)
    try {
      await messagesApi.addMembers(conversation.id, toAdd.map(Number))
      setToAdd([])
      await refresh()
      toastSuccess('Membres ajoutés')
    } catch (err) {
      toastError(err.response?.data?.detail || 'Ajout impossible')
    } finally {
      setBusy(false)
    }
  }

  const removeMember = async (userId) => {
    setBusy(true)
    try {
      await messagesApi.removeMember(conversation.id, userId)
      await refresh()
    } catch (err) {
      toastError(err.response?.data?.detail || 'Retrait impossible')
    } finally {
      setBusy(false)
    }
  }

  const leave = async () => {
    setBusy(true)
    try {
      await messagesApi.leaveConversation(conversation.id)
      onOpenChange?.(false)
      onLeft?.(conversation.id)
    } catch (err) {
      toastError(err.response?.data?.detail || 'Impossible de quitter')
    } finally {
      setBusy(false)
    }
  }

  // WIR157 / ZCTR12 — pose/lève l'alias e-mail du canal (vide = lever).
  const saveAlias = async () => {
    setAliasSaving(true)
    try {
      await messagesApi.setChannelAlias(conversation.id, alias.trim())
      dispatch(upsertConversation({ id: conversation.id, alias_email: alias.trim() }))
      setEditingAlias(false)
      toastSuccess(alias.trim() ? 'Alias e-mail enregistré' : 'Alias e-mail retiré')
    } catch (err) {
      toastError(err.response?.data?.detail || 'Alias impossible à enregistrer')
    } finally {
      setAliasSaving(false)
    }
  }

  // WIR157 / XKB32 — export intégral de la conversation (JSON ou CSV).
  const exportConv = async (format) => {
    setExporting(true)
    try {
      const res = await messagesApi.exportConversation(conversation.id, format)
      downloadBlob(res.data, stampedFilename(`conversation-${conversation.id}`, format))
    } catch (err) {
      toastError(err.response?.data?.detail || 'Export impossible')
    } finally {
      setExporting(false)
    }
  }

  if (!conversation) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>
            <Users aria-hidden="true" className="inline size-5 align-text-bottom" /> Membres du canal
          </SheetTitle>
          <SheetDescription>{members.length} membre(s)</SheetDescription>
        </SheetHeader>

        {isAdmin && (
          <div className="mt-4 grid gap-1.5">
            <Label htmlFor="msg-rename">Nom du canal</Label>
            <div className="flex items-center gap-2">
              <Input
                id="msg-rename"
                value={name}
                onChange={(e) => { setName(e.target.value); setEditingName(true) }}
              />
              <Button size="sm" onClick={rename} loading={busy} disabled={!editingName || !name.trim()}
                      aria-label="Renommer">
                <Pencil aria-hidden="true" /> Renommer
              </Button>
            </div>
          </div>
        )}

        <ul className="mt-4 flex flex-col gap-1" aria-label="Liste des membres">
          {members.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-accent">
              <span className="flex items-center gap-2">
                <Avatar className="size-7">
                  <AvatarFallback>{initials(displayName(m)) || '?'}</AvatarFallback>
                </Avatar>
                <span className="text-sm">
                  {displayName(m)}
                  {m.id === currentUserId && ' (moi)'}
                  {m.is_admin && <Check aria-hidden="true" className="ml-1 inline size-3 text-primary" />}
                </span>
              </span>
              {isAdmin && m.id !== currentUserId && (
                <Button variant="ghost" size="sm" onClick={() => removeMember(m.id)}
                        aria-label={`Retirer ${displayName(m)}`} disabled={busy}>
                  <UserMinus aria-hidden="true" />
                </Button>
              )}
            </li>
          ))}
        </ul>

        {isAdmin && (
          <div className="mt-4 grid gap-1.5">
            <Label htmlFor="msg-add-members">Ajouter des membres</Label>
            <MultiSelect
              id="msg-add-members"
              options={options}
              value={toAdd}
              onChange={setToAdd}
              placeholder="Choisir…"
            />
            <Button size="sm" onClick={addMembers} loading={busy} disabled={!toAdd.length}>
              Ajouter
            </Button>
          </div>
        )}

        {/* WIR157 / ZCTR12 — alias e-mail entrant du canal. */}
        {isAdmin && (
          <div className="mt-4 grid gap-1.5">
            <Label htmlFor="msg-alias-email">
              <Mail aria-hidden="true" className="inline size-3.5 align-text-bottom" /> Alias e-mail entrant
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id="msg-alias-email"
                type="email"
                value={alias}
                placeholder="canal@exemple.ma"
                onChange={(e) => { setAlias(e.target.value); setEditingAlias(true) }}
              />
              <Button size="sm" onClick={saveAlias} loading={aliasSaving}
                      disabled={!editingAlias} aria-label="Enregistrer l’alias">
                Enregistrer
              </Button>
            </div>
          </div>
        )}

        {/* WIR157 / XKB32 — export intégral de la conversation (admin). */}
        {isAdmin && (
          <div className="mt-4 grid gap-1.5">
            <Label>Exporter la conversation</Label>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" onClick={() => exportConv('json')} loading={exporting}>
                <Download aria-hidden="true" /> JSON
              </Button>
              <Button size="sm" variant="ghost" onClick={() => exportConv('csv')} loading={exporting}>
                <Download aria-hidden="true" /> CSV
              </Button>
            </div>
          </div>
        )}

        <div className="mt-6">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" className="text-destructive" disabled={busy}>
                <LogOut aria-hidden="true" /> Quitter le canal
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Quitter ce canal ?</AlertDialogTitle>
                <AlertDialogDescription>
                  Vous ne recevrez plus les messages de ce canal. Vous pourrez y être réinvité.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annuler</AlertDialogCancel>
                <AlertDialogAction onClick={leave}>Quitter</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </SheetContent>
    </Sheet>
  )
}
