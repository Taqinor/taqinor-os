"""
NTP2P2 — Plan d'approbation générique pour les demandes d'achat.

Couvre :
  * CRITÈRE D'ACCEPTATION : une demande dépassant le seuil configuré exige N
    approbateurs SÉQUENTIELS avant de pouvoir être convertie en BCF ;
  * sans règle active, le cycle FG310 historique est INCHANGÉ (soumettre →
    approuver direct) — non-régression ;
  * ``approuver`` est refusé (400) tant qu'une étape reste en attente ;
  * l'ordre des étapes est imposé (approuver l'étape 2 avant la 1 → 400) ;
  * un rejet d'étape bascule la demande ``refusee`` et annule les étapes
    restantes ;
  * arbitrage de la règle la plus spécifique (priorité, puis périmètre
    chantier, puis intervalle le plus étroit) ;
  * scope société : la règle d'une autre société n'est ni vue ni appliquée.

Run :
    python manage.py test apps.installations.tests_ntp2p2_approbation_achat -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntp2p2-co-{n}', defaults={'nom': f'NTP2P2 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_demande(company, user, *, montant, quantite=1, chantier=None):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-TEST-{next(_seq):04d}',
        objet='Réquisition de test', created_by=user, chantier=chantier)
    DemandeAchatLigne.objects.create(
        demande=da, designation='Article', quantite=quantite,
        prix_estime=montant)
    return da


class ApprobationAchatSansRegleTests(TestCase):
    """Non-régression : sans règle, le cycle FG310 est byte-identique."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_soumettre_ne_cree_aucune_etape_sans_regle(self):
        da = make_demande(self.company, self.user, montant=99000)
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], DemandeAchat.Statut.SOUMISE)
        self.assertEqual(da.etapes_approbation.count(), 0)

    def test_approuver_direct_reste_possible_sans_regle(self):
        da = make_demande(self.company, self.user, montant=99000)
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/approuver/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], DemandeAchat.Statut.APPROUVEE)


class ApprobationAchatSequentielleTests(TestCase):
    """CRITÈRE D'ACCEPTATION — N approbateurs séquentiels au-delà du seuil."""

    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        self.appro1 = make_user(self.company, role='responsable')
        self.appro2 = make_user(self.company, role='admin')
        self.api = auth(self.demandeur)
        self.regle = RegleApprobationAchat.objects.create(
            company=self.company, libelle='Au-delà de 20 000 MAD',
            montant_min=20000, nombre_approbateurs=2,
            niveau_approbation=(
                RegleApprobationAchat.NiveauApprobation.DIRECTION))

    def _soumettre(self, montant=50000):
        da = make_demande(self.company, self.demandeur, montant=montant)
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        return da

    def test_soumission_instancie_deux_etapes_sequentielles(self):
        da = self._soumettre()
        etapes = list(da.etapes_approbation.order_by('niveau'))
        self.assertEqual(len(etapes), 2)
        self.assertEqual([e.niveau for e in etapes], [1, 2])
        self.assertTrue(all(
            e.statut == EtapeApprobationAchat.Statut.EN_ATTENTE
            for e in etapes))
        self.assertTrue(all(e.company_id == self.company.id for e in etapes))
        self.assertTrue(all(e.regle_id == self.regle.pk for e in etapes))

    def test_demande_sous_le_seuil_nest_pas_soumise_a_approbation(self):
        da = make_demande(self.company, self.demandeur, montant=1000)
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(da.etapes_approbation.count(), 0)

    def test_approuver_refuse_tant_quune_etape_est_en_attente(self):
        da = self._soumettre()
        resp = auth(self.appro1).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver/')
        self.assertEqual(resp.status_code, 400)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)

    def test_generer_bcf_impossible_avant_la_derniere_etape(self):
        da = self._soumettre()
        resp = auth(self.appro1).post(
            f'{BASE}/demandes-achat/{da.pk}/generer-bcf/')
        self.assertEqual(resp.status_code, 400)

    def test_les_deux_etapes_validees_approuvent_la_demande(self):
        da = self._soumettre()
        r1 = auth(self.appro1).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/',
            {'commentaire': 'OK niveau 1'}, format='json')
        self.assertEqual(r1.status_code, 200)
        da.refresh_from_db()
        # Une seule étape validée ne suffit PAS.
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)

        r2 = auth(self.appro2).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {}, format='json')
        self.assertEqual(r2.status_code, 200)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)
        self.assertEqual(da.approuvee_par_id, self.appro2.pk)
        etapes = list(da.etapes_approbation.order_by('niveau'))
        self.assertEqual([e.approbateur_id for e in etapes],
                         [self.appro1.pk, self.appro2.pk])
        self.assertEqual(etapes[0].commentaire, 'OK niveau 1')

    def test_ordre_sequentiel_impose(self):
        da = self._soumettre()
        etape2 = da.etapes_approbation.order_by('niveau')[1]
        resp = auth(self.appro2).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/',
            {'etape': etape2.pk}, format='json')
        self.assertEqual(resp.status_code, 400)
        etape2.refresh_from_db()
        self.assertEqual(etape2.statut,
                         EtapeApprobationAchat.Statut.EN_ATTENTE)

    def test_rejet_detape_refuse_la_demande_et_annule_le_reste(self):
        da = self._soumettre()
        resp = auth(self.appro1).post(
            f'{BASE}/demandes-achat/{da.pk}/rejeter-etape/',
            {'commentaire': 'Budget insuffisant'}, format='json')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Budget insuffisant')
        self.assertEqual(
            da.etapes_approbation.filter(
                statut=EtapeApprobationAchat.Statut.EN_ATTENTE).count(), 0)

    def test_etapes_approbation_lisibles(self):
        da = self._soumettre()
        resp = self.api.get(
            f'{BASE}/demandes-achat/{da.pk}/etapes-approbation/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]['niveau'], 1)

    def test_soumission_idempotente_ne_duplique_pas_les_etapes(self):
        da = self._soumettre()
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(da.etapes_approbation.count(), 2)


class ArbitrageRegleApprobationAchatTests(TestCase):
    """La règle la plus spécifique gagne ; le scope société est étanche."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_regle_la_plus_prioritaire_gagne(self):
        from apps.installations import services
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Générique', montant_min=1000,
            nombre_approbateurs=1, priorite=0)
        gagnante = RegleApprobationAchat.objects.create(
            company=self.company, libelle='Prioritaire', montant_min=1000,
            nombre_approbateurs=3, priorite=10)
        da = make_demande(self.company, self.user, montant=5000)
        self.assertEqual(
            services.resoudre_regle_approbation_achat(da).pk, gagnante.pk)

    def test_regle_ciblee_chantier_bat_la_generique(self):
        from apps.installations import services
        from apps.installations.models import Installation
        chantier = Installation.objects.create(
            company=self.company, reference=f'CH-{next(_seq)}')
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Générique', montant_min=100,
            nombre_approbateurs=1)
        ciblee = RegleApprobationAchat.objects.create(
            company=self.company, libelle='Chantier X', montant_min=100,
            nombre_approbateurs=2, chantier=chantier)
        da = make_demande(self.company, self.user, montant=5000,
                          chantier=chantier)
        self.assertEqual(
            services.resoudre_regle_approbation_achat(da).pk, ciblee.pk)

    def test_regle_inactive_ignoree(self):
        from apps.installations import services
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Désactivée', montant_min=100,
            nombre_approbateurs=2, actif=False)
        da = make_demande(self.company, self.user, montant=5000)
        self.assertIsNone(services.resoudre_regle_approbation_achat(da))

    def test_regle_dune_autre_societe_jamais_appliquee(self):
        from apps.installations import services
        autre = make_company()
        RegleApprobationAchat.objects.create(
            company=autre, libelle='Autre société', montant_min=100,
            nombre_approbateurs=2)
        da = make_demande(self.company, self.user, montant=5000)
        self.assertIsNone(services.resoudre_regle_approbation_achat(da))

    def test_liste_des_regles_scopee_societe(self):
        autre = make_company()
        RegleApprobationAchat.objects.create(
            company=autre, libelle='Invisible', montant_min=100)
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Visible', montant_min=100)
        resp = self.api.get(f'{BASE}/regles-approbation-achat/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([r['libelle'] for r in data], ['Visible'])

    def test_company_du_corps_ignoree_a_la_creation(self):
        autre = make_company()
        resp = self.api.post(f'{BASE}/regles-approbation-achat/', {
            'libelle': 'Injection', 'montant_min': '100.00',
            'nombre_approbateurs': 1, 'company': autre.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        regle = RegleApprobationAchat.objects.get(pk=resp.data['id'])
        self.assertEqual(regle.company_id, self.company.id)

    def test_montant_max_inferieur_au_min_rejete(self):
        resp = self.api.post(f'{BASE}/regles-approbation-achat/', {
            'libelle': 'Incohérente', 'montant_min': '5000.00',
            'montant_max': '100.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
