# Consignes communes aux lanes du chantier « Tâches »

À lire EN PREMIER par toute lane. Dossier de travail : `docs/taches/travail/` (dans le dépôt, répertoire courant).

## À lire avant de travailler
1. `docs/taches/travail/socle.md` — décisions fondateur + socle validé. **Il fait foi** sur tout autre fichier.
2. `docs/taches/travail/brief-r1.md` — demande du fondateur mot pour mot, faits vérifiés du dépôt, règles maison.
3. Les fichiers que ta mission nomme (conceptions `design-s*.md`, vérifications `verif-*.md`, recherches `recherche-*.md`,
   spécifications `spec-*.md`).

## Règles
- **Lecture seule sur le dépôt**, sauf LE fichier de sortie que ta mission t'attribue dans `docs/taches/travail/`.
  Aucun autre fichier créé, modifié ou supprimé. Pas de docker, pas de tests, pas de migrations, pas de commit, pas de push.
- Tu écris en **français** (termes de code en l'état). Phrases courtes, zéro remplissage.
- Le fondateur dort et a demandé qu'on ne lui pose **aucune question** : face à un choix ouvert, tranche avec
  l'option la plus sûre et la plus simple pour lui, et consigne-la dans une section « Choix par défaut » avec sa raison.
- **Complet ET simple (D-TCH-5).** Chaque fonction est classée : **ESSENTIEL** (visible d'emblée, sans réglage),
  **AVANCÉ** (présente mais repliée, découverte au besoin), **ÉCARTÉ** (avec la raison). On n'écarte pas une fonction
  utile pour « faire simple » : on la replie. Un écran ne montre jamais plus que ce qu'il faut pour le geste en cours.
- **Zéro chiffre inventé** : tout nombre montré à l'utilisateur est réel, dérivé de façon traçable, ou absent.
  Une affirmation sur un produit concurrent ou sur la recherche porte sa source (URL lue dans cette session) ou
  l'étiquette « de mémoire, non vérifié ».
- **Toute affirmation sur le code existant porte son `fichier:ligne`** lu dans cette session.
- Vie privée : les 8 règles du socle §2 s'appliquent à tout ce que tu conçois.
- Ne ré-ouvre pas une décision du socle. Si tu penses qu'elle est fausse, dis-le dans « Objections au socle » avec
  la preuve, et conçois quand même en la respectant.
- Recherche web : respecte le budget donné par ta mission ; préfère lire une source primaire à multiplier les recherches.

## Format d'une spécification (`spec-<sujet>.md`, 2 500 mots au plus)
1. **Parcours** — les parcours de l'utilisateur, étape par étape, avec le NOMBRE DE GESTES (taps ou touches) de chacun,
   sur iPhone et sur bureau.
2. **Fonctions classées** — tableau fonction · ESSENTIEL / AVANCÉ / ÉCARTÉ · d'où elle vient (produit ou source) · pourquoi.
3. **Règles exactes** — algorithmes déterministes, cas limites, exemples chiffrés recalculables.
4. **Données** — champs et modèles AJOUTÉS au schéma plancher du socle §3 (ne renomme rien), contraintes, index.
5. **API** — routes, corps de requête et de réponse (JSON d'exemple), erreurs qui désignent le champ fautif.
6. **Écrans** — éléments de chaque écran, états vide / chargement / erreur / hors ligne (l'esthétique est traitée par un L3 à part).
7. **Assistant** — actions et cartes concernées (voir `design-s3-assistant.md`).
8. **Critères d'acceptation** — « Étant donné / Quand / Alors », exécutables tels quels par un test.
9. **Risques et gardes** — ce qui peut casser, les gardes CI concernées, les fichiers d'un autre propriétaire touchés.
10. **Choix par défaut** et **Objections au socle**.

## Bloc de preuve (à respecter mot pour mot)
Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
