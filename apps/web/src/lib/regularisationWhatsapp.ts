/**
 * ENF19 — script partagé de la page « régularisation Article 33 » (fr/en/ar) :
 * le lien WhatsApp se met à jour en direct, le client n'édite JAMAIS le message.
 */
import { whatsappLink, regularizationWhatsappText } from './whatsapp';
import { WHATSAPP_LEADS } from './nap';

export function initRegularisationWhatsapp() {
  const kwcEl = document.getElementById('rg33-kwc') as HTMLInputElement;
  const unknownEl = document.getElementById('rg33-unknown') as HTMLInputElement;
  const villeEl = document.getElementById('rg33-ville') as HTMLInputElement;
  const goEl = document.getElementById('rg33-go') as HTMLAnchorElement;
  // WAUD10 — message dans la langue de la page (<html lang>).
  const lang = document.documentElement.lang;
  const locale = lang === 'en' || lang === 'ar' ? lang : 'fr';

  function refresh() {
    kwcEl.disabled = unknownEl.checked;
    if (unknownEl.checked) kwcEl.value = '';
    goEl.href = whatsappLink(
      WHATSAPP_LEADS,
      regularizationWhatsappText({
        kwc: unknownEl.checked ? '' : kwcEl.value,
        ville: villeEl.value,
      }, locale),
    );
  }
  for (const el of [kwcEl, unknownEl, villeEl]) el.addEventListener('input', refresh);
  refresh();
}
