/* ROUND 5 — « ce qui manque » : UNE source, deux surfaces.
   ---------------------------------------------------------------------------
   L'intuition fondateur — « voir d'abord ce qui manque selon l'étape » — se
   livre par un BANDEAU qui pointe, jamais par un réordonnancement des
   sections (verdict de la recherche design : Salesforce Path, HubSpot
   required-per-stage, et la littérature anti-réordonnancement d'Office 2000 à
   NN/g — un formulaire qui se réorganise détruit la mémoire spatiale).

   Ce module tient la logique PURE de ce bandeau, à part de tout composant,
   pour deux raisons : l'onglet Devis (rail contexte) et le centre
   (SectionsPane) doivent pointer les MÊMES champs — deux cartes divergentes
   seraient pires que pas de carte — et parce qu'une règle testable sans DOM
   se vérifie exhaustivement.

   Les manquants du DEVIS viennent du serveur (`devis_auto.manquants`, produit
   par apps/crm/devis_auto.py `champs_manquants`) : on ne recalcule JAMAIS la
   règle ici, on ne fait que la rendre cliquable. Les clés d'étape viennent de
   stages.js (miroir STAGES.py, règle #2) — aucune clé en dur. */
// Extensions explicites : ce module est PUR et se teste en `node --test`
// (résolution ESM stricte) — même convention que stages.js → lib/format.js.
import { FOLLOW_UP_STAGE, QUOTE_SENT_STAGE } from '../stages.js'
import { getField } from './draftCore.js'

// LW21 — mapping libellés backend (texte FR fixe de `champs_manquants`) → id
// DOM du champ dans SectionsPane (`lf-*`) + sa section. Déplacé ici depuis
// DevisTab, qui le RÉEXPORTE (aucun appelant ni test existant ne bouge).
export const DEVIS_AUTO_FIELD_IDS = {
  'facture hiver': { field: 'lf-facture-hiver', section: 'energie' },
  'facture été': { field: 'lf-facture-ete', section: 'energie' },
  'consommation mensuelle (kWh)': { field: 'lf-conso-mensuelle', section: 'energie' },
  'pompe (CV)': { field: 'lf-pompe-cv', section: 'pompage' },
  HMT: { field: 'lf-pompe-hmt', section: 'pompage' },
  'débit souhaité': { field: 'lf-pompe-debit', section: 'pompage' },
}

export function missingFieldTarget(label) {
  return DEVIS_AUTO_FIELD_IDS[label] ?? null
}

const vide = (v) => v === '' || v === null || v === undefined

// Les étapes où une relance NON planifiée est une vraie lacune : un devis est
// parti (ou on est déjà en relance) et personne ne sait quand rappeler. Avant
// l'envoi du devis, ne rien avoir planifié est normal — on ne le signale pas.
const ETAPES_RELANCE_ATTENDUE = [QUOTE_SENT_STAGE, FOLLOW_UP_STAGE]

/**
 * chipsAComplete — ce que le bandeau doit montrer, ou RIEN.
 *
 * Renvoie un tableau VIDE quand tout va bien, et l'appelant ne rend alors
 * aucun chrome : pas de boîte « tout est complet ✓ » qui occuperait de la
 * place en permanence pour ne rien dire (leçon fondateur de la « case grise »
 * des en-têtes de colonne, retirée au round 3).
 *
 * @param {object} state état du moteur (draft ∪ serveur)
 * @returns {Array<{id: string, label: string, section: string, field: string|null}>}
 */
export function chipsAComplete(state) {
  const chips = []

  // (1) Ce qui bloque le devis automatique — libellés FR tels que le serveur
  // les écrit, pour que l'écran et l'API disent exactement la même chose.
  for (const label of state?.server?.devis_auto?.manquants ?? []) {
    const cible = missingFieldTarget(label)
    chips.push({
      id: `devis:${label}`,
      label,
      section: cible?.section ?? null,
      field: cible?.field ?? null,
    })
  }

  // (2) Ce que l'ÉTAPE rend attendu. Une seule règle pour l'instant, et elle
  // est délibérément étroite : un signal qu'on apprend à ignorer ne vaut rien.
  const etape = getField(state, 'stage')
  if (ETAPES_RELANCE_ATTENDUE.includes(etape) && vide(getField(state, 'relance_date'))) {
    chips.push({
      id: 'relance',
      label: 'Relance non planifiée',
      section: 'pipeline',
      field: 'lf-relance-date',
    })
  }

  return chips
}

// Les sections pointées par le bandeau — elles ne doivent JAMAIS s'ouvrir
// repliées (SectionsPane), sous peine de se contredire dans le même écran.
export function sectionsPointees(chips) {
  return new Set((chips ?? []).map((c) => c.section).filter(Boolean))
}
