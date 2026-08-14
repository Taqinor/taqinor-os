"""Garde anti-divergence des DEUX registres de gabarits de règles.

Bug corrigé : ``rules.py`` (registre historique ADSENG4, 5 gabarits) et
``rule_templates.py`` (catalogue FIXE réel, 15 gabarits — celui que
``GET /regles/catalogue/`` affiche) avaient été recopiés à la main. Comme
``RulePolicy.template_key`` validait contre le PREMIER, armer ``stop_loss_cpl``
— le premier gabarit du catalogue affiché — repartait en **400 Bad Request** :
l'utilisateur voyait 15 règles et ne pouvait en armer que 5.

Ces tests échouent si les registres redivergent : les ``choices`` du modèle sont
désormais DÉRIVÉS du catalogue (``rules.rule_template_choices``), donc tout
gabarit ajouté à ``rule_templates`` DOIT rester armable, sans rien recopier.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rule_templates as rt
from apps.adsengine import rules
from apps.adsengine.models import RulePolicy

User = get_user_model()
REGLES = '/api/django/adsengine/regles/'


def champ_choices():
    """Choix RÉELLEMENT exposés par le champ du modèle (clé → libellé)."""
    return dict(RulePolicy._meta.get_field('template_key').choices)


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RuleTemplateChoicesDeriveesTests(SimpleTestCase):
    """Le champ modèle dérive du catalogue — aucune liste recopiée."""

    def test_tout_gabarit_du_catalogue_est_un_choix_valide(self):
        """LA garde : un gabarit du catalogue affiché est toujours armable."""
        choix = champ_choices()
        manquants = sorted(set(rt.RULE_TEMPLATES) - set(choix))
        self.assertEqual(
            manquants, [],
            "Registres divergents : ces gabarits sont affichés par "
            "/regles/catalogue/ mais refusés en 400 à l'armement — les choix "
            "doivent DÉRIVER de rule_templates.RULE_TEMPLATES, jamais être "
            f"recopiés à la main : {manquants}")

    def test_le_premier_gabarit_du_catalogue_est_armable(self):
        """Cas exact du bug : ``stop_loss_cpl`` était rejeté."""
        self.assertIn('stop_loss_cpl', champ_choices())

    def test_libelle_du_catalogue_fait_foi(self):
        """Une clé partagée par les deux registres porte le libellé AFFICHÉ."""
        choix = champ_choices()
        for cle, tpl in rt.RULE_TEMPLATES.items():
            self.assertEqual(choix[cle], tpl['label_fr'], cle)

    def test_cles_historiques_toujours_acceptees(self):
        """Aucune ``RulePolicy`` déjà en base ne devient invalide."""
        choix = champ_choices()
        for cle in rules.RULE_TEMPLATES:
            self.assertIn(cle, choix, f'clé historique perdue : {cle}')

    def test_choix_du_champ_identiques_au_registre_derive(self):
        """Le champ consomme bien le callable (pas une copie figée)."""
        self.assertEqual(champ_choices(), dict(rules.rule_template_choices()))

    def test_aucune_cle_ne_depasse_le_max_length(self):
        limite = RulePolicy._meta.get_field('template_key').max_length
        for cle in champ_choices():
            self.assertLessEqual(len(cle), limite, cle)


class ArmementDesGabaritsDuCatalogueTests(TestCase):
    """Bout en bout : chaque gabarit du catalogue s'arme en 201 (plus de 400)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Sync Co', slug='sync-co')
        self.manager = make_user(
            self.company, 'syncmgr', ['adsengine_view', 'adsengine_manage'])

    def test_stop_loss_cpl_s_arme(self):
        resp = auth(self.manager).post(
            REGLES, {'template_key': 'stop_loss_cpl'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        regle = RulePolicy.objects.get(pk=resp.data['id'])
        # Multi-tenant : la société est posée côté serveur, jamais reçue.
        self.assertEqual(regle.company_id, self.company.id)
        # Défaut sûr préservé.
        self.assertFalse(regle.enabled)
        self.assertTrue(regle.dry_run)

    def test_chaque_gabarit_du_catalogue_s_arme(self):
        client = auth(self.manager)
        for cle in rt.RULE_TEMPLATES:
            with self.subTest(gabarit=cle):
                resp = client.post(
                    REGLES, {'template_key': cle}, format='json')
                self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            RulePolicy.objects.filter(company=self.company).count(),
            len(rt.RULE_TEMPLATES))

    def test_gabarit_inconnu_toujours_refuse(self):
        """La validation n'est pas affaiblie : une clé inventée reste 400."""
        resp = auth(self.manager).post(
            REGLES, {'template_key': 'gabarit_invente'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
