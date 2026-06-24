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
 * WJ3 — message pré-rempli pour la CAPTURE WhatsApp-first (/devis/mon-toit).
 * Le client envoie son estimation à Taqinor sur WhatsApp. Toujours complet,
 * jamais de blancs à éditer ; l'estimation (kWc + économies) est jointe quand
 * elle a pu être calculée honnêtement, sinon le message reste naturel sans
 * « undefined ». Aucun chiffre inventé : `kwcLabel`/`savingsLabel` viennent du
 * moteur (billEstimate) et sont absents si l'estimation est indisponible.
 */
export function captureWhatsappText(p: {
  fullName: string;
  city: string;
  kwcLabel?: string;
  savingsLabel?: string;
}): string {
  const name = p.fullName.trim() || 'un visiteur';
  const city = p.city.trim();
  const parts: string[] = [
    `Bonjour, je suis ${name}${city ? ` (${city})` : ''}.`,
    "Je souhaite recevoir mon estimation solaire de taqinor.ma.",
  ];
  if (p.kwcLabel?.trim() || p.savingsLabel?.trim()) {
    const bits: string[] = [];
    if (p.kwcLabel?.trim()) bits.push(`installation estimée ${p.kwcLabel.trim()}`);
    if (p.savingsLabel?.trim()) bits.push(`économies estimées ${p.savingsLabel.trim()}`);
    parts.push(`Mon estimation préliminaire : ${bits.join(', ')}.`);
  }
  parts.push('Pouvez-vous me recontacter pour une étude ?');
  return parts.join(' ');
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
