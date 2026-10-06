"""ADOC81 — Garde de classe des liens et des preuves de signature GED.

1. Tout chemin qui ENVOIE un lien de signature (création mono, multi, lot,
   règle de dossier, opération par lot, relance) produit un lien ABSOLU sur
   la base publique de l'ERP, qui répond 200.
2. Tout chemin qui SIGNE (public mono, public multi) persiste ses preuves :
   IP (dernier saut de confiance), consentement, forme de signature, hash ;
   le marquage manuel `marquer-signe` (attestation émetteur, sans cérémonie)
   persiste au moins le PDF signé figé et son hash.
3. Inventaire (AST de apps/ged/services.py et views.py) : un NOUVEAU chemin
   d'envoi ou de signature non couvert ici fait échouer la garde, nommément.

Sources réelles : services et vues GED, `send_mail` locmem, routes publiques
réelles, stockage MinIO de test réel ; aucun mock.
"""
import ast
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, ModeleDocument

User = get_user_model()

BASE = 'https://erp.exemple.ma'
RE_LIEN = re.compile(r'Lien : (\S+)')
NGINX = '172.18.0.5'
CLIENT = '41.77.1.5'
GED_DIR = Path(services.__file__).resolve().parent

# Fonctions de apps/ged qui DÉCLENCHENT l'envoi d'un lien de signature
# (appellent demander_signature / _send_signataire_email) → test qui les
# couvre ci-dessous. Toute nouvelle entrée doit être ajoutée ET testée.
CHEMINS_ENVOI = {
    ('views.py', 'create'): 'test_creation_mono',
    ('views.py', 'creer_multi'): 'test_creation_multi',
    ('services.py', 'creer_demande_multi_signataires'): 'test_creation_multi',
    ('services.py', 'notifier_prochains_signataires'): 'test_creation_multi',
    ('services.py', 'creer_lot_envoi_signature'): 'test_lot_envoi',
    ('services.py', '_executer_action_regle'): 'test_regle_dossier',
    ('services.py', 'operation_lot'): 'test_operation_lot',
    ('services.py', 'relancer_signataires_dus'): 'test_relance',
}
# Seules fonctions de apps/ged autorisées à appeler send_mail : l'unique
# expéditeur de liens de cérémonie, et deux envois SANS lien de signature.
EXPEDITEURS_SEND_MAIL = {
    '_envoyer_lien_signature',      # tous les liens de cérémonie
    'envoyer_code_otp_signataire',  # code OTP (aucun lien)
    '_notifier_alteration_archives',  # alerte d'intégrité (aucun lien)
}
# Fonctions qui SIGNENT (appellent marquer_signe / la routine de preuve).
CHEMINS_SIGNATURE = {
    ('services.py', 'signer_demande_publique'): 'test_signature_publique_mono',
    ('services.py', 'signer_signataire'): 'test_signature_publique_multi',
    ('services.py', '_maj_statut_global'): 'test_signature_publique_multi',
    ('views.py', 'marquer_signe'): 'test_marquer_signe_manuel',
}


def _appelants(noms_appeles):
    """{(fichier, fonction)} des fonctions de services.py / views.py qui
    appellent l'un des `noms_appeles`."""
    trouves = set()
    for fichier in ('services.py', 'views.py'):
        arbre = ast.parse((GED_DIR / fichier).read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sous in ast.walk(noeud):
                if not isinstance(sous, ast.Call):
                    continue
                f = sous.func
                nom = f.attr if isinstance(f, ast.Attribute) else getattr(
                    f, 'id', None)
                if nom in noms_appeles and sous is not noeud:
                    trouves.add((fichier, noeud.name))
    return trouves


class InventaireCheminsTests(SimpleTestCase):
    def test_inventaire_chemins_envoi(self):
        reels = _appelants({'demander_signature', '_send_signataire_email'})
        for chemin in sorted(reels - set(CHEMINS_ENVOI)):
            with self.subTest(chemin=chemin):
                self.fail(f"Chemin d'envoi de lien NON couvert par la garde "
                          f"ADOC81 : {chemin[0]}::{chemin[1]}")

    def test_inventaire_send_mail(self):
        reels = {nom for _f, nom in _appelants({'send_mail'})}
        for nom in sorted(reels - EXPEDITEURS_SEND_MAIL):
            with self.subTest(fonction=nom):
                self.fail(f"Nouvel appel à send_mail dans apps/ged non "
                          f"inventorié par la garde ADOC81 : {nom}")

    def test_inventaire_chemins_signature(self):
        reels = _appelants({'marquer_signe', '_poser_preuves_signature'})
        reels.discard(('services.py', 'marquer_signe'))
        for chemin in sorted(reels - set(CHEMINS_SIGNATURE)):
            with self.subTest(chemin=chemin):
                self.fail(f"Chemin de signature NON couvert par la garde "
                          f"ADOC81 : {chemin[0]}::{chemin[1]}")


@override_settings(
    PUBLIC_BASE_URL=BASE, NUM_PROXIES=1,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GardeLiensEtPreuvesBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc81-a', defaults={'nom': 'Adoc81 A'})
        self.admin = User.objects.create_user(
            username='adoc81-admin', password='x', company=self.co_a,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder = Folder.objects.create(
            company=self.co_a, cabinet=cab, nom='Contrats')
        self.doc = self._document('Contrat ADOC81')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.anon = APIClient()

    def _document(self, nom):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder, nom=nom)
        contenu = b'%PDF-1.4\n%adoc81\n' + nom.encode('utf-8')
        key, _meta = services._store_bytes(contenu, mime='application/pdf')
        services.add_version(
            doc, file_key=key, company=self.co_a, filename='d.pdf',
            size=len(contenu), mime='application/pdf')
        return doc

    def assertLiensAbsolusAtteignables(self, chemin):
        self.assertTrue(mail.outbox, f'{chemin} : aucun mail envoyé')
        for message in mail.outbox:
            liens = RE_LIEN.findall(message.body)
            self.assertTrue(liens, f'{chemin} : mail sans lien')
            for lien in liens:
                self.assertTrue(
                    lien.startswith(f'{BASE}/ged/'),
                    f'{chemin} : lien non absolu sur la base ERP : {lien}')
                api = '/api/django' + lien[len(BASE):]
                self.assertEqual(
                    self.anon.get(api).status_code, 200,
                    f'{chemin} : le lien {lien} ne répond pas 200')


class GardeLiensTests(GardeLiensEtPreuvesBase):
    def test_tout_lien_mail_est_absolu_et_atteignable(self):
        """Résumé de la classe : chaque chemin d'envoi inventorié."""
        for nom in sorted(set(CHEMINS_ENVOI.values())):
            with self.subTest(chemin=nom):
                mail.outbox = []
                getattr(self, f'_declencher_{nom[len("test_"):]}')()
                self.assertLiensAbsolusAtteignables(nom)

    def _declencher_creation_mono(self):
        resp = self.api.post('/api/django/ged/demandes-signature/', {
            'document': self.doc.pk, 'signataire_nom': 'M',
            'signataire_email': 'm@x.ma'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def _declencher_creation_multi(self):
        resp = self.api.post(
            '/api/django/ged/demandes-signature/creer-multi/', {
                'document': self._document('Multi').pk,
                'destinataires': [{'nom': 'A', 'email': 'a@x.ma'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def _declencher_lot_envoi(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Lot', corps_html='<p>{{ nom }}</p>')
        lot = services.creer_lot_envoi_signature(
            company=self.co_a, modele=modele,
            destinataires=[{'nom': 'L', 'email': 'l@x.ma'}],
            created_by=self.admin)
        self.assertEqual(lot.nb_envoyes, 1, lot.resultats)

    def _declencher_regle_dossier(self):
        services._executer_action_regle(
            self._document('Regle'), {
                'type': 'demander_signature',
                'params': {'signataire_nom': 'R',
                           'signataire_email': 'r@x.ma'}},
            user=self.admin)

    def _declencher_operation_lot(self):
        resultats, erreurs = services.operation_lot(
            [self._document('Lot op')], operation='demander_signature',
            params={'signataire_nom': 'O', 'signataire_email': 'o@x.ma'},
            user=self.admin)
        self.assertFalse(erreurs, erreurs)

    def _declencher_relance(self):
        demande = services.creer_demande_multi_signataires(
            self._document('Relance'),
            destinataires=[{'nom': 'Z', 'email': 'z@x.ma'}],
            company=self.co_a, relance_cadence_jours=1)
        signataire = demande.signataires.get()
        signataire.notifie_le = timezone.now() - timezone.timedelta(days=2)
        signataire.save(update_fields=['notifie_le'])
        mail.outbox = []
        self.assertEqual(len(services.relancer_signataires_dus(self.co_a)), 1)


class GardePreuvesTests(GardeLiensEtPreuvesBase):
    def _assert_preuves(self, cible, chemin):
        cible.refresh_from_db()
        self.assertEqual(cible.adresse_ip, CLIENT,
                         f'{chemin} : IP de preuve absente ou fausse')
        self.assertTrue(cible.consentement_explicite,
                        f'{chemin} : consentement non persisté')
        self.assertTrue(cible.signature_texte or cible.signature_tracee,
                        f'{chemin} : forme de signature absente')
        self.assertEqual(len(cible.hash_contenu), 64,
                         f'{chemin} : hash du contenu signé absent')

    def _post_signer(self, url):
        return self.anon.post(url, {
            'action': 'signer', 'consentement': True,
            'signature_texte': 'Signataire'}, format='json',
            REMOTE_ADDR=NGINX, HTTP_X_FORWARDED_FOR=CLIENT)

    def test_toute_signature_persiste_ses_preuves(self):
        for chemin in ('test_signature_publique_mono',
                       'test_signature_publique_multi',
                       'test_marquer_signe_manuel'):
            with self.subTest(chemin=chemin):
                getattr(self, f'_{chemin[len("test_"):]}')()

    def _signature_publique_mono(self):
        demande = services.demander_signature(
            self._document('Mono'), signataire_nom='S',
            signataire_email='s@x.ma', company=self.co_a)
        resp = self._post_signer(f'/api/django/ged/signature/{demande.token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_preuves(demande, 'signature publique mono')

    def _signature_publique_multi(self):
        demande = services.creer_demande_multi_signataires(
            self._document('Multi signe'),
            destinataires=[{'nom': 'S', 'email': 's@x.ma'}],
            company=self.co_a)
        signataire = demande.signataires.get()
        resp = self._post_signer(
            f'/api/django/ged/signataire/{signataire.token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self._assert_preuves(signataire, 'signature publique multi')
        demande.refresh_from_db()
        self.assertEqual(len(demande.hash_contenu), 64)

    def _marquer_signe_manuel(self):
        demande = services.demander_signature(
            self._document('Manuel'), signataire_nom='S',
            signataire_email='s@x.ma', company=self.co_a)
        resp = self.api.post(
            f'/api/django/ged/demandes-signature/{demande.pk}/marquer-signe/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        demande.refresh_from_db()
        self.assertIsNotNone(demande.version_signee_id,
                             'marquer-signe : PDF signé non figé')
        self.assertEqual(len(demande.hash_contenu), 64,
                         'marquer-signe : hash du PDF signé absent')
