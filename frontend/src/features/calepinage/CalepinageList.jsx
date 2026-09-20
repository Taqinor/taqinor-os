import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LayoutGrid, Plus, Search, X } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import crmApi from '../../api/crmApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  Badge, Button, Card, Combobox, EmptyState, Input, Label, Spinner,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../ui'
import { formatDate } from '../../lib/format'

/* ============================================================================
   CAL35 — L'ÉCRAN LISTE `/calepinage` : la porte autonome, enfin.
   ----------------------------------------------------------------------------
   D3 — cette porte n'existait pas : le seul accès au calepinage passait par un
   devis (`router/index.jsx`) ou par une affaire AO (`features/ao`). Un
   calepinage sans devis est pourtant un objet de PREMIÈRE CLASSE (décision
   fondateur du 19/09/2026) — il lui fallait une liste à lui.

   LES FILTRES SONT CEUX QUE LE SERVEUR SERT VRAIMENT (CAL16) : `lead`,
   `client`, `statut`, `depuis`, `q`. Aucun autre n'est envoyé. La leçon PV22
   est qu'un filtre IGNORÉ par le serveur fait ouvrir le mauvais objet : une
   liste fausse qui a l'air juste est pire qu'une liste qui refuse de filtrer.
   Chaque champ ci-dessous part donc dans la requête, et le test le prouve.

   AUCUNE IMAGE INVENTÉE. Le serveur publie `image.url` — une URL signée à durée
   de vie courte (contrat `calepinage_detail.json`) — ou `null` quand aucun
   aperçu n'a été produit. Dans ce second cas la vignette rend une CARTE NEUTRE,
   jamais une `<img>` vers une source vide (qui afficherait l'icône d'image
   cassée du navigateur) et jamais une illustration de substitution qui
   laisserait croire qu'un toit a été dessiné.

   LES STATUTS NE SONT PAS RECOPIÉS ICI. Aucun échantillon de contrat ne publie
   la LISTE des statuts possibles ; en inventer une produirait un menu qui
   propose des valeurs que le serveur refuse (ou qui en cache). Les options du
   filtre sont donc construites à partir des couples `statut`/`statut_libelle`
   RÉELLEMENT présents dans la page chargée — et le libellé affiché est toujours
   celui du serveur, jamais une traduction maison.
   ========================================================================== */

const errMsg = (e, repli) => e?.response?.data?.detail || repli

/* Les filtres, tels qu'ils partent au serveur. Une valeur vide n'est pas
   envoyée du tout : `?statut=` (vide) serait un filtre, pas une absence de
   filtre. */
function paramsServeur({ q, statut, depuis, lead, client, page }) {
  const params = {}
  if (q) params.q = q
  if (statut) params.statut = statut
  if (depuis) params.depuis = depuis
  if (lead) params.lead = lead
  if (client) params.client = client
  if (page && page > 1) params.page = page
  return params
}

/** Recherche bornée société côté serveur — jamais un filtrage local. */
const chercherLeads = async (q) => {
  const res = await crmApi.getLeads({ q, page_size: 20 })
  return unwrapList(res).map((l) => ({
    value: String(l.id),
    label: l.nom || l.nom_complet || l.raison_sociale || `Lead ${l.id}`,
    description: l.ville || undefined,
  }))
}

const chercherClients = async (q) => {
  const res = await crmApi.searchClients(q)
  return unwrapList(res).map((c) => ({
    value: String(c.id),
    label: c.nom || c.raison_sociale || `Client ${c.id}`,
    description: c.ville || undefined,
  }))
}

/* ── La vignette ───────────────────────────────────────────────────────────
   `image.url` présent ⇒ l'aperçu réel. Absent ⇒ carte neutre explicite. */
export function VignetteCalepinage({ calepinage }) {
  const url = calepinage?.image?.url || null
  const titre = calepinage?.nom || calepinage?.reference || 'Calepinage'
  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-ui-md">
      <Link
        to={`/calepinage/${calepinage.id}`}
        className="block"
        data-testid={`cal-vignette-${calepinage.id}`}
      >
        <div className="aspect-[4/3] w-full bg-muted">
          {url ? (
            <img
              src={url}
              alt={`Aperçu de toiture — ${titre}`}
              className="h-full w-full object-cover"
              data-testid="cal-vignette-image"
            />
          ) : (
            <div
              className="flex h-full w-full flex-col items-center justify-center gap-2 text-muted-foreground"
              data-testid="cal-vignette-sans-image"
            >
              <LayoutGrid size={28} strokeWidth={1.5} aria-hidden="true" />
              <span className="text-xs">Aucun aperçu de toiture</span>
            </div>
          )}
        </div>
        <div className="space-y-1 p-3">
          <div className="flex items-start justify-between gap-2">
            <span className="truncate text-sm font-medium">{titre}</span>
            {calepinage?.statut_libelle ? (
              <Badge variant="outline">{calepinage.statut_libelle}</Badge>
            ) : null}
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {calepinage?.reference || '—'}
            {' · '}
            {calepinage?.client?.nom || calepinage?.lead?.nom || 'Sans rattachement'}
          </div>
          <div className="text-xs text-muted-foreground">
            {calepinage?.modifie_le ? `Modifié le ${formatDate(calepinage.modifie_le)}` : '—'}
          </div>
        </div>
      </Link>
    </Card>
  )
}

export default function CalepinageList() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [statut, setStatut] = useState('')
  const [depuis, setDepuis] = useState('')
  const [lead, setLead] = useState(null)
  const [client, setClient] = useState(null)
  const [page, setPage] = useState(1)

  const params = useMemo(
    () => paramsServeur({ q, statut, depuis, lead, client, page }),
    [q, statut, depuis, lead, client, page],
  )

  const { data, loading, error } = useResource(
    (p) => calepinageApi.calepinages.list(p),
    params,
    {
      initialData: null,
      select: (res) => res?.data ?? null,
      errorMessage: (e) => errMsg(e, 'Impossible de charger les calepinages.'),
    },
  )

  const lignes = useMemo(() => unwrapList({ data }), [data])
  const total = Array.isArray(data) ? data.length : (data?.count ?? lignes.length)
  const pageSuivante = Array.isArray(data) ? null : data?.next
  const pagePrecedente = Array.isArray(data) ? null : data?.previous

  // Options de statut : les couples RÉELS de la page, jamais une liste recopiée.
  const optionsStatut = useMemo(() => {
    const vus = new Map()
    for (const ligne of lignes) {
      if (ligne?.statut && !vus.has(ligne.statut)) {
        vus.set(ligne.statut, ligne.statut_libelle || ligne.statut)
      }
    }
    return [...vus.entries()]
  }, [lignes])

  const reinitialiser = () => {
    setQ(''); setStatut(''); setDepuis(''); setLead(null); setClient(null); setPage(1)
  }
  const filtreActif = Boolean(q || statut || depuis || lead || client)
  const surFiltre = (poser) => (valeur) => { poser(valeur); setPage(1) }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">Calepinages</h1>
        <Button size="sm" onClick={() => navigate('/calepinage/nouveau')}>
          <Plus size={16} aria-hidden="true" />
          Nouveau calepinage
        </Button>
      </div>

      <Card className="grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="space-y-1">
          <Label htmlFor="cal-q">Recherche</Label>
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="cal-q"
              className="pl-7"
              value={q}
              placeholder="Référence, nom…"
              onChange={(e) => surFiltre(setQ)(e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-statut">Statut</Label>
          <Select value={statut || '__tous__'} onValueChange={(v) => surFiltre(setStatut)(v === '__tous__' ? '' : v)}>
            <SelectTrigger id="cal-statut"><SelectValue placeholder="Tous les statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__tous__">Tous les statuts</SelectItem>
              {optionsStatut.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-depuis">Modifié depuis le</Label>
          <Input
            id="cal-depuis"
            type="date"
            value={depuis}
            onChange={(e) => surFiltre(setDepuis)(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-lead">Lead</Label>
          <Combobox
            id="cal-lead"
            value={lead}
            onChange={surFiltre(setLead)}
            onSearch={chercherLeads}
            placeholder="Tous les leads"
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-client">Client</Label>
          <Combobox
            id="cal-client"
            value={client}
            onChange={surFiltre(setClient)}
            onSearch={chercherClients}
            placeholder="Tous les clients"
          />
        </div>

        {filtreActif ? (
          <div className="sm:col-span-2 lg:col-span-5">
            <Button size="sm" variant="ghost" onClick={reinitialiser}>
              <X size={15} aria-hidden="true" />
              Réinitialiser les filtres
            </Button>
          </div>
        ) : null}
      </Card>

      {error ? (
        <Card className="p-4 text-sm text-destructive" role="alert">{error}</Card>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-10"><Spinner /></div>
      ) : null}

      {!loading && !error && lignes.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title={filtreActif ? 'Aucun calepinage ne correspond à ces filtres' : 'Aucun calepinage pour l’instant'}
          description={filtreActif
            ? 'Élargissez la recherche, ou réinitialisez les filtres pour revoir toute la liste.'
            : 'Un calepinage part d’un lead ou d’un client : choisissez-en un, et l’atelier s’ouvre sur son toit. Vous pourrez ensuite générer le devis depuis le calepinage.'}
          action={filtreActif ? (
            <Button size="sm" variant="outline" onClick={reinitialiser}>Réinitialiser les filtres</Button>
          ) : (
            <Button size="sm" onClick={() => navigate('/calepinage/nouveau')}>
              <Plus size={16} aria-hidden="true" />
              Créer un calepinage
            </Button>
          )}
        />
      ) : null}

      {!loading && lignes.length > 0 ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {lignes.map((ligne) => (
              <VignetteCalepinage key={ligne.id} calepinage={ligne} />
            ))}
          </div>
          <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>{`${lignes.length} calepinage(s) affiché(s)${typeof total === 'number' ? ` sur ${total}` : ''}`}</span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1 || (!Array.isArray(data) && !pagePrecedente)}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Précédent
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!pageSuivante}
                onClick={() => setPage((p) => p + 1)}
              >
                Suivant
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
