import { useContext, useEffect, useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import { Users } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import {
  Button, Checkbox, Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '../../../ui'
import useDroitMetier from '../../sav/useDroitMetier'
import { useServerFieldErrors } from '../../../hooks/useServerFieldErrors'
import { toastSuccess } from '../../../lib/toast'

/* ============================================================================
   « Déléguer mes dossiers » (fondateur, 17/11/2026) — confier d'un geste les
   dossiers encore à travailler d'un responsable à un collègue (Meryem). Les
   touches de relance suivent le responsable de leur lead : elles passent donc
   avec lui. Contrat : `apps/crm/contract_samples/lead_deleguer.json`
   (`GET`/`POST /crm/leads/deleguer/`) — la phrase de l'aperçu lit les chiffres
   du serveur, jamais un recompte écran. Un refus s'affiche SOUS le champ qui
   le cause (`useServerFieldErrors`), jamais en toast nu.
   ========================================================================== */

const plurielDossier = (n) => `${n} dossier${n > 1 ? 's' : ''}`
const plurielEtape = (n) => `${n} étape${n > 1 ? 's' : ''} ouverte${n > 1 ? 's' : ''}`

/** La phrase de l'aperçu. */
function phraseApercu(apercu) {
  const { dossiers, etapes_ouvertes: ouvertes, etapes_en_retard: retard, vers_nom: nom } = apercu
  return `${plurielDossier(dossiers)}, dont ${plurielEtape(ouvertes)} (${retard} en retard), passeront à ${nom}.`
}

export function DelegationDialog({ open, onOpenChange, de = null, deNom = '', onDone }) {
  const store = useContext(ReactReduxContext)?.store
  const moiId = store?.getState?.().auth?.user?.id
  const exclureId = de ?? moiId
  const { errors, setFromResponse, clearField, clearAll } = useServerFieldErrors()
  const [users, setUsers] = useState([])
  const [vers, setVers] = useState('')
  const [apercu, setApercu] = useState(null)
  const [prevenir, setPrevenir] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return undefined
    let actif = true
    crmApi.getAssignableUsers()
      .then((r) => { if (actif) setUsers(Array.isArray(r.data) ? r.data : []) })
      .catch(() => { if (actif) setFromResponse(null, { fallbackField: 'vers', fallback: 'Liste des collègues indisponible pour le moment.' }) })
    return () => { actif = false }
  }, [open, setFromResponse])

  useEffect(() => {
    if (!open || !vers) return undefined
    let actif = true
    const params = { vers }
    if (de) params.de = de
    crmApi.apercuDelegation(params)
      .then((r) => { if (actif) { setApercu(r.data); clearAll() } })
      .catch((e) => {
        if (!actif) return
        setApercu(null)
        setFromResponse(e?.response?.data, { fallbackField: 'vers', fallback: 'Aperçu indisponible pour le moment.' })
      })
    return () => { actif = false }
  }, [open, vers, de, setFromResponse, clearAll])

  const choisir = (valeur) => {
    setVers(valeur)
    setApercu(null)
    clearAll()
  }

  const deleguer = () => {
    if (!vers) {
      setFromResponse({ vers: ['Choisissez le collègue à qui confier les dossiers.'] })
      return
    }
    setBusy(true)
    const corps = { vers: Number(vers), prevenir_clients: prevenir }
    if (de) corps.de = de
    crmApi.deleguerDossiers(corps)
      .then((r) => {
        const { confies, vers_nom: nom } = r.data
        toastSuccess(`${plurielDossier(confies)} confié${confies > 1 ? 's' : ''} à ${nom}.`)
        onOpenChange(false)
        if (typeof onDone === 'function') onDone(r.data)
      })
      .catch((e) => setFromResponse(e?.response?.data, { fallbackField: 'submit', fallback: 'Délégation impossible pour le moment.' }))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="delegation-dialog">
        <DialogHeader>
          <DialogTitle>À qui confier {de ? `les dossiers de ${deNom || 'ce collègue'}` : 'vos dossiers'} ?</DialogTitle>
          <DialogDescription>
            Les dossiers encore à travailler (ni perdus, ni archivés, ni signés, ni opposés) et leurs étapes de relance passent au collègue choisi.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1">
          <label htmlFor="delegation-vers" className="text-sm font-medium">Collègue</label>
          <select
            id="delegation-vers" value={vers} onChange={(e) => choisir(e.target.value)}
            aria-invalid={Boolean(errors.vers || errors.de)}
            aria-describedby={errors.vers || errors.de ? 'delegation-vers-erreur' : undefined}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            onFocus={() => { clearField('vers'); clearField('de') }}
          >
            <option value="">Choisir…</option>
            {users.filter((u) => String(u.id) !== String(exclureId)).map((u) => (
              <option key={u.id} value={String(u.id)}>{u.username}</option>
            ))}
          </select>
          {(errors.vers || errors.de) && (
            <p id="delegation-vers-erreur" role="alert" className="text-sm text-destructive">
              {errors.vers || errors.de}
            </p>
          )}
        </div>
        {apercu && (
          <p className="text-sm" data-testid="delegation-apercu">{phraseApercu(apercu)}</p>
        )}
        <div className="flex items-start gap-2">
          <Checkbox
            id="delegation-prevenir" checked={prevenir}
            onCheckedChange={(v) => setPrevenir(v === true)}
          />
          <label htmlFor="delegation-prevenir" className="text-sm">
            Prévenir chaque client du changement de conseiller (une étape de passation par dossier déjà contacté)
          </label>
        </div>
        {errors.prevenir_clients && (
          <p role="alert" className="text-sm text-destructive">{errors.prevenir_clients}</p>
        )}
        {errors.submit && (
          <p role="alert" className="text-sm text-destructive">{errors.submit}</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Annuler</Button>
          <Button onClick={deleguer} disabled={busy}>Déléguer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Le bouton + sa boîte, affiché seulement avec le droit `crm_reassign`. */
export default function BoutonDeleguerDossiers({ de = null, deNom = '', onDone, className }) {
  const peut = useDroitMetier('crm_reassign')
  const [open, setOpen] = useState(false)
  if (!peut) return null
  return (
    <>
      <Button
        variant="outline" size="sm" className={className}
        onClick={() => setOpen(true)} data-testid="bouton-deleguer-dossiers"
      >
        <Users className="h-4 w-4" aria-hidden="true" />
        {de ? `Déléguer les dossiers de ${deNom || 'ce collègue'}` : 'Déléguer mes dossiers'}
      </Button>
      {open && (
        <DelegationDialog
          open onOpenChange={setOpen} de={de} deNom={deNom} onDone={onDone}
        />
      )}
    </>
  )
}
