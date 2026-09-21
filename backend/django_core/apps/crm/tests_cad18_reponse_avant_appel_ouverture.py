"""CAD18 — le lead qui répond AVANT l'appel d'ouverture garde un script.

Le trou : en régime réactif (CKP2) seule la touche 1 — le message d'identité
— existe au démarrage. Le prospect qui répond à ce message avant l'appel
J0+3 min est marqué « joint » ; le récepteur MRY9 arrête alors la prise de
contact, et le filet pose « Appeler le client — il a répondu au message ».
Cette étape naissait sans aucun ``template_cle`` : le dossier le plus chaud
du portefeuille était le SEUL appel du protocole sans script.

Correction du round 2, verrouillée ici : la clé posée est
``appel_apres_reponse``, et surtout PAS ``appel_ouverture`` — « vous venez de
remplir notre formulaire » est faux pour quelqu'un qui vient d'échanger avec
nous.

Garde-fous vérifiés : aucun barreau ajouté (c'est le filet EXISTANT qui
hérite d'un script), une seule touche ouverte (CKP2), et les autres libellés
de filet restent sans gabarit — aucun texte validé n'existe pour eux.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    FILET_APPEL_LIBELLE, FILET_JOINT_LIBELLE, initialiser_plan_relance,
    marquer_etape_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 22 septembre 2026, 10 h à Casablanca — jour ouvré, dans la fenêtre
#: d'appel comme dans la fenêtre de message.
MARDI = datetime.datetime(2026, 9, 22, 10, 0, tzinfo=horaires.CASABLANCA)

#: CAD18 — la clé attendue sur l'étape de filet.
CLE_ATTENDUE = 'appel_apres_reponse'


class _Base(TestCase):
    slug = 'cad18'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD18 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.NEW,
            owner=self.acteur, telephone='+212661001801')

    def _demarrer_contact(self):
        """Le plan de PRISE DE CONTACT, en régime réactif : la touche 1 seule
        (le message d'identité) est matérialisée."""
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, cadence='contact', depart=MARDI)
        ouvertes = [e for e in etapes
                    if e.statut == RelanceEtape.Statut.A_FAIRE]
        return ouvertes[0]

    def _ouvertes(self):
        return list(self.lead.relance_etapes
                    .filter(statut=RelanceEtape.Statut.A_FAIRE)
                    .order_by('due_date', 'ordre'))


class ReponseAvantAppelOuvertureTests(_Base):
    slug = 'cad18-joint'

    def test_la_touche_1_est_bien_le_message_d_identite(self):
        touche = self._demarrer_contact()
        # Sans quoi tout le reste du module testerait autre chose.
        self.assertEqual(touche.ordre, 1)
        self.assertEqual(touche.canal, RelanceEtape.Canal.WHATSAPP)

    def test_joint_sur_la_touche_1_pose_une_etape_avec_son_script(self):
        touche = self._demarrer_contact()
        marquer_etape_relance(
            touche, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].libelle, FILET_APPEL_LIBELLE)
        self.assertEqual(ouvertes[0].template_cle, CLE_ATTENDUE)

    def test_le_script_de_l_appel_d_ouverture_n_est_pas_recolle(self):
        touche = self._demarrer_contact()
        marquer_etape_relance(
            touche, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        cles = list(self.lead.relance_etapes
                    .filter(statut=RelanceEtape.Statut.A_FAIRE)
                    .values_list('template_cle', flat=True))
        # « Vous venez de remplir notre formulaire » est faux pour quelqu'un
        # qui vient de répondre : la clé de l'appel d'ouverture est interdite.
        self.assertNotIn('appel_ouverture', cles)

    def test_interesse_sur_la_touche_1_donne_le_meme_script(self):
        touche = self._demarrer_contact()
        marquer_etape_relance(
            touche, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='interesse')
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].template_cle, CLE_ATTENDUE)

    def test_aucun_barreau_n_est_ajoute_au_protocole(self):
        touche = self._demarrer_contact()
        marquer_etape_relance(
            touche, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        # Le filet EXISTANT hérite d'un script ; il ne naît pas une touche de
        # plus dans la cadence `contact`.
        self.assertEqual(
            self.lead.relance_etapes.filter(
                cadence='contact', statut=RelanceEtape.Statut.A_FAIRE).count(),
            0)
        self.assertEqual(
            self.lead.relance_etapes.filter(cadence='generique').count(), 1)


class AutresFiletsSansGabaritTests(_Base):
    """Les autres libellés de filet restent SANS gabarit : aucun texte validé
    n'existe pour eux, et on n'en invente pas."""

    slug = 'cad18-autres'

    def test_le_filet_appel_fait_reste_sans_gabarit(self):
        # Touche d'APPEL clôturée « joint » : le filet pose « préparer et
        # envoyer le devis », qui n'a pas de script à dire.
        touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            template_cle='appel_ouverture', cadence_depart=MARDI)
        marquer_etape_relance(
            touche, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        self.assertEqual(ouvertes[0].libelle, FILET_JOINT_LIBELLE)
        self.assertEqual(ouvertes[0].template_cle, '')
