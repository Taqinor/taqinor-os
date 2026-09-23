"""CAD69 — les crochets ``[ ]`` ne partent plus tels quels dans WhatsApp.

Avant : ``render_message_template`` ne substitue que les ``{accolades}``,
MRY13 n'omet que les phrases à accolades vides et ``placeholders_manquants``
n'est calculé que sur ``{cle}`` — ``rappel_plus_tard`` partait avec « [jour] à
[heure] » écrits en toutes lettres, ``offre_reda`` avec « [montant en
dirhams] », alors que le catalogue promet « jamais un crochet vide envoyé au
client ».

Done : le rendu LISTE les crochets (``crochets``) ; l'aperçu les affiche dans
le bandeau et désactive « Ouvrir WhatsApp » (test frontend). Contrat partagé :
la réponse a EXACTEMENT les clés de ``relance_etape_message.json``, et la
variante ``exemple_crochets`` est l'accusé « plus tard ».

Aucun gel d'horloge ici (aucune assertion de date) : la partie pure
(``CrochetsPursTests``) tourne sans base.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import crochets_a_completer
from apps.parametres.models import CompanyProfile

User = get_user_model()

JOUR = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class CrochetsPursTests(SimpleTestCase):

    def test_les_blancs_sont_listes_dans_l_ordre_sans_doublon(self):
        texte = ('Je vous rappelle [jour] à [heure]. '
                 'Rappel : [jour] reste à confirmer.')
        self.assertEqual(crochets_a_completer(texte), ['[jour]', '[heure]'])

    def test_un_texte_sans_crochet_ne_liste_rien(self):
        self.assertEqual(crochets_a_completer('Bonjour M. Aziz.'), [])
        self.assertEqual(crochets_a_completer(''), [])
        self.assertEqual(crochets_a_completer(None), [])

    def test_les_blancs_de_l_offre_du_fondateur(self):
        texte = ('Suite à votre échange : [la raison réelle], il vous '
                 'accorde [montant en dirhams], soit [nouveau total TTC].')
        self.assertEqual(crochets_a_completer(texte), [
            '[la raison réelle]', '[montant en dirhams]',
            '[nouveau total TTC]'])

    def test_les_blancs_darija_aussi(self):
        self.assertEqual(
            crochets_a_completer('غادي نعيط ليكم [النهار] على [الساعة].'),
            ['[النهار]', '[الساعة]'])

    def test_un_crochet_ne_traverse_jamais_une_ligne(self):
        self.assertEqual(crochets_a_completer('[début\nfin]'), [])


class CrochetsRendusTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD69 Solaire', slug='cad69')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad69-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212651971400', whatsapp='+212651971400')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, template_cle='valeur_j1'):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=5, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Message valeur (J1)', template_cle=template_cle,
            due_at=JOUR, due_date=JOUR.date())

    def test_l_accuse_plus_tard_liste_ses_crochets(self):
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{self._touche().pk}/message/',
            {'cle': 'rappel_plus_tard'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crochets'], ['[jour]', '[heure]'])
        # Les crochets restent des crochets : jamais un jour inventé.
        self.assertIn('[jour]', resp.data['message'])
        # MÊME forme que le contrat, et sa variante `exemple_crochets`.
        contrat = _contrat('relance_etape_message')
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        self.assertEqual(resp.data['crochets'],
                         contrat['exemple_crochets']['crochets'])

    def test_un_message_sans_blanc_ne_liste_rien(self):
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{self._touche().pk}/message/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crochets'], [])
