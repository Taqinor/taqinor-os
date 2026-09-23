"""CAD79 — le « vocal » ne part plus en texte écrit.

Avant : la touche 7 (``vocal_j3``, canal WhatsApp) n'avait qu'un seul chemin
d'écran, l'aperçu WhatsApp, qui proposait « Ouvrir WhatsApp » : le geste
attendu (une note VOCALE) devenait mécaniquement un message écrit. Le serveur
retirait déjà ``?text=`` du lien, mais rien ne disait à l'écran qu'il
s'agissait d'un script à DIRE.

Done (moitié serveur) : le rendu porte ``vocal`` — l'aperçu en fait un script
à lire et son CTA dit « Enregistrer une note vocale » (test frontend) — et le
lien n'a toujours aucun texte pré-rempli. Contrat partagé :
``relance_etape_message.json`` (variante ``exemple_vocal``).
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import message_pour_etape
from apps.parametres.models import CompanyProfile

User = get_user_model()

JOUR = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class VocalTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD79 Solaire',
                                              slug='cad79')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad79-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212651971400', whatsapp='+212651971400')

    def _touche(self, template_cle):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=7, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Relance — script du vocal (J3)',
            template_cle=template_cle, due_at=JOUR, due_date=JOUR.date())

    def test_le_script_du_vocal_est_marque_et_sans_texte_pre_rempli(self):
        rendu = message_pour_etape(self._touche('vocal_j3'), user=self.acteur)
        self.assertIs(rendu['vocal'], True)
        self.assertTrue(rendu['wa_url'].startswith('https://wa.me/'))
        self.assertNotIn('?text=', rendu['wa_url'])
        self.assertIn('Aziz', rendu['message'])
        self.assertEqual(set(rendu),
                         set(_contrat('relance_etape_message')['exemple']))

    def test_un_message_ecrit_n_est_jamais_marque_vocal(self):
        rendu = message_pour_etape(self._touche('valeur_j1'), user=self.acteur)
        self.assertIs(rendu['vocal'], False)
        self.assertIn('?text=', rendu['wa_url'])
