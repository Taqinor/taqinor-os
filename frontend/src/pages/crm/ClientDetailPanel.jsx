import { useEffect, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import {
  Badge, Button, Spinner, RelationCounters,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { Table } from '../reporting/Table'
import ClientRgpdActions from './ClientRgpdActions'
import OwnerChain from '../../components/OwnerChain'
import OrgChartTab from './clients/OrgChartTab'
import { formatMAD } from '../../lib/format'
import { telHref, waHref } from '../../lib/contactLinks'

// Panneau détail client (L4) — lecture seule : devis, factures et chantiers
// liés au client, avec référence / statut / total (montants client-facing
// uniquement, jamais de prix d'achat ni de marge). Source : l'endpoint scopé
// société GET /crm/clients/<id>/documents/.

const formatDateFR = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')

function DocTable({ titre, rows, withTotal, withDate, emptyLabel, renderActions }) {
  // VX152 — un seul moteur de table : la fiche client rejoint le primitif `Table`
  // partagé (reporting) au lieu d'un troisième moteur `DocTable` maison.
  const columns = [
    { key: 'reference', header: 'Référence', cellClassName: 'font-medium', cell: (r) => r.reference || '—' },
    { key: 'statut', header: 'Statut', cell: (r) => <Badge tone="neutral">{r.statut || '—'}</Badge> },
    ...(withDate ? [{ key: 'date', header: 'Date', cell: (r) => formatDateFR(r.date) }] : []),
    ...(withTotal ? [{ key: 'total', header: 'Total TTC', align: 'right', cell: (r) => formatMAD(r.total_ttc) }] : []),
    // VX245(c) — colonne actions OPTIONNELLE (factures uniquement, pour
    // « Relancer par WhatsApp ») — jamais sur devis/chantiers.
    ...(renderActions ? [{ key: 'actions', header: '', align: 'right', cell: renderActions }] : []),
  ]
  return (
    <section className="mb-4">
      <h4 className="font-medium mb-2">
        {titre} <span className="count-badge">{rows.length}</span>
      </h4>
      {rows.length === 0 ? (
        <p className="text-muted-foreground">{emptyLabel}</p>
      ) : (
        <Table columns={columns} rows={rows} getRowKey={(r) => r.id} aria-label={titre} />
      )}
    </section>
  )
}

export default function ClientDetailPanel({ client, onClose, onNewDevis, onChanged }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // XSAL9 — rollup CA groupe (société mère + filiales). Best-effort : une
  // erreur de chargement n'empêche jamais le reste de la fiche de s'afficher.
  const [consolidation, setConsolidation] = useState(null)
  // VX245(c) — aperçu du rappel WhatsApp (facture en retard) avant ouverture
  // de wa.me — MÊME contrat que RelancesPage/FactureList (`whatsappFacture`,
  // jamais un 2ᵉ constructeur de message).
  const [waPreview, setWaPreview] = useState(null)
  const [waBusy, setWaBusy] = useState(false)

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setError(false)
    api.get(`/crm/clients/${client.id}/documents/`)
      .then((res) => { if (alive) setData(res.data) })
      .catch(() => { if (alive) setError(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [client.id])

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setConsolidation(null)
    api.get(`/crm/clients/${client.id}/consolidation/`)
      .then((res) => { if (alive) setConsolidation(res.data) })
      .catch(() => { /* best-effort — la fiche reste utilisable sans rollup */ })
    return () => { alive = false }
  }, [client.id])

  const nomComplet = [client.nom, client.prenom].filter(Boolean).join(' ')
  // VX108 — tap-to-call : le panneau n'affichait jusqu'ici aucun téléphone.
  const tel = telHref(client.telephone)
  const wa = waHref(client.whatsapp)

  // VX245(c) — construit le message « relance » côté serveur (même
  // constructeur que RelancesPage/FactureList) puis montre un aperçu avant
  // d'ouvrir wa.me. Jamais d'envoi automatique.
  const relancerWhatsApp = async (facture) => {
    setWaBusy(true)
    try {
      const res = await ventesApi.whatsappFacture(facture.id, { modele: 'relance', langue: 'fr' })
      setWaPreview({
        reference: facture.reference,
        message: res.data?.message ?? '',
        url: res.data?.url ?? '',
        wa_url: res.data?.wa_url ?? '',
      })
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusy(false)
    }
  }
  const ouvrirWhatsApp = () => {
    if (waPreview?.wa_url) window.open(waPreview.wa_url, '_blank', 'noopener')
    setWaPreview(null)
  }

  return (
    // VX182 — shell fait-main remplacé par ResponsiveDialog (Escape + focus-
    // trap + bottom-sheet mobile) ; en-tête/pied conservés à l'identique.
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Fiche client — {nomComplet || '—'}</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
        <div className="modal-body">
          {/* VX159/VX250 — RelationCounters : réutilise `data` déjà chargé
              (endpoint /crm/clients/<id>/documents/ ci-dessus) — ZÉRO appel
              réseau nouveau. Devis/factures pré-filtrent désormais la liste
              cible par nom (DevisList.jsx/FactureList.jsx lisent ?q=, VX250) ;
              chantiers reste un compteur statique (InstallationsPage.jsx hors
              périmètre de cette tâche — jamais un lien qui MENT sur un
              pré-filtre qu'il n'applique pas). */}
          {data && (
            <RelationCounters
              className="mb-4"
              counters={[
                { label: 'devis', count: data.devis?.length ?? 0, to: `/ventes/devis?q=${encodeURIComponent(nomComplet)}` },
                { label: 'factures', count: data.factures?.length ?? 0, to: `/ventes/factures?q=${encodeURIComponent(nomComplet)}` },
                { label: 'chantiers', count: data.chantiers?.length ?? 0 },
              ]}
            />
          )}
          {(tel || wa) && (
            <div className="mb-4 flex flex-wrap gap-3 text-sm">
              {tel && (
                <a className="link-blue" href={tel} title="Appeler">
                  ☎ {client.telephone}
                </a>
              )}
              {wa && (
                <a className="link-blue" href={wa} target="_blank" rel="noopener noreferrer" title="Ouvrir WhatsApp">
                  WhatsApp
                </a>
              )}
            </div>
          )}
          {/* WIR12 — onglet Organigramme (ContactClient) à côté des documents,
              chacun gardant son propre chargement (l'onglet Organigramme ne
              fetch qu'à l'activation, via son propre effect interne). */}
          <Tabs defaultValue="documents">
            <TabsList>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="organigramme">Organigramme</TabsTrigger>
            </TabsList>
            <TabsContent value="documents">
              {loading && (
                <p className="page-loading"><Spinner /> Chargement des documents…</p>
              )}
              {error && (
                <p className="page-error">
                  Impossible de charger les documents — réessayez.
                </p>
              )}
              {/* XSAL9 — hiérarchie de comptes : filiales + rollup CA groupe. */}
              {consolidation && consolidation.filiales.length > 0 && (
                <section className="mb-4">
                  <h4 className="font-medium mb-2">
                    Filiales <span className="count-badge">{consolidation.filiales.length}</span>
                  </h4>
                  <p className="text-sm mb-2">
                    CA groupe (devis) : <strong>{formatMAD(consolidation.ca_devis_total)}</strong>
                    {' · '}CA groupe (factures) : <strong>{formatMAD(consolidation.ca_factures_total)}</strong>
                  </p>
                  <ul className="text-sm">
                    {consolidation.filiales.map((f) => (
                      <li key={f.id}>{f.nom}</li>
                    ))}
                  </ul>
                </section>
              )}
              {client.parent_id != null && (
                <p className="text-sm text-muted-foreground mb-4">
                  Filiale de la société mère #{client.parent_id}.
                </p>
              )}
              {/* VX216(c) — chaîne de responsabilité, uniquement quand elle est
                  SANS AMBIGUÏTÉ (un client peut avoir plusieurs devis/chantiers —
                  on ne devine jamais lequel). L'endpoint fiche client n'expose ni
                  lead ni ticket SAV : chaîne partielle (Devis · Chantier), jamais
                  un lien inventé. */}
              {data && data.devis?.length === 1 && data.chantiers?.length === 1 && (
                <OwnerChain
                  className="mb-4"
                  devis={{ id: data.devis[0].id, nom: data.devis[0].reference }}
                  chantier={{ id: data.chantiers[0].id, nom: data.chantiers[0].reference }}
                />
              )}
              {data && (
                <>
                  <DocTable
                    titre="Devis"
                    rows={data.devis}
                    withTotal
                    withDate
                    emptyLabel="Aucun devis lié."
                  />
                  <DocTable
                    titre="Factures"
                    rows={data.factures}
                    withTotal
                    withDate
                    emptyLabel="Aucune facture liée."
                    renderActions={(f) => (
                      f.statut_key === 'en_retard' ? (
                        <Button size="sm" variant="outline" disabled={waBusy}
                                onClick={() => relancerWhatsApp(f)}
                                title="Relancer par WhatsApp">
                          <MessageCircle className="size-4" /> Relancer
                        </Button>
                      ) : null
                    )}
                  />
                  <DocTable
                    titre="Chantiers"
                    rows={data.chantiers}
                    emptyLabel="Aucun chantier lié."
                  />
                </>
              )}
            </TabsContent>
            <TabsContent value="organigramme">
              <OrgChartTab clientId={client.id} />
            </TabsContent>
          </Tabs>
        </div>
        <div className="modal-footer">
          {/* WR9/FG26 — export d'accès du sujet + anonymisation (gatés rôle). */}
          <ClientRgpdActions
            client={client}
            onChanged={() => { onChanged?.(); onClose() }}
          />
          <Button variant="outline" onClick={() => onNewDevis(client)}>
            Nouveau devis
          </Button>
          <Button onClick={onClose}>Fermer</Button>
        </div>
      {/* VX245(c) — Aperçu du rappel WhatsApp avant ouverture de wa.me (même
          patron que RelancesPage/FactureList — jamais un envoi automatique). */}
      <Dialog open={!!waPreview} onOpenChange={(o) => { if (!o) setWaPreview(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aperçu du rappel WhatsApp — {waPreview?.reference}</DialogTitle>
            <DialogDescription>Vérifiez le texte et le lien, puis ouvrez WhatsApp.</DialogDescription>
          </DialogHeader>
          <pre className="m-0 whitespace-pre-wrap break-words rounded-lg bg-muted p-3 text-sm"
               style={{ fontFamily: 'inherit' }}>
            {waPreview?.message}
          </pre>
          {waPreview?.url && (
            <p className="mt-2 break-words text-xs text-muted-foreground">
              Lien public : {waPreview.url}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setWaPreview(null)}>Annuler</Button>
            <Button type="button" variant="success" disabled={!waPreview?.wa_url}
                    onClick={ouvrirWhatsApp}>
              <MessageCircle /> Ouvrir WhatsApp
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ResponsiveDialog>
  )
}
