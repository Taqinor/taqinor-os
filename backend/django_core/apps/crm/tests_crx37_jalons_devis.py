"""CRX37 — les jalons devis entrent enfin dans l'historique du lead.

``apps.ventes.selectors.devis_events_for_lead`` (QX32be) avait été écrit POUR
que le CRM fusionne « devis envoyé / proposition ouverte / signé / refusé »
dans la timeline d'un lead, et n'avait AUCUN appelant. Côté écran tout était
prêt depuis QX32 (``ChatterTimeline`` rend les quatre ``kind``,
``matchesTimelineFilter`` expose le filtre « Devis ») : il ne manquait que la
source.

Ce module AFFIRME le contrat committé — ``apps/crm/contract_samples/
lead_jalons_devis.json`` — plutôt qu'une forme réécrite à la main ici : le
test frontend importe LE MÊME fichier, donc les deux moitiés ne peuvent plus
diverger en silence (PACT10).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.crm.selectors import lead_jalons_devis
from apps.roles.models import Role
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_jalons_devis.json').read_text(encoding='utf-8'))
EXEMPLES = CONTRAT['exemple']['results']
CLES_CONTRAT = set(EXEMPLES[0])
KINDS_CONTRAT = {ligne['kind'] for ligne in EXEMPLES}

MOIS = timezone.now().strftime('%Y%m')


class JalonsDevisContratTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX37', slug='taqinor-crx37')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial CRX37',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_crx37', password='x', company=self.company,
            role=self.role)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Amina',
            telephone='+212600000037')
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani',
            telephone='+212600000037')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-CRX37',
            client=self.client_obj, lead=self.lead, taux_tva=Decimal('20'),
            statut=Devis.Statut.ACCEPTE,
            date_envoi=timezone.now(),
            date_acceptation=timezone.localdate())
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            first_viewed_at=timezone.now())
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _resultats(self):
        res = self.api.get(f'/api/django/crm/leads/{self.lead.pk}/jalons-devis/')
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def test_enveloppe_conforme_au_contrat(self):
        """La réponse porte la clé ``results`` de l'exemple committé."""
        donnees = self._resultats()
        self.assertEqual(set(donnees), set(CONTRAT['exemple']))
        self.assertIsInstance(donnees['results'], list)

    def test_chaque_ligne_porte_exactement_les_cles_du_contrat(self):
        for ligne in self._resultats()['results']:
            self.assertEqual(set(ligne), CLES_CONTRAT, ligne)

    def test_les_trois_jalons_du_contrat_sont_produits(self):
        kinds = {ligne['kind'] for ligne in self._resultats()['results']}
        self.assertEqual(kinds, KINDS_CONTRAT)

    def test_l_id_suit_le_format_du_contrat(self):
        """``devis-<devis_id>-<kind>`` — textuel et stable, jamais en
        collision avec les id NUMÉRIQUES de ``LeadActivity`` que l'écran
        fusionne dans la même liste."""
        attendus = {
            f'devis-{self.devis.pk}-signed',
            f'devis-{self.devis.pk}-opened',
            f'devis-{self.devis.pk}-sent',
        }
        ids = {ligne['id'] for ligne in self._resultats()['results']}
        self.assertEqual(ids, attendus)
        for identifiant in ids:
            self.assertIsInstance(identifiant, str)

    def test_les_notes_du_contrat_sont_vraies(self):
        """Le contrat promet ``user_nom`` toujours nul, ``pinned`` toujours
        faux, la référence en ``body``, et le plus récent d'abord."""
        lignes = self._resultats()['results']
        for ligne in lignes:
            self.assertIsNone(ligne['user_nom'])
            self.assertFalse(ligne['pinned'])
            self.assertEqual(ligne['body'], self.devis.reference)
            self.assertEqual(ligne['reference'], self.devis.reference)
            self.assertEqual(ligne['devis_id'], self.devis.pk)
        horodatages = [ligne['created_at'] for ligne in lignes]
        self.assertEqual(horodatages, sorted(horodatages, reverse=True))

    def test_lead_sans_devis_renvoie_une_liste_vide(self):
        vide = Lead.objects.create(company=self.company, nom='Sans devis')
        res = self.api.get(f'/api/django/crm/leads/{vide.pk}/jalons-devis/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data, {'results': []})

    def test_selecteur_tolere_un_lead_absent(self):
        self.assertEqual(lead_jalons_devis(None), [])

    def test_aucun_montant_n_est_expose(self):
        """Des JALONS, pas des prix — et jamais de ``prix_achat``."""
        interdits = {'montant', 'total', 'total_ttc', 'total_ht', 'prix',
                     'prix_achat', 'marge'}
        for ligne in self._resultats()['results']:
            self.assertEqual(set(ligne) & interdits, set(), ligne)


class JalonsDevisIsolationTests(TestCase):
    """Le lead d'une autre société n'est jamais atteignable (le
    ``get_object()`` de la vue est déjà scopé — on le VÉRIFIE)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX37 A', slug='taqinor-crx37-a')
        self.autre = Company.objects.create(
            nom='Taqinor CRX37 B', slug='taqinor-crx37-b')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial CRX37b',
            permissions=['crm_voir'])
        self.user = User.objects.create_user(
            username='resp_crx37b', password='x', company=self.company,
            role=self.role)
        self.lead_autre = Lead.objects.create(
            company=self.autre, nom='Lead voisin')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_lead_d_une_autre_societe_est_404(self):
        res = self.api.get(
            f'/api/django/crm/leads/{self.lead_autre.pk}/jalons-devis/')
        self.assertEqual(res.status_code, 404)
