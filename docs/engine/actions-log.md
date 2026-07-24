# Journal des actions moteur — objets créés/modifiés sur Meta

Règle : toute action d'écriture sur Meta est consignée ici (IDs, réglages,
statut de naissance). Rien n'est activé par un agent — l'activation est un
geste du fondateur, toujours.

## 2026-07-24 — Token sprint 2 + refresh créatif (Growth System v3.1, P1.3/P1.4)

**Contexte** : app « aqinor Ads Engine » (id 1708624427128028) passée en mode
Live par le fondateur ; App Secret régénéré et stocké côté serveur ; clés CAPI/
Lead-Ads posées dans le `.env` serveur (alias du token système) ; déploiement
ERP fait par le fondateur.

### Écritures Meta effectuées

| Quoi | ID | Détail | Statut |
|---|---|---|---|
| Événement CAPI de TEST | — | `Lead`, `test_event_code=TEST_TAQINOR_WIRING`, pixel « leads » 845710231783646, identifiants factices hachés | accepté (`events_received=1`) — visible uniquement dans l'onglet Test Events |
| Abonnement webhook (app) | app 1708624427128028 | object=page, field=leadgen → `https://api.taqinor.ma/api/django/crm/webhooks/meta-lead-ads/` — challenge validé par Meta | actif |
| Abonnement webhook (page) | page 784992588041621 | `subscribed_apps`, subscribed_fields=leadgen | `success: true` |
| Leads de TEST (formulaire 1363584938545797) | 3075471452642053 | créés pour valider la chaîne — données factices Meta | livraison webhook EN ATTENTE (voir « À suivre ») |
| Annonce V1 « Facture d'été » | ad 120246146967510160 | ad set 120241202673270160 (« ad set 1 »), vidéo réutilisée 1562996058380449, CTA GET_QUOTE → form 1363584938545797 | **née PAUSED** |
| Annonce V2 « Preuve ingénieurs » | ad 120246146968830160 | même ad set, vidéo réutilisée 1201875008529895 | **née PAUSED** |
| Annonce V3 « Étude 3D » | ad 120246146969760160 | même ad set, vidéo réutilisée 2707123896326273 | **née PAUSED** |

Choix d'implantation : les 3 variantes sont créées PAUSED **dans l'ad set
existant** (une entité en pause n'a aucun effet sur la diffusion ; un ad set
cloné entrerait en concurrence d'enchères avec l'original une fois activé).
Aucun objet existant modifié — aucun statut, budget ou ciblage touché.

Copies conformes (aucun chiffre non vérifié, pas de promesse de rachat, pas
de « 3-5 ans », pas d'« assuré décennale », pas de faux témoignage ; vidéos
réelles du compte réutilisées) :
- V1 « L'été fait grimper la facture ? Produisez votre électricité. »
- V2 « Dimensionné par des ingénieurs. Chiffré ligne par ligne. »
- V3 « Vos panneaux sur VOTRE toit, en 3D — avant de décider. » (adossée à
  l'outil réel /devis/mon-toit)

### Préparé, PAS exécuté

- Commande de pause de l'annonce « Ad 5 » (120241202673250160, flag
  WITH_ISSUES) — remise au fondateur, décision à lui :
  `POST graph.facebook.com/v25.0/120241202673250160 status=PAUSED`

### À suivre

- **Livraison du webhook leadgen** : abonnements actifs et callback validé
  (GET facebookplatform 200 dans les logs nginx), mais le lead de test n'a
  pas encore été poussé. Piste n°1 : Leads Access Manager (« Accès aux
  prospects ») — si « Personnaliser l'accès » est actif sur la Page, ajouter
  l'app « aqinor Ads Engine » ; l'outil de test Lead Ads (« Track status »)
  donne le diagnostic de livraison côté Meta.
- **Boucle WhatsApp CTWA : GATED** — le numéro business est porté par
  l'intégration WhatsApp d'Odoo (l'outil de Meryem) ; aucun câblage tant que
  la coexistence n'est pas vérifiée (prévu avec la migration P3).
