// Copilote vague 2 (FND10) — LE registre des composants de carte (clé de
// `registry.CARTES` côté Django -> composant). Une clé absente d'ici (réservée au
// registre, composant pas encore livré) tombe sur la carte générique. Les cartes
// des modules de la vague 2 vivent chacune dans SON fichier `modules/Cartes<Module>.jsx`
// (une lane de cartes ne touche que le sien) ; ce fichier les importe une fois pour toutes.
import CarteTouche from './CarteTouche'
import {
  CarteFileTouches, CarteMatin, CarteListeLeads, CarteFicheLead, CarteSuiteTouche,
} from './CartesCrm'
import {
  CarteWaMessage, CarteWaDevis, CarteDocument, CarteVisite,
} from './CartesWhatsApp'
import CarteDiagnostic from './CarteDiagnostic'
import CarteDevisCree from './CarteDevisCree'
import CarteLienEcran from './CarteLienEcran'
import CartesTaches from '../../taches/cartes/CartesTaches'
import CARTES_CALEPINAGE from './modules/CartesCalepinage'
import CARTES_VISITES from './modules/CartesVisites'
import CARTES_CHANTIERS from './modules/CartesChantiers'
import CARTES_VENTES from './modules/CartesVentes'
import CARTES_STOCK from './modules/CartesStock'
import CARTES_SAV from './modules/CartesSav'
import CARTES_REPORTING from './modules/CartesReporting'

const TACHES = [
  'ma_journee', 'plan_propose', 'liste_taches', 'tache', 'capture_apercu', 'rythme',
  'plan_projet', 'projet', 'revue_semaine', 'priorites', 'point',
]

export const COMPOSANTS = Object.freeze({
  touche: CarteTouche,
  suite_touche: CarteSuiteTouche,
  file_touches: CarteFileTouches,
  matin: CarteMatin,
  liste_leads: CarteListeLeads,
  fiche_lead: CarteFicheLead,
  wa_message: CarteWaMessage,
  wa_devis: CarteWaDevis,
  document: CarteDocument,
  devis_cree: CarteDevisCree,
  visite: CarteVisite,
  diagnostic: CarteDiagnostic,
  lien_ecran: CarteLienEcran,
  // Tâches (TCH118) : une même vue, la clé de la carte choisit son rendu.
  ...Object.fromEntries(TACHES.map((cle) => [cle, CartesTaches])),
  ...CARTES_CALEPINAGE,
  ...CARTES_VISITES,
  ...CARTES_CHANTIERS,
  ...CARTES_VENTES,
  ...CARTES_STOCK,
  ...CARTES_SAV,
  ...CARTES_REPORTING,
})

/** Cartes que l'écran sait rendre — DÉRIVÉES des composants enregistrés (la
 *  liste ne peut plus diverger d'eux). Toute autre valeur — ou `null` — tombe
 *  sur la carte générique. */
export const CARTES_CONNUES = Object.freeze(Object.keys(COMPOSANTS))
