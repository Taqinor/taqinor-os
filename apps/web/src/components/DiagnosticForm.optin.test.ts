/* ==========================================================================
   CAD121 — la case WhatsApp du formulaire de diagnostic part DÉCOCHÉE.

   Décision fondateur du 21/09/2026 (audit L3 cadence, section CAD-K). La case
   `whatsappOptIn` était rendue PRÉ-COCHÉE (`checked`), alimentait
   `whatsapp_opt_in` côté ERP et valait +3 points de score : or la loi 09-08
   (art. 10) exige un consentement « libre, spécifique et informé », qu'une
   case pré-cochée n'est pas — et ce faux consentement polluait le registre de
   consentement (CAD90).

   Ce test lit le SOURCE du composant : une case pré-cochée est une régression
   silencieuse (l'écran a l'air identique, le consentement ne l'est pas), et
   c'est exactement le genre de ligne qu'un futur « petit nettoyage » remet.
   La moitié serveur est verrouillée par
   `apps/crm/tests_cad121_optin_whatsapp_decoche.py`.
   ========================================================================== */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = readFileSync(join(ICI, 'DiagnosticForm.astro'), 'utf8');

/** La balise `<input …>` qui porte `name="<nom>"`, attributs compris. */
function balise(nom: string): string {
  const debut = SOURCE.indexOf(`name="${nom}"`);
  expect(debut, `champ ${nom} introuvable dans DiagnosticForm.astro`)
    .toBeGreaterThan(-1);
  const ouverture = SOURCE.lastIndexOf('<input', debut);
  const fermeture = SOURCE.indexOf('>', debut);
  return SOURCE.slice(ouverture, fermeture + 1);
}

describe('CAD121 — consentement WhatsApp', () => {
  it('la case WhatsApp est rendue NON cochée', () => {
    expect(balise('whatsappOptIn')).not.toMatch(/\bchecked\b/);
  });

  it('la case reste un vrai champ coché par le client', () => {
    const champ = balise('whatsappOptIn');
    expect(champ).toMatch(/type="checkbox"/);
  });

  it("la case de consentement aux données n'a pas bougé", () => {
    // Garde-fou de CAD121 : aucun AUTRE champ du formulaire ne change.
    const champ = balise('consent');
    expect(champ).toMatch(/type="checkbox"/);
    expect(champ).toMatch(/\brequired\b/);
    expect(champ).not.toMatch(/\bchecked\b/);
  });
});
