/**
 * WIR214 — Page PUBLIQUE « Signalement chantier » via QR (aucun login).
 * Route /qhse/signalement/:token — autonome (pas de layout ERP), destination
 * du QR code imprimé sur le panneau chantier (`LienSignalementPublic.token`,
 * généré par `generer_qr_signalement` — INCHANGÉ ici, il encode déjà
 * `/qhse/signalement/<token>/`). Même patron que EquipementSignalerPage
 * (XSAV19) : jeton imprévisible, message honnête si invalide/révoqué,
 * jamais de fausse réussite. La société ET le chantier sont TOUJOURS résolus
 * depuis le jeton côté serveur — jamais lus du corps de la requête.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../api/axios'
import { Button, Textarea, Input, Label } from '../../ui'
import { FieldSelect } from '../../features/qhse/QhseForm'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'

const TYPE_OPTS = [
  { value: 'danger', label: 'Danger observé' },
  { value: 'incident', label: 'Incident' },
]

export default function SignalementPublicPage() {
  const { token } = useParams()
  const [lienStatus, setLienStatus] = useState('loading') // loading|valide|invalide
  const [libelle, setLibelle] = useState('')

  const [typeSignalement, setTypeSignalement] = useState('danger')
  const [description, setDescription] = useState('')
  const [nom, setNom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [status, setStatus] = useState('form') // form|submitting|done|error
  const [error, setError] = useState(null)
  const [reference, setReference] = useState(null)

  // VX169 — garde de navigation IN-APP (clic lien pendant la saisie).
  const dirty = status !== 'done' && Boolean(description || nom || telephone)
  useNavigationGuard(dirty)

  useEffect(() => {
    let vivant = true
    api.get(`/qhse/public/signalement/${token}/`)
      .then((res) => {
        if (!vivant) return
        setLibelle(res.data?.libelle || '')
        setLienStatus('valide')
      })
      .catch(() => { if (vivant) setLienStatus('invalide') })
    return () => { vivant = false }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!description.trim()) return
    setStatus('submitting')
    setError(null)
    try {
      const res = await api.post(`/qhse/public/signalement/${token}/`, {
        type_signalement: typeSignalement,
        description,
        nom: nom.trim() || undefined,
        telephone: telephone.trim() || undefined,
      })
      setReference(res.data?.id ?? null)
      setStatus('done')
    } catch (err) {
      setError(
        err?.response?.data?.detail
        ?? "Impossible d'envoyer votre signalement — réessayez.")
      setStatus(err?.response?.status === 404 ? 'invalid' : 'error')
    }
  }

  if (lienStatus === 'loading') {
    return (
      <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
        <p>Chargement…</p>
      </div>
    )
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <h2>Signalement chantier{libelle ? ` — ${libelle}` : ''}</h2>

      {(lienStatus === 'invalide' || status === 'invalid') && (
        <p role="alert" className="page-error">
          Ce lien de signalement est introuvable ou a été révoqué — vérifiez
          le QR code ou contactez-nous directement.
        </p>
      )}

      {lienStatus === 'valide' && status === 'done' && (
        <p role="status">
          Merci, votre signalement a bien été enregistré
          {reference ? ` (référence ${reference})` : ''}. Notre équipe QHSE
          va le traiter.
        </p>
      )}

      {lienStatus === 'valide'
        && (status === 'form' || status === 'submitting' || status === 'error') && (
        <form onSubmit={handleSubmit} noValidate>
          <p className="text-sm text-muted-foreground">
            Signalez un danger observé ou un incident sur ce chantier —
            notre équipe QHSE sera notifiée.
          </p>

          <Label htmlFor="sp-type">Type de signalement</Label>
          <FieldSelect
            id="sp-type"
            value={typeSignalement}
            onValueChange={setTypeSignalement}
            options={TYPE_OPTS}
          />

          <Label htmlFor="sp-description">Description</Label>
          <Textarea
            id="sp-description"
            className="form-control"
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />

          <Label htmlFor="sp-nom">Nom (optionnel)</Label>
          <Input
            id="sp-nom"
            className="form-control"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
          />

          <Label htmlFor="sp-telephone">Téléphone (optionnel)</Label>
          <Input
            id="sp-telephone"
            type="tel"
            className="form-control"
            value={telephone}
            onChange={(e) => setTelephone(e.target.value)}
          />

          {error && <p role="alert" className="page-error">{error}</p>}

          <Button type="submit" disabled={status === 'submitting' || !description.trim()}>
            {status === 'submitting' ? 'Envoi…' : 'Envoyer le signalement'}
          </Button>
        </form>
      )}
    </div>
  )
}
