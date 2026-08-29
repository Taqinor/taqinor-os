"""QJR61 — ``etude_params`` : schéma, validateur, ÉCRIVAIN UNIQUE.

CE QUI ÉTAIT FAUX. Un PATCH partiel REMPLAÇAIT le bloc entier : toute clé que
l'émetteur ne reconstruisait pas lui-même — ``factures_mensuelles_reelles``,
``gamme``, ``etude_horaire``, ``dimensionnement`` — DISPARAISSAIT à la
sauvegarde suivante du vendeur.

CE QUE CES TESTS TIENNENT :

1. le validateur couvre les clés de tête déclarées (clé inconnue, mauvais type,
   ``None`` toléré) ;
2. ``ecrire`` FUSIONNE — un PATCH partiel ne perd plus RIEN ;
3. une clé DÉRIVÉE écrite par un NON-propriétaire est refusée, jamais ignorée ;
4. l'écriture est chirurgicale : ``update_fields=['etude_params']``.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_etude_schema -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.domain import etude_schema as S
from apps.ventes.models import Devis
from testkit.factories import CompanyFactory, DevisFactory


class _DevisEnMemoire:
    """Porteur minimal (pas de base) pour les tests purs de fusion."""

    pk = None

    def __init__(self, etude_params=None):
        self.etude_params = etude_params


class SchemaTests(SimpleTestCase):

    def test_les_cles_relevees_dans_l_arbre_sont_declarees(self):
        """Les ~24 clés de tête que le dépôt écrit ou lit réellement."""
        attendues = {
            'scenario', 'etude_horaire', 'simulation', 'dimensionnement',
            'puissance_kwc', 'gamme', 'toiture', 'payback_annees',
            'factures_mensuelles_reelles', 'conso_kwh_mensuelles',
            'production_annuelle', 'profils_comparatifs', 'nombre_proprietes',
            'autoconso_sans', 'autoconso_avec', 'resync_apres_envoi',
            'economies_annuelles', 'attribution', 'tension_raccordement',
            'origine', 'recommended_option', 'conso_annuelle', 'distributeur',
            'categorie_commerciale',
        }
        self.assertEqual(attendues - set(S.SCHEMA), set())

    def test_chaque_cle_declare_type_proprietaire_et_nature(self):
        for cle, regle in S.SCHEMA.items():
            with self.subTest(cle=cle):
                self.assertTrue(isinstance(regle['type'], tuple))
                self.assertTrue(regle['type'])
                self.assertIn(regle['nature'], (S.ENTREE, S.DERIVEE))
                self.assertTrue(regle['proprietaire'])

    def test_le_bloc_agricole_est_declare(self):
        for cle in ('pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h',
                    'm3_jour', 'champ_kwc', 'irrigation_method'):
            with self.subTest(cle=cle):
                self.assertIn(cle, S.SCHEMA)


class ContratRoundTripEcran(SimpleTestCase):
    """QJR66 / arbitrage orchestrateur (29/08/2026) — LE CONTRAT `?edit=`.

    Le mappeur de réouverture de brouillon (`DevisGenerator.jsx`) réinjecte ces
    clés de TÊTE dans le formulaire. Non déclarées, la fusion QJR62 les refuse
    en 400 et le round-trip meurt EN SILENCE : l'écran repose ses défauts
    (pompe immergée / triphasé / 20 m, raccordement BT) par-dessus le choix du
    vendeur, et l'enregistrement suivant les fige.

    Le pendant côté écran vit dans
    ``frontend/src/pages/ventes/DevisGeneratorRoundTripEtude.test.mjs``, qui
    lit CE fichier : les deux moitiés du contrat sont épinglées, chacune dans
    son langage.
    """

    #: Les entrées du marché AGRICOLE que `?edit=` relit.
    AGRICOLE = ('debit_souhaite_m3h', 'heures_pompage', 'type_pompe', 'alim',
                'profondeur_m', 'distance_m', 'region', 'crop', 'surface_ha',
                'current_fuel', 'fuel_spend_current', 'hmt_static',
                'hmt_drawdown')
    #: Les entrées du marché INDUSTRIEL / COMMERCIAL que `?edit=` relit
    #: (`tension_raccordement` est déclaré parmi les entrées générales).
    INDUSTRIEL_COMMERCIAL = ('tension_raccordement', 'repartition_mt',
                             'categorie_commerciale')
    #: Les réponses par catégorie commerciale
    #: (`solar.js: COMMERCIAL_CATEGORY_QUESTIONS`), relues à plat `e[q.key]`.
    REPONSES_COMMERCIALES = (
        'chambres', 'occupation_pct', 'piscine', 'chambres_froides',
        'horaires', 'cuisson', 'surface_vente_m2', 'effectif', 'clim', 'lits',
        'garde_nuit', 'internat', 'fermeture_estivale', 'surface_m2',
        'chauffe', 'four', 'cuisson_nocturne', 'temperature_consigne',
        'volume_m3', 'saisonnalite_recolte')

    def test_toutes_les_cles_du_round_trip_sont_declarees(self):
        for cle in (self.AGRICOLE + self.INDUSTRIEL_COMMERCIAL
                    + self.REPONSES_COMMERCIALES):
            with self.subTest(cle=cle):
                self.assertIn(cle, S.SCHEMA)

    def test_ce_sont_des_ENTREES_de_l_ecran_jamais_des_derivees(self):
        """Aucune n'est calculée par le moteur : le commercial les TAPE."""
        for cle in (self.AGRICOLE + self.INDUSTRIEL_COMMERCIAL
                    + self.REPONSES_COMMERCIALES):
            with self.subTest(cle=cle):
                self.assertEqual(S.SCHEMA[cle]['nature'], S.ENTREE)
                self.assertEqual(S.SCHEMA[cle]['proprietaire'], S.ECRAN)

    def test_l_ecran_peut_donc_toutes_les_ecrire(self):
        self.assertEqual(
            S.cles_refusees_pour(
                S.ECRAN, self.AGRICOLE + self.INDUSTRIEL_COMMERCIAL
                + self.REPONSES_COMMERCIALES), [])

    def test_un_bloc_de_marche_complet_passe_le_validateur(self):
        self.assertEqual(S.valider({
            'categorie_commerciale': 'hotel', 'chambres': 40,
            'occupation_pct': 62.5, 'piscine': True,
            'tension_raccordement': 'mt',
            'repartition_mt': {'pointe': 10, 'pleines': 50, 'creuses': 40},
        }), [])
        self.assertEqual(S.valider({
            'pompe_cv': 7.5, 'hmt_m': 60, 'debit_souhaite_m3h': 30,
            'heures_pompage': 7, 'type_pompe': 'immergee', 'alim': 'tri',
            'profondeur_m': 45, 'distance_m': 20, 'region': 'souss-massa',
            'crop': 'agrumes', 'surface_ha': 5, 'current_fuel': 'butane',
            'fuel_spend_current': 42000, 'hmt_static': 40,
            'hmt_drawdown': 15, 'irrigation_method': 'goutte',
        }), [])

    def test_un_booleen_deguise_en_nombre_reste_refuse(self):
        """La déclaration de type est utile, pas décorative."""
        self.assertEqual(len(S.valider({'chambres': True})), 1)
        self.assertEqual(len(S.valider({'piscine': 3})), 1)
        self.assertEqual(len(S.valider({'repartition_mt': [10, 50, 40]})), 1)


class EntreesDuMoteurTests(SimpleTestCase):
    """QJR66 / passe Fable — QUELLES clés font vieillir les études.

    La liste vit DANS le schéma (drapeau ``moteur``), pas dans l'endpoint :
    une clé ajoutée demain se déclare une seule fois, à côté de sa règle.
    """

    def test_les_entrees_du_moteur_sont_declarees(self):
        du_moteur = S.entrees_du_moteur()
        for cle in ('factures_mensuelles_reelles', 'conso_kwh_mensuelles',
                    'conso_annuelle', 'distributeur', 'scenario',
                    'nombre_proprietes'):
            with self.subTest(cle=cle):
                self.assertIn(cle, du_moteur)

    def test_une_cle_de_confort_n_est_PAS_du_moteur(self):
        """Sinon chaque frappe relancerait les quatre études pour rien."""
        du_moteur = S.entrees_du_moteur()
        for cle in ('origine', 'type_pompe', 'categorie_commerciale',
                    'recommended_option', 'region'):
            with self.subTest(cle=cle):
                self.assertNotIn(cle, du_moteur)

    def test_aucune_DERIVEE_n_est_une_entree_du_moteur(self):
        """Une sortie du moteur ne peut pas être ce qui le fait tourner."""
        for cle in S.entrees_du_moteur():
            with self.subTest(cle=cle):
                self.assertEqual(S.SCHEMA[cle]['nature'], S.ENTREE)

    def test_l_intersection_repond_faut_il_recalculer(self):
        self.assertEqual(
            S.entrees_du_moteur(['gamme', 'factures_mensuelles_reelles']),
            {'factures_mensuelles_reelles'})
        self.assertEqual(S.entrees_du_moteur(['gamme', 'origine']), set())
        # Une clé hors schéma n'est jamais du moteur.
        self.assertEqual(S.entrees_du_moteur(['chiffre_invente']), set())


class ValiderTests(SimpleTestCase):

    def test_un_bloc_vide_ou_nul_ne_reproche_rien(self):
        self.assertEqual(S.valider(None), [])
        self.assertEqual(S.valider({}), [])

    def test_une_cle_inconnue_est_reprochee_et_nommee(self):
        reproches = S.valider({'chiffre_invente': 42})
        self.assertEqual(len(reproches), 1)
        self.assertIn('chiffre_invente', reproches[0])

    def test_un_type_impossible_est_reproche(self):
        reproches = S.valider({'factures_mensuelles_reelles': 'six cents'})
        self.assertEqual(len(reproches), 1)
        self.assertIn('factures_mensuelles_reelles', reproches[0])

    def test_none_est_toujours_tolere(self):
        self.assertEqual(
            S.valider({'etude_horaire': None, 'gamme': None}), [])

    def test_un_bloc_reel_complet_passe(self):
        self.assertEqual(S.valider({
            'scenario': 'Les deux (Sans + Avec)',
            'puissance_kwc': 8.52,
            'factures_mensuelles_reelles': [640, 610, 590],
            'etude_horaire': {'kwc': 8.52},
            'dimensionnement': {'tableau': []},
            'nombre_proprietes': 2,
            'resync_apres_envoi': True,
        }), [])

    def test_un_booleen_n_est_pas_un_nombre(self):
        reproches = S.valider({'puissance_kwc': True})
        self.assertEqual(len(reproches), 1)


class ProprieteTests(SimpleTestCase):
    """Une clé DÉRIVÉE n'appartient qu'à l'étape QUI LA CALCULE."""

    def test_le_moteur_horaire_peut_ecrire_son_bloc(self):
        self.assertEqual(
            S.cles_refusees_pour(S.MOTEUR_HORAIRE, ['etude_horaire']), [])

    def test_l_ecran_ne_peut_pas_ecrire_le_bloc_horaire(self):
        self.assertEqual(
            S.cles_refusees_pour(S.ECRAN, ['etude_horaire']),
            ['etude_horaire'])

    def test_une_entree_est_ecrivable_par_n_importe_quelle_etape(self):
        for proprietaire in (None, S.ECRAN, S.AUTO_DEVIS, S.CALEPINAGE):
            with self.subTest(proprietaire=proprietaire):
                self.assertEqual(
                    S.cles_refusees_pour(
                        proprietaire, ['scenario', 'gamme',
                                       'factures_mensuelles_reelles']), [])

    def test_un_ecrivain_anonyme_ne_pose_aucune_derivee(self):
        self.assertEqual(
            S.cles_refusees_pour(None, ['dimensionnement']),
            ['dimensionnement'])


class FusionTests(SimpleTestCase):
    """``ecrire`` FUSIONNE — c'est toute la tâche."""

    def test_un_patch_partiel_ne_perd_plus_rien(self):
        depart = {
            'factures_mensuelles_reelles': [640, 610, 590],
            'gamme': 'premium',
            'etude_horaire': {'kwc': 8.52},
            'dimensionnement': {'tableau': [1, 2, 3]},
        }
        devis = _DevisEnMemoire(dict(depart))
        bloc = S.ecrire(devis, proprietaire=S.ECRAN, scenario='Sans batterie')
        self.assertEqual(bloc['scenario'], 'Sans batterie')
        for cle, valeur in depart.items():
            with self.subTest(cle=cle):
                self.assertEqual(bloc[cle], valeur)

    def test_none_retire_la_cle(self):
        devis = _DevisEnMemoire({'etude_horaire': {'kwc': 8.52},
                                 'gamme': 'premium'})
        bloc = S.ecrire(devis, proprietaire=S.MOTEUR_HORAIRE,
                        etude_horaire=None)
        self.assertNotIn('etude_horaire', bloc)
        self.assertEqual(bloc['gamme'], 'premium')

    def test_une_derivee_ecrite_par_un_non_proprietaire_leve(self):
        devis = _DevisEnMemoire({})
        with self.assertRaises(ValueError) as ctx:
            S.ecrire(devis, proprietaire=S.ECRAN,
                     dimensionnement={'tableau': []})
        self.assertIn('dimensionnement', str(ctx.exception))

    def test_une_cle_inconnue_leve(self):
        with self.assertRaises(ValueError):
            S.ecrire(_DevisEnMemoire({}), proprietaire=S.ECRAN,
                     chiffre_invente=42)

    def test_un_type_impossible_leve(self):
        with self.assertRaises(ValueError):
            S.ecrire(_DevisEnMemoire({}), proprietaire=S.ECRAN,
                     factures_mensuelles_reelles='six cents')


class EcritureChirurgicaleTests(TestCase):
    """``update_fields=['etude_params']`` : rien d'autre ne bouge."""

    def setUp(self):
        self.company = CompanyFactory()
        self.devis = DevisFactory(company=self.company,
                                  etude_params={'gamme': 'premium'})

    def test_la_fusion_est_persistee(self):
        S.ecrire(self.devis, proprietaire=S.ECRAN, scenario='Sans batterie')
        relu = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(relu.etude_params,
                         {'gamme': 'premium', 'scenario': 'Sans batterie'})

    def test_aucun_statut_aucune_ligne_ne_bouge(self):
        avant = self.devis.statut
        S.ecrire(self.devis, proprietaire=S.ECRAN, scenario='Sans batterie')
        relu = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(relu.statut, avant)
        self.assertEqual(relu.lignes.count(), 0)

    def test_le_gel_prix_par_kwc_reste_possible_apres(self):
        """``ecrire`` passe par ``Devis.save`` : le gel write-once garde donc
        son comportement d'origine — on ne le désactive pas en douce."""
        self.assertIsNone(
            Devis.objects.get(pk=self.devis.pk).prix_par_kwc)
        S.ecrire(self.devis, proprietaire=S.ECRAN, puissance_kwc=None)
        self.assertIsNone(
            Devis.objects.get(pk=self.devis.pk).prix_par_kwc)

    def test_un_devis_sans_pk_n_est_pas_persiste(self):
        devis = Devis(company=self.company, reference='DEV-QJR61-X',
                      taux_tva=Decimal('20'))
        bloc = S.ecrire(devis, proprietaire=S.ECRAN, scenario='Sans batterie')
        self.assertEqual(bloc['scenario'], 'Sans batterie')
        self.assertIsNone(devis.pk)


class FusionnerPureTests(SimpleTestCase):
    """QJR62 — la RÈGLE sans la persistance, pour les écrivains multi-colonnes."""

    def test_fusionner_ne_touche_pas_le_bloc_d_entree(self):
        depart = {'gamme': 'premium'}
        resultat = S.fusionner(depart, proprietaire=S.ECRAN,
                               scenario='Sans batterie')
        self.assertEqual(depart, {'gamme': 'premium'})
        self.assertEqual(set(resultat), {'gamme', 'scenario'})

    def test_fusionner_applique_les_memes_refus(self):
        with self.assertRaises(ValueError):
            S.fusionner({}, proprietaire=S.ECRAN,
                        dimensionnement={'tableau': []})
        with self.assertRaises(ValueError):
            S.fusionner({}, proprietaire=S.ECRAN, chiffre_invente=1)


class EndpointFusionTests(TestCase):
    """QJR62 — ``PATCH /ventes/devis/<id>/etude-params/`` FUSIONNE.

    L'écran reconstruisait ``etude_params`` de zéro et le PATCHait sur un
    sérialiseur permissif : chaque clé qu'il ne reconstruit pas lui-même
    DISPARAISSAIT à la sauvegarde suivante du vendeur.
    """

    DEPART = {
        'factures_mensuelles_reelles': [640, 610, 590],
        'gamme': 'premium',
        'etude_horaire': {'kwc': 8.52},
        'dimensionnement': {'tableau': [1, 2, 3]},
    }

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        from authentication.models import CustomUser
        from testkit.factories import UserFactory

        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company,
                                role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.devis = DevisFactory(company=self.company,
                                  etude_params=dict(self.DEPART))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/ventes/devis/{self.devis.id}/etude-params/'

    def test_un_patch_minimal_ne_perd_aucune_autre_cle(self):
        resp = self.api.patch(self.url, {'scenario': 'Sans batterie'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bloc = resp.data['etude_params']
        self.assertEqual(bloc['scenario'], 'Sans batterie')
        for cle, valeur in self.DEPART.items():
            with self.subTest(cle=cle):
                self.assertEqual(bloc[cle], valeur)

    def test_le_get_rend_le_bloc_courant(self):
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['etude_params'], self.DEPART)

    def test_une_cle_derivee_du_moteur_est_refusee_en_400(self):
        resp = self.api.patch(self.url, {'etude_horaire': {'kwc': 1}},
                              format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('etude_horaire', resp.data['detail'])

    def test_une_cle_inconnue_est_refusee_en_400(self):
        resp = self.api.patch(self.url, {'chiffre_invente': 42},
                              format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_un_corps_vide_est_refuse(self):
        resp = self.api.patch(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_null_retire_la_cle(self):
        resp = self.api.patch(self.url, {'gamme': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('gamme', resp.data['etude_params'])
        self.assertIn('factures_mensuelles_reelles',
                      resp.data['etude_params'])

    def test_une_entree_du_moteur_relance_les_etudes(self):
        """QJR66 / passe Fable — LES ÉTUDES SUIVENT LEURS ENTRÉES.

        L'écran écrit désormais ses factures réelles par CET endpoint, donc
        APRÈS le rafraîchissement déclenché par l'écriture des lignes : sans ce
        rappel, le PDF servait des économies dérivées d'entrées PÉRIMÉES.
        """
        from unittest.mock import patch as _patch
        with _patch('apps.ventes.services.rafraichir_etudes_du_devis') as faux:
            resp = self.api.patch(
                self.url, {'factures_mensuelles_reelles': [700] * 12},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(faux.call_count, 1)
        self.assertEqual(faux.call_args.args[0].pk, self.devis.pk)

    def test_une_cle_hors_moteur_ne_relance_RIEN(self):
        """Sinon chaque frappe paierait les quatre études pour rien."""
        from unittest.mock import patch as _patch
        with _patch('apps.ventes.services.rafraichir_etudes_du_devis') as faux:
            resp = self.api.patch(self.url, {'origine': 'salon'},
                                  format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        faux.assert_not_called()

    def test_une_etude_qui_echoue_n_annule_pas_l_entree(self):
        """Best-effort : l'entrée du vendeur est enregistrée quoi qu'il arrive."""
        from unittest.mock import patch as _patch
        with _patch('apps.ventes.services.rafraichir_etudes_du_devis',
                    side_effect=RuntimeError('moteur cassé')):
            resp = self.api.patch(
                self.url, {'factures_mensuelles_reelles': [700] * 12},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['factures_mensuelles_reelles'],
                         [700] * 12)

    def test_isolation_multi_societe(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = self.api.get(
            f'/api/django/ventes/devis/{autre.id}/etude-params/')
        self.assertEqual(resp.status_code, 404)


class EcrivainsRoutesTests(TestCase):
    """QJR62 — les écrivains backend passent par ``ecrire()``."""

    def setUp(self):
        self.company = CompanyFactory()
        self.devis = DevisFactory(
            company=self.company,
            etude_params={'factures_mensuelles_reelles': [640, 610]})

    def test_set_gamme_fusionne_au_lieu_de_remplacer(self):
        from apps.ventes.services import _set_gamme

        _set_gamme(self.devis, nom='Premium')
        relu = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(relu.etude_params['gamme'], {'nom': 'Premium'})
        self.assertEqual(relu.etude_params['factures_mensuelles_reelles'],
                         [640, 610])
