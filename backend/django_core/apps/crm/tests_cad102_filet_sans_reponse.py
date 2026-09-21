"""CAD102 — l'appel du filet resté sans réponse ne réclame plus un devis.

Le client a répondu PAR ÉCRIT au message d'identité, le filet a posé
« Appeler le client — il a répondu au message »… et il ne décroche plus.
L'invariant « aucun lead sans prochaine étape » reposait alors
« Préparer et envoyer le devis (ou fixer un rappel) » à J+1 : l'outil
demandait de chiffrer pour quelqu'un que personne n'avait jamais eu au
téléphone.

Ce module verrouille l'escalier qui s'intercale AVANT le devis :

  1. « Répondeur »/« Occupé » (issue serveur ``non_joint``, CKP4 — aucune
     valeur d'énumération ajoutée) sur l'appel du filet → un MESSAGE pour
     convenir d'un créneau, le jour même, dans la fenêtre des messages ;
  2. ce message traité → un DERNIER appel le lendemain, dans la fenêtre des
     appels ;
  3. ce dernier appel sans réponse → et seulement là, « préparer et envoyer
     le devis ». L'escalier se termine, il ne boucle pas.

Garde-fous vérifiés : une seule touche ouverte à la fois (CKP2), aucun
barreau ajouté à la cadence (ce sont des étapes de FILET, cadence
``generique``), et l'appel du filet réellement ABOUTI garde son ancien
comportement — le devis.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    FILET_APPEL_LIBELLE, FILET_DERNIER_APPEL_LIBELLE, FILET_JOINT_LIBELLE,
    FILET_MESSAGE_CRENEAU_LIBELLE, marquer_etape_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 22 septembre 2026, 10 h à Casablanca — jour ouvré, dans la fenêtre
#: d'appel comme dans celle des messages, et loin du vendredi (dont la pause
#: ne vise que les appels).
MARDI = datetime.datetime(2026, 9, 22, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad102'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD102 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661010201')

    def _filet(self, libelle, canal=RelanceEtape.Canal.APPEL):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=canal, libelle=libelle, due_at=MARDI,
            due_date=MARDI.date(),
            note='Posée automatiquement : aucune autre relance ouverte.')

    def _ouvertes(self):
        return list(self.lead.relance_etapes
                    .filter(statut=RelanceEtape.Statut.A_FAIRE)
                    .order_by('due_at', 'pk'))

    def _seule_ouverte(self):
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        return ouvertes[0]


class EscalierSansReponseTests(_Base):
    slug = 'cad102-escalier'

    def test_l_appel_sans_reponse_pose_un_message_pas_un_devis(self):
        etape = self._filet(FILET_APPEL_LIBELLE)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint', note='Répondeur')
        suite = self._seule_ouverte()
        self.assertEqual(suite.libelle, FILET_MESSAGE_CRENEAU_LIBELLE)
        self.assertNotEqual(suite.libelle, FILET_JOINT_LIBELLE)

    def test_le_message_part_sur_le_canal_des_messages(self):
        etape = self._filet(FILET_APPEL_LIBELLE)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        suite = self._seule_ouverte()
        self.assertEqual(suite.canal, RelanceEtape.Canal.WHATSAPP)
        # Rapproché : le jour même, jamais un délai inventé — la fenêtre de
        # la société décide de l'heure.
        self.assertEqual(suite.due_date, MARDI.date())

    def test_le_message_traite_donne_un_dernier_appel(self):
        premier = self._filet(FILET_APPEL_LIBELLE)
        marquer_etape_relance(
            premier, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        message = self._seule_ouverte()
        # Une touche ÉCRITE se clôt sans issue : l'écran n'en propose pas.
        marquer_etape_relance(
            message, self.acteur, RelanceEtape.Statut.FAIT, outcome='')
        dernier = self._seule_ouverte()
        self.assertEqual(dernier.libelle, FILET_DERNIER_APPEL_LIBELLE)
        self.assertEqual(dernier.canal, RelanceEtape.Canal.APPEL)

    def test_l_escalier_se_termine_sur_le_devis(self):
        etape = self._filet(FILET_DERNIER_APPEL_LIBELLE)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        suite = self._seule_ouverte()
        # Après le dernier essai, le filet reprend son cours : on chiffre.
        self.assertEqual(suite.libelle, FILET_JOINT_LIBELLE)

    def test_aucun_barreau_n_est_ajoute_a_une_cadence(self):
        etape = self._filet(FILET_APPEL_LIBELLE)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        # Toutes les étapes de l'escalier sont des étapes de FILET.
        self.assertEqual(
            self.lead.relance_etapes.exclude(cadence='generique').count(), 0)

    def test_une_seule_touche_ouverte_a_chaque_palier(self):
        etape = self._filet(FILET_APPEL_LIBELLE)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        message = self._seule_ouverte()
        marquer_etape_relance(
            message, self.acteur, RelanceEtape.Statut.FAIT, outcome='')
        dernier = self._seule_ouverte()
        marquer_etape_relance(
            dernier, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        self._seule_ouverte()


class AppelAboutiInchangeTests(_Base):
    """Garde-fou : l'appel du filet qui ABOUTIT garde le devis pour suite."""

    slug = 'cad102-abouti'

    def test_fait_sans_issue_mene_toujours_au_devis(self):
        etape = self._filet(FILET_APPEL_LIBELLE)
        # « Fait — passer à la suite » sur un filet part SANS issue : l'appel
        # a bien eu lieu, le devis est la bonne suite.
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='')
        self.assertEqual(self._seule_ouverte().libelle, FILET_JOINT_LIBELLE)

    def test_joint_mene_toujours_au_devis(self):
        etape = self._filet(FILET_APPEL_LIBELLE)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        self.assertEqual(self._seule_ouverte().libelle, FILET_JOINT_LIBELLE)
