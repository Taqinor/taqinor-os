import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ChevronDown, AlertTriangle } from 'lucide-react'
import { Badge, Button, Card } from '../../ui'
import stockApi from '../../api/stockApi'

/* ============================================================================
   CCAT9 — Encadré « Prêt pour le devis C&I » en tête du catalogue Stock.
   Contrat partagé : `pret_devis_ci.json` (lu par les tests, jamais recopié).
   Une AIDE, pas un verrou : en cas d'erreur on ne rend rien. Aucun prix ici.
   ========================================================================== */

const GROUPES = [
  ['materiel', 'Matériel'],
  ['prestation', 'Prestations (Paramètres)'],
  ['option', 'Options'],
  ['option_batterie', 'Option avec batterie'],
]
const STATUTS = {
  ok: ['success', 'OK'],
  a_completer: ['warning', 'À compléter'],
  absent: ['danger', 'Absent du catalogue'],
}

function LignePoste({ poste }) {
  const [tone, texte] = STATUTS[poste.statut] ?? ['neutral', poste.statut]
  return (
    <li data-testid={`poste-ci-${poste.cle}`}
        className="flex flex-col gap-1 py-2 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-foreground">{poste.libelle}</span>
          <Badge tone={tone}>{texte}</Badge>
          {!poste.obligatoire && <Badge tone="outline">recommandé</Badge>}
        </div>
        {(poste.articles ?? []).length > 0 && (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {poste.articles.map((a) => (
              <li key={a.id}>{a.nom} — {a.motif}</li>
            ))}
          </ul>
        )}
      </div>
      {poste.statut !== 'ok' && poste.action?.lien && (
        <Button asChild variant="outline" size="sm" className="shrink-0 self-start">
          <Link to={poste.action.lien}>{poste.action.texte}</Link>
        </Button>
      )}
    </li>
  )
}

const aTraiter = (p) => p.obligatoire && p.statut !== 'ok'

export default function PretDevisCi() {
  const [data, setData] = useState(null)
  const [ouvert, setOuvert] = useState(null) // null = défaut selon `pret`
  const [toutVoir, setToutVoir] = useState(false)

  useEffect(() => {
    let actif = true
    ;(async () => {
      try {
        const res = await stockApi.getPretDevisCi()
        if (actif && res?.data && Array.isArray(res.data.postes)) setData(res.data)
      } catch {
        /* aide, pas un verrou : silence */
      }
    })()
    return () => { actif = false }
  }, [])

  if (!data) return null
  const { pret, nb_obligatoires_manquants: n } = data
  const estOuvert = ouvert ?? !pret
  // Les postes `ok` facultatifs sont repliés derrière « Voir tout ».
  const postes = data.postes.filter((p) => toutVoir || p.statut !== 'ok' || p.obligatoire)
  const nbCaches = data.postes.length - postes.length
  const titre = pret
    ? 'Prêt pour le devis C&I'
    : `Devis commerciaux et industriels : ${n} élément${n > 1 ? 's' : ''} obligatoire${n > 1 ? 's' : ''} à compléter`

  return (
    <Card data-testid="pret-devis-ci" className="mb-4">
      <button type="button" aria-expanded={estOuvert}
              onClick={() => setOuvert(!estOuvert)}
              className="flex w-full items-center justify-between gap-2 p-3 text-left sm:p-4">
        <span className="flex min-w-0 items-center gap-2 text-sm font-semibold">
          {pret
            ? <CheckCircle2 className="size-4 shrink-0 text-success-text" aria-hidden="true" />
            : <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden="true" />}
          <span className={pret ? 'text-success-text' : 'text-foreground'}>{titre}</span>
        </span>
        <ChevronDown aria-hidden="true"
                     className={`size-4 shrink-0 text-muted-foreground transition-transform ${estOuvert ? 'rotate-180' : ''}`} />
      </button>
      {estOuvert && (
        <div className="flex flex-col gap-3 border-t border-border px-3 pb-3 sm:px-4">
          {GROUPES.map(([groupe, label]) => {
            const lignes = postes
              .filter((p) => p.groupe === groupe)
              .sort((a, b) => Number(aTraiter(b)) - Number(aTraiter(a)))
            if (lignes.length === 0) return null
            return (
              <section key={groupe} aria-label={label}>
                <h4 className="pt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</h4>
                <ul className="divide-y divide-border">
                  {lignes.map((p) => <LignePoste key={p.cle} poste={p} />)}
                </ul>
              </section>
            )
          })}
          {(nbCaches > 0 || toutVoir) && (
            <Button type="button" variant="ghost" size="sm" className="self-start"
                    onClick={() => setToutVoir((v) => !v)}>
              {toutVoir ? 'Masquer les postes OK facultatifs' : 'Voir tout'}
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
