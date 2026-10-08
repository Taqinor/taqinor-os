# Sonde Ad Library (VEIL40)

Sonde autonome du premier contact avec l'API officielle Meta Ad Library (`ads_archive`).
Python standard, aucune dependance. **Construite maintenant, jamais lancee tant que
`tos_risk/meta_ad_library_api.md` n'est pas approuve par Reda et que le jeton de
l'application « YanBow Veille » n'existe pas.** Elle ne tourne jamais depuis le serveur
ni depuis l'ERP : Reda la lance en local, sous son acces officiel.

## Preparation

1. Creer `~/.yanbow/adlib.env` (hors depot, jamais commite) :
   `META_AD_LIBRARY_ACCESS_TOKEN=<jeton>`
2. Verifier le point « a verifier avant le premier appel » du fichier `tos_risk`.

## Lancer

    python tools/adlib_probe/probe.py --mots "sandals" --journal sonde.jsonl [--max-calls 150] [--only E0,E1]

`--max-calls` est plafonne a 150 (jamais depasse). Le journal est un JSONL sans secret :
le jeton n'y est jamais ecrit, `ad_snapshot_url` jamais conservee (E7 = un booleen), les
curseurs de pagination jamais conserves.

## Experiences

E0 duree de vie du jeton (`debug_token`) · E1 taille de page (sans `limit`, puis 100, 250,
500, 1000, 2000) · E2 un appel par pays (27 UE + GB) · E2-UK pubs GB sans pays UE dans la
repartition de portee · E3 UNORDERED vs EXACT_PHRASE · E4 multi-pays (OU ou ET) · E5
profondeur de pagination · E7 jeton present dans `ad_snapshot_url` · E8 jeton accepte en
en-tete `Authorization`. Seuls les chemins `ads_archive` et `debug_token` sont appelables
(liste blanche dans `Probe.call`) ; tout nouveau chemin exige d'abord son ajout a
`tos_risk/meta_ad_library_api.md` et l'accord du fondateur (regle #5).

## Gardes

`X-App-Usage` >= 75 % : pause de 300 s avant l'appel suivant. Codes 4/17/32/613 : attente
300/600/1200/1800 s puis arret (aucun nouvel appel). Codes 10/190 : arret + diagnostic
(sous-code note tel quel dans le journal).

## Tests hors ligne

    python -m unittest discover -s tools/adlib_probe -p "test_probe.py"

Mode `--rejouer reponses.jsonl` : rejoue des reponses enregistrees (une ligne JSON
`{"status":..,"headers":{..},"body":{..}}` par reponse), sans reseau et sans lire de jeton.
