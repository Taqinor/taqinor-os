"""CAD54 — réattribuer un lead : ce que deviennent ses touches ouvertes.

Le round 2 a tranché la moitié technique : elle est SAINE. ``RelanceEtape``
n'a AUCUN champ responsable, donc les touches suivent le lead ; le digest du
matin vise les owners ; le prénom du conseiller est recalculé à chaque rendu ;
le changement est déjà journalisé. Ces tests VERROUILLENT ces quatre faits
plutôt que de les supposer — c'est ce qu'aucune lane n'avait déroulé.

Ce qui manquait est côté CLIENT et côté NOUVEAU responsable, et c'est ce que
CAD54 ajoute :

  * une touche de PASSATION portant le gabarit ``passation``, sur un lead
    DÉJÀ contacté — le prospect ne voit plus changer de prénom sans un mot ;
  * une notification au nouveau responsable qui LISTE ce qu'il hérite, au
    lieu du seul « Nouveau lead assigné ».

Garde-fous vérifiés : aucun prénom codé en dur (le gabarit porte des
variables), aucune valeur d'énumération serveur ajoutée (``template_cle`` est
du texte libre, l'événement est ``lead_assigned`` qui existe déjà), aucune
touche du protocole ajoutée, retirée ni réordonnée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.cadence_reperes import PASSATION_LIBELLE
from apps.crm.cadence_reponses import PASSATION_TEMPLATE_CLE, reattribuer_lead
from apps.crm.leads_socle import lead_notification_recipients
from apps.crm.cadence_selectors import relance_etapes_dues
from apps.crm.fiche_bulk import apply_bulk_action
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()

#: Mardi 22 septembre 2026, 10 h à Casablanca.
MARDI = datetime.datetime(2026, 9, 22, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad54'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD54 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.ancien = User.objects.create_user(
            username=f'{self.slug}-ancien', password='x',
            role_legacy='commercial', company=self.company)
        self.nouveau = User.objects.create_user(
            username=f'{self.slug}-nouveau', password='x',
            role_legacy='commercial', company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, *, contacte=True, stage=stages.CONTACTED):
        return Lead.objects.create(
            company=self.company, nom='Aziz', stage=stage,
            owner=self.ancien, telephone='+212661005401',
            first_contacted_at=MARDI if contacte else None)

    def _touche(self, lead, *, jours=1, libelle='Appel de suivi', ordre=2):
        quand = MARDI + datetime.timedelta(days=jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=ordre,
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            canal=RelanceEtape.Canal.APPEL, libelle=libelle,
            cadence_depart=MARDI)


class LesTouchesSuiventLeLeadTests(_Base):
    """La moitié SAINE, verrouillée : rien ne porte l'ancien responsable."""

    slug = 'cad54-suivent'

    def test_la_touche_ouverte_pointe_le_nouveau_responsable(self):
        lead = self._lead()
        touche = self._touche(lead)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        touche.refresh_from_db()
        # `RelanceEtape` n'a pas de champ responsable : la touche suit le lead.
        self.assertFalse(hasattr(touche, 'responsable'))
        self.assertEqual(touche.lead.owner_id, self.nouveau.pk)

    def test_les_notifications_ne_visent_plus_l_ancien(self):
        lead = self._lead()
        self._touche(lead)
        avant = {u.pk for u in lead_notification_recipients(lead)}
        self.assertIn(self.ancien.pk, avant)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        lead.refresh_from_db()
        apres = {u.pk for u in lead_notification_recipients(lead)}
        self.assertIn(self.nouveau.pk, apres)
        self.assertNotIn(self.ancien.pk, apres)

    def test_la_touche_n_est_ni_deplacee_ni_dupliquee(self):
        lead = self._lead()
        touche = self._touche(lead)
        echeance = touche.due_at
        reattribuer_lead(lead, self.acteur, self.nouveau)
        touche.refresh_from_db()
        self.assertEqual(touche.due_at, echeance)
        self.assertEqual(
            lead.relance_etapes.filter(cadence='contact').count(), 1)


class TouchePassationTests(_Base):
    slug = 'cad54-passation'

    def test_un_lead_deja_contacte_recoit_la_touche_de_passation(self):
        lead = self._lead()
        etape = reattribuer_lead(lead, self.acteur, self.nouveau)
        self.assertIsNotNone(etape)
        self.assertEqual(etape.libelle, PASSATION_LIBELLE)
        self.assertEqual(etape.template_cle, PASSATION_TEMPLATE_CLE)
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_un_patch_owner_pose_la_passation(self):
        """ACVI31 — PATCH ``owner`` et lot ``reassign`` : même état."""
        from rest_framework.test import APIClient

        lead = self._lead()
        api = APIClient()
        api.force_authenticate(self.acteur)
        reponse = api.patch(f'/api/django/crm/leads/{lead.pk}/',
                            {'owner': self.nouveau.pk}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(RelanceEtape.objects.filter(
            lead=lead, libelle=PASSATION_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE).count(), 1)

    def test_aucun_prenom_n_est_ecrit_dans_la_touche(self):
        lead = self._lead()
        etape = reattribuer_lead(lead, self.acteur, self.nouveau)
        # Le prénom du conseiller vit dans le GABARIT, en variable — jamais
        # figé dans une ligne (règle fondateur du 08/09/2026).
        for texte in (etape.libelle or '', etape.note or ''):
            self.assertNotIn(self.ancien.username, texte)
            self.assertNotIn(self.nouveau.username, texte)

    def test_un_lead_jamais_contacte_ne_recoit_rien(self):
        lead = self._lead(contacte=False, stage=stages.NEW)
        self.assertIsNone(reattribuer_lead(lead, self.acteur, self.nouveau))
        self.assertEqual(
            lead.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 0)

    def test_deux_reattributions_ne_posent_pas_deux_passations(self):
        lead = self._lead()
        troisieme = User.objects.create_user(
            username=f'{self.slug}-troisieme', password='x',
            role_legacy='commercial', company=self.company)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        reattribuer_lead(lead, self.acteur, troisieme)
        self.assertEqual(
            lead.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 1)

    def test_un_lead_signe_ne_recoit_pas_de_passation(self):
        lead = self._lead(stage=stages.SIGNED)
        self.assertIsNone(reattribuer_lead(lead, self.acteur, self.nouveau))

    def test_une_reattribution_a_soi_meme_est_un_no_op(self):
        lead = self._lead()
        self.assertIsNone(reattribuer_lead(lead, self.acteur, self.ancien))
        self.assertEqual(lead.relance_etapes.count(), 0)


class NotificationDesTouchesHeriteesTests(_Base):
    slug = 'cad54-notif'

    def _notifs(self, user):
        from apps.notifications.models import Notification
        return list(Notification.objects.filter(recipient=user))

    def test_le_nouveau_responsable_apprend_ce_qu_il_herite(self):
        lead = self._lead()
        self._touche(lead)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        corps = ' '.join(n.body or '' for n in self._notifs(self.nouveau))
        self.assertIn('relance(s) déjà programmée(s)', corps)
        self.assertIn('Appel de suivi', corps)

    def test_sans_touche_ouverte_aucune_notification_de_plus(self):
        lead = self._lead()
        reattribuer_lead(lead, self.acteur, self.nouveau)
        titres = [n.title for n in self._notifs(self.nouveau)]
        self.assertNotIn('Dossier repris — relances héritées', titres)


class ReattributionEnMasseTests(_Base):
    """Le chemin en MASSE passe par le même geste."""

    slug = 'cad54-masse'

    def test_l_action_en_masse_pose_la_passation(self):
        lead = self._lead()
        self._touche(lead)
        res = apply_bulk_action(
            company=self.company, user=self.acteur, lead_ids=[lead.id],
            op='reassign', params={'owner': self.nouveau.pk})
        self.assertEqual(res['updated'], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.nouveau.pk)
        self.assertEqual(
            lead.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 1)

    def test_le_changement_reste_journalise(self):
        lead = self._lead()
        apply_bulk_action(
            company=self.company, user=self.acteur, lead_ids=[lead.id],
            op='reassign', params={'owner': self.nouveau.pk})
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead).exists())


class DelegationDesDossiersTests(_Base):
    """17/11/2026 — « Déléguer mes dossiers » : ``POST/GET leads/deleguer/``."""

    slug = 'cad54-deleguer'
    URL = '/api/django/crm/leads/deleguer/'

    def setUp(self):
        super().setUp()
        role = Role.objects.create(
            company=self.company, nom='Commercial délégant',
            permissions=list(COMMERCIAL_PERMISSIONS) + ['crm_reassign'])
        self.moi = User.objects.create_user(
            username=f'{self.slug}-moi', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.force_authenticate(self.moi)
        self._n = 0

    def _mien(self, nom='Mien', **extra):
        self._n += 1
        return Lead.objects.create(
            company=self.company, nom=nom, owner=self.moi,
            stage=extra.pop('stage', stages.CONTACTED),
            telephone=f'+21266100{5400 + self._n}',
            first_contacted_at=MARDI, **extra)

    def _jeu(self):
        """Un lead suivi (une touche en retard, une à venir), un Froid sans
        touche, puis ceux qui NE partent PAS (perdu, archivé, opposé, signé,
        supprimé) et celui d'un collègue."""
        suivi = self._mien('Suivi')
        self._touche(suivi, jours=-3)
        self._touche(suivi, jours=2, libelle='Appel plus tard', ordre=3)
        froid = self._mien('Froid', stage=stages.COLD)
        restent = [
            self._mien('Perdu', perdu=True),
            self._mien('Archive', is_archived=True),
            self._mien('Oppose', ne_plus_contacter=True),
            self._mien('Signe', stage=stages.SIGNED),
        ]
        supprime = self._mien('Supprime')
        Lead.all_objects.filter(pk=supprime.pk).update(is_deleted=True)
        restent.append(supprime)
        autre = Lead.objects.create(
            company=self.company, nom='Du collègue', owner=self.ancien,
            stage=stages.CONTACTED)
        return suivi, froid, restent, autre

    def test_apercu_puis_ecriture_donnent_les_memes_chiffres(self):
        suivi, froid, restent, autre = self._jeu()
        apercu = self.api.get(self.URL, {'vers': self.nouveau.pk})
        self.assertEqual(apercu.status_code, 200, apercu.content)
        self.assertEqual(apercu.data['dossiers'], 2)  # suivi + froid
        self.assertEqual(apercu.data['etapes_ouvertes'], 2)
        self.assertEqual(apercu.data['etapes_en_retard'], 1)
        res = self.api.post(self.URL, {'vers': self.nouveau.pk}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        for cle in ('dossiers', 'etapes_ouvertes', 'etapes_en_retard'):
            self.assertEqual(res.data[cle], apercu.data[cle], cle)
        self.assertEqual(res.data['confies'], 2)
        for lead in (suivi, froid):
            lead.refresh_from_db()
            self.assertEqual(lead.owner_id, self.nouveau.pk)
        for lead in restent:
            lead_bd = Lead.all_objects.get(pk=lead.pk)
            self.assertEqual(lead_bd.owner_id, self.moi.pk, lead.nom)
        autre.refresh_from_db()
        self.assertEqual(autre.owner_id, self.ancien.pk)

    def test_les_touches_deviennent_visibles_pour_la_cible(self):
        suivi, _froid, _restent, _autre = self._jeu()
        ouvertes = set(suivi.relance_etapes.values_list('id', flat=True))
        self.assertTrue(ouvertes)

        def vues(utilisateur):
            return {e.id for e in relance_etapes_dues(
                self.company, utilisateur, scope='all')}

        self.assertFalse(ouvertes & vues(self.nouveau))
        self.api.post(self.URL, {'vers': self.nouveau.pk}, format='json')
        self.assertTrue(ouvertes <= vues(self.nouveau))
        self.assertFalse(ouvertes & vues(self.moi))

    def test_passation_posee_par_defaut_sautee_sans_prevenir(self):
        suivi, _f, _r, _a = self._jeu()
        self.api.post(self.URL, {'vers': self.nouveau.pk}, format='json')
        self.assertEqual(
            suivi.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 1)
        sans_prevenir = self._mien('Sans prevenir')
        res = self.api.post(
            self.URL, {'vers': self.ancien.pk, 'prevenir_clients': False},
            format='json')
        self.assertEqual(res.status_code, 200, res.content)
        sans_prevenir.refresh_from_db()
        self.assertEqual(sans_prevenir.owner_id, self.ancien.pk)
        self.assertFalse(sans_prevenir.relance_etapes.filter(
            libelle=PASSATION_LIBELLE).exists())
        self.assertEqual(res.data['passations_posees'], 0)

    def test_chatter_en_masse_de_la_reattribution(self):
        suivi, _f, _r, _a = self._jeu()
        self.api.post(self.URL, {'vers': self.nouveau.pk}, format='json')
        self.assertTrue(LeadActivity.objects.filter(
            lead=suivi, field='owner', bulk=True).exists())

    def test_cible_autre_societe_desactivee_ou_identique_refusee(self):
        self._jeu()
        autre = Company.objects.create(nom='Autre', slug=f'{self.slug}-autre')
        etranger = User.objects.create_user(
            username=f'{self.slug}-etranger', password='x', company=autre,
            role_legacy='commercial')
        res = self.api.post(self.URL, {'vers': etranger.pk}, format='json')
        self.assertEqual(res.status_code, 404)
        self.assertIn('vers', res.data)
        self.nouveau.is_active = False
        self.nouveau.save(update_fields=['is_active'])
        res = self.api.post(self.URL, {'vers': self.nouveau.pk}, format='json')
        self.assertEqual(res.status_code, 409)
        self.assertIn('désactivé', res.data['vers'][0])
        res = self.api.post(self.URL, {'vers': self.moi.pk}, format='json')
        self.assertEqual(res.status_code, 409)
        self.assertIn('vers', res.data)
        self.assertFalse(Lead.objects.filter(
            owner__in=[etranger, self.nouveau]).exists())

    def test_les_leads_d_une_autre_societe_ne_bougent_pas(self):
        autre = Company.objects.create(nom='Autre2', slug=f'{self.slug}-a2')
        etranger = User.objects.create_user(
            username=f'{self.slug}-e2', password='x', company=autre,
            role_legacy='commercial')
        lead_etranger = Lead.objects.create(
            company=autre, nom='Etranger', owner=etranger,
            stage=stages.CONTACTED)
        self._jeu()
        res = self.api.post(
            self.URL, {'vers': self.nouveau.pk, 'de': etranger.pk},
            format='json')
        self.assertEqual(res.status_code, 404)
        lead_etranger.refresh_from_db()
        self.assertEqual(lead_etranger.owner_id, etranger.pk)

    def test_sans_crm_reassign_403(self):
        self._jeu()
        prive = User.objects.create_user(
            username=f'{self.slug}-prive', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Commercial simple',
                permissions=list(COMMERCIAL_PERMISSIONS)))
        api = APIClient()
        api.force_authenticate(prive)
        res = api.get(self.URL, {'vers': self.nouveau.pk})
        self.assertEqual(res.status_code, 403, res.content)
        res = api.post(self.URL, {'vers': self.nouveau.pk}, format='json')
        self.assertEqual(res.status_code, 403, res.content)
        self.assertFalse(Lead.objects.filter(owner=self.nouveau).exists())

    def test_dossiers_d_un_collegue_hors_portee_403_puis_admin_200(self):
        Lead.objects.create(
            company=self.company, nom='Du collègue', owner=self.ancien,
            stage=stages.CONTACTED)
        res = self.api.post(
            self.URL, {'vers': self.nouveau.pk, 'de': self.ancien.pk},
            format='json')
        self.assertEqual(res.status_code, 403, res.content)
        self.assertIn('de', res.data)
        admin = User.objects.create_user(
            username=f'{self.slug}-admin', password='x', company=self.company,
            role_legacy='admin')
        api = APIClient()
        api.force_authenticate(admin)
        res = api.post(
            self.URL, {'vers': self.nouveau.pk, 'de': self.ancien.pk},
            format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['confies'], 1)
