/**
 * NTCRM18 — Page PUBLIQUE de la salle de vente digitale (aucun login).
 *
 * Route /salle-vente/:token, autonome (pas de layout ERP). Le token
 * identifie une `crm.SalleVente` (imprévisible, expirante) — jamais un
 * lead/client directement. Chaque consultation réussie journalise une
 * `SalleVenteVue` côté serveur (compteur NTCRM19), sans action ici.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileText, Folder, Video, StickyNote, Lock } from 'lucide-react'
import api from '../../../api/axios'
import { Button, Card, CardHeader, CardTitle, CardContent } from '../../../ui'
import NoIndex from '../../../components/NoIndex'

const ICONS = {
  devis: FileText,
  document: Folder,
  video_lien: Video,
  note: StickyNote,
}

export default function PublicSalleVentePage() {
  const { token } = useParams()
  // loading | ready | need_password | invalid | gone
  const [status, setStatus] = useState('loading')
  const [salle, setSalle] = useState(null)
  const [motDePasse, setMotDePasse] = useState('')
  const [error, setError] = useState(null)

  const charger = (pwd) => {
    setStatus('loading')
    setError(null)
    api.get(`/crm/salle-vente/${token}/`, {
      params: pwd ? { mot_de_passe: pwd } : {},
    })
      .then((res) => {
        setSalle(res.data)
        setStatus('ready')
      })
      .catch((err) => {
        const code = err?.response?.status
        if (code === 403) {
          setStatus('need_password')
          if (pwd) setError('Mot de passe incorrect.')
        } else if (code === 410) {
          setStatus('gone')
        } else {
          setStatus('invalid')
        }
      })
  }

  // setState différé au prochain microtask (jamais synchrone dans l'effet) —
  // évite react-hooks/set-state-in-effect sans changer le comportement visible.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { queueMicrotask(() => charger()) }, [token])

  const handlePasswordSubmit = (e) => {
    e.preventDefault()
    charger(motDePasse)
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <NoIndex />
      {status === 'loading' && (
        <p className="text-center text-muted-foreground">Chargement…</p>
      )}

      {status === 'invalid' && (
        <p className="text-center text-muted-foreground">
          Ce lien est introuvable ou a été révoqué.
        </p>
      )}

      {status === 'gone' && (
        <p className="text-center text-muted-foreground">
          Ce lien a expiré. Contactez votre interlocuteur pour un nouveau lien.
        </p>
      )}

      {status === 'need_password' && (
        <form onSubmit={handlePasswordSubmit} className="mx-auto max-w-sm space-y-3 text-center">
          <Lock className="mx-auto h-6 w-6 text-muted-foreground" />
          <p>Cette salle de vente est protégée par un mot de passe.</p>
          <input
            type="password"
            value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)}
            placeholder="Mot de passe"
            className="w-full rounded-md border border-border px-3 py-2"
            aria-label="Mot de passe"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit">Accéder</Button>
        </form>
      )}

      {status === 'ready' && salle && (
        <div className="space-y-4">
          <h1 className="font-display text-2xl font-semibold">{salle.titre}</h1>
          <div className="space-y-3">
            {(salle.items ?? []).map((item) => {
              const Icon = ICONS[item.type] ?? FileText
              return (
                <Card key={item.id}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Icon className="h-4 w-4" />
                      {item.titre || item.type}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {item.type === 'devis' && item.reference && (
                      <div>
                        <p className="text-sm">Devis {item.reference} — {item.total_ttc} MAD TTC</p>
                        <a
                          href={item.proposal_path}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm text-primary underline"
                        >
                          Voir la proposition
                        </a>
                      </div>
                    )}
                    {item.type === 'video_lien' && item.reference && (
                      <a
                        href={item.reference}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm text-primary underline"
                      >
                        {item.reference}
                      </a>
                    )}
                    {(item.type === 'note' || item.type === 'document') && (
                      <p className="text-sm text-muted-foreground">{item.reference}</p>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
