/**
 * Liens WhatsApp pré-remplis (wa.me). `number` : chiffres uniquement,
 * avec indicatif pays (ex. 2126XXXXXXXX).
 */
export function whatsappLink(number: string, text: string): string {
  const digits = number.replace(/\D/g, '');
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

/** Message pré-rempli après soumission du formulaire (nom + ville + bande ROI). */
export function leadWhatsappText(p: { fullName: string; city: string; kwcLabel: string; paybackLabel: string }): string {
  return (
    `Bonjour, je suis ${p.fullName} (${p.city}). ` +
    `Je viens de faire la simulation sur taqinor.ma : ${p.kwcLabel}, retour estimé ${p.paybackLabel}. ` +
    `Je souhaite être rappelé(e) pour une étude.`
  );
}

/**
 * Message pré-rempli pour la régularisation Article 33 — TOUJOURS complet,
 * jamais de blancs « ___ » à éditer par le client. Les champs viennent du
 * mini-formulaire de la page Régularisation ; sans eux, le message reste
 * naturel et complet.
 */
export function regularizationWhatsappText(p?: { kwc?: string; ville?: string }): string {
  const kwc = p?.kwc?.trim();
  const ville = p?.ville?.trim();
  return (
    'Bonjour, je dispose d’une installation solaire existante et je souhaite la régulariser ' +
    'dans le cadre de l’Article 33 de la loi 82-21. ' +
    (kwc ? `Puissance approximative : ${kwc} kWc. ` : 'Puissance : à déterminer ensemble. ') +
    (ville ? `Ville : ${ville}. ` : '') +
    'Merci de me recontacter pour constituer le dossier.'
  );
}
