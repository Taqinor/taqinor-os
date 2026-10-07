# Règles du site YanBow (gardées par `tests/founderRules.test.ts`)

Source : règles du Website Playbook §4a (mémoire fondateur, 30/09/2026) + décisions
D-YBW du 06/10/2026 (`docs/plans/PLAN_YANBOW_WEB.md`). Chaque règle ci-dessous a
**un test sur le HTML RENDU, en français ET en anglais** (texte visible, titres,
méta-descriptions, textes alternatifs, JSON-LD) ; une fixture qui la viole fait
rougir le test qui la nomme. Changer une règle = décision de Reda, jamais
d'un agent.

| ID | Règle | Origine |
| --- | --- | --- |
| R1-PRIX | Aucun prix ni devise (`€`, `EUR`, `MAD`, `DH`, « tarif », « pricing ») | D-YBW-4, D-YBW-8 |
| R2-CHIFFRES | Aucun nombre de clients, d'installations, d'utilisateurs, de projets ni d'années | Playbook §4a, chiffres vérifiés seulement |
| R3-PREUVE-SOCIALE | Aucun avis, étoile, témoignage, note agrégée, compte à rebours, « offre limitée » | Playbook §4a |
| R4-COMPTE | Aucun « essai gratuit », « inscription », « créer un compte » (une seule conversion : prendre rendez-vous) | D-YBW-6 |
| R5-ANCRETO | « Ancreto » n'apparaît nulle part | D-YBW-3 |
| R6-MARQUE | Aucun `®`, « marque déposée », « OMPIC » (vérification du nom non faite) | YBWM14 |
| R7-EMPLOI | Aucun « remplacer un employé » | Playbook §4a |
| R8-SCRAPING | Aucun « scraping » ; États-Unis et Australie jamais cités | D-YBW-7, plan veille |
| R9-VEILLE | Aucune mention de veille, d'Ad Library, de bibliothèque publicitaire (tant que YBW90 n'est pas débloquée) | D-YBW-7 |
| R10-FRANCE | Jamais « prêt pour la France » | D-YBW-8 |
| R11-IDENTIFIANTS | Aucun identifiant de l'entreprise d'installation (RC, ICE, téléphone, mention CNDP, nom du gérant) | D-YBW-9 |
| R12-NOM-ENTREPRISE | Le nom de l'entreprise d'installation n'apparaît JAMAIS (la phrase D-YBW-9 ne la nomme pas) | D-YBW-9 |
| R13-MARKETINGBOW | « en service », « en production », « in use », « in production », « live » jamais dans la même phrase que MarketingBow | D-YBW-7, faits établis |
| R14-PERSONNES | Aucune image de personne (portrait, équipe, fondateur, visage, avatar) | Défauts retenus, Playbook |

Règles de travail associées (vérifiées ailleurs) : tout chiffre = fait vérifié
et tracé (`src/lib/facts.ts`, YBW18) ; toute phrase publique = affirmation
publiable du registre (`src/lib/claims.ts`, YBW18) ; noms de marque depuis
`src/lib/brand.ts` seulement (YBW19).
