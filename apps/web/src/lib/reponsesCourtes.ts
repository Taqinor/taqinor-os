/**
 * WAUD77 — « Réponse courte » citable en tête des pages pilier. Chaque chiffre est importé de sa
 * constante source (jamais retapé). Le pilier prix n'en porte PAS : tant que lib/prixConstants.ts
 * n'existe pas (D-WAUD-5 / WAUD68), le bloc prix reste omis plutôt qu'avec un montant non sourcé.
 */
import { AUTORISATION_THRESHOLD_KW, DECLARATION_BT_MAX_KW } from './regime';
import {
  BATTERY_CAPACITY_FLOOR_PCT,
  BATTERY_WARRANTY_YEARS,
  DEYE_INVERTER_WARRANTY_YEARS,
  HUAWEI_INVERTER_WARRANTY_YEARS,
  INSTALL_WARRANTY_YEARS,
  PANEL_PERFORMANCE_FLOOR_FR,
  PANEL_PERFORMANCE_WARRANTY_YEARS,
  PANEL_PRODUCT_WARRANTY_YEARS,
  STRUCTURE_WARRANTY_YEARS,
} from './warranty';
import { FDA_PLAFOND_PAR_HA_DH, FDA_PLAFOND_PAR_KWC_DH, FDA_PLAFOND_PAR_PROJET_DH, FDA_TAUX_PCT } from './subventionFacts';

const fr = (n: number) => n.toLocaleString('fr-FR');

export type ReponseCourteId = 'loi8221' | 'garanties' | 'pompage';

export const REPONSES_COURTES: Record<ReponseCourteId, string> = {
  loi8221: `En basse tension, une installation de moins de ${DECLARATION_BT_MAX_KW} kW relève de la déclaration ; à partir de ${DECLARATION_BT_MAX_KW} kW (ou en moyenne tension) elle relève d’un accord de raccordement ; l’autorisation commence à ${fr(AUTORISATION_THRESHOLD_KW / 1000)} MW.`,
  garanties: `Panneaux : ${PANEL_PRODUCT_WARRANTY_YEARS} ans produit et ${PANEL_PERFORMANCE_WARRANTY_YEARS} ans de performance linéaire (${PANEL_PERFORMANCE_FLOOR_FR} à ${PANEL_PERFORMANCE_WARRANTY_YEARS} ans) ; onduleurs : ${DEYE_INVERTER_WARRANTY_YEARS} ans (hybrides Deye) ou ${HUAWEI_INVERTER_WARRANTY_YEARS} ans (réseau Huawei) ; batteries Dyness : ${BATTERY_WARRANTY_YEARS} ans, ≥ ${BATTERY_CAPACITY_FLOOR_PCT} % de capacité ; structure : ${STRUCTURE_WARRANTY_YEARS} ans ; pose : ${INSTALL_WARRANTY_YEARS} ans.`,
  pompage: `Le pompage solaire se dimensionne sur votre HMT et votre débit souhaité. Règle de l’aide FDA : ${FDA_TAUX_PCT} % de l’investissement, plafonnée à ${fr(FDA_PLAFOND_PAR_HA_DH)} DH par hectare, ${fr(FDA_PLAFOND_PAR_KWC_DH)} DH par kWc et ${fr(FDA_PLAFOND_PAR_PROJET_DH)} DH par projet, avec accord préalable avant travaux ; décision de la DPA/ORMVA, non garantie.`,
};
