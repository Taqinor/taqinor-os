"""Tests des Avoirs (notes de crédit) — workstream D.

Couvre : création depuis une facture émise (admin), avoir partiel qui réduit
le montant dû avec le split TVA 10/20 intact, garde admin sur la création.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture

User = get_user_model()


def make_company(slug='avo-co', nom='Avo Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestAvoirs(TestCase):
    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            ALL_PERMISSIONS,
            RESPONSABLE_PERMISSIONS,
        )
        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='avo_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.resp = User.objects.create_user(
            username='avo_resp', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Avo',
            telephone='+212600000001')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PV1',
            prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND1',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        # Facture émise : 10×1000 (TVA10) + 1×5000 (TVA20) = 15000 HT,
        # TVA = 1000 + 1000 = 2000 → 17000 TTC.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-TEST-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_facture_baseline_due(self):
        self.assertEqual(self.facture.total_ttc, Decimal('17000.00'))
        self.assertEqual(self.facture.montant_du, Decimal('17000.00'))

    def test_partial_avoir_lowers_due_with_tva_split(self):
        # Avoir partiel : on crédite uniquement l'onduleur (5000 HT, TVA 20 %
        # = 1000 → 6000 TTC).
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Onduleur retourné',
             'lignes': [{'produit': self.onduleur.id, 'designation': 'Onduleur',
                         'quantite': '1', 'prix_unitaire': '5000',
                         'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(id=resp.data['id'])
        self.assertEqual(avoir.total_ht, Decimal('5000.00'))
        self.assertEqual(avoir.total_tva, Decimal('1000.00'))
        self.assertEqual(avoir.total_ttc, Decimal('6000.00'))
        # Le split TVA est présent (un seul taux ici, 20 %).
        bucket = avoir.tva_par_taux
        self.assertEqual(len(bucket), 1)
        self.assertEqual(bucket[0]['taux'], Decimal('20.00'))
        # Le dû de la facture baisse de 6000 → 11000.
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.avoirs_total, Decimal('6000.00'))
        self.assertEqual(self.facture.montant_du, Decimal('11000.00'))
        # Référence en séquence AVO.
        self.assertTrue(avoir.reference.startswith('AVO-'))

    def test_full_avoir_copies_lines_and_zeroes_due(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Annulation totale'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(id=resp.data['id'])
        self.assertEqual(avoir.total_ttc, Decimal('17000.00'))
        # Split 10/20 préservé sur l'avoir complet.
        taux = sorted(b['taux'] for b in avoir.tva_par_taux)
        self.assertEqual(taux, [Decimal('10.00'), Decimal('20.00')])
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('0.00'))

    def test_avoir_and_payment_are_logged_in_facture_chatter(self):
        api = self._api(self.admin)
        # Encaisser un paiement → consigne une activité « Paiement ».
        api.post(
            f'/api/django/ventes/factures/{self.facture.id}/enregistrer-paiement/',
            {'montant': '100', 'date_paiement': '2026-06-19', 'mode': 'virement'},
            format='json')
        # Créer un avoir → consigne une activité « Avoir » (acteur côté serveur).
        api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Test chatter',
             'lignes': [{'produit': self.onduleur.id, 'designation': 'Onduleur',
                         'quantite': '1', 'prix_unitaire': '5000',
                         'taux_tva': '20.00'}]},
            format='json')
        resp = api.get(
            f'/api/django/ventes/factures/{self.facture.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        fields = {a['field'] for a in resp.data}
        self.assertIn('avoir', fields)
        self.assertIn('paiement', fields)
        # L'acteur est posé côté serveur (jamais lu du corps).
        self.assertTrue(all(a['user_nom'] == 'avo_admin' for a in resp.data))

    def test_commerciale_cannot_create_avoir(self):
        api = self._api(self.resp)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
        # Mais peut le lister/voir.
        self.assertEqual(
            api.get('/api/django/ventes/avoirs/').status_code, 200)

    def test_cannot_avoir_draft_facture(self):
        self.facture.statut = Facture.Statut.BROUILLON
        self.facture.save(update_fields=['statut'])
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'x'}, format='json')
        self.assertEqual(resp.status_code, 409)

    def test_avoir_exceeding_remaining_rejected(self):
        # Une ligne d'avoir à 20 000 HT (24 000 TTC) dépasse les 17 000 TTC
        # créditables de la facture → 409 (refus d'état, CI #997), aucun
        # avoir persisté. AARG38 — sur une facture à lignes le P.U. est borné
        # d'abord : ce plafond se lit sur un acompte (ligne libre).
        acompte = Facture.objects.create(
            company=self.company, reference='FAC-TEST-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ht=Decimal('14166.67'),
            montant_tva=Decimal('2833.33'), montant_ttc=Decimal('17000.00'))
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{acompte.id}/creer-avoir/',
            {'motif': 'Trop gros',
             'lignes': [{'produit': None, 'designation': 'X',
                         'quantite': '1', 'prix_unitaire': '20000',
                         'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('dépasse', resp.data['detail'])
        self.assertEqual(Avoir.objects.count(), 0)

    def test_second_avoir_capped_by_first(self):
        # 1er avoir total (17 000 TTC) → plus rien de créditable ; un 2e avoir
        # partiel est refusé.
        api = self._api(self.admin)
        r1 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Total'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'lignes': [{'produit': self.onduleur.id, 'designation': 'Onduleur',
                         'quantite': '1', 'prix_unitaire': '5000',
                         'taux_tva': '20'}]},
            format='json')
        # CI #997 (3) : plafond d'avoir dépassé = conflit d'état (409), corps conforme.
        self.assertEqual(r2.status_code, 409, r2.data)
        self.assertEqual(Avoir.objects.count(), 1)

    def test_ecart_de_vente_reparti_sous_le_creditable(self):
        """ATOT43 — écart 3 000 TTC sur 5 × 2 400 : 2 400 + 600, Σ dû 9 000 ;
        un écart au-delà du créditable n'écrit rien."""
        import datetime

        from apps.ventes.domain.facturation_ops import AvoirPlafondDepasse
        from apps.ventes.domain.facturation_vente import (
            crediter_ecart_de_vente)
        from testkit.factories import DevisFactory
        devis = DevisFactory(company=self.company, client=self.client_obj,
                             statut='accepte')
        tranches = [Facture.objects.create(
            company=self.company, reference=f'FAC-ATOT43-{i}', devis=devis,
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ht=Decimal('2000.00'),
            montant_tva=Decimal('400.00'), montant_ttc=Decimal('2400.00'),
            date_emission=datetime.date(2026, 10, 1 + i)) for i in range(5)]
        paniers = [{'taux': '20', 'base_ht': '2500', 'montant': '500'}]
        with self.assertRaises(AvoirPlafondDepasse):
            crediter_ecart_de_vente(devis, Decimal('12000.01'), paniers,
                                    user=self.admin, motif='Trop')
        self.assertEqual(Avoir.objects.count(), 0)
        avoirs = crediter_ecart_de_vente(
            devis, Decimal('3000'), paniers, user=self.admin,
            motif='Prix négocié')
        self.assertEqual(len(avoirs), 2)
        self.assertEqual([a.facture_id for a in avoirs],
                         [tranches[4].id, tranches[3].id])
        for avoir, ttc, ht, tva in zip(
                avoirs, ('2400.00', '600.00'), ('2000.00', '500.00'),
                ('400.00', '100.00')):
            avoir.refresh_from_db()
            self.assertEqual(avoir.type, Avoir.Type.CORRECTION)
            self.assertEqual(avoir.total_ttc, Decimal(ttc))
            self.assertEqual(avoir.total_ht, Decimal(ht))
            self.assertEqual(avoir.ventilation_tva, [
                {'taux': '20', 'base_ht': ht, 'montant': tva}])
        for f in tranches:
            f.refresh_from_db()
        self.assertEqual(tranches[4].montant_du, Decimal('0'))
        self.assertEqual(tranches[3].montant_du, Decimal('1800.00'))
        self.assertEqual(sum(f.montant_du for f in tranches),
                         Decimal('9000.00'))

    def test_corps_hors_schema_400_jamais_500(self):
        # CI M1 tour 3 (api-fuzz run 38295727060) — corps EXACT du fuzzeur :
        # ``designation`` liste → ``.strip()`` levait AttributeError (500).
        api = self._api(self.admin)
        url = f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/'
        corps = {'mode': 'correction', 'motif': '', 'type': 'correction',
                 'lignes': [{'produit': 0, 'designation': [None, None],
                             'quantite': '0', 'prix_unitaire': '0',
                             'remise': '0', 'taux_tva': '0'}]}
        resp = api.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Ligne 1', resp.data['detail'])
        self.assertEqual(resp.data['code'], 'ligne_invalide')
        for corps in ([1, 2], {'lignes': 'abc'}, {'mode': 'bogus'},
                      {'lignes': [{'produit': self.onduleur.id,
                                   'designation': 'X', 'quantite': '',
                                   'prix_unitaire': '1'}]}):
            with self.subTest(corps=corps):
                resp = api.post(url, corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(Avoir.objects.count(), 0)

    def test_motif_et_ligne_strictement_types(self):
        # CI #997 (2) (cas 6kYQk5) — ``motif: 0`` créait l'avoir (201, motif
        # « 0 ») ; ``produit: "5"`` / ``designation: 5`` étaient convertis.
        api = self._api(self.admin)
        url = f'/api/django/facturation/factures/{self.facture.id}/creer-avoir/'
        ligne = {'produit': self.onduleur.id, 'designation': 'X',
                 'quantite': '1', 'prix_unitaire': '1'}
        for corps in ({'motif': 0}, {'motif': None},
                      {'lignes': [dict(ligne, produit=str(self.onduleur.id))]},
                      {'lignes': [dict(ligne, designation=5)]}):
            resp = api.post(url, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.data))
        self.assertEqual(Avoir.objects.count(), 0)

    def test_lignes_correction_bornees_aux_lignes_facturees(self):
        # AARG38 — ni un taux, ni une quantité, ni un P.U. jamais facturés.
        facture = Facture.objects.create(
            company=self.company, reference='FAC-TEST-0003',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.onduleur, designation='Panneau',
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        api = self._api(self.admin)
        url = f'/api/django/ventes/factures/{facture.id}/creer-avoir/'
        ligne = {'produit': self.onduleur.id, 'designation': 'Panneau',
                 'quantite': '1', 'prix_unitaire': '1000', 'taux_tva': '20'}

        def poster(**champs):
            return api.post(url, {'lignes': [dict(ligne, **champs)]},
                            format='json')
        for champs, motif in (
                ({'quantite': '3'}, 'Ligne 1 : quantité créditée supérieure à '
                 'la quantité facturée restante (2).'),
                ({'taux_tva': '10'}, 'Ligne 1 : taux de TVA absent de la facture.'),
                ({'prix_unitaire': '1200'}, 'Ligne 1 : prix unitaire supérieur '
                 'au prix facturé (1000.00).'),
                ({'produit': self.panneau.id}, 'Ligne 1 : quantité créditée '
                 'supérieure à la quantité facturée restante (0).')):
            with self.subTest(champs=champs):
                r = poster(**champs)
                self.assertEqual(r.status_code, 400, r.data)
                self.assertEqual(r.data['detail'], motif)
        self.assertEqual(Avoir.objects.filter(facture=facture).count(), 0)
        # Deux lignes du même produit se cumulent dans le même corps.
        r = api.post(url, {'lignes': [dict(ligne, quantite='2'),
                                      dict(ligne, quantite='1')]}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Ligne 2', r.data['detail'])
        # Une quantité créditée par un avoir actif ne se crédite plus ; rendue
        # par son annulation, elle redevient créditable.
        premier = poster(quantite='2')
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(
            api.post(f"/api/django/ventes/avoirs/{premier.data['id']}/annuler/"
                     ).status_code, 200)
        self.assertEqual(poster().status_code, 201)
        r = poster(quantite='2')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('(1)', r.data['detail'])
        # Facture sans ligne produit : ligne libre au plafond, au taux porté.
        acompte = Facture.objects.create(
            company=self.company, reference='FAC-TEST-0004',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'))
        libre = {'produit': None, 'designation': 'Acompte', 'quantite': '1',
                 'prix_unitaire': '1000', 'taux_tva': '20'}
        url_acompte = f'/api/django/ventes/factures/{acompte.id}/creer-avoir/'
        r = api.post(url_acompte, {'lignes': [dict(libre, taux_tva='10')]},
                     format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = api.post(url_acompte, {'lignes': [libre]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_ligne_sans_taux_controlee_au_taux_d_entete(self):
        # AARG38 — lignes à 10 %, en-tête à 20 % : une ligne sans taux créditerait
        # à 20 %, un taux que la facture n'a jamais porté ; le taux 10 passe.
        facture = Facture.objects.create(
            company=self.company, reference='FAC-TEST-0005',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.panneau, designation='Panneau',
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10.00'))
        api = self._api(self.admin)
        url = f'/api/django/ventes/factures/{facture.id}/creer-avoir/'
        ligne = {'produit': self.panneau.id, 'designation': 'Panneau',
                 'quantite': '1', 'prix_unitaire': '1000'}
        r = api.post(url, {'lignes': [ligne]}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['detail'],
                         'Ligne 1 : taux de TVA absent de la facture.')
        self.assertEqual(Avoir.objects.filter(facture=facture).count(), 0)
        r = api.post(url, {'lignes': [dict(ligne, taux_tva='10')]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        # En-tête égal au taux des lignes : l'omission reste permise.
        Facture.objects.filter(pk=facture.pk).update(taux_tva=Decimal('10.00'))
        r = api.post(url, {'lignes': [ligne]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_annuler_regenere_le_pdf_annule(self):
        # AARG37 — le PDF servi après annulation imprime « Annulé », et une
        # annulation rejouée ne refait ni rendu ni événement.
        from unittest import mock

        from core.events import avoir_annule
        api = self._api(self.admin)
        r = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Total'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir = Avoir.objects.get(pk=r.data['id'])
        evenements = []

        def recepteur(**kw):
            evenements.append(kw['instance'].pk)
        avoir_annule.connect(recepteur)
        self.addCleanup(avoir_annule.disconnect, recepteur)
        with mock.patch('apps.ventes.utils.pdf._html_to_pdf',
                        return_value=b'%PDF') as rendu, \
                mock.patch('apps.ventes.utils.pdf._upload_pdf') as televerse:
            url = f'/api/django/ventes/avoirs/{avoir.id}/annuler/'
            self.assertEqual(api.post(url).status_code, 200)
            self.assertEqual(rendu.call_count, 1)
            self.assertIn('Annul', rendu.call_args[0][0])
            self.assertEqual(api.post(url).status_code, 200)
        self.assertEqual(rendu.call_count, 1)
        self.assertEqual(televerse.call_count, 1)
        self.assertEqual(evenements, [avoir.pk])
        avoir.refresh_from_db()
        self.assertEqual(avoir.statut, Avoir.Statut.ANNULEE)
        self.assertTrue(avoir.fichier_pdf)

    # ── AUD126 — la garde de plafond est SÉRIALISÉE ──
    def test_creer_avoir_verrouille_la_facture_avant_de_lire_le_plafond(self):
        """AUD126 — `creer_avoir` n'avait ni `transaction.atomic` ni
        `select_for_update` : deux requêtes concurrentes lisaient chacune
        l'ancien `reste_creditable` et passaient toutes deux la garde,
        créditant le client de deux fois le plafond. C'est le motif déjà
        corrigé sous ERR72 sur `enregistrer-paiement`.

        Preuve DÉTERMINISTE (pas de course à reproduire) : la requête émet
        bien un `SELECT ... FOR UPDATE` sur `ventes_facture`. ROUGE avant le
        correctif, où aucune requête de la vue ne portait `FOR UPDATE`.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api = self._api(self.admin)
        with CaptureQueriesContext(connection) as capture:
            r = api.post(
                f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
                {'motif': 'Total'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        verrous = [
            q['sql'] for q in capture.captured_queries
            if 'for update' in q['sql'].lower()
            and 'ventes_facture' in q['sql'].lower()
        ]
        self.assertTrue(
            verrous,
            'aucun SELECT ... FOR UPDATE sur la facture : la lecture du '
            'plafond et la création ne sont pas sérialisées')


class TestAvoirConcurrenceAUD126(TransactionTestCase):
    """AUD126 — le scénario joué POUR DE VRAI, sur deux connexions.

    ``TransactionTestCase`` (et non ``TestCase``) est indispensable : les
    données doivent être COMMITÉES pour que les threads, qui ouvrent leur
    propre connexion, les voient. Deux requêtes demandent chacune la
    TOTALITÉ du reste créditable ; une seule doit réussir et
    ``Facture.avoirs_total`` ne doit jamais dépasser le TTC.
    """

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ALL_PERMISSIONS
        self.company = make_company(slug='avo-conc-co', nom='Avo Conc Co')
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='avo_conc_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Conc',
            telephone='+212600000126')
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-AUD126',
            prix_vente=Decimal('5000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD126-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.onduleur,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))

    def test_deux_avoirs_concurrents_ne_depassent_jamais_le_plafond(self):
        import threading

        url = f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/'
        resultats = []
        verrou_resultats = threading.Lock()
        # La barrière garantit que les DEUX requêtes sont dans la vue en même
        # temps : sans le verrou de ligne, elles lisent toutes deux l'ancien
        # reste créditable et créent chacune un avoir plein.
        barriere = threading.Barrier(2, timeout=30)

        def _creer():
            from django.db import connection as thread_connection
            try:
                api = APIClient()
                api.credentials(
                    HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
                barriere.wait()
                reponse = api.post(url, {'motif': 'Total'}, format='json')
                with verrou_resultats:
                    resultats.append(reponse.status_code)
            except threading.BrokenBarrierError:
                pass
            finally:
                thread_connection.close()

        threads = [threading.Thread(target=_creer) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)

        self.assertEqual(sorted(resultats), [201, 409], resultats)
        self.facture.refresh_from_db()
        self.assertEqual(Avoir.objects.filter(facture=self.facture).count(), 1)
        self.assertLessEqual(
            self.facture.avoirs_total, self.facture.total_ttc)
