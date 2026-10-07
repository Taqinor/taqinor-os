# Portes de lancement du site YanBow

Le site est **FERMÉ par défaut** (YBW12, `worker/launchGate.mjs`) : tant que la
variable d'exécution `SITE_PUBLIC` ne vaut pas exactement `1`, chaque réponse
porte `X-Robots-Tag: noindex, nofollow`, `/robots.txt` répond `Disallow: /`,
aucun sitemap ni lien canonique n'est émis, et les pages juridiques non
complètes ne sont pas routables (même ouvert).

`SITE_PUBLIC=1` n'est posé QUE par Reda, au tableau de bord Cloudflare, quand
TOUTES les portes ci-dessous sont cochées (YBWM16). Il n'est jamais écrit dans
`wrangler.jsonc` (un test le vérifie).

Format : une porte par ligne `- [ ] ID — description (source)`. Le contrôle
automatique `scripts/check-launch-gates.mjs` (YBW85) lit cette liste ; cocher
`[x]` seulement quand la porte est réellement franchie, avec la date.

## Portes

- [ ] ENTITE-UK — YanBow Ltd immatriculée au Royaume-Uni : nom exact, partie du Royaume-Uni, numéro, siège renseignés dans `src/lib/legal.ts` (YBWM5, YBW25)
- [ ] ENTITE-MA — SARLAU marocaine immatriculée (RC, ICE, IF, capital, siège, gérant) si une page la cite (YBWM6, YBW25)
- [ ] CNDP — déclaration CNDP déposée et récépissé reçu, si la SARLAU est responsable du traitement du formulaire (YBWM6, YBW29)
- [ ] ICO — enregistrement ICO de YanBow Ltd fait (YBWM5)
- [ ] CONSEIL — relecture des pages juridiques par un conseil (Maroc, France, Royaume-Uni) et décision sur le représentant UE (YBWM9)
- [ ] EDITEUR — directeur de la publication désigné, responsable du traitement nommé, hébergeur confirmé (YBWM8)
- [ ] JURIDIQUE — pages Mentions légales et Confidentialité complètes et routables (YBW27, YBW28)
- [ ] DOMAINE — domaine acheté et posé dans `src/lib/site.ts` (`ORIGINE_CANONIQUE`) (YBWM10)
- [ ] DESIGN — candidat design choisi par Reda (YBWM12)
- [ ] TEXTE-FR — texte français approuvé par Reda (YBWM13)
- [ ] CONTACT — numéro WhatsApp et e-mail YanBow fournis (YBWM4)
- [ ] WORKER — projet Workers Builds créé et secrets du formulaire posés (YBWM1, YBWM2)
- [ ] ERP — société YanBow prête dans l'ERP et clé `SITE_RDV_CLES` posée (YBWM7)
- [ ] PREUVE — preuve en direct sur l'adresse workers.dev consignée, dont la survie du drapeau posé au tableau de bord après un merge (YBW86)
- [ ] NOM — décision de Reda sur la vérification du nom « YanBow » (marques, OMPIC) (YBWM14)
- [ ] AFFIRMATIONS — `check-claims --stale` vide (YBW18)
