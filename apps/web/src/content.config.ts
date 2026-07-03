/**
 * Content collections (W132) — blog Taqinor, sans dépendance.
 *
 * Le loader `glob` et le validateur Zod (`z`) sont fournis par le cœur d'Astro 6
 * (`astro:content` / `astro/loaders`) : AUCUN paquet ajouté. Les articles vivent
 * en Markdown sous `src/content/blog/` et ne portent QUE du frontmatter + le
 * corps — aucun schéma JSON-LD en ligne (les routes le construisent à partir du
 * frontmatter). Schéma figé : les autres agents rédigent leurs articles contre
 * lui, ne pas le modifier.
 */
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// W329 — thèmes du blog, VOLONTAIREMENT alignés sur les groupes déjà affichés
// sur /guides (groups[].theme dans src/pages/guides/index.astro : Solaire,
// Batteries, Voiture électrique, Prix) : un même vocabulaire des deux côtés
// est ce qui permet le lien croisé « guide associé » (posts et guides
// partageant un thème se lient entre eux sans mapping séparé à maintenir).
export const BLOG_THEMES = ['Solaire', 'Batteries', 'Voiture électrique', 'Prix'] as const;

const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    author: z.string().default('Taqinor'),
    ogSlug: z.string().optional(),
    draft: z.boolean().default(false),
    /** Image de couverture (W198) — chemin /public relatif ou URL. Optionnel :
     *  les articles sans cover restent valides et s'affichent sans image. */
    cover: z.string().optional(),
    /** W329 — thème éditorial optionnel, pour les puces de filtre de
     *  /blog et le lien « guide associé ». Optionnel : les articles sans
     *  thème (actus, méta) restent valides et sortent simplement de tout
     *  filtre de thème (jamais de build cassé par un frontmatter manquant). */
    theme: z.enum(BLOG_THEMES).optional(),
  }),
});

export const collections = { blog };
