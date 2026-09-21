"""Tests FG136 — Indemnités kilométriques & per-diem chantier.

Couvre : barème km/per-diem par société (un seul défaut actif), calcul AUTO du
montant depuis la distance GPS (haversine) × taux_km (× 2 si aller-retour) +
per_diem × nombre de jours, référence posée côté serveur (IND-YYYYMM-NNNN,
jamais count()+1), cycle de vie (soumise → validée → remboursée / rejetée),
posting des écritures équilibrées (validation = débit charge classe 6 / crédit
personnel-créditeur 4432 ; remboursement = débit 4432 / crédit trésorerie),
respect du verrou de période (FG115), idempotence, garde multi-société, et les
endpoints API (company posée côté serveur, gate de rôle).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    BaremeIndemnite, CompteTresorerie, EcritureComptable, IndemniteChantier,
    PeriodeComptable,
)

User = get_user_model()

# Casablanca ↔ Rabat ≈ 86 km à vol d'oiseau (haversine).
CASA = (33.5731, -7.5898)
RABAT = (34.0209, -6.8416)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CalculIndemniteTests(TestCase):
    """Calcul pur (math) — distance × taux + per_diem × jours."""

    def test_haversine_casa_rabat(self):
        d = services._haversine_km(CASA[0], CASA[1], RABAT[0], RABAT[1])
        # ~86 km : tolérance large, on vérifie l'ordre de grandeur.
        self.assertTrue(80 < d < 92, d)

    def test_haversine_coordonnee_manquante(self):
        self.assertIsNone(services._haversine_km(None, -7.5, 34.0, -6.8))

    def test_calcul_aller_retour_double_la_distance(self):
        res = services.calculer_indemnite(
            taux_km='3', per_diem='100', distance_km='50', nombre_jours=2,
            aller_retour=True)
        # 50 km × 2 (A/R) × 3 MAD = 300 ; per-diem 100 × 2 = 200 ; total 500.
        self.assertEqual(res['distance_km'], Decimal('100.000'))
        self.assertEqual(res['montant_km'], Decimal('300.00'))
        self.assertEqual(res['montant_per_diem'], Decimal('200.00'))
        self.assertEqual(res['montant_total'], Decimal('500.00'))

    def test_calcul_aller_simple(self):
        res = services.calculer_indemnite(
            taux_km='2.5', per_diem='0', distance_km='40', nombre_jours=1,
            aller_retour=False)
        self.assertEqual(res['distance_km'], Decimal('40.000'))
        self.assertEqual(res['montant_km'], Decimal('100.00'))
        self.assertEqual(res['montant_total'], Decimal('100.00'))


class IndemniteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg136', 'FG136 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.employe = make_user(self.co, 'fg136-emp', role='normal')
        self.resp = make_user(self.co, 'fg136-resp')
        self.bareme = BaremeIndemnite.objects.create(
            company=self.co, libelle='Barème 2026',
            taux_km=Decimal('3'), per_diem=Decimal('150'), defaut=True)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE',
            compte_comptable=services.get_compte(self.co, '5141'))

    def _indem(self, jours=2, aller_retour=True):
        return services.creer_indemnite_chantier(
            self.co, employe=self.employe, date_deplacement=date(2026, 2, 10),
            depart_lat=CASA[0], depart_lng=CASA[1],
            site_lat=RABAT[0], site_lng=RABAT[1],
            aller_retour=aller_retour, nombre_jours=jours,
            libelle_chantier='Chantier Rabat', user=self.resp)

    def test_creer_calcule_montant_depuis_gps(self):
        indem = self._indem()
        self.assertEqual(indem.company_id, self.co.id)
        self.assertEqual(indem.bareme_id, self.bareme.id)
        self.assertTrue(indem.reference.startswith('IND-'))
        # distance A/R ≈ 2 × 86 ≈ 172 km, taux 3 → ~516 MAD ; per-diem 150×2=300.
        self.assertTrue(indem.distance_km > Decimal('160'))
        self.assertEqual(
            indem.montant_total,
            indem.montant_km + indem.montant_per_diem)
        self.assertEqual(indem.montant_per_diem, Decimal('300.00'))
        self.assertTrue(indem.montant_km > Decimal('480'))

    def test_creer_sans_bareme_defaut_refuse(self):
        co2 = make_company('fg136-nobareme', 'Sans barème')
        services.seed_plan_comptable(co2)
        emp = make_user(co2, 'fg136-nb-emp', role='normal')
        with self.assertRaises(ValidationError):
            services.creer_indemnite_chantier(
                co2, employe=emp, date_deplacement=date(2026, 2, 1),
                site_lat=RABAT[0], site_lng=RABAT[1])

    def test_reference_increment_highest_used(self):
        n1 = self._indem()
        n2 = self._indem()
        self.assertNotEqual(n1.reference, n2.reference)
        self.assertTrue(n2.reference > n1.reference)
        reused = n2.reference
        n2.delete()
        n3 = self._indem()
        self.assertEqual(n3.reference, reused)

    def test_distance_sans_gps_donne_per_diem_seul(self):
        indem = services.creer_indemnite_chantier(
            self.co, employe=self.employe, date_deplacement=date(2026, 2, 10),
            nombre_jours=3, user=self.resp)
        self.assertEqual(indem.distance_km, Decimal('0.000'))
        self.assertEqual(indem.montant_km, Decimal('0.00'))
        self.assertEqual(indem.montant_per_diem, Decimal('450.00'))

    def test_recalculer_brouillon(self):
        indem = self._indem(jours=1)
        indem.nombre_jours = 5
        indem.save(update_fields=['nombre_jours'])
        services.recalculer_indemnite_chantier(indem)
        self.assertEqual(indem.montant_per_diem, Decimal('750.00'))

    def test_recalculer_validee_refuse(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        with self.assertRaises(ValidationError):
            services.recalculer_indemnite_chantier(indem)

    def test_soumettre_montant_nul_refuse(self):
        indem = services.creer_indemnite_chantier(
            self.co, employe=self.employe, date_deplacement=date(2026, 2, 10),
            nombre_jours=0, user=self.resp)
        # Sans GPS ni jours, montant total nul → soumission refusée.
        self.assertEqual(indem.montant_total, Decimal('0.00'))
        with self.assertRaises(ValidationError):
            services.soumettre_indemnite_chantier(indem)

    def test_valider_poste_charge_equilibree(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        indem.refresh_from_db()
        self.assertEqual(indem.statut, IndemniteChantier.Statut.VALIDEE)
        ecr = indem.ecriture_charge
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.journal.type_journal, 'OD')
        montant = indem.montant_total
        self.assertEqual(
            ecr.lignes.get(compte__numero='6143').debit, montant)
        ligne_perso = ecr.lignes.get(compte__numero='4432')
        self.assertEqual(ligne_perso.credit, montant)
        self.assertEqual(ligne_perso.tiers_id, self.employe.id)

    def test_valider_avant_soumission_refuse(self):
        indem = self._indem()
        with self.assertRaises(ValidationError):
            services.valider_indemnite_chantier(indem, user=self.resp)

    def test_valider_idempotent(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        ecr1 = indem.ecriture_charge
        services.valider_indemnite_chantier(indem, user=self.resp)
        indem.refresh_from_db()
        self.assertEqual(indem.ecriture_charge_id, ecr1.id)

    def test_rembourser_poste_paiement(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        services.rembourser_indemnite_chantier(
            indem, compte_tresorerie=self.banque,
            date_remboursement=date(2026, 2, 28), user=self.resp)
        indem.refresh_from_db()
        self.assertEqual(indem.statut, IndemniteChantier.Statut.REMBOURSEE)
        ecr = indem.ecriture_remboursement
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.journal.type_journal, 'BNK')
        montant = indem.montant_total
        self.assertEqual(
            ecr.lignes.get(compte__numero='4432').debit, montant)
        self.assertEqual(
            ecr.lignes.get(compte__numero='5141').credit, montant)

    def test_rembourser_idempotent(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        services.rembourser_indemnite_chantier(
            indem, compte_tresorerie=self.banque, user=self.resp)
        ecr1 = indem.ecriture_remboursement
        services.rembourser_indemnite_chantier(
            indem, compte_tresorerie=self.banque, user=self.resp)
        indem.refresh_from_db()
        self.assertEqual(indem.ecriture_remboursement_id, ecr1.id)

    def test_rembourser_compte_autre_societe_refuse(self):
        autre = make_company('fg136-autre', 'Autre')
        services.seed_plan_comptable(autre)
        compte_autre = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque autre',
            compte_comptable=services.get_compte(autre, '5141'))
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        with self.assertRaises(ValidationError):
            services.rembourser_indemnite_chantier(
                indem, compte_tresorerie=compte_autre, user=self.resp)

    def test_rejeter_fige_motif_et_resoumission(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.rejeter_indemnite_chantier(
            indem, motif_rejet='GPS erroné', user=self.resp)
        indem.refresh_from_db()
        self.assertEqual(indem.statut, IndemniteChantier.Statut.REJETEE)
        self.assertEqual(indem.motif_rejet, 'GPS erroné')
        services.soumettre_indemnite_chantier(indem)
        self.assertEqual(indem.statut, IndemniteChantier.Statut.SOUMISE)
        self.assertEqual(indem.motif_rejet, '')

    def test_valider_refuse_periode_verrouillee(self):
        PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        with self.assertRaises(ValidationError):
            services.valider_indemnite_chantier(indem, user=self.resp)

    def test_charge_ecriture_validee(self):
        indem = self._indem()
        services.soumettre_indemnite_chantier(indem)
        services.valider_indemnite_chantier(indem, user=self.resp)
        indem.refresh_from_db()
        self.assertEqual(
            indem.ecriture_charge.statut, EcritureComptable.Statut.VALIDEE)


class BaremeDefautTests(TestCase):
    def setUp(self):
        self.co = make_company('fg136-bareme', 'FG136 Barème')

    def test_un_seul_defaut_via_demotion(self):
        b1 = BaremeIndemnite.objects.create(
            company=self.co, libelle='2025', taux_km=Decimal('2'),
            defaut=True)
        # Démotion explicite (faite côté viewset) avant d'en poser un nouveau.
        BaremeIndemnite.objects.filter(
            company=self.co, defaut=True, actif=True).update(defaut=False)
        b2 = BaremeIndemnite.objects.create(
            company=self.co, libelle='2026', taux_km=Decimal('3'),
            defaut=True)
        b1.refresh_from_db()
        self.assertFalse(b1.defaut)
        self.assertEqual(services.bareme_indemnite_defaut(self.co).id, b2.id)


class IndemniteApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg136-a', 'FG136 A')
        self.co_b = make_company('fg136-b', 'FG136 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.user_a = make_user(self.co_a, 'fg136-user-a')
        self.user_b = make_user(self.co_b, 'fg136-user-b')
        self.employe_a = make_user(self.co_a, 'fg136-emp-a', role='normal')
        self.bareme_a = BaremeIndemnite.objects.create(
            company=self.co_a, libelle='A', taux_km=Decimal('3'),
            per_diem=Decimal('100'), defaut=True)
        self.banque_a = CompteTresorerie.objects.create(
            company=self.co_a, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque A',
            compte_comptable=services.get_compte(self.co_a, '5141'))

    def _payload(self):
        return {
            'employe': self.employe_a.id,
            'date_deplacement': '2026-02-10',
            'depart_lat': CASA[0], 'depart_lng': CASA[1],
            'site_lat': RABAT[0], 'site_lng': RABAT[1],
            'aller_retour': True, 'nombre_jours': 2,
            'libelle_chantier': 'Rabat',
        }

    def test_endpoint_create_calcule_montant(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/indemnites-chantier/',
            self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        indem = IndemniteChantier.objects.get(id=resp.data['id'])
        self.assertEqual(indem.company_id, self.co_a.id)
        self.assertTrue(indem.reference.startswith('IND-'))
        self.assertTrue(indem.montant_total > 0)
        # Montants posés côté serveur (read-only), non lus du corps.
        self.assertEqual(indem.montant_per_diem, Decimal('200.00'))

    def test_endpoint_montants_corps_ignores(self):
        api = auth(self.user_a)
        payload = self._payload()
        payload['montant_total'] = '99999'
        payload['distance_km'] = '0'
        resp = api.post(
            '/api/django/compta/indemnites-chantier/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        indem = IndemniteChantier.objects.get(id=resp.data['id'])
        self.assertNotEqual(indem.montant_total, Decimal('99999'))
        self.assertTrue(indem.distance_km > 0)

    def test_endpoint_full_cycle(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/indemnites-chantier/',
            self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        indem_id = resp.data['id']
        self.assertEqual(
            api.post(
                f'/api/django/compta/indemnites-chantier/{indem_id}/'
                'soumettre/').status_code, 200)
        self.assertEqual(
            api.post(
                f'/api/django/compta/indemnites-chantier/{indem_id}/valider/',
                {}, format='json').status_code, 200)
        resp_r = api.post(
            f'/api/django/compta/indemnites-chantier/{indem_id}/rembourser/',
            {'compte_tresorerie': self.banque_a.id,
             'date_remboursement': '2026-02-28'}, format='json')
        self.assertEqual(resp_r.status_code, 200, resp_r.data)
        self.assertEqual(resp_r.data['statut'], 'remboursee')
        indem = IndemniteChantier.objects.get(id=indem_id)
        self.assertIsNotNone(indem.ecriture_charge_id)
        self.assertIsNotNone(indem.ecriture_remboursement_id)

    def test_endpoint_isolation_societe(self):
        services.creer_indemnite_chantier(
            self.co_a, employe=self.employe_a,
            date_deplacement=date(2026, 2, 1), nombre_jours=1,
            bareme=self.bareme_a)
        resp = auth(self.user_b).get(
            '/api/django/compta/indemnites-chantier/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(
            data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg136-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/indemnites-chantier/')
        self.assertEqual(resp.status_code, 403)

    def test_company_forced_server_side(self):
        api = auth(self.user_a)
        payload = self._payload()
        payload['company'] = self.co_b.id
        resp = api.post(
            '/api/django/compta/indemnites-chantier/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        indem = IndemniteChantier.objects.get(id=resp.data['id'])
        self.assertEqual(indem.company_id, self.co_a.id)

    def test_endpoint_create_refuse_employe_autre_societe(self):
        api = auth(self.user_b)
        payload = self._payload()
        resp = api.post(
            '/api/django/compta/indemnites-chantier/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_bareme_endpoint_pose_company_et_demote_defaut(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/baremes-indemnite/',
            {'libelle': '2027', 'taux_km': '4', 'per_diem': '120',
             'defaut': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        nouveau = BaremeIndemnite.objects.get(id=resp.data['id'])
        self.assertEqual(nouveau.company_id, self.co_a.id)
        self.assertTrue(nouveau.defaut)
        # L'ancien défaut a été démot.
        self.bareme_a.refresh_from_db()
        self.assertFalse(self.bareme_a.defaut)

    def test_bareme_taux_negatif_refuse(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/baremes-indemnite/',
            {'libelle': 'X', 'taux_km': '-1'}, format='json')
        self.assertEqual(resp.status_code, 400)
