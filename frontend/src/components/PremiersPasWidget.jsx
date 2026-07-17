// NTDMO13 — widget « Premiers pas » du Dashboard.
// Carte compacte listant la checklist d'onboarding de l'utilisateur avec une
// barre de progression (« Premiers pas — 2/6 »). Autonome : se masque dès que
// tout est fait (100 %) ou après « Tout ignorer ». Progression persistée
// côté serveur (company + user), donc stable après déconnexion/reconnexion.
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, ChevronRight, X } from 'lucide-react'
import api from '../api/axios'
import { Card, CardContent } from '../ui'

export default function PremiersPasWidget() {
  const navigate = useNavigate()
  const [resume, setResume] = useState(null)

  const load = useCallback(() => {
    api.get('/onboarding/progress/')
      .then((r) => setResume(r.data))
      .catch(() => setResume(null))
  }, [])

  useEffect(() => { load() }, [load])

  if (!resume || resume.termine || resume.total === 0) return null

  const ignoreItem = async (id) => {
    try {
      const r = await api.post(`/onboarding/progress/${id}/ignorer/`)
      setResume(r.data)
    } catch { /* silencieux — non bloquant */ }
  }
  const ignoreAll = async () => {
    try {
      const r = await api.post('/onboarding/progress/ignorer-tout/')
      setResume(r.data)
    } catch { /* silencieux */ }
  }

  return (
    <Card className="mb-4 sm:mb-5" data-testid="premiers-pas-widget">
      <CardContent className="pt-4 sm:pt-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-sm font-bold">
              Premiers pas — {resume.faits}/{resume.total}
            </h3>
            <p className="text-[11.5px] text-muted-foreground">
              Quelques étapes pour tirer le meilleur de votre ERP.
            </p>
          </div>
          <button
            type="button"
            onClick={ignoreAll}
            className="text-[11.5px] font-medium text-muted-foreground hover:text-foreground"
          >
            Tout ignorer
          </button>
        </div>

        {/* Barre de progression */}
        <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${resume.pourcentage}%` }}
            role="progressbar"
            aria-valuenow={resume.pourcentage}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Progression des premiers pas"
          />
        </div>

        <ul className="flex flex-col gap-1">
          {resume.items.map((it) => (
            <li key={it.key} className="flex items-center gap-2">
              <span
                className={`flex size-4 shrink-0 items-center justify-center rounded-full border ${
                  it.fait ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-muted-foreground/40'
                }`}
              >
                {it.fait && <Check className="size-3" aria-hidden="true" />}
              </span>
              <button
                type="button"
                disabled={!it.lien}
                onClick={() => it.lien && navigate(it.lien)}
                className={`flex-1 text-left text-[13px] ${
                  it.fait ? 'text-muted-foreground line-through' : ''
                } ${it.lien ? 'hover:text-primary' : ''}`}
              >
                {it.libelle}
              </button>
              {it.lien && !it.fait && (
                <ChevronRight
                  className="size-3.5 text-muted-foreground" aria-hidden="true" />
              )}
              {!it.fait && (
                <button
                  type="button"
                  onClick={() => ignoreItem(it.id)}
                  aria-label={`Ignorer « ${it.libelle} »`}
                  className="text-muted-foreground/60 hover:text-foreground"
                >
                  <X className="size-3.5" aria-hidden="true" />
                </button>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
