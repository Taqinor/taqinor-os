/**
 * XKB19 — Page PUBLIQUE de consultation d'un article partagé (aucun login).
 *
 * Route /kb/public/:token, autonome (pas de layout ERP) — même motif que
 * /rdv/:token (PublicBookingPage) : le jeton est l'UNIQUE secret d'accès,
 * jamais une identité/société lue de la requête. Sans jeton valide/actif :
 * message honnête (jamais un faux succès). 410 = lien expiré, 404 = lien
 * introuvable ou dépublié (indistinct, pas de fuite d'information).
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import kbApi from '../../api/kbApi'
import { KbMarkdownBody } from '../../features/kb/kbMarkdown'
import NoIndex from '../../components/NoIndex'

export default function PublicArticlePage() {
  const { token } = useParams()
  const [status, setStatus] = useState('loading') // loading | valid | invalid | expired
  const [article, setArticle] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    kbApi.getPublicArticle(token)
      .then((res) => {
        if (!alive) return
        setArticle(res.data)
        setStatus('valid')
      })
      .catch((err) => {
        if (!alive) return
        const code = err?.response?.status
        setError(
          err?.response?.data?.detail
          || "Ce lien est introuvable ou n'est plus disponible.")
        setStatus(code === 410 ? 'expired' : 'invalid')
      })
    return () => { alive = false }
  }, [token])

  return (
    <div className="ui-root page" style={{ maxWidth: 720, margin: '40px auto' }}>
      <NoIndex />
      {status === 'loading' && <p>Chargement…</p>}
      {(status === 'invalid' || status === 'expired') && (
        <p role="alert" className="page-error">{error}</p>
      )}
      {status === 'valid' && article && (
        <article dir={article.langue === 'ar' ? 'rtl' : 'ltr'}>
          {article.categorie && (
            <p style={{ color: 'var(--muted-foreground, #6b7280)', marginBottom: 4 }}>
              {article.categorie}
            </p>
          )}
          <h1>{article.titre}</h1>
          {!article.corps && <span>(Aucun contenu)</span>}
          {article.corps && (article.corps_format === 'markdown'
            ? <KbMarkdownBody corps={article.corps} />
            : <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{article.corps}</div>)}
        </article>
      )}
    </div>
  )
}
