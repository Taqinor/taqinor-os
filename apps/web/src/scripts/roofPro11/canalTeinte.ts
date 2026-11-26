// Demande croisée (ACAL1621) — le canal de teinte des panneaux du pan actif (tampon `instanceColor`, scene3d.ts) a deux
// sources : la carte d'accès solaire (allumée par l'utilisateur ou le temps de « Joindre la carte de chaleur ») et la
// teinte par chaîne (table servie). Tant que la carte d'accès est allumée, elle passe AVANT les chaînes — y compris
// quand le maillage est reconstruit ; éteinte, les chaînes reviennent (sinon la teinte d'origine).
// LOT 6 — une cellule peut rendre `null` : la scène y écrit sa teinte d'origine (un module sans mesure n'est pas teinté).
export type CouleurDe = ((cellIndex: number) => { r: number; g: number; b: number } | null) | null;

export function creerCanalTeinte(ecrire: (couleur: CouleurDe) => void) {
  let acces: CouleurDe = null;
  return {
    /** Carte d'accès allumée (`fn`) ou éteinte (`null`) ; éteinte, la teinte des chaînes (`chaines()`) revient. */
    acces(fn: CouleurDe, chaines: () => CouleurDe): void {
      acces = fn;
      ecrire(fn ?? chaines());
    },
    /** Teinte par chaîne (ou maillage reconstruit) : la carte d'accès, allumée, passe avant. */
    chaines(fn: CouleurDe): void {
      ecrire(acces ?? fn);
    },
    accesActive: (): boolean => acces != null,
  };
}
