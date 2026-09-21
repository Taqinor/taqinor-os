import { useEffect, useId, useRef, useState } from 'react'
import { Input, Label, Segmented, Switch } from '../../../ui'
import { safeGet, safeSet } from '../../../lib/safeStorage'
import RobustesseBadges from './RobustesseBadges'

/* ============================================================================
   AOF101 (1/2) — Mode expert : « le débutant voit un verdict et 5 tiroirs ;
   l'expert a tout. »
   ----------------------------------------------------------------------------
   Les 5 tiroirs (Kits AOF95, Allées AOF96, Rives AOF97, Orientation AOF98,
   Électrique AOF99) suffisent au débutant : ils recouvrent la décision
   courante. Cinq réglages plus fins n'intéressent que l'opérateur qui sait
   pourquoi il les touche — les exposer par défaut noierait l'écran :

     · pas de recherche du DP (`Parametres.pas_recherche_m`, 1 cm par défaut) ;
     · seuils de robustesse (`marge_troncon_min_m` / `marge_bande_min_m`) ;
     · phase (mode de pose « rangées uniformes à phase balayée », AOF47) ;
     · mode de pose : rangées explicites (DP) vs rangées uniformes (phase).

   **Désactivé par défaut, mémorisé PAR UTILISATEUR** (`safeStorage.js`,
   VX170 — jamais un `localStorage.setItem` direct) : un opérateur qui active
   le mode expert le retrouve activé à sa prochaine visite, mais un AUTRE
   utilisateur de la même machine ne l'hérite pas.

   **Aucun chiffre n'est recalculé ici** (garde AOF94) : `RobustesseBadges`
   (2/2) affiche les marges et leurs seuils tels que renvoyés par le moteur,
   ce composant ne fait que les transmettre et exposer les réglages.

   **PV51 — la clé de la Phase est `phase_forcee_m`, pas `phase_m`.** Le champ
   envoyait `{ phase_m }` par `majParametres` alors que le SEUL consommateur
   serveur (`apps/ao/calepinage_io.parametres_vers_document`) lit
   `params.get('phase_forcee_m')` : la clé voyageait jusqu'au corps de
   `/ao/calepinage/calculer/` et le serveur l'ignorait purement et simplement,
   silencieusement, en retombant sur la phase par défaut. Corrigé ici.

   **Le forçage de rangée a été RETIRÉ (PV51) :** `rangee_forcee` n'a jamais eu
   de consommateur côté serveur (`calepinage_io.parametres_vers_document` ne le
   lit nulle part) — un champ qui envoyait un patch dans le vide, sans jamais
   rien changer au calcul.
   ========================================================================== */

const MODES_POSE = [
  { value: 'rangees_explicites_dp', label: 'Rangées explicites (DP)' },
  { value: 'rangees_uniformes_phase', label: 'Rangées uniformes (phase)' },
]

function cleStockage(utilisateurId) {
  return `taqinor:ao-mode-expert:${utilisateurId ?? 'anonyme'}`
}

function ChampNombreExpert({
  id, label, valeur, onValide, disabled, suffixe,
}) {
  const [saisie, setSaisie] = useState(valeur == null ? '' : String(valeur))
  // Resynchronise si la valeur EXTERNE change (recalcul serveur, reset du
  // tiroir) — sans écraser une frappe en cours (même piège que
  // `TableauGeometrie.useBrouillon`, AOF77).
  const derniereExterne = useRef(valeur)
  useEffect(() => {
    if (derniereExterne.current !== valeur) {
      derniereExterne.current = valeur
      setSaisie(valeur == null ? '' : String(valeur))
    }
  }, [valeur])
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        step="any"
        inputMode="decimal"
        disabled={disabled}
        value={saisie}
        onChange={(e) => {
          const brut = e.target.value
          setSaisie(brut)
          const n = Number.parseFloat(brut)
          if (Number.isFinite(n)) onValide(suffixe ? n / suffixe : n)
        }}
      />
    </div>
  )
}

export function ModeExpert({
  valeurs = {},
  onChange,
  marges,
  seuils,
  utilisateurId,
}) {
  const cle = cleStockage(utilisateurId)
  const [actif, setActif] = useState(() => safeGet(cle) === true)

  // Identifiants UNIQUES par instance (`useId`) : deux ateliers montés côte à
  // côte (comparaison de variantes, un panneau par utilisateur) partageaient
  // sinon le même `id="ao-mode-expert"`. Le `label[for]` en double ne nomme
  // alors qu'UN seul interrupteur — le second devient anonyme pour un lecteur
  // d'écran comme pour le pilotage vocal.
  const uid = useId()
  const idExpert = `${uid}-mode-expert`
  const idDescription = `${uid}-mode-expert-description`
  const idPasRecherche = `${uid}-pas-recherche`
  const idPhase = `${uid}-phase`
  const idSeuilTroncon = `${uid}-seuil-troncon`
  const idSeuilBande = `${uid}-seuil-bande`

  const basculer = (valeur) => {
    setActif(valeur)
    safeSet(cle, valeur)
  }

  const modePose = valeurs.mode_pose ?? MODES_POSE[0].value

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border p-3" data-ao-tiroir="expert">
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <Label htmlFor={idExpert}>Mode expert</Label>
          <p id={idDescription} className="text-xs font-normal text-muted-foreground">
            Réglages fins du moteur — pas de recherche, seuils, phase.
          </p>
        </div>
        <Switch
          id={idExpert}
          aria-describedby={idDescription}
          checked={actif}
          onCheckedChange={basculer}
        />
      </div>

      {actif && (
        <div className="flex flex-col gap-4 border-t border-border pt-3">
          <RobustesseBadges marges={marges} seuils={seuils} />

          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">Mode de pose</span>
            <Segmented
              aria-label="Mode de pose"
              options={MODES_POSE}
              value={modePose}
              onChange={(v) => onChange?.({ mode_pose: v })}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <ChampNombreExpert
              id={idPasRecherche}
              label="Pas de recherche (m)"
              valeur={valeurs.pas_recherche_m}
              onValide={(n) => onChange?.({ pas_recherche_m: n })}
            />
            <ChampNombreExpert
              id={idPhase}
              label="Phase (m)"
              valeur={valeurs.phase_forcee_m}
              disabled={modePose !== 'rangees_uniformes_phase'}
              onValide={(n) => onChange?.({ phase_forcee_m: n })}
            />
            <ChampNombreExpert
              id={idSeuilTroncon}
              label="Seuil marge tronçon (cm)"
              valeur={Number.isFinite(valeurs.marge_troncon_min_m) ? valeurs.marge_troncon_min_m * 100 : null}
              suffixe={100}
              onValide={(n) => onChange?.({ marge_troncon_min_m: n })}
            />
            <ChampNombreExpert
              id={idSeuilBande}
              label="Seuil marge bande (cm)"
              valeur={Number.isFinite(valeurs.marge_bande_min_m) ? valeurs.marge_bande_min_m * 100 : null}
              suffixe={100}
              onValide={(n) => onChange?.({ marge_bande_min_m: n })}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default ModeExpert
