/**
 * L-ECO — lecture du bloc public `economies_periodes`.
 *
 * ORDRE FONDATEUR (24/08/2026) : sous le graphe « Sur une journée », le client
 * doit lire ce qu'il économise le JOUR TYPE affiché, le MOIS, l'ANNÉE, et en
 * combien d'années l'installation est remboursée — et ces valeurs doivent
 * suivre la puce de saison ET la puce de profil d'occupation.
 *
 * CE MODULE NE CALCULE RIEN. Il ne fait que LIRE et valider ce que le serveur
 * a déjà calculé (`apps/ventes/economies_periodes.py`) : pas une addition, pas
 * une division, pas un produit en croix. Règle « zéro chiffre inventé » — un
 * chiffre qui apparaît côté client sort du moteur, ou n'apparaît pas.
 *
 * Toute valeur absente/illisible fait DISPARAÎTRE la case concernée (jamais un
 * zéro, jamais un tiret présenté comme une donnée).
 */

/** Un montant servi par le moteur : un nombre fini, rien d'autre. */
function nombre(valeur: unknown): number | null {
  return typeof valeur === 'number' && Number.isFinite(valeur) ? valeur : null;
}

function texte(valeur: unknown): string | null {
  return typeof valeur === 'string' && valeur.trim() ? valeur : null;
}

export interface EcoMois {
  mois: number;
  jours: number;
  saison: string | null;
  mad: number;
  jourMad: number | null;
}

export interface EcoSaison {
  mad: number;
  jours: number;
  nbMois: number | null;
  jourMad: number | null;
  /** Économie d'un mois MOYEN de cette saison — servie, jamais divisée ici. */
  moisMoyenMad: number | null;
}

/** Une variante servie (sans batterie / avec batterie / un profil). */
export interface EcoVariante {
  annuelMad: number;
  mois: EcoMois[];
  saisons: Record<string, EcoSaison>;
  /** Absent quand le moteur n'a pas su calculer un retour — jamais « 0 an ». */
  retourInvestissementAns: number | null;
}

export interface EcoProfil {
  occupancy: string;
  estProfilReel: boolean;
  sans: EcoVariante;
  avec: EcoVariante | null;
}

export interface EconomiesPeriodes {
  devise: string;
  estimation: boolean;
  sans: EcoVariante;
  avec: EcoVariante | null;
  profils: EcoProfil[];
}

function parseMois(brut: unknown): EcoMois[] | null {
  if (!Array.isArray(brut) || brut.length !== 12) return null;
  const sortie: EcoMois[] = [];
  for (const item of brut) {
    if (!item || typeof item !== 'object') return null;
    const o = item as Record<string, unknown>;
    const mad = nombre(o.mad);
    const mois = nombre(o.mois);
    const jours = nombre(o.jours);
    if (mad === null || mois === null || jours === null) return null;
    sortie.push({
      mois,
      jours,
      saison: texte(o.saison),
      mad,
      jourMad: nombre(o.jour_mad),
    });
  }
  return sortie;
}

function parseSaisons(brut: unknown): Record<string, EcoSaison> {
  const sortie: Record<string, EcoSaison> = {};
  if (!brut || typeof brut !== 'object') return sortie;
  for (const [cle, valeur] of Object.entries(brut as Record<string, unknown>)) {
    if (!valeur || typeof valeur !== 'object') continue;
    const o = valeur as Record<string, unknown>;
    const mad = nombre(o.mad);
    const jours = nombre(o.jours);
    if (mad === null || jours === null) continue;
    sortie[cle] = {
      mad,
      jours,
      nbMois: nombre(o.nb_mois),
      jourMad: nombre(o.jour_mad),
      moisMoyenMad: nombre(o.mois_moyen_mad),
    };
  }
  return sortie;
}

function parseVariante(brut: unknown): EcoVariante | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const annuelMad = nombre(o.annuel_mad);
  const mois = parseMois(o.mois);
  if (annuelMad === null || mois === null) return null;
  const retour = nombre(o.retour_investissement_ans);
  return {
    annuelMad,
    mois,
    saisons: parseSaisons(o.saisons),
    // Le serveur OMET déjà un retour non calculé ; on refuse en plus tout
    // zéro/négatif qui aurait survécu : « remboursé en 0 an » est un mensonge.
    retourInvestissementAns: retour !== null && retour > 0 ? retour : null,
  };
}

function parseProfils(brut: unknown): EcoProfil[] {
  if (!Array.isArray(brut)) return [];
  const sortie: EcoProfil[] = [];
  for (const item of brut) {
    if (!item || typeof item !== 'object') continue;
    const o = item as Record<string, unknown>;
    const occupancy = texte(o.occupation);
    const sans = parseVariante(o.sans);
    if (!occupancy || !sans) continue;
    sortie.push({
      occupancy,
      estProfilReel: o.est_profil_reel === true,
      sans,
      avec: parseVariante(o.avec),
    });
  }
  return sortie;
}

/**
 * `null` quand le backend ne sert pas la clé (devis antérieur à cette couche,
 * section « économies » décochée, moteur sans ancrage réel) : le bandeau ne
 * s'affiche alors pas du tout, et la page reste exactement celle d'avant.
 */
export function economiesPeriodes(payload: unknown): EconomiesPeriodes | null {
  if (!payload || typeof payload !== 'object') return null;
  const brut = (payload as Record<string, unknown>).economies_periodes;
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const sans = parseVariante(o.sans);
  if (!sans) return null;
  return {
    devise: texte(o.devise) ?? 'MAD',
    estimation: o.estimation === true,
    sans,
    avec: parseVariante(o.avec),
    profils: parseProfils(o.profils),
  };
}

/**
 * La variante à montrer pour un profil donné : celle du profil quand le moteur
 * l'a servie, sinon celle du devis. JAMAIS un mélange — on ne montre pas le
 * jour type d'un comportement à côté de l'annuel d'un autre.
 */
export function varianteDuProfil(
  bloc: EconomiesPeriodes,
  occupancy: string | null,
  avecBatterie: boolean,
): EcoVariante | null {
  const profil = occupancy
    ? bloc.profils.find((p) => p.occupancy === occupancy)
    : undefined;
  const source = profil ?? bloc;
  return avecBatterie ? (source.avec ?? null) : source.sans;
}
