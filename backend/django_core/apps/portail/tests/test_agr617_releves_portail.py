"""AGR617 — monitoring pompage phase 1, sans dépendance payante : le client
saisit ses heures de pompage et l'index de son compteur d'eau sur le portail
(contrat ``mes_releves_pompage.json``).

Run :
    python manage.py test apps.portail.tests.test_agr617_releves_portail
"""
import json
import pathlib
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.installations.models import Installation
from apps.portail.tests.test_ntprt14_mes_chantiers import (
    make_client, make_company, make_portal_user,
)
from apps.sav.models import Equipement, ReleveCompteurEquipement
from apps.stock.models import Produit
from apps.ventes.models import Devis
from authentication.models import CustomUser

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'mes_releves_pompage.json').read_text(encoding='utf-8'))


class RelevesPompagePortailTests(TestCase):
    def setUp(self):
        self.company = make_company('agr617-co', 'AGR617 Société')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AGR617-1',
            client=self.client_a, statut='accepte',
            taux_tva=Decimal('20'), mode_installation='agricole',
            etude_params={'m3_jour': 134.2, 'debit_hmt_m3h': 30.5})
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-AGR617-1',
            client=self.client_a, devis=devis, type_installation='agricole')
        self.pompe = self._equipement(self.chantier, 'pompe',
                                      'Pompe immergée OSP')
        self.variateur = self._equipement(self.chantier, 'variateur_pompage',
                                          'Variateur VEICHI')
        self.panneau = self._equipement(self.chantier, '', 'Panneau 710W')
        user = make_portal_user(
            self.company, 'agr617-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.user = user
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def _equipement(self, chantier, role, nom):
        produit = Produit.objects.create(
            company=self.company, nom=nom, role_pompage=role,
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'))
        return Equipement.objects.create(
            company=self.company, produit=produit, installation=chantier)

    def _url(self, chantier):
        return f'/api/django/portail/mes-chantiers/{chantier.id}/releves/'

    def _post(self, corps, chantier=None):
        return self.api.post(self._url(chantier or self.chantier), corps,
                             format='json')

    def test_le_client_poste_un_releve_m3_visible_cote_sav(self):
        r = self._post({'equipement': self.pompe.id, 'type': 'm3',
                        'valeur': '1250', 'date': '2027-01-05'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data, {
            'equipement': self.pompe.id, 'type': 'm3', 'valeur': '1250.00',
            'date': '2027-01-05', 'moyenne_jour_depuis_precedent': None})
        releve = ReleveCompteurEquipement.objects.get(equipement=self.pompe)
        self.assertEqual(releve.company_id, self.company.id)
        self.assertEqual(releve.created_by_id, self.user.id)
        r = self._post({'equipement': self.pompe.id, 'type': 'm3',
                        'valeur': '1838', 'date': '2027-02-04'})
        self.assertEqual(r.data['moyenne_jour_depuis_precedent'], 19.6)
        # Visible côté SAV : l'historique de l'équipement le porte.
        self.assertEqual(
            list(self.pompe.releves_compteur.order_by('date')
                 .values_list('valeur', flat=True)),
            [Decimal('1250.00'), Decimal('1838.00')])

    def test_get_forme_du_contrat_et_m3_jour_du_devis(self):
        self._post({'equipement': self.pompe.id, 'type': 'm3',
                    'valeur': '1250', 'date': '2027-01-05'})
        self._post({'equipement': self.variateur.id, 'type': 'heures',
                    'valeur': '412', 'date': '2027-02-04'})
        r = self.api.get(self._url(self.chantier))
        self.assertEqual(r.status_code, 200, r.data)
        exemple = CONTRAT['exemple']
        self.assertEqual(set(r.data), set(exemple))
        self.assertEqual(set(r.data['equipements'][0]),
                         set(exemple['equipements'][0]))
        self.assertEqual(set(r.data['releves'][0]),
                         set(exemple['releves'][0]))
        ids = [e['id'] for e in r.data['equipements']]
        self.assertEqual(ids, [self.pompe.id, self.variateur.id])
        self.assertNotIn(self.panneau.id, ids)
        self.assertEqual(r.data['equipements'][0]['types_admis'], ['m3'])
        self.assertEqual(r.data['equipements'][1]['types_admis'], ['heures'])
        # Plus récent d'abord.
        self.assertEqual([x['date'] for x in r.data['releves']],
                         ['2027-02-04', '2027-01-05'])
        self.assertEqual(r.data['m3_jour_estime_devis'], 134.2)
        self.assertEqual(r.data['omissions'], [])
        texte = json.dumps(r.data)
        for interdit in ('prix', 'created_by', 'instrument', 'marge'):
            self.assertNotIn(interdit, texte)

    def test_sans_m3_jour_au_devis_null_et_motif(self):
        Devis.objects.filter(pk=self.chantier.devis_id).update(
            etude_params={'debit_hmt_m3h': 30.5})
        r = self.api.get(self._url(self.chantier))
        self.assertIsNone(r.data['m3_jour_estime_devis'])
        self.assertEqual(r.data['omissions'][0]['cle'],
                         'm3_jour_estime_devis')

    def test_chantier_d_un_autre_client_404(self):
        autre = Installation.objects.create(
            company=self.company, reference='CH-AGR617-2',
            client=self.client_b, type_installation='agricole')
        eq = self._equipement(autre, 'pompe', 'Pompe Beta')
        self.assertEqual(self.api.get(self._url(autre)).status_code, 404)
        r = self._post({'equipement': eq.id, 'type': 'm3', 'valeur': '10'},
                       chantier=autre)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data, CONTRAT['exemple_404'])
        self.assertFalse(ReleveCompteurEquipement.objects.exists())

    def test_recul_400(self):
        self._post({'equipement': self.pompe.id, 'type': 'm3',
                    'valeur': '1838', 'date': '2027-02-04'})
        r = self._post({'equipement': self.pompe.id, 'type': 'm3',
                        'valeur': '1500', 'date': '2027-03-01'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data, CONTRAT['exemple_400_recul'])

    def test_kwh_400(self):
        r = self._post({'equipement': self.pompe.id, 'type': 'kwh',
                        'valeur': '10'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data, CONTRAT['exemple_400_type'])
        self.assertFalse(ReleveCompteurEquipement.objects.exists())

    def test_equipement_d_un_autre_chantier_400(self):
        autre = Installation.objects.create(
            company=self.company, reference='CH-AGR617-3',
            client=self.client_a, type_installation='agricole')
        eq = self._equipement(autre, 'pompe', 'Pompe 2')
        r = self._post({'equipement': eq.id, 'type': 'm3', 'valeur': '10'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data, CONTRAT['exemple_400_equipement'])
        # Un équipement du chantier hors rôle pompage (panneau) aussi.
        r = self._post({'equipement': self.panneau.id, 'type': 'm3',
                        'valeur': '10'})
        self.assertEqual(r.status_code, 400, r.data)
