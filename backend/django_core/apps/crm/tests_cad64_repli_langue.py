"""CAD64 — le repli de langue devient VISIBLE (darija, anglais, arabe).

Avant : ``message_pour_etape`` lisait ``lead.langue_preferee or 'fr'`` au lieu
du résolveur COMMUN des documents client (``resolve_langue_sortie`` — un devis
pouvait partir en arabe pendant que la relance restait en français), et
``MessageTemplate.get_corps`` retombait sur le français sans un mot quand la
clé n'avait pas de texte dans la langue demandée.

Done : une touche dont la clé n'a pas de darija renvoie le drapeau
``repli_langue`` (l'aperçu affiche l'avertissement — test frontend) ; la
langue passe par le résolveur commun ; aucun texte anglais ni arabe classique
n'est ouvert par défaut. Contrat partagé : les réponses ont EXACTEMENT les
clés de l'exemple committé ``relance_etape_message.json``.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import (
    langue_relance_du_lead, message_pour_etape, texte_en_repli_de_langue,
)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import MessageTemplate

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'cad64'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD64 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Omar',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661000552', whatsapp='+212661000552')
        # Une clé SANS texte darija (ni défaut, ni texte société) : le
        # français de la société est le seul texte validé.
        MessageTemplate.objects.create(
            company=self.company, cle='relance',
            corps_fr='Bonjour {civilite} {prenom}, petit mot de suivi de '
                     'votre demande solaire.')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, template_cle='relance'):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=5, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Message de suivi', template_cle=template_cle,
            due_at=MERCREDI, due_date=MERCREDI.date())


class ReplisDarijaTests(_Base):
    slug = 'cad64-darija'

    def setUp(self):
        super().setUp()
        self.lead.langue_preferee = 'darija'
        self.lead.save(update_fields=['langue_preferee'])

    def test_une_cle_sans_darija_leve_le_drapeau_de_repli(self):
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertEqual(rendu['langue'], 'darija')
        self.assertTrue(rendu['repli_langue'])
        # C'est bien la version FRANÇAISE qui part — rendue comme un texte
        # français : « M. », jamais « السي » dans une phrase française.
        self.assertIn('Bonjour M. Omar', rendu['message'])
        self.assertNotIn('السي', rendu['message'])

    def test_une_cle_avec_darija_ne_leve_rien(self):
        rendu = message_pour_etape(self._touche('valeur_j1'), user=self.acteur)
        self.assertEqual(rendu['langue'], 'darija')
        self.assertFalse(rendu['repli_langue'])
        self.assertIn('السلام', rendu['message'])

    def test_l_api_renvoie_le_drapeau_a_la_forme_du_contrat(self):
        etape = self._touche()
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{etape.pk}/message/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIs(resp.data['repli_langue'], True)
        self.assertEqual(set(resp.data),
                         set(_contrat('relance_etape_message')['exemple']))

    def test_jamais_de_traduction_automatique(self):
        self.assertTrue(texte_en_repli_de_langue(
            self.company, 'relance', 'darija'))
        # Le catalogue n'a rien écrit à la place de la société.
        ligne = MessageTemplate.objects.get(company=self.company, cle='relance')
        self.assertEqual(ligne.corps_darija, '')


class ResolveurCommunTests(_Base):
    slug = 'cad64-resolveur'

    def test_sans_preference_la_langue_documentaire_du_client_est_suivie(self):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', langue_document='ar')
        self.lead.client = client
        self.lead.save(update_fields=['client'])
        self.assertEqual(langue_relance_du_lead(self.lead), 'ar')
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        # Aucun texte arabe classique n'est ouvert par défaut : le français
        # part, et le repli est DIT (un devis arabe ne laisse plus la relance
        # en français en silence).
        self.assertEqual(rendu['langue'], 'ar')
        self.assertTrue(rendu['repli_langue'])
        self.assertIn('Bonjour M. Omar', rendu['message'])

    def test_un_texte_arabe_ecrit_par_la_societe_part_sans_repli(self):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', langue_document='ar')
        self.lead.client = client
        self.lead.save(update_fields=['client'])
        MessageTemplate.objects.filter(
            company=self.company, cle='relance').update(
                corps_ar='مرحبا {prenom}، متابعة لطلبكم.')
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertFalse(rendu['repli_langue'])
        self.assertIn('مرحبا Omar', rendu['message'])

    def test_la_preference_du_lead_prime_sur_le_client(self):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', langue_document='ar')
        self.lead.client = client
        self.lead.langue_preferee = 'fr'
        self.lead.save(update_fields=['client', 'langue_preferee'])
        self.assertEqual(langue_relance_du_lead(self.lead), 'fr')
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertEqual(rendu['langue'], 'fr')
        self.assertFalse(rendu['repli_langue'])

    def test_sans_client_ni_preference_le_francais_reste_le_defaut(self):
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertEqual(rendu['langue'], 'fr')
        self.assertFalse(rendu['repli_langue'])
