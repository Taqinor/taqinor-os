/**
 * Régimes de la loi 82-21 (autoproduction d'énergie électrique),
 * décret d'application 2-25-100 — en vigueur depuis le 9 juin 2026.
 *
 *  - déclaration : < 11 kW en basse tension, ou installation non raccordée
 *    au réseau (site isolé) ;
 *  - accord de raccordement : du seuil de déclaration jusqu'à 5 MW (BT/MT) ;
 *  - autorisation : ≥ 5 MW (MT/HT/THT).
 */
export type Voltage = 'BT' | 'MT' | 'HT';
export type RegimeId = 'declaration' | 'accord' | 'autorisation';

export interface RegimeInput {
  powerKw: number;
  gridConnected: boolean;
  voltage: Voltage;
}

export const AUTORISATION_THRESHOLD_KW = 5000; // 5 MW
export const DECLARATION_BT_MAX_KW = 11;

export function determineRegime(input: RegimeInput): RegimeId {
  if (!input.gridConnected) return 'declaration';
  if (input.powerKw >= AUTORISATION_THRESHOLD_KW) return 'autorisation';
  if (input.voltage === 'BT' && input.powerKw < DECLARATION_BT_MAX_KW) return 'declaration';
  return 'accord';
}

export interface RegimeInfo {
  id: RegimeId;
  title: string;
  summary: string;
  obligations: string[];
}

export const REGIMES: Record<RegimeId, RegimeInfo> = {
  declaration: {
    id: 'declaration',
    title: 'Régime de déclaration',
    summary:
      'Installations de moins de 11 kW raccordées en basse tension, ou installations non raccordées au réseau (sites isolés). Une déclaration préalable suffit.',
    obligations: [
      'Déposer une déclaration avant la mise en service',
      'Respecter les prescriptions techniques de raccordement (si raccordé)',
      'Conserver l’accusé de dépôt de la déclaration',
    ],
  },
  accord: {
    id: 'accord',
    title: 'Régime de l’accord de raccordement',
    summary:
      'Installations raccordées au réseau, du seuil de déclaration jusqu’à 5 MW, en basse ou moyenne tension. Un accord de raccordement avec le gestionnaire de réseau est requis avant la mise en service.',
    obligations: [
      'Obtenir l’accord de raccordement du gestionnaire de réseau avant mise en service',
      'Installer un dispositif de comptage conforme',
      'Respecter les conditions techniques de l’accord (puissance injectée, protections)',
    ],
  },
  autorisation: {
    id: 'autorisation',
    title: 'Régime d’autorisation',
    summary:
      'Installations de 5 MW et plus, raccordées en moyenne, haute ou très haute tension. Une autorisation préalable est exigée.',
    obligations: [
      'Obtenir l’autorisation avant tout démarrage des travaux',
      'Constituer un dossier technique complet (étude de raccordement, schémas, conformité)',
      'Se conformer au suivi et au contrôle de l’ANRE',
    ],
  },
};
