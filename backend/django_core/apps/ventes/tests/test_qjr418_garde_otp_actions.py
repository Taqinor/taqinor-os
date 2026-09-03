"""QJR418 (DR2, actions) — les ACTIONS clientes publiques passent la même garde.

CE QUE LE ROUGE PROUVAIT. ``proposal_activate_option`` ne consultait JAMAIS
``otp_lecture_verified`` : n'importe qui détenant le jeton pouvait **changer le
périmètre facturé** d'un devis — activer une ligne optionnelle payante — sans
franchir la garde que la LECTURE, elle, exige (QJR132/QJR417). Le raisonnement
de QJR132 (« signer est au moins aussi gardé que lire ») ne leur avait jamais
été appliqué.

DR2 tranche : **la garde couvre les actions clientes**, ``activate_option``
étant le minimum absolu. On réutilise LA garde de QJR417, jamais une seconde
formulation, posée AVANT toute mutation.

Le troisième test écrit l'INVENTAIRE des actions publiques du fichier : chacune
est déclarée **gardée** ou **délibérément non gardée avec sa raison** — jamais
un silence. C'est cet inventaire qui empêchera la prochaine action d'arriver
non gardée.
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes import public_views
from apps.ventes.models import Devis, LigneDevis, ShareLink


class _BaseActivationOption(TestCase):

    def setUp(self):
        cache.clear()
        self.company = Company.objects.get_or_create(
            slug='qjr418', defaults={'nom': 'QJR418'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR418', email='',
            telephone='')
        self.devis = Devis.objects.create(
            company=self.company, reference='DV-QJR418-1',
            client=self.client_obj, statut='envoye',
            taux_tva=Decimal('20'))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, designation='Batterie supplémentaire 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('12000'),
            remise=Decimal('0'), optionnelle=True)
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis, otp_lecture=True)
        self.anon = APIClient()

    def tearDown(self):
        cache.clear()

    def _url(self):
        from django.urls import reverse
        return reverse('public-proposal-activate-option',
                       args=[self.link.token])

    def _deverrouiller(self):
        from apps.ventes.services import _otp_lecture_verified_key
        cache.set(_otp_lecture_verified_key(self.link.token), True, 3600)


class ActivationOptionGardeTests(_BaseActivationOption):

    def test_sans_otp_verifie_l_option_n_est_pas_activee(self):
        """ROUGE avant QJR418 : l'option basculait, et le total facturé avec."""
        reponse = self.anon.post(
            self._url(), {'ligne_id': self.ligne.id}, format='json')
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(reponse.data['detail'], 'otp_required')
        # État en base INCHANGÉ : la ligne reste optionnelle.
        self.ligne.refresh_from_db()
        self.assertTrue(self.ligne.optionnelle)

    def test_avec_otp_verifie_l_activation_se_comporte_comme_avant(self):
        self._deverrouiller()
        reponse = self.anon.post(
            self._url(), {'ligne_id': self.ligne.id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['ligne_id'], self.ligne.id)
        self.ligne.refresh_from_db()
        self.assertFalse(self.ligne.optionnelle)

    def test_le_total_facture_qui_en_decoule_est_inchange_au_centime(self):
        """Second test du `Done` : la garde ne touche PAS l'argent."""
        self._deverrouiller()
        self.anon.post(
            self._url(), {'ligne_id': self.ligne.id}, format='json')
        self.devis.refresh_from_db()
        self.ligne.refresh_from_db()
        self.assertFalse(self.ligne.optionnelle)
        self.assertEqual(
            Decimal(self.ligne.quantite) * Decimal(self.ligne.prix_unitaire),
            Decimal('12000'))

    def test_un_lien_sans_code_est_inchange(self):
        """NO-OP : ``otp_lecture`` faux ⇒ la garde répond True."""
        self.link.otp_lecture = False
        self.link.save(update_fields=['otp_lecture'])
        reponse = self.anon.post(
            self._url(), {'ligne_id': self.ligne.id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_la_garde_est_posee_avant_la_lecture_du_corps(self):
        """Un corps invalide + pas d'OTP ⇒ 403 (la garde d'abord), jamais le
        400 « Option invalide » qui prouverait qu'on a déjà travaillé."""
        reponse = self.anon.post(
            self._url(), {'ligne_id': 'pas-un-entier'}, format='json')
        self.assertEqual(reponse.status_code, 403)


class InventaireDesActionsPubliquesTests(TestCase):
    """Troisième test du `Done` — CHAQUE action publique du fichier est
    déclarée : gardée, ou délibérément non gardée AVEC SA RAISON.

    Un endpoint POST public qui apparaîtrait dans ``public_views.py`` sans
    figurer ici fait ROUGIR ce test : c'est la garde qui empêche la prochaine
    action d'arriver non gardée.
    """

    #: Actions publiques (``@api_view(['POST'])``) qui DOIVENT consulter
    #: ``otp_lecture_verified``.
    GARDEES = {
        'proposal_accept':
            'QJR132 — la signature électronique engage le client : elle est '
            'au moins aussi gardée que la lecture.',
        'proposal_activate_option':
            'QJR418/DR2 — activer une option CHANGE le périmètre facturé.',
    }

    #: Actions publiques délibérément NON gardées, chacune avec sa raison.
    NON_GARDEES = {
        'proposal_request_otp':
            'DEMANDE le code : l\'exiger pour l\'obtenir serait circulaire.',
        'proposal_request_otp_lecture':
            'DEMANDE le code de lecture : même raison circulaire.',
        'proposal_verify_otp_lecture':
            'VÉRIFIE le code : c\'est le point d\'entrée de la garde.',
        'proposal_contact_request':
            'Le client demande à être RAPPELÉ : aucune donnée du devis n\'est '
            'lue ni modifiée, et un client qui a perdu son code doit pouvoir '
            'joindre son commercial.',
        'proposal_engagement':
            'Beacon d\'engagement par section (XSAL16) : aucune donnée '
            'personnelle, aucune mutation du devis, une section inconnue est '
            'simplement ignorée.',
        'proposal_virement_declare':
            'Déclaration de virement : ne change ni statut ni montant '
            '(pose une note chatter, règle #4) et le client qui vient de '
            'payer ne doit pas être bloqué par un code expiré.',
        'pay_webhook':
            'Webhook PSP, PAS une action cliente : authentifié par le jeton '
            'PaymentLink et la signature du prestataire, aucun ShareLink.',
        'ecatalogue_demander_devis':
            'E-catalogue public (XPOS14) : aucun ShareLink, donc aucun OTP de '
            'lecture à consulter — gardé par honeypot + throttle.',
    }

    def test_l_inventaire_couvre_toutes_les_actions_publiques(self):
        source = Path(public_views.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        actions = {}
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.FunctionDef):
                continue
            for decorateur in noeud.decorator_list:
                if not (isinstance(decorateur, ast.Call)
                        and getattr(decorateur.func, 'id', '') == 'api_view'):
                    continue
                methodes = ast.unparse(decorateur.args[0])
                if 'POST' in methodes:
                    actions[noeud.name] = ast.unparse(noeud)
        self.assertTrue(actions, 'aucune action publique trouvée')

        declarees = set(self.GARDEES) | set(self.NON_GARDEES)
        non_declarees = sorted(set(actions) - declarees)
        self.assertEqual(
            non_declarees, [],
            'actions publiques non déclarées dans l\'inventaire : %r'
            % (non_declarees,))
        disparues = sorted(declarees - set(actions))
        self.assertEqual(
            disparues, [],
            'inventaire périmé (actions disparues) : %r' % (disparues,))

        for nom in self.GARDEES:
            with self.subTest(action=nom, attendu='gardée'):
                self.assertIn('otp_lecture_verified', actions[nom])
        for nom in self.NON_GARDEES:
            with self.subTest(action=nom, attendu='non gardée'):
                self.assertNotIn('otp_lecture_verified', actions[nom])

    def test_chaque_action_non_gardee_porte_une_raison(self):
        for nom, raison in self.NON_GARDEES.items():
            with self.subTest(action=nom):
                self.assertTrue(
                    raison and len(raison) > 30,
                    '%s : la raison doit être explicite' % nom)
