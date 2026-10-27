---
name: residentiel-decisions-2710
description: "Décisions fondateur 27/10/2026 (cahier des charges Nabil Amar, villa 150 m de la mer) : ombrage du calepinage câblé dans le moteur horaire résidentiel ; VE déjà possédé non ajouté ; réponse à un cahier des charges = 3 devis /proposal + un mémoire technique hors moteur"
metadata:
  type: project
---

Trois décisions prises par Reda le 27/10/2026, en réponse au cahier des charges du lead crm 1658
(« nabil amar », villa Casablanca à 150 m de la mer, deux variantes hybrides 15 kWc et 18-20 kWc,
batterie ≈ 10 kWh, secours). Contexte complet : mémoire utilisateur
`sessions/2026-10-27-cahier-charges-nabil-amar.md` (dépôt taqinor-memoire).

## D-RES-2710-1 — Ombrage du calepinage dans la production du devis résidentiel

**Décision :** quand un calepinage existe pour le devis, le moteur horaire résidentiel
(`apps/ventes/etude_horaire.py`) applique la perte d'ombrage SERVIE par le calepinage
(`apps.calepinage.selectors.ombrage_servi`, par pan), exactement comme l'étude bancable le fait déjà
(`apps/ventes/etude.py`, CALX197/ACAL144). Sans calepinage : comportement inchangé (PVGIS 30°/sud,
14 % + derate, aucune lecture de `lead.ombrage`).

**Why :** le cahier des charges exige que l'étude d'ombrage soit « intégrée au dimensionnement et à la
simulation de production » ; aujourd'hui le chiffre client (économies, couverture) ignore l'ombrage
alors que la planche du même calepinage peut figurer dans le PDF → deux productions dans une même
offre, et une économie optimiste sur un site à arbres.

**How to apply :** D-ACAL-6 reste vrai (le chiffre client vient du moteur du devis) : le moteur
CONSOMME la perte du calepinage, il ne la remplace pas par la simulation du calepinage. QJR107/D7
reste vrai pour `lead.orientation` / `inclinaison_deg` / `ombrage` (CRM seulement, jamais câblés : pas
de coefficient sourcé). Un devis déjà envoyé garde ses chiffres (règle « nouveaux rendus seulement »).
Tâche de code M (goldens `build_quote_data` à recapturer) — non planifiée au 27/10 (« hold the plan
tasks »).

## D-RES-2710-2 — Voiture électrique déjà possédée : pas d'ajout

**Décision :** quand `Lead.equip_ve_statut = possede`, la couche VE n'est PAS ajoutée par-dessus la
consommation facturée (ses kWh sont déjà dans la facture) : ni dans la courbe horaire, ni dans
l'estimation affichée au client (`horaire/public.py`), ni dans le plancher de stockage « recharge
nocturne ». La décision du 21/09 (voiture pas encore achetée = « comptée des deux côtés ») reste
valable pour `prevu`.

**Why :** pour le lead 1658 (200 km/semaine, 11 kW la nuit) l'ajout vaut ≈ 172 kWh/mois affichés en
trop et pousse la batterie recommandée vers le haut, alors que le client déclare 3 850 kWh/mois
bornes comprises. Aucun effet sur l'économie en MAD (plafonnée à la facture), mais un chiffre client
faux.

**How to apply :** `apps/ventes/courbes_journalieres.py` (couche `ve`, mode `addition`) lit le statut ;
`possede` → pas de couche (ou couche en redistribution si l'on veut garder la forme nocturne, sans
changer le total). Le commercial renseigne `equip_ve_statut` sur le lead ; un statut vide garde le
comportement du 21/09 (ajout). Tâche de code S — non planifiée au 27/10.

## D-RES-2710-3 — Répondre à un cahier des charges : 3 devis /proposal + un mémoire technique

**Décision :** la réponse à un cahier des charges client qui impose sa propre structure et une offre
par variante = **un devis `/proposal` par variante** (ici A 15 kWc, B 18-20 kWc, et l'alternative
argumentée) pour les PRIX, plus **UN mémoire technique d'accompagnement SANS prix**, structuré selon
les sections du client (secours, protections, environnement marin, démarches 82-21, planning,
entretien, références), produit hors moteur de devis (document GED) et envoyé avec les fiches
techniques et certificats.

**Why :** règle #4 — `/proposal` est l'unique chemin des PDF de devis client ; son gabarit résidentiel
(3 pages) ne peut pas suivre les sections d'un client. Fabriquer un PDF de devis à la main est interdit.

**How to apply :** les devis sont créés séparément (« dupliquer », jamais « dupliquer-variante » qui
multiplie les quantités par 0,8/1,2), chacun en option unique « avec batterie » ; l'option pilotage
= lignes `optionnelle` (hors total) ; le texte libre du devis = `Devis.note` (page 3). Une option
`include_dossier_technique` (+1 page) du moteur pourra plus tard remplacer le mémoire — P1, non
planifiée au 27/10.


**D-RES-2710-GAR (Reda, 27/10, sur le PDF résidentiel) — une garantie client = UNE durée, celle du Maroc,
jamais « selon site » ni « variante régionale ».** Onduleur Deye = **5 ans** (termes Deye mondiaux v1.7 :
« 5 Years (10 Years Optional) », option non achetée) ; batterie Dyness DL5.0C = **10 ans** (version Afrique).
Catalogue + migration stock 0174 ; si l'extension Deye 10 ans est un jour achetée, repasser à 10.

Related: [[calepinage-decisions-fondateur]] (D-ACAL-6, D-ACAL-12), [[dimensionnement-decisions-2310]],
[[devis-envoyes-nouveaux-rendus]].
