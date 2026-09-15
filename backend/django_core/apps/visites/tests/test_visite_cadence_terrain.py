"""VISITE-CADENCE — la moitié TERRAIN : ce que l'app visites publie.

Ordre fondateur du 15/09/2026 : la visite technique est une ÉTAPE DU SUIVI
COMMERCIAL, posée APRÈS l'envoi du devis. Cette app n'en sait rien — et c'est
le point : elle PUBLIE deux faits et expose deux lectures, le CRM décide.

Ce qui est prouvé ici :

* ``planifier_visite`` crée la visite (brouillon, société prise du LEAD),
  prévient l'assigné (primitive VTA7 existante) et publie
  ``visite_planifiee`` ; ses DEUX refus arrivent AVANT toute écriture et
  NOMMENT leur champ (date passée, commercial d'une autre société) ;
* ``terminer`` publie ``visite_terminee`` en emportant le RETOUR TERRAIN —
  le texte libre, précisément ce que le récap de ``visite_validee`` (mesures
  seules) n'a jamais transporté — et prévient ceux qui peuvent valider ;
* ``visites_pour_lead`` sert la forme du contrat CRM, bornée à la société du
  lead, et ``retour_disponible`` ne s'allume que s'il y a vraiment du texte
  à lire.

Isolation multi-société : deux VRAIS locataires, avec leurs données.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.time import frozen

from apps.crm.models import Lead
from apps.notifications.models import EventType, Notification
from apps.roles.models import Role
from apps.visites import qualification, selectors, services
from apps.visites.models import VisiteMedia, VisiteTerrain
from authentication.models import Company

User = get_user_model()

#: Octets magiques PNG — suffisants pour la détection de ``records.storage``.
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64

#: Mardi 15 septembre 2026, 10 h — horloge FIXE : « hier » et « demain » ne
#: doivent pas dépendre du jour où passe la CI.
MAINTENANT = datetime.datetime(2026, 9, 15, 10, 0,
                               tzinfo=datetime.timezone.utc)
AUJOURDHUI = datetime.date(2026, 9, 15)

TERRAIN = ['crm_voir', 'visites_voir', 'visites_creer', 'visites_modifier']
BUREAU = TERRAIN + ['visites_valider']

SLOTS_REQUIS = [
    ('toiture_vue_generale', 2),
    ('toiture_obstacles', 1),
    ('tableau_ouvert', 1),
    ('onduleur_mur', 1),
    ('general_facade', 1),
]

MESURES_COMPLETES = {
    'toiture': {
        'longueur_m': 12.5, 'largeur_m': 8, 'pente_deg': 15,
        'toit_plat': False, 'orientation': 'sud', 'type_couverture': 'tuile',
        'etat_couverture': 'bon',
    },
    'tableau': {
        'calibre_disjoncteur_a': 63, 'type_alimentation': 'mono',
        'emplacements_libres': 4,
    },
    'local_onduleur': {
        'largeur_mur_cm': 200, 'hauteur_mur_cm': 250,
        'profondeur_degagement_cm': 80, 'distance_tableau_m': 5,
        'local_abrite': True, 'local_ventile': True,
    },
}


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, username, permissions, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy,
        role=Role.objects.create(company=company, nom=f'role-{username}',
                                 permissions=list(permissions)))


class VisiteCadenceBase(TestCase):
    """Deux locataires RÉELS, chacun avec son commercial et son lead."""

    def setUp(self):
        self.company = Company.objects.create(nom='VCAD Solaire',
                                              slug='vcad-a')
        self.autre = Company.objects.create(nom='VCAD Concurrent',
                                            slug='vcad-b')
        self.commercial = make_user(self.company, 'vcad-commercial', TERRAIN)
        self.bureau = make_user(self.company, 'vcad-bureau', BUREAU)
        self.etranger = make_user(self.autre, 'vcad-etranger', BUREAU)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            ville='Bouskoura')
        self.lead_autre = Lead.objects.create(
            company=self.autre, nom='Client concurrent', ville='Rabat')
        self.api = auth(self.commercial)


class PlanifierVisiteTests(VisiteCadenceBase):
    """Le service que le CRM appelle depuis la fiche lead."""

    def test_cree_la_visite_notifie_et_publie_levenement(self):
        recus = []
        from core.events import visite_planifiee

        def espion(sender, **kwargs):
            recus.append(kwargs)

        visite_planifiee.connect(espion, dispatch_uid='vcad-espion-planif')
        try:
            with frozen(MAINTENANT):
                visite, erreurs = services.planifier_visite(
                    self.lead, self.bureau,
                    AUJOURDHUI + datetime.timedelta(days=2),
                    commercial=self.commercial, notes='Portail bleu')
        finally:
            visite_planifiee.disconnect(dispatch_uid='vcad-espion-planif')

        self.assertEqual(erreurs, {})
        self.assertEqual(visite.statut, VisiteTerrain.Statut.BROUILLON)
        # La société vient du LEAD, jamais d'un corps de requête.
        self.assertEqual(visite.company_id, self.company.id)
        self.assertEqual(visite.commercial_id, self.commercial.id)
        self.assertEqual(visite.notes, 'Portail bleu')

        self.assertEqual(len(recus), 1, recus)
        charge = recus[0]
        self.assertEqual(charge['lead_id'], self.lead.id)
        self.assertEqual(charge['date_prevue'],
                         AUJOURDHUI + datetime.timedelta(days=2))
        self.assertEqual(charge['user'], self.bureau)
        self.assertIn('vcad-commercial', charge['commercial_nom'])

        # VTA7 — l'assigné apprend que sa journée a changé.
        notification = Notification.objects.get(
            recipient=self.commercial,
            event_type=EventType.VISITE_TERRAIN_ASSIGNEE)
        self.assertEqual(notification.link, f'/visites/{visite.pk}')

    def test_refuse_une_date_passee_en_nommant_le_champ(self):
        with frozen(MAINTENANT):
            visite, erreurs = services.planifier_visite(
                self.lead, self.bureau,
                AUJOURDHUI - datetime.timedelta(days=1))
        self.assertIsNone(visite)
        self.assertIn('date_prevue', erreurs)
        self.assertIn('passé', erreurs['date_prevue'][0])
        # Refus AVANT écriture : rien n'a été créé.
        self.assertEqual(VisiteTerrain.objects.count(), 0)

    def test_accepte_aujourdhui(self):
        """On planifie souvent le matin pour l'après-midi."""
        with frozen(MAINTENANT):
            visite, erreurs = services.planifier_visite(
                self.lead, self.bureau, AUJOURDHUI)
        self.assertEqual(erreurs, {})
        self.assertEqual(visite.date_prevue, AUJOURDHUI)

    def test_refuse_une_date_absente_en_nommant_le_champ(self):
        with frozen(MAINTENANT):
            visite, erreurs = services.planifier_visite(
                self.lead, self.bureau, None)
        self.assertIsNone(visite)
        self.assertIn('date_prevue', erreurs)

    def test_refuse_un_commercial_dune_autre_societe(self):
        with frozen(MAINTENANT):
            visite, erreurs = services.planifier_visite(
                self.lead, self.bureau,
                AUJOURDHUI + datetime.timedelta(days=1),
                commercial=self.etranger)
        self.assertIsNone(visite)
        self.assertIn('commercial', erreurs)
        self.assertEqual(VisiteTerrain.objects.count(), 0)

    def test_refuse_un_commercial_desactive(self):
        dormant = make_user(self.company, 'vcad-dormant', TERRAIN)
        dormant.is_active = False
        dormant.save(update_fields=['is_active'])
        with frozen(MAINTENANT):
            visite, erreurs = services.planifier_visite(
                self.lead, self.bureau,
                AUJOURDHUI + datetime.timedelta(days=1), commercial=dormant)
        self.assertIsNone(visite)
        self.assertIn('commercial', erreurs)


class RetourVisiteSelectorTests(VisiteCadenceBase):
    """``retour_visite`` — le TEXTE LIBRE, jamais des mesures."""

    def _visite(self):
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            commercial=self.commercial, notes='  Tableau saturé.  ')

    def _photo(self, visite, slot_code, commentaire):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Attachment

        content_type = ContentType.objects.get(app_label='crm', model='lead')
        attachment = Attachment.objects.create(
            company=self.company, content_type=content_type,
            object_id=self.lead.id, uploaded_by=self.commercial,
            filename=f'{slot_code}.png', file_key=f'k/{slot_code}',
            mime='image/png', size=64)
        return VisiteMedia.objects.create(
            company=self.company, visite=visite, attachment=attachment,
            slot_code=slot_code, commentaire=commentaire)

    def test_porte_les_notes_et_les_commentaires_de_photos(self):
        visite = self._visite()
        self._photo(visite, 'toiture_vue_generale', 'Tuiles fragiles')
        self._photo(visite, 'tableau_ouvert', '   ')  # vide → ignoré
        retour = selectors.retour_visite(visite)
        self.assertEqual(retour['notes'], 'Tableau saturé.')
        self.assertEqual(retour['nb_photos'], 2)
        self.assertEqual(len(retour['commentaires_photos']), 1)
        ligne = retour['commentaires_photos'][0]
        self.assertEqual(ligne['commentaire'], 'Tuiles fragiles')
        # Le LIBELLÉ du slot, pas son code : la phrase part au chatter.
        self.assertNotEqual(ligne['slot'], 'toiture_vue_generale')
        self.assertTrue(ligne['slot'])

    def test_un_retour_muet_sort_vide_sans_rien_inventer(self):
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead)
        retour = selectors.retour_visite(visite)
        self.assertEqual(retour, {'notes': '', 'commentaires_photos': [],
                                  'nb_photos': 0})

    def test_slot_inconnu_garde_son_code_plutot_que_de_disparaitre(self):
        visite = self._visite()
        self._photo(visite, 'slot_dune_autre_version', 'Vu de la rue')
        retour = selectors.retour_visite(visite)
        self.assertEqual(retour['commentaires_photos'],
                         [{'slot': 'slot_dune_autre_version',
                           'commentaire': 'Vu de la rue'}])


class VisitesPourLeadTests(VisiteCadenceBase):
    """La porte de lecture du CRM (frontière M3)."""

    def test_forme_du_contrat_et_ordre_du_plus_recent(self):
        ancienne = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            commercial=self.commercial,
            date_prevue=AUJOURDHUI - datetime.timedelta(days=10),
            statut=VisiteTerrain.Statut.TERMINEE,
            date_realisee=timezone.now(), notes='Retour terrain')
        recente = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            date_prevue=AUJOURDHUI + datetime.timedelta(days=3))

        lignes = selectors.visites_pour_lead(self.lead)
        self.assertEqual([ligne['id'] for ligne in lignes],
                         [recente.id, ancienne.id])
        self.assertEqual(
            sorted(lignes[0]),
            ['commercial_nom', 'date_prevue', 'date_realisee', 'id', 'notes',
             'retour_disponible', 'statut', 'statut_libelle'])
        # Visite non assignée → nom VIDE, jamais un « — » inventé.
        self.assertEqual(lignes[0]['commercial_nom'], '')
        self.assertIs(lignes[0]['retour_disponible'], False)
        self.assertIs(lignes[1]['retour_disponible'], True)
        self.assertEqual(lignes[1]['statut_libelle'], 'Terminée')

    def test_bornee_par_la_societe_du_lead(self):
        VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead_autre,
            date_prevue=AUJOURDHUI)
        self.assertEqual(selectors.visites_pour_lead(self.lead), [])
        self.assertEqual(
            len(selectors.visites_pour_lead(self.lead_autre)), 1)

    def test_lead_absent_rend_une_liste_vide(self):
        self.assertEqual(selectors.visites_pour_lead(None), [])


class TerminerPublieLeRetourTests(VisiteCadenceBase):
    """``terminer`` — l'événement ET la notification qui manquaient."""

    def _visite_complete(self):
        reponse = self.api.post('/api/django/visites/visites/',
                                {'lead': self.lead.id}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        visite_id = reponse.data['id']
        for slot, combien in SLOTS_REQUIS:
            for index in range(combien):
                upload = SimpleUploadedFile(f'{slot}-{index}.png', PNG,
                                            content_type='image/png')
                corps = {'slot_code': slot, 'fichier': upload}
                if (slot, index) == ('tableau_ouvert', 0):
                    corps['commentaire'] = 'Disjoncteur au plafond'
                reponse = self.api.post(
                    f'/api/django/visites/visites/{visite_id}/photos/',
                    corps, format='multipart')
                self.assertEqual(reponse.status_code, 200, reponse.data)
        for categorie, valeurs in MESURES_COMPLETES.items():
            reponse = self.api.patch(
                f'/api/django/visites/visites/{visite_id}/mesures/',
                {'categorie': categorie, 'valeurs': valeurs}, format='json')
            self.assertEqual(reponse.status_code, 200, reponse.data)
        visite = VisiteTerrain.objects.get(pk=visite_id)
        visite.notes = 'Le client veut aussi une borne de recharge.'
        visite.save(update_fields=['notes'])
        return visite_id

    def test_terminer_publie_visite_terminee_avec_le_retour(self):
        visite_id = self._visite_complete()
        recus = []
        from core.events import visite_terminee

        def espion(sender, **kwargs):
            recus.append(kwargs)

        visite_terminee.connect(espion, dispatch_uid='vcad-espion-fin')
        try:
            reponse = self.api.post(
                f'/api/django/visites/visites/{visite_id}/terminer/', {},
                format='json')
        finally:
            visite_terminee.disconnect(dispatch_uid='vcad-espion-fin')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(len(recus), 1, recus)
        retour = recus[0]['retour']
        self.assertEqual(retour['notes'],
                         'Le client veut aussi une borne de recharge.')
        self.assertEqual(recus[0]['lead_id'], self.lead.id)
        commentaires = [ligne['commentaire']
                        for ligne in retour['commentaires_photos']]
        self.assertEqual(commentaires, ['Disjoncteur au plafond'])
        # Sans qualification saisie, la clé voyage à ``None`` — jamais un
        # dict de défauts qui ferait croire à une qualification faite.
        self.assertIn('qualification', recus[0])
        self.assertIsNone(recus[0]['qualification'])

    def test_terminer_est_idempotent_jamais_une_seconde_emission(self):
        # Revue Fable (15/09) — un double clic ou un retry réseau re-POSTait
        # terminer/ : deuxième note chatter, deuxième salve de notifications,
        # débrief ré-avancé. Désormais : une visite DÉJÀ terminée renvoie
        # l'agrégat tel quel, sans rien ré-émettre ni ré-horodater.
        visite_id = self._visite_complete()
        premiere = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(premiere.status_code, 200, premiere.data)
        date_realisee = VisiteTerrain.objects.get(pk=visite_id).date_realisee

        recus = []
        from core.events import visite_terminee

        def espion(sender, **kwargs):
            recus.append(kwargs)

        visite_terminee.connect(espion, dispatch_uid='vcad-espion-idem')
        try:
            seconde = self.api.post(
                f'/api/django/visites/visites/{visite_id}/terminer/', {},
                format='json')
        finally:
            visite_terminee.disconnect(dispatch_uid='vcad-espion-idem')

        self.assertEqual(seconde.status_code, 200, seconde.data)
        self.assertEqual(recus, [])
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.statut, VisiteTerrain.Statut.TERMINEE)
        self.assertEqual(visite.date_realisee, date_realisee)

    def test_terminer_emporte_la_qualification_quand_elle_existe(self):
        visite_id = self._visite_complete()
        reponse = self.api.post(
            f'/api/django/visites/visites/{visite_id}/qualification/',
            dict(QUALIFICATION_VALIDE, rappel='cette_semaine'),
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

        recus = []
        from core.events import visite_terminee

        def espion(sender, **kwargs):
            recus.append(kwargs)

        visite_terminee.connect(espion, dispatch_uid='vcad-espion-qualif')
        try:
            reponse = self.api.post(
                f'/api/django/visites/visites/{visite_id}/terminer/', {},
                format='json')
        finally:
            visite_terminee.disconnect(dispatch_uid='vcad-espion-qualif')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(recus[0]['qualification']['rappel'],
                         'cette_semaine')

    def test_terminer_nest_pas_bloque_par_labsence_de_qualification(self):
        visite_id = self._visite_complete()
        reponse = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'], 'terminee')

    def test_terminer_previent_ceux_qui_peuvent_valider(self):
        visite_id = self._visite_complete()
        reponse = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        notification = Notification.objects.get(
            recipient=self.bureau,
            event_type=EventType.VISITE_TERRAIN_A_VALIDER)
        self.assertEqual(notification.link, f'/visites/{visite_id}')
        self.assertEqual(notification.company_id, self.company.id)
        # Ni l'acteur (il vient de la terminer), ni l'autre société.
        self.assertFalse(Notification.objects.filter(
            recipient=self.commercial,
            event_type=EventType.VISITE_TERRAIN_A_VALIDER).exists())
        self.assertFalse(Notification.objects.filter(
            recipient=self.etranger,
            event_type=EventType.VISITE_TERRAIN_A_VALIDER).exists())

    def test_un_role_sans_le_code_nest_pas_notifie(self):
        sans_droit = make_user(self.company, 'vcad-sansdroit', TERRAIN)
        visite_id = self._visite_complete()
        self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/',
                      {}, format='json')
        self.assertFalse(Notification.objects.filter(
            recipient=sans_droit,
            event_type=EventType.VISITE_TERRAIN_A_VALIDER).exists())


QUALIFICATION_VALIDE = {
    'temperature': 'chaud',
    'devis': 'convient',
    'decideur': 'seul',
    'frein': 'aucun',
    'declencheur': 'economies',
    'rappel': 'demain_matin',
}


class QualificationVocabulaireTests(TestCase):
    """Le vocabulaire FERMÉ, isolé — aucune base n'est nécessaire."""

    def test_accepte_une_saisie_complete(self):
        propre, erreurs = qualification.valider(dict(QUALIFICATION_VALIDE))
        self.assertEqual(erreurs, {})
        self.assertEqual(propre['temperature'], 'chaud')
        # Les champs libres absents sortent VIDES, jamais ``None``.
        self.assertEqual(propre['devis_details'], '')
        self.assertEqual(propre['conseil_closing'], '')

    def test_refuse_une_valeur_inconnue_en_nommant_le_champ(self):
        saisie = dict(QUALIFICATION_VALIDE, temperature='bouillant')
        propre, erreurs = qualification.valider(saisie)
        self.assertIsNone(propre)
        self.assertEqual(list(erreurs), ['temperature'])
        self.assertIn('bouillant', erreurs['temperature'][0])

    def test_refuse_un_champ_obligatoire_manquant(self):
        saisie = dict(QUALIFICATION_VALIDE)
        del saisie['decideur']
        propre, erreurs = qualification.valider(saisie)
        self.assertIsNone(propre)
        self.assertIn('decideur', erreurs)

    def test_refuse_un_champ_inconnu_plutot_que_de_lignorer(self):
        saisie = dict(QUALIFICATION_VALIDE, budget='50000')
        propre, erreurs = qualification.valider(saisie)
        self.assertIsNone(propre)
        self.assertIn('budget', erreurs)

    def test_exige_le_detail_quand_le_devis_est_a_reprendre(self):
        for valeur in ('a_modifier', 'nouveau'):
            saisie = dict(QUALIFICATION_VALIDE, devis=valeur)
            propre, erreurs = qualification.valider(saisie)
            self.assertIsNone(propre, valeur)
            self.assertIn('devis_details', erreurs)

    def test_accepte_le_detail_quand_il_est_fourni(self):
        saisie = dict(QUALIFICATION_VALIDE, devis='a_modifier',
                      devis_details='Ajouter une batterie 5 kWh.')
        propre, erreurs = qualification.valider(saisie)
        self.assertEqual(erreurs, {})
        self.assertEqual(propre['devis_details'],
                         'Ajouter une batterie 5 kWh.')

    def test_borne_les_champs_libres(self):
        saisie = dict(QUALIFICATION_VALIDE,
                      conseil_closing='x' * (qualification.MAX_CONSEIL + 1))
        propre, erreurs = qualification.valider(saisie)
        self.assertIsNone(propre)
        self.assertIn('conseil_closing', erreurs)

    def test_refuse_autre_chose_quun_objet(self):
        propre, erreurs = qualification.valider('chaud')
        self.assertIsNone(propre)
        self.assertIn('qualification', erreurs)

    def test_la_phrase_suit_lordre_du_vocabulaire(self):
        phrase = qualification.phrase(dict(QUALIFICATION_VALIDE))
        self.assertEqual(
            phrase,
            'Qualification : Client chaud — prêt à signer · Le devis convient '
            '· Décide seul · Frein : aucun · L\'a accroché : les économies · '
            'Rappeler demain matin.')

    def test_la_phrase_insere_le_detail_du_devis(self):
        phrase = qualification.phrase(dict(
            QUALIFICATION_VALIDE, devis='a_modifier',
            devis_details='Ajouter une batterie'))
        self.assertIn('Devis à modifier : Ajouter une batterie', phrase)

    def test_une_qualification_absente_ne_rend_aucune_phrase(self):
        self.assertEqual(qualification.phrase(None), '')
        self.assertEqual(qualification.phrase({}), '')
        self.assertEqual(qualification.conseil(None), '')

    def test_le_moment_de_rappel_dicte_le_delai(self):
        self.assertEqual(qualification.jours_avant_rappel(
            dict(QUALIFICATION_VALIDE, rappel='demain_matin')), 1)
        self.assertEqual(qualification.jours_avant_rappel(
            dict(QUALIFICATION_VALIDE, rappel='demain_soir')), 1)
        self.assertEqual(qualification.jours_avant_rappel(
            dict(QUALIFICATION_VALIDE, rappel='cette_semaine')), 3)
        self.assertEqual(qualification.jours_avant_rappel(None), 1)

    def test_devis_a_reprendre(self):
        self.assertFalse(qualification.devis_a_reprendre(
            dict(QUALIFICATION_VALIDE)))
        self.assertTrue(qualification.devis_a_reprendre(
            dict(QUALIFICATION_VALIDE, devis='nouveau')))


class QualificationApiTests(VisiteCadenceBase):
    """L'action ``POST <pk>/qualification/`` — réservée à l'ASSIGNÉ."""

    def setUp(self):
        super().setUp()
        self.visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            commercial=self.commercial, date_prevue=AUJOURDHUI)
        self.url = (f'/api/django/visites/visites/{self.visite.pk}'
                    '/qualification/')

    def test_enregistre_et_rend_lagregat(self):
        reponse = self.api.post(self.url, dict(QUALIFICATION_VALIDE),
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['qualification']['temperature'],
                         'chaud')
        self.visite.refresh_from_db()
        self.assertEqual(self.visite.qualification['declencheur'],
                         'economies')

    def test_lagregat_porte_null_tant_que_rien_nest_saisi(self):
        reponse = self.api.get(
            f'/api/django/visites/visites/{self.visite.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn('qualification', reponse.data)
        self.assertIsNone(reponse.data['qualification'])

    def test_refus_par_champ(self):
        reponse = self.api.post(
            self.url, dict(QUALIFICATION_VALIDE, frein='cher'),
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('frein', reponse.data['erreurs'])
        self.visite.refresh_from_db()
        self.assertIsNone(self.visite.qualification)

    def test_reservee_a_lassigne(self):
        reponse = auth(self.bureau).post(
            self.url, dict(QUALIFICATION_VALIDE), format='json')
        self.assertEqual(reponse.status_code, 403, reponse.data)
        self.visite.refresh_from_db()
        self.assertIsNone(self.visite.qualification)

    def test_refusee_sur_une_visite_validee(self):
        self.visite.statut = VisiteTerrain.Statut.VALIDEE
        self.visite.save(update_fields=['statut'])
        reponse = self.api.post(self.url, dict(QUALIFICATION_VALIDE),
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('statut', reponse.data['erreurs'])

    def test_isolation_societe(self):
        etrangere = VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead_autre,
            commercial=self.etranger)
        reponse = self.api.post(
            f'/api/django/visites/visites/{etrangere.pk}/qualification/',
            dict(QUALIFICATION_VALIDE), format='json')
        self.assertEqual(reponse.status_code, 404)


class EvenementsEtEventTypesTests(TestCase):
    """Gardes YEVNT7/NTPLT12 — aucun orphelin silencieux sur le bus."""

    def test_les_deux_evenements_sont_catalogues(self):
        from core import event_coverage

        orphelins = event_coverage.uncatalogued_events()
        self.assertNotIn('visite_planifiee', orphelins)
        self.assertNotIn('visite_terminee', orphelins)

    def test_les_deux_evenements_ont_un_abonne(self):
        from core import event_coverage

        orphelins = event_coverage.orphan_signals()
        self.assertNotIn('visite_planifiee', orphelins)
        self.assertNotIn('visite_terminee', orphelins)

    def test_les_deux_eventtypes_ont_un_producteur(self):
        from core import event_coverage

        sans_producteur = event_coverage.unproduced_eventtypes()
        self.assertNotIn('VISITE_RETOUR_TERRAIN', sans_producteur)
        self.assertNotIn('VISITE_TERRAIN_A_VALIDER', sans_producteur)

    def test_les_cles_sont_distinctes(self):
        self.assertEqual(EventType.VISITE_RETOUR_TERRAIN,
                         'visite_retour_terrain')
        self.assertEqual(EventType.VISITE_TERRAIN_A_VALIDER,
                         'visite_terrain_a_valider')
        self.assertNotEqual(EventType.VISITE_TERRAIN_A_VALIDER,
                            EventType.VISITE_TERRAIN_VALIDEE)
