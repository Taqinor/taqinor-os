import { useCallback, useEffect, useMemo, useState } from 'react'
import { LayoutGrid, AlertTriangle } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Card, Checkbox, EmptyState, Skeleton, toast } from '../../../ui'
import VarianteColonne from './VarianteColonne'

/* ============================================================================
   AOF102 — Comparateur de variantes côte à côte (2 à 4 colonnes).
   ----------------------------------------------------------------------------
   Le différenciateur revendiqué est « technique + commercial + CONFORMITÉ AO
   dans UN écran » : la bande conformité de chaque colonne (`VarianteColonne`)
   est donc structurelle, pas optionnelle.

   ── RÈGLE ÉCONOMIE (en-tête du Groupe AOF : « l'économie est réservée au
   directeur ») ─────────────────────────────────────────────────────────────
   Sans la permission `ao_rentabilite_voir`, aucune donnée de marge n'est ni
   affichée NI PRÉSENTE DANS LE PAYLOAD. Deux verrous, dans cet ordre :
     1. la REQUÊTE ne demande jamais l'économie (`avec_economie` n'est envoyé
        que si la permission est portée) — le serveur n'a donc rien à filtrer ;
     2. la RÉPONSE est quand même passée par `retirerEconomie()` avant d'être
        remise au rendu — un serveur trop bavard (ou un cache tiède) ne peut
        pas faire entrer un chiffre de marge dans l'arbre React. Le test monte
        exactement ce cas hostile.
   `CLES_ECONOMIE` est une liste EXACTE de noms de champs, jamais un motif
   `marge*` : « marge de robustesse » et « marge d'engagement » sont des
   grandeurs TECHNIQUES qui doivent rester visibles de tous — les filtrer
   viderait la bande conformité, exactement le contraire du but.

   ── UNE SEULE VARIANTE RETENUE ────────────────────────────────────────────
   La variante retenue alimente le bordereau et les planches, et elle seule.
   Le front ne se fie pas au payload pour l'unicité : `retenueId` est UN
   identifiant unique dérivé de la liste (première variante marquée) — même un
   payload contenant deux `retenue: true` ne rend QU'UN marqueur. Le serveur
   reste l'autorité (PATCH `{ retenue: true }` → refetch).

   ── MINIATURE DU PLAN ─────────────────────────────────────────────────────
   La conversion SVG → PNG est la brique partagée AOF75
   (`features/ao/studio/svgToPng.js`), propriété de la lane `frontend/ao-studio`
   et NON livrée par cette lane. Elle est donc INJECTÉE (`exporterImage`) au
   lieu d'être importée : un import statique vers un fichier non encore livré
   casserait le build de toute l'app. Sans exporteur, la colonne affiche une
   miniature indisponible NOMMÉE (jamais une image cassée).
   ========================================================================== */

// Champs d'ÉCONOMIE (interne/directeur). Liste EXACTE — voir l'en-tête.
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que DevisTab.DEVIS_MINI_TRACK
export const CLES_ECONOMIE = [
  'economie',
  'prix_vente_ht',
  'prix_vente_ttc',
  'prix_achat',
  'cout_total',
  'cout_unitaire',
  'marge_mad',
  'marge_pct',
  'marge_brute',
  'benefice',
  'rentabilite',
]

const MIN_COLONNES = 2
const MAX_COLONNES = 4

// Retrait RÉCURSIF des champs d'économie (objets + tableaux). Retourne une
// nouvelle structure : jamais de mutation du payload d'origine.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function retirerEconomie(valeur) {
  if (Array.isArray(valeur)) return valeur.map(retirerEconomie)
  if (valeur && typeof valeur === 'object') {
    const out = {}
    for (const [cle, v] of Object.entries(valeur)) {
      if (CLES_ECONOMIE.includes(cle)) continue
      out[cle] = retirerEconomie(v)
    }
    return out
  }
  return valeur
}

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

export function VariantesCompare({ affaireId, exporterImage = null }) {
  const peutVoirEconomie = useHasPermission('ao_rentabilite_voir')
  const [selection, setSelection] = useState([])
  const [miniatures, setMiniatures] = useState({})
  const [enCours, setEnCours] = useState(false)

  // La requête elle-même ne demande l'économie que si la permission est portée.
  const params = useMemo(
    () => (peutVoirEconomie
      ? { affaire: affaireId, avec_economie: 1 }
      : { affaire: affaireId }),
    [affaireId, peutVoirEconomie],
  )

  const { data: brut, loading, error, refetch } = useResource(
    () => aoApi.variantes.list(params), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les variantes.' },
  )

  // 2ᵉ verrou : le payload remis au rendu est NETTOYÉ quand la permission
  // manque — un serveur bavard ne peut pas faire entrer une marge dans l'UI.
  const variantes = useMemo(
    () => (peutVoirEconomie ? brut : retirerEconomie(brut)),
    [brut, peutVoirEconomie],
  )

  // Sélection par défaut : les 4 premières (bornée à MAX_COLONNES).
  useEffect(() => {
    setSelection((prev) => {
      const connus = new Set(variantes.map((v) => v.id))
      const gardees = prev.filter((id) => connus.has(id))
      if (gardees.length) return gardees
      return variantes.slice(0, MAX_COLONNES).map((v) => v.id)
    })
  }, [variantes])

  const colonnes = useMemo(
    () => variantes.filter((v) => selection.includes(v.id)).slice(0, MAX_COLONNES),
    [variantes, selection],
  )

  // Unicité de la variante retenue, garantie côté rendu (voir en-tête).
  const retenueId = useMemo(() => variantes.find((v) => v.retenue)?.id ?? null, [variantes])

  // Miniatures — via l'exporteur INJECTÉ (AOF75), jamais un import statique.
  useEffect(() => {
    if (typeof exporterImage !== 'function') return undefined
    let annule = false
    const cibles = colonnes.filter((v) => v.miniature_svg)
    if (!cibles.length) return undefined
    Promise.all(cibles.map(async (v) => {
      try {
        return [v.id, await exporterImage(v.miniature_svg, { largeur: 320 })]
      } catch {
        return [v.id, null]
      }
    })).then((paires) => {
      if (annule) return
      setMiniatures(Object.fromEntries(paires.filter(([, src]) => src)))
    })
    return () => { annule = true }
  }, [colonnes, exporterImage])

  const basculerSelection = useCallback((id) => {
    setSelection((prev) => (prev.includes(id)
      ? prev.filter((x) => x !== id)
      : prev.length >= MAX_COLONNES ? prev : [...prev, id]))
  }, [])

  const dupliquer = useCallback(async (variante) => {
    setEnCours(true)
    try {
      await aoApi.variantes.create({ dupliquer_de: variante.id, affaire: affaireId })
      toast.success(`« ${variante.nom} » dupliquée.`)
      await refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Duplication impossible.'))
    } finally {
      setEnCours(false)
    }
  }, [affaireId, refetch])

  const definirRetenue = useCallback(async (variante) => {
    setEnCours(true)
    try {
      await aoApi.variantes.update(variante.id, { retenue: true })
      toast.success(`« ${variante.nom} » retenue — alimente le bordereau et les planches.`)
      await refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Impossible de définir la variante retenue.'))
    } finally {
      setEnCours(false)
    }
  }, [refetch])

  const epingler = useCallback(async (variante) => {
    setEnCours(true)
    try {
      await aoApi.variantes.update(variante.id, { epinglee: !variante.epinglee })
      await refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Épinglage impossible.'))
    } finally {
      setEnCours(false)
    }
  }, [refetch])

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 3 }).map((unused, i) => (
          <Card key={i} className="p-4"><Skeleton className="h-5 w-2/3" /><Skeleton className="mt-3 h-32 w-full" /></Card>
        ))}
      </div>
    )
  }

  if (error) {
    return <EmptyState icon={AlertTriangle} title="Impossible de charger les variantes" description={error} />
  }

  if (variantes.length < MIN_COLONNES) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title="Pas assez de variantes à comparer"
        description={`Le comparateur exige au moins ${MIN_COLONNES} variantes calculées sur cette affaire.`}
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight">Comparer les variantes</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Technique, conformité AO et — pour le directeur seul — économie, dans un seul écran.
            {retenueId == null && ' Aucune variante retenue : le bordereau et les planches n’ont pas de source.'}
          </p>
        </div>
        <fieldset className="flex flex-wrap items-center gap-3 rounded-md border border-border p-2">
          <legend className="px-1 text-xs text-muted-foreground">
            {`Variantes comparées (${MIN_COLONNES} à ${MAX_COLONNES})`}
          </legend>
          {variantes.map((v) => {
            const coche = selection.includes(v.id)
            return (
              <label key={v.id} className="flex items-center gap-1.5 text-sm">
                <Checkbox
                  checked={coche}
                  disabled={!coche && selection.length >= MAX_COLONNES}
                  onCheckedChange={() => basculerSelection(v.id)}
                  aria-label={`Comparer ${v.nom}`}
                />
                {v.nom}
              </label>
            )
          })}
        </fieldset>
      </div>

      {colonnes.length < MIN_COLONNES ? (
        <EmptyState
          icon={LayoutGrid}
          title="Sélection insuffisante"
          description={`Choisissez au moins ${MIN_COLONNES} variantes à comparer (${MAX_COLONNES} au maximum).`}
        />
      ) : (
        <div
          className="grid gap-3 overflow-x-auto sm:grid-cols-2 xl:grid-cols-4"
          role="group"
          aria-label="Colonnes de comparaison"
        >
          {colonnes.map((v) => (
            <VarianteColonne
              key={v.id}
              variante={{ ...v, retenue: v.id === retenueId }}
              peutVoirEconomie={peutVoirEconomie}
              miniatureSrc={miniatures[v.id] ?? null}
              miniatureIndisponible={
                typeof exporterImage === 'function'
                  ? 'Aperçu du plan non généré'
                  : 'Aperçu indisponible sur cet écran'
              }
              onDupliquer={enCours ? undefined : dupliquer}
              onDefinirRetenue={enCours ? undefined : definirRetenue}
              onEpingler={enCours ? undefined : epingler}
            />
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Seule la variante retenue alimente le bordereau des prix et les planches du dossier.
      </p>
    </div>
  )
}

export default VariantesCompare
