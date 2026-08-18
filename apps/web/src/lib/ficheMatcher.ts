/**
 * WJ131 — APPARIEMENT « ligne de devis → fiche technique ».
 *
 * Le tableau « Ce qui sera posé chez vous » de la proposition liste les lignes
 * du devis telles que le backend les nomme (« Panneau CANADIAN SOLAR 710W »,
 * « Tableau De Protection AC/DC », « Accessoires »…). Ce module PUR décide, à
 * partir de la seule désignation (+ la marque quand le devis la porte), vers
 * quelle fiche `/produits/<slug>` cette ligne renvoie — ou vers AUCUNE.
 *
 * DEUX RÈGLES DURES, dans cet ordre :
 *
 *  1. JAMAIS LA MAUVAISE MARQUE. Une fiche marquée (Canadian Solar, Jinko,
 *     Huawei, Deye, Dyness) n'est liée que si la ligne porte SA marque. Un
 *     « panneau 710 Wc » sans marque connue ne devient pas un Canadian Solar
 *     par défaut : il ne reçoit aucun lien. Symétriquement, une ligne qui cite
 *     une marque CONCURRENTE connue coupe le lien même si le contexte colle
 *     (« onduleur hybride Growatt » ne renvoie pas vers la fiche Deye).
 *
 *  2. AUCUNE CORRESPONDANCE → `null`. Le tableau n'affiche alors simplement pas
 *     de lien pour cette ligne : rien n'est inventé, rien ne casse.
 *
 * Les deux postes GÉNÉRIQUES du devis (« Tableau De Protection AC/DC » et
 * « Accessoires ») pointent vers des fiches EXPLICATIVES sans marque : le
 * client comprend enfin à quoi sert la ligne qu'il paie.
 *
 * Le module ne connaît que des chaînes : il n'importe pas `fiches.ts` (aucun
 * cycle, aucun coût au rendu). L'existence RÉELLE de chaque slug retourné est
 * verrouillée par `tests/ficheMatcherWJ131.test.ts`, qui importe le vrai
 * catalogue — renommer une fiche sans toucher ce module casse le test.
 */

/**
 * Normalise un libellé : minuscules, accents retirés, toute ponctuation
 * ramenée à un espace (« Tableau De Protection AC/DC » → « tableau de
 * protection ac dc »). Les variantes d'écriture du Wi-Fi sont recollées pour
 * qu'un seul mot-clé les couvre toutes.
 */
function normaliser(valeur: string | null | undefined): string {
  return String(valeur ?? '')
    .normalize('NFD')
    // Marques diacritiques combinantes que NFD vient de détacher des lettres.
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\bwi fi\b/g, 'wifi')
    .trim();
}

/** Échappement pour insérer un mot-clé littéral dans une expression régulière. */
function echapper(motif: string): string {
  return motif.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Le libellé contient-il ce mot-clé ? Le test se fait sur des FRONTIÈRES DE MOT
 * pour qu'un token court ne se cache pas dans un autre mot (« sma » ne doit
 * jamais matcher « smart meter »). Un mot-clé terminé par `*` accepte les
 * suffixes (« accessoire* » couvre accessoire ET accessoires).
 */
function contient(libelle: string, motCle: string): boolean {
  const prefixe = motCle.endsWith('*');
  const racine = echapper(prefixe ? motCle.slice(0, -1) : motCle);
  return new RegExp(prefixe ? `\\b${racine}` : `\\b${racine}\\b`).test(libelle);
}

function contientUn(libelle: string, motsCles: readonly string[]): boolean {
  return motsCles.some((m) => contient(libelle, m));
}

/**
 * Marques réellement croisées sur ce marché (les nôtres + les concurrentes les
 * plus courantes au Maroc). Sert UNIQUEMENT de garde-fou « mauvaise marque » :
 * une marque de cette liste absente des marques acceptées par la règle annule
 * le lien. Une marque inconnue de la liste ne déclenche rien — le garde-fou ne
 * ment jamais dans l'autre sens.
 */
// « deyness » = ANCIENNE faute d'orthographe de Dyness (corrigée au catalogue le
// 2026-08-18) : elle reste listée ici et dans la règle `batterie-dyness` parce que
// les désignations FIGÉES des devis déjà émis arrivent encore avec cette graphie
// via la proposition — elles doivent continuer d'être appariées à la bonne fiche.
const MARQUES_CONNUES: readonly string[] = [
  'canadian', 'jinko', 'huawei', 'deye', 'dyness', 'deyness',
  'growatt', 'sma', 'fronius', 'solis', 'sungrow', 'goodwe', 'chint',
  'longi', 'trina', 'ja solar', 'risen', 'astronergy',
  'pylontech', 'byd', 'victron', 'felicity',
  'hoymiles', 'enphase', 'solaredge', 'tigo', 'veichi',
];

interface RegleFiche {
  slug: string;
  /** Le TYPE de poste (au moins un mot doit être présent). */
  contexte: readonly string[];
  /**
   * Qualificatif exigé EN PLUS du contexte (marque, topologie…). `null` quand le
   * contexte suffit à lui seul.
   */
  qualificatif: readonly string[] | null;
  /**
   * Marques acceptées par cette fiche (tokens normalisés). `null` = fiche
   * GÉNÉRIQUE, sans marque : aucun garde-fou de marque ne s'applique (un
   * coffret de n'importe quelle marque mérite l'explication du coffret).
   */
  marques: readonly string[] | null;
}

/**
 * ORDRE VOLONTAIRE, du plus spécifique au plus générique — même logique que le
 * classement en familles de `propositionPage.classifyEquipment` : la PROTECTION
 * est testée avant la production, parce qu'un « coffret DC pour onduleur »
 * contient aussi un mot de production, et le poste le plus précis doit gagner.
 * Le câblage ferme la marche : c'est le filet, jamais le premier filtre.
 */
const REGLES: readonly RegleFiche[] = [
  {
    // « Tableau De Protection AC/DC », « Coffret AC », « Parafoudre DC »…
    slug: 'tableau-protection-ac-dc',
    contexte: [
      'tableau*', 'coffret*', 'parafoudre*', 'sectionneur*', 'disjoncteur*', 'differentiel*',
    ],
    qualificatif: null,
    marques: null,
  },
  {
    slug: 'batterie-dyness',
    contexte: ['batterie', 'batteries', 'stockage'],
    qualificatif: ['dyness', 'deyness'],
    marques: ['dyness', 'deyness'],
  },
  {
    slug: 'onduleur-deye-hybride',
    contexte: ['onduleur', 'onduleurs'],
    qualificatif: ['hybride', 'deye'],
    marques: ['deye'],
  },
  {
    slug: 'onduleur-huawei-reseau',
    contexte: ['onduleur', 'onduleurs'],
    qualificatif: ['reseau', 'injection', 'huawei', 'sun2000'],
    marques: ['huawei'],
  },
  {
    slug: 'canadian-solar-710',
    contexte: ['panneau', 'panneaux', 'module', 'modules', 'photovoltaique'],
    qualificatif: ['canadian'],
    marques: ['canadian'],
  },
  {
    slug: 'jinko-710',
    contexte: ['panneau', 'panneaux', 'module', 'modules', 'photovoltaique'],
    qualificatif: ['jinko'],
    marques: ['jinko'],
  },
  {
    slug: 'smart-meter-huawei',
    contexte: ['smart meter', 'smartmeter', 'compteur intelligent', 'compteur communicant', 'dtsu666'],
    qualificatif: null,
    marques: ['huawei'],
  },
  {
    slug: 'wifi-dongle-huawei',
    contexte: ['wifi', 'dongle', 'wlan'],
    qualificatif: null,
    marques: ['huawei'],
  },
  {
    // Filet du câblage : « Accessoires », « Câblage solaire », « Connecteurs MC4 »…
    slug: 'accessoires-cablage',
    contexte: [
      'accessoire*', 'cablage', 'connecteur*', 'mc4', 'goulotte*',
      'presse etoupe*', 'chemin de cable*', 'gaine*', 'cable solaire*',
    ],
    qualificatif: null,
    marques: null,
  },
];

/**
 * Slug de fiche technique pour une ligne d'équipement — ou `null` si rien ne
 * correspond avec certitude (cas NORMAL et sans conséquence : la ligne
 * s'affiche simplement sans lien).
 *
 * @param designation Le libellé de la ligne, tel que le devis le porte.
 * @param marque      La marque de la ligne quand le devis la renseigne : elle
 *                    est lue AU MÊME TITRE que la désignation, ce qui rattrape
 *                    « Panneau 710 Wc » + marque « Canadian Solar ».
 */
export function ficheSlugPourLigne(
  designation: string | null | undefined,
  marque?: string | null,
): string | null {
  const libelle = normaliser(`${designation ?? ''} ${marque ?? ''}`);
  if (!libelle) return null;

  for (const regle of REGLES) {
    if (!contientUn(libelle, regle.contexte)) continue;
    if (regle.qualificatif && !contientUn(libelle, regle.qualificatif)) continue;

    // Garde-fou « jamais la mauvaise marque » : une fiche MARQUÉE refuse toute
    // ligne qui cite une autre marque connue. On s'arrête net plutôt que de
    // glisser vers une règle voisine — une ligne ambiguë ne mérite aucun lien.
    if (regle.marques) {
      const acceptees = regle.marques;
      const intruse = MARQUES_CONNUES.some(
        (m) => !acceptees.includes(m) && contient(libelle, m),
      );
      if (intruse) return null;
    }
    return regle.slug;
  }
  return null;
}
