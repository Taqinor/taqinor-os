"""QJR516 (Groupe QJR5) — UN seul prédicat de modifiabilité par geste
(``domain/modifiabilite``), servi au front, et le verrou d'un devis accepté
posé sur TOUS ses chemins d'écriture.

* la table : 5 statuts × is_active, verdict comparé à l'exemple COMMITTÉ
  ``contract_samples/devis_modifiabilite.json`` (PACT10) ;
* le détail ET la liste du devis servent ``modifiable`` /
  ``raison_non_modifiable`` / ``revision_possible`` ;
* les HUIT écritures jadis sans garde (layout POST, roof-image, overrides
  PATCH/DELETE, etude-params PATCH, offres-tailles config/regenerer, lots
  POST) : accepté / refusé / expiré / remplacé → 409 {detail, statut,
  revision_possible} et RIEN n'a bougé (roof-image : l'upload MinIO n'est
  jamais appelé) ; brouillon / envoyé actifs → jamais 409 ;
* une ligne ne change pas de devis (PATCH {devis} → 400) ;
* plus aucune copie ``_MODIFIABLES`` / ``FROZEN =`` dans ``views/``.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_modifiabilite_gestes"
"""
import json
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import modifiabilite as mod
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
RACINE = Path(__file__).resolve().parent.parent
CONTRAT = RACINE / 'contract_samples' / 'devis_modifiabilite.json'
CLES = ('modifiable', 'raison_non_modifiable', 'revision_possible')
STATUTS = ('brouillon', 'envoye', 'accepte', 'refuse', 'expire')
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR516 Co', slug='qjr516-co')
        self.user = User.objects.create_user(
            username='qjr516_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR516',
            email='qjr516@example.test', telephone='+212600005160')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR516-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut='brouillon', is_active=True, reference=None):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company,
            reference=reference or f'DEV-{MONTH}-516{self.n:02d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        if not is_active:
            Devis.objects.filter(pk=devis.pk).update(is_active=False)
            devis.refresh_from_db()
        return devis


class TableContreContrat(_Base):
    """Le verdict du prédicat = l'exemple committé, cas par cas."""

    def setUp(self):
        super().setUp()
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_chaque_exemple_du_contrat(self):
        successeur = self._devis('brouillon', reference='DEV-202609-0012')
        for variante in ('exemple_brouillon', 'exemple_envoye',
                         'exemple_accepte', 'exemple_refuse',
                         'exemple_expire', 'exemple_remplace'):
            ex = self.contrat[variante]
            with self.subTest(variante=variante):
                devis = self._devis(ex['statut'], is_active=ex['is_active'])
                if variante == 'exemple_remplace':
                    Devis.objects.filter(pk=devis.pk).update(
                        superseded_by=successeur)
                    devis.refresh_from_db()
                attendu = {k: ex[k] for k in CLES}
                self.assertEqual(mod.verdict(devis), attendu)
                r = self.api.get(f'/api/django/ventes/devis/{devis.id}/')
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual({k: r.data[k] for k in CLES}, attendu)

    def test_la_liste_sert_aussi_les_trois_cles(self):
        self._devis('accepte')
        r = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(r.status_code, 200, r.content)
        lignes = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertTrue(lignes)
        for ligne in lignes:
            for cle in CLES:
                self.assertIn(cle, ligne)

    def test_gestes_calepinage_et_taille_brouillon_seul(self):
        envoye = self._devis('envoye')
        for geste in (mod.CALEPINAGE, mod.TAILLE):
            with self.subTest(geste=geste):
                self.assertFalse(mod.verdict(envoye, geste)['modifiable'])
                self.assertTrue(
                    mod.verdict(self._devis('brouillon'), geste)['modifiable'])
        for geste in (mod.LIGNES, mod.ENTETE, mod.BOQ, mod.OPTIONS, mod.ETUDE):
            with self.subTest(geste=geste):
                self.assertTrue(mod.verdict(envoye, geste)['modifiable'])

    def test_geste_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            mod.verdict(self._devis(), 'N_IMPORTE_QUOI')


class LesHuitEcrituresGardees(_Base):
    """Accepté / refusé / expiré / remplacé → 409, rien n'a bougé ;
    brouillon / envoyé actifs → jamais 409."""

    def _ecritures(self, devis):
        base = f'/api/django/ventes/devis/{devis.id}'
        return {
            'layout': lambda: self.api.post(
                f'{base}/layout/', {'areas': [], 'result': {'panels': 4}},
                format='json'),
            'roof-image': lambda: self.api.post(
                f'{base}/roof-image/',
                {'image': SimpleUploadedFile('toit.png', PNG,
                                             content_type='image/png')},
                format='multipart'),
            'overrides PATCH': lambda: self.api.patch(
                f'{base}/overrides/',
                {'scenario': {'valeur': 'Sans batterie'}}, format='json'),
            'overrides DELETE': lambda: self.api.delete(
                f'{base}/overrides/?chemin=scenario'),
            'etude-params': lambda: self.api.patch(
                f'{base}/etude-params/', {'nb_proprietes': 2},
                format='json'),
            'offres-tailles config': lambda: self.api.patch(
                f'{base}/offres-tailles/config/',
                {'cle': 'eco', 'config': {'nb_panneaux': 8}},
                format='json'),
            'offres-tailles regenerer': lambda: self.api.post(
                f'{base}/offres-tailles/regenerer/', {'cle': 'eco'},
                format='json'),
            'lots': lambda: self.api.post(
                f'{base}/lots/', {'nom_lot': 'Villa A'}, format='json'),
        }

    @staticmethod
    def _etat(devis):
        devis.refresh_from_db()
        return (devis.statut, devis.roof_layout, devis.roof_image,
                devis.overrides, devis.etude_params,
                devis.offres_tailles_config, devis.lots.count(),
                devis.is_active)

    def test_statuts_x_is_active(self):
        for statut in STATUTS:
            for actif in (True, False):
                devis = self._devis(statut, is_active=actif)
                doit_refuser = not (actif and statut in ('brouillon',
                                                         'envoye'))
                for nom, appel in self._ecritures(devis).items():
                    with self.subTest(statut=statut, actif=actif, ecriture=nom):
                        avant = self._etat(devis)
                        with patch('apps.ventes.utils.pdf.upload_roof_image') \
                                as upload, \
                                patch('apps.ventes.quote_engine.builder.'
                                      '_ensure_pdf_bucket'), \
                                patch('apps.ventes.utils.pdf.'
                                      'roof_image_signed_url',
                                      return_value='https://x/y.png'):
                            r = appel()
                        if doit_refuser:
                            self.assertEqual(r.status_code, 409, r.content)
                            self.assertEqual(
                                set(r.data),
                                {'detail', 'statut', 'revision_possible'})
                            self.assertEqual(r.data['statut'], statut)
                            self.assertEqual(r.data['revision_possible'],
                                             actif and statut != 'brouillon')
                            self.assertEqual(self._etat(devis), avant)
                            upload.assert_not_called()
                        else:
                            self.assertNotEqual(r.status_code, 409,
                                                r.content)


class UneLigneNeChangePasDeDevis(_Base):

    def test_patch_devis_d_une_ligne_refuse(self):
        a = self._devis('brouillon')
        b = self._devis('brouillon')
        ligne = a.lignes.get()
        r = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                           {'devis': b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('devis', r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.devis_id, a.id)

    def test_ligne_d_un_devis_remplace_refusee(self):
        devis = self._devis('envoye', is_active=False)
        ligne = devis.lignes.get()
        r = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                           {'quantite': '2'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('devis', r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, Decimal('10'))


class PlusAucuneCopieDeLaRegle(SimpleTestCase):

    def test_views_ne_recopient_plus_la_regle(self):
        for chemin in sorted((RACINE / 'views').glob('*.py')):
            source = chemin.read_text(encoding='utf-8')
            with self.subTest(fichier=chemin.name):
                self.assertNotIn('_MODIFIABLES', source)
                self.assertIsNone(re.search(r'\bFROZEN\s*=', source))
