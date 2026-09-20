import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, MapPin, Plus } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import crmApi from '../../api/crmApi'
import { unwrapList } from '../../api/resource'
import {
  Button, Card, Combobox, Input, Label, Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'

/* ============================================================================
   CAL36 — `/calepinage/nouveau` : CHOISIR UN LEAD **OU** UN CLIENT.
   ----------------------------------------------------------------------------
   DEMANDE FONDATEUR n°3 (19/09/2026, verbatim) : « pick whatever client or lead
   and make its calpinage ». C'est tout l'écran.

   LE BORNAGE SOCIÉTÉ EST CELUI DU SERVEUR, JAMAIS DE L'ÉCRAN. Les deux
   recherches partent à crm (`/crm/leads/`, `/crm/clients/search/`), qui filtre
   par `request.user.company`. Un écran qui pré-chargerait une liste pour la
   filtrer lui-même ne pourrait PAS garantir qu'un lead d'une autre société
   n'apparaisse jamais — c'est la raison de fond, pas une préférence de style.

   LE CONTEXTE GÉOGRAPHIQUE EST LU, JAMAIS DEVINÉ (D5).
     * Un LEAD peut porter une épingle publique `roof_point` (posée par le
       client depuis le site), un contour `roof_outline`, ou à défaut les
       `gps_lat`/`gps_lng` saisis côté « Toiture & site » du CRM. C'est
       exactement le repli déjà tenu par `pinDepuisLead` dans l'atelier — on ne
       s'en écarte pas, et on n'invente JAMAIS un centre du Maroc quand aucune
       source n'existe : l'écran affiche « non renseigné ».
     * Un CLIENT n'a PAS de `roof_point` : `crm.Client` ne porte pas ce champ.
       Son point de départ est le GÉOCODAGE de son adresse (CAL49), qui se joue
       côté serveur — et quand l'adresse manque, rien n'est deviné ici non plus.
   Le contexte définitif du calepinage est celui que le serveur rend
   (`design-context`, CAL15/CAL231) ; ce bloc n'est qu'un APERÇU de la source de
   départ, ce qu'il dit explicitement.

   LES ERREURS SE POSENT SOUS LE CHAMP FAUTIF (règle fondateur 08/09) : un
   « Non enregistré » générique est interdit. Le bandeau NOMME le champ, le
   message du serveur s'affiche TEL QUEL sous ce champ, et un clic sur le
   bandeau y emmène.
   ========================================================================== */

const CHAMPS = { lead: 'Lead', client: 'Client' }

/** Le message serveur, tel quel. Jamais un texte fabriqué par l'écran. */
function erreursServeur(e) {
  const data = e?.response?.data
  if (!data) return { global: 'Le serveur n’a pas répondu. Réessayez dans un instant.' }
  if (typeof data === 'string') return { global: data }
  const parChamp = {}
  let global = null
  for (const [cle, valeur] of Object.entries(data)) {
    const texte = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
    if (cle === 'detail' || cle === 'non_field_errors') global = texte
    else parChamp[cle] = texte
  }
  return { ...parChamp, global }
}

/* Ce que l'écran sait du point de départ d'un LEAD — lu, jamais deviné.
   NON exporté : `react-refresh/only-export-components` veut qu'un fichier de
   composant n'exporte que des composants, et cette fonction n'a pas assez de
   vie propre pour mériter un module à elle. Elle est vérifiée À TRAVERS
   L'ÉCRAN, qui est de toute façon le seul endroit où son résultat compte. */
function contexteDuLead(lead) {
  if (!lead) return null
  const lat = lead.gps_lat
  const lng = lead.gps_lng
  const coordsSaisies = (lat != null && lng != null
    && Number.isFinite(Number(lat)) && Number.isFinite(Number(lng)))
  if (lead.roof_point) return { source: 'Épingle posée par le client (site web)' }
  if (coordsSaisies) return { source: 'Coordonnées GPS saisies dans la fiche (Toiture & site)' }
  return { source: null }
}

function LigneContexte({ libelle, valeur }) {
  return (
    <div className="flex gap-2 text-sm">
      <span className="w-40 shrink-0 text-muted-foreground">{libelle}</span>
      <span className={valeur ? '' : 'text-muted-foreground italic'}>
        {valeur || 'non renseigné'}
      </span>
    </div>
  )
}

export default function CalepinageNouveau() {
  const navigate = useNavigate()
  const [onglet, setOnglet] = useState('lead')
  const [leadId, setLeadId] = useState(null)
  const [clientId, setClientId] = useState(null)
  const [leadChoisi, setLeadChoisi] = useState(null)
  const [clientChoisi, setClientChoisi] = useState(null)
  const [nom, setNom] = useState('')
  const [erreurs, setErreurs] = useState({})
  const [envoi, setEnvoi] = useState(false)
  const refLead = useRef(null)
  const refClient = useRef(null)

  const surLead = onglet === 'lead'
  const cibleId = surLead ? leadId : clientId
  const champCible = surLead ? 'lead' : 'client'

  /* Recherches SERVEUR. On conserve l'objet complet renvoyé pour l'aperçu du
     contexte : une seconde requête de détail ne dirait rien de plus. */
  const chercherLeads = async (q) => {
    const res = await crmApi.getLeads({ q, page_size: 20 })
    const lignes = unwrapList(res)
    refLead.current = lignes
    return lignes.map((l) => ({
      value: String(l.id),
      label: [l.nom, l.prenom].filter(Boolean).join(' ') || `Lead ${l.id}`,
      description: l.ville || undefined,
    }))
  }

  const chercherClients = async (q) => {
    const res = await crmApi.searchClients(q)
    const lignes = unwrapList(res)
    refClient.current = lignes
    return lignes.map((c) => ({
      value: String(c.id),
      label: [c.nom, c.prenom].filter(Boolean).join(' ') || `Client ${c.id}`,
      description: c.adresse || undefined,
    }))
  }

  const choisirLead = (valeur) => {
    setLeadId(valeur)
    setLeadChoisi((refLead.current || []).find((l) => String(l.id) === String(valeur)) || null)
    setErreurs((e) => ({ ...e, lead: undefined, global: undefined }))
  }

  const choisirClient = (valeur) => {
    setClientId(valeur)
    setClientChoisi((refClient.current || []).find((c) => String(c.id) === String(valeur)) || null)
    setErreurs((e) => ({ ...e, client: undefined, global: undefined }))
  }

  const changerOnglet = (valeur) => {
    setOnglet(valeur)
    setErreurs({})
  }

  const contexteLead = useMemo(() => contexteDuLead(leadChoisi), [leadChoisi])

  const creer = async (e) => {
    e.preventDefault()
    // Côté écran : créer sans lead NI client est impossible. Le serveur refuse
    // de son côté en nommant le champ (CAL16) — les deux gardes existent, et
    // celle-ci n'est pas une excuse pour se passer de celle-là.
    if (!cibleId) {
      setErreurs({
        [champCible]: surLead
          ? 'Choisissez le lead dont vous voulez calepiner la toiture.'
          : 'Choisissez le client dont vous voulez calepiner la toiture.',
        global: `${CHAMPS[champCible]} : aucun ${surLead ? 'lead' : 'client'} n’est sélectionné.`,
      })
      return
    }
    setEnvoi(true)
    setErreurs({})
    try {
      const corps = { [champCible]: cibleId }
      if (nom.trim()) corps.nom = nom.trim()
      const res = await calepinageApi.calepinages.create(corps)
      const id = res?.data?.id
      if (id) navigate(`/calepinage/${id}`)
      else setErreurs({ global: 'Le serveur n’a pas renvoyé l’identifiant du calepinage créé.' })
    } catch (err) {
      setErreurs(erreursServeur(err))
    } finally {
      setEnvoi(false)
    }
  }

  const champsEnErreur = Object.keys(erreurs).filter((c) => c !== 'global' && erreurs[c])

  return (
    <form className="space-y-4" onSubmit={creer} noValidate>
      <h1 className="text-lg font-semibold">Nouveau calepinage</h1>

      {(erreurs.global || champsEnErreur.length > 0) ? (
        <Card className="border-destructive/50 bg-destructive/5 p-3" role="alert">
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div className="space-y-1">
              {erreurs.global ? <p>{erreurs.global}</p> : null}
              {champsEnErreur.map((champ) => (
                <button
                  key={champ}
                  type="button"
                  className="block underline underline-offset-2"
                  onClick={() => document.getElementById(`cal-nouveau-${champ}`)?.focus()}
                >
                  {`Corriger le champ « ${CHAMPS[champ] || champ} »`}
                </button>
              ))}
            </div>
          </div>
        </Card>
      ) : null}

      <Card className="space-y-4 p-4">
        <Tabs value={onglet} onValueChange={changerOnglet}>
          <TabsList>
            <TabsTrigger value="lead">Lead</TabsTrigger>
            <TabsTrigger value="client">Client</TabsTrigger>
          </TabsList>

          <TabsContent value="lead" className="space-y-3 pt-3">
            <div className="space-y-1">
              <Label htmlFor="cal-nouveau-lead">Lead</Label>
              <Combobox
                id="cal-nouveau-lead"
                value={leadId}
                onChange={choisirLead}
                onSearch={chercherLeads}
                invalid={Boolean(erreurs.lead)}
                placeholder="Rechercher un lead…"
              />
              {erreurs.lead ? (
                <p className="text-sm text-destructive" data-testid="erreur-lead">{erreurs.lead}</p>
              ) : null}
            </div>

            <div className="space-y-1 rounded-md border border-border p-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <MapPin size={15} aria-hidden="true" />
                Point de départ
              </div>
              <p className="text-xs text-muted-foreground">
                Aperçu de la source connue côté CRM. Le contexte définitif du calepinage
                est établi par le serveur à l’ouverture de l’atelier.
              </p>
              <LigneContexte libelle="Ville" valeur={leadChoisi?.ville} />
              <LigneContexte libelle="Source du repère" valeur={contexteLead?.source} />
            </div>
          </TabsContent>

          <TabsContent value="client" className="space-y-3 pt-3">
            <div className="space-y-1">
              <Label htmlFor="cal-nouveau-client">Client</Label>
              <Combobox
                id="cal-nouveau-client"
                value={clientId}
                onChange={choisirClient}
                onSearch={chercherClients}
                invalid={Boolean(erreurs.client)}
                placeholder="Rechercher un client…"
              />
              {erreurs.client ? (
                <p className="text-sm text-destructive" data-testid="erreur-client">{erreurs.client}</p>
              ) : null}
            </div>

            <div className="space-y-1 rounded-md border border-border p-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <MapPin size={15} aria-hidden="true" />
                Point de départ
              </div>
              <p className="text-xs text-muted-foreground">
                Un client ne porte pas d’épingle de toiture : son point de départ vient du
                géocodage de son adresse, côté serveur. Sans adresse, rien n’est deviné.
              </p>
              <LigneContexte libelle="Adresse" valeur={clientChoisi?.adresse} />
              <LigneContexte
                libelle="Source du repère"
                valeur={clientChoisi?.adresse ? 'Géocodage de l’adresse du client' : null}
              />
            </div>
          </TabsContent>
        </Tabs>

        <div className="space-y-1">
          <Label htmlFor="cal-nouveau-nom">Nom du calepinage (facultatif)</Label>
          <Input
            id="cal-nouveau-nom"
            value={nom}
            placeholder="Toiture — bâtiment principal"
            onChange={(e) => setNom(e.target.value)}
          />
        </div>
      </Card>

      <div className="flex gap-2">
        <Button type="submit" disabled={envoi}>
          <Plus size={16} aria-hidden="true" />
          Créer le calepinage
        </Button>
        <Button type="button" variant="ghost" onClick={() => navigate('/calepinage')}>
          Annuler
        </Button>
      </div>
    </form>
  )
}
