import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle, Check } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import {
  Badge, Button, Card, Spinner,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../ui'

/* ============================================================================
   CAL42 — COMPARER LES VARIANTES d'un calepinage (CAL105 fondue ici).
   ----------------------------------------------------------------------------
   Le serveur sert déjà la comparaison (CAL21) mais RIEN ne l'affiche ; l'AO a
   son propre comparateur, hors du module neutre. Cet écran est celui du module.

   TOUT VIENT DU CONTRAT `variantes_comparer.json` (CAL3, PACT10) — et RIEN
   n'est recalculé ici :
     * LES ÉCARTS SONT SERVEUR. `ecart_modules`, `ecart_kwc`, `ecart_p50_kwh`
       sont lus tels quels. Un écart recalculé à l'écran est une SECONDE source
       de vérité : elle finit par diverger du serveur et personne ne sait
       laquelle croire. La variante retenue porte `0` (un écart MESURÉ, nul par
       construction) ; un calepinage à UNE SEULE variante porte `null` partout —
       il n'y a rien à quoi se comparer, ce n'est pas un écart nul.
     * UNE VARIANTE NON SIMULÉE EST DITE NON SIMULÉE. `simulee: false` ⇒ toutes
       ses grandeurs de production valent `null`, et l'écran écrit « non
       simulée » — jamais `0`, qui se lirait « zéro kWh » là où personne n'a
       lancé de simulation. Même discipline pour les marges (`null` = rien de ce
       type n'a été mesuré, pas « au ras »).
     * AUCUNE CLÉ INVENTÉE. Ce que le contrat ne publie pas n'est pas affiché :
       le comparatif n'a ni vignette de plan, ni indice d'accès solaire propre —
       la seule grandeur d'ombrage publiée est le poste de perte `shading` des
       `pertes_dominantes`, avec SA SOURCE, et c'est donc elle qui est montrée.

   « RETENIR » appelle le serveur (CAL21) puis RECHARGE : l'ancienne retenue
   redevient non retenue parce que le serveur le dit, jamais parce que l'écran
   a basculé un drapeau local.
   ========================================================================== */

const errMsg = (e, repli) => e?.response?.data?.detail || repli

/** Une grandeur non mesurée s'écrit « — », jamais `0`. */
const ou = (valeur, rendu) => (valeur === null || valeur === undefined ? '—' : rendu(valeur))

const nombre = (v, decimales = 0) => ou(v, (x) => Number(x).toLocaleString('fr-FR', {
  minimumFractionDigits: decimales, maximumFractionDigits: decimales,
}))

/** Un écart signé — `0` est une vraie valeur (la retenue), `null` ne l'est pas. */
const ecart = (v, decimales = 0) => ou(v, (x) => {
  const n = Number(x)
  const texte = Math.abs(n).toLocaleString('fr-FR', {
    minimumFractionDigits: decimales, maximumFractionDigits: decimales,
  })
  if (n === 0) return '0'
  return `${n > 0 ? '+' : '−'}${texte}`
})

const pourcentage = (v) => ou(v, (x) => `${(Number(x) * 100).toFixed(1).replace('.', ',')} %`)

function orientationTexte(o) {
  if (!o) return '—'
  const morceaux = [
    o.orientation_module,
    o.axe_rangee ? `rangées ${String(o.axe_rangee).replace('_', '-').toLowerCase()}` : null,
    o.azimut_deg != null ? `azimut ${nombre(o.azimut_deg)}°` : null,
    o.inclinaison_deg != null ? `inclinaison ${nombre(o.inclinaison_deg)}°` : null,
  ].filter(Boolean)
  return morceaux.length ? morceaux.join(' · ') : '—'
}

function margesTexte(ligne) {
  const m = ligne?.marges
  if (!m) return '—'
  const morceaux = [
    m.troncon_min_cm != null ? `tronçon ${nombre(m.troncon_min_cm, 1)} cm` : null,
    m.bande_min_cm != null ? `bande ${nombre(m.bande_min_cm, 1)} cm` : null,
    m.rangee_critique || null,
    m.obstacle_critique || null,
  ].filter(Boolean)
  return morceaux.length ? morceaux.join(' · ') : '—'
}

/* Le seul indicateur d'ombrage que le contrat publie : le poste `shading` des
   `pertes_dominantes`. NON exporté (`react-refresh/only-export-components` :
   un fichier de composant n'exporte que des composants) — il est vérifié à
   travers l'écran, où son résultat est de toute façon le seul qui compte. */
function ombragePublie(ligne) {
  const postes = ligne?.production?.pertes_dominantes
  if (!Array.isArray(postes)) return null
  return postes.find((p) => p?.poste === 'shading') || null
}

const LIGNES_TABLEAU = [
  { id: 'role', libelle: 'Rôle', rendu: (l) => l.role || '—' },
  { id: 'statut', libelle: 'Statut', rendu: (l) => l.statut || '—' },
  {
    id: 'modules',
    libelle: 'Modules',
    rendu: (l) => (l.total_optimal != null && l.total_optimal !== l.total_modules
      ? `${nombre(l.total_modules)} (optimal : ${nombre(l.total_optimal)})`
      : nombre(l.total_modules)),
  },
  { id: 'kwc', libelle: 'Puissance (kWc)', rendu: (l) => nombre(l.kwc, 2) },
  { id: 'orientation', libelle: 'Orientation', rendu: (l) => orientationTexte(l.orientation) },
  { id: 'marges', libelle: 'Marges', rendu: margesTexte },
  { id: 'methode', libelle: 'Méthode', rendu: (l) => l.methode || '—' },
  {
    id: 'ecart_modules',
    libelle: 'Écart modules / retenue',
    rendu: (l) => ecart(l.ecart_modules),
  },
  {
    id: 'ecart_kwc',
    libelle: 'Écart kWc / retenue',
    rendu: (l) => ecart(l.ecart_kwc, 2),
  },
]

function EtiquetteVariante({ ligne }) {
  return (
    <div className="space-y-1">
      <div className="font-medium">{ligne.nom}</div>
      {ligne.est_retenue ? <Badge>Retenue</Badge> : null}
      {!ligne.simulee ? <Badge variant="outline">Non simulée</Badge> : null}
    </div>
  )
}

/* ── La vue CÔTE À CÔTE de deux variantes ─────────────────────────────────── */
function CoteACote({ lignes }) {
  /* `null` = « pas encore choisi par l'utilisateur » : la sélection par défaut
     est DÉRIVÉE des données au rendu, jamais posée par un effet (un setState
     dans un effet provoque un rendu en cascade — et ici il n'apporte rien). */
  const [gaucheChoisie, setGauche] = useState(null)
  const [droiteChoisie, setDroite] = useState(null)

  const parDefaut = useMemo(() => {
    if (!lignes.length) return { gauche: '', droite: '' }
    const retenue = lignes.find((l) => l.est_retenue) ?? lignes[0]
    const autre = lignes.find((l) => l.id !== retenue.id) ?? retenue
    return { gauche: String(retenue.id), droite: String(autre.id) }
  }, [lignes])

  const gauche = gaucheChoisie ?? parDefaut.gauche
  const droite = droiteChoisie ?? parDefaut.droite

  const paire = [gauche, droite].map(
    (id) => lignes.find((l) => String(l.id) === String(id)) || null)

  if (lignes.length < 2) {
    return (
      <Card className="p-4 text-sm text-muted-foreground" data-testid="cal-cote-a-cote-vide">
        Ce calepinage ne porte qu’une variante : il n’y a rien à comparer côte à côte.
      </Card>
    )
  }

  return (
    <Card className="space-y-3 p-4" data-testid="cal-cote-a-cote">
      <h2 className="text-sm font-semibold">Côte à côte</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {[[gauche, setGauche, 'Variante de gauche'], [droite, setDroite, 'Variante de droite']]
          .map(([valeur, poser, libelle]) => (
            <Select key={libelle} value={valeur ?? ''} onValueChange={poser}>
              <SelectTrigger aria-label={libelle}><SelectValue placeholder={libelle} /></SelectTrigger>
              <SelectContent>
                {lignes.map((l) => (
                  <SelectItem key={l.id} value={String(l.id)}>{l.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {paire.map((ligne, i) => (
          <div key={i} className="space-y-1 rounded-md border border-border p-3 text-sm">
            {ligne ? (
              <>
                <EtiquetteVariante ligne={ligne} />
                <Ligne libelle="Plan" valeur={`${orientationTexte(ligne.orientation)} — ${ligne.methode || '—'}`} />
                <Ligne libelle="Modules" valeur={nombre(ligne.total_modules)} />
                <Ligne libelle="Puissance (kWc)" valeur={nombre(ligne.kwc, 2)} />
                <Ligne
                  libelle="Ombrage (poste de perte)"
                  valeur={ligne.simulee
                    ? ou(ombragePublie(ligne), (p) => `${nombre(p.pct, 1)} % — ${p.source}`)
                    : 'non simulée'}
                />
                <Ligne
                  libelle="Production P50 (kWh)"
                  valeur={ligne.simulee ? nombre(ligne.production?.p50_kwh) : 'non simulée'}
                />
                <Ligne libelle="Écart modules / retenue" valeur={ecart(ligne.ecart_modules)} />
                <Ligne libelle="Écart kWc / retenue" valeur={ecart(ligne.ecart_kwc, 2)} />
                <Ligne
                  libelle="Écart P50 / retenue"
                  valeur={ligne.simulee ? ecart(ligne.ecart_p50_kwh) : 'non simulée'}
                />
              </>
            ) : <span className="text-muted-foreground">Choisissez une variante.</span>}
          </div>
        ))}
      </div>
    </Card>
  )
}

function Ligne({ libelle, valeur }) {
  return (
    <div className="flex gap-2">
      <span className="w-44 shrink-0 text-muted-foreground">{libelle}</span>
      <span>{valeur}</span>
    </div>
  )
}

export default function VariantesCompare() {
  const { id } = useParams()
  const [erreurAction, setErreurAction] = useState(null)
  const [enCours, setEnCours] = useState(null)

  const { data, loading, error, refetch } = useResource(
    (p) => calepinageApi.calepinages.comparer(p.id),
    { id },
    {
      initialData: null,
      select: (res) => res?.data ?? null,
      errorMessage: (e) => errMsg(e, 'Impossible de charger le comparatif des variantes.'),
    },
  )

  const lignes = useMemo(() => (Array.isArray(data?.lignes) ? data.lignes : []), [data])

  const retenir = async (ligne) => {
    setErreurAction(null)
    setEnCours(ligne.id)
    try {
      await calepinageApi.calepinages.retenirVariante(id, ligne.id)
      // On RECHARGE : c'est le serveur qui dé-retient la précédente.
      await refetch()
    } catch (e) {
      setErreurAction(errMsg(e, 'Impossible de retenir cette variante.'))
    } finally {
      setEnCours(null)
    }
  }

  if (loading && !data) return <div className="flex justify-center py-10"><Spinner /></div>
  if (error) return <Card className="p-4 text-sm text-destructive" role="alert">{error}</Card>

  if (!lignes.length) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Aucune variante à comparer pour ce calepinage.
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Comparer les variantes</h1>

      {erreurAction ? (
        <Card className="border-destructive/50 bg-destructive/5 p-3" role="alert">
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{erreurAction}</span>
          </div>
        </Card>
      ) : null}

      {Array.isArray(data?.introuvables) && data.introuvables.length > 0 ? (
        <Card className="p-3 text-sm text-muted-foreground" data-testid="cal-introuvables">
          {`Variantes demandées mais introuvables : ${data.introuvables.join(', ')}`}
        </Card>
      ) : null}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm" data-testid="cal-tableau-variantes">
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="p-3 text-left font-medium">Variante</th>
              {lignes.map((ligne) => (
                <th key={ligne.id} scope="col" className="p-3 text-left align-top">
                  <EtiquetteVariante ligne={ligne} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {LIGNES_TABLEAU.map((rangee) => (
              <tr key={rangee.id} className="border-b border-border/60">
                <th scope="row" className="p-3 text-left font-normal text-muted-foreground">
                  {rangee.libelle}
                </th>
                {lignes.map((ligne) => (
                  <td key={ligne.id} className="p-3" data-testid={`cal-${rangee.id}-${ligne.id}`}>
                    {rangee.rendu(ligne)}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-b border-border/60">
              <th scope="row" className="p-3 text-left font-normal text-muted-foreground">
                Production P50 (kWh)
              </th>
              {lignes.map((ligne) => (
                <td key={ligne.id} className="p-3" data-testid={`cal-p50-${ligne.id}`}>
                  {ligne.simulee ? nombre(ligne.production?.p50_kwh) : 'non simulée'}
                </td>
              ))}
            </tr>
            <tr className="border-b border-border/60">
              <th scope="row" className="p-3 text-left font-normal text-muted-foreground">
                Performance ratio
              </th>
              {lignes.map((ligne) => (
                <td key={ligne.id} className="p-3" data-testid={`cal-pr-${ligne.id}`}>
                  {ligne.simulee ? pourcentage(ligne.production?.performance_ratio) : 'non simulée'}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="p-3 text-left font-normal text-muted-foreground">
                Décision
              </th>
              {lignes.map((ligne) => (
                <td key={ligne.id} className="p-3">
                  {ligne.est_retenue ? (
                    <span
                      className="inline-flex items-center gap-1 text-sm text-muted-foreground"
                      data-testid={`cal-retenue-${ligne.id}`}
                    >
                      <Check size={15} aria-hidden="true" />
                      Retenue
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={enCours != null}
                      onClick={() => retenir(ligne)}
                    >
                      Retenir
                    </Button>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </Card>

      <CoteACote lignes={lignes} />
    </div>
  )
}
