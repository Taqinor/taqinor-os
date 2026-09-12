"""CHT10 — Service portail : publier un jalon de chantier.

Avant CHT10, AUCUNE fonction d'écriture propre n'existait pour publier un
jalon de chantier au portail client : seul le ``ModelViewSet`` CRUD legacy
(``apps.compta.views.JalonChantierPortailViewSet``) écrivait
``JalonChantierPortail``, sans aucune clé stable pour discriminer une phase
(``libelle``/``ordre``/``atteint``/``date_jalon`` seulement).

Ce module couvre le nouveau SEUL point d'entrée d'écriture cross-app :
``apps.portail.services.upsert_jalon_chantier`` — idempotent par
``(company, chantier_id, cle_phase)``, jamais de suppression — et le
sélecteur de lecture ``apps.portail.selectors.jalons_du_chantier``.

Run :
    python manage.py test apps.portail.tests.test_cht10_upsert_jalon_chantier -v2
"""
import itertools
from datetime import date

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.portail.models import JalonChantierPortail
from apps.portail.selectors import jalons_du_chantier
from apps.portail.services import upsert_jalon_chantier
from authentication.models import Company

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht10-co-{n}', defaults={'nom': nom or f'CHT10 Co {n}'})
    return company


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='CHT10',
        email=f'cht10-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-CHT10-{n}', client=client)


class TestUpsertJalonChantierIdempotent(TestCase):
    def setUp(self):
        self.company = make_company()
        self.chantier = make_installation(self.company)

    def test_premier_appel_cree_le_jalon(self):
        jalon = upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude technique',
            atteint=False)
        self.assertIsNotNone(jalon)
        self.assertEqual(jalon.company_id, self.company.id)
        self.assertEqual(jalon.chantier_id, self.chantier.id)
        self.assertEqual(jalon.cle_phase, 'etude')
        self.assertEqual(jalon.libelle, 'Étude technique')
        self.assertFalse(jalon.atteint)
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                chantier=self.chantier, cle_phase='etude').count(), 1)

    def test_second_appel_meme_phase_met_a_jour_sans_dupliquer(self):
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'installation',
            'Installation en cours', atteint=False)
        jalon = upsert_jalon_chantier(
            self.company, self.chantier.id, 'installation',
            'Installation terminée', atteint=True,
            date_jalon=date(2026, 9, 10))
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                chantier=self.chantier, cle_phase='installation').count(), 1)
        self.assertTrue(jalon.atteint)
        self.assertEqual(jalon.libelle, 'Installation terminée')
        self.assertEqual(jalon.date_jalon, date(2026, 9, 10))

    def test_phases_distinctes_du_meme_chantier_ne_se_collisionnent_pas(self):
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude')
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'commande', 'Commande passée')
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                chantier=self.chantier).count(), 2)

    def test_cle_phase_vide_est_un_no_op(self):
        self.assertIsNone(
            upsert_jalon_chantier(self.company, self.chantier.id, '', 'X'))
        self.assertIsNone(
            upsert_jalon_chantier(self.company, self.chantier.id, None, 'X'))
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                chantier=self.chantier).count(), 0)

    def test_jalon_legacy_sans_cle_phase_reste_intact(self):
        """Les jalons créés à la main (écran admin, sans ``cle_phase``) ne
        sont jamais touchés par l'upsert — la contrainte d'unicité ne les
        concerne pas (NULL exclu)."""
        legacy = JalonChantierPortail.objects.create(
            company=self.company, chantier=self.chantier,
            libelle='Mise en service (saisie manuelle)', ordre=5)
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'mes', 'Mise en service')
        legacy.refresh_from_db()
        self.assertEqual(legacy.libelle, 'Mise en service (saisie manuelle)')
        self.assertIsNone(legacy.cle_phase)
        self.assertEqual(
            JalonChantierPortail.objects.filter(chantier=self.chantier).count(), 2)

    def test_scoping_societe(self):
        autre_societe = make_company()
        autre_chantier = make_installation(autre_societe)
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude Co A')
        upsert_jalon_chantier(
            autre_societe, autre_chantier.id, 'etude', 'Étude Co B')
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                company=self.company).count(), 1)
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                company=autre_societe).count(), 1)


class TestJalonsDuChantierSelector(TestCase):
    def setUp(self):
        self.company = make_company()
        self.chantier = make_installation(self.company)

    def test_liste_dans_l_ordre_d_affichage(self):
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'mes', 'Mise en service')
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude')
        jalons = list(jalons_du_chantier(self.company, self.chantier.id))
        self.assertEqual(len(jalons), 2)
        self.assertEqual({j.cle_phase for j in jalons}, {'mes', 'etude'})

    def test_scope_par_societe(self):
        autre_societe = make_company()
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude')
        self.assertEqual(
            list(jalons_du_chantier(autre_societe, self.chantier.id)), [])

    def test_sans_chantier_renvoie_vide(self):
        self.assertEqual(list(jalons_du_chantier(self.company, None)), [])
