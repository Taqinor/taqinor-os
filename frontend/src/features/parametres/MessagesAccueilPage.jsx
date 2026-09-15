import { useEffect, useMemo, useState } from 'react'
import { Sun, Trash2 } from 'lucide-react'
import api from '../../api/axios'
import notificationsApi from '../../api/notificationsApi'
import {
  Button, DataTable, EmptyState, FormField, FormErrorSummary, IconButton,
  Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner, Textarea,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
import { useConfirmDialog, toast } from '../../ui/confirm'
import MicDicteeButton from '../../components/MicDicteeButton'

/* MSGACC1 — Écran d'envoi des messages d'accueil (Paramètres, réservé
   Responsable/Admin — reflète IsAdminOrResponsableTier côté serveur).

   CE N'EST PAS UNE NOTIFICATION : posé pour UN destinataire précis, avec une
   date + heure de visibilité choisies ; il s'affiche en plein écran à
   l'ouverture de l'ERP du destinataire à partir de cette heure (modale
   `MessageAccueilModal`, montée dans main.jsx).

   Erreurs de champ (règle fondateur « le champ fautif, message exact ») :
   une 400 `{destinataire: […], visible_a_partir_de: […], corps: […]}`
   s'affiche SOUS le champ concerné ET dans un bandeau qui NOMME le(s)
   champ(s) en cause (`FormErrorSummary`) — jamais un message générique. */

const FIELD_LABELS = {
  destinataire: 'Destinataire',
  visible_a_partir_de: 'Date et heure',
  corps: 'Message',
}

function nouveauFormulaire() {
  return { destinataire: '', date: '', heure: '', corps: '' }
}

function dateHeureFr(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function MessagesAccueilPage() {
  const { confirmDelete } = useConfirmDialog()
  const [users, setUsers] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(nouveauFormulaire)
  const [saving, setSaving] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [erreurGenerale, setErreurGenerale] = useState('')

  const utilisateursActifs = useMemo(
    () => users.filter((u) => u.is_active),
    [users],
  )

  const recharger = () => notificationsApi.getMessagesAccueil()
    .then((r) => setMessages(r.data?.results ?? r.data ?? []))
    .catch(() => setMessages([]))

  useEffect(() => {
    let active = true
    Promise.all([api.get('/users/'), notificationsApi.getMessagesAccueil()])
      .then(([u, m]) => {
        if (!active) return
        setUsers(u.data?.results ?? u.data ?? [])
        setMessages(m.data?.results ?? m.data ?? [])
      })
      .catch(() => { if (active) { setUsers([]); setMessages([]) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setChamp = (champ, valeur) => {
    setForm((f) => ({ ...f, [champ]: valeur }))
    setErreurs((prev) => (prev[champ] ? { ...prev, [champ]: undefined } : prev))
  }

  const soumettre = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreurs({})
    setErreurGenerale('')
    const payload = {
      destinataire: form.destinataire ? Number(form.destinataire) : null,
      corps: form.corps,
    }
    if (form.date && form.heure) {
      const dt = new Date(`${form.date}T${form.heure}:00`)
      if (!Number.isNaN(dt.getTime())) payload.visible_a_partir_de = dt.toISOString()
    }
    try {
      await notificationsApi.createMessageAccueil(payload)
      toast.success('Message d’accueil créé.')
      setForm(nouveauFormulaire())
      recharger()
    } catch (err) {
      const data = err?.response?.data
      if (err?.response?.status === 400 && data && typeof data === 'object' && !Array.isArray(data)) {
        setErreurs(data)
      } else {
        setErreurGenerale('La création du message a échoué — réessayez.')
      }
    } finally {
      setSaving(false)
    }
  }

  const supprimer = async (message) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce message d’accueil ?',
      description: `Le message pour « ${message.destinataire_nom} » sera supprimé.`,
    })
    if (!ok) return
    try {
      await notificationsApi.deleteMessageAccueil(message.id)
      toast.success('Message supprimé.')
      recharger()
    } catch {
      toast.error('Suppression impossible — le message a peut-être déjà été lu.')
    }
  }

  const bandeauErreurs = Object.entries(erreurs)
    .filter(([, v]) => v)
    .map(([champ, msgs]) => {
      const msg = Array.isArray(msgs) ? msgs[0] : String(msgs)
      const libelle = FIELD_LABELS[champ] ?? champ
      return { field: `msgacc-${champ.replace(/_/g, '-')}`, message: `${libelle} : ${msg}` }
    })

  const colonnes = useMemo(() => [
    { id: 'destinataire', header: 'Destinataire', accessor: (r) => r.destinataire_nom },
    {
      id: 'visible', header: 'Prévu le', width: 170,
      accessor: (r) => dateHeureFr(r.visible_a_partir_de),
    },
    {
      id: 'statut', header: 'Statut', width: 150,
      accessor: (r) => (r.lu_le ? `Lu le ${dateHeureFr(r.lu_le)}` : 'Non lu'),
    },
    {
      id: 'actions', header: '', width: 60, align: 'right',
      accessor: () => '',
      cell: (v, r) => (r.lu_le ? null : (
        <IconButton variant="ghost" label="Supprimer" onClick={() => supprimer(r)}>
          <Trash2 />
        </IconButton>
      )),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- callbacks recréés par rendu
  ], [])

  return (
    <div className="page" data-testid="messages-accueil-page">
      <PageHeader
        title="Messages d’accueil"
        subtitle="Un bonjour ou une consigne pour un employé, affiché en plein écran dès l’heure choisie."
        icon={Sun}
      />

      <form onSubmit={soumettre} noValidate className="mb-6 flex flex-col gap-3 rounded-lg border border-border p-4">
        {bandeauErreurs.length > 0 && <FormErrorSummary errors={bandeauErreurs} />}
        <FormField
          label="Destinataire" required htmlFor="msgacc-destinataire"
          error={erreurs.destinataire?.[0]} errorKind="required"
        >
          <Select
            value={form.destinataire}
            onValueChange={(v) => setChamp('destinataire', v)}
          >
            <SelectTrigger id="msgacc-destinataire"><SelectValue placeholder="Choisir un employé…" /></SelectTrigger>
            <SelectContent>
              {utilisateursActifs.map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>

        <div className="flex gap-3">
          <div className="flex-1">
            <Label htmlFor="msgacc-date">Date</Label>
            <Input
              id="msgacc-date" type="date" value={form.date}
              onChange={(e) => setChamp('date', e.target.value)}
            />
          </div>
          <div className="flex-1">
            <Label htmlFor="msgacc-heure">Heure</Label>
            <Input
              id="msgacc-heure" type="time" value={form.heure}
              onChange={(e) => setChamp('heure', e.target.value)}
            />
          </div>
        </div>
        {erreurs.visible_a_partir_de?.[0] && (
          <p role="alert" className="text-xs text-destructive">{erreurs.visible_a_partir_de[0]}</p>
        )}

        <FormField
          label="Message" required htmlFor="msgacc-corps"
          error={erreurs.corps?.[0]} errorKind="required"
        >
          <div className="flex items-start gap-2">
            <Textarea
              id="msgacc-corps" rows={5} value={form.corps}
              onChange={(e) => setChamp('corps', e.target.value)}
              placeholder="Bonjour, …"
              className="flex-1"
            />
            <MicDicteeButton
              onTexte={(texte) => setChamp('corps', form.corps ? `${form.corps} ${texte}` : texte)}
            />
          </div>
        </FormField>

        {erreurGenerale && (
          <p role="alert" className="text-sm text-destructive">{erreurGenerale}</p>
        )}

        <div className="flex justify-end">
          <Button type="submit" loading={saving} disabled={saving || !form.destinataire || !form.corps}>
            Envoyer le message
          </Button>
        </div>
      </form>

      <h2 className="mb-3 text-sm font-semibold text-foreground">Messages envoyés</h2>
      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : messages.length === 0 ? (
        <EmptyState
          icon={Sun}
          title="Aucun message envoyé"
          description="Les messages que vous envoyez apparaissent ici, avec leur statut de lecture."
        />
      ) : (
        <DataTable
          data={messages}
          columns={colonnes}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Messages d’accueil envoyés"
        />
      )}
    </div>
  )
}
