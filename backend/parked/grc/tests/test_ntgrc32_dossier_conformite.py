"""NTGRC32 — dossier de conformité pour un auditeur externe.

Garantie centrale : le ZIP contient les SIX exports + un manifeste dont
l'empreinte SHA-256 est RECALCULABLE par l'auditeur. Contrôles de contenu :
aucun prix d'achat, aucune donnée personnelle brute non nécessaire, aucune
ligne d'une autre société. Horloge FIGÉE.
"""
import hashlib
import io
import json
import zipfile

from django.test import TestCase
from django.utils import timezone

from apps.grc.models import (
    ControleInterne, PolitiqueInterne, RisqueEntreprise, TestControle,
)
from apps.grc.services import (
    EXPORTS_DOSSIER, construire_dossier_conformite, empreinte_globale,
    creer_violation, journaliser_destruction, publier_politique,
)
from authentication.models import Company
from core.models import RegistreTraitement
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 14:00:00+00:00'


def _peupler(company, suffixe=''):
    RegistreTraitement.objects.create(
        company=company, code=f'PROSPECTS{suffixe}',
        finalite='Gestion des prospects', base_legale='Consentement',
        donnees_sensibles=False)
    RisqueEntreprise.objects.create(
        company=company, reference=f'RQ-TEST{suffixe}',
        titre='Fuite de données', probabilite=4, impact=5)
    controle = ControleInterne.objects.create(
        company=company, code=f'ACC-01{suffixe}',
        intitule='Revue des comptes')
    TestControle.objects.create(
        company=company, controle=controle, testeur='auditeur',
        resultat=TestControle.RESULTAT_EFFICACE,
        date_realisee=timezone.now().date())
    politique = PolitiqueInterne.objects.create(
        company=company, titre=f'Charte{suffixe}', contenu='Texte')
    publier_politique(politique)
    journaliser_destruction(
        company, type_objet='crm_lead', objet_ref='42',
        action='anonymise', motif='Demande d\'effacement',
        empreinte='a' * 64)
    creer_violation(
        company, date_detection=timezone.now(),
        nombre_personnes_estime=3)


class DossierConformiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC32 SA', slug='ntgrc32')

    def _zip(self):
        with frozen(INSTANT):
            _peupler(self.company)
            octets, manifeste = construire_dossier_conformite(self.company)
        return zipfile.ZipFile(io.BytesIO(octets)), manifeste, octets

    def test_le_zip_contient_les_six_exports_et_le_manifeste(self):
        archive, _, _ = self._zip()
        noms = set(archive.namelist())
        self.assertEqual(noms, set(EXPORTS_DOSSIER) | {'manifeste.json'})
        self.assertEqual(len(EXPORTS_DOSSIER), 6)

    def test_le_manifeste_est_verifiable_fichier_par_fichier(self):
        archive, manifeste, _ = self._zip()
        for entree in manifeste['fichiers']:
            contenu = archive.read(entree['nom'])
            self.assertEqual(
                hashlib.sha256(contenu).hexdigest(), entree['sha256'],
                entree['nom'])
            self.assertEqual(len(contenu), entree['taille_octets'])

    def test_l_empreinte_globale_est_recalculable(self):
        archive, manifeste, _ = self._zip()
        recalculees = [
            {'nom': nom,
             'sha256': hashlib.sha256(archive.read(nom)).hexdigest()}
            for nom in EXPORTS_DOSSIER
        ]
        self.assertEqual(
            empreinte_globale(recalculees), manifeste['empreinte_globale'])

    def test_le_manifeste_embarque_est_le_meme(self):
        archive, manifeste, _ = self._zip()
        embarque = json.loads(archive.read('manifeste.json'))
        self.assertEqual(embarque['empreinte_globale'],
                         manifeste['empreinte_globale'])
        self.assertEqual(embarque['genere_le'], '2026-09-12T14:00:00+00:00')
        self.assertEqual(embarque['algorithme'], 'sha256')

    def test_les_exports_portent_bien_les_donnees(self):
        archive, _, _ = self._zip()
        traitements = archive.read(
            'registre-traitements.csv').decode('utf-8')
        self.assertIn('PROSPECTS', traitements)
        risques = archive.read('registre-risques.csv').decode('utf-8')
        self.assertIn('Fuite de données', risques)
        journal = archive.read('journal-destruction.csv').decode('utf-8')
        self.assertIn('a' * 64, journal)
        politiques = archive.read('politiques-publiees.csv').decode('utf-8')
        self.assertIn('Charte', politiques)

    def test_aucun_prix_d_achat_dans_le_dossier(self):
        archive, _, _ = self._zip()
        for nom in archive.namelist():
            contenu = archive.read(nom).decode('utf-8', errors='ignore')
            self.assertNotIn('prix_achat', contenu, nom)
            self.assertNotIn("Prix d'achat", contenu, nom)

    def test_le_dossier_ne_contient_aucune_autre_societe(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc32-autre')
        with frozen(INSTANT):
            _peupler(autre, suffixe='-X')
            _peupler(self.company)
            octets, _ = construire_dossier_conformite(self.company)
        archive = zipfile.ZipFile(io.BytesIO(octets))
        for nom in EXPORTS_DOSSIER:
            contenu = archive.read(nom).decode('utf-8')
            self.assertNotIn('-X', contenu, nom)

    def test_une_societe_vierge_produit_un_dossier_valide(self):
        vierge = Company.objects.create(nom='Vierge', slug='ntgrc32-vierge')
        with frozen(INSTANT):
            octets, manifeste = construire_dossier_conformite(vierge)
        archive = zipfile.ZipFile(io.BytesIO(octets))
        self.assertEqual(len(manifeste['fichiers']), 6)
        for nom in EXPORTS_DOSSIER:
            self.assertGreater(len(archive.read(nom)), 0, nom)


class EndpointDossierTests(TenantAPITestCase):
    URL = '/api/django/grc/dossier-conformite/'

    def test_telechargement_du_zip(self):
        with frozen(INSTANT):
            _peupler(self.company)
            r = self.client_as(role='admin').get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/zip')
        self.assertIn('dossier-conformite-2026-09-12.zip',
                      r['Content-Disposition'])
        archive = zipfile.ZipFile(io.BytesIO(r.content))
        self.assertIn('manifeste.json', archive.namelist())
        manifeste = json.loads(archive.read('manifeste.json'))
        self.assertEqual(r['X-Empreinte-Globale'],
                         manifeste['empreinte_globale'])
