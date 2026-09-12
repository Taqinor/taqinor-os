// VTA16 — ADMINISTRATION LÉGÈRE DANS L'APP VISITES (perm `visites_valider`).
//
// Le chemin « bureau » sans ouvrir le CRM : chercher un lead, l'assigner à un
// commercial, dater la visite. La création depuis la fiche lead (VisiteTab,
// côté crm) reste — ce n'est pas un remplacement, c'est le second point
// d'entrée pour quelqu'un qui n'a PAS la fiche sous les yeux.
//
// PÉRIMÈTRE VOLONTAIREMENT ÉTROIT : la recherche renvoie {id, nom, ville,
// telephone} et rien d'autre. Ce n'est PAS une liste CRM, on ne l'affiche pas
// sans requête (aucun listing « tous les leads »), et la porte est côté
// SERVEUR : `visites_valider` est portée par l'endpoint lui-même — cet écran
// est gaté en plus (module.config), il ne se substitue pas à cette garde.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import visitesApi from '../../api/visitesApi'
import PageHeader from '../../components/layout/PageHeader'
import {
  Button, Card, Input, Label, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { toast } from '../../ui/confirm'

// Sous ce seuil on n'interroge pas le serveur : une requête à une lettre
// ramènerait un pan entier de l'annuaire — exactement ce que cet écran refuse.
const MIN_CARACTERES = 2
const DELAI_FRAPPE_MS = 300

export default function PlanifierVisitePage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [resultats, setResultats] = useState([])
  const [cherche, setCherche] = useState(false)
  const [lead, setLead] = useState(null)
  const [datePrevue, setDatePrevue] = useState('')
  const [commercial, setCommercial] = useState('')
  const [membres, setMembres] = useState([])
  const [creation, setCreation] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const abort = useRef(null)

  const chargerMembres = useCallback(() => {
    visitesApi.getMembres()
      .then((res) => setMembres(res.data?.results ?? res.data ?? []))
      // Le champ « assigner à » reste alors vide et facultatif : le serveur
      // assignera son défaut. On n'invente pas une liste d'utilisateurs.
      .catch(() => setMembres([]))
  }, [])

  useEffect(() => { chargerMembres() }, [chargerMembres])

  const terme = q.trim()
  const assezLong = terme.length >= MIN_CARACTERES

  // NOTE hooks (react-hooks/set-state-in-effect) : cet effet ne POSE aucun
  // état de façon synchrone. Sous le seuil, on ne vide pas la liste par un
  // setState — on la DÉRIVE au rendu (`resultatsAffiches` plus bas).
  useEffect(() => {
    if (!assezLong) return undefined
    const minuteur = setTimeout(() => {
      abort.current?.abort()
      const ctrl = new AbortController()
      abort.current = ctrl
      setCherche(true)
      visitesApi.rechercherLeads(terme, { signal: ctrl.signal })
        .then((res) => setResultats(res.data?.results ?? res.data ?? []))
        .catch(() => setResultats([]))
        .finally(() => setCherche(false))
    }, DELAI_FRAPPE_MS)
    return () => clearTimeout(minuteur)
  }, [terme, assezLong])

  useEffect(() => () => abort.current?.abort(), [])

  const peutCreer = useMemo(() => Boolean(lead) && !creation, [lead, creation])
  // Dérivés (jamais un setState d'effet) : sous le seuil, ou une fois le
  // client choisi, il n'y a rien à proposer.
  const resultatsAffiches = assezLong && !lead ? resultats : []
  const chercheAffiche = assezLong && !lead && cherche

  const planifier = async () => {
    if (!lead) return
    setCreation(true)
    setErreurs({})
    try {
      const corps = { lead: lead.id }
      if (datePrevue) corps.date_prevue = datePrevue
      if (commercial) corps.commercial = Number(commercial)
      const res = await visitesApi.createVisite(corps)
      toast.success('Visite planifiée.')
      navigate(`/visites/${res.data.id}`)
    } catch (err) {
      // Erreurs SERVEUR sous le champ fautif (règle fondateur), jamais un
      // « non enregistré » générique.
      const data = err?.response?.data
      if (data && typeof data === 'object') setErreurs(data)
      else toast.error('Planification impossible.')
    } finally {
      setCreation(false)
    }
  }

  const msg = (champ) => {
    const v = erreurs?.[champ]
    if (!v) return null
    return Array.isArray(v) ? v.join(' ') : String(v)
  }

  return (
    <div className="page max-w-[640px]">
      <PageHeader
        title="Planifier une visite"
        subtitle="Chercher le client, assigner, dater — sans ouvrir le CRM"
      />

      <Card className="space-y-4 p-4">
        <div>
          <Label htmlFor="visite-recherche-lead">Client</Label>
          <Input
            id="visite-recherche-lead"
            value={q}
            onChange={(e) => { setQ(e.target.value); setLead(null) }}
            placeholder="Nom, ville ou téléphone"
            autoComplete="off"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Tapez au moins {MIN_CARACTERES} caractères. Seuls le nom, la ville et
            le téléphone sont renvoyés.
          </p>
          {msg('lead') && (
            <p role="alert" className="mt-1 text-xs text-destructive">{msg('lead')}</p>
          )}
        </div>

        {chercheAffiche && <Spinner />}

        {!chercheAffiche && assezLong && !lead && resultatsAffiches.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Aucun client ne correspond à « {terme} ».
          </p>
        )}

        {resultatsAffiches.length > 0 && (
          <ul className="divide-y divide-border rounded-md border border-border">
            {resultatsAffiches.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className="flex min-h-11 w-full items-center justify-between gap-2 px-3 text-left text-sm"
                  onClick={() => { setLead(r); setResultats([]) }}
                >
                  <span className="min-w-0 truncate">{r.nom}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {[r.ville, r.telephone].filter(Boolean).join(' · ')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {lead && (
          <div className="rounded-md border border-border p-3 text-sm" data-testid="visite-lead-choisi">
            <p className="font-medium">{lead.nom}</p>
            <p className="text-xs text-muted-foreground">
              {[lead.ville, lead.telephone].filter(Boolean).join(' · ')}
            </p>
            <Button
              type="button" size="sm" variant="ghost" className="mt-1 px-0"
              onClick={() => { setLead(null); setQ('') }}
            >
              Changer de client
            </Button>
          </div>
        )}

        <div>
          <Label htmlFor="visite-date-prevue">Date prévue</Label>
          <Input
            id="visite-date-prevue"
            type="date"
            value={datePrevue}
            onChange={(e) => setDatePrevue(e.target.value)}
          />
          {msg('date_prevue') && (
            <p role="alert" className="mt-1 text-xs text-destructive">{msg('date_prevue')}</p>
          )}
        </div>

        <div>
          <Label htmlFor="visite-commercial">Assigner à</Label>
          <Select value={commercial} onValueChange={setCommercial}>
            <SelectTrigger id="visite-commercial">
              <SelectValue placeholder="Commercial terrain" />
            </SelectTrigger>
            <SelectContent>
              {membres.map((m) => (
                <SelectItem key={m.id} value={String(m.id)}>
                  {m.nom_affiche || m.full_name || m.username || `Utilisateur ${m.id}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {msg('commercial') && (
            <p role="alert" className="mt-1 text-xs text-destructive">{msg('commercial')}</p>
          )}
        </div>

        <Button type="button" className="min-h-11 w-full" disabled={!peutCreer} onClick={planifier}>
          Planifier la visite
        </Button>
      </Card>
    </div>
  )
}
