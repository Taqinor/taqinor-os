// QJW3 — LE SEUL CONSTRUCTEUR DE CORPS DU TUNNEL « mon-toit ».
//
// Remplace les TROIS `buildBody()` recopiés dans `src/pages/devis/mon-toit.astro`,
// `src/pages/en/devis/mon-toit.astro` et `src/pages/ar/devis/mon-toit.astro`.
// Ce module est PUR : il prend un objet d'état simple (`EtatTunnel`, construit
// par la page à partir de son DOM), rend un objet simple, et ne touche ni au
// DOM ni à Astro. C'est ce qui le rend testable sans navigateur — et c'est ce
// qui rend la parité entre locales VÉRIFIABLE plutôt qu'espérée.
//
// IL NE DÉCIDE RIEN LUI-MÊME. Tout ce qui est « quel champ, sous quel nom, à
// quelle condition » vit dans le registre (`champs.ts`, QJW2) ; ce fichier est
// une boucle sur ce registre. Un moteur sans cas particulier est la seule
// façon d'être sûr qu'aucune locale ne peut plus diverger d'une autre.
//
// LA DISCIPLINE, INCHANGÉE : « nettoyer ou omettre, jamais fabriquer ». Une
// question qui n'a pas été posée est une clé ABSENTE du corps — jamais un
// défaut fabriqué. Le registre porte cette règle champ par champ ; la boucle
// ci-dessous se contente de ne rien écrire quand le nettoyage rend `undefined`.
//
// IL NE RÉ-IMPLÉMENTE PAS LA VALIDATION. Le pré-contrôle client appelle le
// `validateLead` existant de `src/lib/lead.ts` — le MÊME code que le serveur —
// au lieu d'en tenir un miroir en ligne qui dériverait.

import { validateLead } from '../lead';
import { CHAMPS_TUNNEL, type CleChamp, type EtatTunnel } from './champs';

/** Les trois locales servies par le tunnel. */
export type LocaleTunnel = 'fr' | 'en' | 'ar';

/**
 * Les messages d'erreur que la PAGE possède, clés sur les clés du registre.
 *
 * `nomComplet` est obligatoire : c'est le seul message que le tunnel produit
 * de lui-même (le durcissement WJ65 ci-dessous), il n'a donc aucun repli
 * possible côté `validateLead`. Les autres sont FACULTATIFS et se substituent
 * au message de `validateLead` quand ils existent — c'est ainsi qu'un visiteur
 * anglophone ou arabophone cesse de recevoir un message d'erreur en français.
 *
 * `telephone` est DÉLIBÉRÉMENT absent de cette liste côté appelant :
 * `normalizeMoroccanPhone` produit un message CIRCONSTANCIÉ (indicatif,
 * longueur, format) qu'aucune chaîne statique ne peut remplacer sans perdre de
 * l'information. Fournir la clé reste possible, mais ce serait un recul.
 */
export type MessagesErreurs = Partial<Record<CleChamp, string>> & {
  readonly nomComplet: string;
};

/**
 * Le contexte d'un envoi : ce qui dépend de la LOCALE ACTIVE et non de l'état
 * du formulaire. La page FR et la page AR basculent leur langue en direct :
 * elles passent la table de la langue affichée AU MOMENT DE L'ENVOI, pas celle
 * de leur URL.
 */
export interface ContexteCorps {
  readonly messages: MessagesErreurs;
}

/** Ce que rend `construireCorps` : le corps à envoyer + les erreurs de champ. */
export interface ResultatCorps {
  body: Record<string, unknown>;
  errors: Record<string, string>;
}

/**
 * Index `webhookKey` → clé de registre. `validateLead` rend ses erreurs sous
 * les noms du CONTRAT RÉSEAU (`fullName`, `city`, `billRange`…) ; la table de
 * messages, elle, est clée sur le registre. Cet index fait le pont sans
 * qu'aucune correspondance ne soit écrite à la main deux fois.
 */
const CLE_PAR_WEBHOOK_KEY: ReadonlyMap<string, CleChamp> = new Map(
  CHAMPS_TUNNEL.map((c) => [c.webhookKey, c.cle as CleChamp]),
);

/**
 * Construit le corps de lead et rend les erreurs client.
 *
 * @param etat  l'état du formulaire, déjà lu depuis le DOM par la page.
 * @param ctx   les messages d'erreur de la locale ACTIVE.
 */
export function construireCorps(etat: EtatTunnel, ctx: ContexteCorps): ResultatCorps {
  const body: Record<string, unknown> = {};
  for (const champ of CHAMPS_TUNNEL) {
    const valeur = champ.nettoyer(champ.lire(etat));
    // `undefined` = la question n'a pas été posée : la clé reste ABSENTE.
    // Jamais un `false`, un `0` ou une chaîne vide fabriqués à sa place.
    if (valeur === undefined) continue;
    body[champ.webhookKey] = valeur;
  }

  const v = validateLead(body);
  const errors: Record<string, string> = v.ok ? {} : { ...v.errors };

  // WJ65 — `validateLead` n'exige qu'une longueur ≥ 2 doublée d'au moins une
  // lettre sur le nom NETTOYÉ ; le tunnel ajoute la même exigence sur la
  // saisie BRUTE pour que l'erreur s'affiche dans la langue de l'écran.
  // \p{L} couvre tous les alphabets — latin ET arabe.
  if (!errors.fullName && !/\p{L}/u.test(etat.nomComplet)) {
    errors.fullName = ctx.messages.nomComplet;
  }

  // Localisation des messages de `validateLead` (français par construction) :
  // on ne substitue QUE là où la page a fourni une traduction. Sans entrée,
  // le message d'origine passe tel quel — jamais un texte approximatif à la
  // place d'un message précis.
  for (const [webhookKey, message] of Object.entries(errors)) {
    const cle = CLE_PAR_WEBHOOK_KEY.get(webhookKey);
    if (!cle) continue;
    const traduit = ctx.messages[cle];
    if (traduit && message !== traduit) errors[webhookKey] = traduit;
  }

  return { body, errors };
}
