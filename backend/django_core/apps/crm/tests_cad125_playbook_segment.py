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
        # CIQ517 — `dossier_8221` exige en plus un site MT, une
        # régularisation ou une revente (voir Ciq517Tests).
        for segment, attendue in (
                ('industriel', None),
                ('commercial', None),
                ('residentiel', None),
                ('', None),
                (None, None)):
            with self.subTest(segment=segment):
                self.assertEqual(
                    cle_message_segment(
                        Lead(type_installation=segment)), attendue)
        # AGR525 — `dossier_fda` pour un agricole AU BUTANE seulement.
        self.assertEqual(cle_message_segment(Lead(
            type_installation='agricole', pompe_alim_actuelle='butane')),
            'dossier_fda')
        for energie in (None, 'diesel', 'electrique', 'aucune'):
            with self.subTest(energie=energie):
                self.assertIsNone(cle_message_segment(Lead(
                    type_installation='agricole',
                    pompe_alim_actuelle=energie)))


class LePlaybookPoseLaTacheTests(TestCase):
    slug = 'cad125'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        seed_playbooks_segment(self.company)

    def _lead(self, segment, **extra):
        return Lead.objects.create(
            company=self.company, nom=f'Lead {segment or "vide"}',
            owner=self.acteur, stage=stages.CONTACTED,
            type_installation=segment, **extra)

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
        # CIQ517 — un industriel en MT.
        noms = self._noms_recommandes(
            self._lead('industriel', tension_raccordement='mt'))
        self.assertEqual(noms, {PLAYBOOKS_SEGMENT_CAD125[0]['nom']})

    def test_un_agricole_reçoit_le_playbook_FDA_et_lui_seul(self):
        # AGR525 — l'agricole AU BUTANE (cible du pilote FDA).
        noms = self._noms_recommandes(
            self._lead('agricole', pompe_alim_actuelle='butane'))
        self.assertEqual(noms, {PLAYBOOKS_SEGMENT_CAD125[1]['nom']})

    def test_agr525_un_agricole_au_diesel_n_a_aucune_tache_fda(self):
        lead = self._lead('agricole', pompe_alim_actuelle='diesel')
        self.assertEqual(self._noms_recommandes(lead), set())
        self.assertIsNone(cle_message_segment(lead))
        from apps.crm.services import generer_playbook_progress
        self.assertEqual(generer_playbook_progress(lead, stages.CONTACTED),
                         [])

    def test_agr525_au_butane_tache_et_cle_fda(self):
        from apps.crm.services import generer_playbook_progress
        lead = self._lead('agricole', pompe_alim_actuelle='butane')
        self.assertEqual(len(generer_playbook_progress(
            lead, stages.CONTACTED)), 1)
        self.assertEqual(cle_message_segment(lead), 'dossier_fda')

    def test_agr525_diesel_puis_butane_a_contacted_la_tache_apparait(self):
        from apps.crm.models import LeadPlaybookProgress
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        lead = self._lead('agricole', pompe_alim_actuelle='diesel')
        self.assertFalse(
            LeadPlaybookProgress.objects.filter(lead=lead).exists())
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        resp = api.patch(f'/api/django/crm/leads/{lead.id}/',
                         {'pompe_alim_actuelle': 'butane'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 1)
        # Rejouer ne double rien.
        from apps.crm.services import rattraper_playbooks_pompe
        lead.refresh_from_db()
        self.assertEqual(rattraper_playbooks_pompe(lead), [])
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 1)

    def test_agr525_migration_rejouee_et_playbook_personnalise_intact(self):
        import importlib
        from django.apps import apps as django_apps
        migration = importlib.import_module(
            'apps.crm.migrations.0122_agr525_seed_playbooks_segment_existants')
        ancienne = Company.objects.create(slug='agr525-anc', nom='anc')
        fda = Playbook.objects.create(
            company=ancienne, nom=PLAYBOOKS_SEGMENT_CAD125[1]['nom'],
            condition=migration.ANCIENNE_CONDITION_FDA)
        perso = Company.objects.create(slug='agr525-perso', nom='perso')
        condition_perso = {'field': 'canal', 'operator': 'eq',
                           'value': 'reference'}
        fda_perso = Playbook.objects.create(
            company=perso, nom=PLAYBOOKS_SEGMENT_CAD125[1]['nom'],
            condition=condition_perso)
        migration.rattraper(django_apps, None)
        etat = sorted(Playbook.objects.values_list(
            'company_id', 'nom', 'condition'), key=repr)
        migration.rattraper(django_apps, None)
        self.assertEqual(sorted(Playbook.objects.values_list(
            'company_id', 'nom', 'condition'), key=repr), etat)
        fda.refresh_from_db()
        fda_perso.refresh_from_db()
        self.assertEqual(fda.condition, migration.NOUVELLE_CONDITION_FDA)
        self.assertEqual(fda_perso.condition, condition_perso)
        # Les deux playbooks existent pour chaque société, une seule fois.
        for company in (ancienne, perso, self.company):
            self.assertEqual(
                Playbook.objects.filter(company=company).count(), 2)
        # La condition semée par le code égale celle de la migration.
        self.assertEqual(
            Playbook.objects.get(
                company=self.company,
                nom=PLAYBOOKS_SEGMENT_CAD125[1]['nom']).condition,
            migration.NOUVELLE_CONDITION_FDA)

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


# ── CIQ517 (D-CIQ-6) — 82-21 seulement pour un site MT, une régularisation
# ou une revente ; un texte « raccordement et autorisations du site » ──────

class Ciq517Tests(TestCase):
    slug = 'ciq517'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        seed_playbooks_segment(self.company)
        self.nom_8221 = PLAYBOOKS_SEGMENT_CAD125[0]['nom']

    def _lead(self, segment, **extra):
        return Lead.objects.create(
            company=self.company, nom=f'Lead {segment}', owner=self.acteur,
            stage=stages.CONTACTED, type_installation=segment, **extra)

    def _taches(self, lead):
        from apps.crm.services import generer_playbook_progress
        return generer_playbook_progress(lead, stages.CONTACTED)

    def test_a_commercial_bt_sans_regularisation_ni_revente(self):
        lead = self._lead('commercial', tension_raccordement='bt')
        self.assertEqual(self._taches(lead), [])
        self.assertIsNone(cle_message_segment(lead))

    def test_b_industriel_mt_tache_et_cle(self):
        lead = self._lead('industriel', tension_raccordement='mt')
        self.assertEqual(len(self._taches(lead)), 1)
        self.assertEqual(cle_message_segment(lead), 'dossier_8221')

    def test_c_commercial_bt_qui_veut_revendre(self):
        lead = self._lead('commercial', tension_raccordement='bt',
                          objectif_projet='injection_8221')
        self.assertEqual(len(self._taches(lead)), 1)
        self.assertEqual(cle_message_segment(lead), 'dossier_8221')

    def test_regularisation_8221(self):
        lead = self._lead('commercial', regularisation_8221=True)
        self.assertEqual(cle_message_segment(lead), 'dossier_8221')

    def test_deja_contacte_passe_en_mt_la_tache_apparait(self):
        from apps.crm.models import LeadPlaybookProgress
        from apps.crm.services import rattraper_playbooks_8221
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        lead = self._lead('industriel', tension_raccordement='bt')
        self._taches(lead)
        self.assertFalse(
            LeadPlaybookProgress.objects.filter(lead=lead).exists())
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        resp = api.patch(f'/api/django/crm/leads/{lead.id}/',
                         {'tension_raccordement': 'mt'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 1)
        lead.refresh_from_db()
        self.assertEqual(rattraper_playbooks_8221(lead), [])
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 1)

    def test_d_migration_rejouee_et_playbook_personnalise_intact(self):
        import importlib
        from django.apps import apps as django_apps
        migration = importlib.import_module(
            'apps.crm.migrations.0127_ciq517_playbook_8221_condition')
        from apps.crm.models import PlaybookEtape, PlaybookTache
        ancienne = Company.objects.create(slug='ciq517-anc', nom='anc')
        pb = Playbook.objects.create(
            company=ancienne, nom=self.nom_8221,
            condition=migration.ANCIENNE_CONDITION_8221)
        etape = PlaybookEtape.objects.create(
            playbook=pb, stage=stages.CONTACTED, ordre=0)
        tache = PlaybookTache.objects.create(
            etape=etape, libelle=migration.ANCIENNE_TACHE, ordre=0)
        perso = Company.objects.create(slug='ciq517-perso', nom='perso')
        condition_perso = {'field': 'canal', 'operator': 'eq',
                           'value': 'reference'}
        pb_perso = Playbook.objects.create(
            company=perso, nom=self.nom_8221, condition=condition_perso)
        migration.restreindre(django_apps, None)
        etat = sorted(Playbook.objects.values_list(
            'company_id', 'nom', 'condition'), key=repr)
        migration.restreindre(django_apps, None)
        self.assertEqual(sorted(Playbook.objects.values_list(
            'company_id', 'nom', 'condition'), key=repr), etat)
        pb.refresh_from_db()
        pb_perso.refresh_from_db()
        tache.refresh_from_db()
        self.assertEqual(pb.condition, migration.NOUVELLE_CONDITION_8221)
        self.assertEqual(tache.libelle, migration.NOUVELLE_TACHE)
        self.assertEqual(pb_perso.condition, condition_perso)
        # La condition semée par le code égale celle de la migration.
        self.assertEqual(
            Playbook.objects.get(company=self.company,
                                 nom=self.nom_8221).condition,
            migration.NOUVELLE_CONDITION_8221)
        self.assertEqual(PLAYBOOKS_SEGMENT_CAD125[0]['tache'],
                         migration.NOUVELLE_TACHE)

    def test_e_texte_fr_et_darija_sans_loi_ni_8221_ni_chiffre(self):
        from apps.parametres.models_messages import (
            MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
        )
        for texte in (MESSAGE_TEMPLATE_DEFAULTS['dossier_8221'],
                      MESSAGE_TEMPLATE_DEFAULTS_DARIJA['dossier_8221']):
            with self.subTest(texte=texte[:30]):
                self.assertNotIn('82-21', texte)
                self.assertNotIn('loi', texte.lower())
                self.assertNotIn('قانون', texte)
                self.assertEqual(re.findall(r'\d', texte), [])
        self.assertIn('raccordement et autorisations du site',
                      MESSAGE_TEMPLATE_DEFAULTS['dossier_8221'])
        self.assertNotIn('82-21', PLAYBOOKS_SEGMENT_CAD125[0]['tache'])
