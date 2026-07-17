# ADSENG19 — Règle Meta native « homme-mort » (dead-man switch)

> **Statut : GATED — décision fondateur. RIEN N'EST ACTIVÉ.**
> Ce document + `apps/adsengine/deadman.py` décrivent la règle et rendent la
> commande d'installation. Ils n'installent rien : aucun appel Meta n'existe
> dans le code. L'installation est un geste **manuel** du fondateur.

## Ce que c'est

Une règle **native Meta**, hébergée par Meta via l'API `adrules_library`, donc
**indépendante de notre infrastructure**. Elle met en PAUSE tout ce qui dépasse
un **plafond de dépense catastrophe** (dernier recours — pas le pacing quotidien
ENG20/ENG21, bien au-dessus). C'est la **seule** protection qui survit à une
panne totale de notre côté (Celery mort, serveur down, réseau coupé) : la règle
continue de tourner chez Meta.

## Pourquoi une commande manuelle (et pas du code qui l'installe)

- **Vérifié** : le CLI Meta Ads n'expose **pas** `adrules_library` — seule l'API
  Graph brute le fait.
- Installer programmatiquement une règle qui **agit sur le compte** serait
  exactement le pouvoir que la **règle #3** nous interdit d'exercer sans décision
  explicite (« les campagnes naissent en pause, jamais d'activation
  programmatique »). Le module se contente donc de **construire** le payload et
  de **rendre** la commande `curl` ; le fondateur l'exécute lui-même.
- `DEADMAN_ENABLED` reste `False` **en dur** ; aucun chemin du module n'appelle
  Meta.

## La règle (spec)

- **Évaluation** : `entity_type = CAMPAIGN`, `time_preset = TODAY`,
  `spent > plafond_catastrophe` (Meta compte en centimes → `plafond_mad × 100`).
- **Exécution** : `PAUSE` (jamais `ACTIVATE`) + alertes email/instapush.
- **Cadence** : `SEMI_HOURLY` (le rythme le plus serré côté Meta).
- **Plafond par défaut** : `2000 MAD/jour` — un **défaut sûr** ; le fondateur
  fixe la valeur réelle au moment de la décision.

Payload exact : `apps.adsengine.deadman.build_deadman_rule_spec()`.

## Installer la règle (manuel, fondateur)

```bash
# Prérequis : un jeton System User avec la permission ads_management.
export META_SYSTEM_USER_TOKEN=<jeton>

# Rendre la commande exacte (le jeton n'est jamais incorporé, il est lu de
# l'environnement) :
python manage.py shell -c "from apps.adsengine.deadman import deadman_install_command; print(deadman_install_command(ad_account_id='act_XXXX', ceiling_mad=2000))"

# … puis exécuter la commande curl affichée, À LA MAIN, une fois.
```

## Déclencheur de décision

Installer la règle devient pertinent quand **un budget réel tourne en autonomie**
(mode autonome ENG38 activable) **et** qu'un **plafond catastrophe chiffré** est
arrêté par le fondateur. Tant que le moteur est OFF par défaut, la règle est
superflue.

## Désinstaller

Supprimer la règle se fait dans le **gestionnaire de règles Meta Ads** (ou un
`DELETE` sur l'ID de la règle via l'API Graph) — également un geste manuel.
