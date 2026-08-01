import { AlertTriangle, FileMinus, FilePlus, PenLine } from 'lucide-react'
import { Badge, Card, EmptyState } from '../../../ui'

/* ============================================================================
   AOF180 — Rendu du rapport de bascule (AOF142).
   ----------------------------------------------------------------------------
   Quatre catégories, jamais mélangées :
     • **modifié**  — emplacement effectivement mis à jour par l'opération ;
     • **SUSPECT**  — mention textuelle libre qui porte ENCORE l'ancienne
       référence ou l'ancien prix. C'est le défaut réel de la session : le
       montant final avait bien été cascadé (4 166 600 / 4 999 920) mais sa
       parenthèse de justification disait toujours « batteries 2 800 DH HT/kWh »
       alors que le bordereau final était à 2 600 ;
     • **fiche retirée** / **fiche ajoutée** — l'annexe suit l'équipement actif
       (l'oubli statistiquement le plus fréquent).

   **Les SUSPECTS ne sont jamais repliés, jamais réduits à un compteur.** Ils
   sont la seule raison d'être de ce rapport : les masquer derrière un
   « voir plus » reproduit exactement le défaut qu'il sert à attraper.
   ========================================================================== */

function Groupe({ titre, icone: Icone, tone, entrees, vide }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="flex items-center gap-1.5 text-sm font-medium">
        <Icone className="size-4" aria-hidden="true" />
        {titre}
        <Badge tone={tone}>{entrees.length}</Badge>
      </p>
      {entrees.length === 0 ? (
        <p className="text-xs text-muted-foreground">{vide}</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {entrees.map((e, i) => (
            <li key={e.id ?? `${e.emplacement}-${i}`} className="text-xs">
              <span className="font-medium text-foreground">{e.emplacement || e.libelle}</span>
              {e.extrait ? <span className="text-muted-foreground"> — « {e.extrait} »</span> : null}
              {e.motif ? <span className="text-muted-foreground"> — {e.motif}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function RapportBascule({ rapport }) {
  if (!rapport) {
    return (
      <EmptyState
        icon={PenLine}
        title="Aucun rapport"
        description="Aucune bascule d’équipement n’a encore été exécutée sur ce dossier."
      />
    )
  }

  const modifies = rapport.emplacements_modifies ?? []
  const suspects = rapport.emplacements_suspects ?? []
  const retirees = rapport.fiches_retirees ?? []
  const ajoutees = rapport.fiches_ajoutees ?? []

  return (
    <Card className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="font-display text-base font-semibold">Rapport de bascule</h3>
        {rapport.ancien_libelle && rapport.nouveau_libelle && (
          <p className="text-xs text-muted-foreground">
            {rapport.ancien_libelle} → {rapport.nouveau_libelle}
            {rapport.motif ? ` — motif : ${rapport.motif}` : ''}
          </p>
        )}
      </div>

      {/* Les SUSPECTS en premier, TOUJOURS dépliés. */}
      {suspects.length > 0 && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3" role="alert">
          <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-destructive">
            <AlertTriangle className="size-4" aria-hidden="true" />
            {suspects.length} emplacement(s) SUSPECT(S) — l’ancienne référence ou l’ancien prix y figure encore
          </p>
          <ul className="flex flex-col gap-1">
            {suspects.map((s, i) => (
              <li key={s.id ?? `${s.emplacement}-${i}`} className="text-xs">
                <span className="font-medium text-foreground">{s.emplacement || s.libelle}</span>
                {s.extrait ? <span className="text-destructive"> — « {s.extrait} »</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Groupe
        titre="Emplacements modifiés" icone={PenLine} tone="success"
        entrees={modifies} vide="Aucun emplacement modifié."
      />
      <Groupe
        titre="Fiches techniques retirées" icone={FileMinus} tone="warning"
        entrees={retirees} vide="Aucune fiche retirée."
      />
      <Groupe
        titre="Fiches techniques ajoutées" icone={FilePlus} tone="info"
        entrees={ajoutees} vide="Aucune fiche ajoutée."
      />

      {suspects.length === 0 && (
        <p className="text-xs text-success">Aucun emplacement suspect détecté.</p>
      )}
    </Card>
  )
}
