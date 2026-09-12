import { useEffect, useState } from 'react'
import { Handshake } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Form, FormField, Input, Spinner, toast,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT28 — « Enregistrer une affaire » (deal registration), portail
   PARTENAIRE.
   ----------------------------------------------------------------------------
   Branché sur le modèle FG234 déjà présent (`crm.SoumissionLeadPartenaire`) :
   aucune seconde modélisation. Le partenaire est déduit du compte connecté
   côté serveur — le formulaire n'envoie AUCUN identifiant de partenaire.

   ANTI-DOUBLON : si le serveur répond 409, le même prospect a déjà été
   enregistré par CE partenaire il y a moins de 30 jours. On l'affiche sous le
   champ email (jamais un « non enregistré » générique) et on rappelle que son
   antériorité est conservée — le but est de rassurer, pas de rejeter.

   La QUALIFICATION reste un acte interne : la soumission ne crée jamais de
   lead par elle-même ; la colonne « Dossier ouvert » reflète seulement le
   moment où l'équipe l'a transformée.
   ========================================================================== */

const TON_STATUT = {
  soumis: 'info',
  qualifie: 'primary',
  converti: 'success',
  rejete: 'neutral',
}

const VIDE = {
  nom_prospect: '',
  email_prospect: '',
  telephone_prospect: '',
  ville: '',
  note: '',
}

export default function PortailPartenaireLeads() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [agree, setAgree] = useState(true)
  const [form, setForm] = useState(VIDE)
  const [erreursChamps, setErreursChamps] = useState({})
  const [busy, setBusy] = useState(false)

  const charger = () => {
    setLoading(true)
    portailApi.partenaire.soumissions.liste()
      .then((r) => {
        setRows(r.data?.results ?? [])
        setErreur(false)
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // Différé d'un microtask (react-hooks/set-state-in-effect).
    Promise.resolve().then(charger)
  }, [])

  // NTPRT32 — l'AGRÉMENT commande le droit de déposer une affaire. Le serveur
  // reste l'autorité (403 motivé) ; on lit ici le statut déjà publié par le
  // tableau de bord pour ne pas faire remplir un formulaire pour rien. Une
  // lecture qui échoue laisse le formulaire ouvert : c'est le serveur qui
  // tranche, jamais un écran qui se ferme tout seul.
  useEffect(() => {
    let annule = false
    portailApi.partenaire.tableauDeBord()
      .then((r) => {
        if (!annule) setAgree(r.data?.statut_onboarding === 'agree')
      })
      .catch(() => {})
    return () => { annule = true }
  }, [])

  const set = (champ) => (e) => {
    setForm((f) => ({ ...f, [champ]: e.target.value }))
  }

  const soumettre = async (e) => {
    e.preventDefault()
    setErreursChamps({})
    setBusy(true)
    try {
      await portailApi.partenaire.soumissions.creer(form)
      toast.success('Affaire enregistrée. Nous revenons vers vous rapidement.')
      setForm(VIDE)
      charger()
    } catch (err) {
      const data = err?.response?.data || {}
      // Le serveur NOMME le champ fautif (nom_prospect / email_prospect) :
      // on affiche son message sous CE champ.
      const champs = {}
      if (data.nom_prospect) champs.nom_prospect = data.nom_prospect
      if (data.email_prospect) champs.email_prospect = data.email_prospect
      if (!Object.keys(champs).length) {
        champs.global = data.detail || "L'enregistrement n'a pas abouti."
      }
      setErreursChamps(champs)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <Handshake className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes affaires
        </h1>
      </div>

      {!agree && (
        <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          Votre agrément n’est pas encore actif : vous pourrez enregistrer vos
          affaires dès l’activation de votre partenariat. Vos affaires déjà
          déposées restent consultables ci-dessous.
        </p>
      )}

      <Card className="p-4">
        <Form onSubmit={soumettre} className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Enregistrez un prospect pour protéger votre antériorité. Nous vous
            tenons informé de son avancement.
          </p>
          <FormField label="Nom du prospect" required
                     error={erreursChamps.nom_prospect}>
            <Input value={form.nom_prospect} onChange={set('nom_prospect')} />
          </FormField>
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Email du prospect"
                       error={erreursChamps.email_prospect}>
              <Input type="email" value={form.email_prospect}
                     onChange={set('email_prospect')} />
            </FormField>
            <FormField label="Téléphone du prospect">
              <Input value={form.telephone_prospect}
                     onChange={set('telephone_prospect')} />
            </FormField>
          </div>
          <FormField label="Ville">
            <Input value={form.ville} onChange={set('ville')} />
          </FormField>
          <FormField label="Ce qu’il faut savoir (facultatif)">
            <Input value={form.note} onChange={set('note')} />
          </FormField>
          {erreursChamps.global ? (
            <p className="text-sm text-destructive" role="alert">
              {erreursChamps.global}
            </p>
          ) : null}
          <div>
            <Button type="submit" disabled={busy || !agree}>
              Enregistrer cette affaire
            </Button>
          </div>
        </Form>
      </Card>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Chargement de vos affaires…
        </div>
      ) : erreur ? (
        <EmptyState
          title="Affaires indisponibles"
          description="Vos affaires n’ont pas pu être chargées. Réessayez plus tard."
        />
      ) : rows.length === 0 ? (
        <EmptyState
          title="Aucune affaire enregistrée"
          description="Enregistrez votre premier prospect avec le formulaire ci-dessus."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((s) => (
            <Card key={s.id} className="flex flex-col gap-1 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{s.nom_prospect}</p>
                  <p className="text-xs text-muted-foreground">
                    Enregistré le {formatDate(s.date_soumission)}
                    {s.ville ? ` — ${s.ville}` : ''}
                  </p>
                </div>
                <Badge tone={TON_STATUT[s.statut] || 'neutral'}>
                  {s.statut_display}
                </Badge>
              </div>
              {s.converti && (
                <p className="text-sm text-muted-foreground">
                  Dossier ouvert par notre équipe.
                </p>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
