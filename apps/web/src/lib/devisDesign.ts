/**
 * W118 — helpers de LIVRAISON du lien de proposition (page interne devis-design).
 *
 * Pur et testable : construit l'URL de proposition tokenisée (origine du site +
 * chemin renvoyé par le backend), le texte WhatsApp français, et le mailto:
 * pré-rempli. Aucune dépendance, aucun effet de bord — la page câble les liens.
 */

/** URL absolue de la proposition : origine du site + `proposal_path` du backend. */
export function designProposalUrl(origin: string, proposalPath: string): string {
  const base = (origin || '').replace(/\/+$/, '');
  const path = proposalPath?.startsWith('/') ? proposalPath : `/${proposalPath ?? ''}`;
  return `${base}${path}`;
}

/** Message WhatsApp français pré-rempli (nom optionnel) + lien de proposition. */
export function designWhatsappText(name: string, proposalUrl: string): string {
  const hello = name?.trim() ? `Bonjour ${name.trim()}, ` : 'Bonjour, ';
  return (
    `${hello}voici votre proposition d'installation solaire Taqinor : ${proposalUrl} ` +
    `N'hésitez pas à me poser vos questions.`
  );
}

/** Objet de l'e-mail français pré-rempli. */
export function designMailSubject(): string {
  return 'Votre proposition solaire Taqinor';
}

/** Corps de l'e-mail français pré-rempli (nom optionnel) + lien de proposition. */
export function designMailBody(name: string, proposalUrl: string): string {
  const hello = name?.trim() ? `Bonjour ${name.trim()},` : 'Bonjour,';
  return (
    `${hello}\n\n` +
    `Voici votre proposition d'installation solaire Taqinor :\n${proposalUrl}\n\n` +
    `Je reste à votre disposition pour toute question.\n\n` +
    `Cordialement,\nL'équipe Taqinor`
  );
}

/** Lien mailto: pré-rempli (destinataire + objet + corps encodés). */
export function designMailto(email: string, name: string, proposalUrl: string): string {
  const subject = encodeURIComponent(designMailSubject());
  const body = encodeURIComponent(designMailBody(name, proposalUrl));
  return `mailto:${email}?subject=${subject}&body=${body}`;
}
