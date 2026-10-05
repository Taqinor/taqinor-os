"""CIQ403 — résolution lead → Client ENTREPRISE (contrat CIQ8
``client_entreprise.json``) : raison sociale, ICE d'abord, conflit visible.

Appelants de ``resolve_client_for_lead`` vérifiés (grep, 05/10/2026) : aucun
ne suppose un particulier — ventes/views/devis.py (perform_create + atomic),
ventes/domain/creation.py (×2), ventes/domain/pipeline.py, crm/services.py
(``convertir_lead_en_client``), automation/actions.py (``except Exception`` →
None). ``ConflitIdentiteEntreprise`` est une ``ValidationError`` DRF : les
appelants HTTP rendent un 400 sans être modifiés.

Run :
    python manage.py test apps.crm.tests_ciq403_resolution_entreprise -v 2
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm.services import (
    ConflitIdentiteEntreprise, resolve_client_for_lead)

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'client_entreprise.json').read_text(encoding='utf-8'))


class ResolutionEntreprise(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq403-co', defaults={'nom': 'CIQ403 Co'})

    def _lead(self, **kw):
        return Lead.objects.create(company=self.company, **kw)

    def test_raison_sociale_nomme_le_client_la_personne_est_le_contact(self):
        lead = self._lead(nom='Alaoui', prenom='Karim', societe='Hôtel Atlas',
                          type_installation='commercial',
                          fonction_contact='Directeur', tva_recuperable='oui',
                          ice='000000000000000')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.type_client, 'entreprise')
        self.assertEqual(client.nom, 'Hôtel Atlas')
        self.assertIsNone(client.prenom)
        self.assertEqual(client.contact_nom, 'Karim Alaoui')
        self.assertEqual(client.contact_fonction, 'Directeur')
        self.assertEqual(client.ice, '000000000000000')
        self.assertEqual(client.tva_recuperable, 'oui')
        self.assertFalse(client.raison_sociale_a_confirmer)

    def test_pro_sans_raison_sociale_nom_de_la_personne_a_confirmer(self):
        lead = self._lead(nom='Exemple', prenom='Youssef',
                          type_installation='industriel')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.type_client, 'entreprise')
        self.assertEqual(client.nom, 'Youssef Exemple')
        self.assertTrue(client.raison_sociale_a_confirmer)

    def test_meme_ice_meme_client(self):
        a = self._lead(nom='A', societe='Atelier SA', ice='000000000000000',
                       email='a@atelier.example',
                       type_installation='industriel')
        b = self._lead(nom='B', societe='Atelier SA', ice='000 000000000000',
                       email='b@atelier.example',
                       type_installation='industriel')
        self.assertEqual(resolve_client_for_lead(a).pk,
                         resolve_client_for_lead(b).pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(),
                         1)

    def test_meme_email_ice_different_conflit_sans_creation(self):
        Client.objects.create(
            company=self.company, nom='Atelier Exemple SA',
            type_client='entreprise', ice='111111111111111',
            email='compta@groupe.example')
        lead = self._lead(nom='B', societe='Filiale SA',
                          ice='000000000000000',
                          email='compta@groupe.example',
                          type_installation='commercial')
        with self.assertRaises(ConflitIdentiteEntreprise) as ctx:
            resolve_client_for_lead(lead)
        detail = ctx.exception.detail
        self.assertEqual(set(detail), set(CONTRAT['exemple_conflit']))
        self.assertEqual(detail['code'], 'conflit_identite_entreprise')
        self.assertEqual(detail['champ'], 'ice')
        self.assertEqual(Client.objects.filter(company=self.company).count(),
                         1)
        lead.refresh_from_db()
        self.assertIsNone(lead.client_id)

    def test_meme_telephone_ice_different_conflit(self):
        Client.objects.create(
            company=self.company, nom='Autre SA', type_client='entreprise',
            ice='111111111111111', telephone='0612340403')
        lead = self._lead(nom='B', societe='Filiale SA',
                          ice='000000000000000', telephone='0612340403',
                          type_installation='commercial')
        with self.assertRaises(ConflitIdentiteEntreprise):
            resolve_client_for_lead(lead)

    def test_residentiel_identique(self):
        lead = self._lead(nom='Benali', prenom='Amina',
                          email='amina@example.com', telephone='0612345590',
                          adresse='12 rue X', ville='Settat')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.type_client, 'particulier')
        self.assertEqual(client.nom, 'Benali')
        self.assertEqual(client.prenom, 'Amina')
        self.assertEqual(client.adresse, '12 rue X, Settat')
        for champ in ('contact_nom', 'contact_fonction', 'ice', 'rc',
                      'if_fiscal', 'adresse_siege', 'tva_recuperable'):
            self.assertIsNone(getattr(client, champ), champ)
        self.assertFalse(client.raison_sociale_a_confirmer)


class ConflitParLeDevis(TestCase):
    def test_post_devis_400_qui_nomme_ice_jamais_500(self):
        company, _ = Company.objects.get_or_create(
            slug='ciq403-devis', defaults={'nom': 'CIQ403 Devis'})
        user = User.objects.create_user(
            username='ciq403_devis', password='x',
            role_legacy='responsable', company=company)
        Client.objects.create(
            company=company, nom='Atelier Exemple SA',
            type_client='entreprise', ice='111111111111111',
            email='compta@groupe.example')
        lead = Lead.objects.create(
            company=company, nom='B', societe='Filiale SA',
            ice='000000000000000', email='compta@groupe.example',
            type_installation='commercial')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.post('/api/django/ventes/devis/', {
            'lead': lead.id, 'statut': 'brouillon',
            'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['champ'], 'ice')
        self.assertEqual(Client.objects.filter(company=company).count(), 1)
