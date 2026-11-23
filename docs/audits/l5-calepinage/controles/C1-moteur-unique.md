# C1 — « Un seul moteur, celui du CRM » et le lead 1742

Enquête en lecture seule, 23/11/2026, branche `claude/calpinage-module-l5-aadbde` (HEAD 38a6bf7941). Faits du lead :
lecture de la prod du 22/11 (code servi `bfb859c90`). « Lue » = fonction ouverte ; « probable » = déduit ; « à
reproduire » = à rejouer sur la pile. Aucun test lancé, aucun conteneur.

## 1. Carte des moteurs

Pour une même installation, **quatre moteurs** calculent : (A) le moteur de devis C&I serveur (`apps/ventes/moteur_ci/`
+ `domain/etude_ci.py`) ; (B) le moteur de devis résidentiel serveur (`domain/pipeline.py` + `solar_design.py`) ; (C) le
calepinage serveur (`apps/calepinage/services/` sur `core/electrique/`) ; (D) l'atelier dans le navigateur
(`apps/web/src/scripts/roofPro11/`). S'y ajoutent deux tables annexes : le noyau d'appel d'offres
`core/calepinage/electrique.py` (constantes 16 modules, 60 kWc, 0,75-1,00) et `frontend/src/features/ventes/solar.js`
(productible par ville, miroir). Le moteur agricole n'a pas été ouvert (voir §6).

| Grandeur | Devis (A/B) | Calepinage (C/D) | Où deux réponses naissent |
|---|---|---|---|
| Panneaux, kWc | A : `moteur_ci/taille.py::dimensionner_ci` (règle 10 ans, deux options sans/avec, `taille_creation_ci`) ; B : `domain/pipeline.py::decider_taille` | compte DESSINÉ `roof_layout.zones[].geometry.count` ; cible = `ventes/services::cible_depuis_lignes(devis)` option `'sans'` TOUJOURS (lue, `domain/lignes.py`) servie par `selectors_calepinage.py` ; atelier `cible.ts::repartirCibleVendue`, remplissage `limiteModules.ts::noteToitRempli` | le document ne note aucune option (clés relevées sur le calepinage 9) ; la cible ignore `etude_params.recommended_option` : un devis qui recommande « Avec batterie » fait dessiner l'option sans |
| Onduleur retenu | A : `moteur_ci/onduleurs.py::_chercher` (le moins d'appareils puis le coût) ; B : `solar_design.py::match_inverter` | `services/electrique.py::resoudre_materiel` : saisie explicite > 1re ligne du devis lié hors `'avec'` (`equipements.py::equipements_du_calepinage` ← `selectors_calepinage.py::lignes_produits_calepinage`) ; nombre par `core/electrique/onduleurs.py::dimensionner_onduleurs` borné au plafond AO 60 kWc | nombre d'onduleurs : combinaison du devis contre plafond de dossier |
| Ratio DC/AC | A : `bornes_dc_ac` (1,35 « convention atelier ») + D1/D-HYB-1 hybride = `dc_max_kwc` (`moteur_ci/onduleurs.py::_capacite_kwc`, lue) ; B : `solar_design.py::MAX_DC_AC = 1.35` ; `compatibilites.py` 0,8-1,4 cible 1,15 ; `domain/composition_imposee.py::RATIO_DC_AC` (0,8, 1,4) | `electrique.py::_bornes_ratio` / `_juger_ratio` (ACAL1538 : la borne du noyau ne juge plus) ; `core/electrique/onduleurs.py::dimensionner_onduleurs` alerte > 1,50 sans exception hybride ; `core/calepinage/electrique.py::BORNES_RATIO_AC_DC` (0,75, 1,00) | **cinq bornes** ; D-HYB-1 n'existe que dans A (grep `dc_max_kwc` : le calepinage ne le lit que comme repli de `ac_kw`, `etapes/onduleur.py`) |
| Longueur de chaîne, tension à froid | A : `moteur_ci/chaines_ci.py::concevoir_chaines_ci`, toujours -5 / 70 °C (`core/electrique/types.py::TEMP_FROID_DEFAUT_C`) ; B : `solar_design.py::string_design`, -5 °C | `services/chaines.py::concevoir_par_pan` avec `electrique.py::temperatures_site` (saisie > TMY de l'épingle > -5 / 70) ; puis `_longueur_chaine_retenue` compare à `core/calepinage/electrique.py::MODULES_PAR_CHAINE = 16` | températures différentes dès qu'une épingle existe ; « écart » mesuré contre une constante d'AO, jamais contre le devis |
| Production annuelle | A : `moteur_ci/production.py::bloc_production_ci` (PVGIS jours types, pertes 14 %, figée `production_figee`) ; B : `horaire/productible_pose.py::base_de_production` (pose réelle du calepinage, D-ACAL-36/44, nouveaux devis) ; écran `solar.js::productibleForCity` | `services/simulation.py::simuler_calepinage` (PVGIS série + cascade de pertes, sur geste seulement) ; atelier `result.annualKwh` (navigateur, 52 709 kWh sur le lead 1742) | trois chiffres possibles ; le calepinage ne lit AUCUNE clé d'étude du devis (grep `production_figee|etude_ci|taille_creation_ci|recommended_option` dans `apps/calepinage` : 0 résultat) |
| Autoconsommation | A : `moteur_ci/autoconso.py::bilan_horaire` ; ancien `solar_design.py::hourly_self_consumption` | `services/autoconsommation.py::bilan_autoconsommation` | deux bilans horaires |
| Consommation | A : facture MAD du lead par `etude_ci.py::CHEMINS_LEAD` (`consommation.facture_mad`) → profils du moteur C&I | `services/consommation.py::facture_mensuelle_du_lead` / `_profil_mensuel` (facture hiver/été, propre lecture) ; document `billKwh: null` sur le lead 1742 | deux lectures de la même facture |

Sens inverse (voulu, décision fondateur) : B et A lisent la production de la pose réelle du calepinage pour les
NOUVEAUX devis (`horaire/productible_pose.py`, D-ACAL-36/44/46). Un devis envoyé garde sa base rangée.

## 2. Lead 1742 — un écart par ligne

| Écart | Cause (`fichier::symbole`) | Statut | Changé par le L5 (`git log bfb859c90..HEAD`) | Correctif |
|---|---|---|---|---|
| Calepinage 9 lié au brouillon 554, pas au 564 envoyé | La re-liaison n'existe qu'à la RÉVISION (`calepinage/receivers.py::relier_calepinage_au_devis_revise`) ou à son abandon ; le calepinage n'est pas abonné à `core/events/devis.py::devis_sent` (abonnés : crm, onboarding) ; chaque devis automatique du lead est une v1 neuve, pas une révision ; ouvrir 564 dans l'atelier en fait une VARIANTE de C9 (`services/creation.py::_variante_de_l_ouvert_lie`) ; tout re-pointage est refusé tant que 554 reste actif (`services/liens.py::_refuser_repointage_d_un_actif`, 554 `is_active` vrai) | lue | non (receivers.py, liens.py intouchés ; creation.py : seulement ACAL1419) | C1-T1 |
| 48 panneaux au lieu de 35 (option recommandée) | La cible servie est l'option sans = 35 (`cible_depuis_lignes`, lue). 48 × 715 W = 34,32 kWc = contenance du toit à 30° du moteur C&I ET option avec. Le document dit `scenario: reseau`, `battery: null` : ce n'est pas l'option avec choisie ; remplissage automatique du toit (`noteToitRempli`) ou geste manuel | probable, à reproduire | aucun commit ne porte l'option | C1-T3 |
| Onduleur Deye hybride 20 kW (produit 30) au lieu du Huawei 20 kW (21) de l'option sans | `resultat.entree_electrique.onduleur_produit = 30` est une désignation EXPLICITE (écrite par `EtapeElectrique.jsx` / `ConfigurationsOnduleur.jsx` → `enregistrerEntreeElectrique`) ; elle prime sur la ligne du devis dans `resoudre_materiel` ; le défaut aurait rendu 21 | lue (qui a cliqué : à reproduire) | non | C1-T4 |
| Ratio 1,72 « au-dessus de la borne 1,35 » contre D-HYB-1 | Message de `electrique.py::_bloc_ratio_dc_ac`, borne `SOURCE_BORNE_NOYAU` ; le calepinage n'applique jamais la capacité `dc_max_kwc` d'un hybride (Deye 20 kW : 40 kWc publiés ; 34,32 < 40) | lue | **en partie** : ACAL1538 (`3dc0e36b9a`) rend « Non jugé » sans fourchette société, donc plus d'« à régler » ici ; mais une fourchette société rejugerait 1,72 sans D-HYB-1, et `dimensionner_onduleurs` émet encore « au-dessus du seuil d'alerte 1,50 » (remontée à l'écran : à reproduire) | C1-T5 |
| Longueur de chaîne 12 « contre 16 au dossier » | 16 n'est PAS le devis : c'est `core/calepinage/electrique.py::MODULES_PAR_CHAINE` (dossier d'appel d'offres, modules 625 W) comparé dans `electrique.py::_longueur_chaine_retenue` ; 12 = calcul sur les fiches. Le devis 564 option avec porte 4 protections DC par chaîne pour 48 panneaux, soit 12 par chaîne : faux écart | lue (12 côté devis : probable, déduit des quantités) | non (ACAL1540/1338 ne touchent que des textes) | C1-T6 |
| Production « non simulée », étape Résultats « à faire » | La simulation ne part que sur geste : `views/simulation.py::simuler` (POST) ou `services/simulation.py::recalculer_simulations_societe` ; rien à l'enregistrement ; la production figée du devis n'est pas lue | lue (un refus de simulation faute de pertes, D-ACAL-82 : à reproduire) | non (ACAL1602/1606/1607 changent le calcul, pas le déclencheur) | C1-T7 |

Pour qu'un calepinage de devis ENVOYÉ reprenne exactement le devis, sans rien recalculer : (1) il est lié au devis
envoyé (T1) ; (2) il lit par sélecteur l'option recommandée, son module × quantité, ses onduleurs × quantité, ses chaînes
et sa production figée (T2) ; (3) son entrée électrique est pré-remplie avec provenance « devis » — les options existent
déjà dans `electrique.py::_options_entree` (`nombre_onduleurs` ACAL633, `longueur_chaine_forcee`) (T4) ; (4) la cible
de l'atelier = la quantité de l'option retenue, et le document mémorise l'option (T3) ; (5) les contrôles jugent avec
les règles du devis (D-HYB-1) et plus jamais contre la constante 16 (T5, T6).

## 3. Chemin vers UN moteur

- **Lire du devis** (une fonction dans `apps/ventes/selectors_calepinage.py`, propriétaire `calepinage` d'après
  `check_ownership.py`) : option retenue, panneaux et module, onduleurs et nombre, chaînes (longueur, nombre),
  production figée (kWh/an et mensuel), hypothèses du calcul (bornes, températures). Jamais `apps.ventes.models`.
- **Cesser de recalculer**, pour un devis envoyé ou accepté : choix et nombre d'onduleurs (plafond AO 60 kWc), borne
  propre du ratio, comparaison à 16, production « à faire ». Ces contrôles restent en VÉRIFICATION (information), sans
  « à régler » contre un devis déjà reçu par le client.
- **Règles partagées, pas copiées** : la capacité d'un hybride (D-HYB-1) et la politique de températures vivent dans
  `core/electrique/` et sont importées par `moteur_ci` ET le calepinage.
- **Reste au calepinage** : géométrie et contenance réelle, ombrage, câblage du chantier (longueurs DC/AC mesurées,
  coffrets, protections), fixation et lestage, documents ; et la production de la pose réelle qui alimente les NOUVEAUX
  devis (D-ACAL-36/44/46, inchangé).

## 4. Tâches proposées (non inscrites)

- **C1-T1 — Le calepinage suit le devis envoyé du lead.** Constat : C9 reste sur le brouillon 554 ; le 564 envoyé n'a
  au mieux qu'une variante. Fichiers : `apps/calepinage/receivers.py` (abonné `devis_sent`), `services/liens.py`,
  `services/creation.py`. Fini quand : à l'envoi d'un devis S du lead, l'ouvert lié à un brouillon jamais envoyé du même
  lead est re-lié à S (chatter CAL26), test avec deux devis automatiques v1. Propriétaire : calepinage. Question au
  fondateur : le brouillon quitté garde-t-il une variante, ou rien ?
- **C1-T2 — Sélecteur « conception retenue du devis ».** Constat : aucune lecture des clés d'étude. Fichiers :
  `apps/ventes/selectors_calepinage.py` + contrat `apps/calepinage/contract_samples/` (contrat d'abord, PACT10). Fini
  quand : pour un devis « Les deux » recommandé sans, il rend `option: sans`, 35 × produit module, 1 × onduleur, chaînes,
  production figée ; recommandé avec ⇒ l'option avec. Propriétaire : calepinage.
- **C1-T3 — Le document mémorise l'option dessinée ; la cible suit l'option retenue.** Fichiers :
  `selectors_calepinage.py` (cible = option recommandée, plus `'sans'` en dur), `roofPro11/prefill.ts`, `roofPro11/cible.ts`.
  Fini quand : un pan rempli au-delà de la cible dit l'écart à l'option retenue, et `roof_layout` porte l'option.
  Propriétaire : calepinage.
- **C1-T4 — Entrée électrique d'un devis envoyé = celle du devis.** Fichiers : `services/electrique.py`
  (`resoudre_materiel`, `_options_entree`), `services/equipements.py`. Fini quand : sans saisie, onduleur, nombre et
  longueur de chaîne viennent de T2 avec provenance « devis » ; une saisie contraire est montrée comme écart au devis.
  Propriétaire : calepinage.
- **C1-T5 — D-HYB-1 dans le noyau partagé.** Fichiers : `core/electrique/onduleurs.py` (propriétaire calepinage),
  `apps/ventes/moteur_ci/onduleurs.py::_capacite_kwc` (propriétaire devis) ⇒ `docs/plans/PLAN_AUDIT_TRANSVERSE.md`. Fini
  quand : hybride Deye 20 kW + 34,32 kWc ⇒ ni alerte 1,50 ni « à régler », dans les deux moteurs, par la même fonction.
- **C1-T6 — Plus d'écart contre la longueur d'AO 16 pour un calepinage de devis.** Fichiers : `services/electrique.py::
  _longueur_chaine_retenue`. Fini quand : la référence est la longueur du devis (T2), le 16 ne sert qu'aux dossiers AO.
  Propriétaire : calepinage.
- **C1-T7 — Résultats d'un devis envoyé jamais vides.** Fichiers : `services/simulation.py`, `services/parcours_guide.py`.
  Fini quand : l'étape montre la production figée du devis (T2) à côté de la simulation, et la simulation part en tâche
  de fond à l'enregistrement d'une pose complète. Propriétaire : calepinage. Question au fondateur : lancer PVGIS à
  chaque enregistrement (coût en appels) ou seulement à l'ouverture de Résultats ?
- **C1-T8 — Une politique de températures de chaîne.** Fichiers : `apps/ventes/moteur_ci/chaines_ci.py` (devis),
  `apps/calepinage/services/electrique.py::temperatures_site` (calepinage) ⇒ plan transverse. Fini quand : devis et
  calepinage du même site calculent la même longueur maximale.

## 5. Requêtes de lecture à jouer (`manage.py shell`, transaction annulée, ASCII, identifiants seulement)

```python
from collections import Counter
from django.db import transaction
from apps.calepinage.models import Calepinage
from apps.ventes.models import Devis
from apps.ventes.services import cible_depuis_lignes
from apps.ventes.selectors import lignes_produits_calepinage
from apps.stock.selectors import type_fiche_produit, specs_for_produit
c, ex = Counter(), {}
def note(k, v):
    c[k] += 1; ex.setdefault(k, []).append(v) if len(ex.get(k, [])) < 15 else None
with transaction.atomic():
    for cal in Calepinage.objects.filter(archive_le__isnull=True, devis__isnull=False).select_related('devis').iterator():
        c['cal_lies'] += 1; d = cal.devis
        sent = Devis.objects.filter(company_id=cal.company_id, lead_id=cal.lead_id, is_active=True,
                                    statut__in=('envoye', 'accepte')).order_by('-date_envoi', '-id').first() if cal.lead_id else None
        if sent is not None and sent.pk != d.pk:
            note('lie_a_autre_que_dernier_envoye', (cal.pk, d.pk, d.statut, sent.pk))
        ref = sent or d
        ep = ref.etude_params if isinstance(ref.etude_params, dict) else {}
        rl = cal.roof_layout if isinstance(cal.roof_layout, dict) else {}
        n_cal = (rl.get('result') or {}).get('panels')
        n_sans = cible_depuis_lignes(ref).get('panneaux'); n_avec = cible_depuis_lignes(ref, variante='avec').get('panneaux')
        reco = 'avec' if 'avec' in str(ep.get('recommended_option', '')).lower() else 'sans'
        n_reco = n_avec if reco == 'avec' else n_sans
        if n_cal is not None and n_reco is not None and int(n_cal) != int(n_reco):
            note('panneaux_diff_option_recommandee', (cal.pk, ref.pk, n_cal, n_sans, n_avec, reco))
        ond_dev = [l['produit'].pk for l in lignes_produits_calepinage(ref) if type_fiche_produit(l['produit']) == 'onduleur']
        ent = (cal.resultat or {}).get('entree_electrique') or {}
        if ent.get('onduleur_produit') and ond_dev and int(ent['onduleur_produit']) not in ond_dev:
            note('onduleur_saisi_hors_option_sans', (cal.pk, ref.pk, ent['onduleur_produit'], ond_dev[:2]))
        if not (cal.resultat or {}).get('simulation'):
            note('sans_simulation', (cal.pk, ref.statut))
        if (cal.resultat or {}).get('journal_longueur_chaine'):
            note('ecart_longueur_vs_16', cal.pk)
    c['leads_multi_devis_v1'] = sum(1 for _ in Devis.objects.filter(version=1, lead__isnull=False).values('lead_id')
                                    .annotate(n=__import__('django').db.models.Count('id')).filter(n__gt=1))
    transaction.set_rollback(True)
print(dict(c)); [print(k, v) for k, v in ex.items()]
```

Ce script n'a PAS été exécuté (aucune base) : relire `Devis.version` et `LigneDevis.variante` à la première sortie.

## 6. Non couvert

Moteur agricole (`core/pompage`, `domain/creation_auto_agricole.py`) et le détail de `decider_taille` résidentiel : non
ouverts. Structure de `Devis.electrical_design` (chaînes du devis) non lue : tronquée dans le relevé de prod, d'où le
« 12 côté devis » seulement probable. Atelier : `estimatorBrainV6` et `consumption.ts` non lus. Origine exacte des 48
panneaux (remplissage ou geste) et remontée de l'alerte 1,50 après ACAL1538 : à reproduire sur la pile. Côté C2
(entrées par défaut, facture absente du document) : laissé à l'enquêteur C2.
