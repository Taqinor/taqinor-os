/* ============================================================================
   AOF9 — Provenance d'une valeur relevée (toiture/calepinage AO), PURE (aucune
   dépendance React) : testable au node, consommé par `ProvenanceBadge.jsx`.
   ----------------------------------------------------------------------------
   Miroir des 3 couleurs d'IMPRESSION figées par `dessin.py:16-19` (BLEU
   mesuré / ORANGE à confirmer / GRIS plan-ou-déduit) + une 4ᵉ nuance
   « deviné » sans équivalent imprimé (compteur AOF90 « X mesurés, Y à
   confirmer, Z deviné »). `token` référence le custom-property CSS posé dans
   `design/tokens.css` (paires clair/sombre AA — voir ce fichier) ; `printHex`
   est le hex NORMATIF d'impression (celui que verra la planche imprimée),
   `null` quand il n'y en a pas (deviné). Un token CSS et son `printHex`
   documentent la MÊME teinte — jamais un byte-à-byte forcé côté écran (AA
   l'exige), fixé par `provenance.test.jsx`.
   ========================================================================== */

export const PROVENANCE_ORDER = ['mesure', 'confirmer', 'deduit', 'devine']

export const PROVENANCE_LEVELS = {
  mesure: {
    label: 'Mesuré',
    token: '--ao-provenance-mesure',
    printHex: '#1d4ed8',
    description: 'Valeur relevée directement sur site ou sur un plan calibré à 2 points.',
  },
  confirmer: {
    label: 'À confirmer',
    token: '--ao-provenance-confirmer',
    printHex: '#d97706',
    description: 'Valeur saisie mais non vérifiée sur site — à confirmer avant dépôt.',
  },
  deduit: {
    label: 'Plan / déduit',
    token: '--ao-provenance-deduit',
    printHex: '#64748b',
    description: "Valeur lue sur un plan fourni ou déduite d'une fermeture de cotes (résidu de chaîne).",
  },
  devine: {
    label: 'Deviné',
    token: '--ao-provenance-devine',
    printHex: null,
    description: 'Valeur estimée, sans mesure ni plan ni déduction — la moins fiable des 4 provenances.',
  },
}

export function provenanceLabel(level) {
  return PROVENANCE_LEVELS[level]?.label ?? level
}

export function provenanceToken(level) {
  return PROVENANCE_LEVELS[level]?.token ?? null
}

export function provenanceDescription(level) {
  return PROVENANCE_LEVELS[level]?.description ?? ''
}

export function provenancePrintHex(level) {
  return PROVENANCE_LEVELS[level]?.printHex ?? null
}

export default PROVENANCE_LEVELS
