// ENF22 — helpers extraits de Raccordement.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/* ============================================================================
   CALX244 — L'ONGLET « RACCORDEMENT RÉSEAU » DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. Aucun écran du module ne demandait la
   puissance souscrite, le régime du branchement, la limite d'élévation de
   tension ni le cos φ imposé par le contrat de raccordement : les trois
   calculs existaient côté serveur (CALX241-243) et personne ne pouvait ni
   les nourrir ni les lire. Parité OpenSolar : les réglages de site se
   saisissent dans les détails du site et redescendent dans tous les
   contrôles.

   LA SOURCE EST `GET`/`POST calepinages/<pk>/raccordement/` (CALX205,
   contrat `calepinage_raccordement.json`), ajoutée EN FIN de
   `calepinageApi.js` (`// CALX244`). Le `POST` REND le raccordement
   recalculé : cet écran n'enchaîne donc aucun second appel.

   ZÉRO CHIFFRE INVENTÉ (D-CALX 7), DANS LES DEUX SENS. Les quatre grandeurs
   du bloc `calcul` sont recopiées telles quelles ; `null` n'est jamais rendu
   `0` (`formatNumber`/`formatPercent` rendent « — »). Les cinq verdicts sont
   lus PAR LEUR CODE, jamais par leur position — et un verdict `omis` affiche
   le MOTIF du serveur, jamais une pastille verte et jamais un chiffre qui
   ferait croire à un contrôle réussi.

   UNE LIMITE EST UNE SAISIE QUI PORTE SA SOURCE. `limite_elevation_pct` et
   `cos_phi_impose` exigent leur provenance : c'est le SERVEUR qui refuse (il
   est la seule autorité), et l'écran pose son message SOUS le champ qu'il
   NOMME, avec un bandeau qui y renvoie d'un clic (règle fondateur du
   08/09/2026 — jamais un « non enregistré » générique).
   ========================================================================== */

/** Le préfixe que le serveur met devant le champ fautif d'un refus. */
export const PREFIXE_CHAMP = 'raccordement.'

/** Les neuf champs de la saisie, dans l'ordre où l'écran les demande. */
export const CHAMPS = [
  {
    cle: 'puissance_souscrite_kva',
    libelle: 'Puissance souscrite',
    unite: 'kVA',
    aide: 'Celle du contrat de raccordement. Laissez vide tant qu’elle n’est pas connue — rien n’est supposé.',
  },
  {
    cle: 'phases',
    libelle: 'Phases du branchement',
    unite: '1 ou 3',
    aide: 'Monophasé (1) ou triphasé (3). Aucun régime n’est deviné.',
  },
  {
    cle: 'tension_nominale_v',
    libelle: 'Tension nominale',
    unite: 'V',
    aide: 'Celle du compteur. Ni 230 V ni 400 V ne sont supposés.',
  },
  {
    cle: 'limite_elevation_pct',
    libelle: 'Limite d’élévation de tension',
    unite: '%',
    aide: 'Aucun barème marocain n’est présent dans ce dépôt : sans limite saisie, l’élévation est publiée mais aucun verdict n’est prononcé.',
  },
  {
    cle: 'source_limite',
    libelle: 'Source de la limite',
    unite: '',
    texte: true,
    aide: 'Le texte réglementaire ou le contrat qui fixe la limite. Obligatoire dès qu’une limite est saisie.',
  },
  {
    cle: 'cos_phi_impose',
    libelle: 'Cos φ imposé',
    unite: '',
    simulation: true, // ACAL156 — lu par la simulation (autoconsommation, batterie)
    aide: 'Celui que le contrat de raccordement de CE site impose — à ne pas confondre avec le réglage société « cos φ retenu à défaut de mesure ».',
  },
  {
    cle: 'source_cos_phi',
    libelle: 'Source du cos φ',
    unite: '',
    texte: true,
    aide: 'Le contrat de raccordement ou la prescription du gestionnaire de réseau. Obligatoire dès qu’un cos φ est saisi.',
  },
  // ACAL9 — les deux champs du plafond d'injection (lus par les étapes
  // autoconsommation et batterie) : un plafond est une saisie qui porte sa
  // justification, refusée par le SERVEUR sans elle.
  {
    cle: 'plafond_injection_kw',
    libelle: 'Plafond d’injection',
    unite: 'kW',
    simulation: true, // ACAL156 — lu par la simulation (autoconsommation, batterie)
    aide: 'Le plafond d’injection au réseau imposé à ce site. Laissez vide tant qu’il n’est pas connu — rien n’est supposé.',
  },
  {
    cle: 'plafond_injection_justification',
    libelle: 'Justification du plafond',
    unite: '',
    texte: true,
    aide: 'Le contrat de raccordement ou la prescription du gestionnaire de réseau qui impose le plafond. Obligatoire dès qu’un plafond est saisi.',
  },
]

/** Le libellé FRANÇAIS de chaque statut publié par le contrat. */
export const LIBELLES_STATUT = {
  ok: 'Conforme',
  alerte: 'À surveiller',
  bloquant: 'Bloquant',
  omis: 'Non vérifié',
}

/** Le ton du badge — `omis` est NEUTRE : ce n'est pas un contrôle réussi. */
export const TONS_STATUT = {
  ok: 'success',
  alerte: 'warning',
  bloquant: 'danger',
  omis: 'neutral',
}

/** Le libellé d'un statut — un statut inconnu est NOMMÉ, jamais tu. */
export function libelleStatut(statut) {
  return LIBELLES_STATUT[statut] ?? `statut « ${statut} »`
}

/**
 * Les erreurs du serveur, rangées PAR CHAMP : `{ 'raccordement.source_limite':
 * '…' }` devient `{ source_limite: '…' }`. Une clé sans préfixe (refus
 * générique) est conservée telle quelle — elle s'affiche alors en bandeau
 * seul, jamais avalée.
 */
export function erreursParChamp(donnees) {
  const par = {}
  if (!donnees || typeof donnees !== 'object') return par
  for (const [cle, message] of Object.entries(donnees)) {
    const champ = cle.startsWith(PREFIXE_CHAMP)
      ? cle.slice(PREFIXE_CHAMP.length)
      : cle
    par[champ] = Array.isArray(message) ? message.join(' ') : String(message)
  }
  return par
}

/**
 * Le corps POSTÉ : les NEUF champs, un champ vidé valant `null` (« pas
 * saisi »), jamais `0` ni une chaîne vide qui se lirait comme une valeur.
 */
export function corpsDeSaisie(saisie) {
  const corps = {}
  for (const { cle } of CHAMPS) {
    const valeur = saisie?.[cle]
    corps[cle] = valeur === '' || valeur === undefined ? null : valeur
  }
  return corps
}

/**
 * ACAL158 — la saisie est-elle VIDE (ni puissance souscrite ni phases) ? Seule une saisie
 * vide laisse reprendre les valeurs du lead : une saisie enregistrée n'est jamais écrasée.
 */
export function saisieVide(saisie) {
  const vide = (v) => v === null || v === undefined || v === ''
  return vide(saisie?.puissance_souscrite_kva) && vide(saisie?.phases)
}
