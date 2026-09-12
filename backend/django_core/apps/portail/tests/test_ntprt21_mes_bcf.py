"""Tests NTPRT21 — « Mes BCF à confirmer » du portail FOURNISSEUR authentifié.

Deux choses sont vérifiées ici, et ce sont les deux que la tâche exige :

1. **L'isolation.** Le fournisseur est résolu depuis le COMPTE connecté, jamais
   d'un paramètre : un BCF d'un autre fournisseur (ou d'une autre société) est
   INTROUVABLE en lecture comme en écriture — 404, jamais « trouvé puis
   refusé ».
2. **L'équivalence bit-à-bit avec XPUR22.** La confirmation authentifiée doit
   produire EXACTEMENT le même effet que l'ancien lien tokenisé : accusé posé,
   date DEMANDÉE d'origine (``date_livraison_prevue``) jamais écrasée.

Run :
    python manage.py test apps.portail.tests.test_ntprt21_mes_bcf -v2
"""
import datetime
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.achats.models import (
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
)
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from apps.stock.models import Fournisseur
from authentication.models import Company, CustomUser

URL_LISTE = '/api/django/portail/mes-bons-commande/'


def url_confirmer(bcf_id):
    return f'{URL_LISTE}{bcf_id}/confirmer/'


_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_fournisseur(company, nom='Fournisseur'):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}')


def make_bcf(company, fournisseur, statut=BonCommandeFournisseur.Statut.ENVOYE,
             date_prevue=datetime.date(2026, 3, 10)):
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'BCF-NTPRT21-{next(_seq)}',
        statut=statut,
        date_commande=datetime.date(2026, 3, 1),
        date_livraison_prevue=date_prevue)
    LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, designation='Panneau 550 Wc', sans_stock=True,
        quantite=12)
    return bc


class MesBcfLectureTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt21-co', 'NTPRT21 Société')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.bcf_a = make_bcf(self.company, self.f_a)
        self.bcf_b = make_bcf(self.company, self.f_b)
        self.user_a = make_portal_user(
            self.company, 'ntprt21-f-a',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_le_fournisseur_ne_voit_que_SES_bons_de_commande(self):
        res = self.api.get(URL_LISTE)
        self.assertEqual(res.status_code, 200, res.data)
        refs = [r['reference'] for r in res.data['results']]
        self.assertIn(self.bcf_a.reference, refs)
        self.assertNotIn(self.bcf_b.reference, refs)

    def test_le_drapeau_a_confirmer_suit_l_accuse(self):
        res = self.api.get(URL_LISTE)
        ligne = res.data['results'][0]
        self.assertTrue(ligne['a_confirmer'])

        self.bcf_a.date_confirmee_fournisseur = datetime.date(2026, 3, 12)
        self.bcf_a.save(update_fields=['date_confirmee_fournisseur'])
        res = self.api.get(URL_LISTE)
        self.assertFalse(res.data['results'][0]['a_confirmer'])

    def test_aucun_prix_d_achat_expose(self):
        """Le fournisseur voit le QUOI et le QUAND — jamais un montant."""
        res = self.api.get(URL_LISTE)
        charge = str(res.data)
        for interdit in ('prix_achat', 'prix_achat_unitaire', 'total_achat',
                         'marge'):
            self.assertNotIn(interdit, charge)

    def test_brouillon_et_annule_ne_sont_pas_montres(self):
        make_bcf(self.company, self.f_a,
                 statut=BonCommandeFournisseur.Statut.BROUILLON)
        make_bcf(self.company, self.f_a,
                 statut=BonCommandeFournisseur.Statut.ANNULE)
        res = self.api.get(URL_LISTE)
        statuts = {r['statut'] for r in res.data['results']}
        self.assertNotIn('brouillon', statuts)
        self.assertNotIn('annule', statuts)

    def test_detail_d_un_bcf_d_un_autre_fournisseur_est_404(self):
        res = self.api.get(f'{URL_LISTE}{self.bcf_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_un_compte_client_est_refuse(self):
        client_user = make_portal_user(
            self.company, 'ntprt21-c', CustomUser.PORTEE_PORTAIL_CLIENT, 1)
        api = APIClient()
        api.force_authenticate(user=client_user)
        self.assertEqual(api.get(URL_LISTE).status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL_LISTE).status_code, (401, 403))

    def test_fournisseur_d_une_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt21-co-b', 'NTPRT21 Société B')
        etranger = make_portal_user(
            autre, 'ntprt21-f-etranger',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        api = APIClient()
        api.force_authenticate(user=etranger)
        res = api.get(URL_LISTE)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results'], [])


class MesBcfConfirmationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt21b-co', 'NTPRT21b Société')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.bcf_a = make_bcf(self.company, self.f_a)
        self.bcf_b = make_bcf(self.company, self.f_b)
        self.user_a = make_portal_user(
            self.company, 'ntprt21b-f-a',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_confirmation_pose_l_accuse_sans_ecraser_la_date_demandee(self):
        """Critère NTPRT21 : identique au flux tokenisé XPUR22."""
        demandee = self.bcf_a.date_livraison_prevue
        res = self.api.post(url_confirmer(self.bcf_a.id), {
            'date_confirmee': '2026-03-18',
            'numero_confirmation': 'ACK-42',
        }, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.bcf_a.refresh_from_db()
        self.assertEqual(self.bcf_a.date_confirmee_fournisseur,
                         datetime.date(2026, 3, 18))
        self.assertEqual(self.bcf_a.numero_confirmation_fournisseur, 'ACK-42')
        # La date DEMANDÉE d'origine reste intacte : l'OTD promis-vs-reçu
        # doit rester mesurable.
        self.assertEqual(self.bcf_a.date_livraison_prevue, demandee)

    def test_confirmer_le_bcf_d_un_autre_fournisseur_est_404(self):
        res = self.api.post(url_confirmer(self.bcf_b.id),
                            {'date_confirmee': '2026-03-18'}, format='json')
        self.assertEqual(res.status_code, 404)
        self.bcf_b.refresh_from_db()
        self.assertIsNone(self.bcf_b.date_confirmee_fournisseur)

    def test_date_manquante_nomme_le_champ_fautif(self):
        res = self.api.post(url_confirmer(self.bcf_a.id), {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('date_confirmee', res.data)

    def test_date_invalide_nomme_le_champ_fautif(self):
        res = self.api.post(url_confirmer(self.bcf_a.id),
                            {'date_confirmee': '18/03/2026'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('date_confirmee', res.data)

    def test_un_compte_client_ne_peut_pas_confirmer(self):
        client_user = make_portal_user(
            self.company, 'ntprt21b-c', CustomUser.PORTEE_PORTAIL_CLIENT, 1)
        api = APIClient()
        api.force_authenticate(user=client_user)
        res = api.post(url_confirmer(self.bcf_a.id),
                       {'date_confirmee': '2026-03-18'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_un_fournisseur_d_une_autre_societe_ne_confirme_rien(self):
        autre = make_company('ntprt21b-co-b', 'NTPRT21b Société B')
        etranger = make_portal_user(
            autre, 'ntprt21b-f-etranger',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        api = APIClient()
        api.force_authenticate(user=etranger)
        res = api.post(url_confirmer(self.bcf_a.id),
                       {'date_confirmee': '2026-03-18'}, format='json')
        self.assertEqual(res.status_code, 404)
        self.bcf_a.refresh_from_db()
        self.assertIsNone(self.bcf_a.date_confirmee_fournisseur)
