# Module Innovation — boîte à idées, campagnes et feedback produit

`backend/django_core/apps/innovation` + `frontend/src/features/innovation`.
Trois étages indépendants, une seule app :

1. **Boîte à idées interne** — un collaborateur propose une idée, les autres
   votent, le palier Directeur/Responsable la fait avancer.
2. **Campagnes d'innovation ciblées** — inciter un segment précis (rôles /
   départements) à proposer des idées sur un sujet, avec tag automatique.
3. **Canal feedback produit** — retour 1→N vers le founder, jamais
   conversationnel (la messagerie d'équipe reste `apps/chat`).

Tout est scopé par société (`authentication.Company`) : la société et l'auteur
sont posés **côté serveur** depuis le JWT, jamais lus du corps de requête.

---

## 1. Modèles

| Modèle | Rôle | Points à connaître |
| --- | --- | --- |
| `Idee` | l'idée proposée | statuts `ouvert / examinee / retenue / realisee / fermee` ; `votes_count` **dénormalisé** (maintenu par `VoteIdee`, jamais recalculé à la lecture) ; `draft` (brouillon interne à l'auteur) ; `archived` (masquée par modération, jamais supprimée) ; `linked_type`/`linked_id` et `client_id` = références **opaques** (jamais de FK cross-app) |
| `VoteIdee` | un vote | unique par `(idee, votant)` ; l'auteur ne vote pas pour sa propre idée |
| `InnovationSettings` | singleton société | toggles `campagnes_activees`, `feedback_digest_actif`, `idees_clients_actif` (tous **OFF** par défaut), `seuil_votes_notification`, et les 6 gabarits e-mail (voir §5) |
| `CampagneInnovation` | campagne ciblée | statuts `brouillon / active / fermee` ; `segment` = **liste JSON** de noms de rôles/départements ; `cible_departement` = repli mono-valeur ; `message_incitation` (bandeau) ; `tag_auto` |
| `FeedbackProduit` | retour produit | `theme`, `sentiment` (optionnel), `context_type`/`context_id` (opaques), `source_page` + `user_agent` (posé serveur), `starred`, `archived`, `annonce` |
| `AnnonceProduit` | annonce « c'est livré » | repli **local** volontairement minimal — voir `docs/innovation-annonceproduit.md` |

Aucune idée ni aucun feedback ne se **supprime** : on ferme (`fermer`) ou on
masque (`masquer`). C'est un dossier de décision produit.

## 2. Permissions (`apps/innovation/permissions.py`)

| Garde | Qui | Où |
| --- | --- | --- |
| `IdeasVote` | tout utilisateur interne connecté, **sauf** le rôle Viewer | lire/proposer/voter, actions `publier`/`reouvrir`/`lier`/`historique`/`timeline` |
| `IdeasChangeStatus` | palier Directeur/Responsable | `examiner` / `retenir` / `realiser` / `fermer` |
| `IdeasModerate` | palier Directeur/Responsable | `masquer` une idée |
| `IdeasSeeAll` | palier Directeur/Admin | tableau de bord, export, actions en masse, campagnes, feedback, carte, autocomplétion auteur |
| `FeedbackModerate` | palier **Administrateur strict** | `masquer` un feedback (jamais Responsable) |
| `IdeasAggregateRead` | `IdeasSeeAll` **ou** rôle Viewer (`ideas_agrege_voir`) | tableaux de bord agrégés uniquement, jamais le détail |

## 3. Routes API (`/api/django/innovation/…`)

**Idées** — `idees/` (GET liste, POST création, GET/PATCH détail ; jamais de
DELETE). Filtres de liste : `statut`, `contexte`, `owner`, `created_since`,
`include_archived=1` (palier Responsable), `ordering`.

Actions : `idees/contextes/`, `idees/similaires/?q=`, `idees/tableau-bord/`,
`idees/auteurs/?q=`, `idees/geolocalisation/`, `idees/export-xlsx/`,
`idees/bulk/`, et par idée `examiner/`, `retenir/`, `realiser/`, `fermer/`,
`publier/`, `masquer/`, `reouvrir/`, `lier/`, `historique/`, `timeline/`.

**Votes** — `votes/` (POST pour voter, DELETE pour retirer),
`votes/recents/`, `votes/mes-idees/`.

**Campagnes** — `campagnes/` (CRUD), `campagnes/incitation/` (tout
utilisateur), `campagnes/tableau-bord/`, `campagnes/segments-disponibles/`,
et par campagne `rapport/`, `cloner/`, `historique/`, `noter/`.

**Feedback produit** — `feedback-produit/` (POST par tout utilisateur, liste
et détail réservés au palier admin), `feedback-produit/<id>/etoiler/`,
`masquer/`, `lier-annonce/` ; agrégats `feedback-resume/` et
`feedback-hotspot/`. **Annonces** — `annonces-produit/`.

**Divers** — `parametres/` (GET/PATCH singleton société), `timeline/`
(idées par jour).

### Exemples curl

```bash
TOKEN=...   # JWT obtenu sur /api/django/auth/login/
BASE=https://api.taqinor.ma/api/django/innovation

# Proposer une idée (company + auteur posés par le serveur)
curl -X POST "$BASE/idees/" -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"titre":"Scanner les BL au dépôt","description":"…","contexte":"Stock"}'

# Voter
curl -X POST "$BASE/votes/" -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"idee": 42}'

# Faire avancer (palier Directeur/Responsable)
curl -X POST "$BASE/idees/42/retenir/" -H "Authorization: Bearer $TOKEN"

# Lancer une campagne : le PATCH du statut EST le lancement
curl -X PATCH "$BASE/campagnes/7/" -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"statut":"active"}'

# Envoyer un retour produit
curl -X POST "$BASE/feedback-produit/" -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"titre":"L écran devis rame","theme":"performance","sentiment":"negatif"}'
```

## 4. Écrans (frontend)

| Route | Écran | Accès |
| --- | --- | --- |
| `/innovation/idees` | liste + actions en masse | tous |
| `/innovation/idees/:id` | détail, vote, transitions, chatter, minigraph des statuts | tous |
| `/innovation/proposer` | formulaire (bandeau d'incitation si campagne active) | tous |
| `/innovation/mes-idees` | mes propositions, brouillons compris | tous |
| `/innovation/tableau-bord` | KPI, top votes, idées par jour | Directeur/Admin |
| `/innovation/campagnes` | créer, **lancer**, rapport, cloner | Directeur/Admin |
| `/innovation/retours-produit` | feedback reçu, étoile, annonce, modération | Directeur/Admin |
| `/innovation/carte` | carte des idées liées à un chantier géolocalisé | Directeur/Admin |

La modale « Envoyer un retour » n'a **pas** de bouton flottant : elle s'ouvre
depuis le menu profil de l'en-tête (ordre fondateur du 2026-08-04).

## 5. Guide utilisateur

**Proposer une idée.** `/innovation/proposer` → titre + description +
contexte. Le formulaire propose des idées similaires pendant la frappe (pour
éviter les doublons) et affiche le message d'incitation si une campagne cible
votre rôle. « Enregistrer en brouillon » garde l'idée invisible des autres
jusqu'à ce que vous la publiiez depuis son détail.

**Voter.** Sur le détail d'une idée : un vote par personne, jamais pour sa
propre idée. Au seuil configuré (`seuil_votes_notification`, 3 par défaut),
l'auteur est notifié une seule fois.

**Faire avancer (Directeur/Responsable).** Examiner → Retenir → Réaliser, ou
Fermer avec une note. Chaque transition est journalisée dans l'historique, et
« retenue » puis « réalisée » envoient un e-mail à l'auteur — gabarits
personnalisables dans Paramètres → Avancé (vide = gabarit par défaut, seul le
jeton `{titre}` est substitué).

**Campagnes (Directeur/Admin).** `/innovation/campagnes` → « Nouvelle
campagne » (nom, segment, message d'incitation, tag automatique, dates), créée
en **brouillon**. L'action **Lancer** la passe en `active` : c'est cette
transition — et elle seule — qui notifie le segment ciblé et fait apparaître le
bandeau d'incitation. Chaque idée proposée par un membre du segment pendant que
la campagne est active reçoit le tag automatique (modifiable ensuite).

**Feedback produit.** Menu profil → « Envoyer un retour » : titre, description,
thème, ressenti optionnel. Le contexte (devis/ticket/chantier) est pré-rempli
si vous étiez sur une page détail. Seul le palier Directeur/Admin le lit, sur
`/innovation/retours-produit`.

## 6. Voir aussi

- `docs/innovation-annonceproduit.md` — lier un feedback ou une idée réalisée
  à une annonce produit.
- `docs/innovation-deploiement.md` — checklist avant mise en production.
