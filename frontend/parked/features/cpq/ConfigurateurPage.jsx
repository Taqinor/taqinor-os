import { useCallback, useEffect, useState } from 'react'
import { FileText, Play, Plus, Save, Trash2 } from 'lucide-react'
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import cpqApi from '../../api/cpqApi'
import crmApi from '../../api/crmApi'

/* ============================================================================
   PACT125 — écran « Configurateur guidé » (`/cpq/configurateur`).
   ----------------------------------------------------------------------------
   Le backend pilotait une session questions-réponses COMPLÈTE (NTCPQ9/10,
   `apps/cpq/views.py`) sans aucun frontend : démarrer une session, répondre,
   résoudre produits/offres groupées via le moteur de règles produit (NTCPQ2),
   puis matérialiser un devis BROUILLON. Cet écran expose ce parcours tel
   qu'il existe — il n'invente aucune route.

   Deux onglets, comme le demande la tâche (l'administration des questions est
   un ONGLET du même écran, pas un second écran) :
     1. « Configurateur » — démarrer → répondre → résultat résolu → devis
        brouillon. La génération exige un client (le serveur refuse sinon :
        `services.generer_devis_depuis_configurateur` lève « Un client ou un
        lead est requis »), donc le bouton reste désactivé tant qu'aucun
        client n'est choisi : jamais un 400 qu'on aurait pu éviter.
     2. « Questions » — CRUD des `QuestionConfigurateur` (ordre, texte, type,
        clé de contexte, choix, actif). L'écriture est réservée au palier
        Directeur/Commercial responsable CÔTÉ SERVEUR ; l'écran se contente de
        remonter proprement un refus.

   Le devis produit reste un BROUILLON : cet écran ne génère JAMAIS de PDF
   client (règle #4 — `/proposal` est le seul chemin).
   ========================================================================== */

const TYPES_QUESTION = [
  ['CHOIX_UNIQUE', 'Choix unique'],
  ['CHOIX_MULTIPLE', 'Choix multiple'],
  ['NUMERIQUE', 'Numérique'],
]

/* Les listes DRF sont paginées par défaut (`core.pagination.StandardPagination`)
   mais certaines vues renvoient un tableau à plat : on tolère les deux formes
   sans jamais jeter. */
function listeDe(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

/* Choix proposés par une question : `options.choices` accepte aussi bien
   ["A", "B"] que [{value, label}] — on normalise sans rien inventer. */
function choixDeQuestion(question) {
  const opts = question && typeof question.options === 'object' && question.options
    ? question.options
    : {}
  const bruts = Array.isArray(opts.choices) ? opts.choices : []
  return bruts
    .map((c) => {
      if (c && typeof c === 'object') {
        const valeur = c.value ?? c.valeur ?? ''
        return { valeur: String(valeur), libelle: String(c.label ?? c.libelle ?? valeur) }
      }
      return { valeur: String(c), libelle: String(c) }
    })
    .filter((c) => c.valeur !== '')
}

function valeurInitiale(question) {
  return question && question.type === 'CHOIX_MULTIPLE' ? [] : ''
}

/* Corps de `POST configurateur/{token}/repondre/` : une entrée par question
   active. Le numérique part en NOMBRE (jamais une chaîne) pour que les règles
   produit (NTCPQ2) puissent le comparer ; une saisie vide part à `null`. */
function reponsesPayload(questions, valeurs) {
  return questions.map((q) => {
    let valeur = valeurs[q.id]
    if (valeur === undefined) valeur = valeurInitiale(q)
    if (q.type === 'NUMERIQUE') {
      const brut = String(valeur ?? '').trim().replace(',', '.')
      const n = Number(brut)
      valeur = brut === '' || Number.isNaN(n) ? null : n
    }
    return { question: q.id, valeur }
  })
}

/* Aplatit `{actions_declenchees: [{nom, actions:[...]}]}` en lignes lisibles :
   une action porte `produit_id` OU `offre_id` (cf. `services._ligne_depuis_action`). */
function elementsResolus(resultat) {
  const regles = Array.isArray(resultat?.actions_declenchees)
    ? resultat.actions_declenchees
    : []
  const out = []
  regles.forEach((regle) => {
    const actions = Array.isArray(regle?.actions) ? regle.actions : []
    actions.forEach((a) => {
      if (!a || typeof a !== 'object') return
      if (a.produit_id) {
        out.push({
          cle: `p${a.produit_id}-${out.length}`,
          type: 'Produit',
          reference: a.produit_id,
          quantite: a.quantite ?? 1,
          regle: regle.nom || '',
        })
      } else if (a.offre_id) {
        out.push({
          cle: `o${a.offre_id}-${out.length}`,
          type: 'Offre groupée',
          reference: a.offre_id,
          quantite: a.quantite ?? 1,
          regle: regle.nom || '',
        })
      }
    })
  })
  return out
}

function messageErreur(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'string' && data) return data
  return repli
}

/* -------------------------------------------------------------------------- */
/* Onglet 1 — parcours guidé                                                   */
/* -------------------------------------------------------------------------- */

function SessionTab() {
  const [session, setSession] = useState(null)
  const [questions, setQuestions] = useState([])
  const [valeurs, setValeurs] = useState({})
  const [resultat, setResultat] = useState(null)
  const [clients, setClients] = useState([])
  const [clientId, setClientId] = useState('')
  const [devis, setDevis] = useState(null)
  const [occupe, setOccupe] = useState(false)

  useEffect(() => {
    let vivant = true
    crmApi.getClients({ page_size: 200 })
      .then((res) => { if (vivant) setClients(listeDe(res?.data)) })
      .catch(() => { if (vivant) setClients([]) })
    return () => { vivant = false }
  }, [])

  const demarrer = useCallback(async () => {
    if (occupe) return
    setOccupe(true)
    try {
      const res = await cpqApi.demarrerConfigurateur()
      const data = res?.data || {}
      const qs = listeDe(data.questions)
      setSession(data.session || null)
      setQuestions(qs)
      setValeurs(Object.fromEntries(qs.map((q) => [q.id, valeurInitiale(q)])))
      setResultat(null)
      setDevis(null)
      toast.success(`Session démarrée — ${qs.length} question(s) active(s).`)
    } catch (err) {
      toast.error(messageErreur(err, 'Impossible de démarrer une session.'))
    } finally {
      setOccupe(false)
    }
  }, [occupe])

  const resoudre = useCallback(async () => {
    if (!session || occupe) return
    setOccupe(true)
    try {
      await cpqApi.repondreConfigurateur(session, reponsesPayload(questions, valeurs))
      const res = await cpqApi.resultatConfigurateur(session)
      setResultat(res?.data || { context: {}, actions_declenchees: [] })
      toast.success('Configuration résolue.')
    } catch (err) {
      toast.error(messageErreur(err, 'Résolution impossible.'))
    } finally {
      setOccupe(false)
    }
  }, [session, occupe, questions, valeurs])

  const genererDevis = useCallback(async () => {
    if (!session || !clientId || occupe) return
    setOccupe(true)
    try {
      const res = await cpqApi.genererDevisConfigurateur(session, { client: clientId })
      const data = res?.data || {}
      setDevis(data)
      toast.success(`Devis brouillon ${data.reference || ''} créé.`.trim())
    } catch (err) {
      toast.error(messageErreur(err, 'Génération du devis impossible.'))
    } finally {
      setOccupe(false)
    }
  }, [session, clientId, occupe])

  function majValeur(question, valeur) {
    setValeurs((v) => ({ ...v, [question.id]: valeur }))
  }

  function basculerChoix(question, choix) {
    setValeurs((v) => {
      const courant = Array.isArray(v[question.id]) ? v[question.id] : []
      const suivant = courant.includes(choix)
        ? courant.filter((c) => c !== choix)
        : [...courant, choix]
      return { ...v, [question.id]: suivant }
    })
  }

  const resolus = elementsResolus(resultat)

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-wrap items-center gap-3 p-4 sm:p-5">
        <Button onClick={demarrer} disabled={occupe} data-testid="cpq-cfg-demarrer">
          <Play /> Démarrer une session
        </Button>
        {session && (
          <span className="text-sm text-muted-foreground" data-testid="cpq-cfg-session">
            Session en cours · {questions.length} question(s)
          </span>
        )}
      </Card>

      {!session && (
        <EmptyState
          title="Aucune session en cours"
          description="Démarrez une session pour répondre aux questions et obtenir une configuration résolue."
        />
      )}

      {session && questions.length === 0 && (
        <EmptyState
          title="Aucune question active"
          description="Ajoutez des questions dans l'onglet « Questions » pour guider la configuration."
        />
      )}

      {session && questions.length > 0 && (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          {questions.map((q) => {
            const choix = choixDeQuestion(q)
            return (
              <div key={q.id} className="flex flex-col gap-2" data-testid={`cpq-cfg-q-${q.id}`}>
                <span className="text-sm font-medium text-foreground">{q.texte}</span>
                {q.type === 'NUMERIQUE' && (
                  <Input
                    className="sm:w-56"
                    inputMode="decimal"
                    step="any"
                    aria-label={q.texte}
                    value={valeurs[q.id] ?? ''}
                    onChange={(e) => majValeur(q, e.target.value)}
                  />
                )}
                {q.type === 'CHOIX_UNIQUE' && (
                  choix.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {choix.map((c) => (
                        <Button
                          key={c.valeur}
                          type="button"
                          size="sm"
                          variant={valeurs[q.id] === c.valeur ? 'default' : 'secondary'}
                          aria-pressed={valeurs[q.id] === c.valeur}
                          onClick={() => majValeur(q, c.valeur)}
                        >
                          {c.libelle}
                        </Button>
                      ))}
                    </div>
                  ) : (
                    <Input
                      className="sm:w-72"
                      aria-label={q.texte}
                      value={valeurs[q.id] ?? ''}
                      onChange={(e) => majValeur(q, e.target.value)}
                    />
                  )
                )}
                {q.type === 'CHOIX_MULTIPLE' && (
                  <div className="flex flex-wrap gap-3">
                    {choix.length === 0 && (
                      <span className="text-sm text-muted-foreground">
                        Aucun choix configuré pour cette question.
                      </span>
                    )}
                    {choix.map((c) => (
                      <label key={c.valeur} className="flex items-center gap-2 text-sm">
                        <Checkbox
                          aria-label={`${q.texte} — ${c.libelle}`}
                          checked={
                            Array.isArray(valeurs[q.id]) && valeurs[q.id].includes(c.valeur)
                          }
                          onCheckedChange={() => basculerChoix(q, c.valeur)}
                        />
                        {c.libelle}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          <div>
            <Button onClick={resoudre} disabled={occupe} data-testid="cpq-cfg-resoudre">
              <Save /> Résoudre la configuration
            </Button>
          </div>
        </Card>
      )}

      {resultat && (
        <Card className="flex flex-col gap-3 p-4 sm:p-5" data-testid="cpq-cfg-resultat">
          <h3 className="text-sm font-medium text-foreground">Configuration résolue</h3>
          {resolus.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune règle produit ne s&apos;applique à ces réponses.
            </p>
          ) : (
            <ul className="flex flex-col gap-2" data-testid="cpq-cfg-resolus">
              {resolus.map((r) => (
                <li
                  key={r.cle}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3"
                >
                  <Badge tone="neutral">{r.type}</Badge>
                  <span className="font-medium">#{r.reference}</span>
                  <span className="text-sm text-muted-foreground">× {r.quantite}</span>
                  {r.regle && (
                    <span className="text-xs text-muted-foreground">via « {r.regle} »</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Client du devis</span>
              <Select value={clientId} onValueChange={setClientId}>
                <SelectTrigger className="w-64" aria-label="Client du devis">
                  <SelectValue placeholder="Choisir un client" />
                </SelectTrigger>
                <SelectContent>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.nom || c.raison_sociale || `Client #${c.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={genererDevis}
              disabled={occupe || !clientId}
              data-testid="cpq-cfg-generer-devis"
            >
              <FileText /> Générer un devis brouillon
            </Button>
          </div>

          {devis && (
            <p className="text-sm text-foreground" data-testid="cpq-cfg-devis-cree">
              Devis brouillon créé : {devis.reference || `#${devis.devis_id}`}
            </p>
          )}
        </Card>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Onglet 2 — administration des questions                                     */
/* -------------------------------------------------------------------------- */

const NOUVELLE_QUESTION = {
  texte: '', type: 'CHOIX_UNIQUE', ordre: '', champ: '', choix: '',
}

function QuestionsTab() {
  const [questions, setQuestions] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [brouillon, setBrouillon] = useState(NOUVELLE_QUESTION)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const res = await cpqApi.getQuestionsConfigurateur()
      setQuestions(listeDe(res?.data))
      setErreur('')
    } catch (err) {
      setErreur(messageErreur(err, 'Questions indisponibles.'))
      setQuestions([])
    } finally {
      setChargement(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger() }, [charger])

  async function creer() {
    if (occupe) return
    const texte = String(brouillon.texte || '').trim()
    if (!texte) {
      toast.error('Le texte de la question est obligatoire.')
      return
    }
    const choix = String(brouillon.choix || '')
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean)
    const options = {}
    if (brouillon.champ.trim()) options.champ = brouillon.champ.trim()
    if (choix.length > 0) options.choices = choix
    const ordre = Number(String(brouillon.ordre || '').trim())
    setOccupe(true)
    try {
      await cpqApi.createQuestionConfigurateur({
        texte,
        type: brouillon.type,
        ordre: Number.isFinite(ordre) && String(brouillon.ordre).trim() !== '' ? ordre : 0,
        options,
        actif: true,
      })
      toast.success('Question ajoutée.')
      setBrouillon(NOUVELLE_QUESTION)
      charger()
    } catch (err) {
      toast.error(messageErreur(err, "Impossible d'ajouter cette question."))
    } finally {
      setOccupe(false)
    }
  }

  async function basculerActif(question) {
    try {
      await cpqApi.updateQuestionConfigurateur(question.id, { actif: !question.actif })
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Modification impossible.'))
    }
  }

  async function supprimer(question) {
    try {
      await cpqApi.deleteQuestionConfigurateur(question.id)
      toast.success('Question supprimée.')
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Ajouter une question</h3>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            className="sm:flex-1"
            placeholder="Texte de la question"
            aria-label="Texte de la question"
            value={brouillon.texte}
            onChange={(e) => setBrouillon((b) => ({ ...b, texte: e.target.value }))}
          />
          <Select
            value={brouillon.type}
            onValueChange={(v) => setBrouillon((b) => ({ ...b, type: v }))}
          >
            <SelectTrigger className="sm:w-48" aria-label="Type de question">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPES_QUESTION.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="sm:w-28"
            inputMode="numeric"
            step="any"
            placeholder="Ordre"
            aria-label="Ordre"
            value={brouillon.ordre}
            onChange={(e) => setBrouillon((b) => ({ ...b, ordre: e.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            className="sm:w-56"
            placeholder="Clé de contexte (ex. kwc)"
            aria-label="Clé de contexte"
            value={brouillon.champ}
            onChange={(e) => setBrouillon((b) => ({ ...b, champ: e.target.value }))}
          />
          <Input
            className="sm:flex-1"
            placeholder="Choix séparés par des virgules"
            aria-label="Choix proposés"
            value={brouillon.choix}
            onChange={(e) => setBrouillon((b) => ({ ...b, choix: e.target.value }))}
          />
          <Button onClick={creer} disabled={occupe} data-testid="cpq-q-creer">
            <Plus /> Ajouter
          </Button>
        </div>
      </Card>

      {chargement && <p className="text-sm text-muted-foreground">Chargement des questions…</p>}
      {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
      {!chargement && !erreur && questions.length === 0 && (
        <EmptyState
          title="Aucune question"
          description="Le configurateur n'a encore aucune question : ajoutez-en une ci-dessus."
        />
      )}
      {!chargement && !erreur && questions.length > 0 && (
        <ul className="flex flex-col gap-2" data-testid="cpq-q-liste">
          {questions.map((q) => (
            <li
              key={q.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{q.ordre}</Badge>
                <span className="font-medium">{q.texte}</span>
                <span className="text-xs text-muted-foreground">{q.type}</span>
                {q.champ && (
                  <span className="text-xs text-muted-foreground">clé : {q.champ}</span>
                )}
                {!q.actif && <Badge tone="warning">Inactive</Badge>}
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => basculerActif(q)}>
                  {q.actif ? 'Désactiver' : 'Activer'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => supprimer(q)}>
                  <Trash2 /> Supprimer
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function ConfigurateurPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Configurateur guidé"
        subtitle="Répondez aux questions, obtenez la configuration résolue et générez un devis brouillon (NTCPQ9/10)."
      />
      <Tabs defaultValue="session">
        <TabsList>
          <TabsTrigger value="session">Configurateur</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
        </TabsList>
        <TabsContent value="session">
          <SessionTab />
        </TabsContent>
        <TabsContent value="questions">
          <QuestionsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
