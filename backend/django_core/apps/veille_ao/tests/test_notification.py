"""VAO25 — la notification quotidienne : utile, en français, NON bruyante.

Le « Done = » de la tâche :
  * notification envoyée SEULEMENT s'il y a du nouveau (rien à dire = rien à
    envoyer — une notification quotidienne vide apprend à ignorer les
    notifications, et le jour où elle compte personne ne la lit) ;
  * destinataires = porteurs de ``veille_ao_voir`` ;
  * texte FR testé (« 3 nouveaux avis — dont 1 à échéance J-12 ») ;
  * AUCUN envoi réseau depuis le service de collecte lui-même : il demande,
    ``apps.notifications`` livre (et respecte préférences, heures calmes et
    canaux de chacun).
"""
import ast
import pathlib
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company, CustomUser
from apps.notifications.models import EventType, Notification
from apps.roles.models import Role

from apps.veille_ao.models import (
    AvisMarche, MotCleVeille, NiveauMotCle, SourceVeille, StatutAvis,
    TypeSource,
)
from apps.veille_ao.services import (
    destinataires_veille, notifier_nouveaux_avis,
)

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Notif')
        self.source = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)
        self.lecteur = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['veille_ao_voir'])
        self.commercial = CustomUser.objects.create_user(
            username='vao_commercial', password='x', company=self.company,
            role=self.lecteur, role_legacy='commercial')

    def _avis(self, *, jours_restants=None):
        limite = (timezone.now() + timedelta(days=jours_restants)
                  if jours_restants is not None else None)
        return AvisMarche.objects.create(
            company=self.company, source=self.source,
            objet='Pompage solaire', statut=StatutAvis.NOUVEAU,
            date_limite_remise=limite)


class DestinatairesTests(_Base):
    def test_les_porteurs_de_veille_ao_voir_sont_destinataires(self):
        self.assertIn(self.commercial, destinataires_veille(self.company))

    def test_un_role_sans_la_permission_n_est_pas_destinataire(self):
        role = Role.objects.create(
            company=self.company, nom='Technicien', permissions=['sav_voir'])
        technicien = CustomUser.objects.create_user(
            username='vao_technicien', password='x', company=self.company,
            role=role, role_legacy='technicien')
        self.assertNotIn(technicien, destinataires_veille(self.company))

    def test_un_utilisateur_d_une_AUTRE_societe_n_est_jamais_destinataire(self):
        autre = Company.objects.create(nom='Autre société')
        role = Role.objects.create(
            company=autre, nom='Commercial', permissions=['veille_ao_voir'])
        etranger = CustomUser.objects.create_user(
            username='vao_etranger', password='x', company=autre, role=role)
        self.assertNotIn(etranger, destinataires_veille(self.company))

    def test_un_compte_desactive_ne_recoit_rien(self):
        self.commercial.is_active = False
        self.commercial.save(update_fields=['is_active'])
        self.assertNotIn(self.commercial, destinataires_veille(self.company))


class SilenceTests(_Base):
    """Rien à dire = RIEN à envoyer. C'est la moitié de la valeur de VAO25."""

    def test_zero_nouveau_n_envoie_AUCUNE_notification(self):
        envoyees = notifier_nouveaux_avis(
            self.company, [{'nouveaux': 0, 'mis_a_jour': 4}])
        self.assertEqual(envoyees, 0)
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.VEILLE_AO_NOUVEAUX_AVIS).exists())

    def test_aucun_rapport_du_tout_n_envoie_rien(self):
        self.assertEqual(notifier_nouveaux_avis(self.company, []), 0)
        self.assertEqual(notifier_nouveaux_avis(self.company, None), 0)


class TexteFrancaisTests(_Base):
    def test_le_texte_annonce_le_nombre_et_l_echeance_la_plus_proche(self):
        self._avis(jours_restants=12)
        self._avis(jours_restants=90)
        self._avis()

        envoyees = notifier_nouveaux_avis(self.company, [{'nouveaux': 3}])

        self.assertEqual(envoyees, 1)
        notification = Notification.objects.get(
            recipient=self.commercial,
            event_type=EventType.VEILLE_AO_NOUVEAUX_AVIS)
        self.assertIn('3 nouveaux avis', notification.title)
        self.assertIn('3 nouveaux avis', notification.body)
        self.assertIn('J-12', notification.body)

    def test_le_singulier_est_correct(self):
        self._avis()
        notifier_nouveaux_avis(self.company, [{'nouveaux': 1}])
        notification = Notification.objects.get(
            recipient=self.commercial,
            event_type=EventType.VEILLE_AO_NOUVEAUX_AVIS)
        self.assertIn('1 nouvel avis', notification.title)
        self.assertNotIn('nouveaux', notification.body)

    def test_sans_echeance_proche_le_texte_ne_ment_pas(self):
        self._avis(jours_restants=200)
        notifier_nouveaux_avis(self.company, [{'nouveaux': 1}])
        notification = Notification.objects.get(
            recipient=self.commercial,
            event_type=EventType.VEILLE_AO_NOUVEAUX_AVIS)
        self.assertNotIn('J-', notification.body)
        self.assertIn('à trier', notification.body)

    def test_une_echeance_DEPASSEE_n_est_jamais_annoncee_comme_urgente(self):
        self._avis(jours_restants=-3)
        notifier_nouveaux_avis(self.company, [{'nouveaux': 1}])
        notification = Notification.objects.get(
            recipient=self.commercial,
            event_type=EventType.VEILLE_AO_NOUVEAUX_AVIS)
        self.assertNotIn('J-', notification.body)

    def test_le_lien_mene_a_la_liste_filtree_sur_les_nouveaux(self):
        self._avis()
        notifier_nouveaux_avis(self.company, [{'nouveaux': 1}])
        notification = Notification.objects.get(
            recipient=self.commercial,
            event_type=EventType.VEILLE_AO_NOUVEAUX_AVIS)
        self.assertEqual(notification.link,
                         '/veille-ao/avis?statut=nouveau')


class AucunEnvoiDepuisLaCollecteTests(TestCase):
    """« Jamais un envoi réseau depuis le service de collecte. »

    Garde MÉCANIQUE (AST) : le module ne doit importer aucun transport
    (e-mail, SMS, WhatsApp, HTTP). Tout part par ``apps.notifications``, qui
    sait respecter les préférences et les heures calmes — un envoi direct les
    contournerait toutes.
    """

    TRANSPORTS_INTERDITS = {
        'smtplib', 'email', 'httpx', 'requests', 'urllib', 'twilio',
        'sendgrid',
    }

    def test_le_module_n_ouvre_aucun_transport_lui_meme(self):
        fautifs = []
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                racines = []
                if isinstance(noeud, ast.Import):
                    racines = [a.name.split('.')[0] for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    racines = [(noeud.module or '').split('.')[0]]
                if any(r in self.TRANSPORTS_INTERDITS for r in racines):
                    fautifs.append(f'{relatif}:{noeud.lineno}')
        self.assertEqual(fautifs, [], fautifs)

    def test_l_envoi_passe_par_apps_notifications(self):
        source = (MODULE_DIR / 'services.py').read_text(encoding='utf-8')
        self.assertIn('from apps.notifications.services import notify_many',
                      source)
