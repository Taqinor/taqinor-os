import { useEffect, useState } from 'react'
import { PhoneCall } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Button, Spinner,
  Input, Label,
} from '../../ui'
import { useServerFieldErrors } from '../../hooks/useServerFieldErrors'
import { formatDate } from '../../lib/format'

/* ============================================================================
   « Liste froide » (fondateur, 17/11/2026) — la commerciale PREND elle-même ses
   appels de dossiers au Froid quand sa journée le permet, au lieu d'étapes
   datées poussées sur des jours déjà pleins. Sœur de la carte « Anciens leads à
   placer » (dossiers NON Froid). Contrat `apps/crm/contract_samples/liste_froide.json`
   (`GET`/`POST /crm/leads/liste-froide/`) : chaque chiffre de cette carte vient
   du serveur, jamais d'un recompte écran. Visible pour qui a des dossiers dans
   le vivier (ou des appels encore ouverts) ; une lecture impossible la tait. Un
   refus s'affiche SOUS le bouton qui l'a causé, jamais en toast nu.
   `onPris` : la page relit la file du jour et le contrôle après une prise.
   20/11/2026 (fondateur) — les dossiers repris d'Odoo sans responsable passent
   en premier (`restes_odoo`), et la commerciale CHOISIT combien elle prend : le
   champ part de `prise_proposee`, borné par `prise_max` ; un nombre hors bornes
   est dit sous le champ, jamais corrigé à sa place.
   ========================================================================== */

const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`

/** « 103 dossiers repris d’Odoo, 14 dossiers déjà chiffrés et 100 demandes sans
    réponse attendent un appel. » */
function phraseVivier(restes, chiffres, sansReponse) {
  const morceaux = []
  if (restes > 0) morceaux.push(`${pluriel(restes, 'dossier')} repris d’Odoo`)
  if (chiffres > 0) morceaux.push(`${pluriel(chiffres, 'dossier')} déjà chiffré${chiffres > 1 ? 's' : ''}`)
  if (sansReponse > 0) morceaux.push(`${pluriel(sansReponse, 'demande')} sans réponse`)
  if (morceaux.length === 0) return 'Aucun dossier de la liste froide ne vous attend.'
  const liste = morceaux.length > 1
    ? `${morceaux.slice(0, -1).join(', ')} et ${morceaux[morceaux.length - 1]}`
    : morceaux[0]
  return `${liste} attend${restes + chiffres + sansReponse > 1 ? 'ent' : ''} un appel.`
}

/** Ce que le champ « Combien de dossiers » affiche à l'arrivée d'un état. */
const proposee = (etat) => {
  const n = etat?.prise_proposee ?? etat?.prise_max ?? 0
  return n > 0 ? String(n) : ''
}

/** Le nombre saisi, s'il est un entier entre 1 et `max` ; sinon `null`. */
function nombreChoisi(saisie, max) {
  const n = Number(saisie)
  return saisie !== '' && Number.isInteger(n) && n >= 1 && n <= max ? n : null
}

/** La ligne qui suit une prise réussie. */
function phrasePrise({ nombre_places: n, du_jour: duJour, pour_le: pourLe }) {
  if (!n) return 'Aucun appel ajouté : la liste a changé entre-temps.'
  const debut = `${pluriel(n, 'appel')} ajouté${n > 1 ? 's' : ''} à vos étapes`
  return duJour ? `${debut} du jour.` : `${debut}, pour le ${formatDate(pourLe)}.`
}

export default function ListeFroideCard({ onPris } = {}) {
  const [etat, setEtat] = useState(null)
  const [saisie, setSaisie] = useState('')
  const [busy, setBusy] = useState(false)
  const [succes, setSucces] = useState('')
  const { errors, setFromResponse, clearAll } = useServerFieldErrors()

  useEffect(() => {
    let actif = true
    crmApi.getListeFroide()
      .then((r) => { if (actif) { setEtat(r.data); setSaisie(proposee(r.data)) } })
      .catch(() => { if (actif) setEtat(null) })
    return () => { actif = false }
  }, [])

  if (!etat) return null
  const {
    restes_odoo: restes = 0,
    dossiers_chiffres: chiffres, demandes_sans_reponse: sansReponse,
    appels_ouverts: ouverts, plafond_appels_ouverts: plafond,
    prise_max: priseMax, peut_prendre: peutPrendre, raison,
  } = etat
  if (restes + chiffres + sansReponse + ouverts === 0 && !succes) return null
  const nombre = nombreChoisi(saisie, priseMax)
  const horsBornes = peutPrendre && nombre === null

  const prendre = () => {
    setBusy(true)
    setSucces('')
    clearAll()
    crmApi.prendreListeFroide(nombre)
      .then((r) => {
        setEtat(r.data)
        setSaisie(proposee(r.data))
        setSucces(phrasePrise(r.data))
        if (typeof onPris === 'function') onPris(r.data)
      })
      .catch((e) => setFromResponse(e?.response?.data, {
        fallbackField: 'nombre', fallback: 'Prise impossible pour le moment.',
      }))
      .finally(() => setBusy(false))
  }

  const erreur = errors.nombre
  const motif = !peutPrendre ? raison : ''
  return (
    <Card data-testid="liste-froide-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PhoneCall className="h-4 w-4" /> Liste froide
        </CardTitle>
        <CardDescription data-testid="liste-froide-vivier">
          {phraseVivier(restes, chiffres, sansReponse)}
          {restes > 0 && ' Les dossiers repris d’Odoo passent en premier : en prendre un en fait votre dossier.'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground" data-testid="liste-froide-ouverts">
          Vos appels de la liste froide encore ouverts : {ouverts} / {plafond}.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {peutPrendre && (
            <div className="flex items-center gap-1.5">
              <Label className="text-xs" htmlFor="liste-froide-nombre">Combien de dossiers</Label>
              <Input
                id="liste-froide-nombre" type="number" inputMode="numeric"
                min="1" max={priseMax} step="any" className="w-20"
                value={saisie} disabled={busy} invalid={horsBornes}
                aria-describedby={horsBornes ? 'liste-froide-nombre-aide' : undefined}
                onChange={(e) => setSaisie(e.target.value)}
              />
            </div>
          )}
          <Button
            size="sm" onClick={prendre} disabled={!peutPrendre || nombre === null || busy}
            aria-describedby={erreur || motif ? 'liste-froide-motif' : undefined}
          >
            {nombre !== null ? `Prendre ${pluriel(nombre, 'dossier')}` : 'Prendre des dossiers'}
          </Button>
          {busy && <Spinner className="h-4 w-4" label="Prise en cours…" />}
        </div>
        {horsBornes && (
          <p id="liste-froide-nombre-aide" className="mt-1.5 text-sm text-destructive">
            {priseMax > 1
              ? `Choisissez un nombre entier entre 1 et ${priseMax}.`
              : 'Un seul dossier peut être pris pour le moment.'}
          </p>
        )}
        {(erreur || motif) && (
          <p
            id="liste-froide-motif" role={erreur ? 'alert' : undefined}
            className={`mt-1.5 text-sm ${erreur ? 'text-destructive' : 'text-muted-foreground'}`}
          >
            {erreur || motif}
          </p>
        )}
        {succes && (
          <p className="mt-1.5 text-sm text-foreground" data-testid="liste-froide-succes">{succes}</p>
        )}
      </CardContent>
    </Card>
  )
}
