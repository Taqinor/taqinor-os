// SONDE = {constat: "C-AGNR-VER-005", sha: "5093a9913",
//   attendu: "le chargeur ?edit= (useChargeurEdition.js:84, sans `produits`) rouvre 12 × « Modules toiture sud » liés à un produit panneau à 12 panneaux, comme lignes_classement.panneaux_et_watt_lu"}
// Sonde Node (fonctions pures). Sortie 0 = REPRO (compte du chargeur réel ≠ compte serveur), 1 = non reproduit.
import { devisVersEtat } from '../../../../frontend/src/features/ventes/quote/etatDevis.js'

const l = (id, des, q, produit) => ({ id, produit, designation: des, quantite: String(q), prix_unitaire: '1000.00',
  taux_tva: '20.00', ordre: id, type_ligne: 'produit', optionnelle: false, variante: '' })
const devis = { id: 1, mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0', etude_params: {},
  lignes: [l(1, 'Modules toiture sud', 12, 7)] }
const serveur = 12 // _is_panel(designation, produit.nom='Panneau Jinko 550W') ⇒ 12 (lignes_classement.py:365-387)
const chargeur = devisVersEtat(devis, { bareme: null }).panneaux // appel exact de useChargeurEdition.js:84
console.log(`chargeur ?edit= : ${chargeur} panneaux ; serveur : ${serveur}`)
const repro = chargeur !== serveur
console.log(`verdict : ${repro ? 'REPRO' : 'NON REPRODUIT'}`)
process.exit(repro ? 0 : 1)
