import { LIBELLES_REGLAGES, estProfilDepart } from '../reglages/profilDepart'

/* Item 15 (T4-U2-013, T4-U4-009) — LE résolveur du nom d'un réglage figé au calcul. La simulation sert des clés
   PRÉFIXÉES de leur section (`electrique_societe.seuil_bas_dc_ac`), les libellés sont tenus SANS préfixe (registre
   `GET parametres/`, table du profil de départ) : la clé est cherchée telle quelle, puis sans son préfixe. Une clé
   sans libellé ne s'imprime JAMAIS brute. `courant` : les mots de tous les jours (note guidée), en minuscules ;
   sinon le terme du registre (ligne experte), à défaut le nom du profil. */
export const NOM_SANS_LIBELLE = 'Autre réglage (réglage de la société)'
const sansPrefixe = (cle) => {
  const texte = String(cle ?? '')
  return texte.includes('.') ? texte.slice(texte.lastIndexOf('.') + 1) : texte
}
export function nomDuReglage(cle, { registre = {}, courant = false } = {}) {
  const courte = sansPrefixe(cle)
  const profil = (LIBELLES_REGLAGES[cle] ?? LIBELLES_REGLAGES[courte])?.[0] ?? null
  const technique = registre[cle] ?? registre[courte] ?? null
  const nom = courant ? (profil ?? technique) : (technique ?? profil)
  if (nom) return courant ? nom.toLowerCase() : nom
  return courant ? NOM_SANS_LIBELLE.toLowerCase() : NOM_SANS_LIBELLE
}

/** Les clés des réglages FIGÉS au calcul dont la référence est une valeur publiée (profil de départ). La note parle des
    PERTES : les réglages de la section `electrique_societe.*` (seuils et tolérances du câblage) n'y sont ni nommés ni
    comptés (ACAL1632). */
const SECTION_ELECTRIQUE = 'electrique_societe.'
export function reglagesPublies(simulation) {
  const reglages = simulation?.reglages_utilises
  return reglages && typeof reglages === 'object'
    ? Object.keys(reglages).filter((cle) => !cle.startsWith(SECTION_ELECTRIQUE) && estProfilDepart(reglages[cle]?.reference))
    : []
}
