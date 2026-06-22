// W114/W118 — la page de design devis : helpers de livraison PURS (URL proposition,
// wa.me, mailto) + gardes STATIQUES sur la page interne (auth Bearer attachée,
// from-layout appelé avec {layout, lead}, login générique « Identifiant ERP »,
// états d'erreur 401 → re-login). Pas de DOM lourd : on teste les builders + la source.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  designProposalUrl,
  designWhatsappText,
  designMailto,
  designMailSubject,
} from '../src/lib/devisDesign';
import { whatsappLink } from '../src/lib/whatsapp';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('W118 — helpers de livraison (URL proposition / wa.me / mailto)', () => {
  it('construit l\'URL de proposition (origine + chemin tokenisé)', () => {
    expect(designProposalUrl('https://taqinor.ma', '/p/abc123')).toBe('https://taqinor.ma/p/abc123');
    // tolère une origine avec slash final + un chemin sans slash initial
    expect(designProposalUrl('https://taqinor.ma/', 'p/xyz')).toBe('https://taqinor.ma/p/xyz');
  });

  it('le lien wa.me porte le numéro client + le message FR + le lien', () => {
    const url = designProposalUrl('https://taqinor.ma', '/p/tok9');
    const wa = whatsappLink('212661850410', designWhatsappText('Reda', url));
    expect(wa.startsWith('https://wa.me/212661850410?text=')).toBe(true);
    const decoded = decodeURIComponent(wa.split('text=')[1]);
    expect(decoded).toContain('Reda');
    expect(decoded).toContain(url);
    expect(decoded).toContain('Taqinor');
  });

  it('le message wa.me reste naturel sans nom', () => {
    const url = designProposalUrl('https://taqinor.ma', '/p/tok9');
    const decoded = decodeURIComponent(whatsappLink('212661850410', designWhatsappText('', url)).split('text=')[1]);
    expect(decoded.startsWith('Bonjour, ')).toBe(true);
    expect(decoded).toContain(url);
  });

  it('le mailto: porte destinataire + objet + corps avec le lien', () => {
    const url = designProposalUrl('https://taqinor.ma', '/p/tok9');
    const mail = designMailto('client@example.com', 'Reda', url);
    expect(mail.startsWith('mailto:client@example.com?')).toBe(true);
    expect(decodeURIComponent(mail.split('subject=')[1].split('&')[0])).toBe(designMailSubject());
    const body = decodeURIComponent(mail.split('body=')[1]);
    expect(body).toContain('Reda');
    expect(body).toContain(url);
  });
});

describe('W114 — la page de design : auth + from-layout + dégradés d\'erreur', () => {
  const page = read('../src/pages/internal/devis-design.astro');

  it('est noindex (page interne)', () => {
    expect(page).toContain('noindex={true}');
  });

  it('s\'authentifie sur /api/django/token/ avec un champ générique « Identifiant ERP »', () => {
    expect(page).toContain('Identifiant ERP');
    expect(page).toContain('/api/django/token/');
    // envoie username ET email (au cas où), + password
    expect(page).toContain('username');
    expect(page).toContain('email: username');
    expect(page).toContain('password');
  });

  it('garde le jeton d\'accès en sessionStorage (jamais localStorage)', () => {
    expect(page).toContain('sessionStorage');
    expect(page).not.toContain('localStorage');
  });

  it('appelle from-layout avec {layout, lead} et le header Bearer', () => {
    expect(page).toContain('/ventes/devis/from-layout/');
    expect(page).toContain('JSON.stringify({ layout, lead: leadId })');
    expect(page).toContain('authorization: `Bearer ${t}`');
  });

  it('persiste le layout (devis/<id>/layout/) puis envoie le PNG (W115, roof-image multipart)', () => {
    expect(page).toContain('/layout/');
    expect(page).toContain('/roof-image/');
    expect(page).toContain('FormData');
    expect(page).toContain("fd.append('image'");
  });

  it('gère le 401 (re-login) et lit ?lead=<id>', () => {
    expect(page).toContain('createRes.status === 401');
    expect(page).toContain('showLogin');
    expect(page).toContain("params.get('lead')");
  });

  it('boote le builder en mode hydraté (W113) avec le repère du lead', () => {
    expect(page).toContain('hydrate: { lead');
    expect(page).toContain('onApiReady');
  });
});
