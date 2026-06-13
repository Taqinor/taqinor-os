// Garde-fou de positionnement : contenu vérifiable de l'accueil.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const index = readFileSync(fileURLToPath(new URL('../src/pages/index.astro', import.meta.url)), 'utf-8');

describe('accueil — positionnement', () => {
  it('1re carte de confiance = « Chantiers visitables », sans décompte de projets', () => {
    expect(index).toContain('Chantiers visitables');
    expect(index).toContain('Installations réelles à voir sur demande — Casablanca, El Jadida, Nouaceur');
    // Cible le rendu de la carte, pas les commentaires de code internes.
    expect(index).not.toContain('>5 projets<');
    expect(index).not.toContain('livrés depuis 2025');
  });

  it('fiches chantier sans ligne « témoignage à venir » ni faux témoignage', () => {
    expect(index).not.toContain('Témoignage client à venir');
    expect(index.toLowerCase()).not.toContain('témoignage');
  });
});
