# Copilote — Devis automatique (résidentiel) + édition par chat

- **Date** : 2026-06-24
- **Statut** : conçu, en attente de validation founder
- **Périmètre** : Phase 1 — résidentiel uniquement (industriel / agricole = Phase 2, hors périmètre ici)

## Problème

Aujourd'hui, quand on demande au Copilote « crée le devis du client X », son action
`ventes.devis.creer` crée une **coquille vide** (0 ligne, 0 DH) : elle ne sait pas
dimensionner l'installation. Le moteur de dimensionnement (le « devis automatique »)
vit uniquement côté **frontend** (`frontend/src/features/ventes/solar.js`) et n'est
pas accessible à l'agent (qui tourne côté serveur). Le founder veut que le Copilote :

1. **n'utilise JAMAIS** un chemin de création « à la main » — toujours le devis automatique ;
2. **récupère les données directement** depuis la fiche du lead (zéro question si la
   fiche est complète ; sinon il demande la donnée manquante) ;
3. puisse **modifier** un devis automatique par chat (ex. « réduis le prix de la
   batterie à 14000 TTC », ajouter / retirer un produit).

## Objectif (Phase 1)

Le Copilote peut, depuis une phrase :

- **créer** un devis résidentiel correctement dimensionné à partir de la fiche lead ;
- **éditer** ce devis (prix, quantités, ajout/retrait de lignes, remise globale).

## Hors périmètre

- Dimensionnement automatique **industriel / commercial** (étude autoconso) et
  **agricole** (pompage HMT/débit) → Phase 2.
- **Envoi WhatsApp automatique** (Business API). L'action existante
  `crm.lead.whatsapp_prepare` (prépare un lien wa.me, n'envoie pas) reste inchangée.
- Aucune modification du moteur de PDF ni des statuts (règle #4).

## Briques existantes réutilisées

- `apps/ventes/services.py::build_devis_from_layout` — compose les lignes
  (panneau / onduleur / batterie) depuis le catalogue, numérotation sûre, écrit
  `etude_params`, laisse le devis en `brouillon`.
- `apps/ventes/views/devis.py` + `urls.py` : `LigneDevisViewSet` exposé sur
  `/api/django/ventes/devis-lignes/` (create / update / delete, déjà scopé société
  + permissions) → support direct de l'édition.
- `apps/crm/services.py::resolve_client_for_lead` — résout le client sans doublon.
- Modèle `crm.Lead` : `conso_mensuelle_kwh`, `facture_hiver` / `facture_ete` /
  `ete_differente`, `regularisation_8221`, toiture (`type_toiture`,
  `surface_toiture_m2`, `orientation`, `inclinaison_deg`), `type_installation`,
  `taille_souhaitee_kwc`.
- Heuristique de dimensionnement résidentiel (à porter en Python depuis `solar.js`) :
  `estimerPanneaux(factureHiver) = floor(factureHiver / 900) * 8` panneaux ; kWc =
  panneaux × W_panneau / 1000.

## Conception

### 1. Garde-fou (règle « toujours automatique »)

- **Retirer** l'action agent `ventes.devis.creer` (la création « à la main ») du
  catalogue. Le Copilote ne peut plus créer de devis vide.

### 2. Moteur de devis automatique (résidentiel)

- **Service** `apps/ventes/services.py::build_devis_auto(*, lead, user, company)` :
  1. lit le profil énergétique + toiture du lead ;
  2. dimensionne en résidentiel : panneaux depuis la facture d'hiver (heuristique
     ci-dessus) ou `taille_souhaitee_kwc` si présent → kWc ;
  3. scénario par défaut **réseau** (sans batterie) ; une batterie s'ajoute ensuite
     par édition (§3) ;
  4. compose le devis via la logique existante de `build_devis_from_layout`
     (sélection catalogue, numérotation, `etude_params`), statut **`brouillon`**.
- **Endpoint** : `POST /api/django/ventes/devis/auto/` (action sur `DevisViewSet`),
  body `{ lead }` (ou `{ client }` si le client porte un lead lié). Société +
  `created_by` forcés serveur. Re-vérifie permission `ventes_creer`.
- **Données manquantes** : si une donnée clé manque (pas de facture/conso ni de
  `taille_souhaitee_kwc`), l'endpoint renvoie une erreur 422 listant le champ
  manquant ; l'agent **demande** alors cette donnée dans le chat (comportement
  retenu). Marché ≠ résidentiel (`type_installation` industriel/agricole) → 422
  « auto-devis non disponible pour ce marché en Phase 1, utilisez l'écran
  générateur ».
- **Action agent** `ventes.devis.creer_auto` (RISK_INTERNAL) → appelle l'endpoint ;
  résultat surfacé (référence devis + kWc + total).

### 3. Édition d'un devis par chat (complète)

Nouvelles actions agent **adossées à des endpoints existants** :

| Action agent | Endpoint réel | Risque |
|---|---|---|
| `ventes.devis.ligne_modifier` | `PATCH /ventes/devis-lignes/{id}/` | internal |
| `ventes.devis.ligne_ajouter` | `POST /ventes/devis-lignes/` | internal |
| `ventes.devis.ligne_supprimer` | `DELETE /ventes/devis-lignes/{id}/` | **outward (confirme)** |
| `ventes.devis.remise` | `PATCH /ventes/devis/{id}/` (`remise_globale`) | internal |

- **Identification de la ligne** : l'agent lit d'abord les lignes du devis (chemin
  lecture existant) pour retrouver la ligne « batterie » par mot-clé de désignation,
  puis agit par `id`.
- **TTC → HT** : l'écran/devis est saisi en TTC ; `LigneDevis.prix_unitaire` est en
  HT. Une consigne « 14000 TTC » est convertie : `prix_unitaire = 14000 / (1 + TVA)`.
  Le helper de conversion est testé.
- **Indicateur de marge** : si le nouveau prix < `prix_achat` (coût), l'agent
  **prévient** ; `prix_achat` n'apparaît jamais dans une sortie client (règle existante).
- **Devis brouillon uniquement** : l'édition ne s'applique qu'à un devis `brouillon`
  (Django reste l'autorité ; un devis envoyé/accepté n'est pas réécrit).

### 4. Sécurité (garanties inchangées)

- Chaque action relaie le JWT de l'appelant à Django, qui re-applique scope société
  (multi-tenant) + permissions de rôle. Aucune écriture SQL directe (règle #1).
- Suppressions / actions destructrices → proposition signée à confirmer (AG2).
- Règle #4 : `/proposal` reste l'unique chemin PDF client ; aucun statut modifié par
  ces actions (devis créé/édité en `brouillon`).

## Modèle de données

Aucune migration prévue : on réutilise les champs `crm.Lead` et `LigneDevis`
existants. (À confirmer pendant le plan d'implémentation si la sélection produit a
besoin d'un champ d'aide ; par défaut : non.)

## Tests

- `build_devis_auto` : facture hiver → nb panneaux → kWc → lignes (cas nominal,
  `taille_souhaitee_kwc` fourni, données manquantes → 422, marché non résidentiel → 422).
- Conversion TTC→HT (helper) ; isolement société (un lead d'une autre société est
  refusé) ; édition limitée au brouillon.
- Actions agent : validation des entrées (fail-closed), `ligne_supprimer` renvoie
  une proposition à confirmer, indicateur de marge déclenché sous le coût.
- Catalogue agent : `ventes.devis.creer` retiré, `creer_auto` présent.

## Phasage

- **Phase 1 (ce spec)** : garde-fou + auto-devis **résidentiel** + édition complète.
- **Phase 2 (plus tard)** : auto-devis industriel/commercial (autoconso) et agricole
  (pompage).
