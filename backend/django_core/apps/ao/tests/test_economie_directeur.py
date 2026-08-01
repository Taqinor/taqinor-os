"""AOF157 — économie DIRECTEUR : table SÉPARÉE, permission ÉLEVÉE.

Ce qui est prouvé ici :

* **aucune référence à ces modèles dans les serializers AO généraux** ni aucun
  champ de coût/marge sur ``AppelOffre``, le bordereau ou une variante
  (introspection — la règle est vérifiable en machine, pas relue à l'œil) ;
* **403 pour Responsable / Commercial / Technicien / Utilisateur**, 200 pour
  Directeur ;
* **le cas réel est reproduit AU DIRHAM** : coût de revient 2 666 600 HT
  (dont panneaux 492 800 au régime réduit), bénéfice net visé 1 500 000 →
  total 4 166 600 HT / 4 999 920 TTC, TVA nette à reverser 349 280, marge
  36,00 %, **contrôle de trésorerie == bénéfice, écart 0** ;
* le point ouvert signalé au comptable est chiffré : ventiler les panneaux à
  10 % à la VENTE baisserait le TTC de 165 200 sans changer le bénéfice HT.

Run :
    python manage.py test apps.ao.tests.test_economie_directeur -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services_directeur
from apps.ao.models import (
    AppelOffre, BordereauPrix, CibleFinanciere, EconomieAO, LigneCoutRevient,
    VarianteCalepinage,
)
from apps.roles.models import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS, ELEVATED_PERMISSIONS,
    RESPONSABLE_PERMISSIONS, Role,
)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/economie/'

#: Les postes RÉELS du dossier. Les panneaux (880 MAD × 560 modules) sont au
#: régime réduit ; tout le reste au régime standard.
POSTES = (
    ('panneaux', 'Modules photovoltaïques', '560', 'U', '880.0000', 'reduit'),
    ('structure', 'Structure de pose', '560', 'U', '495.0000', 'standard'),
    ('garantie_onduleurs', 'Extension de garantie onduleurs', '1', 'Ens',
     '30000.0000', 'standard'),
    ('cable_solaire', 'Câble solaire (métré DOUBLÉ)', '16000', 'ml',
     '11.0000', 'standard'),
    ('cable_ac', 'Câble 16 mm²', '1', 'Ens', '5500.0000', 'standard'),
    ('main_oeuvre', "Main d'œuvre", '1', 'Ens', '140000.0000', 'standard'),
    ('aleas', 'Aléas', '1', 'Ens', '65000.0000', 'standard'),
    ('onduleurs', 'Onduleurs, stockage, coffrets et équipements', '1', 'Ens',
     '1480100.0000', 'standard'),
)


class TestCloisonnement(SimpleTestCase):
    """L'économie ne fuit par AUCUNE surface non-directeur."""

    def test_aucun_champ_de_cout_sur_l_appel_offre(self):
        noms = {f.name for f in AppelOffre._meta.get_fields()}
        for interdit in ('cout_revient', 'cout_de_revient', 'marge',
                         'marge_pct', 'benefice', 'benefice_net',
                         'prix_achat'):
            self.assertNotIn(interdit, noms, interdit)

    def test_aucun_champ_de_cout_sur_le_bordereau_ni_une_variante(self):
        from apps.ao.models import LigneBordereau

        for modele in (BordereauPrix, LigneBordereau, VarianteCalepinage):
            noms = {f.name for f in modele._meta.get_fields()}
            for interdit in ('cout_revient', 'marge', 'benefice',
                             'prix_achat', 'cout_unitaire'):
                self.assertNotIn(interdit, noms, f'{modele.__name__}.{interdit}')

    def test_les_serializers_ao_generaux_ignorent_l_economie(self):
        """Test d'INTROSPECTION : aucune référence dans le module général."""
        from pathlib import Path

        import apps.ao.serializers as serializers_generaux

        source = Path(serializers_generaux.__file__).read_text(
            encoding='utf-8')
        for interdit in ('EconomieAO', 'LigneCoutRevient', 'CibleFinanciere',
                         'cout_revient', 'benefice_net', 'marge_pct'):
            self.assertNotIn(interdit, source, interdit)

    def test_les_vues_ao_generales_ignorent_l_economie(self):
        from pathlib import Path

        import apps.ao.views as vues_generales
        import apps.ao.viewsets as viewsets_generaux

        for module in (vues_generales, viewsets_generaux):
            source = Path(module.__file__).read_text(encoding='utf-8')
            for interdit in ('EconomieAO', 'LigneCoutRevient',
                             'CibleFinanciere'):
                self.assertNotIn(interdit, source,
                                 f'{module.__name__}:{interdit}')

    def test_la_permission_est_ELEVEE(self):
        self.assertIn('ao_rentabilite_voir', ELEVATED_PERMISSIONS)

    def test_aucun_role_non_direction_ne_la_porte(self):
        for liste in (RESPONSABLE_PERMISSIONS, COMMERCIAL_PERMISSIONS):
            self.assertNotIn('ao_rentabilite_voir', liste)


class BaseEconomie(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF157 Co',
                                              slug='aof157-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-157-1', objet='Économie')
        self.economie = services_directeur.creer_economie(
            self.ao, benefice_net_cible_ht=Decimal('1500000.00'),
            motif='Cible initiale', seuil_psychologique=Decimal('5000000.00'))
        for ordre, (poste, designation, quantite, unite, pu,
                    regime) in enumerate(POSTES):
            LigneCoutRevient.objects.create(
                company=self.company, economie=self.economie, poste=poste,
                designation=designation, quantite=Decimal(quantite),
                unite=unite, prix_unitaire_ht=Decimal(pu),
                regime_tva=regime, ordre=ordre)


class TestCasReelAuDirham(BaseEconomie):
    def test_cout_de_revient(self):
        self.assertEqual(self.economie.cout_revient_ht,
                         Decimal('2666600.00'))

    def test_ventilation_des_regimes_de_tva_sur_achats(self):
        self.assertEqual(self.economie.cout_regime_reduit_ht,
                         Decimal('492800.00'))
        self.assertEqual(self.economie.cout_regime_standard_ht,
                         Decimal('2173800.00'))

    def test_tva_deductible_differenciee(self):
        # 10 % sur 492 800 + 20 % sur 2 173 800.
        self.assertEqual(self.economie.tva_deductible, Decimal('484040.00'))

    def test_benefice_net_vise_exactement(self):
        self.assertEqual(self.economie.benefice_net_cible_ht,
                         Decimal('1500000.00'))

    def test_totaux_ht_et_ttc(self):
        self.assertEqual(self.economie.total_ht, Decimal('4166600.00'))
        self.assertEqual(self.economie.tva_collectee, Decimal('833320.00'))
        self.assertEqual(self.economie.total_ttc, Decimal('4999920.00'))

    def test_tva_nette_a_reverser(self):
        self.assertEqual(self.economie.tva_nette_a_reverser,
                         Decimal('349280.00'))

    def test_marge(self):
        self.assertEqual(self.economie.marge_pct, Decimal('36.00'))

    def test_controle_de_tresorerie_egale_le_benefice_ecart_zero(self):
        """Le contrôle du classeur : écart 0, ou le classeur est rouge."""
        self.assertEqual(self.economie.controle_tresorerie,
                         Decimal('1500000.00'))
        self.assertEqual(self.economie.ecart_tresorerie, Decimal('0.00'))

    def test_le_ttc_reste_sous_la_barre_des_cinq_millions(self):
        self.assertTrue(self.economie.sous_seuil_psychologique)
        self.assertLess(self.economie.total_ttc, Decimal('5000000.00'))

    def test_point_ouvert_ventiler_les_panneaux_a_dix_pourcent(self):
        """Le point signalé au comptable, CHIFFRÉ.

        Les modules vendus 2 950 MAD/U × 560 = 1 652 000 HT. Les ventiler à
        10 % au lieu de 20 % baisse le TTC de 165 200 SANS toucher au
        bénéfice HT.
        """
        base_panneaux_vente = Decimal('560') * Decimal('2950.00')
        self.assertEqual(base_panneaux_vente, Decimal('1652000.00'))
        economie_tva = (base_panneaux_vente
                        * (Decimal('20.00') - Decimal('10.00'))
                        / Decimal('100'))
        self.assertEqual(economie_tva, Decimal('165200.00'))
        # Le bénéfice HT, lui, ne bouge pas d'un dirham.
        self.assertEqual(self.economie.benefice_net_cible_ht,
                         Decimal('1500000.00'))


class TestVersionsDeCible(BaseEconomie):
    def test_la_premiere_version_est_active(self):
        cible = self.economie.cible
        self.assertEqual(cible.version, 1)
        self.assertTrue(cible.active)
        self.assertEqual(cible.motif, 'Cible initiale')

    def test_une_nouvelle_version_desactive_la_precedente(self):
        deuxieme = services_directeur.nouvelle_cible(
            self.economie, benefice_net_cible_ht=Decimal('1400000.00'),
            motif='Concurrence agressive')
        self.assertEqual(deuxieme.version, 2)
        self.economie.refresh_from_db()
        self.assertEqual(self.economie.cible.pk, deuxieme.pk)
        self.assertEqual(
            CibleFinanciere.objects.filter(
                economie=self.economie, active=True).count(), 1)

    def test_l_historique_reste_consultable(self):
        services_directeur.nouvelle_cible(
            self.economie, benefice_net_cible_ht=Decimal('1400000.00'),
            motif='v2')
        services_directeur.nouvelle_cible(
            self.economie, benefice_net_cible_ht=Decimal('1500000.00'),
            motif='v3')
        versions = list(CibleFinanciere.objects.filter(
            economie=self.economie).order_by('version'))
        self.assertEqual([c.version for c in versions], [1, 2, 3])
        self.assertEqual([c.motif for c in versions],
                         ['Cible initiale', 'v2', 'v3'])

    def test_l_auteur_est_pose_cote_serveur(self):
        user = User.objects.create_user(
            username='aof157_dir', password='x', company=self.company)
        cible = services_directeur.nouvelle_cible(
            self.economie, benefice_net_cible_ht=Decimal('1450000.00'),
            motif='Ajustement', user=user)
        self.assertEqual(cible.auteur_id, user.id)

    def test_le_total_suit_la_cible_active(self):
        services_directeur.nouvelle_cible(
            self.economie, benefice_net_cible_ht=Decimal('1000000.00'),
            motif='Baisse')
        self.economie.refresh_from_db()
        self.assertEqual(self.economie.total_ht, Decimal('3666600.00'))

    def test_le_chatter_ne_publie_pas_le_montant(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        services_directeur.nouvelle_cible(
            self.economie, benefice_net_cible_ht=Decimal('1400000.00'),
            motif='Concurrence')
        ct = ContentType.objects.get_for_model(AppelOffre)
        entree = Activity.objects.filter(
            content_type=ct, object_id=self.ao.pk,
            field='cible_financiere').first()
        self.assertIsNotNone(entree)
        for valeur in (entree.old_value, entree.new_value, entree.body):
            self.assertNotIn('1400000', valeur)


class TestPermissions(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF157 API',
                                              slug='aof157-api')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-157-API', objet='API')
        self.economie = services_directeur.creer_economie(
            self.ao, benefice_net_cible_ht=Decimal('1500000.00'))

    def _client_pour(self, nom_role, permissions):
        role = Role.objects.create(
            company=self.company, nom=nom_role,
            permissions=list(permissions))
        user = User.objects.create_user(
            username=f'aof157_{nom_role.lower()}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_403_pour_responsable(self):
        api = self._client_pour('Responsable', RESPONSABLE_PERMISSIONS)
        self.assertEqual(api.get(URL).status_code, 403)

    def test_403_pour_commercial(self):
        api = self._client_pour('Commercial', COMMERCIAL_PERMISSIONS)
        self.assertEqual(api.get(URL).status_code, 403)

    def test_403_pour_un_role_sans_permission(self):
        api = self._client_pour('Technicien', ['crm_voir'])
        self.assertEqual(api.get(URL).status_code, 403)

    def test_403_pour_un_compte_sans_role(self):
        user = User.objects.create_user(
            username='aof157_viewer', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self.assertEqual(api.get(URL).status_code, 403)

    def test_200_pour_directeur(self):
        api = self._client_pour('Directeur', DIRECTEUR_PERMISSIONS)
        reponse = api.get(URL)
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_la_synthese_est_derivee(self):
        api = self._client_pour('Directeur', DIRECTEUR_PERMISSIONS)
        reponse = api.get(f'{URL}{self.economie.id}/synthese/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['benefice_net_cible_ht'], '1500000.00')
        self.assertEqual(reponse.data['ecart_tresorerie'], '0.00')

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF157 X', slug='aof157-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-157-X', objet='X')
        services_directeur.creer_economie(ao)
        api = self._client_pour('Directeur', DIRECTEUR_PERMISSIONS)
        reponse = api.get(URL)
        lignes = reponse.data['results'] if isinstance(reponse.data, dict) \
            and 'results' in reponse.data else reponse.data
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['appel_offre'], self.ao.id)


class TestVerrou(BaseEconomie):
    def test_le_verrou_est_un_champ(self):
        self.assertFalse(self.economie.verrouillee)
        self.economie.verrouillee = True
        self.economie.save(update_fields=['verrouillee'])
        self.economie.refresh_from_db()
        self.assertTrue(self.economie.verrouillee)

    def test_une_economie_verrouillee_refuse_l_ecriture_par_l_api(self):
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(
            username='aof157_verrou', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        api.post(f'{URL}{self.economie.id}/verrouiller/', {}, format='json')
        reponse = api.patch(
            f'{URL}{self.economie.id}/',
            {'note_comptable': 'Tentative'}, format='json')
        self.assertEqual(reponse.status_code, 403, reponse.data)


class TestSeparationAvecLaSimulationClient(BaseEconomie):
    """AOF135 (client) et AOF157 (directeur) ne se confondent jamais."""

    def test_deux_tables_distinctes(self):
        from apps.ao.models import SimulationRentabilite

        self.assertNotEqual(EconomieAO._meta.db_table,
                            SimulationRentabilite._meta.db_table)

    def test_la_simulation_client_ne_pointe_pas_l_economie(self):
        from apps.ao.models import SimulationRentabilite

        cibles = {getattr(f, 'related_model', None)
                  for f in SimulationRentabilite._meta.get_fields()}
        self.assertNotIn(EconomieAO, cibles)
        self.assertNotIn(LigneCoutRevient, cibles)
        self.assertNotIn(CibleFinanciere, cibles)
