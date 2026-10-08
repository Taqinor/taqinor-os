# Flux de données du site (YBW26)

Source unique : `src/lib/subprocessors.ts` (registre des sous-traitants). La
CSP du Worker (`worker/headers.mjs`) est construite depuis ce registre ; la page
Confidentialité (YBW27) le lit. Garde : `tests/subprocessors.test.ts` (un hôte
présent dans la CSP sans entrée au registre fait échouer le test).

Faits : plan `docs/plans/PLAN_YANBOW_WEB.md` (§ Faits établis, D-YBW-6, YBW51,
YBW54), état au 07/10/2026.

| Flux | Déclencheur | Données | Destinataire | Pays | Hôte tiers dans le navigateur ? |
| --- | --- | --- | --- | --- | --- |
| Visite d'une page | chaque requête | journaux techniques de la plateforme | Cloudflare (hébergement + Worker) | réseau mondial de Cloudflare | non (même origine) |
| Demande de rendez-vous | envoi du formulaire | champs du formulaire (registre YBW53) | Worker → serveur de l'ERP (relais SIGNÉ côté serveur, YBW54) | Allemagne (serveur de l'ERP) | non — le navigateur ne poste qu'à `/api/rendez-vous` (même origine) |
| Lien WhatsApp | clic du visiteur sur `wa.me` | ce que le visiteur écrit lui-même dans WhatsApp | WhatsApp (Meta) | selon Meta | non — navigation au clic, aucune requête avant |
| Reprise KV | seulement si l'ERP ne répond pas ET si l'espace KV existe (YBWM3) | champs du formulaire | Cloudflare KV | réseau de Cloudflare | non |

## Ce qui n'existe PAS (et ne doit pas apparaître sans mise à jour du registre)

- Aucun traceur, aucun analytics, aucun pixel, aucun cookie (défauts retenus du plan).
- Aucune police, image ou script chargé depuis un CDN tiers (polices auto-hébergées, YBW39).
- Aucune IP ni agent du visiteur transmis à l'ERP (contrat YBW50).
- Stockage KV : **inexistant** tant que `KV_REPRISE_DUREE_JOURS` vaut `null`
  (aucune entrée au registre) ; s'il est créé, sa durée est posée là et
  apparaît d'elle-même sur la page Confidentialité.

## Ajouter un sous-traitant

1. Ajouter l'entrée au registre (`role`, `roleEn`, `pays`, `quand`, `donnees`,
   `dureeJours`, et `csp` seulement si le NAVIGATEUR doit contacter l'hôte).
2. Mettre ce tableau à jour.
3. La CSP et la page Confidentialité suivent seules ; le crawl YBW15 refuse
   toute requête vers un hôte absent du registre.
