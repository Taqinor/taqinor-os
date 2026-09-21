import { AlertTriangle, CheckCircle2, FileMinus, FilePlus, PenLine, Replace } from 'lucide-react'
import { Badge, Card, EmptyState } from '../../../ui'
import { MOTIF_SUSPECT_LABEL, libelleEmplacement } from './EquipementsPage.utils'

/* ============================================================================
   AOF180 — Rendu du rapport de bascule (AOF142).
   ----------------------------------------------------------------------------
   **LA VÉRITÉ EST `apps/ao/fabrique/bascule_rapport.py::rapport_bascule`**, et
   ce composant est écrit sur SES clés :

       {ancien, nouveau, plan, modifies, suspects, bloquant}

   La version précédente lisait `emplacements_modifies`, `emplacements_suspects`,
   `fiches_retirees`, `fiches_ajoutees` et `ancien_libelle`/`nouveau_libelle` :
   SIX clés qui n'existent dans aucun module serveur. Le rapport se serait donc
   affiché entièrement vide — « aucun emplacement suspect détecté » sur un
   rapport qui en contenait — c'est-à-dire le contraire exact de sa raison
   d'être. Les fiches techniques ne sont pas deux listes : elles sont l'entrée
   `{nature: 'annexe', retirer, ajouter}` du PLAN, un seul geste indivisible
   (`annexes.appliquer_bascule` : « les deux moitiés séparées sont exactement
   la façon dont on garde une fiche périmée »).

   Le `motif` de la bascule n'est PAS dans le rapport (le module est pur, il ne
   connaît pas la requête) : il est passé en prop par l'écran, qui vient de le
   saisir. Afficher `rapport.motif` aurait été une septième clé inventée.

   **Les SUSPECTS ne sont jamais repliés, jamais réduits à un compteur.** Ils
   sont la seule raison d'être de ce rapport : les masquer derrière un
   « voir plus » reproduit exactement le défaut qu'il sert à attraper — le
   montant cascadé (4 166 600 / 4 999 920) dont la parenthèse de justification
   disait toujours « batteries 2 800 DH HT/kWh » quand le bordereau était à
   2 600.
   ========================================================================== */

// Les cinq champs comparés par `plan_bascule()`. `prix_unitaire` est le PU du
// BORDEREAU (la ligne que le maître d'ouvrage lit) — jamais un prix d'achat,
// jamais une marge : aucune donnée de coût n'entre dans ce rapport.
const CHAMP_LABEL = {
  designation: 'Désignation',
  reference: 'Référence',
  marque: 'Marque',
  prix_unitaire: 'Prix unitaire',
  unite: 'Unité',
}

const texte = (valeur) => (valeur == null || valeur === '' ? '—' : String(valeur))

function Groupe({ titre, icone, tone, entrees, vide, children }) {
  const Icone = icone
  return (
    <div className="flex flex-col gap-1.5">
      <p className="flex items-center gap-1.5 text-sm font-medium">
        <Icone className="size-4" aria-hidden="true" />
        {titre}
        <Badge tone={tone}>{entrees.length}</Badge>
      </p>
      {entrees.length === 0 ? <p className="text-xs text-muted-foreground">{vide}</p> : children}
    </div>
  )
}

export default function RapportBascule({ rapport, motif }) {
  if (!rapport) {
    return (
      <EmptyState
        icon={PenLine}
        title="Aucun rapport"
        description="Aucune bascule d’équipement n’a encore été exécutée sur ce dossier."
      />
    )
  }

  const ancien = rapport.ancien ?? {}
  const nouveau = rapport.nouveau ?? {}
  const plan = rapport.plan ?? []
  const modifies = rapport.modifies ?? []
  const suspects = rapport.suspects ?? []
  // `bloquant` est VRAI dès qu'un suspect subsiste : une bascule qui laisse une
  // justification en arrière n'est pas terminée, même si tous les montants sont
  // justes. C'est le verdict du module — jamais un calcul d'écran.
  const bloquant = rapport.bloquant === true

  const changements = plan.filter(
    (c) => c.nature === 'champ' || c.nature === 'caracteristique',
  )
  const annexe = plan.find((c) => c.nature === 'annexe') ?? {}

  return (
    <Card className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="font-display text-base font-semibold">Rapport de bascule</h3>
        <p className="text-xs text-muted-foreground">
          {texte(ancien.designation || ancien.reference)}
          {' → '}
          {texte(nouveau.designation || nouveau.reference)}
          {motif ? ` — motif : ${motif}` : ''}
        </p>
      </div>

      {bloquant ? (
        <p className="flex items-start gap-1.5 rounded-lg border border-destructive/40 bg-destructive/5 p-2.5 text-sm font-medium text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          Bascule INCOMPLÈTE — un emplacement porte encore l’ancienne référence ou
          l’ancien prix.
        </p>
      ) : (
        <p className="flex items-start gap-1.5 text-sm text-success">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          Aucun emplacement suspect détecté.
        </p>
      )}

      {/* Les SUSPECTS en premier, TOUJOURS dépliés. */}
      {suspects.length > 0 && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3" role="alert">
          <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-destructive">
            <AlertTriangle className="size-4" aria-hidden="true" />
            {suspects.length} emplacement(s) SUSPECT(S) — l’ancienne référence ou l’ancien prix y figure encore
          </p>
          <ul className="flex flex-col gap-1">
            {suspects.map((s, i) => (
              <li key={`${s.emplacement}-${s.motif}-${i}`} className="text-xs">
                <span className="font-medium text-foreground">{libelleEmplacement(s)}</span>
                {s.motif ? (
                  <span className="text-muted-foreground">
                    {' — '}
                    {MOTIF_SUSPECT_LABEL[s.motif] ?? s.motif}
                  </span>
                ) : null}
                {s.extrait ? <span className="text-destructive"> — « {s.extrait} »</span> : null}
                {s.attendu != null ? (
                  <span className="text-muted-foreground"> — attendu : {String(s.attendu)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Groupe
        titre="Emplacements modifiés" icone={PenLine} tone="success"
        entrees={modifies} vide="Aucun emplacement modifié."
      >
        <ul className="flex flex-col gap-1">
          {modifies.map((entree, i) => (
            <li key={`${libelleEmplacement(entree)}-${i}`} className="text-xs text-foreground">
              {libelleEmplacement(entree)}
            </li>
          ))}
        </ul>
      </Groupe>

      <Groupe
        titre="Changements appliqués" icone={Replace} tone="info"
        entrees={changements} vide="Aucun champ modifié."
      >
        <ul className="flex flex-col gap-1">
          {changements.map((c, i) => (
            <li key={`${c.nature}-${c.champ}-${i}`} className="text-xs">
              <span className="font-medium text-foreground">
                {CHAMP_LABEL[c.champ] ?? c.champ}
              </span>
              <span className="text-muted-foreground">
                {' : '}{texte(c.avant)} → {texte(c.apres)}
              </span>
            </li>
          ))}
        </ul>
      </Groupe>

      {/* L'annexe : UNE entrée du plan, deux moitiés indissociables. */}
      <div className="flex flex-col gap-1.5">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <FileMinus className="size-4" aria-hidden="true" />
          Fiche technique annexée
        </p>
        <ul className="flex flex-col gap-1 text-xs">
          <li className="flex items-center gap-1.5">
            <FileMinus className="size-3.5 shrink-0 text-warning" aria-hidden="true" />
            Fiche retirée : <span className="font-medium text-foreground">{texte(annexe.retirer)}</span>
          </li>
          <li className="flex items-center gap-1.5">
            <FilePlus className="size-3.5 shrink-0 text-info" aria-hidden="true" />
            Fiche ajoutée : <span className="font-medium text-foreground">{texte(annexe.ajouter)}</span>
          </li>
        </ul>
      </div>
    </Card>
  )
}
