// ENF22 — helpers extraits de PlanificationPage.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

export // ── FG68 / VX251 — Calendrier dispatch techniciens (glisser-déposer) ──────────
// VX251 — glisser une carte intervention d'une colonne-technicien à une autre
// réaffecte réellement (PATCH `technicien` EXISTANT) avec un toastWithUndo 6 s
// (VX95, jamais un 2ᵉ primitif undo) : « Annuler » restaure l'affectation.
// Le geste réplique le pattern drag+recul-guard prouvé par KanbanView.jsx (CRM).
const NON_ASSIGNE = '__non_assigne__'

export // Clé droppable stable d'une colonne technicien (id numérique ou sentinelle).
const colKey = (grp) => String(grp?.technicien?.id ?? NON_ASSIGNE)

export // ── APX28 — VRAIE grille horaire (jour) × techniciens ────────────────────────
// CHAMPS RÉELLEMENT SERVIS (vérifiés dans `apps/installations/models_intervention.py`
// + `InterventionSerializer(fields='__all__')`) : `date_prevue` est un DateField
// (AUCUNE heure), il n'existe AUCUN champ de durée, et la seule information
// horaire est la fenêtre de RDV XFSM5 `fenetre_debut`/`fenetre_fin` (TimeField,
// nullable, écrivable par le PATCH générique).
// CONSÉQUENCE ASSUMÉE : une intervention SANS fenêtre n'est JAMAIS placée à une
// heure inventée — elle va dans la bande « Sans créneau » de sa colonne, en
// blocs séquencés à hauteur fixe. Poser/déplacer une intervention sur la grille
// ÉCRIT la fenêtre choisie (action explicite de l'utilisateur, confirmée).
const HEURE_DEBUT = 7

export const HEURE_FIN = 19

export const SLOT_PX = 44

// + les 2 bordures 1 px

// 'HH:MM' / 'HH:MM:SS' → minutes depuis minuit ; null si absent/illisible.
export function minutesDeHeure(t) {
  if (typeof t !== 'string') return null
  const m = /^(\d{1,2}):(\d{2})/.exec(t.trim())
  if (!m) return null
  const h = Number(m[1]), min = Number(m[2])
  if (h > 23 || min > 59) return null
  return h * 60 + min
}

export const deuxChiffres = (n) => String(n).padStart(2, '0')

export const heureEnTime = (h, min = 0) => `${deuxChiffres(h)}:${deuxChiffres(min)}:00`

// Géométrie d'un bloc sur l'axe des heures. `null` = pas de fenêtre servie
// (l'intervention n'a rien à faire sur l'axe : elle ira en « Sans créneau »).
export function blocGeometry(iv) {
  const debut = minutesDeHeure(iv?.fenetre_debut)
  if (debut == null) return null
  const finBrute = minutesDeHeure(iv?.fenetre_fin)
  // Fenêtre sans fin servie : on ne DEVINE pas une durée — un créneau d'une
  // graduation, la hauteur minimale de la grille.
  const fin = finBrute != null && finBrute > debut ? finBrute : debut + 60
  const min0 = HEURE_DEBUT * 60, min1 = HEURE_FIN * 60
  const d = Math.max(debut, min0)
  const f = Math.min(fin, min1)
  if (f <= min0 || d >= min1) return null // entièrement hors de la plage rendue
  return {
    topPx: ((d - min0) / 60) * SLOT_PX,
    heightPx: Math.max(((f - d) / 60) * SLOT_PX, 22),
    debutMin: debut,
    finMin: fin,
    horsPlage: debut < min0 || fin > min1,
  }
}

// Corps EXACT du PATCH d'un dépôt (endpoint EXISTANT `updateIntervention`) :
// technicien + jour, et la fenêtre UNIQUEMENT quand un créneau a été visé.
// Aucune durée n'est inventée : un créneau vaut la graduation de la grille (1 h).
export function payloadDeplacement(toKey, jourCible, heure) {
  return {
    technicien: String(toKey) === NON_ASSIGNE ? null : Number(toKey),
    date_prevue: jourCible,
    ...(heure != null
      ? { fenetre_debut: heureEnTime(heure), fenetre_fin: heureEnTime(heure + 1) }
      : {}),
  }
}

// Chevauchements RÉELS au sein d'une même colonne (même technicien, même jour) :
// renvoie l'ensemble des ids en conflit. Deux interventions sans fenêtre ne
// sont PAS un conflit (aucune heure n'est connue — on n'invente rien).
export function chevauchements(interventions) {
  const avecHeure = (interventions ?? [])
    .map((iv) => ({ id: iv.id, geo: blocGeometry(iv) }))
    .filter((x) => x.geo)
  const enConflit = new Set()
  for (let i = 0; i < avecHeure.length; i += 1) {
    for (let j = i + 1; j < avecHeure.length; j += 1) {
      const a = avecHeure[i].geo, b = avecHeure[j].geo
      if (a.debutMin < b.finMin && b.debutMin < a.finMin) {
        enConflit.add(avecHeure[i].id)
        enConflit.add(avecHeure[j].id)
      }
    }
  }
  return enConflit
}

// VX251 — déplacement PUR (testable) d'une intervention entre colonnes
// technicien de l'état du calendrier. Renvoie un nouvel état (jamais de
// mutation) ; renvoie l'entrée inchangée si l'intervention est introuvable
// dans la colonne source.
export function moveInterventionLocal(list, ivId, fromKey, toKey) {
  let moved = null
  const stripped = (list ?? []).map((grp) => {
    if (colKey(grp) !== String(fromKey)) return grp
    const kept = grp.interventions.filter((x) => {
      if (String(x.id) === String(ivId)) { moved = x; return false }
      return true
    })
    return { ...grp, interventions: kept }
  })
  if (!moved) return list
  return stripped.map((grp) => (colKey(grp) === String(toKey)
    ? { ...grp, interventions: [...grp.interventions, moved] }
    : grp))
}
