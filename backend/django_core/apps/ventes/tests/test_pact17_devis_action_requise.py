"""PACT17 — « Relances du jour » : l'agrégat serveur que l'écran
``DevisActionBoardPage`` appelait depuis sa création SANS QU'IL EXISTE.

L'entrée de menu « Ventes → Action requise » est publiée aux rôles responsable
et admin : un utilisateur pouvait cliquer dessus et tomber sur un écran mort,
parce que ``GET /ventes/devis/action-requise/`` retombait sur la route de
DÉTAIL du routeur (``devis/<pk>/`` accepte n'importe quel segment) → 404.

Ce module vérifie les quatre choses qui font que le trou est vraiment bouché :
  1. la route RÉPOND (200) et publie TOUJOURS les 5 paniers ;
  2. chaque devis tombe dans le BON panier, et dans UN SEUL ;
  3. la réponse est bornée à la société de l'appelant (multi-tenant) ;
  4. la réponse a EXACTEMENT la forme de l'exemple de contrat committé
     (``contract_samples/devis_action_requise.json``, PACT10) — c'est ce
     fichier que le test frontend importe, donc les deux moitiés ne peuvent
     plus diverger en silence.
"""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors import devis_action_requise

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
URL = '/api/django/ventes/devis/action-requise/'
ECHANTILLON = (Path(__file__).resolve().parent.parent
               / 'contract_samples' / 'devis_action_requise.json')

PANIERS = [
    'envoyes_sans_reponse', 'acceptes_non_factures', 'refuses_sans_motif',
    'expirant_bientot', 'engagement_relance',
]
# Clés d'une ligne d'affichage — affirmées ICI contre la VRAIE sortie du
# sélecteur (voir test_la_ligne_d_affichage_est_servie_par_le_serveur) ET
# contre l'exemple de contrat que le test frontend importe : les deux moitiés
# ne peuvent plus diverger.
CLES_LIGNE = ['client_nom', 'client_telephone', 'client_whatsapp', 'id',
              'reference', 'total_ttc']


class Pact17ActionRequiseSelectorTests(TestCase):
    """Le classement lui-même : un devis, un panier, jamais deux."""

    def setUp(self):
        self.company = Company.objects.create(nom='PACT17 Co')
        self.autre = Company.objects.create(nom='PACT17 Autre Co')
        self.user = User.objects.create_user(
            username='pact17_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Benali', prenom='Amine',
            telephone='+212600000017')
        self.today = timezone.localdate()

    def _devis(self, ref, **kwargs):
        kwargs.setdefault('taux_tva', Decimal('20'))
        return Devis.objects.create(
            company=kwargs.pop('company', self.company), reference=ref,
            client=kwargs.pop('client', self.client_obj),
            created_by=self.user, **kwargs)

    def _ids(self, panier, **kwargs):
        board = devis_action_requise(self.company, today=self.today, **kwargs)
        return board['buckets'][panier]['ids']

    def test_les_cinq_paniers_sont_toujours_publies(self):
        """Une société SANS aucun devis publie quand même les 5 clés à zéro :
        un panier absent ferait afficher « — » pour toujours côté écran."""
        board = devis_action_requise(self.company, today=self.today)
        self.assertEqual(sorted(board['buckets']), sorted(PANIERS))
        for cle in PANIERS:
            self.assertEqual(board['buckets'][cle],
                             {'count': 0, 'ids': []}, cle)
        self.assertEqual(board['wa_drafts'], {})
        self.assertEqual(board['devis'], {})

    def test_la_ligne_d_affichage_est_servie_par_le_serveur(self):
        """L'écran cherchait `client_telephone`/`client_whatsapp` dans la liste
        des devis — deux champs que `DevisSerializer` NE PUBLIE PAS : les
        raccourcis « Appeler »/WhatsApp ne s'affichaient jamais. Le serveur
        sert désormais la ligne complète pour chaque id cité."""
        devis = self._devis(
            f'DEV-{MONTH}-P1740', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=9))
        ligne = devis_action_requise(
            self.company, today=self.today)['devis'][devis.id]
        self.assertEqual(ligne['id'], devis.id)
        self.assertEqual(ligne['reference'], devis.reference)
        self.assertEqual(ligne['client_nom'], 'Benali')
        self.assertEqual(ligne['client_telephone'], '+212600000017')
        self.assertEqual(ligne['client_whatsapp'], '')
        # Le total est du TEXTE décimal (jamais un flottant), et AUCUN prix
        # d'achat ni aucune marge n'accompagne la ligne (règle #4).
        self.assertIsInstance(ligne['total_ttc'], str)
        self.assertEqual(sorted(ligne), CLES_LIGNE)

    def test_aucune_ligne_pour_un_devis_hors_panier(self):
        self._devis(f'DEV-{MONTH}-P1741', statut=Devis.Statut.BROUILLON)
        self.assertEqual(
            devis_action_requise(self.company, today=self.today)['devis'], {})

    def test_envoye_depuis_plus_du_palier_de_cadence(self):
        devis = self._devis(
            f'DEV-{MONTH}-P1701', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=5))
        self.assertEqual(self._ids('envoyes_sans_reponse'), [devis.id])

    def test_envoye_du_jour_n_est_pas_encore_une_relance(self):
        self._devis(f'DEV-{MONTH}-P1702', statut=Devis.Statut.ENVOYE,
                    date_envoi=timezone.now())
        self.assertEqual(self._ids('envoyes_sans_reponse'), [])

    def test_accepte_non_facture_reutilise_zfac12(self):
        devis = self._devis(
            f'DEV-{MONTH}-P1703', statut=Devis.Statut.ACCEPTE,
            date_acceptation=self.today - timedelta(days=30))
        self.assertEqual(self._ids('acceptes_non_factures'), [devis.id])

    def test_refuse_sans_motif(self):
        devis = self._devis(f'DEV-{MONTH}-P1704', statut=Devis.Statut.REFUSE,
                            motif_refus='')
        avec_motif = self._devis(
            f'DEV-{MONTH}-P1705', statut=Devis.Statut.REFUSE,
            motif_refus='Trop cher')
        ids = self._ids('refuses_sans_motif')
        self.assertIn(devis.id, ids)
        self.assertNotIn(avec_motif.id, ids)

    def test_expirant_bientot(self):
        devis = self._devis(
            f'DEV-{MONTH}-P1706', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=10),
            date_validite=self.today + timedelta(days=2))
        # Prime sur « envoyés sans réponse » : le signal le plus fort gagne, et
        # le devis n'est JAMAIS compté deux fois.
        self.assertEqual(self._ids('expirant_bientot'), [devis.id])
        self.assertNotIn(devis.id, self._ids('envoyes_sans_reponse'))

    def test_echeance_deja_depassee_n_est_pas_expirant_bientot(self):
        devis = self._devis(
            f'DEV-{MONTH}-P1707', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=40),
            date_validite=self.today - timedelta(days=1))
        self.assertEqual(self._ids('expirant_bientot'), [])
        self.assertIn(devis.id, self._ids('envoyes_sans_reponse'))

    def test_engagement_prime_sur_tout_et_porte_son_brouillon(self):
        devis = self._devis(
            f'DEV-{MONTH}-P1708', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=6),
            date_validite=self.today + timedelta(days=3))
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=4,
            engagement_triggers_fired=['reopened_3x'])
        board = devis_action_requise(self.company, today=self.today)
        self.assertEqual(board['buckets']['engagement_relance']['ids'],
                         [devis.id])
        self.assertEqual(board['buckets']['expirant_bientot']['ids'], [])
        self.assertEqual(board['buckets']['envoyes_sans_reponse']['ids'], [])
        brouillon = board['wa_drafts'][devis.id]
        self.assertIn('Amine', brouillon)
        self.assertIn(devis.reference, brouillon)
        # Un brouillon part TEL QUEL dans WhatsApp : jamais de montant dedans.
        self.assertNotIn('MAD', brouillon)

    def test_lien_sans_declencheur_ne_cree_aucune_file_engagement(self):
        devis = self._devis(
            f'DEV-{MONTH}-P1709', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=6))
        ShareLink.objects.create(company=self.company, devis=devis)
        board = devis_action_requise(self.company, today=self.today)
        self.assertEqual(board['buckets']['engagement_relance']['ids'], [])
        self.assertEqual(board['wa_drafts'], {})
        self.assertEqual(board['buckets']['envoyes_sans_reponse']['ids'],
                         [devis.id])

    def test_brouillon_et_expire_ne_sont_dans_aucun_panier(self):
        self._devis(f'DEV-{MONTH}-P1710', statut=Devis.Statut.BROUILLON)
        self._devis(f'DEV-{MONTH}-P1711', statut=Devis.Statut.EXPIRE,
                    date_envoi=timezone.now() - timedelta(days=90))
        board = devis_action_requise(self.company, today=self.today)
        for cle in PANIERS:
            self.assertEqual(board['buckets'][cle]['ids'], [], cle)

    def test_compte_et_ids_sont_coherents(self):
        for i in range(3):
            self._devis(f'DEV-{MONTH}-P172{i}', statut=Devis.Statut.ENVOYE,
                        date_envoi=timezone.now() - timedelta(days=9))
        board = devis_action_requise(self.company, today=self.today)
        panier = board['buckets']['envoyes_sans_reponse']
        self.assertEqual(panier['count'], len(panier['ids']))
        self.assertEqual(panier['count'], 3)

    def test_jamais_de_devis_d_une_autre_societe(self):
        autre_client = Client.objects.create(
            company=self.autre, nom='Fuite', prenom='Cross')
        intrus = self._devis(
            f'DEV-{MONTH}-P1730', company=self.autre, client=autre_client,
            statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=9))
        board = devis_action_requise(self.company, today=self.today)
        tous = [i for cle in PANIERS for i in board['buckets'][cle]['ids']]
        self.assertNotIn(intrus.id, tous)


class Pact17ActionRequiseApiTests(TestCase):
    """La ROUTE : elle existe, elle est gardée, elle respecte le contrat."""

    def setUp(self):
        self.company = Company.objects.create(nom='PACT17 API Co')
        self.responsable = User.objects.create_user(
            username='pact17_api_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()

    def test_la_route_repond_200_et_ne_404_plus(self):
        """LE défaut de PACT17 : ce chemin retombait sur `devis/<pk>/`."""
        self.api.force_authenticate(user=self.responsable)
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sorted(resp.data['buckets']), sorted(PANIERS))
        self.assertIn('wa_drafts', resp.data)
        self.assertIn('devis', resp.data)

    def test_anonyme_refuse(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_forme_identique_a_l_exemple_de_contrat_committe(self):
        """PACT10 — le test backend affirme que sa VRAIE réponse égale
        l'exemple ; le test frontend importe ce même fichier. Si le serveur
        change de forme, l'exemple doit changer et les deux tests cassent."""
        exemple = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        self.api.force_authenticate(user=self.responsable)
        reelle = self.api.get(URL).data
        for variante in ('exemple', 'exemple_vide'):
            attendu = exemple[variante]
            self.assertEqual(sorted(attendu), sorted(reelle), variante)
            self.assertEqual(sorted(attendu['buckets']),
                             sorted(reelle['buckets']), variante)
            for cle, panier in attendu['buckets'].items():
                self.assertEqual(sorted(panier), ['count', 'ids'], cle)
            for cle, ligne in attendu['devis'].items():
                self.assertEqual(sorted(ligne), CLES_LIGNE, cle)
