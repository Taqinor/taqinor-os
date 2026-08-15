/**
 * WIR214 — Page PUBLIQUE « Signalement chantier » via QR QHSE (aucun login).
 * Route /qhse/signalement/:token — le token DOIT rester en phase avec
 * `apps/qhse/services.py:generer_qr_signalement` (jamais modifié ici) qui
 * encode exactement cette URL dans le QR imprimé sur chantier.
 *
 * Même patron que EquipementSignalerPage (XSAV19) : GET du payload au
 * montage pour vérifier la validité du lien (jeton révoqué → message FR
 * honnête, jamais une fausse réussite), puis formulaire type danger/incident
 * + description, POST vers le même endpoint public tokenisé.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../api/axios'
import { Button, Textarea, Input } from '../../ui'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'

export default function SignalementPublicPage() {
  const { token } = useParams()
  const [type, setType] = useState('danger')
  const [description, setDescription] = useState('')
  const [nom, setNom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [libelle, setLibelle] = useState('')
  const [status, setStatus] = useState('loading') // loading | form | submitting | done | invalid | error
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.get(`/qhse/public/signalement/${token}/`)
      .then((res) => {
        if (cancelled) return
        setLibelle(res.data?.libelle || '')
        setStatus('form')
      })
      .catch(() => { if (!cancelled) setStatus('invalid') })
    return () => { cancelled = true }
  }, [token])

  // VX169 — garde de navigation IN-APP (clic lien pendant la saisie).
  const dirty = status === 'form' && Boolean(description || nom || telephone)
  useNavigationGuard(dirty)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!description.trim()) return
    setStatus('submitting')
    setError(null)
    try {
      await api.post(`/qhse/public/signalement/${token}/`, {
        type_signalement: type,
        description,
        nom: nom.trim() || undefined,
        telephone: telephone.trim() || undefined,
      })
      setStatus('done')
    } catch (err) {
      setError(
        err?.response?.data?.detail
        || "Impossible d'envoyer votre signalement — réessayez.")
      setStatus(err?.response?.status === 404 ? 'invalid' : 'error')
    }
  }

  if (status === 'loading') {
    return (
      <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
        <p role="status">Chargement…</p>
      </div>
    )
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <h2>Signalement chantier</h2>

      {status === 'invalid' && (
        <p role="alert" className="page-error">
          Ce lien de signalement est introuvable ou a été révoqué — vérifiez
          le QR code ou contactez le responsable QHSE directement.
        </p>
      )}

      {status === 'done' && (
        <p role="status">
          Merci, votre signalement a bien été enregistré. L’équipe QHSE va le
          traiter.
        </p>
      )}

      {(status === 'form' || status === 'submitting' || status === 'error') && (
        <form onSubmit={handleSubmit} noValidate>
          {libelle && (
            <p className="text-sm text-muted-foreground">{libelle}</p>
          )}
          <p className="text-sm text-muted-foreground">
            Décrivez le danger ou l’incident constaté sur ce chantier.
          </p>

          <fieldset className="form-control" style={{ border: 0, padding: 0 }}>
            <legend className="form-label">Type de signalement</legend>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginRight: 16 }}>
              <input type="radio" name="type" value="danger"
                checked={type === 'danger'} onChange={() => setType('danger')} />
              Danger
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <input type="radio" name="type" value="incident"
                checked={type === 'incident'} onChange={() => setType('incident')} />
              Incident
            </label>
          </fieldset>

          <label className="form-label" htmlFor="sp-description">
            Description
          </label>
          <Textarea
            id="sp-description"
            className="form-control"
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />

          <label className="form-label" htmlFor="sp-nom">
            Nom (optionnel)
          </label>
          <Input
            id="sp-nom"
            className="form-control"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
          />

          <label className="form-label" htmlFor="sp-telephone">
            Téléphone (optionnel)
          </label>
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
