/* ACAL1193 — les CINQ cartes de l'écran Documents guidé (maquette `Documents.dc.html`), choisies parmi
   les pièces SERVIES : l'inventaire `documents/` (CALX291) et l'inventaire `sorties/` (CALX19).
   Rien n'est inventé : une pièce que le serveur ne publie pas pour ce calepinage n'a pas de carte ;
   une pièce publiée mais indisponible garde sa carte, grisée, avec le motif servi. Les titres et
   descriptions sont ceux de la maquette (texte fixe, aucun chiffre). */

const CARTES = [
  { cle: 'plan_pose', vignette: 'plan_pose', source: 'sortie', code: 'plan_pose_pdf', titre: 'Plan de pose pour l’équipe',
    description: 'Place de chaque panneau, distances aux bords du toit, chaînes en couleur. PDF.' },
  { cle: 'schema', vignette: 'schema', source: 'document', code: 'plan_cablage', titre: 'Schéma électrique',
    description: 'Des panneaux au compteur, avec la section de chaque câble. PDF.' },
  { cle: 'note_calcul', vignette: 'note_calcul', source: 'sortie', code: 'note_calcul_pdf', titre: 'Note de calcul',
    description: 'Tension par temps froid, câbles, protections : chaque chiffre avec sa règle. PDF.' },
  { cle: 'rapport_etude', vignette: 'rapport_etude', source: 'document', code: 'rapport_etude', titre: 'Rapport d’étude',
    description: 'Production mois par mois, pertes, ombres, et ce que le calcul ne prend pas en compte. PDF.' },
  { cle: 'dxf', vignette: 'dxf', source: 'sortie', code: 'dxf', titre: 'Plan au format DXF',
    description: 'Pour AutoCAD ou un autre logiciel de dessin : chaque panneau numéroté, avec son pan et sa chaîne.' },
]

/** Les cartes à montrer : `{cle, vignette, titre, description, source, code, entree, disponible, motif,
    apercu}` — `apercu` : 'html' (aperçu serveur de `documents/`), 'pdf' (la pièce PDF ouverte dans un
    onglet) ou `null` (le DXF ne s'affiche pas : pas de bouton). */
export function cartesGuide(documents, sorties) {
  return CARTES.flatMap((carte) => {
    const liste = carte.source === 'document' ? documents : sorties
    const entree = (liste || []).find((e) => e.code === carte.code)
    if (!entree) return []
    let apercu = null
    if (carte.source === 'document' && entree.apercu) apercu = 'html'
    else if (entree.format === 'pdf') apercu = 'pdf'
    return [{ ...carte, entree, disponible: Boolean(entree.disponible), motif: entree.motif_indisponible || '', apercu }]
  })
}
