"""AGR522 — champ interne ``dossier_subvention`` + rappel « 3 mois après
l'approbation préalable » (Guide FDA 2024, p.22-23).

Contrat partagé : ``apps/crm/contract_samples/lead_dossier_subvention.json``
(AGR501). Le champ est INTERNE : jamais dans une charge utile client.

Run :
    python manage.py test apps.crm.tests_agr_dossier_subvention -v 2
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import activity, services
from apps.crm.models import Client, Lead, RelanceEtape

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_dossier_subvention.json').read_text(encoding='utf-8'))


class RegleDuContrat(SimpleTestCase):
    def test_les_valeurs_et_libelles_sont_ceux_du_contrat(self):
        self.assertEqual(dict(Lead.DossierSubvention.choices),
                         CONTRAT['notes']['libelles'])

    def test_le_message_400_est_celui_du_contrat(self):
        from apps.crm.serializers import LeadSerializer
        self.assertEqual(
            [LeadSerializer.MESSAGE_DATE_SUBVENTION],
            CONTRAT['exemple_400']['dossier_subvention_le'])

    def test_les_deux_colonnes_sont_journalisees(self):
        self.assertIn('dossier_subvention', activity.TRACKED_FIELDS)
        self.assertIn('dossier_subvention_le', activity.TRACKED_FIELDS)

    def test_trois_mois_apres_le_10_10_c_est_le_10_01(self):
        libelle = services.libelle_rappel_subvention(
            datetime.date(2026, 10, 10))
        self.assertIn('Approbation préalable du 10/10', libelle)
        self.assertIn('avant le 10/01', libelle)
        self.assertIn('Guide FDA 2024, p.22-23', libelle)

    def test_fin_de_mois_ramenee(self):
        self.assertEqual(services._ajouter_mois(datetime.date(2026, 11, 30), 3),
                         datetime.date(2027, 2, 28))


class DossierSubventionApi(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AGR522 Co', slug='agr522-co')
        self.user = User.objects.create_user(
            username='agr522_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Fellah', type_installation='agricole',
            telephone='+212600000522')
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def _patch(self, corps):
        return self.api.patch(self.url, corps, format='json')

    def test_depose_sans_date_refuse_en_400_nommant_le_champ(self):
        resp = self._patch({'dossier_subvention': 'depose'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            [str(m) for m in resp.data['dossier_subvention_le']],
            CONTRAT['exemple_400']['dossier_subvention_le'])

    def test_le_corps_du_contrat_est_accepte_et_relu(self):
        resp = self._patch(CONTRAT['corps'])
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(self.url).data
        for cle in ('dossier_subvention', 'dossier_subvention_le'):
            self.assertEqual(lu[cle], CONTRAT['exemple'][cle])

    def test_accorde_le_10_10_pose_l_etape_une_seule_fois(self):
        corps = {'dossier_subvention': 'accorde',
                 'dossier_subvention_le': '2026-10-10'}
        self.assertEqual(self._patch(corps).status_code, 200)
        etapes = RelanceEtape.objects.filter(
            lead=self.lead, libelle__contains='avant le 10/01')
        self.assertEqual(etapes.count(), 1)
        self.assertEqual(etapes.get().cadence, 'generique')
        # Rejouer (geste identique, ou appel direct) ne double rien.
        self.assertEqual(self._patch(corps).status_code, 200)
        self.lead.refresh_from_db()
        services.poser_rappel_subvention(self.lead)
        self.assertEqual(etapes.count(), 1)

    def test_enregistrer_rouvrir_enregistrer_sans_toucher_est_identique(self):
        self._patch(CONTRAT['corps'])
        avant = self.api.get(self.url).data
        self.assertEqual(self._patch({}).status_code, 200)
        apres = self.api.get(self.url).data
        for cle in ('dossier_subvention', 'dossier_subvention_le'):
            self.assertEqual(apres[cle], avant[cle])

    def test_la_valeur_n_apparait_pas_dans_la_proposition_publique(self):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis, ShareLink

        self._patch(CONTRAT['corps'])
        client = Client.objects.create(company=self.company, nom='Fellah')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AGR522-01', client=client,
            lead=self.lead, statut='envoye', taux_tva=Decimal('20'),
            mode_installation='agricole', etude_params={})
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc', prix_vente='1500',
            quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau 550 Wc',
            quantite=Decimal('4'), prix_unitaire=Decimal('1500'),
            remise=Decimal('0'))
        lien = ShareLink.objects.create(company=self.company, devis=devis)
        resp = APIClient().get(
            f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        texte = json.dumps(resp.json(), ensure_ascii=False)
        self.assertNotIn('dossier_subvention', texte)
        self.assertNotIn('2026-10-20', texte)
        self.assertNotIn('approbation préalable', texte.lower())
