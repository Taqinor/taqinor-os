# Points à poser au conseil (YBW29 — YBWM9)

Liste des points juridiques **non tranchés** ou **non vérifiés à la source**.
Aucune règle juridique n'est citée sur le site lui-même ; ces documents restent
dans `apps/yanbow-web/docs/`. Les pages juridiques (YBW27/YBW28) restent non
routables tant que leurs champs sont `null` (`src/lib/legal.ts`).

## Sources relues le 2026-10-07

| Règle | URL | Lu le | Résumé |
| --- | --- | --- | --- |
| Companies Act 2006, s.51 | <https://www.legislation.gov.uk/ukpga/2006/46/section/51> | 2026-10-07 | un contrat conclu au nom d'une société non encore constituée engage personnellement celui qui agit pour elle → rien sur le site ne doit laisser croire que la Ltd existe avant l'immatriculation |
| Regs 2015 (SI 2015/17), reg. 25 | <https://www.legislation.gov.uk/uksi/2015/17/regulation/25> | 2026-10-07 | site web : partie du Royaume-Uni d'immatriculation, numéro, adresse du siège, statut de société à responsabilité limitée le cas échéant ; si le capital est cité, seulement le capital libéré |
| LCEN (loi 2004-575), art. 1-1 | <https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000801164> | 2026-10-07 | l'éditeur personne morale met à disposition : dénomination, siège, téléphone, n° d'immatriculation, capital, directeur de la publication, nom et coordonnées de l'hébergeur |
| RGPD art. 27 | <https://gdpr-info.eu/art-27-gdpr/> | 2026-10-07 | voir `EU_REPRESENTATIVE.md` |
| UK GDPR art. 27 | <https://www.legislation.gov.uk/eur/2016/679/article/27> | 2026-10-07 | voir `EU_REPRESENTATIVE.md` |
| CNDP — formulaires et procédure | <https://www.cndp.ma/notifier-une-declaration-type-de-declaration-formulaires/>, <https://www.cndp.ma/procedures-de-notification-process/> | 2026-10-07 | voir `CNDP_DOSSIER.md` |

## Questions ouvertes

1. **Portée de la LCEN** sur un éditeur établi hors de France (société
   britannique) qui vise des installateurs français : les mentions de l'art. 1-1
   sont-elles obligatoires ? (Le site les prévoit de toute façon, YBW28.)
2. **Exemption RGPD art. 27(2)** pour un simple formulaire de rendez-vous ?
   Représentant UE nécessaire selon la branche (Ltd ou SARLAU) ?
3. **Voie CNDP** : déclaration simplifiée (F214) ou normale (F211) ? La
   délibération « clients » couvre-t-elle des prospects ? Transfert F-118 vers
   l'Allemagne / Cloudflare / le Royaume-Uni ?
4. **Mentions marocaines** sur le site pour la SARLAU (loi 5-96, art. 45 selon le
   plan — **texte non relu** : dénomination + forme + capital ? RC, ICE, IF ?).
5. **Loi 09-08** articles 2, 10, 19, 43-44 cités par le plan — **texte non
   relu** (entrée : <https://www.cndp.ma/loi-09-08/>).
6. **Version qui fait foi** : la page Mentions légales dit « la version française
   fait foi » — à confirmer (ou anglaise pour une société britannique ?).
7. **Cookies CNIL** : sans traceur au lancement, aucun bandeau ; à confirmer que
   le journal d'erreurs client (`/api/client-error`, sans donnée personnelle)
   n'appelle pas de consentement.
8. **Responsable du traitement** : quelle entité (YBWM8) ?
9. **Durée de conservation** affichée (3 ans après le dernier contact,
   anonymisation seulement si `CRM_LEAD_RETENTION_ACTIF` est armé) : la
   formulation est-elle acceptable tant que la purge n'est pas armée ?
