"""CAD125 — le dossier 82-21 et le dossier FDA déclenchent enfin une parole.

Constat de l'audit L3 du 21/09/2026 : ``Lead.regularisation_8221`` est
capté et LU par le scoring (+5 points) — mais par aucune logique de message
ni de touche ; et aucune des clés de relance ne parlait d'une subvention ou
d'un dossier institutionnel, alors que le résidentiel a son équivalent avec
``j6_garanties``.

Le remède n'ajoute NI barreau NI migration : les deux textes sont posés par
une TÂCHE de ``Playbook`` conditionnée sur ``{type_installation}`` — le
mécanisme existe et est déjà évalué contre ce contexte.

**Garde-fou « zéro chiffre inventé », vérifié ici de façon stricte** : les
textes ne citent AUCUN montant, AUCUN plafond, AUCUNE fenêtre de dépôt,
AUCUN nombre de régimes. Le plafond FDA et la fenêtre de dépôt cités au round
2 sont introuvables sur leur source et ne doivent jamais réapparaître.
"""
import re

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, Playbook
from apps.crm.services import (
    PLAYBOOKS_SEGMENT_CAD125, cle_message_segment, playbooks_recommandes,
    seed_playbooks_segment,
)
from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MessageTemplate,
)

User = get_user_model()

CLES_CAD125 = ('dossier_8221', 'dossier_fda')


class LesDeuxClesExistentTests(SimpleTestCase):
    def test_les_deux_cles_sont_au_catalogue(self):
        for cle in CLES_CAD125:
            with self.subTest(cle=cle):
                self.assertIn(cle, CLES_RELANCE)
                self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS)

    def test_elles_sont_des_choix_du_modele(self):
        choix = {valeur for valeur, _ in MessageTemplate.Cle.choices}
        for cle in CLES_CAD125:
            with self.subTest(cle=cle):
                self.assertIn(cle, choix)

    def test_aucun_chiffre_dans_les_deux_textes(self):
        """Le garde-fou le plus important de la tâche."""
        for cle in CLES_CAD125:
            texte = MESSAGE_TEMPLATE_DEFAULTS[cle]
            with self.subTest(cle=cle):
                # Seul « 82-21 » est autorisé : c'est le NOM de la loi, pas un
                # montant. On le retire avant de chercher un chiffre.
                sans_loi = texte.replace('82-21', '')
                self.assertEqual(re.findall(r'\d', sans_loi), [], texte)

    def test_aucun_mot_de_montant_ni_de_plafond(self):
        interdits = ('plafond', 'dirham', 'mad', 'subvention de',
                     'pourcent', '%', 'centime')
        for cle in CLES_CAD125:
            bas = MESSAGE_TEMPLATE_DEFAULTS[cle].lower()
            for mot in interdits:
                with self.subTest(cle=cle, mot=mot):
                    self.assertNotIn(mot, bas)

    def test_les_textes_posent_une_QUESTION(self):
        for cle in CLES_CAD125:
            with self.subTest(cle=cle):
                self.assertIn('?', MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_aucun_prenom_code_en_dur(self):
        """Règle fondateur du 08/09 : l'expéditeur est une VARIABLE."""
        for cle in CLES_CAD125:
            texte = MESSAGE_TEMPLATE_DEFAULTS[cle]
            with self.subTest(cle=cle):
                self.assertIn('{conseiller}', texte)
                self.assertIn('{marque}', texte)


class LeBonSegmentTests(SimpleTestCase):
    def test_82_21_vise_l_industriel_et_le_commercial(self):
        entree = PLAYBOOKS_SEGMENT_CAD125[0]
        self.assertEqual(entree['cle_message'], 'dossier_8221')
        self.assertEqual(set(entree['segments']),
                         {'industriel', 'commercial'})

    def test_le_FDA_vise_l_agricole(self):
        entree = PLAYBOOKS_SEGMENT_CAD125[1]
        self.assertEqual(entree['cle_message'], 'dossier_fda')
        self.assertEqual(set(entree['segments']), {'agricole'})

    def test_la_cle_du_lead_suit_son_segment(self):
        for segment, attendue in (
                ('industriel', 'dossier_8221'),
                ('commercial', 'dossier_8221'),
                ('agricole', 'dossier_fda'),
                ('residentiel', None),
                ('', None),
                (None, None)):
            with self.subTest(segment=segment):
                self.assertEqual(
                    cle_message_segment(
                        Lead(type_installation=segment)), attendue)


class LePlaybookPoseLaTacheTests(TestCase):
    slug = 'cad125'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        seed_playbooks_segment(self.company)

    def _lead(self, segment):
        return Lead.objects.create(
            company=self.company, nom=f'Lead {segment or "vide"}',
            owner=self.acteur, stage=stages.CONTACTED,
            type_installation=segment)

    def _noms_recommandes(self, lead):
        return {p.nom for p in playbooks_recommandes(lead, stages.CONTACTED)}

    def test_les_deux_playbooks_sont_poses(self):
        self.assertEqual(
            Playbook.objects.filter(company=self.company).count(), 2)

    def test_le_seed_est_idempotent(self):
        seed_playbooks_segment(self.company)
        self.assertEqual(
            Playbook.objects.filter(company=self.company).count(), 2)

    def test_un_industriel_reçoit_le_playbook_82_21_et_lui_seul(self):
        noms = self._noms_recommandes(self._lead('industriel'))
        self.assertEqual(noms, {PLAYBOOKS_SEGMENT_CAD125[0]['nom']})

    def test_un_agricole_reçoit_le_playbook_FDA_et_lui_seul(self):
        noms = self._noms_recommandes(self._lead('agricole'))
        self.assertEqual(noms, {PLAYBOOKS_SEGMENT_CAD125[1]['nom']})

    def test_un_residentiel_n_en_recoit_AUCUN(self):
        """Il a déjà `j6_garanties` : on n'invente pas un dossier
        institutionnel pour lui."""
        self.assertEqual(self._noms_recommandes(self._lead('residentiel')),
                         set())

    def test_un_lead_SANS_segment_n_en_recoit_aucun(self):
        self.assertEqual(self._noms_recommandes(self._lead(None)), set())

    def test_la_tache_NOMME_le_texte_a_utiliser(self):
        """Sans cela, la commerciale voit une tâche sans savoir quoi dire."""
        for entree in PLAYBOOKS_SEGMENT_CAD125:
            playbook = Playbook.objects.get(
                company=self.company, nom=entree['nom'])
            libelles = [t.libelle
                        for e in playbook.etapes.all()
                        for t in e.taches.all()]
            with self.subTest(nom=entree['nom']):
                self.assertEqual(len(libelles), 1)
                self.assertIn(entree['cle_message'], libelles[0])

    def test_aucun_barreau_de_cadence_n_est_ajoute(self):
        """« zéro migration et zéro nouveau barreau »."""
        from apps.parametres.models_relance import CADENCES_DEFAUT
        for barreaux in CADENCES_DEFAUT.values():
            for barreau in barreaux:
                with self.subTest(ordre=barreau['ordre']):
                    self.assertNotIn(
                        barreau.get('template_cle', ''), CLES_CAD125)

    def test_une_societe_ne_voit_pas_les_playbooks_d_une_autre(self):
        voisine = Company.objects.create(
            slug=f'{self.slug}-voisine', nom='voisine')
        self.assertEqual(
            Playbook.objects.filter(company=voisine).count(), 0)
