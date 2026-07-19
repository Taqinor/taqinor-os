# Playbook — compte publicitaire Meta restreint

> PUB101. Quoi faire, dans quel ordre, quand le compte publicitaire n'est plus
> `Actif`. Le moteur LIT `account_status` / `disable_reason` à chaque synchro et
> lève une alerte typée `account_status` (garde-fou) qui pointe ce document. Un
> compte restreint ressemble à une « panne de données » (dépense/leads à plat) —
> ne PAS chercher un bug dans l'ERP tant que ce playbook n'est pas passé.

## 1. Identifier le statut

L'alerte porte le `account_status_label` et, si présent, le `disable_reason_label`.

| Statut Meta | Gravité | Sens |
|---|---|---|
| Actif (1/201) | — | Rien à faire (aucune alerte). |
| En revue de risque (7) | 🟠 Attention | Meta vérifie le compte ; diffusion souvent ralentie. |
| Période de grâce (9) | 🟠 Attention | Impayé récent ; régler avant la fin de la grâce. |
| En attente de règlement (8) | 🟠 Attention | Un paiement est en cours de traitement. |
| Impayé — non réglé (3) | 🟠 Attention | Solde dû ; la diffusion peut s'arrêter. |
| Désactivé (2) | 🔴 Urgent | Diffusion stoppée ; action requise. |
| Fermeture en attente (100) / Fermé (101/202) | 🔴 Urgent | Compte en fin de vie. |

## 2. Ordre des vérifications (du plus fréquent au plus grave)

1. **Paiement / solde** (statuts 3, 8, 9) — vérifier le mode de paiement dans le
   Gestionnaire de publicités Meta ; régler le solde dû. Compléter avec l'alerte
   trésorerie PUB97 (solde prépayé bas) si elle est aussi ouverte.
2. **Revue de risque** (statut 7, motifs 2/3/5/6) — attendre la fin de la revue
   Meta (24-48 h en général) ; ne rien resoumettre en boucle. Vérifier l'e-mail
   du gestionnaire du compte pour une demande de justificatif.
3. **Intégrité des annonces** (motif 1) — une ou plusieurs annonces enfreignent
   les règles ; corriger/retirer l'annonce fautive DANS Meta, puis demander une
   nouvelle revue.
4. **Désactivation / fermeture** (statuts 2/100/101, motif 4/7) — ouvrir un
   recours via le Centre d'aide Meta (Business Support) ; si le compte est
   définitivement fermé, prévoir un nouveau compte publicitaire.

## 3. Pendant la restriction

- Le moteur ne se fie plus aux chiffres (dépense/leads potentiellement gelés) :
  l'alerte reste ouverte tant que le statut n'est pas revenu `Actif`, puis se
  résout automatiquement à la synchro suivante.
- Aucune action automatique n'est prise sur le compte (règle #3 : rien ne
  s'active jamais tout seul).
- Ne PAS supprimer/recréer des campagnes tant que le compte n'est pas rétabli.

## 4. Référence technique

- Lecture : `meta_client.MetaClient.get_account_health()`
  (`account_status`, `disable_reason`, libellés FR).
- Alerte : `tasks.check_account_health()` (dédup par `entity_key='account_status'`,
  résolue au retour à l'actif).
