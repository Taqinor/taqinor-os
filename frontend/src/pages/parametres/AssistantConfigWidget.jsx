// PACT145 — Assistant de paramétrage (« Où régler… ? ») — NTAI35.
//
// `POST /ai/assistant-config/` répond EN FRANÇAIS avec des LIENS PROFONDS vers
// les écrans de paramètres concernés, et ne modifie JAMAIS rien (contrat
// serveur : `modifie: false`, aucun verbe d'écriture exposé). L'endpoint
// existait sans aucun appelant frontend.
//
// CAS PARTICULIER UTILE — la dégradation n'est PAS une panne : sans clé LLM
// configurée, le serveur répond depuis une FAQ statique (`source: 'faq'`) et
// renvoie quand même les liens. Cet écran ne désactive donc RIEN : il affiche
// simplement une réponse plus sommaire, et le lien reste cliquable dans les
// deux cas. Les liens viennent tous d'un index serveur vérifié contre les
// routes réelles — aucune URL inventée.
//
// Les écrans que le rôle de l'appelant ne peut pas ouvrir ne lui sont jamais
// proposés (filtrage serveur).
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { HelpCircle, Search, ArrowRight } from 'lucide-react'
import api from '../../api/axios'
import { Card, CardContent, Input, Button, Badge, Spinner } from '../../ui'

export default function AssistantConfigWidget() {
  const [question, setQuestion] = useState('')
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [busy, setBusy] = useState(false)

  const demander = async () => {
    const q = question.trim()
    if (!q) return
    setBusy(true)
    setErreur('')
    try {
      const res = await api.post('/ai/assistant-config/', { question: q })
      setResultat(res.data ?? null)
    } catch (e) {
      setResultat(null)
      setErreur(e?.response?.data?.detail
        ?? "L'assistant de paramétrage est momentanément indisponible.")
    } finally { setBusy(false) }
  }

  const ecrans = Array.isArray(resultat?.ecrans) ? resultat.ecrans : []

  return (
    <Card className="mb-4" data-testid="assistant-config">
      <CardContent className="pt-4 sm:pt-5">
        <div className="mb-2 flex items-center gap-2">
          <HelpCircle className="size-4 shrink-0 text-primary" aria-hidden="true" />
          <span className="text-sm font-semibold tracking-tight text-foreground">
            Où régler… ?
          </span>
        </div>
        <p className="mb-2.5 text-[11.5px] text-muted-foreground">
          Décrivez le réglage cherché : l'assistant vous répond et vous donne le
          lien direct vers le bon écran. Il ne modifie jamais aucun paramètre.
        </p>

        <div className="flex flex-wrap gap-1.5">
          <Input
            className="min-w-[220px] flex-1"
            value={question}
            aria-label="Où régler… ?"
            placeholder="Ex. où régler la TVA par défaut ?"
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              // Entrée = poser la question, sans jamais soumettre un
              // formulaire parent (la page Paramètres est un seul <form>).
              if (e.key === 'Enter') { e.preventDefault(); demander() }
            }}
          />
          <Button type="button" onClick={demander} disabled={busy}>
            {busy
              ? <Spinner className="size-4" aria-hidden="true" />
              : <Search className="size-4" aria-hidden="true" />}
            Demander
          </Button>
        </div>

        {erreur && <p className="mt-2 text-xs text-destructive">{erreur}</p>}

        {resultat && (
          <div className="mt-3" data-testid="assistant-config-reponse">
            <p className="text-sm text-foreground">{resultat.reponse}</p>
            {resultat.source === 'faq' && (
              <Badge tone="neutral" className="mt-1.5">Réponse de référence</Badge>
            )}
            {ecrans.length > 0 && (
              <div className="mt-2 flex flex-col gap-1.5">
                {ecrans.map((ecran) => (
                  <Link key={ecran.lien} to={ecran.lien}
                    data-testid="assistant-config-lien"
                    className="flex items-center gap-2 rounded-lg border border-border p-2.5 text-sm hover:bg-accent">
                    <ArrowRight className="size-4 shrink-0 text-primary" aria-hidden="true" />
                    <span className="font-medium">{ecran.titre}</span>
                    <span className="ml-auto text-[11px] text-muted-foreground">
                      {ecran.lien}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
