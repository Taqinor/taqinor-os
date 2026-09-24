"""CAD101 — « pièce reçue » : le geste pour enregistrer ce que le client envoie.

Avant : le client envoie sa facture ou son adresse sur WhatsApp — l'événement
commercial le plus important du parcours — et rien ne l'enregistrait en un
clic ; un message entrant est une note SYSTÈME que les récepteurs d'arrêt
ignorent, donc le système continuait de relancer quelqu'un qui venait
d'envoyer sa facture.

Done : ``POST relance-etapes/<id>/piece-recue/`` clôt la touche (issue
« joint »), attache le document et pose « Préparer et envoyer le devis » ; un
message ENTRANT n'arrête toujours rien (le geste reste humain). Contrat
partagé : la réponse a EXACTEMENT les clés de ``relance_piece_recue.json`` et
sa touche celles de ``relance_etape_v2.json``.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import FILET_JOINT_LIBELLE
from apps.parametres.models import CompanyProfile
from apps.records.models import Attachment

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'

# PNG minimal (octets magiques suffisants pour la détection de type).
_FAUX_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'cad101'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.gel = gel
        self.company = Company.objects.create(nom='CAD101 Solaire',
                                              slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661112233', whatsapp='+212661112233')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=5,
            canal=RelanceEtape.Canal.WHATSAPP, libelle='Message valeur (J1)',
            template_cle='valeur_j1', due_at=MERCREDI,
            due_date=MERCREDI.date(), cadence_depart=MERCREDI)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _piece(self, etape=None, **corps):
        etape = etape or self.etape
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/piece-recue/', corps,
            format='multipart' if 'fichier' in corps else 'json')


class PieceRecueTests(_Base):
    slug = 'cad101-geste'

    def test_la_touche_est_close_et_l_etape_devis_posee(self):
        resp = self._piece(type_piece='facture')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(self.etape.outcome, 'joint')
        self.assertIn('Pièce reçue — facture', self.etape.note)
        ouvertes = list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE))
        # UNE seule suite, et c'est « préparer le devis » — jamais un second
        # filet posé par le récepteur « joint ».
        self.assertEqual([e.libelle for e in ouvertes], [FILET_JOINT_LIBELLE])
        self.assertEqual(resp.data['prochaine_touche']['due_date'],
                         ouvertes[0].due_date.isoformat())

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._piece(type_piece='adresse', note='Villa 12, Targa')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = _contrat('relance_piece_recue')
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        self.assertEqual(
            set(resp.data) - {'prochaine_touche'},
            set(_contrat('relance_etape_v2')['exemple']['results'][0]))

    def test_le_document_est_attache_a_la_ligne_de_la_touche(self):
        fichier = SimpleUploadedFile('facture.png', _FAUX_PNG,
                                     content_type='image/png')
        # Le VRAI téléversement MinIO signe ses requêtes S3 avec l'horloge du
        # processus : sous gel, botocore signe à MERCREDI (prouvé — l'ignore
        # freezegun ne couvre pas ce chemin) et MinIO refuse en
        # RequestTimeTooSkewed dès que |réel − gel| > 15 min → 500. Ce test
        # n'affirme aucune date : le geste s'exécute à l'horloge réelle — avec
        # un jeton minté DANS la même fenêtre (celui du setUp, né sous gel,
        # serait déjà expiré à l'horloge réelle : 401).
        self.gel.stop()
        try:
            self.api.credentials(
                HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
            resp = self._piece(type_piece='facture', fichier=fichier)
        finally:
            self.gel.start()
        self.assertEqual(resp.status_code, 200, resp.data)
        piece = Attachment.objects.get(company=self.company,
                                       object_id=self.lead.pk)
        ligne = LeadActivity.objects.get(lead=self.lead, attachment=piece)
        self.assertEqual(ligne.outcome, 'joint')
        self.assertIn('fichier joint', ligne.body)

    def test_une_piece_inconnue_ou_absente_est_refusee_en_nommant_le_champ(self):
        for corps in ({}, {'type_piece': 'photo_toit'}):
            resp = self._piece(**corps)
            self.assertEqual(resp.status_code, 400)
            self.assertIn('type_piece', resp.data['erreurs'])
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_une_touche_deja_traitee_est_refusee(self):
        self._piece(type_piece='facture')
        resp = self._piece(type_piece='facture')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('etape', resp.data['erreurs'])

    def test_sur_l_etape_preparer_le_devis_elle_reste_ouverte(self):
        filet = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle=FILET_JOINT_LIBELLE, due_at=MERCREDI,
            due_date=MERCREDI.date())
        resp = self._piece(etape=filet, type_piece='localisation')
        self.assertEqual(resp.status_code, 200, resp.data)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__contains='Pièce reçue du client').exists())


class MessageEntrantTests(_Base):
    slug = 'cad101-entrant'

    def test_un_message_entrant_n_arrete_rien(self):
        # Un message entrant = une note SYSTÈME (`user=None`) : c'est le geste
        # humain « pièce reçue », jamais le message, qui clôt la touche.
        LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=None,
            kind=LeadActivity.Kind.WHATSAPP, body='Merci, voici ma facture.')
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
