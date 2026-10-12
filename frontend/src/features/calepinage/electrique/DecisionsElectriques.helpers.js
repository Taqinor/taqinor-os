// ENF22 — helpers extraits de DecisionsElectriques.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { nombreOuNull, texteOuNull } from './entreeElectrique'

/** Les champs de la décision de terre. `genre` : bool | nombre | texte | date (AAAA-MM-JJ). */
export const TERRE_CHAMPS = [
  { cle: 'justification_continuite', libelle: 'Justification de la continuité de la terre existante', genre: 'bool' },
  { cle: 'resistance_ohm', libelle: 'Résistance de la prise de terre (Ω)', genre: 'nombre' },
  { cle: 'point_mesure_prise', libelle: 'Point de mesure de la prise de terre', genre: 'texte' },
  { cle: 'date_mesure_prise', libelle: 'Date de la mesure de la prise (AAAA-MM-JJ)', genre: 'date' },
  { cle: 'continuite_structure_barrette_ohm', libelle: 'Continuité structure ↔ barrette (Ω)', genre: 'nombre' },
  { cle: 'date_continuite_structure_barrette', libelle: 'Date de cette mesure (AAAA-MM-JJ)', genre: 'date' },
  { cle: 'continuite_barrette_coffrets_ohm', libelle: 'Continuité barrette ↔ coffrets (Ω)', genre: 'nombre' },
  { cle: 'date_continuite_barrette_coffrets', libelle: 'Date de cette mesure (AAAA-MM-JJ)', genre: 'date' },
]

const enTexte = (v) => (v === null || v === undefined ? '' : String(v))

const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** L'entrée stockée (GET) → l'état du formulaire (chaînes ; rien d'inventé). */
export function depuisEntree(entree) {
  const e = entree ?? {}
  const prot = estObjet(e.protections) ? e.protections : {}
  const terre = estObjet(e.terre) ? e.terre : {}
  const etat = {
    ecartes: (Array.isArray(prot.ecartes) ? prot.ecartes : [])
      .map((l) => ({ repere: enTexte(l?.repere), motif: enTexte(l?.motif) })),
    ajouts: (Array.isArray(prot.ajouts) ? prot.ajouts : [])
      .map((l) => ({
        repere: enTexte(l?.repere), designation: enTexte(l?.designation), calibre: enTexte(l?.calibre),
        quantite: enTexte(l?.quantite), motif: enTexte(l?.motif),
      })),
    terre: {},
    polystring: (Array.isArray(e.polystring) ? e.polystring : [])
      .map((g) => ({ mppt: enTexte(g?.mppt), pans: Array.isArray(g?.pans) ? g.pans.join(', ') : enTexte(g?.pans) })),
  }
  for (const { cle, genre } of TERRE_CHAMPS) {
    etat.terre[cle] = genre === 'bool' ? Boolean(terre[cle]) : enTexte(terre[cle])
  }
  return etat
}

const ligneVide = (ligne) => Object.values(ligne).every((v) => String(v).trim() === '')

function protectionsPosees(etat, entree) {
  const stocke = estObjet(entree?.protections) ? entree.protections : null
  const ecartes = etat.ecartes.filter((l) => !ligneVide(l))
    .map((l) => ({ repere: l.repere.trim(), motif: l.motif.trim() }))
  const ajouts = etat.ajouts.filter((l) => !ligneVide(l)).map((l) => {
    const ligne = { designation: l.designation.trim(), motif: l.motif.trim() }
    for (const cle of ['repere', 'calibre']) if (l[cle].trim() !== '') ligne[cle] = l[cle].trim()
    const quantite = nombreOuNull(l.quantite)
    if (quantite !== null) ligne.quantite = quantite
    return ligne
  })
  if (!stocke && ecartes.length === 0 && ajouts.length === 0) return undefined
  return { ...(stocke ?? {}), ecartes, ajouts }
}

function terrePosee(etat, entree) {
  const stocke = estObjet(entree?.terre) ? entree.terre : null
  const bloc = { ...(stocke ?? {}) }
  let pose = false
  for (const { cle, genre } of TERRE_CHAMPS) {
    const brut = etat.terre[cle]
    const v = genre === 'bool' ? (brut ? true : null)
      : genre === 'nombre' ? nombreOuNull(brut) : texteOuNull(brut)
    if (v !== null) { bloc[cle] = v; pose = true } else if (cle in bloc) {
      bloc[cle] = genre === 'bool' ? false : null
    }
  }
  return stocke || pose ? bloc : undefined
}

function polystringPose(etat, entree) {
  const groupes = etat.polystring.filter((g) => !ligneVide(g)).map((g) => ({
    mppt: nombreOuNull(g.mppt),
    pans: String(g.pans).split(/[,;]/).map((p) => p.trim()).filter(Boolean),
  }))
  if (groupes.length) return groupes
  return entree?.polystring != null ? null : undefined
}

/**
 * Le corps POSTÉ : seulement les trois décisions (la fusion par clé du serveur laisse le
 * reste de l'entrée intact). Un champ vidé vaut `null`, jamais 0 ; une décision jamais
 * prise et absente du stock n'est pas inventée.
 */
export function corpsDeDecisions(etat, entree) {
  const corps = {}
  const protections = protectionsPosees(etat, entree)
  if (protections !== undefined) corps.protections = protections
  const terre = terrePosee(etat, entree)
  if (terre !== undefined) corps.terre = terre
  const polystring = polystringPose(etat, entree)
  if (polystring !== undefined) corps.polystring = polystring
  return corps
}
