# `contract_samples/` — PACT10 : le contrat part EN PREMIER, et il est PARTAGÉ

Même règle et même format que `apps/ao/contract_samples/README.md` (lire ce
fichier-là pour le « pourquoi » complet : incident du 03/08/2026, l'écran AO
Tableau de bord, zéro clé sur six concordante).

En bref : dès qu'une fonctionnalité a une moitié front et une moitié back, le
contrat atterrit **seul et en premier** sur `main`. Ce dossier EST le porteur.
Un fichier `<nom_endpoint>.json` par endpoint, avec `endpoint` (verbe + chemin
exact), `pourquoi` (une phrase) et `exemple` (une réponse complète et
réaliste — ce sont les **clés et leurs natures** qui font le contrat).

`scripts/check_api_shapes.py` échoue si l'exemple et le serveur divergent, et
un test frontend importe l'exemple au lieu d'écrire son mock à la main (un
mock manuel est une DEUXIÈME source de vérité).

## Ce que ce dossier couvre (WIR275 / WIR277)

Les registres ISO QHSE exposés REST : campagnes de rappel produit,
certifications + audits externes, programme d'audit interne, réunions et
revues de direction, objectifs 6.2 — plus le contexte SMQ ISO 4 (parties
intéressées, contexte de l'organisation) et la diffusion des procédures.

Les endpoints de LISTE d'un `ModelViewSet` ne sont pas des agrégats : leur
forme est celle du sérialiseur. Les exemples déposés ici servent d'abord les
écrans (WIR276 / WIR278) pour qu'ils ne devinent aucune clé.
