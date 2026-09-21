"""NTGRC1 — les 4 apps métier alimentent le registre DSR de `core`.

Garanties vérifiées :
  * les fournisseurs `crm`, `ventes`, `stock` et `rh` sont ENREGISTRÉS ;
  * un ACCÈS agrège les exports des 4 apps en UN seul payload ;
  * un EFFACEMENT pseudonymise la personne dans CRM / ventes / stock, et le
    dossier reste cohérent (les agrégats comptables ne bougent pas) ;
  * tout reste borné à la société de la demande.
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Fournisseur
from apps.ventes.models import Devis
from authentication.models import Company
from core import dsr
from core.models import DataSubjectRequest

EMAIL = 'personne.ntgrc1@exemple.ma'


class RegistreDesFournisseursTests(TestCase):
    def test_les_quatre_apps_sont_enregistrees(self):
        noms = dsr.list_dsr_providers()
        for attendu in ('crm', 'ventes', 'stock', 'rh'):
            self.assertIn(attendu, noms, f'fournisseur DSR manquant : {attendu}')


class DsrBoutABoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC1 SA', slug='ntgrc1')
        cls.autre = Company.objects.create(nom='NTGRC1 Autre', slug='ntgrc1-b')

        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Dupont', prenom='Amine',
            email=EMAIL, telephone='0600000001')
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Dupont', prenom='Amine', email=EMAIL,
            telephone='0600000001')
        cls.devis = Devis.objects.create(
            company=cls.company, reference='DEV-NTGRC1-0001',
            client=cls.client_obj, accepte_par_nom='Amine Dupont')
        cls.fournisseur = Fournisseur.objects.create(
            company=cls.company, nom='SARL Bricolage',
            contact_personne='Amine Dupont', email=EMAIL,
            telephone='0600000001')
        # Même email, AUTRE société : ne doit jamais apparaître ni bouger.
        cls.fournisseur_autre = Fournisseur.objects.create(
            company=cls.autre, nom='Autre SARL',
            contact_personne='Amine Dupont', email=EMAIL)

    def test_acces_agrege_les_exports_des_quatre_apps(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier=EMAIL,
            kind=DataSubjectRequest.KIND_ACCESS)
        dsr.traiter_demande(demande)
        resultat = demande.resultat
        for app in ('crm', 'ventes', 'stock', 'rh'):
            self.assertIn(app, resultat, f'export manquant pour {app}')
        self.assertEqual(len(resultat['crm']['clients']), 1)
        self.assertEqual(len(resultat['ventes']['devis']), 1)
        self.assertEqual(len(resultat['stock']['fournisseurs']), 1)

    def test_effacement_pseudonymise_et_conserve_les_agregats(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier=EMAIL,
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(demande)

        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)
        self.assertIsNone(self.client_obj.email)

        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.email)

        self.fournisseur.refresh_from_db()
        self.assertIsNone(self.fournisseur.email)
        self.assertIsNone(self.fournisseur.telephone)
        # La PERSONNE MORALE survit (raison sociale, historique d'achat).
        self.assertEqual(self.fournisseur.nom, 'SARL Bricolage')

        # Agrégats comptables INCHANGÉS : la ligne devis existe toujours, sa
        # référence et son statut n'ont pas bougé ; seul le nom de l'accepteur
        # est pseudonymisé.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.reference, 'DEV-NTGRC1-0001')
        self.assertEqual(self.devis.accepte_par_nom, 'Anonymisé')
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 1)

        # RH refuse l'effacement (obligations sociales) — jamais en silence.
        self.assertTrue(demande.resultat['rh']['refuse'])

    def test_effacement_ne_franchit_jamais_la_frontiere_societe(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier=EMAIL,
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(demande)
        self.fournisseur_autre.refresh_from_db()
        self.assertEqual(self.fournisseur_autre.email, EMAIL)
        self.assertEqual(
            self.fournisseur_autre.contact_personne, 'Amine Dupont')


class EmpreinteTests(TestCase):
    def test_empreinte_est_stable_et_ne_contient_pas_la_valeur(self):
        from apps.grc.services import empreinte_avant

        empreinte = empreinte_avant({'email': EMAIL, 'nom': 'Dupont'})
        self.assertEqual(len(empreinte), 64)
        self.assertNotIn('dupont', empreinte.lower())
        self.assertEqual(
            empreinte, empreinte_avant({'nom': 'Dupont', 'email': EMAIL}))
        self.assertEqual(empreinte_avant({}), '')

    def test_journaliser_sans_societe_est_un_no_op(self):
        from apps.grc.services import journaliser_destruction

        self.assertIsNone(journaliser_destruction(
            None, type_objet='crm_lead', objet_ref=1, action='anonymise'))


class MontantsIntactsTests(TestCase):
    """Le chemin d'effacement ne touche JAMAIS un montant."""

    def test_aucun_montant_du_devis_ne_bouge(self):
        company = Company.objects.create(nom='NTGRC1 M', slug='ntgrc1-m')
        cl = Client.objects.create(
            company=company, nom='X', email='m.ntgrc1@exemple.ma')
        devis = Devis.objects.create(
            company=company, reference='DEV-NTGRC1-0009', client=cl,
            remise_globale=Decimal('10.00'), accepte_par_nom='X Y')
        demande = DataSubjectRequest.objects.create(
            company=company, subject_identifier='m.ntgrc1@exemple.ma',
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(demande)
        devis.refresh_from_db()
        self.assertEqual(devis.remise_globale, Decimal('10.00'))
