# Notes de déploiement — vague 3 (sécurité / connexions)

À lire **avant** de déployer la vague 3 (lot ASEC). En clair : ce qu'il faut
régler dans le fichier `.env` du serveur, ce qui s'éteint si on ne le fait pas,
et ce qui change pour les utilisateurs.

## 1. Variables à poser dans `.env` AVANT le déploiement

| Variable | À quoi elle sert | Si elle reste vide |
|---|---|---|
| `SAV_WHATSAPP_APP_SECRET` | Secret de l'application Meta qui signe les messages WhatsApp entrants du SAV. | **Le WhatsApp SAV entrant s'éteint** : tout message reçu est refusé, aucun ticket n'est créé ni complété. C'est volontaire (plus aucun message non signé n'écrit en base). |
| `SAV_WHATSAPP_NUMEROS` | Dit à quelle société appartient chaque numéro WhatsApp Business. Format : `<phone_number_id>=<id société>` séparés par des virgules, ex. `1234567890=1`. | **Messages ignorés** : un numéro absent de la liste n'est rattaché à aucune société (avant, tout tombait dans « la première société »). |
| `ODOO_COMPANY_ID` | Numéro (id) de la société ERP à qui appartiennent les données Odoo (TAQINOR). | **Le connecteur Odoo lecture seule s'éteint pour tout le monde** (coût par signature réel, import des notes) même si `ODOO_URL`/`ODOO_DB`/`ODOO_USERNAME`/`ODOO_API_KEY` sont posés. |

Après modification du `.env` : redémarrer les conteneurs Django et Celery
(le déploiement habituel le fait).

## 2. Commandes Odoo : nouvel argument `--company`

`odoo_pull` et `odoo_import_notes` exigent maintenant la société en clair :

```
python manage.py odoo_pull --company <slug-ou-id>
python manage.py odoo_import_notes --company <slug-ou-id> [--dry-run]
```

Sans `--company` (ou avec une autre société que `ODOO_COMPANY_ID`), la commande
s'arrête sans rien faire. Toute tâche planifiée ou script qui les lance doit
être mis à jour.

## 3. Changements de droits (rôles)

- **Gestion des comptes (ASEC10).** Créer, modifier, désactiver un compte exige
  désormais le droit « Gérer les utilisateurs ». Commercial responsable,
  Technicien responsable et Responsable le reçoivent automatiquement (ils le
  faisaient déjà). **Admin Ventes le perd** (votre décision du 07/10) : il voit
  la liste des comptes mais ne peut plus les modifier.
- **Droits par module (ASEC11).** Un rôle ne peut plus écrire dans un module
  dont il ne porte aucun droit (ex. Commercial terrain ne crée plus de client
  CRM, Admin RH ne crée plus de facture). Ajustements de la revue :
  - Commercial, Commercial responsable et Admin Ventes gardent « Créer le
    chantier » depuis un devis accepté et la liste des chantiers à facturer ;
  - Commercial et Technicien gardent le glisser-déposer de l'agenda ; les
    rapports sauvegardés, la configuration du tableau de bord et les alertes
    KPI restent réservés aux administrateurs / responsables.

## 4. Connexion

- **Verrou par compte + adresse IP (ASEC4).** 10 échecs de connexion d'affilée
  depuis la même adresse IP bloquent ce compte **depuis cette adresse
  seulement**, pendant 15 minutes. Le titulaire qui se connecte d'ailleurs
  n'est pas gêné. Le verrou « société » (si vous l'avez réglé dans Paramètres)
  garde son fonctionnement : il bloque le compte partout.
- **Même réponse qu'un mauvais mot de passe (ASEC14).** Un compte bloqué reçoit
  exactement le message « identifiants incorrects » — l'écran n'annonce plus
  qu'un compte est verrouillé. Un utilisateur bloqué doit attendre 15 minutes
  (ou demander à un administrateur de le débloquer).

## 5. Double authentification : réinscription recommandée (ASEC8)

Avant cette vague, le journal d'activité pouvait garder en clair le secret 2FA
d'un compte au moment où il l'activait. La migration l'a effacé du journal,
mais une copie a pu être vue ou sauvegardée avant. **Recommandé :** pour chaque
compte qui a la 2FA activée (au minimum les administrateurs), la désactiver
puis la réactiver pour générer un nouveau secret.

## 6. Inscription en libre-service : fermée par défaut (ASEC13)

La création d'une société depuis l'écran de connexion est **fermée** (réponse
404). Pour l'ouvrir un jour : `TENANT_SIGNUP_ENABLED=1` côté serveur **et**
`VITE_TENANT_SIGNUP_ENABLED=1` à la construction du frontend (sinon le lien
« Créer votre société » reste caché). Laisser les deux à 0 aujourd'hui.

## 7. Société de démonstration (`est_demo`, ASEC16)

Les commandes et l'assistant de démo n'agissent plus que sur une société
marquée `est_demo=True` (jamais sur une société dont le nom contient « demo »).
Sur une machine locale (QA nocturne) dont la société `taqinor-demo` a été créée
avant ce changement, `seed_demo` la refuse : la marquer `est_demo=True` une
fois si c'est bien une démo. Rien à faire sur le serveur de production.
