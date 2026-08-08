// PACT96 — Comptes portail (accès client) : administration ERP de
// `apps.portail.ComptePortailClient`. Le compte porte le jeton d'accès et le
// statut actif d'un client ; `provisionner-acces` (IsAdminRole, plus strict
// que la liste/le CRUD IsResponsableOrAdmin) crée le VRAI compte utilisateur
// portail — mot de passe temporaire envoyé par email, jamais renvoyé ici.
// « jamais de réactivation silencieuse d'un compte révoqué » (docstring
// serveur) : cet écran ne fait QUE relayer l'action serveur, aucune logique
// de réactivation côté client.
import { useEffect, useState } from 'react'
import { Plus, KeyRound } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import crmApi from '../../../api/crmApi'
import {
  Button, Card, EmptyState, Skeleton, Switch, Select, SelectTrigger,
  SelectValue, SelectContent, SelectItem, Form, FormField, DataTable, toast,
} from '../../../ui'

const formatDateHeure = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR') : '—')

export default function ComptesPortailAdmin() {
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [clientChoisi, setClientChoisi] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return portailApi.admin.comptes.liste()
      .then((r) => setRows(r.data?.results ?? r.data ?? []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    crmApi.getClients().then((r) => setClients(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const creer = async () => {
    if (!clientChoisi) return
    try {
      await portailApi.admin.comptes.creer({ client: clientChoisi })
      setClientChoisi('')
      toast.success('Compte portail créé')
      load()
    } catch (e) {
      toast.error(
        e?.response?.data?.client
        ?? e?.response?.data?.non_field_errors?.[0]
        ?? e?.response?.data?.detail
        ?? 'Création impossible.',
      )
    }
  }

  const toggleActif = async (row) => {
    setBusyId(row.id)
    try {
      await portailApi.admin.comptes.patch(row.id, { actif: !row.actif })
      load()
    } catch {
      toast.error('Bascule impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const provisionner = async (row) => {
    setBusyId(row.id)
    try {
      const r = await portailApi.admin.comptes.provisionnerAcces(row.id)
      toast.success(r.data?.detail ?? 'Accès provisionné')
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Provisionnement impossible.')
    } finally {
      setBusyId(null)
    }
  }

  const columns = [
    { id: 'client', header: 'Client', width: 160, accessor: (r) => `#${r.client}` },
    { id: 'email', header: 'Email', width: 200, accessor: (r) => r.email || '—' },
    {
      id: 'token', header: "Jeton d'accès", width: 220,
      cell: (_v, row) => <code className="text-xs">{row.token_acces}</code>,
      exportValue: (row) => row.token_acces || '',
    },
    {
      id: 'actif', header: 'Actif', width: 90, sortable: false,
      cell: (_v, row) => (
        <Switch checked={!!row.actif} disabled={busyId === row.id}
                onCheckedChange={() => toggleActif(row)}
                aria-label={`${row.actif ? 'Révoquer' : 'Activer'} le compte ${row.email || row.client}`} />
      ),
    },
    {
      id: 'derniere_connexion', header: 'Dernière connexion', width: 170,
      accessor: (r) => formatDateHeure(r.derniere_connexion),
    },
    {
      id: 'date_creation', header: 'Créé le', width: 170,
      accessor: (r) => formatDateHeure(r.date_creation),
    },
    {
      id: 'actions', header: '', width: 170, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (
        <Button variant="outline" size="sm" disabled={busyId === row.id}
                onClick={() => provisionner(row)}>
          <KeyRound /> Provisionner l'accès
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Un compte porte le jeton d'accès self-service d'un client. « Provisionner
        l'accès » crée le vrai compte utilisateur portail (mot de passe
        temporaire envoyé par email, jamais affiché ici). Révoquer un compte
        (bascule Actif) empêche sa prochaine connexion.
      </p>

      <Card className="p-4">
        <Form onSubmit={(e) => { e.preventDefault(); creer() }}
              className="grid items-end gap-3 sm:grid-cols-[2fr_auto]">
          <FormField label="Client">
            <Select value={clientChoisi ? String(clientChoisi) : '__none'}
                    onValueChange={(v) => setClientChoisi(v === '__none' ? '' : v)}>
              <SelectTrigger aria-label="Client"><SelectValue placeholder="— Client —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Client —</SelectItem>
                {clients.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <Button type="submit" disabled={!clientChoisi}><Plus /> Créer un compte</Button>
        </Form>
      </Card>

      {loading ? (
        <Card className="space-y-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </Card>
      ) : loadError ? (
        <EmptyState title="Chargement impossible"
                    description="Les comptes portail n'ont pas pu être chargés. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState title="Aucun compte portail"
                    description="Créez un compte pour un client ci-dessus." />
      ) : (
        <DataTable data={rows} columns={columns} getRowId={(r) => r.id}
                   searchable={false} exportName="comptes-portail" emptyTitle="Aucun compte portail" />
      )}
    </div>
  )
}
