import { useRef, useState } from 'react'
import { Users2 } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Button, Spinner,
} from '../../ui'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'

/* ============================================================================
   MRY33 — Cockpit (rôles responsable/admin) : « Anciens leads à placer dans
   les cadences ». Décision fondateur 06/09/2026 — tous les anciens leads non
   Froid sont traités : le moteur décide seul à quelle étape des six appels
   chacun se trouve. « Aperçu » n'écrit RIEN (`POST leads/placement-cadences/
   {apply:false}`, MRY30) ; « Appliquer » (confirmation explicite, N/M dérivés
   de l'aperçu — jamais recomptés à la main) place réellement les leads.

   Contrat committé `apps/crm/contract_samples/placement_anciens_leads.json`
   (PACT10) — PAYLOAD importé dans le test, jamais un objet retapé à la main.
   Gate de rôle FAIT ICI (composant auto-suffisant, `null` pour un rôle
   normal) plutôt que dans `CrmCockpit.jsx` — même esprit que le badge « vient
   de la pub » de `IdentityRail.jsx` (`useIsAdminOrResponsable`).

   PERFORMANCE (incident du 07/09 en prod : « Aperçu » a dépassé le timeout
   axios de 20 s — nginx 499). L'aperçu est resté un calcul pur côté serveur
   (rapide, inchangé) ; « Appliquer » écrit maintenant PAR LOTS (`limite`,
   défaut 40) et renvoie `restants` — cet écran rappelle l'API tant qu'il en
   reste ET qu'un lot a effectivement avancé, jamais un unique appel qui
   pourrait de nouveau dépasser le timeout sur un grand volume.
   ========================================================================== */

// Taille de lot envoyée au serveur (`limite`, alignée sur le défaut du
// contrat) et plafond de sécurité du nombre de lots enchaînés — un filet
// jamais atteint en pratique (le volume réel tient en quelques lots de 40).
const TAILLE_LOT = 40
const PLAFOND_LOTS = 50

// `prochaine_le` (ISO, fuseau posé par le serveur) → « JJ/MM HH:MM » Casablanca
// EXPLICITE (jamais le fuseau du navigateur — même trick que `heureDue` de
// `features/crm/relances/RelanceEtapeRow.jsx`).
function heureCasa(iso) {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    timeZone: 'Africa/Casablanca',
  }).format(t)
}

// M de la confirmation « Appliquer » — somme des codes de décision DORMANTS
// (Froid + réveil étalé, cf. `placement_anciens_leads.json`) — jamais les
// codes contact/après-devis positionnés, qui ne changent pas l'étape.
function nombreDormants(parEtape) {
  return parEtape
    .filter((e) => e.code.startsWith('dormant_'))
    .reduce((somme, e) => somme + (e.nombre || 0), 0)
}

export default function PlacementAnciensLeadsCard() {
  const isResponsableOuAdmin = useIsAdminOrResponsable()
  const { confirm } = useConfirmDialog()
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(false)
  const [donnees, setDonnees] = useState(null)
  const [applying, setApplying] = useState(false)
  // Progression du lot en cours (`{ places, restants }`, lus tels quels sur
  // chaque réponse — jamais recalculés). `interrompu` + `nonPlaces` portent
  // l'arrêt anormal (lot sans avancée ou erreur réseau) qui affiche
  // « Reprendre » à la place d'« Appliquer ».
  const [progression, setProgression] = useState(null)
  const [interrompu, setInterrompu] = useState(false)
  const [nonPlaces, setNonPlaces] = useState(0)
  // Cumul des leads placés sur TOUTE la séquence (survit à un « Reprendre »,
  // remis à zéro seulement par un nouveau clic sur « Appliquer ») — le toast
  // final annonce ce total, jamais le seul dernier lot.
  const totalPlaceRef = useRef(0)

  if (!isResponsableOuAdmin) return null

  const chargerApercu = () => {
    setLoading(true)
    setErreur(false)
    crmApi.placerAnciensLeads({ apply: false })
      .then((r) => setDonnees(r.data))
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  // Un lot (`{apply:true, limite:40}`) à la fois : avance le cumul, publie la
  // progression, et continue tant qu'il reste des leads ET que le dernier
  // lot en a placé au moins un — sinon (tout a échoué) ou au-delà du plafond
  // de sécurité, on s'arrête et on laisse « Reprendre » relancer plus tard.
  const lancerLot = async () => {
    setApplying(true)
    setInterrompu(false)
    setNonPlaces(0)
    let iterations = 0
    let reponse = { applique: 0, erreurs: 0, restants: 1 }
    try {
      do {
        iterations += 1
        const r = await crmApi.placerAnciensLeads({ apply: true, limite: TAILLE_LOT })
        reponse = r.data || {}
        totalPlaceRef.current += reponse.applique || 0
        setProgression({ places: totalPlaceRef.current, restants: reponse.restants || 0 })
      } while (
        (reponse.restants || 0) > 0
        && (reponse.applique || 0) > 0
        && iterations < PLAFOND_LOTS
      )
      if ((reponse.restants || 0) === 0) {
        toast.success(`${totalPlaceRef.current} lead(s) placé(s).`)
        setProgression(null)
        totalPlaceRef.current = 0
        // La carte se resynchronise sur le nouvel état serveur (peut désormais
        // retomber à 0 à placer, ou refléter les ignorés recalculés) — jamais
        // un décrément local optimiste qui divergerait du vrai résultat.
        chargerApercu()
      } else {
        // Le dernier lot n'a rien avancé (ou le plafond de sécurité est
        // atteint) alors qu'il en reste : on arrête plutôt que de boucler
        // sans fin sur des leads qui échouent tous.
        setNonPlaces(reponse.erreurs || 0)
        setInterrompu(true)
      }
    } catch {
      toast.error('Placement impossible pour le moment.')
      setInterrompu(true)
    } finally {
      setApplying(false)
    }
  }

  const appliquer = async () => {
    if (!donnees) return
    const m = nombreDormants(donnees.par_etape)
    const ok = await confirm({
      title: 'Placer les anciens leads dans les cadences ?',
      description: `${donnees.a_placer} lead(s) seront placés dans une cadence, `
        + `dont ${m} passeront en Froid avec un réveil. Continuer ?`,
      confirmLabel: 'Appliquer',
      cancelLabel: 'Annuler',
      destructive: false,
    })
    if (!ok) return
    totalPlaceRef.current = 0
    await lancerLot()
  }

  // « Reprendre » relance la même boucle SANS reconfirmer (l'utilisateur a
  // déjà validé l'action globale) — elle continue le cumul là où il s'est
  // arrêté.
  const reprendre = () => { lancerLot() }

  const aApercu = !!donnees
  const aucunAPlacer = aApercu && donnees.a_placer === 0

  return (
    <Card data-testid="placement-anciens-leads-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users2 className="h-4 w-4" /> Anciens leads à placer dans les cadences
        </CardTitle>
        <CardDescription>
          Tous les anciens leads non Froid sont traités : le moteur décide seul à
          quelle étape des six appels chacun se trouve.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={chargerApercu} disabled={loading || applying}>
            Aperçu
          </Button>
          {interrompu ? (
            <Button size="sm" onClick={reprendre} disabled={applying}>
              Reprendre
            </Button>
          ) : (
            <Button size="sm" onClick={appliquer} disabled={!aApercu || donnees?.a_placer === 0 || applying}>
              Appliquer
            </Button>
          )}
          {applying && <Spinner className="h-4 w-4" label="Placement en cours…" />}
        </div>
        {applying && progression && (
          <p className="mb-2 text-xs text-muted-foreground">
            {progression.places} placés · {progression.restants} restants
          </p>
        )}
        {interrompu && nonPlaces > 0 && (
          <p className="mb-2 text-sm text-muted-foreground">
            {nonPlaces} lead(s) n&apos;ont pas pu être placés.
          </p>
        )}
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : !aApercu ? (
          <p className="text-sm text-muted-foreground">
            Cliquez « Aperçu » pour voir les anciens leads à placer.
          </p>
        ) : aucunAPlacer ? (
          <p className="text-sm text-muted-foreground">Aucun ancien lead à placer.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="outline">Candidats : {donnees.total_candidats}</Badge>
              <Badge tone="primary">À placer : {donnees.a_placer}</Badge>
              {donnees.restants !== donnees.a_placer && (
                <Badge tone="neutral">Restants : {donnees.restants}</Badge>
              )}
              {donnees.ignores.deja_en_cadence > 0 && (
                <Badge tone="neutral">Déjà en cadence : {donnees.ignores.deja_en_cadence}</Badge>
              )}
              {donnees.ignores.devis_accepte_non_signe > 0 && (
                <Badge tone="warning">
                  Devis accepté non signé : {donnees.ignores.devis_accepte_non_signe}
                </Badge>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="pb-1 pr-2 font-medium">Étape</th>
                    <th className="pb-1 pr-2 font-medium">Cadence</th>
                    <th className="pb-1 text-right font-medium">Nombre</th>
                  </tr>
                </thead>
                <tbody>
                  {donnees.par_etape.map((e) => (
                    <tr key={e.code} className="border-t border-border">
                      <td className="py-1 pr-2">{e.libelle}</td>
                      <td className="py-1 pr-2">{e.cadence}</td>
                      <td className="py-1 text-right tabular-nums">{e.nombre}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {donnees.apercu.length > 0 && (
              <ul className="space-y-1.5">
                {donnees.apercu.map((l) => (
                  <li key={l.lead} className="rounded-md border border-border p-2 text-xs">
                    <span className="font-medium">{l.nom}</span>
                    <span className="text-muted-foreground"> · {l.stage_libelle} · {l.jours} j</span>
                    <span className="block text-muted-foreground">
                      {l.cadence} — {l.prochaine_touche}
                      {l.prochaine_le ? ` (${heureCasa(l.prochaine_le)})` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {donnees.reveils_jusqu_au && (
              <p className="text-xs text-muted-foreground">
                Réveils étalés jusqu&apos;au {donnees.reveils_jusqu_au}.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
