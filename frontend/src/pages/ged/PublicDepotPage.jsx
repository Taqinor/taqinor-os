/**
 * XGED7 — Page PUBLIQUE de DÉPÔT de fichier (upload-request, sans login).
 *
 * Route /ged/depot/:token (hors coquille authentifiée) : la destination d'un
 * lien de dépôt tokenisé (imprévisible, expirant, à quota). Le déposant voit le
 * message d'instruction + le quota restant, dépose un fichier, jamais le contenu
 * déjà présent dans le dossier cible. Sans jeton valide : message honnête.
 */
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import gedApi from '../../api/gedApi'
import { Button } from '../../ui'
import { errMessage } from '../../features/ged/advanced/shared.js'
import NoIndex from '../../components/NoIndex'

// VX202 — throttle CLIENT de re-soumission (défense en profondeur ; le vrai
// rate-limit vit côté nginx, backend/nginx/nginx.conf) : un échec ne doit pas
// permettre un ré-essai en rafale immédiat.
const THROTTLE_MS = 4000

export default function PublicDepotPage() {
  const { token } = useParams()
  const [status, setStatus] = useState('loading') // loading | valid | invalid | done
  const [info, setInfo] = useState(null)
  const [error, setError] = useState(null)
  const [file, setFile] = useState(null)
  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [throttled, setThrottled] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    let alive = true
    gedApi.getDepotPublic(token)
      .then((res) => {
        if (!alive) return
        setInfo(res.data || {})
        setStatus('valid')
      })
      .catch((err) => {
        if (!alive) return
        setError(errMessage(err, 'Ce lien de dépôt est introuvable ou a expiré.'))
        setStatus('invalid')
      })
    return () => { alive = false }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (throttled) return
    if (!file) { setError('Choisissez un fichier à déposer.'); return }
    setError(null)
    setSubmitting(true)
    setThrottled(true)
    setTimeout(() => setThrottled(false), THROTTLE_MS)
    try {
      await gedApi.deposerPublique(token, { file, nom: nom.trim(), email: email.trim() })
      setStatus('done')
    } catch (err) {
      setError(errMessage(err, 'Le dépôt a échoué — réessayez ou contactez-nous.'))
      if (err?.response?.status === 410 || err?.response?.status === 404) {
        setStatus('invalid')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 520, margin: '40px auto', padding: '0 16px' }}>
      <NoIndex />
      <h2>Déposer un document</h2>

      {status === 'loading' && <p role="status">Chargement…</p>}
      {status === 'invalid' && <p role="alert" className="page-error">{error}</p>}
      {status === 'done' && (
        <p role="status">
          Merci ! Votre fichier a bien été déposé. Vous pouvez fermer cette page.
        </p>
      )}

      {status === 'valid' && (
        <form onSubmit={handleSubmit} noValidate style={{ marginTop: 16 }}>
          {info?.message && <p>{info.message}</p>}
          {typeof info?.quota_fichiers_restant === 'number' && (
            <p className="text-sm text-muted-foreground">
              Fichiers encore acceptés : {info.quota_fichiers_restant}
            </p>
          )}
          <div style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="ged-depot-file">Fichier</label>
            <input
              id="ged-depot-file"
              ref={fileRef}
              type="file"
              className="form-control"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="ged-depot-nom">Votre nom (optionnel)</label>
            <input
              id="ged-depot-nom"
              className="form-control"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="ged-depot-email">Votre email (optionnel)</label>
            <input
              id="ged-depot-email"
              type="email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          {error && <p role="alert" className="page-error">{error}</p>}
          <Button type="submit" disabled={submitting || !file || throttled}>
            {submitting ? 'Dépôt…' : 'Déposer'}
          </Button>
          {throttled && !submitting && (
            <p className="text-sm text-muted-foreground">Veuillez patienter avant de réessayer.</p>
          )}
        </form>
      )}
    </div>
  )
}
