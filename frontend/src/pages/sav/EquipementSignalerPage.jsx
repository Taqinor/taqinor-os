/**
 * XSAV19 — Page PUBLIQUE « Signaler un problème » via QR équipement (aucun
 * login). Route /e/:token — autonome (pas de layout ERP), destination du QR
 * code imprimé sur l'étiquette de l'équipement (public_token, distinct du
 * jeton interne equipement_token). Même patron que PublicBookingPage
 * (XSAL17) : jeton imprévisible, message honnête si invalide, jamais de
 * fausse réussite.
 *
 * Champ caché `site_web` = honeypot anti-spam (jamais rempli par un humain) —
 * le serveur renvoie un 201 factice sans créer de ticket si rempli.
 */
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../api/axios'
import { Button, Textarea, Input } from '../../ui'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'

export default function EquipementSignalerPage() {
  const { token } = useParams()
  const [description, setDescription] = useState('')
  const [telephone, setTelephone] = useState('')
  const [photo, setPhoto] = useState(null)
  const [siteWeb, setSiteWeb] = useState('') // honeypot
  const [status, setStatus] = useState('form') // form | submitting | done | error
  const [error, setError] = useState(null)
  const [reference, setReference] = useState(null)

  // VX169 — garde de navigation IN-APP (clic lien pendant la saisie).
  const dirty = status !== 'done' && Boolean(description || telephone || photo)
  useNavigationGuard(dirty)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!description.trim()) return
    setStatus('submitting')
    setError(null)
    try {
      const form = new FormData()
      form.append('description', description)
      if (telephone.trim()) form.append('telephone', telephone)
      if (siteWeb) form.append('site_web', siteWeb)
      if (photo) form.append('photo', photo)
      const res = await api.post(
        `/public/sav/equipement/${token}/signaler/`, form,
        { headers: { 'Content-Type': 'multipart/form-data' } })
      setReference(res.data?.reference || null)
      setStatus('done')
    } catch (err) {
      setError(
        err?.response?.data?.detail
        || "Impossible d'envoyer votre signalement — réessayez.")
      setStatus(err?.response?.status === 404 ? 'invalid' : 'error')
    }
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <h2>Signaler un problème</h2>

      {status === 'invalid' && (
        <p role="alert" className="page-error">
          Ce lien est invalide ou introuvable — vérifiez le QR code ou
          contactez-nous directement.
        </p>
      )}

      {status === 'done' && (
        <p role="status">
          Merci, votre signalement a bien été enregistré
          {reference ? ` (référence ${reference})` : ''}. Notre équipe SAV va
          le traiter et vous recontacter.
        </p>
      )}

      {(status === 'form' || status === 'submitting' || status === 'error') && (
        <form onSubmit={handleSubmit} noValidate>
          <p className="text-sm text-muted-foreground">
            Décrivez le problème rencontré avec cet équipement — notre équipe
            après-vente sera notifiée.
          </p>

          <label className="form-label" htmlFor="es-description">
            Description du problème
          </label>
          <Textarea
            id="es-description"
            className="form-control"
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />

          <label className="form-label" htmlFor="es-telephone">
            Téléphone (optionnel)
          </label>
          <Input
            id="es-telephone"
            type="tel"
            className="form-control"
            value={telephone}
            onChange={(e) => setTelephone(e.target.value)}
          />

          <label className="form-label" htmlFor="es-photo">
            Photo (optionnel)
          </label>
          <input
            id="es-photo"
            type="file"
            accept="image/*"
            className="form-control"
            onChange={(e) => setPhoto(e.target.files?.[0] || null)}
          />

          {/* Honeypot anti-spam — champ caché, invisible pour un humain. */}
          <input
            type="text"
            name="site_web"
            value={siteWeb}
            onChange={(e) => setSiteWeb(e.target.value)}
            tabIndex={-1}
            autoComplete="off"
            style={{ position: 'absolute', left: '-9999px', width: 1, height: 1 }}
            aria-hidden="true"
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
