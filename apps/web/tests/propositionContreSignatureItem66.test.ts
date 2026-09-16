// Audit item 66 — la contre-signature Taqinor.
//
// RECALIBRÉ — décision fondateur du 16/09/2026 : « réduire au minimum prouvé ».
// L'item 66 avait ajouté à la PAGE un panneau « Pour Taqinor — signature et
// cachet », parce que le PDF en affiche un. La recherche vérifiée (r8/r9
// sign_flows : DocuSign, Jobber, Housecall Pro, ServiceTitan, OpenSolar,
// Yousign) ne montre AUCUN flux qui expose au client le cachet du vendeur
// AVANT qu'il signe : la contre-signature vit sur le document et dans l'accusé
// de réception. Le panneau quitte donc l'écran d'acceptation.
//
// L'INTENTION de l'item 66 — le client ne doit pas signer sans savoir que
// l'engagement est RÉCIPROQUE — n'est pas abandonnée, elle change de support :
//   (1) la phrase de droit (DOC art. 65-5 : le contrat naît de l'ACCEPTATION,
//       l'acompte ne fait que déclencher les travaux) est rendue SOUS le bouton
//       de signature, dans les trois langues ;
//   (2) le PDF garde ses DEUX cases de signature côte à côte — c'est le moteur
//       vendoré (règle #4), rien n'y a été touché, et ce test le vérifie.
//
// Ce fichier verrouille donc : le panneau n'est PLUS dans le formulaire, la
// phrase EST sous le bouton, et le moteur PDF est intact.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');
const TRUST_PY = read(
  '../../../backend/django_core/apps/ventes/quote_engine/residential/trust.py',
);

const formStart = PROPOSITION.indexOf('id="sign-form"');
const formEnd = PROPOSITION.indexOf('</form>', formStart);
const form = PROPOSITION.slice(formStart, formEnd);
const boutonIdx = PROPOSITION.indexOf('id="sign-submit"');

describe('Audit item 66 — la réciprocité, sans panneau avant la signature', () => {
  it('le panneau « signature et cachet » a quitté la page (décision fondateur 16/09)', () => {
    expect(PROPOSITION).not.toContain('id="prop-contre-signature"');
    expect(PROPOSITION).not.toContain('data-testid="contre-signature-marque"');
    // Le libellé RENDU du panneau (le gabarit `Pour ${brand} — …`) a disparu ;
    // seul le commentaire qui explique la décision en parle encore.
    expect(PROPOSITION).not.toContain('Pour ${brand} — signature et cachet');
    expect(PROPOSITION).not.toContain('For ${brand} — signature and stamp');
  });

  it('sa phrase de droit survit, SOUS le bouton de signature (DOC art. 65-5)', () => {
    const phrase = 'Votre commande est ferme dès votre acceptation';
    const idx = PROPOSITION.indexOf(phrase);
    expect(idx).toBeGreaterThan(0);
    // Sous le bouton, pas avant : c'est de l'information, pas une étape.
    expect(idx).toBeGreaterThan(boutonIdx);
    expect(idx).toBeLessThan(formEnd);
    // La suite exacte : l'acompte DÉCLENCHE les travaux, il ne forme pas le
    // contrat. L'ancienne phrase (« Le devis fait foi dès réception de
    // l'acompte ») disait au client l'inverse du droit, à son désavantage.
    expect(PROPOSITION).toContain('les travaux démarrent à réception de l’acompte.');
    expect(PROPOSITION).not.toContain('Le devis fait foi');
  });

  it('cette phrase porte ses trois langues (jamais du français figé sous EN/AR)', () => {
    const bloc = PROPOSITION.slice(boutonIdx, formEnd);
    expect(bloc).toContain('Your order is firm as soon as you accept');
    expect(bloc).toContain('يصبح طلبكم نهائياً بمجرد قبولكم');
  });

  it('aucun nom de vendeur n’est fabriqué dans le formulaire d’acceptation', () => {
    // Le panneau affichait `seller.name` quand le backend le servait. Il n'y a
    // plus de nom de contre-signataire du tout dans le formulaire : rien à
    // inventer quand le payload est muet.
    expect(form).not.toContain('seller?.name');
    expect(form).not.toContain('{seller.name}');
  });

  it('le PDF, lui, garde ses DEUX cases de signature (moteur vendoré, règle #4)', () => {
    expect(TRUST_PY).toContain('Bon pour accord — le client');
    expect(TRUST_PY).toContain('Pour {brand}');
    expect(TRUST_PY).toContain('Cachet et signature');
  });

  it('const brand est un littéral simple (site public Taqinor, jamais multi-tenant)', () => {
    expect(PROPOSITION).toContain("const brand = 'Taqinor';");
  });
});
