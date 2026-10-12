"""ODX20 — App Achats, étape 2 (vues/urls/flux stock).

Les ViewSets achats fournisseurs (BCF, réceptions, factures fournisseur,
paiements, retours, prix fournisseur) sont désormais servis SOUS DEUX préfixes :
les nouvelles routes ``/api/django/achats/…`` ET les routes historiques
``/api/django/stock/…`` conservées à l'identique (mêmes classes, scoping société
côté serveur, aucun client cassé). Les mouvements de stock à la réception/au
retour passent par ``apps.stock.services`` (jamais d'import direct des modèles
stock).

Run :
    python manage.py test apps.achats.tests.test_odx20_achats_split -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_fournisseur(company, nom='ODX20 Fournisseur'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data \
        else data
    return [x['id'] for x in rows]


class TestODX20ModelsShim(TestCase):
    def test_achats_models_are_the_stock_shim(self):
        # ODX19 a déplacé l'ÉTAT vers apps.achats ; stock garde un shim de
        # ré-export : la MÊME classe est visible des deux côtés.
        from apps.achats.models import (
            BonCommandeFournisseur, ReceptionFournisseur, FactureFournisseur)
        from apps.stock.models import (
            BonCommandeFournisseur as SB,
            ReceptionFournisseur as SR,
            FactureFournisseur as SF)
        self.assertIs(BonCommandeFournisseur, SB)
        self.assertIs(ReceptionFournisseur, SR)
        self.assertIs(FactureFournisseur, SF)
        # Tables physiques préservées (stock_*), app_label = achats.
        self.assertEqual(
            BonCommandeFournisseur._meta.db_table,
            'stock_boncommandefournisseur')
        self.assertEqual(
            BonCommandeFournisseur._meta.app_label, 'achats')


class TestODX20Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx20-co', 'ODX20 Co')
        self.user = make_user(self.company, 'odx20_resp')
        self.fournisseur = make_fournisseur(self.company)
        self.api = auth(self.user)

    def _bcf(self, reference):
        from apps.achats.models import BonCommandeFournisseur
        return BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur)

    def test_new_achats_route_lists_scoped(self):
        bcf = self._bcf('BCF-2026-0001')
        r = self.api.get('/api/django/achats/bons-commande-fournisseur/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(bcf.id, ids_of(r))

    def test_legacy_stock_route_serves_same_data(self):
        bcf = self._bcf('BCF-2026-0002')
        r = self.api.get('/api/django/stock/bons-commande-fournisseur/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(bcf.id, ids_of(r))

    def test_prix_fournisseurs_dual_prefix(self):
        r_new = self.api.get('/api/django/achats/prix-fournisseurs/')
        r_old = self.api.get('/api/django/stock/prix-fournisseurs/')
        self.assertEqual(r_new.status_code, 200, r_new.data)
        self.assertEqual(r_old.status_code, 200, r_old.data)

    def test_tenant_isolation_on_new_route(self):
        other = make_company('odx20-other', 'Autre Co')
        other_f = make_fournisseur(other, nom='Autre Fournisseur')
        from apps.achats.models import BonCommandeFournisseur
        BonCommandeFournisseur.objects.create(
            company=other, reference='BCF-X', fournisseur=other_f)
        r = self.api.get('/api/django/achats/bons-commande-fournisseur/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids_of(r), [])


class TestEnf11FuzzAchats(TestCase):
    """ENF11 (api-fuzz achats) — une déclaration OpenAPI exacte : entrées
    illisibles refusées en 400, champs nullables rendus (jamais omis), fichier
    xlsx illisible en 400 au lieu d'un 500."""

    def setUp(self):
        self.company = make_company('enf11-ach', 'ENF11 Achats')
        self.user = make_user(self.company, 'enf11_admin', role='admin')
        self.fournisseur = make_fournisseur(self.company)
        self.api = auth(self.user)

    def test_filtre_entier_illisible_refuse_en_400_sur_les_listes(self):
        base = '/api/django/achats/'
        for ressource, param in (
                ('bons-commande-fournisseur', 'fournisseur'),
                ('factures-fournisseur', 'fournisseur'),
                ('retours-fournisseur', 'fournisseur'),
                ('paiements-fournisseur', 'facture'),
                ('prix-fournisseurs', 'produit'),
                ('receptions-fournisseur', 'bon_commande')):
            r = self.api.get(f'{base}{ressource}/', {param: 'abc'})
            self.assertEqual(r.status_code, 400, (ressource, r.content))
            self.assertIn(param, r.json())
            ok = self.api.get(f'{base}{ressource}/', {param: '999999'})
            self.assertEqual(ok.status_code, 200, (ressource, ok.content))
            self.assertEqual(ids_of(ok), [])

    def test_facture_sans_resolveur_rend_resolu_par_username_nul(self):
        from apps.achats.models import (
            FactureFournisseur, LigneFactureFournisseur)
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ENF11-1',
            fournisseur=self.fournisseur)
        LigneFactureFournisseur.objects.create(
            facture=facture, designation='Transport', quantite=1,
            prix_unitaire_ht=10)
        r = self.api.get(
            f'/api/django/achats/factures-fournisseur/{facture.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertIn('resolu_par_username', data)
        self.assertIsNone(data['resolu_par_username'])
        self.assertIsNone(data['lignes'][0]['produit_nom'])

    def test_import_xlsx_archive_non_classeur_refusee_en_400(self):
        import io
        import zipfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, 'w') as archive:
            archive.writestr('lisez-moi.txt', 'pas un classeur')
        fichier = SimpleUploadedFile(
            'tarif.xlsx', tampon.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet')
        r = self.api.post(
            '/api/django/achats/prix-fournisseurs/import-xlsx/',
            {'fournisseur': self.fournisseur.id, 'file': fichier},
            format='multipart')
        self.assertEqual(r.status_code, 400, r.content)

    def test_bcf_envoye_modification_directe_est_un_conflit_409(self):
        from apps.achats.models import BonCommandeFournisseur
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ENF11-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        r = self.api.patch(
            f'/api/django/achats/bons-commande-fournisseur/{bcf.id}/',
            {'note': 'x'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)

    def test_rapports_fournisseur_illisible_refuse_en_400(self):
        base = '/api/django/achats/'
        for chemin in ('bons-commande-fournisseur/achats-hors-contrat/',
                       'factures-fournisseur/suggestions-bcf/'):
            r = self.api.get(base + chemin, {'fournisseur': 'abc'})
            self.assertEqual(r.status_code, 400, (chemin, r.content))
            self.assertIn('fournisseur', r.json())


class TestEnf11SchemaCreationsAchats(TestCase):
    """ENF11 (achats) — le schéma OpenAPI de REQUÊTE dit ce que les serializers
    exigent déjà : listes de lignes non vides, quantités et montants > 0,
    produit OU désignation, identifiants de fusion distincts. Sans cela
    l'api-fuzz générait des corps « conformes » refusés en 400."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from drf_spectacular.generators import SchemaGenerator
        from apps.achats import urls as achats_urls
        schema = SchemaGenerator(
            patterns=achats_urls.urlpatterns).get_schema(
                request=None, public=True)
        cls.composants = schema['components']['schemas']

    def _propriete(self, composant, champ):
        return self.composants[composant]['properties'][champ]

    def test_lignes_non_vides_declarees_minitems(self):
        for composant in ('BonCommandeFournisseurRequest',
                          'ReceptionFournisseurRequest',
                          'RetourFournisseurRequest'):
            with self.subTest(composant=composant):
                self.assertEqual(
                    self._propriete(composant, 'lignes').get('minItems'), 1)

    def test_quantites_de_ligne_strictement_positives(self):
        for composant in ('LigneBonCommandeFournisseurRequest',
                          'LigneReceptionFournisseurRequest',
                          'LigneRetourFournisseurRequest'):
            with self.subTest(composant=composant):
                self.assertEqual(
                    self._propriete(composant, 'quantite').get('minimum'), 1)

    def test_montant_de_paiement_chaine_decimale_positive(self):
        import re
        motif = re.compile(
            self._propriete('PaiementFournisseurRequest', 'montant')['pattern'])
        for refuse in ('', '-', '.', '0', '0.00', '-5', '5.'):
            self.assertIsNone(motif.match(refuse), refuse)
        for accepte in ('12.50', '0.05', '1200', '0.5'):
            self.assertIsNotNone(motif.match(accepte), accepte)

    def test_decimaux_de_ligne_sans_chaine_vide(self):
        import re
        motif = re.compile(self._propriete(
            'LigneBonCommandeFournisseurRequest',
            'prix_achat_unitaire')['pattern'])
        for refuse in ('', '-', '.'):
            self.assertIsNone(motif.match(refuse), refuse)
        self.assertIsNotNone(motif.match('800.00'))

    def test_ligne_de_bcf_produit_ou_designation_declare(self):
        regles = self.composants[
            'LigneBonCommandeFournisseurRequest']['anyOf']
        self.assertEqual(
            sorted(r['required'][0] for r in regles),
            ['designation', 'produit'])

    def test_fusion_identifiants_distincts_et_au_moins_deux(self):
        ids = self._propriete('BcfFusionnerCorpsRequest', 'bons_commande')
        self.assertEqual(ids.get('minItems'), 2)
        self.assertTrue(ids.get('uniqueItems'))
        self.assertEqual(ids['items'].get('minimum'), 1)
        self.assertEqual(ids['items'].get('maximum'), 2147483647)

    def test_tranches_d_echeancier_typees(self):
        tranche = self.composants['TrancheEcheancierRequest']
        self.assertEqual(tranche['required'], ['date_echeance'])
        self.assertEqual(
            self._propriete('FactureEcheancierCorpsRequest',
                            'tranches')['items']['$ref'],
            '#/components/schemas/TrancheEcheancierRequest')


class TestEnf11EtatsAchats(TestCase):
    """ENF11 (achats) — un refus qui dépend de l'ÉTAT des données répond 409
    (référence introuvable : 404), jamais le 400 d'un corps mal formé."""

    def setUp(self):
        from apps.stock.models import Produit
        self.company = make_company('enf11-etats', 'ENF11 Etats')
        self.user = make_user(self.company, 'enf11_etats', role='admin')
        self.fournisseur = make_fournisseur(self.company, 'ENF11 Etats F')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ENF11', prix_achat=800,
            prix_vente=1000)
        self.api = auth(self.user)

    def _bcf(self, fournisseur=None, statut=None, reference='BCF-ENF11-E1'):
        from apps.achats.models import BonCommandeFournisseur
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=fournisseur or self.fournisseur,
            statut=statut or BonCommandeFournisseur.Statut.BROUILLON)
        ligne = bcf.lignes.create(
            produit=self.produit, quantite=5, prix_achat_unitaire=800)
        return bcf, ligne

    def _facture(self, ttc=100, fournisseur=None, reference='FF-ENF11-E1'):
        from apps.achats.models import FactureFournisseur
        return FactureFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=fournisseur or self.fournisseur,
            montant_ht=ttc, montant_tva=0, montant_ttc=ttc)

    def test_bcf_fournisseur_bloque_est_un_conflit_409(self):
        from apps.stock.models import Fournisseur
        self.fournisseur.statut = Fournisseur.Statut.BLOQUE_COMMANDES
        self.fournisseur.save(update_fields=['statut'])
        r = self.api.post('/api/django/achats/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{'produit': self.produit.id, 'quantite': 1,
                        'prix_achat_unitaire': '800.00'}],
        }, format='json')
        self.assertEqual(r.status_code, 409, r.content)

    def test_fusion_ids_introuvables_404_et_etats_incompatibles_409(self):
        url = '/api/django/achats/bons-commande-fournisseur/fusionner/'
        bcf1, _ = self._bcf(reference='BCF-ENF11-F1')
        r = self.api.post(url, {'bons_commande': [bcf1.id, 2147483646]},
                          format='json')
        self.assertEqual(r.status_code, 404, r.content)
        autre = make_fournisseur(self.company, 'ENF11 Autre')
        bcf2, _ = self._bcf(fournisseur=autre, reference='BCF-ENF11-F2')
        r = self.api.post(url, {'bons_commande': [bcf1.id, bcf2.id]},
                          format='json')
        self.assertEqual(r.status_code, 409, r.content)
        r = self.api.post(url, {'bons_commande': [bcf1.id]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_reception_sur_bcf_brouillon_ou_ligne_etrangere_409(self):
        from apps.achats.models import BonCommandeFournisseur
        url = '/api/django/achats/receptions-fournisseur/'
        brouillon, ligne = self._bcf(reference='BCF-ENF11-R1')
        r = self.api.post(url, {
            'bon_commande': brouillon.id,
            'lignes': [{'ligne_commande': ligne.id, 'quantite': 1}],
        }, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        envoye, _ = self._bcf(
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            reference='BCF-ENF11-R2')
        r = self.api.post(url, {
            'bon_commande': envoye.id,
            'lignes': [{'ligne_commande': ligne.id, 'quantite': 1}],
        }, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('hors de ce bon de commande', r.json()['detail'])

    def test_ubl_desactive_409_et_ocr_sans_fournisseur_404(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        base = '/api/django/achats/factures-fournisseur/'
        r = self.api.post(
            base + 'depuis-ubl/',
            {'file': SimpleUploadedFile('f.xml', b'<Invoice/>')},
            format='multipart')
        self.assertEqual(r.status_code, 409, r.content)
        r = self.api.post(
            base + 'depuis-ocr/',
            {'fields': {'fournisseur': 'Zzz Introuvable'}}, format='json')
        self.assertEqual(r.status_code, 404, r.content)

    def test_paiement_au_dela_du_solde_ou_fournisseur_bloque_409(self):
        from apps.stock.models import Fournisseur
        facture = self._facture(ttc=100)
        for url, corps in (
                ('/api/django/achats/paiements-fournisseur/',
                 {'facture': facture.id, 'montant': '150'}),
                (f'/api/django/achats/factures-fournisseur/{facture.id}/'
                 'paiements/', {'montant': '150'})):
            r = self.api.post(url, corps, format='json')
            self.assertEqual(r.status_code, 409, (url, r.content))
        # Le montant lui-même reste une entrée : <= 0 est un 400.
        r = self.api.post('/api/django/achats/paiements-fournisseur/',
                          {'facture': facture.id, 'montant': '0'},
                          format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.fournisseur.statut = Fournisseur.Statut.BLOQUE_PAIEMENTS
        self.fournisseur.save(update_fields=['statut'])
        r = self.api.post(
            f'/api/django/achats/factures-fournisseur/{facture.id}/paiements/',
            {'montant': '10'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)

    def test_resoudre_exception_hors_exception_409(self):
        facture = self._facture()
        r = self.api.post(
            f'/api/django/achats/factures-fournisseur/{facture.id}'
            '/resoudre-exception/', {'commentaire': 'ok'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)

    def test_prix_fournisseur_en_double_409(self):
        corps = {'produit': self.produit.id, 'fournisseur': self.fournisseur.id,
                 'prix_achat': '10.00'}
        r = self.api.post('/api/django/achats/prix-fournisseurs/', corps,
                          format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.api.post('/api/django/achats/prix-fournisseurs/', corps,
                          format='json')
        self.assertEqual(r.status_code, 409, r.content)
        premier = self.api.get(
            '/api/django/achats/prix-fournisseurs/').json()
        rows = premier['results'] if isinstance(premier, dict) else premier
        # Modifier le prix existant n'est PAS un doublon.
        r = self.api.patch(
            f'/api/django/achats/prix-fournisseurs/{rows[0]["id"]}/',
            {'prix_achat': '12.00'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_echeancier_tranche_mal_formee_400_jamais_500(self):
        facture = self._facture(ttc=1000)
        url = (f'/api/django/achats/factures-fournisseur/{facture.id}'
               '/echeancier/')
        for corps in ({'tranches': ['x']},
                      {'tranches': [{'pourcentage': 100}]},
                      {'tranches': []}):
            r = self.api.post(url, corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.content))
        r = self.api.post(url, {'tranches': [
            {'pourcentage': 30, 'date_echeance': '2026-07-01'},
            {'pourcentage': 70, 'date_echeance': '2026-08-01'}]},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()), 2)
