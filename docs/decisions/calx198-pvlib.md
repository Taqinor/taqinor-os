# CALX198 — Adopter `pvlib` pour le modèle de cellule, la position du soleil et la transposition

**Statut : TRANCHÉ par Reda le 21/09/2026 — `pvlib` est ADOPTÉ.**
(Décision n° 1 de l'en-tête du groupe CALX dans `docs/PLAN2.md` : « `pvlib`
ADOPTÉ (dépendance libre BSD) pour le modèle de cellule, la position du soleil
et la transposition — CALX198 sort de GATED et se construit dans le lot 3 ».)

Ce mémo est celui que la tâche demandait AVANT la décision : il reste ici parce
qu'il dit **ce que la dépendance remplace, ce qu'elle n'apporte pas, ce qu'elle
coûte et où elle ne doit pas entrer**. Il est la référence des tâches de la
chaîne de pertes qui vont s'y brancher.

---

## 1. Le constat qui la motive (vérifié fichier par fichier)

Toute la physique du module, aujourd'hui, est une affaire de **rapports de
puissance** et de **dérives linéaires** ; il n'existe nulle part de courbe I-V.

| Où | Ce qui y est fait aujourd'hui | Ce que `pvlib` y apporterait |
| --- | --- | --- |
| `backend/django_core/core/electrique/types.py:137-152` | dérive de tension/puissance en `%/°C` (`temp_coeff_vmp_pct_c` renvoie le coefficient Pmax), avec `coefficients_sources` pour dire lesquels viennent de la fiche | modèle à une diode (De Soto / CEC) : Vmp, Imp et Pmp RÉELS à toute température et tout éclairement |
| `backend/django_core/apps/calepinage/services/thermique.py:72-116` | `temperature_cellule` (Faiman / NOCT) puis une perte en % | rien à remplacer — ces deux modèles sont déjà ceux de `pvlib.temperature`, écrits ici avec leurs sources ; `pvlib` ne ferait que dupliquer |
| `backend/django_core/apps/calepinage/services/bifacial.py:76-204` | `gain_bifacial` = un gain en % à partir de la bifacialité, l'albédo et la hauteur de pose | `pvlib.bifacial` (modèle infinite-sheds) : le gain arrière calculé heure par heure depuis la géométrie, plus une hypothèse de gain |
| `backend/django_core/core/calepinage/politique_pas.py:92-120` (`position_solaire_solstice`) | position du soleil AU SEUL solstice d'hiver, à une heure solaire choisie, pour espacer les rangées | `pvlib.solarposition` : la position à n'importe quel instant (algorithme NREL SPA)  |
| poste `iam` — `apps/calepinage/services/pertes.py:59-60` (CALX160) | au catalogue, **sans aucun calcul** | `pvlib.iam` : Fresnel (« physical »), ASHRAE, Martin-Ruiz |
| poste `irradiance` — `apps/calepinage/services/pertes.py:63-64` (CALX162) | au catalogue, **sans aucun calcul** | le faible éclairement sort GRATUITEMENT du modèle à une diode |
| transposition GHI → plan des modules | **inexistante** dans le dépôt : on ne sait lire que le `G(i)` déjà transposé par PVGIS | `pvlib.irradiance` (Perez, Hay-Davies) : transposer une météo apportée par le client (CALX62), ou une inclinaison différente de celle demandée à PVGIS |

## 2. Ce que `pvlib` n'apporte PAS

1. **Aucune donnée.** Ce sont des modèles, pas des mesures. La météo reste
   PVGIS SARAH3 (décision n° 2 : aucune donnée payante) ou le fichier du
   client. `pvlib.iotools` sait interroger des fournisseurs — **nous ne
   l'importons pas** : c'est le seul sous-module qui fait du réseau.
2. **Aucun paramètre de datasheet.** Le modèle à une diode a besoin de Rsérie /
   Rshunt / Iph / I0 / a, qui ne figurent sur AUCUNE fiche constructeur. Il faut
   soit un fichier `.PAN` (CALX356, gaté sur des fichiers réels de Reda —
   décision n° 6), soit l'extraction CEC depuis les 5 valeurs de la fiche
   (`pvlib.ivtools.sdm.fit_cec_sam`), soit la base CEC. **Sans l'un des trois,
   la tâche OMET son poste en nommant le champ manquant** — elle n'invente pas
   un Rsérie par défaut (D-CALX 7).
3. **Aucun verdict.** `pvlib` calcule ; il ne dit jamais si un résultat est
   acceptable.
4. **Aucune dispense de source.** Un modèle `pvlib` reste un modèle : son nom et
   sa référence doivent apparaître dans le rapport comme n'importe quel poste.

## 3. Le coût

* **Licence** : BSD-3-Clause. Libre, gratuite, aucun service tiers, aucune clé.
* **Épingle** : `pvlib==0.15.2` (dernière version stable au 21/09/2026).
* **Transitif** : `numpy>=1.21.2` (déjà épinglé `1.26.4` — compatible),
  `pandas>=1.3.3` et `scipy>=1.7.2` (déjà tirés par `statsmodels`),
  `requests` (déjà tiré), **`pytz` et `h5py` réellement neufs**. `h5py` est une
  roue binaire manylinux à HDF5 embarqué : **rien à ajouter au `Dockerfile`**
  (vérifié : l'image installe `requirements.txt` tel quel, ligne 36).
* **Poids** : ~19 Mo de roue `pvlib` + ~3 Mo de `h5py` dans l'image.
* **Maintenance** : `pvlib` casse son API entre majeures (dépréciations
  annoncées une version à l'avance). L'épingle exacte nous en protège ; la
  contrepartie est une relecture au moment de monter de version.
* **Temps d'import** : `pvlib` importe `pandas` et `scipy`. C'est la raison
  principale de la frontière ci-dessous.

## 4. La frontière — où `pvlib` n'entre PAS

`core/calepinage/` et `core/electrique/` sont des **noyaux purs** : le contrat
import-linter `calepinage-est-un-noyau-pur` et le test AST
`backend/django_core/core/tests/test_calepinage_purete.py` (liste blanche
`DEPENDANCES_AUTORISEES = {"numpy"}`, plus `matplotlib` confiné à `rendu/`)
interdisent toute autre dépendance externe. C'est ce qui rend le moteur
testable sans base de données, donc hors du gate migrations — le poste de coût
CI dominant.

**Règle retenue :**

* `pvlib` s'importe dans `backend/django_core/apps/calepinage/services/`
  (étapes de la chaîne de pertes, modèle de cellule, transposition, IAM) ;
* les noyaux purs gardent leur liste blanche `stdlib + numpy` — leur
  géométrie solaire est écrite à la main avec ses sources nommées
  (`core/calepinage/soleil.py`, CALX146) ;
* `pvlib` sert alors d'**oracle de validation** dans les tests : l'écart entre
  `core.calepinage.soleil.position_solaire` et
  `pvlib.solarposition.get_solarposition` est MESURÉ, il n'est pas supposé.
  Mesure du 21/09/2026 sur les 288 points de
  `apps/calepinage/tests/fixtures_pvgis/seriescalc_casablanca_sud.json` :
  **0,009° d'écart maximal en élévation, 0,017° en azimut**.

Élargir la liste blanche du noyau à `pvlib` reviendrait à faire dépendre le
calepinage de `pandas`, `scipy` et `h5py` au chargement : c'est ce que ce mémo
refuse, et la mesure ci-dessus montre que nous n'y perdons rien.

## 5. Où l'adoption ne doit pas faire perdre le droit de refuser

`pvlib` rend toujours un nombre, y compris quand l'entrée est une hypothèse.
C'est exactement ce que D-CALX 7 interdit. Les chemins à surveiller :

* **modèle à une diode** sans `.PAN` ni extraction CEC → le poste est OMIS en
  nommant le paramètre manquant, jamais rempli par la base CEC d'un module
  « ressemblant » ;
* **transposition Perez** sans DNI/DHI (PVGIS `seriescalc` rend `G(i)` déjà
  transposé) → décomposer un GHI par un modèle (Erbs, DISC) est une HYPOTHÈSE :
  elle se déclare comme telle dans le rapport, ou le poste est omis ;
* **albédo** : `pvlib` a un défaut de 0,25 — il ne doit JAMAIS être pris
  implicitement ; l'albédo est saisi avec sa provenance ou le gain bifacial est
  omis ;
* **`pvlib.temperature`** : ses jeux de paramètres (`SAPM`, `PVSYST`) sont des
  catalogues d'hypothèses de montage. Le dépôt sait déjà faire Faiman/NOCT avec
  la fiche produit : on ne remplace pas une valeur SOURCÉE par un catalogue.

## 6. Ce qui reste à faire (hors de cette tâche)

CALX160 (IAM), CALX162 (faible éclairement), la transposition d'une météo
apportée par le client (CALX62) et le mismatch d'ombrage exact se branchent sur
`pvlib` dans `apps/calepinage/services/etapes/`. CALX356 (import `.PAN`) reste
gaté sur les deux fichiers réels attendus de Reda (décision n° 6).
