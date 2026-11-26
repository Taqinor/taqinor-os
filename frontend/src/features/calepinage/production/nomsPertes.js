/* Les noms EN CLAIR des pertes de la chaîne (maquettes Resultats / ResultatsIncomplet : « Poussière
   sur les panneaux », « Vieillissement de la première année »…). Le serveur ne sert que le terme
   technique (`cascade.etapes[].libelle`, `cascade.a_renseigner.lignes[].libelle`, ex. « Salissure »,
   « LID (première exposition) ») ; cette table — UNE seule, clé = `etape` de la chaîne — donne le mot
   simple. Le terme technique reste lisible en infobulle (`title`). Une clé inconnue garde le libellé
   servi : jamais un nom inventé. Utilisée partout dans l'étape Résultats qui nomme une perte. */

export const NOMS_PERTES = {
  horizon: 'Relief et horizon au loin',
  ombrage_proche: 'Ombres proches',
  acces_module: 'Soleil reçu par chaque panneau',
  ombrage_diffus: 'Ombre sur la lumière du ciel',
  inter_rangees: 'Ombre entre les rangées',
  bifacial: 'Gain de la face arrière',
  iam: 'Reflet sur la vitre des panneaux',
  spectral: 'Couleur de la lumière',
  salissure: 'Poussière sur les panneaux',
  neige: 'Neige sur les panneaux',
  niveau_irradiance: 'Lumière faible',
  thermique: 'Chaleur des panneaux',
  qualite_module: 'Qualité des panneaux',
  lid: 'Vieillissement de la première année',
  mismatch_fabricant: 'Écarts entre panneaux',
  mismatch_ombrage: 'Écarts entre panneaux dus à l’ombre',
  diodes: 'Diodes de chaîne',
  optimiseur: 'Optimiseurs de puissance',
  ohmique_dc: 'Câbles en courant continu',
  mppt: 'Plage de tension de l’onduleur',
  onduleur: 'Rendement de l’onduleur',
  ecretage: 'Plafond de l’onduleur',
  ohmique_ac: 'Câbles en courant alternatif',
  transformateur: 'Transformateur',
  auxiliaires: 'Équipements de l’installation',
  indisponibilite: 'Pannes et arrêts',
}

/** `{nom, technique}` : le mot simple de la perte `etape`, et le terme servi (pour l'infobulle, ou `''`
    quand il n'apporte rien). Clé inconnue : le libellé servi, sans infobulle. */
export function nomDePerte(etape, libelleServi = '') {
  const clair = NOMS_PERTES[etape]
  if (!clair) return { nom: libelleServi || etape || '', technique: '' }
  return { nom: clair, technique: libelleServi && libelleServi !== clair ? libelleServi : '' }
}

/* « Pour un résultat complet » AVANT toute simulation : le serveur sert `parcours.manque[]` (code, message,
   cible, nombre) ; le message est une phrase d'ingénieur (normes, « OMIS »…). UNE table, clé = `code` de
   `parcours_guide.MOTIFS`, donne le titre simple, une ligne claire et le mot du bouton ; la phrase servie
   reste derrière le « ? ». Code inconnu : le message servi sert de titre, sans ligne — rien n'est perdu. */
export const MANQUES_CLAIRS = {
  norme_absente: { titre: 'Choisir la norme électrique de votre société', ligne: 'Sans elle, les câbles, les chutes de tension et les protections ne sont pas calculés.' },
  simulation_perimee: { titre: 'Calcul à refaire', ligne: 'Le calepinage ou un réglage de votre société a changé depuis le dernier calcul.', bouton: 'Voir' },
  production_non_simulee: { titre: 'Production à calculer', ligne: 'Lancez la simulation pour la connaître.', bouton: 'Voir' },
  coefficients_non_sources: { titre: 'Températures de référence', ligne: 'Des valeurs standard servent en attendant celles du site.' },
  // R5B-N5 (rejeu 26/11) — la cible servie de ces deux lignes est l'onglet Production, l'écran même où on lit la ligne :
  // « Renseigner » ne faisait rien de visible. L'ombre par panneau se calcule à l'étape Panneaux (carte « Ensoleillement de
  // chaque panneau », allumée à l'entrée, ACAL1981) : le bouton y mène (`etape`).
  acces_solaire_absent: { titre: 'Ombrage panneau par panneau', ligne: 'Aucune ombre n’est signalée, mais cela ne prouve pas qu’il n’y en a pas.', bouton: 'Voir les ombres', etape: 'panneaux' },
  // Item 14 (T4-U1-023) — des obstacles / voisins hauts sont posés : la phrase SERVIE les nomme et dit le geste.
  ombres_non_mesurees: (m) => ({ titre: 'Ombres à compter sur les panneaux', ligne: m?.message || 'Des objets font de l’ombre : leur ombre n’est pas encore comptée.', bouton: 'Voir les ombres', etape: 'panneaux' }),
  ratio_dc_ac: { titre: 'Rapport panneaux / onduleur', ligne: 'À vérifier dans l’étape Électrique.' },
  longueur_chaine: { titre: 'Longueur des chaînes de panneaux', ligne: 'À vérifier dans l’étape Électrique.' },
  reglage_manquant: { titre: 'Réglage de la société à saisir', ligne: 'Nécessaire au calcul.' },
  // T4-B4-007 — les codes de l'étape Électrique servis avant toute simulation : une phrase d'utilisateur qui NOMME
  // ce qui est à compléter et dit le geste ; la phrase servie (d'ingénieur) reste derrière le « ? ».
  verdict_electrique: { titre: 'À compléter : le verdict électrique', ligne: 'Terminez l’étape Électrique : le raccordement y est vérifié.' },
  materiel_designe: (m) => {
    const module = /module/i.test(m?.message || '')
    const onduleur = /onduleur/i.test(m?.message || '')
    const quoi = module && onduleur ? 'le panneau et l’onduleur' : (onduleur ? 'l’onduleur' : 'le panneau')
    return { titre: `À compléter : ${quoi}`, ligne: `Choisissez-${module && onduleur ? 'les' : 'le'} dans « Matériel électrique » (étape Électrique).` }
  },
  chutes_tension: (m) => (/cheminement|tracé|tronçon/i.test(m?.message || '')
    ? { titre: 'À compléter : le tracé des câbles', ligne: 'Tracez les liaisons dans l’atelier ou saisissez leurs longueurs : la chute de tension se calcule ensuite.' }
    : { titre: 'À vérifier : les chutes de tension', ligne: 'À vérifier dans l’étape Électrique.' }),
  terre_protections: (m) => (/norme/i.test(m?.message || '')
    ? { titre: 'Choisir la norme électrique de votre société', ligne: 'Sans elle, les câbles et les protections ne sont pas calculés.' }
    : { titre: 'À vérifier : la terre et les protections', ligne: 'À vérifier dans l’étape Électrique.' }),
  divers: (m) => {
    const n = Number(m?.nombre) > 1 ? Number(m.nombre) : 1
    return {
      titre: `À vérifier : ${n > 1 ? `${n} valeurs supposées` : 'une valeur supposée'} par le calcul`,
      ligne: 'Faute de donnée, le calcul les suppose : remplacez-les par vos valeurs quand vous les avez.',
    }
  },
}

/** `{titre, ligne, bouton, technique}` d'une ligne de `parcours.manque` ; `technique` = la phrase servie
    (pour le « ? »), vide quand elle serait identique au titre. */
export function manqueClair(m) {
  const entree = MANQUES_CLAIRS[m?.code]
  const clair = typeof entree === 'function' ? entree(m) : entree
  const servi = m?.message || ''
  if (!clair) return { titre: servi, ligne: '', bouton: 'Renseigner', technique: '' }
  return { titre: clair.titre, ligne: clair.ligne, bouton: clair.bouton || 'Renseigner', technique: servi === clair.ligne ? '' : servi,
    etape: clair.etape ?? null }
}
