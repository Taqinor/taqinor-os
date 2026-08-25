// LANE T-WEB (25/08/2026) — verrous de source : la balise de visite site
// entier est bien branchée dans le layout partagé, la bannière d'aperçu
// interne de la page proposition est bien gatée sur `apercuInterne`, aucune
// balise/beacon ne part depuis un aperçu interne, et `appareil_id` est bien
// joint aux 3 flux additifs (tunnel, questionnaire, proposition). Même
// discipline « lecture de la source brute » que cardSelectedWJ117.test.ts —
// ces éléments vivent dans des <script>/attributs Astro non couverts par un
// test comportemental unitaire.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('Layout.astro — balise de visite branchée sitewide', () => {
  const layout = read('../src/layouts/Layout.astro');

  it('déclare la prop skipVisitBeacon (défaut false — rendu inchangé partout ailleurs)', () => {
    expect(layout).toMatch(/skipVisitBeacon\?:\s*boolean/);
    expect(layout).toContain('skipVisitBeacon = false');
  });

  it('importe et appelle demarrerBalise depuis lib/visite', () => {
    expect(layout).toContain("import { demarrerBalise } from '../lib/visite';");
    expect(layout).toMatch(/demarrerBalise\(location\.pathname/);
  });

  it('la balise est gatée sur apercuInterne via le flag skip transmis au module client', () => {
    expect(layout).toContain('apercuInterne: init?.skip === true');
  });
});

describe('proposition/[...token].astro — bandeau + désactivation aperçu interne', () => {
  const src = read('../src/pages/proposition/[...token].astro');

  it("calcule apercuInterne depuis data.apercu_interne (backend L-INTPREV)", () => {
    expect(src).toContain('const apercuInterne = ok && data?.apercu_interne === true;');
  });

  it('transmet skipVisitBeacon={apercuInterne} au Layout — aucune balise en aperçu interne', () => {
    expect(src).toContain('skipVisitBeacon={apercuInterne}');
  });

  it('le bandeau « Aperçu interne » est gaté sur apercuInterne et sticky', () => {
    expect(src).toMatch(/\{apercuInterne && \(/);
    expect(src).toContain('id="apercu-interne-banner"');
    expect(src).toContain('Aperçu interne — le client ne voit pas cette visite');
    expect(src).toMatch(/id="apercu-interne-banner"[\s\S]{0,40}class="sticky top-0/);
  });

  it('le formulaire de signature est masqué ET le bouton désactivé sous apercuInterne', () => {
    expect(src).toContain("hidden={offerState !== 'live' || apercuInterne}");
    expect(src).toContain("disabled={offerState === 'expired' || apercuInterne}");
  });

  it('les 4 boutons de contact perdent leur href et deviennent non cliquables sous apercuInterne', () => {
    const contactHrefGuards = src.match(/href=\{apercuInterne \? undefined : \w+\}/g) ?? [];
    expect(contactHrefGuards.length).toBe(4);
    expect(src).toMatch(/pointer-events-none opacity-50/);
  });

  it('le formulaire « Demander une modification » est désactivé sous apercuInterne (3 boutons + textarea + submit)', () => {
    const disabledGuards = src.match(/disabled=\{apercuInterne\}/g) ?? [];
    // 3 puces de type + textarea + bouton d'envoi = 5.
    expect(disabledGuards.length).toBe(5);
  });

  it('AUCUN beacon (proposition-track NI funnel-beacon) ne part sous apercuInterne', () => {
    const trackFn = src.slice(src.indexOf('function trackProposalEvent'));
    expect(trackFn.slice(0, 400)).toContain('if (cfg.apercuInterne) return;');
    const funnelFn = src.slice(src.indexOf('function sendProposalFunnelBeacon'));
    expect(funnelFn.slice(0, 400)).toContain('if (cfg.apercuInterne) return;');
  });

  it('appareil_id est joint au beacon d’engagement (proposition-track), additif', () => {
    expect(src).toContain('appareilId: appareilId(),');
    expect(src).toContain("import { appareilId } from '../../lib/visite';");
  });

  it('SignConfig porte apercuInterne, transmis depuis le frontmatter serveur', () => {
    expect(src).toMatch(/interface SignConfig \{[\s\S]*?apercuInterne\?:\s*boolean;/);
    const signConfigBlock = src.slice(src.indexOf('const signConfig = ok'), src.indexOf('const signConfig = ok') + 800);
    expect(signConfigBlock).toContain('apercuInterne,');
    expect(signConfigBlock).toContain(': null;');
  });
});

describe('questionnaire/[token].astro — appareil_id joint au POST', () => {
  const src = read('../src/pages/questionnaire/[token].astro');

  it("importe appareilId et le joint à buildQuestionnairePostBody", () => {
    expect(src).toContain("import { appareilId } from '../../lib/visite';");
    expect(src).toContain('buildQuestionnairePostBody(section, raw, photo, appareilId());');
  });

  it('transmet skipVisitBeacon={interne} au Layout — aucune balise sous aperçu interne questionnaire', () => {
    expect(src).toContain('skipVisitBeacon={interne}');
  });
});

describe('devis/mon-toit.astro (FR) — appareil_id additif au payload lead du tunnel', () => {
  const src = read('../src/pages/devis/mon-toit.astro');

  it("importe appareilId et le joint au corps du lead, jamais bloquant", () => {
    expect(src).toContain("import { appareilId } from '../../lib/visite';");
    expect(src).toContain('appareilId: appareilId() || undefined,');
  });
});

describe('lib/lead.ts — appareilId accepté, additif, anti-garbage', () => {
  const src = read('../src/lib/lead.ts');

  it('ValidatedLead porte appareilId en champ optionnel', () => {
    expect(src).toMatch(/appareilId\?:\s*string;/);
  });

  it("validateOptionalFields n'accepte qu'un format uuid plausible", () => {
    expect(src).toMatch(
      /if \(appareilId && \/\^\[0-9a-f\]\{8\}-\[0-9a-f\]\{4\}-\[0-9a-f\]\{4\}-\[0-9a-f\]\{4\}-\[0-9a-f\]\{12\}\$\/i\.test\(appareilId\)\) \{/,
    );
  });
});

describe('lib/questionnaire.ts — appareil_id additif au corps POST par section', () => {
  const src = read('../src/lib/questionnaire.ts');

  it('buildQuestionnairePostBody accepte un 4e paramètre appareilId, additif', () => {
    expect(src).toMatch(/buildQuestionnairePostBody\(\s*section: QuestionnaireSectionId,\s*raw: Record<string, unknown>,\s*photoDataUrl\?: string \| null,\s*appareilId\?: string,/);
    expect(src).toContain('if (appareilId) body.appareil_id = appareilId;');
  });
});

describe('lib/proposition.ts — appareil_id additif au payload de track', () => {
  const src = read('../src/lib/proposition.ts');

  it('buildProposalTrackPayload accepte un appareilId optionnel, omis quand absent', () => {
    expect(src).toContain('appareilId?: string,');
    expect(src).toContain('...(appareilId ? { appareil_id: appareilId } : {}),');
  });
});

describe('pages/api/visite.ts — proxy same-origin, même discipline que les autres', () => {
  const src = read('../src/pages/api/visite.ts');

  it('applique la garde same-origin + rejet cross-site (même chemin que le tunnel)', () => {
    expect(src).toContain("import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';");
    expect(src).toContain('if (!isSameOriginRequest(request)) return crossSiteRejection();');
  });

  it('applique un rate-limit par IP dédié', () => {
    expect(src).toMatch(/rateLimit\(`visite:\$\{clientIpFromRequest\(request\)\}`/);
  });

  it('relaie vers /api/django/crm/public/visite/ (endpoint public, pas le webhook de lead)', () => {
    expect(src).toContain("/api/django/crm/public/visite/");
    // Le secret statique du webhook de capture de lead n'est ni lu ni envoyé —
    // seulement MENTIONNÉ dans le commentaire expliquant pourquoi (cf. juste
    // au-dessus) : on vérifie l'absence de tout USAGE réel (accès env./en-tête).
    expect(src).not.toContain('env.LEAD_WEBHOOK_SECRET');
    expect(src).not.toContain('x-webhook-secret');
  });

  it('valide le corps via validateVisiteBody avant tout relais', () => {
    expect(src).toContain("import { validateVisiteBody } from '../../lib/visite';");
    expect(src).toContain('const validated = validateVisiteBody(body);');
  });
});
