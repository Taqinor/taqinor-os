import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ChevronDown, AlertTriangle } from 'lucide-react'
import { Badge, Button, Card } from '../../ui'
import stockApi from '../../api/stockApi'

/* ============================================================================
   CCAT9/CCAT14/CCAT16 — Encadré « Prêt pour les devis » en tête du catalogue Stock,
   un onglet par segment. Contrats partagés : `pret_devis_ci.json`,
   `pret_devis_agricole.json` et `pret_devis_residentiel.json` (même forme ; lus par les tests, jamais recopiés).
   Une AIDE, pas un verrou : un segment en erreur est masqué, tous en erreur =
   rien à l'écran. Aucun prix ici.
   ========================================================================== */

// Segments : une ligne par segment.
const SEGMENTS = [
  { cle: 'ci', label: 'Commercial & industriel', charger: () => stockApi.getPretDevisCi() },
  { cle: 'agricole', label: 'Agricole', charger: () => stockApi.getPretDevisAgricole() },
  { cle: 'residentiel', label: 'Résidentiel', charger: () => stockApi.getPretDevisResidentiel() },
]

const GROUPES = [
  ['materiel', 'Matériel'],
  ['onduleur', 'Onduleurs'],
  ['cable', 'Câbles'],
  ['protection', 'Protections'],
  ['prestation', 'Prestations'],
  ['forfait', 'Forfaits'],
  ['option', 'Options'],
  ['option_batterie', 'Option avec batterie'],
  ['accessoire', 'Accessoires'],
]
const STATUTS = {
  ok: ['success', 'OK'],
  a_completer: ['warning', 'À compléter'],
  absent: ['danger', 'Absent du catalogue'],
}

/** Le lien de l'action, avec les articles en cause (`&articles=12,34`) : le
 * filtre Stock les montre même quand sa règle locale ne connaît pas le motif. */
function lienAction(poste) {
  const ids = (poste.articles ?? []).map((a) => a.id)
  if (!ids.length || !poste.action.lien.includes('a_completer')) return poste.action.lien
  const sep = poste.action.lien.includes('?') ? '&' : '?'
  return `${poste.action.lien}${sep}articles=${ids.join(',')}`
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
          {!poste.obligatoire && <Badge tone="outline">facultatif</Badge>}
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
          <Link to={lienAction(poste)}>{poste.action.texte}</Link>
        </Button>
      )}
    </li>
  )
}

// Un groupe inconnu de l'écran reste affiché (jamais un poste masqué).
const autresGroupes = (postes) => [...new Set(postes.map((p) => p.groupe))]
  .filter((g) => !GROUPES.some(([cle]) => cle === g)).map((g) => [g, 'Autres'])

const aTraiter = (p) => p.obligatoire && p.statut !== 'ok'
const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`

function PanneauSegment({ data }) {
  const [toutVoir, setToutVoir] = useState(false)
  // Les postes `ok` facultatifs sont repliés derrière « Voir tout ».
  const postes = data.postes.filter((p) => toutVoir || p.statut !== 'ok' || p.obligatoire)
  const nbCaches = data.postes.length - postes.length
  return (
    <div className="flex flex-col gap-3">
      {[...GROUPES, ...autresGroupes(postes)].map(([groupe, label]) => {
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
  )
}

export default function PretDevisCi() {
  const [donnees, setDonnees] = useState({}) // cle -> réponse ; absent = pas (encore) chargé
  const [ouvert, setOuvert] = useState(null) // null = défaut selon `pret`
  const [onglet, setOnglet] = useState(null) // null = premier segment non prêt

  useEffect(() => {
    let actif = true
    SEGMENTS.forEach(({ cle, charger }) => {
      ;(async () => {
        try {
          const res = await charger()
          if (actif && res?.data && Array.isArray(res.data.postes)) {
            setDonnees((d) => ({ ...d, [cle]: res.data }))
          }
        } catch (e) {
          // aide, pas un verrou : segment masqué
          console.warn(`Segment « ${cle} » du tableau « Prêt pour les devis » indisponible`, e)
        }
      })()
    })
    return () => { actif = false }
  }, [])

  const charges = SEGMENTS.filter((s) => donnees[s.cle])
  if (charges.length === 0) return null
  const tousPrets = charges.every((s) => donnees[s.cle].pret)
  const total = charges.reduce((t, s) => t + (donnees[s.cle].nb_obligatoires_manquants ?? 0), 0)
  const estOuvert = ouvert ?? !tousPrets
  const actif = charges.find((s) => s.cle === onglet)
    ?? charges.find((s) => !donnees[s.cle].pret) ?? charges[0]
  const titre = tousPrets
    ? 'Prêt pour les devis'
    : `Prêt pour les devis : ${pluriel(total, 'élément')} obligatoire${total > 1 ? 's' : ''} à compléter`

  return (
    <Card data-testid="pret-devis-ci" className="mb-4">
      <button type="button" aria-expanded={estOuvert}
              onClick={() => setOuvert(!estOuvert)}
              className="flex w-full items-center justify-between gap-2 p-3 text-left sm:p-4">
        <span className="flex min-w-0 items-center gap-2 text-sm font-semibold">
          {tousPrets
            ? <CheckCircle2 className="size-4 shrink-0 text-success-text" aria-hidden="true" />
            : <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden="true" />}
          <span className={tousPrets ? 'text-success-text' : 'text-foreground'}>{titre}</span>
        </span>
        <ChevronDown aria-hidden="true"
                     className={`size-4 shrink-0 text-muted-foreground transition-transform ${estOuvert ? 'rotate-180' : ''}`} />
      </button>
      {estOuvert && (
        <div className="flex flex-col gap-1 border-t border-border px-3 pb-3 sm:px-4">
          <div role="tablist" aria-label="Segments de devis" className="flex flex-wrap gap-2 pt-3">
            {charges.map((s) => {
              const d = donnees[s.cle]
              const choisi = s.cle === actif.cle
              return (
                <Button key={s.cle} type="button" role="tab" size="sm"
                        variant={choisi ? 'secondary' : 'outline'}
                        aria-selected={choisi} data-testid={`onglet-pret-${s.cle}`}
                        onClick={() => setOnglet(s.cle)}>
                  {s.label} — {d.pret ? 'prêt' : `${d.nb_obligatoires_manquants} à compléter`}
                </Button>
              )
            })}
          </div>
          <PanneauSegment key={actif.cle} data={donnees[actif.cle]} />
        </div>
      )}
    </Card>
  )
}
