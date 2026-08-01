/* ============================================================================
   AOF107 (3/3) — Garde de VOCABULAIRE avant tout export Q/R.
   ----------------------------------------------------------------------------
   Contrainte réelle : depuis une session cloud, les pièces jointes classiques
   sont illisibles (SVG bloqué par la politique MIME, PNG en erreur Graph 400,
   PDF de plans = scans raster sans texte) — seule une image COLLÉE dans la
   conversation passe. `ExportQR.jsx` (2/3) produit donc une image à coller ;
   ce module (3/3), lui, est le CONTRÔLE qui la précède : signaler EN LIGNE les
   mots interdits d'un texte destiné au client, avec sa formulation de
   remplacement quand il en existe une.

   **Portée volontairement ÉTROITE.** Le lexique complet à DEUX niveaux
   (bloquant + avertissement, contextuel PAR CHAMP) est une tâche SÉPARÉE côté
   fabrique documentaire (`apps/ao/fabrique/sanitisation.py`, AOF143, W6b) — ce
   module ne l'anticipe pas et ne le réimplémente pas : il couvre seulement le
   petit lexique nommé par CE ticket (« client », « croquis », « maximum
   posable », toute mention de marge ou de prix d'achat), pour l'export d'une
   fiche Q/R. Les DEUX modules resteront décorrélés par design (l'un est du
   Python serveur pour le pack complet, l'autre du JS pur pour un export
   ponctuel) — ne pas les fusionner à l'occasion d'un futur audit.

   **Détection, jamais de substitution automatique.** Ce module ne réécrit
   RIEN tout seul : une reformulation automatique et silencieuse d'un texte
   destiné au client serait pire que le mot qu'elle corrige (elle pourrait
   changer le sens sans que personne ne s'en aperçoive). Il rend la liste des
   mots trouvés, avec la formulation de remplacement PROPOSÉE quand il y en a
   une — à l'écran de décider (bloquer, ou exporter après confirmation
   explicite, per le Done de l'AOF107).
   ========================================================================== */

// `remplacement` est soit une chaîne fixe, soit une fonction du contexte
// (`{ date }`) quand la formulation de rechange embarque une date — soit
// `null` quand il n'y a AUCUNE reformulation acceptable (le mot doit
// simplement disparaître : « maximum posable », « marge », « prix d'achat »
// n'ont pas de synonyme client-compatible, ils n'ont rien à faire dans un
// document remis au maître d'ouvrage).
export const REGISTRE_VOCABULAIRE = [
  {
    code: 'client',
    libelle: '« client »',
    motif: /\bclients?\b/giu,
    remplacement: (contexte) => `décision d’études du ${contexte?.date ?? '[date]'}`,
  },
  {
    code: 'croquis',
    libelle: '« croquis »',
    motif: /\bcroquis\b/giu,
    remplacement: (contexte) => `relevé contradictoire du ${contexte?.date ?? '[date]'}`,
  },
  {
    code: 'maximum_posable',
    libelle: '« maximum posable »',
    motif: /\bmaximum posable\b/giu,
    remplacement: null,
  },
  {
    code: 'marge',
    libelle: '« marge »',
    motif: /\bmarges?\b/giu,
    remplacement: null,
  },
  {
    code: 'prix_achat',
    libelle: "« prix d'achat »",
    motif: /\bprix d[’']achat\b/giu,
    remplacement: null,
  },
]

/**
 * Détecte chaque occurrence d'un mot interdit dans `texte`.
 * Rend `[{ code, libelle, motTrouve, index, remplacement }]`, triés par
 * position — `remplacement` est `null` quand aucune reformulation n'existe
 * (le mot doit être retiré, pas remplacé).
 */
export function detecterMotsInterdits(texte, contexte = {}) {
  if (typeof texte !== 'string' || texte === '') return []
  const trouvailles = []
  for (const regle of REGISTRE_VOCABULAIRE) {
    // Clone du motif : un `RegExp` global est STATEFUL (`lastIndex`) — le
    // registre est un module-level singleton réutilisé par tous les appels.
    const motif = new RegExp(regle.motif.source, regle.motif.flags)
    let m = motif.exec(texte)
    while (m !== null) {
      trouvailles.push({
        code: regle.code,
        libelle: regle.libelle,
        motTrouve: m[0],
        index: m.index,
        remplacement: typeof regle.remplacement === 'function'
          ? regle.remplacement(contexte)
          : regle.remplacement,
      })
      // Garde anti-boucle infinie sur un motif qui matcherait la chaîne vide
      // (aucune règle actuelle ne le fait, mais un futur ajout pourrait).
      if (m[0].length === 0) motif.lastIndex += 1
      m = motif.exec(texte)
    }
  }
  return trouvailles.sort((a, b) => a.index - b.index)
}

/** Vrai dès qu'AU MOINS UN mot interdit est présent dans `texte`. */
export function contientMotInterdit(texte, contexte = {}) {
  return detecterMotsInterdits(texte, contexte).length > 0
}

/**
 * Applique la détection à PLUSIEURS champs nommés (`{ question: '…',
 * reponse: '…' }`) — rend un objet `{ <champ>: [trouvailles] }` ne portant
 * QUE les champs effectivement fautifs (un champ propre n'apparaît pas).
 * C'est ce que l'écran d'export interroge pour savoir s'il doit exiger une
 * confirmation explicite avant de produire l'image.
 */
export function detecterSurChamps(champs = {}, contexte = {}) {
  const parChamp = {}
  for (const [nom, texte] of Object.entries(champs)) {
    const trouvailles = detecterMotsInterdits(texte, contexte)
    if (trouvailles.length > 0) parChamp[nom] = trouvailles
  }
  return parChamp
}

export default {
  REGISTRE_VOCABULAIRE,
  detecterMotsInterdits,
  contientMotInterdit,
  detecterSurChamps,
}
