# -*- coding: utf-8 -*-
"""QJR431 (S3-N2, optionnel) — les appelants de ``calculer_etude_horaire``
survivent-ils au ``ValueError`` que le moteur peut désormais lever ?

PRÉMISSE REQUALIFIÉE — la docstring de ``hourly_self_consumption``
(``solar_design.py:2167-2171``, ``raise`` à ``:2195-2200``) est DÉJÀ honnête :
elle documente elle-même l'exception introduite par QJR146 (« SEULE
EXCEPTION… deux courbes NON VIDES de longueurs DIFFÉRENTES lèvent
``ValueError`` »). Il n'y a donc RIEN à corriger dans ce texte. La seule
question réelle : les QUATRE appelants de ``calculer_etude_horaire`` hors
tests (``etude_horaire_view.py:374``, ``etude_horaire.py`` — la fonction
``etude_horaire_pour_devis``, ``dimensionnement.py:1113``,
``offres_tailles.py:833``) gèrent-ils ce ``ValueError`` ?

CE QUE CE MODULE PROUVE (lecture de code + tests) :

1. Deux des quatre appelants sont DÉJÀ protégés, PAR LECTURE DE CODE : la
   fonction publique ``etude_horaire_pour_devis`` enveloppe son appel interne
   à ``calculer_etude_horaire`` dans un ``try/except Exception`` (« Ne lève
   JAMAIS : un calcul d'étude n'empêche pas d'enregistrer un devis » — sa
   propre docstring) ; ``offres_tailles.py:833`` fait de même
   (``try: ... except Exception: ... etude = None``). Les deux autres
   (``etude_horaire_view.py:374``, ``dimensionnement.py:1113``) N'ONT AUCUNE
   protection.
2. Le chemin qui produirait réellement la divergence est INATTEIGNABLE en
   production : ``jours_types_annee`` construit ``conso_24h`` ET ``prod_24h``
   à partir de deux silhouettes TOUJOURS longues de 24 (``forme`` — une
   composition de :data:`SILHOUETTES_OCCUPATION`, des tuples FIXES de 24
   valeurs, jamais tronquées ou allongées par
   ``_normaliser_a_un``/``_decaler_bloc`` — de pure permutation/échelle — ni
   par :func:`forme_consommation_detaillee`, qui ne fait qu'ADDITIONNER des
   énergies aux 24 index existants ; ``forme_prod`` — dont
   ``pvgis_profils.vers_heure_locale`` REFUSE explicitement toute forme dont
   la longueur n'est pas exactement 24, en rendant ``None`` sinon, ce qui
   fait SAUTER le mois entier avant tout appel à
   ``forme_consommation_detaillee``/``hourly_self_consumption``).

CE MODULE NE FABRIQUE AUCUN CORRECTIF POUR UN CHEMIN MORT : aucun
``try/except`` n'est ajouté aux deux appelants non protégés
(``etude_horaire_view.py``, ``dimensionnement.py`` — Files listés mais
NON modifiés, exactement ce que prescrit une tâche non atteignable). Les
tests ci-dessous restent une GARDE : si une future modification casse
l'invariant « 24 partout » (silhouette, forme de production, ou composeur),
``LongueurDesCourbesTest`` ROUGIT avant qu'un client ne voie un 500.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr431_appelants_etude_horaire"
"""
from datetime import date

from django.test import SimpleTestCase

from apps.parametres.pvgis_profils import vers_heure_locale
from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH
from apps.ventes.solar_design import hourly_self_consumption

VILLE = 'Casablanca'
CONSO = [900.0] * 12

PISCINE = {'piscine': {'kw': 1.4, 'heures': list(range(10, 18)),
                       'saisons': list(CJ.PISCINE_SAISONS),
                       'mode': 'redistribution', 'source': 'test'}}
CLIM = {'clim': {'kw': 2.0, 'heures': list(range(13, 22)),
                 'saisons': list(CJ.CLIM_SAISONS),
                 'mode': 'redistribution', 'source': 'test'}}
VE_TOUTE_SAISON = {'ve': {'kwh_jour': 6.0, 'heures': [21, 22, 23, 0, 1, 2],
                          'saisons': None, 'mode': 'addition',
                          'source': 'test'}}
#: Un VE dont la charge dépasse largement la facture mensuelle — le cas
#: dégénéré évoqué par ``renormalisation_redistribution`` (« la charge VE
#: déclarée dépasse à elle seule la facture »), celui le plus susceptible de
#: faire diverger une longueur si l'invariant venait à se relâcher un jour.
VE_DISPROPORTIONNE = {'ve': {'kwh_jour': 500.0, 'heures': [0, 1, 2],
                             'saisons': None, 'mode': 'addition',
                             'source': 'test'}}

TOUS_EQUIPEMENTS = dict(PISCINE, **CLIM, **VE_TOUTE_SAISON)

#: Occupations RÉELLES + une valeur INCONNUE (déclenche le repli
#: ``OCCUPATION_REPLI``) — jamais une exception sur une entrée mal formée.
OCCUPATIONS = (CJ.OCCUPATION_PRESENCE, CJ.OCCUPATION_ABSENCE,
               CJ.OCCUPATION_PARTIELLE, 'valeur-inconnue', None)

#: Dates couvrant un Ramadan MODÉLISÉ (fenêtre imsak/iftar réelle) et une
#: date hors table (après 2033, ``contexte_ramadan_du_mois`` rend alors
#: ``{}`` — chemin de repli, jamais une exception).
DATES = (date(2026, 3, 15), date(2026, 9, 2), date(2040, 1, 1))


class AtteignabiliteViaCalculerEtudeHoraireTest(SimpleTestCase):
    """Tente RÉELLEMENT de produire le ``ValueError`` par le seul chemin de
    production qui existe : ``calculer_etude_horaire`` (les quatre appelants
    de la tâche l'appellent tous, directement ou via
    ``etude_horaire_pour_devis``/le mini-balayage)."""

    def test_positif_hourly_self_consumption_leve_bien_sur_courbes_divergentes(self):
        """CONTRÔLE POSITIF : le mécanisme existe réellement — sans lui, un
        test qui ne trouve jamais le ValueError ne prouverait rien."""
        with self.assertRaises(ValueError):
            hourly_self_consumption(
                load_curve=[1.0] * 288, production_curve=[1.0] * 24)

    def test_rouge_si_un_jour_atteignable_aucune_combinaison_ne_leve_aujourd_hui(self):
        """ROUGE le jour où ce test échoue : ça voudrait dire qu'une
        combinaison réelle (équipements × occupation × date) a fini par
        produire des courbes de longueurs différentes à l'intérieur de
        ``calculer_etude_horaire`` — la preuve d'atteignabilité que cette
        tâche cherche. Aujourd'hui, VERT partout : inatteignable."""
        equipements_a_tester = (None, PISCINE, CLIM, VE_TOUTE_SAISON,
                                TOUS_EQUIPEMENTS, VE_DISPROPORTIONNE)
        for occupation in OCCUPATIONS:
            for equipements in equipements_a_tester:
                for jour_reference in DATES:
                    with self.subTest(occupation=occupation,
                                      equipements=list((equipements or {})),
                                      jour_reference=jour_reference):
                        try:
                            etude = EH.calculer_etude_horaire(
                                kwc=6.0, conso_kwh_mensuelles=CONSO,
                                ville=VILLE, occupation=occupation,
                                equipements=equipements,
                                batterie_kwh_utile=10.0,
                                jour_reference=jour_reference)
                        except ValueError as exc:
                            self.fail(
                                'ValueError atteint en production : %s '
                                '(occupation=%r, equipements=%r, '
                                'jour_reference=%r) — cette combinaison '
                                'DEVIENT le chemin d\'atteignabilité que '
                                'QJR431 cherchait ; les quatre appelants '
                                'doivent alors être corrigés.'
                                % (exc, occupation, equipements,
                                   jour_reference))
                        # ``None`` est un résultat honnête (règle Z2) — ce
                        # test ne juge que l'ABSENCE de ValueError.
                        if etude is not None:
                            self.assertIn('annuel', etude)


class LongueurDesCourbesTest(SimpleTestCase):
    """LA GARDE MÉCANISTE — pourquoi c'est inatteignable, pas seulement
    qu'il l'est. Si une future modification casse l'un de ces invariants,
    CE test rougit avant qu'un ``ValueError`` n'atteigne un appelant."""

    def test_vers_heure_locale_refuse_toute_longueur_hors_24(self):
        """Le verrou en amont de toute forme de PRODUCTION : 24 en entrée,
        24 en sortie, ou ``None`` — jamais une longueur intermédiaire."""
        self.assertEqual(len(vers_heure_locale([0.1] * 24)), 24)
        self.assertIsNone(vers_heure_locale([0.1] * 23))
        self.assertIsNone(vers_heure_locale([0.1] * 25))
        self.assertIsNone(vers_heure_locale([]))
        self.assertIsNone(vers_heure_locale(None))

    def test_silhouette_occupation_toujours_24_quelle_que_soit_l_entree(self):
        """Le verrou en amont de toute forme de CONSOMMATION : les tuples de
        :data:`SILHOUETTES_OCCUPATION` sont FIXES, et le repli
        (``OCCUPATION_REPLI``) s'applique à toute valeur inconnue — jamais
        une forme d'une autre longueur."""
        for occupation in OCCUPATIONS:
            for saison in (None,) + EH.SAISONS:
                forme = CJ.silhouette_occupation(occupation, saison=saison)
                self.assertEqual(
                    len(forme), 24,
                    'occupation=%r saison=%r' % (occupation, saison))
                self.assertAlmostEqual(sum(forme), 1.0, places=6)

    def test_forme_consommation_detaillee_toujours_24_meme_avec_ve_disproportionne(self):
        """Le composeur de forme n'ADDITIONNE que sur les 24 index déjà
        posés par la silhouette — un VE disproportionné grossit des heures,
        il n'allonge jamais la liste."""
        for equipements in (None, PISCINE, CLIM, VE_TOUTE_SAISON,
                            TOUS_EQUIPEMENTS, VE_DISPROPORTIONNE):
            for saison in EH.SAISONS:
                conso_24h, _couches = CJ.forme_consommation_detaillee(
                    20.0, CJ.OCCUPATION_PRESENCE, saison=saison,
                    equipements=equipements)
                self.assertEqual(len(conso_24h), 24,
                                 'equipements=%r saison=%r'
                                 % (equipements, saison))

    def test_jours_types_annee_rend_des_courbes_toujours_egales_en_longueur(self):
        """Le test le plus proche du call-site réel
        (``etude_horaire.py``, l'appel à ``hourly_self_consumption`` dans la
        boucle mensuelle) : les DOUZE jours types, sur la combinatoire
        adverse, ont TOUJOURS ``len(conso_24h) == len(prod_24h) == 24``."""
        equipements_a_tester = (None, PISCINE, CLIM, VE_TOUTE_SAISON,
                                TOUS_EQUIPEMENTS, VE_DISPROPORTIONNE)
        for occupation in OCCUPATIONS:
            for equipements in equipements_a_tester:
                jours_types, _avert, _sources = EH.jours_types_annee(
                    kwc=6.0, conso_kwh_mensuelles=CONSO, ville=VILLE,
                    occupation=occupation, equipements=equipements)
                if jours_types is None:
                    continue
                for jour in jours_types:
                    self.assertEqual(len(jour['conso_24h']), 24)
                    self.assertEqual(len(jour['prod_24h']), 24)
                    self.assertEqual(len(jour['conso_24h']),
                                     len(jour['prod_24h']))
