import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, Checkbox, Dialog, DialogContent, DialogFooter,
  DialogHeader, DialogTitle, EmptyState, Input, Label, Spinner, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT10 — « Mes devis » (portail client authentifié).
   ----------------------------------------------------------------------------
   Liste + PDF + acceptation. Le PDF ouvre l'UNIQUE chemin canonique
   `/api/django/ventes/devis/<id>/proposal/` (CLAUDE.md règle #4) — jamais un
   rendu propre au portail. L'acceptation POSTe sur l'endpoint portail, qui
   appelle le service d'acceptation UNIQUE de `ventes` : la chaîne aval (statut
   accepté → BC/facture → chantier) est donc identique au lien public.

   Le consentement e-signature est EXPLICITE (QX9, loi 43-20) : la case n'est
   jamais pré-cochée et le bouton reste désactivé tant qu'elle ne l'est pas.

   CIQ322 (D-CIQ-11, contrat `acceptation_entreprise.json`) — une ligne qui
   porte `exige_identite_entreprise` (devis commercial / industriel) demande en
   plus la raison sociale, la qualité du signataire et l'ICE, envoyés dans le
   bloc `entreprise`. Le serveur valide (même règle que la page publique) ;
   son 400 `{detail, champ}` s'affiche SOUS le champ fautif.
   ========================================================================== */

const CHAMPS_ENTREPRISE = [
  { cle: 'raison_sociale', label: 'Raison sociale', placeholder: 'Nom de la société' },
  { cle: 'signataire_qualite', label: 'Qualité du signataire', placeholder: 'Ex. directeur général, gérant' },
  { cle: 'ice', label: 'ICE', placeholder: '15 chiffres' },
]
const ENTREPRISE_VIDE = { raison_sociale: '', signataire_qualite: '', ice: '' }

export default function PortailClientDevis() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [aSigner, setASigner] = useState(null)
  const [nom, setNom] = useState('')
  const [consent, setConsent] = useState(false)
  const [option, setOption] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [entreprise, setEntreprise] = useState(ENTREPRISE_VIDE)
  const [erreurs, setErreurs] = useState({})

  const charger = () => {
    setLoading(true)
    portailApi.devis.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // Différé d'un microtask : `charger` pose l'état de chargement de façon
    // synchrone, ce qui déclenche un rendu en cascade
    // (react-hooks/set-state-in-effect). Comportement inchangé.
    Promise.resolve().then(charger)
  }, [])

  const ouvrirSignature = (devis) => {
    setASigner(devis)
    setNom('')
    setConsent(false)
    setEntreprise(ENTREPRISE_VIDE)
    setErreurs({})
    setOption('')
  }

  const exigeEntreprise = !!aSigner?.exige_identite_entreprise
  const entrepriseComplete = !exigeEntreprise
    || CHAMPS_ENTREPRISE.every(({ cle }) => entreprise[cle].trim())
  const majEntreprise = (cle, valeur) => {
    setEntreprise((e) => ({ ...e, [cle]: valeur }))
    setErreurs((e) => ({ ...e, [`entreprise.${cle}`]: undefined }))
  }

  const accepter = async () => {
    if (!aSigner || !nom.trim() || !consent || !entrepriseComplete) return
    if (aSigner.deux_options && !option) return
    setEnvoi(true)
    setErreurs({})
    const corps = { nom: nom.trim(), consent_esign: true }
    // ADOC114 — devis à deux options : le client choisit, le serveur
    // refuse (400) un corps sans `option`.
    if (aSigner.deux_options) corps.option = option
    if (exigeEntreprise) {
      corps.entreprise = Object.fromEntries(
        CHAMPS_ENTREPRISE.map(({ cle }) => [cle, entreprise[cle].trim()]))
    }
    try {
      await portailApi.devis.accepter(aSigner.id, corps)
      toast.success('Devis accepté. Merci !')
      setASigner(null)
      charger()
    } catch (err) {
      const data = err?.response?.data
      if (data?.champ && String(data.champ).startsWith('entreprise.')) {
        setErreurs({ [data.champ]: data.detail })
      } else {
        toast.error(data?.detail || "L'acceptation n'a pas abouti.")
      }
    } finally {
      setEnvoi(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos devis…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Devis indisponibles"
        description="Vos devis n’ont pas pu être chargés. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <FileText className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes devis
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun devis"
          description="Vous n’avez aucun devis pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((d) => (
            <Card key={d.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{d.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(d.date_creation)}
                    {d.date_validite
                      ? ` — valable jusqu’au ${formatDate(d.date_validite)}`
                      : ''}
                  </p>
                  {/* QJR565 (contrat mes_devis_liste.json) — un devis corrigé
                      après envoi le dit, comme la page proposition. */}
                  {d.mis_a_jour_le && (
                    <p className="text-xs text-muted-foreground" data-testid={`devis-mis-a-jour-${d.id}`}>
                      Document mis à jour le {formatDate(d.mis_a_jour_le)}
                    </p>
                  )}
                </div>
                <Badge tone={d.accepte ? 'success' : 'neutral'}>
                  {d.statut_display}
                </Badge>
              </div>
              <p className="text-sm">
                <span className="text-muted-foreground">Total TTC : </span>
                <span className="font-medium">{formatMAD(d.total_ttc)}</span>
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="outline" size="sm">
                  <a href={portailApi.devis.pdfUrl(d.id)}
                     target="_blank" rel="noreferrer">
                    Voir le devis (PDF)
                  </a>
                </Button>
                {!d.accepte && (
                  <Button size="sm" onClick={() => ouvrirSignature(d)}>
                    Accepter
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </ul>
      )}

      <Dialog open={!!aSigner} onOpenChange={(o) => !o && setASigner(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Accepter le devis {aSigner?.reference}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="portail-signataire">Votre nom</Label>
              <Input id="portail-signataire" value={nom}
                     onChange={(e) => setNom(e.target.value)}
                     placeholder="Nom et prénom du signataire" />
            </div>
            {aSigner?.deux_options && Array.isArray(aSigner.options) && (
              <fieldset className="flex flex-col gap-1.5">
                <legend className="text-sm font-medium">Option choisie</legend>
                {aSigner.options.map((o) => (
                  <label key={o.cle} className="flex items-center gap-2 text-sm">
                    <input type="radio" name="portail-option" value={o.cle}
                           checked={option === o.cle}
                           onChange={() => setOption(o.cle)} />
                    {o.libelle}
                  </label>
                ))}
              </fieldset>
            )}
            {exigeEntreprise && CHAMPS_ENTREPRISE.map(({ cle, label, placeholder }) => {
              const id = `portail-entreprise-${cle}`
              const erreurChamp = erreurs[`entreprise.${cle}`]
              return (
                <div key={cle} className="flex flex-col gap-1.5">
                  <Label htmlFor={id}>{label}</Label>
                  <Input id={id} value={entreprise[cle]} required
                         aria-invalid={erreurChamp ? true : undefined}
                         aria-describedby={erreurChamp ? `${id}-erreur` : undefined}
                         onChange={(e) => majEntreprise(cle, e.target.value)}
                         placeholder={placeholder} />
                  {erreurChamp && (
                    <p id={`${id}-erreur`} role="alert"
                       className="text-xs text-destructive">
                      {erreurChamp}
                    </p>
                  )}
                </div>
              )
            })}
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={consent}
                        onCheckedChange={(v) => setConsent(v === true)} />
              <span>
                J’accepte ce devis et je consens à sa signature électronique.
              </span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setASigner(null)}>
              Annuler
            </Button>
            <Button onClick={accepter}
                    disabled={envoi || !nom.trim() || !consent
                      || !entrepriseComplete
                      || (aSigner?.deux_options && !option)}>
              {envoi ? 'Envoi…' : 'Confirmer l’acceptation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
