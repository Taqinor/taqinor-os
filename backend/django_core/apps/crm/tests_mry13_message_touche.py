"""MRY13 — Le message d'une touche, rendu côté serveur, et le clic qui marque.

Le serveur REND, il n'ENVOIE pas (décision D5) : l'écran montre une modale
d'aperçu, et c'est le clic humain qui ouvre WhatsApp. Aucun BSP, aucun appel
réseau sortant — la garde négative en fin de fichier le vérifie.

LA règle du lot, celle qui protège le client : AUCUN chiffre inventé. Une
phrase dont le placeholder n'a pas de valeur réelle est OMISE — jamais un blanc
(« valable jusqu'au  »), jamais un défaut. Les prix, kWc et économies ne sont
pas des placeholders du tout : ils restent dans le devis et la proposition.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.services import message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MessageTemplate)
from apps.ventes.models import Devis

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry13'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company,
            first_name='Meryem')
        self.normal = User.objects.create_user(
            username=f'{self.slug}-n', password='x', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            ville='Casablanca', telephone='+212651971400',
            owner=self.acteur)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, template_cle='identite', canal='whatsapp', devis=None):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1, canal=canal,
            due_date=LUNDI.date(), due_at=LUNDI, cadence='contact',
            template_cle=template_cle, devis=devis)


class RenduTests(_Base):
    slug = 'mry13-rendu'

    def test_le_texte_valide_est_rendu_avec_le_prenom(self):
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertIn('Aziz', rendu['message'])
        self.assertNotIn('{prenom}', rendu['message'])
        self.assertEqual(rendu['langue'], 'fr')
        self.assertTrue(rendu['wa_url'].startswith('https://wa.me/'))

    def test_la_darija_du_lead_est_respectee(self):
        self.lead.langue_preferee = 'darija'
        self.lead.save(update_fields=['langue_preferee'])
        MessageTemplate.objects.create(
            company=self.company, cle='identite',
            corps_fr='Bonjour {prenom}', corps_darija='السلام {prenom}')
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertEqual(rendu['langue'], 'darija')
        self.assertIn('السلام', rendu['message'])

    def test_un_gabarit_maison_prime_sur_le_defaut(self):
        MessageTemplate.objects.create(
            company=self.company, cle='identite', corps_fr='Texte maison')
        self.assertEqual(
            message_pour_etape(self._touche(), user=self.acteur)['message'],
            'Texte maison')

    def test_le_conseiller_est_lutilisateur_courant(self):
        MessageTemplate.objects.create(
            company=self.company, cle='identite',
            corps_fr='Je suis {conseiller}.')
        self.assertEqual(
            message_pour_etape(self._touche(), user=self.acteur)['message'],
            'Je suis Meryem.')


class AucunChiffreInventeTests(_Base):
    slug = 'mry13-omission'

    def _devis(self, reference, date_validite=None):
        client = Client.objects.create(
            company=self.company, nom='Client', email=f'{reference}@ex.com')
        return Devis.objects.create(
            company=self.company, reference=reference, client=client,
            lead=self.lead, statut='envoye', taux_tva=Decimal('20.00'),
            date_validite=date_validite)

    def test_une_phrase_sans_date_de_validite_est_OMISE(self):
        """« valable jusqu'au  » serait pire que rien : le client lirait une
        promesse tronquée. On perd la phrase, jamais la vérité."""
        MessageTemplate.objects.create(
            company=self.company, cle='j9_validite',
            corps_fr=("Bonjour {prenom}. Votre proposition est valable "
                      "jusqu'au {date_validite}. Je reste disponible."))
        devis = self._devis('DEV-MRY13-0001', date_validite=None)
        rendu = message_pour_etape(
            self._touche(template_cle='j9_validite', devis=devis),
            user=self.acteur)
        self.assertNotIn('{date_validite}', rendu['message'])
        self.assertNotIn('valable', rendu['message'])
        self.assertIn('Bonjour Aziz', rendu['message'])
        self.assertIn('Je reste disponible', rendu['message'])
        self.assertIn('date_validite', rendu['placeholders_manquants'])

    def test_la_phrase_est_gardee_quand_la_date_existe(self):
        MessageTemplate.objects.create(
            company=self.company, cle='j9_validite',
            corps_fr="Valable jusqu'au {date_validite}.")
        devis = self._devis('DEV-MRY13-0002',
                            date_validite=datetime.date(2026, 10, 15))
        rendu = message_pour_etape(
            self._touche(template_cle='j9_validite', devis=devis),
            user=self.acteur)
        self.assertIn('15/10/2026', rendu['message'])
        self.assertEqual(rendu['placeholders_manquants'], [])

    def test_le_lien_est_lURL_reelle_de_la_proposition(self):
        MessageTemplate.objects.create(
            company=self.company, cle='j1_pdf', corps_fr='Voici : {lien}')
        devis = self._devis('DEV-MRY13-0003')
        rendu = message_pour_etape(
            self._touche(template_cle='j1_pdf', devis=devis),
            user=self.acteur)
        from apps.ventes.utils.client_links import url_proposition
        self.assertIn(url_proposition(devis), rendu['message'])

    def test_aucun_chiffre_de_prix_ne_peut_etre_un_placeholder(self):
        """Prix, kWc et économies restent dans le devis : un `{prix}` laissé
        dans un gabarit ne serait JAMAIS rempli — il resterait visible, ce que
        la garde de placeholders de MRY12 interdit déjà à la saisie."""
        from apps.parametres.models_messages import PLACEHOLDERS_RELANCE
        for interdit in ('{prix}', '{montant}', '{kwc}', '{economie}'):
            self.assertNotIn(interdit, PLACEHOLDERS_RELANCE)


class VocalTests(_Base):
    slug = 'mry13-vocal'

    def test_le_vocal_nouvre_que_la_conversation(self):
        """Le texte de `vocal_j3` est un SCRIPT À DIRE : le pré-remplir dans
        WhatsApp ferait coller à Meryem le script au lieu de le prononcer."""
        rendu = message_pour_etape(
            self._touche(template_cle='vocal_j3'), user=self.acteur)
        self.assertNotIn('?text=', rendu['wa_url'])
        self.assertTrue(rendu['message'])
        self.assertNotIn('{', rendu['message'])

    def test_les_autres_touches_pre_remplissent_bien(self):
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertIn('?text=', rendu['wa_url'])


class NumeroInvalideTests(_Base):
    slug = 'mry13-numero'

    def test_wa_url_null_sans_numero(self):
        self.lead.telephone = None
        self.lead.whatsapp = None
        self.lead.save(update_fields=['telephone', 'whatsapp'])
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertIsNone(rendu['wa_url'])

    def test_le_POST_refuse_un_numero_inexploitable(self):
        """Prétendre avoir contacté quelqu'un qu'on ne peut pas joindre
        fausserait la file du lendemain ET le KPI."""
        self.lead.telephone = None
        self.lead.whatsapp = None
        self.lead.save(update_fields=['telephone', 'whatsapp'])
        touche = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/whatsapp/')
        self.assertEqual(resp.status_code, 400)
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.A_FAIRE)


class ApiTests(_Base):
    slug = 'mry13-api'

    def test_message_est_une_lecture_ouverte_a_tout_role(self):
        touche = self._touche()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.normal)}')
        resp = api.get(
            f'/api/django/crm/relance-etapes/{touche.pk}/message/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for cle in ('message', 'wa_url', 'langue', 'phone',
                    'placeholders_manquants'):
            self.assertIn(cle, resp.data)

    def test_message_ne_marque_RIEN(self):
        touche = self._touche()
        self.api.get(f'/api/django/crm/relance-etapes/{touche.pk}/message/')
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.A_FAIRE)

    def test_whatsapp_est_refuse_au_role_normal(self):
        touche = self._touche()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.normal)}')
        resp = api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/whatsapp/')
        self.assertEqual(resp.status_code, 403)

    def test_le_POST_marque_fait_et_pose_le_premier_contact(self):
        touche = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/whatsapp/')
        self.assertEqual(resp.status_code, 200, resp.data)
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)
        # MRY10 — une activité TYPÉE WhatsApp, pas une note libre.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.WHATSAPP).exists())

    def test_la_reponse_du_POST_porte_letape_a_jour(self):
        touche = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/whatsapp/')
        self.assertEqual(resp.data['etape']['statut'], 'fait')

    def test_touche_dune_autre_societe_404(self):
        autre = _company('mry13-autre')
        owner = User.objects.create_user(
            username='mry13-autre-u', password='x', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', owner=owner,
            telephone='+212661998877')
        touche = RelanceEtape.objects.create(
            company=autre, lead=lead_autre, ordre=1, canal='whatsapp',
            due_date=LUNDI.date(), cadence='contact', template_cle='identite')
        self.assertEqual(
            self.api.get(
                f'/api/django/crm/relance-etapes/{touche.pk}/message/'
            ).status_code, 404)


class AucunEnvoiReseauTests(_Base):
    """Garde négative (décision D5) : le serveur RÉEND, il n'ENVOIE jamais."""

    slug = 'mry13-d5'

    def test_le_module_nimporte_aucun_client_denvoi(self):
        import ast
        import inspect

        from apps.crm import services
        source = inspect.getsource(services.message_pour_etape)
        # La docstring de la fonction EXPLIQUE volontairement l'absence de
        # BSP (« Aucun BSP, aucun appel réseau sortant ») : un grep littéral
        # sur la source complète se prend lui-même au mot. On retire la
        # docstring via l'AST (jamais en l'effaçant du code — elle reste,
        # seul le TEXTE analysé change) avant de chercher du CODE interdit.
        arbre = ast.parse(source)
        fonction = arbre.body[0]
        corps = fonction.body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            corps = corps[1:]
        code_sans_docstring = '\n'.join(
            ast.get_source_segment(source, noeud) or '' for noeud in corps)
        for interdit in ('requests.', 'urlopen', 'send_mail', 'bsp',
                         'graph.facebook'):
            self.assertNotIn(interdit, code_sans_docstring.lower())

    def test_le_defaut_du_gabarit_reste_celui_de_MRY12(self):
        """Le rendu part des textes VALIDÉS, jamais d'un texte fabriqué."""
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        defaut = MESSAGE_TEMPLATE_DEFAULTS['identite']
        self.assertIn(defaut.split('{prenom}')[0].strip()[:20],
                      rendu['message'])
