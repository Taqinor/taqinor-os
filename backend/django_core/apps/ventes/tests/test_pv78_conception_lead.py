"""PV78 — la fiche lead expose la conception 3D de son devis.

Trois garanties :

* le sélecteur ventes est COMPANY-SCOPÉ (un devis d'une autre société ne fuit
  rien) et rend TOUJOURS ses deux clés ;
* ``crm`` lit ``ventes`` par son SÉLECTEUR, jamais par ses modèles ;
* le bloc n'est servi que sur la fiche (RETRIEVE) — jamais sur la liste, où il
  coûterait une requête + une URL pré-signée par carte.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv78_conception_lead -v 2
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.calepinage.selectors import reference_calepinage
from apps.crm.selectors import conception_3d_du_lead
from apps.ventes.models import Devis
from apps.ventes.selectors import conception_pour_lead
from authentication.models import Company

User = get_user_model()

LAYOUT = {'result': {'kwc': 7.7, 'panels': 14, 'annualKwh': 12000},
          '_pans_geometry': [{'label': 'Sud', 'nb_panneaux': 14}]}


class ConceptionPourLeadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv78-acme")
        self.other = Company.objects.create(nom="Autre", slug="pv78-autre")
        self.user = User.objects.create_user(
            username="pv78_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom="Lead PV78", telephone="0600000078")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV78", email="pv78@example.com")
        self.crm_client_autre = Client.objects.create(
            company=self.other, nom="Client PV78 bis",
            email="pv78bis@example.com")

    def _conception(self, kwc=21.6, option='sans', lead=None, **extra):
        """ACAL2021 — la conception COURANTE rangée du lead (moteur unique)."""
        from apps.ventes.models import ConceptionLead
        champs = dict(
            etat='complet', marche='residentiel', option_retenue=option,
            valeurs={option: {'puissance_kwc': {'valeur': kwc, 'unite': 'kWc', 'source': 'moteur'}}},
            empreinte='a' * 64, niveau_regles=14, version_moteur='t')
        champs.update(extra)
        return ConceptionLead.ranger(lead=lead or self.lead, **champs)

    def _devis(self, company=None, layout=LAYOUT, image='', lead=None):
        company = company or self.company
        return Devis.objects.create(
            company=company,
            reference="DV-PV78-%s" % Devis.objects.count(),
            client=(self.crm_client if company == self.company
                    else self.crm_client_autre),
            lead=lead if lead is not None else self.lead,
            roof_layout=layout, roof_image=image,
            etude_params={'puissance_kwc': 9.9})

    def test_toujours_les_deux_cles_sans_devis(self):
        self.assertEqual(conception_pour_lead(self.lead, self.company),
                         {'kwc': None, 'image_url': None, 'calepinage': None,
                          'devis': None})

    def test_kwc_de_la_conception_jamais_celui_du_devis(self):
        # ACAL2021 — un devis à 7,7 kWc (calepinage) et 9,9 (étude), une
        # conception à 21,6 : la pastille rend 21,6.
        self._devis()
        self._conception(21.6)
        self.assertEqual(conception_pour_lead(self.lead, self.company)['kwc'], 21.6)

    def test_sans_conception_kwc_nul_jamais_suppose(self):
        # Ni le calepinage du devis, ni la puissance de l'étude ne remplacent
        # la conception : sans conception rangée, ``null``.
        self._devis()
        self._devis(layout={'zones': []})
        self.assertIsNone(conception_pour_lead(self.lead, self.company)['kwc'])

    def test_devis_sans_calepinage_ignore(self):
        self._devis(layout=None)
        self.assertIsNone(
            conception_pour_lead(self.lead, self.company)['kwc'])

    def test_deux_brouillons_la_pastille_suit_la_conception(self):
        # Mesuré en direct : deux brouillons à 4,40 et 6,05 kWc, la pastille
        # suivait le DERNIER devis (copie périmée) au lieu de la conception.
        self._devis(layout={'result': {'kwc': 4.4}})
        self._devis(layout={'result': {'kwc': 6.05}})
        self._conception(5.5)
        self.assertEqual(conception_pour_lead(self.lead, self.company)['kwc'], 5.5)

    def test_option_retenue_de_la_conception(self):
        self._conception(7.2, option='avec',
                         valeurs={'sans': {'puissance_kwc': {'valeur': 6.0, 'unite': 'kWc', 'source': 'moteur'}},
                                  'avec': {'puissance_kwc': {'valeur': 7.2, 'unite': 'kWc', 'source': 'moteur'}}})
        self.assertEqual(conception_pour_lead(self.lead, self.company)['kwc'], 7.2)

    def test_conception_refusee_kwc_nul(self):
        self._conception(etat='refus', option_retenue='', valeurs={},
                         refus={'code': 'localisation_inconnue', 'champ': 'ville', 'message': 'x'})
        self.assertIsNone(conception_pour_lead(self.lead, self.company)['kwc'])

    def test_scope_societe(self):
        self._devis(company=self.other)
        # Même lead, autre société sur le devis → rien ne remonte.
        self.assertEqual(conception_pour_lead(self.lead, self.company),
                         {'kwc': None, 'image_url': None, 'calepinage': None,
                          'devis': None})

    def test_conception_d_une_autre_societe_ne_remonte_pas(self):
        self._conception(8.8)  # rangée sous la société du lead : l'autre société ne la lit pas
        self.assertIsNone(conception_pour_lead(self.lead, self.other)['kwc'])

    def test_image_url_chemin_relatif_meme_origine(self):
        # ACAL314 — un chemin RELATIF servi par Django, plus une URL
        # pré-signée (hôte interne minio:9000, injoignable du navigateur).
        devis = self._devis(image='ventes/1/rendu.png')
        with mock.patch('apps.ventes.utils.pdf.roof_image_signed_url',
                        return_value='https://minio/signed?x=1') as signe:
            resultat = conception_pour_lead(self.lead, self.company)
        self.assertEqual(
            resultat['image_url'],
            f'/api/django/ventes/devis/{devis.pk}/roof-image/fichier/')
        signe.assert_not_called()

    def test_stockage_indisponible_ne_casse_rien(self):
        # Le chemin ne lit pas le magasin : une panne de stockage ne touche
        # ni le kWc ni la fiche (le proxy répondra 404 au navigateur).
        self._devis(image='ventes/1/rendu.png')
        self._conception(7.7)
        with mock.patch('apps.ventes.utils.pdf.roof_image_signed_url',
                        side_effect=RuntimeError('MinIO down')):
            resultat = conception_pour_lead(self.lead, self.company)
        self.assertTrue(resultat['image_url'].startswith('/api/django/'))
        self.assertEqual(resultat['kwc'], 7.7)

    # ── ACAL2021 — la pastille lit la CONCEPTION, plus le vendu ni le calepinage ──
    def test_pastille_ne_lit_plus_le_vendu(self):
        """Devis 10 lignes de 550 W (5,5 kWc, ``puissance_kwc_du_devis``) et
        une conception à 8,0 kWc : la pastille dit 8,0 (ACAL273 remplacé)."""
        from decimal import Decimal

        from apps.stock.models import Produit
        devis = self._devis(layout={'result': {'kwc': 7.2, 'panels': 10}})
        produit = Produit.objects.create(
            company=self.company, nom='Panneau Solar 550W', sku='ACAL273-550',
            prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
            quantite_stock=100)
        devis.lignes.create(
            produit=produit, designation='Panneau Solar 550W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        self._conception(8.0)
        resultat = conception_pour_lead(self.lead, self.company)
        self.assertEqual(resultat['kwc'], 8.0)
        self.assertIsNone(resultat['calepinage'])

    def test_lead_sans_conception_ne_lit_plus_le_calepinage_mais_garde_le_lien(self):
        """Calepinage ouvert de 12 modules de 710 Wc (8,52 kWc) mais aucune
        conception rangée : kWc ``null`` (jamais le chiffre du calepinage),
        le LIEN du calepinage reste servi."""
        from apps.calepinage.models import Calepinage
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit',
            roof_layout={
                'modules': [{'id': 'm710', 'pmaxWc': 710}],
                'zones': [{'label': 'Sud',
                           'geometry': {'count': 12, 'moduleId': 'm710'}}]})
        resultat = conception_pour_lead(self.lead, self.company)
        self.assertIsNone(resultat['kwc'])
        self.assertEqual(
            resultat['calepinage'],
            {'id': calepinage.pk, 'statut': calepinage.statut,
             'reference': reference_calepinage(calepinage)})
        self.assertIsNone(resultat['devis'])

    def test_calepinage_servi_aussi_quand_un_devis_existe(self):
        """R2-10 — avec un devis, le lien vers le calepinage ne disparaît
        plus ; le statut du devis est servi (clé additive ``devis``)."""
        from apps.calepinage.models import Calepinage
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='',
            roof_layout={'zones': []})
        devis = self._devis()
        self._conception(7.7)
        resultat = conception_pour_lead(self.lead, self.company)
        self.assertEqual(resultat['calepinage']['id'], calepinage.pk)
        self.assertEqual(resultat['calepinage']['reference'],
                         reference_calepinage(calepinage))
        self.assertEqual(resultat['kwc'], 7.7)
        self.assertEqual(resultat['devis'], {
            'id': devis.pk, 'reference': devis.reference,
            'statut': devis.statut})

    def test_calepinage_d_une_autre_societe_jamais_servi(self):
        from apps.calepinage.models import Calepinage
        Calepinage.objects.create(
            company=self.other, lead_id=self.lead.pk, titre='X',
            roof_layout={'zones': []})
        self._devis()
        self.assertIsNone(
            conception_pour_lead(self.lead, self.company)['calepinage'])

    def test_selecteur_crm_passe_plat(self):
        self._devis()
        self._conception(7.7)
        self.assertEqual(conception_3d_du_lead(self.lead),
                         conception_pour_lead(self.lead, self.company))
        self.assertEqual(conception_3d_du_lead(None),
                         {'kwc': None, 'image_url': None, 'calepinage': None,
                          'devis': None})


class ConceptionSurLaFicheLeadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv78b-acme")
        self.user = User.objects.create_user(
            username="pv78b_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom="Lead PV78b", telephone="0600000079")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV78b",
            email="pv78b@example.com")
        Devis.objects.create(
            company=self.company, reference="DV-PV78B-1", lead=self.lead,
            client=self.crm_client, roof_layout=LAYOUT)

    def test_fiche_expose_la_conception(self):
        from apps.ventes.models import ConceptionLead
        ConceptionLead.ranger(
            lead=self.lead, etat='complet', marche='residentiel', option_retenue='sans',
            valeurs={'sans': {'puissance_kwc': {'valeur': 7.7, 'unite': 'kWc', 'source': 'moteur'}}},
            empreinte='a' * 64, niveau_regles=14, version_moteur='t')
        resp = self.api.get('/api/django/crm/leads/%s/' % self.lead.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('conception', resp.data)
        self.assertEqual(set(resp.data['conception']), {'kwc', 'image_url', 'calepinage', 'devis'})
        self.assertEqual(resp.data['conception']['kwc'], 7.7)

    def test_liste_ne_porte_pas_la_conception(self):
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertNotIn('conception', ligne)
