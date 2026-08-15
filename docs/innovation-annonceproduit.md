# Lier un retour ou une idée réalisée à une annonce produit

Guide bref pour la boucle « vous l'aviez demandé, c'est livré ».
Voir `docs/innovation.md` pour le module complet.

## Aujourd'hui : `innovation.AnnonceProduit` (repli local)

`AnnonceProduit` est un repli **volontairement minimal** (titre, description,
lien) : uniquement ce dont `FeedbackProduit.annonce` a besoin pour afficher la
fermeture. Il n'est pas le référentiel d'annonces produit de la plateforme.

### Fermer un feedback avec une annonce EXISTANTE

`POST /api/django/innovation/feedback-produit/<id>/lier-annonce/`

```json
{
  "annonce_id": 12,
  "message": "Livré dans la version du 12/08 — merci pour le signalement."
}
```

### Fermer un feedback en créant l'annonce à la volée

```json
{
  "annonce": {
    "titre": "Export XLSX des devis",
    "description": "Le bouton Export est maintenant disponible sur la liste des devis.",
    "lien": "https://taqinor.ma/nouveautes/export-devis"
  },
  "message": "C'est livré !"
}
```

Effet : `FeedbackProduit.statut` passe à `adresse`, `annonce` pointe la ligne,
`message_fermeture` porte le message affiché à l'auteur. Le feedback n'est
**jamais** supprimé — seule la référence à l'annonce peut disparaître si
l'annonce est retirée (`on_delete=SET_NULL`).

### Idée réalisée

Une idée n'a pas de champ `annonce` : l'annonce se rattache au **feedback**.
Pour une idée, la boucle passe par sa transition `realiser/`, qui envoie à
l'auteur l'e-mail « idée réalisée » (gabarit personnalisable, voir
`docs/innovation.md` §5). Si l'idée avait un feedback jumeau, fermez ce
feedback avec l'annonce comme ci-dessus.

## Demain : `NTADM18` (référentiel plateforme)

Quand le référentiel d'annonces produit de la plateforme existera, les deux
modèles **ne fusionnent pas**. La bascule prévue :

1. `FeedbackProduit.annonce` (FK locale) devient une référence **opaque**
   `annonce_type` / `annonce_id`, exactement comme `Idee.linked_type` /
   `linked_id` — jamais une FK cross-app (règle de frontière : on lit une
   autre app via ses `selectors.py`/`services.py` ou une string-FK).
2. `services.fermer_feedback_via_annonce` garde sa signature ; seule sa
   résolution interne change (appel au selector de l'app propriétaire au lieu
   d'un `AnnonceProduit.objects.get`).
3. `innovation.AnnonceProduit` se retire alors, sans migration de données
   destructive : les lignes existantes sont recopiées vers le référentiel
   plateforme, puis le modèle local est supprimé dans une migration séparée.

Le contrat d'API du client ne bouge pas : `{"annonce_id": N}` reste la forme
attendue par `lier-annonce/`.
