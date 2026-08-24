// L-NIV-VU (24/08/2026) — « Version simplifiée », affichée SEULEMENT si vrai.
//
// Constat fondateur : basculer « Client standard » ↔ « Client de confiance » ne
// se voyait pas sur la page client. La chaîne fonctionnait — la page ne DISAIT
// simplement rien. Elle le dit désormais, mais jamais à vide : le serveur
// CONSTATE ce qui a été dégradé (`niveau_masque`) et la page se tait quand la
// liste est vide (niveau confiance, backend antérieur, ou devis sans rien à
// masquer). Annoncer une simplification qui n'a pas eu lieu serait un fait
// inventé — règle fondateur.
import { describe, expect, it } from 'vitest';
import { noteVersionSimplifiee } from '../src/lib/proposition';

describe('L-NIV-VU — noteVersionSimplifiee', () => {
  it('niveau confiance (liste vide) → aucune annonce', () => {
    expect(noteVersionSimplifiee({ niveau_masque: [] })).toBeNull();
  });

  it('clé absente (backend antérieur) → aucune annonce', () => {
    expect(noteVersionSimplifiee({})).toBeNull();
    expect(noteVersionSimplifiee({ niveau_masque: null })).toBeNull();
  });

  it('kit regroupé → la phrase nomme CE qui a été regroupé', () => {
    const note = noteVersionSimplifiee({ niveau_masque: ['nomenclature_kit'] });
    expect(note).toContain('Version simplifiée');
    expect(note).toContain('fixations');
    expect(note).toContain('une seule ligne');
    expect(note).toContain('votre conseiller');
    // Ce qui n'a PAS été masqué n'est pas annoncé.
    expect(note).not.toContain('calibres');
  });

  it('dimensionnement électrique masqué → la phrase nomme les calibres', () => {
    const note = noteVersionSimplifiee({
      niveau_masque: ['dimensionnement_electrique'],
    });
    expect(note).toContain('calibres');
    expect(note).not.toContain('fixations');
  });

  it('les deux dégradations → les deux raisons, une seule phrase', () => {
    const note = noteVersionSimplifiee({
      niveau_masque: ['nomenclature_kit', 'dimensionnement_electrique'],
    });
    expect(note).toContain('fixations');
    expect(note).toContain('calibres');
    expect(note?.split('Version simplifiée').length).toBe(2);
  });

  it('une clé inconnue est ignorée — jamais de jargon serveur affiché', () => {
    expect(noteVersionSimplifiee({ niveau_masque: ['bogus_futur'] })).toBeNull();
    const note = noteVersionSimplifiee({
      niveau_masque: ['bogus_futur', 'nomenclature_kit'],
    });
    expect(note).not.toContain('bogus_futur');
    expect(note).toContain('fixations');
  });

  it('RÈGLE FONDATEUR — la note ne parle JAMAIS des marques (toujours visibles aux deux niveaux)', () => {
    const note = noteVersionSimplifiee({
      niveau_masque: ['nomenclature_kit', 'dimensionnement_electrique'],
    });
    expect(note?.toLowerCase()).not.toContain('marque');
    expect(note?.toLowerCase()).not.toContain('modèle');
  });
});
