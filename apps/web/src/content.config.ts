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
  }),
});

export const collections = { blog };
