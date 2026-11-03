"""APRF21 — ``message_ouvert_le`` lu EN LOT et ``traite_par`` chargé dans la
frise ``?lead=`` : +10 touches WhatsApp à faire et +10 touches traitées
n'ajoutent aucune requête ; les valeurs restent celles d'avant.

Test-du-test : remettre la requête par touche dans
``get_message_ouvert_le`` (ou retirer ``traite_par`` du ``select_related``)
⇒ +1 requête par touche, test_file_plate / test_frise_plate échouent.
Remettre ``cycles_standby`` par touche (``raison_fin_de_cadence`` sans lecteur)
⇒ test_file_derniere_touche_pro_plate échoue.
"""
import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.cadence_reperes import prefixe_activite_message_ouvert

User = get_user_model()
URL = '/api/django/crm/relance-etapes/'


class RelanceEtapesRequetesTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='APRF21 Solaire', slug='aprf21-relances')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aprf21-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0
        self.attendu = {}

    def _touche(self, lead, statut=RelanceEtape.Statut.A_FAIRE, **kw):
        self.n += 1
        maintenant = timezone.now()
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact',
            ordre=self.n, canal=RelanceEtape.Canal.WHATSAPP,
            libelle=f'Message {self.n}', due_at=maintenant,
            due_date=maintenant.date(), statut=statut, **kw)

    def _touches_whatsapp(self, nombre, **sur_le_lead):
        for _ in range(nombre):
            lead = Lead.objects.create(
                company=self.company, nom=f'L{self.n}', owner=self.user,
                stage=stages.CONTACTED, **sur_le_lead)
            touche = self._touche(lead)
            act = LeadActivity.objects.create(
                company=self.company, lead=lead, user=self.user,
                kind=LeadActivity.Kind.WHATSAPP,
                body=prefixe_activite_message_ouvert(touche) + ' (test)')
            self.attendu[touche.pk] = act.created_at

    def _requetes(self, params):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(URL, params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return len(ctx.captured_queries), resp.data['results']

    def test_file_plate(self):
        # 11 touches : ``ordre`` = 1…11, la dernière du gabarit de prise de contact
        # en est. La première dernière touche d'une page paie, UNE fois, les
        # lectures en lot de la promesse (D-CADV22-PROMESSE) ; c'est ensuite que
        # rien ne doit s'ajouter, et les +10 sont toutes des dernières touches.
        self._touches_whatsapp(11)
        self._requetes({'scope': 'all'})  # échauffement
        avant, _ = self._requetes({'scope': 'all'})
        self._touches_whatsapp(10)
        apres, lignes = self._requetes({'scope': 'all'})
        self.assertEqual(apres, avant)
        obtenu = {r['id']: r['message_ouvert_le'] for r in lignes}
        for pk, cree in self.attendu.items():
            self.assertIsNotNone(obtenu[pk])
            self.assertEqual(
                datetime.datetime.fromisoformat(
                    str(obtenu[pk]).replace('Z', '+00:00')), cree)

    def test_file_derniere_touche_pro_plate(self):
        """CADV102 — la dernière touche d'un pro lit ses cycles de Standby : en lot."""
        self._touches_whatsapp(11, type_installation='commercial')
        self._requetes({'scope': 'all'})  # échauffement
        avant, _ = self._requetes({'scope': 'all'})
        self._touches_whatsapp(10, type_installation='commercial')
        apres, lignes = self._requetes({'scope': 'all'})
        self.assertEqual(apres, avant)
        self.assertEqual(len(lignes), 21)

    def test_message_ouvert_par_touche(self):
        lead = Lead.objects.create(
            company=self.company, nom='Deux', owner=self.user,
            stage=stages.CONTACTED)
        ouverte = self._touche(lead)
        fermee = self._touche(lead)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.WHATSAPP,
            body=prefixe_activite_message_ouvert(ouverte))
        _, lignes = self._requetes({'lead': lead.pk})
        obtenu = {r['id']: r['message_ouvert_le'] for r in lignes}
        self.assertIsNotNone(obtenu[ouverte.pk])
        self.assertIsNone(obtenu[fermee.pk])

    def test_frise_plate(self):
        lead = Lead.objects.create(
            company=self.company, nom='Frise', owner=self.user,
            stage=stages.CONTACTED)

        def traitees(nombre):
            for _ in range(nombre):
                self._touche(lead, statut=RelanceEtape.Statut.FAIT,
                             traite_par=self.user, traite_le=timezone.now())

        traitees(10)
        self._requetes({'lead': lead.pk})
        avant, _ = self._requetes({'lead': lead.pk})
        traitees(10)
        apres, lignes = self._requetes({'lead': lead.pk})
        self.assertEqual(apres, avant)
        self.assertEqual(len(lignes), 20)
        self.assertTrue(all(r['traite_par_nom'] == 'aprf21-admin'
                            for r in lignes))

    # ── ERR-PERF-CRM-N1 — touches converties d'un numéro FIXE ───────────────
    # Rejeu APRF42 : relance-etapes 18 vs 32 requêtes selon la société. Une
    # touche née WhatsApp au protocole puis convertie en e-mail (fixe + adresse,
    # CIQ505) calcule ``canal_adapte`` avec la langue du lead, qui lit
    # ``lead.client`` puis ``lead.company`` — non joints : 2 requêtes PAR
    # touche. Test-du-test : retirer ``lead__client``/``lead__company`` du
    # ``select_related`` ⇒ +2 requêtes par touche, l'égalité tombe.

    def _lead_fixe(self):
        from apps.crm.models import Client
        self.n += 1
        return Lead.objects.create(
            company=self.company, nom=f'Fixe {self.n}', owner=self.user,
            stage=stages.CONTACTED, telephone='0522123456',
            email=f'fixe{self.n}@example.invalid',
            client=Client.objects.create(
                company=self.company, nom=f'Client fixe {self.n}'))

    def _touche_convertie(self, lead, ordre):
        from apps.parametres.models_relance import CadenceRelanceEtape
        CadenceRelanceEtape.objects.get_or_create(
            company=self.company, cadence='contact', ordre=ordre,
            defaults={'delai_jours': 0, 'canal': 'whatsapp',
                      'libelle': f'Message {ordre}', 'template_cle': 'j1_pdf'})
        maintenant = timezone.now()
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=ordre,
            canal=RelanceEtape.Canal.EMAIL, template_cle='j1_pdf',
            libelle=f'Message {ordre}', due_at=maintenant,
            due_date=maintenant.date())

    def _verifier_canal_adapte(self, lignes):
        from apps.crm import cadence_temps
        self.assertTrue(lignes)
        # Valeur d'avant : la MÊME fonction pure que le moteur (CIQ505).
        self.assertTrue(all(r['canal_adapte'] == cadence_temps.CAUSE_FIXE_EMAIL
                            for r in lignes), [r['canal_adapte'] for r in lignes])

    def test_file_touches_converties_plate(self):
        for _ in range(5):
            self._touche_convertie(self._lead_fixe(), 1)
        self._requetes({'scope': 'all'})  # échauffement
        a_5, lignes_5 = self._requetes({'scope': 'all'})
        self.assertEqual(len(lignes_5), 5)
        for _ in range(20):
            self._touche_convertie(self._lead_fixe(), 1)
        a_25, lignes_25 = self._requetes({'scope': 'all'})
        self.assertEqual(len(lignes_25), 25)
        self.assertLessEqual(abs(a_25 - a_5), 1, (a_5, a_25))
        self._verifier_canal_adapte(lignes_25)

    def test_frise_touches_converties_plate(self):
        lead = self._lead_fixe()
        for ordre in range(1, 6):
            self._touche_convertie(lead, ordre)
        self._requetes({'lead': lead.pk})
        a_5, lignes_5 = self._requetes({'lead': lead.pk})
        self.assertEqual(len(lignes_5), 5)
        for ordre in range(6, 26):
            self._touche_convertie(lead, ordre)
        a_25, lignes_25 = self._requetes({'lead': lead.pk})
        self.assertEqual(len(lignes_25), 25)
        self.assertLessEqual(abs(a_25 - a_5), 1, (a_5, a_25))
        self._verifier_canal_adapte(lignes_25)


class SuiviEtudeParamsNonChargeeTests(TestCase):
    """AOOM3 — « Suivi des relances » joint le devis pour sa SEULE référence,
    jamais pour son ``etude_params``.

    Incident du 02/11/2026 : mesuré en production, la fenêtre de 62 jours
    chargeait 128,5 Mio de JSON d'études (631 de ses 1 837 touches portent un
    devis, et le même devis lourd — jusqu'à 1,45 Mio — est relu à CHAQUE
    touche), décodés en centaines de Mio d'objets Python à chaque ouverture de
    l'écran. C'est la rafale sur cette route qui a précédé le premier worker
    tué par le noyau (08:32 UTC) et, côté écran, les abandons de requête à
    20 s que Meryem a vus comme un « problème de connexion ».

    Test-du-test : retirer ``.defer('devis__etude_params')`` de
    ``cadence_selectors.relance_etapes_periode`` ⇒ la colonne revient dans le
    SELECT et ``test_etude_params_jamais_chargee`` échoue ; retirer ``devis``
    du ``select_related`` ⇒ une requête par touche
    (``test_requetes_plates``).
    """
    URL = '/api/django/crm/relance-etapes/suivi/'

    #: La taille ne change RIEN aux assertions (elles portent sur le SQL
    #: émis) : 744 h = un mois, là où la production en stocke 8 760.
    ETUDE_LOURDE = {'scenario': 'Avec batterie',
                    'profil_horaire': [round(i % 24 * 0.37, 3)
                                       for i in range(744)]}

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='AOOM3 Solaire', slug='aoom3-suivi')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aoom3-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0
        self.jour = timezone.localdate()

    def _touches_avec_devis(self, nombre):
        from decimal import Decimal
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        for _ in range(nombre):
            self.n += 1
            client = Client.objects.create(
                company=self.company, nom=f'Client {self.n}')
            lead = Lead.objects.create(
                company=self.company, nom=f'L{self.n}', owner=self.user,
                stage=stages.QUOTE_SENT, client=client)
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-AOOM3-{self.n:04d}',
                client=client, lead=lead, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), version=1,
                etude_params=dict(self.ETUDE_LOURDE))
            RelanceEtape.objects.create(
                company=self.company, lead=lead, cadence='apres_devis',
                ordre=self.n, canal=RelanceEtape.Canal.WHATSAPP,
                libelle=f'Relance {self.n}', devis=devis,
                due_at=timezone.now(), due_date=self.jour,
                statut=RelanceEtape.Statut.A_FAIRE)

    def _fenetre(self):
        debut = self.jour - datetime.timedelta(days=30)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(self.URL, {
                'date_debut': debut.isoformat(),
                'date_fin': (self.jour
                             + datetime.timedelta(days=30)).isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        return ctx.captured_queries, resp.data['results']

    def test_etude_params_jamais_chargee(self):
        self._touches_avec_devis(12)
        self._fenetre()  # échauffement
        requetes, lignes = self._fenetre()
        self.assertEqual(len(lignes), 12)
        fautives = [q['sql'] for q in requetes if 'etude_params' in q['sql']]
        self.assertEqual(
            fautives, [],
            f'le suivi charge etude_params : {fautives[:1]}')
        # La référence du devis, elle, reste servie — sans requête de plus.
        self.assertTrue(all(ligne['devis_reference'].startswith('DEV-AOOM3-')
                            for ligne in lignes))

    def test_file_et_frise_ne_chargent_pas_etude_params(self):
        # ACVI77 — même règle sur la file, la frise (`?lead=`) et le digest.
        from apps.crm.management.commands.notifier_relances_dues import (
            notifier_relances_dues)
        self._touches_avec_devis(3)
        lead = RelanceEtape.objects.filter(company=self.company).first().lead
        base = '/api/django/crm/relance-etapes/'
        for params in ({'scope': 'all'}, {'lead': lead.pk}):
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get(base, params)
            self.assertEqual(resp.status_code, 200, resp.data)
            lignes = resp.data.get('results', resp.data)
            self.assertTrue(all(ligne['devis_reference'].startswith('DEV-AOOM3-')
                                for ligne in lignes))
            self.assertEqual(
                [q['sql'] for q in ctx.captured_queries
                 if 'etude_params' in q['sql']], [], params)
        with CaptureQueriesContext(connection) as ctx:
            notifier_relances_dues()
        self.assertEqual(
            [q['sql'] for q in ctx.captured_queries
             if 'etude_params' in q['sql']], [])

    def test_requetes_plates(self):
        self._touches_avec_devis(5)
        self._fenetre()  # échauffement
        avant, lignes_5 = self._fenetre()
        self.assertEqual(len(lignes_5), 5)
        self._touches_avec_devis(15)
        apres, lignes_20 = self._fenetre()
        self.assertEqual(len(lignes_20), 20)
        self.assertLessEqual(
            abs(len(apres) - len(avant)), 1,
            f'suivi : {len(avant)} requêtes à 5 touches, '
            f'{len(apres)} à 20')
