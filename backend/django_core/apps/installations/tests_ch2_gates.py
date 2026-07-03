"""
CH2 — Gates BLOQUANTS appliqués sur le cycle de vie chantier.

Couvre :
  * une étape BLOQUANTE aux exigences non réunies REFUSE le changement de
    statut (message français explicite), une fois les exigences réunies elle
    passe ;
  * une étape NON BLOQUANTE laisse avancer librement (consultative) ;
  * une société SANS étapes configurées garde EXACTEMENT le comportement
    historique (aucun blocage — interrupteur) ;
  * les points d'arrêt QHSE sont lus via ``apps.qhse.selectors`` (référence
    lâche par chantier_id) et bloquent une étape bloquante tant qu'ils ne sont
    pas levés ;
  * les effets de bord existants (consommation du stock à « Installé », remise
    de garantie/parc à « Réceptionné ») tirent toujours sur les gates mappés ;
  * l'action ``avancer-etape`` applique les mêmes gates.

Run :
    python manage.py test apps.installations.tests_ch2_gates -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, StageModele
from apps.installations.services import (
    seed_stages, verifier_transition_statut,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ch2-co-{n}', defaults={'nom': f'CH2 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ch2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, statut=Installation.Statut.SIGNE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='CH2',
        email=f'ch2-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-CH2-{n}', client=client,
        statut=statut)


class GateBlockingServiceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def test_gate_dossier_bloque_puis_autorise(self):
        # « Autorisations » est bloquante et exige le dossier 82-21 approuvé.
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        inst.regime_8221 = Installation.Regime8221.ACCORD_RACCORDEMENT
        inst.dossier_statut = Installation.DossierStatut.A_DEPOSER
        inst.save(update_fields=['regime_8221', 'dossier_statut'])
        # Passer à MATERIEL_COMMANDE franchit « approvisionnement » (matériel)
        # ET « autorisations » (dossier) — le dossier non approuvé bloque.
        raisons = verifier_transition_statut(
            inst, Installation.Statut.MATERIEL_COMMANDE)
        self.assertTrue(raisons)
        self.assertTrue(any('82-21' in r for r in raisons))
        # Dossier approuvé + aucun manque matériel → transition autorisée.
        inst.dossier_statut = Installation.DossierStatut.APPROUVE
        inst.save(update_fields=['dossier_statut'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.MATERIEL_COMMANDE)
        self.assertEqual(raisons, [])

    def test_gate_tests_bloque_mise_en_service(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        # « Mise en service » (IEC 62446-1) exige des essais enregistrés.
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertTrue(any('service' in r.lower() for r in raisons))
        inst.mes_production_test = Decimal('5.2')
        inst.save(update_fields=['mes_production_test'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertEqual(raisons, [])

    def test_etape_non_bloquante_ne_bloque_pas(self):
        # Rendre « autorisations » NON bloquante : plus aucun blocage même
        # avec un dossier non approuvé.
        StageModele.objects.filter(
            company=self.company, cle='autorisations').update(bloquant=False)
        StageModele.objects.filter(
            company=self.company, cle='approvisionnement').update(
            bloquant=False)
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        inst.regime_8221 = Installation.Regime8221.ACCORD_RACCORDEMENT
        inst.dossier_statut = Installation.DossierStatut.A_DEPOSER
        inst.save(update_fields=['regime_8221', 'dossier_statut'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.MATERIEL_COMMANDE)
        self.assertEqual(raisons, [])

    def test_recul_de_statut_jamais_bloque(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.INSTALLE)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.SIGNE)
        self.assertEqual(raisons, [])

    def test_societe_sans_etapes_configurees_comportement_historique(self):
        autre = make_company()  # aucune étape amorcée
        inst = make_installation(autre, statut=Installation.Statut.SIGNE)
        inst.regime_8221 = Installation.Regime8221.ACCORD_RACCORDEMENT
        inst.dossier_statut = Installation.DossierStatut.A_DEPOSER
        inst.save(update_fields=['regime_8221', 'dossier_statut'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.RECEPTIONNE)
        self.assertEqual(raisons, [])


class GateQhseHoldPointTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def _plan_avec_hold_point(self, chantier_id, conforme=None):
        from apps.qhse.models import (
            PlanInspectionModele, PointControleModele,
            PlanInspectionChantier, ReleveControle,
        )
        modele = PlanInspectionModele.objects.create(
            company=self.company, nom='ITP CH2')
        plan = PlanInspectionChantier.objects.create(
            company=self.company, modele=modele, chantier_id=chantier_id)
        point = PointControleModele.objects.create(
            company=self.company, plan=modele, intitule='Serrage câblage DC',
            hold_point=True)
        if conforme is not None:
            ReleveControle.objects.create(
                company=self.company, plan_chantier=plan, point=point,
                conforme=conforme)
        return plan, point

    def test_hold_point_non_leve_bloque_gate_bloquant(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        inst.mes_production_test = Decimal('4.0')  # essais OK
        inst.save(update_fields=['mes_production_test'])
        self._plan_avec_hold_point(inst.id, conforme=None)
        # « Mise en service » est bloquante → la porte QHSE est interrogée.
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertTrue(any("arrêt qhse" in r.lower()
                            for r in raisons), raisons)

    def test_hold_point_leve_debloque(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        inst.mes_production_test = Decimal('4.0')
        inst.save(update_fields=['mes_production_test'])
        self._plan_avec_hold_point(inst.id, conforme=True)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertEqual(raisons, [])


class GateApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_patch_statut_bloque_renvoie_400(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        r = self.api.patch(
            f'{BASE}/chantiers/{inst.id}/',
            {'statut': Installation.Statut.INSTALLE}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('statut', r.data)

    def test_patch_statut_autorise_apres_exigences(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        inst.mes_production_test = Decimal('6.0')
        inst.save(update_fields=['mes_production_test'])
        r = self.api.patch(
            f'{BASE}/chantiers/{inst.id}/',
            {'statut': Installation.Statut.INSTALLE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertEqual(inst.statut, Installation.Statut.INSTALLE)

    def test_effet_de_bord_stock_conserve_sur_gate_mappe(self):
        # Le passage à « Installé » consomme la réservation de stock (N14).
        from apps.stock.models import Produit, EmplacementStock
        produit = Produit.objects.create(
            company=self.company, nom='Panneau CH2',
            prix_vente=Decimal('100'), quantite_stock=10)
        EmplacementStock.objects.create(company=self.company, nom='Dépôt')
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        inst.mes_production_test = Decimal('6.0')
        inst.bom = [{'produit_id': produit.id, 'designation': 'Panneau CH2',
                     'quantite': 4}]
        inst.save(update_fields=['mes_production_test', 'bom'])
        from apps.installations.services import seed_reservations
        seed_reservations(inst)
        r = self.api.patch(
            f'{BASE}/chantiers/{inst.id}/',
            {'statut': Installation.Statut.INSTALLE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 6)  # 10 − 4 consommés

    def test_etapes_endpoint_liste_les_gates(self):
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        r = self.api.get(f'{BASE}/chantiers/{inst.id}/etapes/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['etapes']), 10)
        self.assertEqual(r.data['etape_courante'], 'etude_site')
        # Chaque étape porte son verdict de gate.
        mes = next(e for e in r.data['etapes'] if e['cle'] == 'mise_en_service')
        self.assertTrue(mes['bloquant'])
        self.assertFalse(mes['satisfait'])
        self.assertTrue(mes['raisons'])

    def test_avancer_etape_bloque_puis_passe(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        r = self.api.post(
            f'{BASE}/chantiers/{inst.id}/avancer-etape/',
            {'etape': 'mise_en_service'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('raisons', r.data)
        inst.mes_production_test = Decimal('6.0')
        inst.save(update_fields=['mes_production_test'])
        r = self.api.post(
            f'{BASE}/chantiers/{inst.id}/avancer-etape/',
            {'etape': 'mise_en_service'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertEqual(inst.etape.cle, 'mise_en_service')
        self.assertEqual(inst.statut, Installation.Statut.INSTALLE)
