// W329 — vocabulaire de thèmes éditoriaux partagé par le schéma blog
// (src/content.config.ts) ET la page /blog (puces de filtre + lien « guide
// associé »). Isolé ici, SANS aucune dépendance à `astro:content`, pour que
// src/pages/blog/index.astro puisse l'importer sans tirer `content.config`
// (dont les content-loaders Astro importent `node:fs`, ce qui faisait échouer
// le prerender Cloudflare de /blog/index.html — page rendue vide). Un même
// vocabulaire des deux côtés, une seule source de vérité.
export const BLOG_THEMES = ['Solaire', 'Batteries', 'Voiture électrique', 'Prix'] as const;
