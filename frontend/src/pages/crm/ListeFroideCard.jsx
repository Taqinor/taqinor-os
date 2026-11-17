import { useEffect, useState } from 'react'
import { PhoneCall } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Button, Spinner,
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
   ========================================================================== */

const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`

/** « 14 dossiers déjà chiffrés et 100 demandes sans réponse attendent un appel. » */
function phraseVivier(chiffres, sansReponse) {
  const morceaux = []
  if (chiffres > 0) morceaux.push(`${pluriel(chiffres, 'dossier')} déjà chiffré${chiffres > 1 ? 's' : ''}`)
  if (sansReponse > 0) morceaux.push(`${pluriel(sansReponse, 'demande')} sans réponse`)
  if (morceaux.length === 0) return 'Aucun dossier de la liste froide ne vous attend.'
  return `${morceaux.join(' et ')} attend${chiffres + sansReponse > 1 ? 'ent' : ''} un appel.`
}

/** La ligne qui suit une prise réussie. */
function phrasePrise({ nombre_places: n, du_jour: duJour, pour_le: pourLe }) {
  if (!n) return 'Aucun appel ajouté : la liste a changé entre-temps.'
  const debut = `${pluriel(n, 'appel')} ajouté${n > 1 ? 's' : ''} à vos étapes`
  return duJour ? `${debut} du jour.` : `${debut}, pour le ${formatDate(pourLe)}.`
}

export default function ListeFroideCard({ onPris } = {}) {
  const [etat, setEtat] = useState(null)
  const [busy, setBusy] = useState(false)
  const [succes, setSucces] = useState('')
  const { errors, setFromResponse, clearAll } = useServerFieldErrors()

  useEffect(() => {
    let actif = true
    crmApi.getListeFroide()
      .then((r) => { if (actif) setEtat(r.data) })
      .catch(() => { if (actif) setEtat(null) })
    return () => { actif = false }
  }, [])

  if (!etat) return null
  const {
    dossiers_chiffres: chiffres, demandes_sans_reponse: sansReponse,
    appels_ouverts: ouverts, plafond_appels_ouverts: plafond,
    prise_max: priseMax, peut_prendre: peutPrendre, raison,
  } = etat
  if (chiffres + sansReponse + ouverts === 0 && !succes) return null

  const prendre = () => {
    setBusy(true)
    setSucces('')
    clearAll()
    crmApi.prendreListeFroide(priseMax)
      .then((r) => {
        setEtat(r.data)
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
          {phraseVivier(chiffres, sansReponse)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground" data-testid="liste-froide-ouverts">
          Vos appels de la liste froide encore ouverts : {ouverts} / {plafond}.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm" onClick={prendre} disabled={!peutPrendre || busy}
            aria-describedby={erreur || motif ? 'liste-froide-motif' : undefined}
          >
            {priseMax > 0 ? `Prendre ${pluriel(priseMax, 'dossier')}` : 'Prendre des dossiers'}
          </Button>
          {busy && <Spinner className="h-4 w-4" label="Prise en cours…" />}
        </div>
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
