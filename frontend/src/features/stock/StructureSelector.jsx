/* ── STKCAT10 — LE SÉLECTEUR DE STRUCTURES, PILOTÉ PAR LE CATALOGUE ─────────
   Décision fondateur du 16/09/2026 (audit L3 stock ↔ CRM ↔ devis, « Pergola
   introuvable ») : le bouton acier / aluminium est REMPLACÉ par un sélecteur
   ouvert sur TOUTES les structures typées de la société — celles
   d'aujourd'hui ET celles de demain. Aucune liste de structures n'est écrite
   dans le code : les règles d'éligibilité et de tri vivent dans
   `structures.js` (moitié pure), ce fichier n'a que le rendu.

   REPLI — « le sélecteur ne peut jamais naître vide » : une société dont
   AUCUNE catégorie n'est typée `structure` (ou dont aucune structure n'est
   tarifée) reçoit le `fallback` que l'appelant fournit — le bouton acier /
   aluminium d'hier, au caractère près. Aucun écran ne perd son contrôle.

   CATALOGUE : `produits` fourni (tableau) ⇒ composant PUR, zéro réseau —
   c'est le chemin du générateur de devis, qui a déjà chargé le catalogue.
   `produits` absent ⇒ le composant va le chercher LUI-MÊME, une seule fois
   par session d'écran (promesse mémorisée au niveau module, partagée par
   toutes les instances) — c'est le chemin de la fiche lead (CRM), où la
   section « Toiture & site » reste purement présentationnelle, exactement
   comme `TraceToitClient` y demande déjà la photo du toit au serveur. Un
   échec réseau DÉGRADE (on retombe sur le `fallback`), il ne casse jamais
   l'écran. */
import { useEffect, useState } from 'react'
import { FormField } from '../../ui'
import { groupesStructures } from './structures'
import stockApi from '../../api/stockApi'
import { fetchAllPages } from '../../utils/fetchAllPages'

/* Promesse MÉMORISÉE au niveau module : plusieurs sélecteurs montés dans la
   même session d'écran partagent UN seul aller-retour réseau (même patron que
   le chargement paresseux du catalogue dans `DevisTab`). Un échec rend un
   tableau vide — le sélecteur retombe sur son repli, jamais une exception. */
let catalogueEnVol = null
function chargerCatalogueStructures() {
  if (!catalogueEnVol) {
    catalogueEnVol = fetchAllPages(
      (page) => stockApi.getProduits({ page }).then((r) => r.data),
    ).then((liste) => (Array.isArray(liste) ? liste : [])).catch(() => [])
  }
  return catalogueEnVol
}

/**
 * Sélecteur de structure.
 *
 * @param {object[]} [produits]  Catalogue déjà chargé. Absent ⇒ le composant
 *                               le charge lui-même (voir l'entête).
 * @param {string|number} value  Id du produit choisi ('' = aucune structure).
 * @param {function} onChange    Reçoit l'id choisi (chaîne, '' si aucune).
 * @param {node}     fallback    Rendu À LA PLACE quand la société n'a AUCUNE
 *                               structure éligible (le bouton acier/alu).
 */
export default function StructureSelector({
  produits, value, onChange, fallback = null,
  id = 'structure-produit', label = 'Type de structure',
  error, className, 'data-testid': dataTestId,
}) {
  const fourni = Array.isArray(produits)
  const [charge, setCharge] = useState(null)
  useEffect(() => {
    if (fourni) return undefined
    let vivant = true
    chargerCatalogueStructures().then((liste) => { if (vivant) setCharge(liste) })
    return () => { vivant = false }
  }, [fourni])

  const groupes = groupesStructures(fourni ? produits : charge)
  // REPLI — jamais un sélecteur vide : l'écran garde le contrôle d'hier.
  if (!groupes.length) return fallback

  return (
    <FormField label={label} htmlFor={id} error={error} className={className}>
      <select
        id={id}
        className={error ? 'form-select is-invalid' : 'form-select'}
        aria-invalid={error ? true : undefined}
        data-testid={dataTestId}
        value={value == null ? '' : String(value)}
        onChange={(e) => onChange?.(e.target.value)}
      >
        <option value="">Aucune structure</option>
        {groupes.map((g) => (
          <optgroup key={g.categorie} label={g.categorie}>
            {g.items.map((p) => (
              <option key={p.id} value={String(p.id)}>{p.nom}</option>
            ))}
          </optgroup>
        ))}
      </select>
    </FormField>
  )
}
