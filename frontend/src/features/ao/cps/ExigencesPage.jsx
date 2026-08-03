import { useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileText, RefreshCcw, ShieldCheck } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import { unwrapList } from '../../../api/resource'
import useResource from '../../../hooks/useResource'
import useVisibilityAwarePolling from '../../../hooks/useVisibilityAwarePolling'
import { Button, Card, Checkbox, EmptyState, Input, Label, Skeleton, toast } from '../../../ui'
import PiecePreview from '../dossier/PiecePreview'
import ConformiteTable from './ConformiteTable'
import { motifBlocageDepot } from './ConformiteTable.utils'
import { TYPES_CLAUSE, estIntervalle, payloadClause } from './ExigencesPage.utils'

/* ============================================================================
   AOF181 — Écran « CPS & exigences » : l'analyse du cahier des charges.
   ----------------------------------------------------------------------------
   AOF13 introduit l'étape `analyse_cps` du cycle de vie et AOF14 fait des
   clauses une DONNÉE paramétrable. Sans écran, une étape entière du cycle n'a
   pas d'interface et les clauses se saisiraient par API — c'est-à-dire nulle
   part, pour l'équipe qui répond réellement à l'appel d'offres.

   **Le jeu de clauses FRDISI se saisit intégralement** : ratio DC/AC 0,75-1
   (intervalle), plafond 60 kWc par onduleur, caution provisoire en MONTANT
   ABSOLU (jamais un pourcentage déduit), validité des offres 75 jours. Chaque
   clause porte sa SOURCE (pièce du DCE + page) : une exigence sans source ne
   se défend pas devant la commission.

   **Les nombres tapés ne sont JAMAIS retouchés.** Les champs de valeur sont des
   champs texte à `inputMode="decimal"` et le formulaire est `noValidate` : « 0,75 »
   part au serveur tel quel, sans normalisation, sans arrondi, sans rejet — la
   règle du générateur de devis, appliquée ici pour la même raison.

   **Aucun chiffre de conformité n'est calculé côté front** (AOF94) : le tableau
   vivant (`ConformiteTable`) n'affiche que ce que la chaîne électrique (AOF99)
   et le contrôleur (AOF146) ont conclu, resondés par le hook PARTAGÉ
   `useVisibilityAwarePolling` (VX56 — jamais un `setInterval` maison, aucun
   sondage d'onglet masqué).

   **Une clause bloquante non satisfaite EMPÊCHE `pret_a_deposer`** : le bouton
   n'est jamais grisé sans explication — le motif est écrit DESSUS (même règle
   produit qu'AOF176). Le serveur reste la vraie porte ; l'écran la rend visible.

   L'aperçu du CPS à côté réutilise `PiecePreview` (AOF175) — même composant,
   même worker pdfjs partagé, aucun `<iframe>`/`<embed>`.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const POLL_MS = 30000

/* RÉPARATION 03/08/2026 — le type par défaut valait `plafond`, que le serveur
   REFUSE : il n'est pas dans `ExigenceCPS.TypeExigence` (cf. la liste réelle
   dans `ExigencesPage.utils.js`). Une clause soumise sans toucher au sélecteur
   partait donc systématiquement en erreur. Le défaut est désormais `autre`, le
   choix le plus neutre du modèle — il existe, il est même le `default` du champ
   côté Django, et il n'impose aucune sémantique à une clause qu'on n'a pas
   encore qualifiée. Sa valeur part en `valeur_texte` (type non chiffrable). */
const FORM_VIDE = {
  libelle: '',
  type: 'autre',
  valeur: '',
  valeurMax: '',
  unite: '',
  sourcePiece: '',
  sourcePage: '',
  bloquant: true,
}

function ClauseForm({ onCreer }) {
  const [form, setForm] = useState(FORM_VIDE)
  const [envoi, setEnvoi] = useState(false)

  const set = (champ) => (e) => setForm((f) => ({ ...f, [champ]: e.target.value }))

  const intervalle = estIntervalle(form.type)
  const complet = Boolean(form.libelle.trim() && form.sourcePiece.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!complet) return
    setEnvoi(true)
    try {
      await onCreer(form)
      toast.success('Clause enregistrée.')
      setForm(FORM_VIDE)
    } catch (e2) {
      toast.error(errMsg(e2, 'Clause non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1 sm:col-span-2">
          <Label htmlFor="ao-cps-libelle" required>Intitulé de la clause</Label>
          <Input
            id="ao-cps-libelle" value={form.libelle} onChange={set('libelle')}
            placeholder="Ex. Ratio DC/AC admissible"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-cps-type">Type</Label>
          <select
            id="ao-cps-type" value={form.type} onChange={set('type')}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          >
            {TYPES_CLAUSE.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-cps-unite">Unité</Label>
          <Input
            id="ao-cps-unite" value={form.unite} onChange={set('unite')}
            placeholder="Ex. kWc/onduleur, MAD, jours"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-cps-valeur">{intervalle ? 'Valeur minimale' : 'Valeur'}</Label>
          {/* Champ TEXTE : « 0,75 » ne doit être ni rejeté ni normalisé. */}
          <Input
            id="ao-cps-valeur" value={form.valeur} onChange={set('valeur')}
            inputMode="decimal" placeholder="Ex. 0,75"
          />
        </div>
        {intervalle && (
          <div className="flex flex-col gap-1">
            <Label htmlFor="ao-cps-valeur-max">Valeur maximale</Label>
            <Input
              id="ao-cps-valeur-max" value={form.valeurMax} onChange={set('valeurMax')}
              inputMode="decimal" placeholder="Ex. 1"
            />
          </div>
        )}
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-cps-source" required>Pièce du DCE</Label>
          <Input
            id="ao-cps-source" value={form.sourcePiece} onChange={set('sourcePiece')}
            placeholder="Ex. CPS — article 12"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-cps-page">Page</Label>
          <Input
            id="ao-cps-page" value={form.sourcePage} onChange={set('sourcePage')}
            inputMode="numeric" placeholder="Ex. 34"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox
          id="ao-cps-bloquant"
          checked={form.bloquant}
          onCheckedChange={(v) => setForm((f) => ({ ...f, bloquant: v === true }))}
          aria-label="Clause bloquante"
        />
        <Label htmlFor="ao-cps-bloquant" className="text-sm font-normal">
          Clause bloquante — le dossier ne peut pas être déposé si elle n’est pas satisfaite
        </Label>
      </div>
      <Button type="submit" size="sm" className="self-start" disabled={!complet || envoi}>
        {envoi ? 'Enregistrement…' : 'Ajouter la clause'}
      </Button>
    </form>
  )
}

export default function ExigencesPage({
  affaireId,
  pieceCps = null,
  blobCps = null,
  renderApercu,
  onPretADeposer,
  pollIntervalMs = POLL_MS,
}) {
  const routeParams = useParams()
  const id = affaireId ?? routeParams.id
  const [depot, setDepot] = useState(false)

  /* RÉPARATION 03/08/2026 — le filtre s'appelle `appel_offre`, PAS `affaire`.
     Vérifié dans le code serveur : `ExigenceCPSViewSet.get_queryset`
     (`apps/ao/views.py`) n'honore que ('appel_offre', 'type_exigence',
     'bloquant', 'a_reverifier', 'piece_consultation') via `_filtres_exacts`,
     qui LIT les noms qu'il connaît et IGNORE tout le reste — aucun 400, aucune
     trace. `?affaire=` renvoyait donc les clauses de TOUTES les affaires de la
     société sous le titre d'une seule : un filtre ignoré ne se voit pas, à la
     différence d'un 404. (`ExigenceCPS.appel_offre` est bien le nom du champ
     du modèle.) */
  const params = useMemo(() => (id ? { appel_offre: id } : undefined), [id])
  const { data: exigences, loading, error, refetch } = useResource(
    (p) => aoApi.exigencesCps.list(p), params,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les exigences du CPS.',
    },
  )

  // Tableau VIVANT : la conformité bouge quand le calepinage ou la chaîne
  // électrique bougent, sans que l'utilisateur rafraîchisse la page.
  useVisibilityAwarePolling(
    useMemo(() => [{ fn: refetch, intervalMs: pollIntervalMs }], [refetch, pollIntervalMs]),
    { enabled: Boolean(id) },
  )

  const creer = useCallback(async (form) => {
    await aoApi.exigencesCps.create(payloadClause(form, id))
    refetch()
  }, [id, refetch])

  const motif = useMemo(() => motifBlocageDepot(exigences), [exigences])
  const bloque = Boolean(motif)
  const aReverifier = useMemo(
    () => (exigences || []).filter((e) => e.a_reverifier),
    [exigences],
  )

  const marquerPret = useCallback(async () => {
    setDepot(true)
    try {
      // Le serveur reste la porte (AOF146) : cet appel peut être refusé, et
      // c'est son motif qui s'affiche alors.
      await (onPretADeposer
        ? onPretADeposer()
        : aoApi.affaires.update(id, { statut: 'pret_a_deposer' }))
      toast.success('Dossier marqué prêt à déposer.')
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Passage à « prêt à déposer » refusé.'))
    } finally {
      setDepot(false)
    }
  }, [id, onPretADeposer, refetch])

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">CPS &amp; exigences</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Clauses du cahier des charges, leur source dans le DCE, et leur conformité constatée
          sur le dossier réel.
        </p>
      </div>

      {aReverifier.length > 0 && (
        <Card className="flex items-start gap-2 border-warning/50 bg-warning/5 p-3" role="status">
          <RefreshCcw className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-warning">
              Exigences à revérifier après erratum
            </p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {/* RÉPARATION 03/08/2026 — `e.erratum_ref` n'existe pas : le
                  sérialiseur ne porte que le drapeau `a_reverifier`, jamais la
                  référence de l'additif. La mention était donc toujours vide.
                  Retirée : la pièce qui a déclenché la revérification se lit
                  sur l'onglet des pièces du DCE, pas ici. */}
              {aReverifier.map((e) => (
                <li key={e.id ?? e.code} className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{e.libelle || e.code}</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="flex min-w-0 flex-col gap-4">
          {loading && exigences.length === 0 ? (
            <Skeleton className="h-40 w-full" />
          ) : error ? (
            <EmptyState
              icon={ShieldCheck}
              title="Exigences indisponibles"
              description={error}
              action={<Button size="sm" variant="outline" onClick={refetch}>Réessayer</Button>}
            />
          ) : (
            <ConformiteTable exigences={exigences} />
          )}

          <Card className="p-4">
            <h2 className="mb-2 font-display text-base font-semibold">Saisir une clause</h2>
            <ClauseForm onCreer={creer} />
          </Card>

          {/* La porte de dépôt : jamais un bouton grisé sans explication. */}
          <Button
            className="self-start"
            disabled={bloque || depot}
            title={motif || undefined}
            onClick={marquerPret}
          >
            {bloque
              ? `Dépôt bloqué — ${motif}`
              : depot ? 'Enregistrement…' : 'Marquer « prêt à déposer »'}
          </Button>
        </div>

        {/* Aperçu du CPS à côté (AOF175, même composant). */}
        <Card className="min-h-[24rem] p-3">
          <h2 className="mb-2 flex items-center gap-1.5 font-display text-base font-semibold">
            <FileText className="size-4" aria-hidden="true" />
            Cahier des charges
          </h2>
          {renderApercu
            ? renderApercu({ piece: pieceCps })
            : <PiecePreview piece={pieceCps} blob={blobCps} />}
        </Card>
      </div>
    </div>
  )
}
