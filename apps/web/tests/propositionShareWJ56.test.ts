// WJ56 — « Partager sur WhatsApp » : logique PURE (aucun DOM).
// Distinct de whatsappLink (qui adresse un message AU numéro Taqinor) :
// whatsappShareLink partage le lien tokenisé lui-même, sans numéro de
// destinataire — le client choisit à qui l'envoyer (feuille wa.me générique).
import { describe, expect, it } from 'vitest';
import { whatsappShareLink } from '../src/lib/proposition';

describe('WJ56 — whatsappShareLink (partage du lien tokenisé, pas un message à Taqinor)', () => {
  it('ne cible aucun numéro (compositeur générique wa.me/)', () => {
    const url = whatsappShareLink('https://taqinor.ma/proposition/abc123', 'DEV-2026-042');
    expect(url.startsWith('https://wa.me/?text=')).toBe(true);
  });

  it('inclut l’URL complète de la page telle quelle', () => {
    const pageUrl = 'https://taqinor.ma/proposition/abc123';
    const url = whatsappShareLink(pageUrl, 'DEV-2026-042');
    expect(decodeURIComponent(url)).toContain(pageUrl);
  });

  it('cite la référence quand présente', () => {
    const url = whatsappShareLink('https://taqinor.ma/proposition/abc123', 'DEV-2026-042');
    expect(decodeURIComponent(url)).toContain('DEV-2026-042');
  });

  it('sans référence → message générique valide, toujours avec l’URL', () => {
    const pageUrl = 'https://taqinor.ma/proposition/xyz';
    const url = whatsappShareLink(pageUrl, '');
    expect(decodeURIComponent(url)).toContain(pageUrl);
    expect(decodeURIComponent(url)).toContain('Taqinor');
  });
});
