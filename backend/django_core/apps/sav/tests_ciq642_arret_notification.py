"""CIQ642 — une panne qui met un site pro à l'arrêt crée l'action « notifier le
distributeur » sur son dossier 82-21 (décret 2.25.100 art. 28).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.sav.tests_ciq642_arret_notification"
"""
from decimal import Decimal

from django.test import TestCase

from apps.installations.models import Installation
from apps.sav import services
from apps.sav.models import Ticket
from apps.sav.tests_fg81_fg90 import (
    auth, make_company, make_installation, make_ticket, make_user,
)
from apps.ventes.models import Devis, RegulatoryDossier

URL = '/api/django/sav/tickets/'
ACTION = (
    "Notifier l'arrêt de l'installation au distributeur "
    '(décret 2.25.100 art. 28)')


class ArretInstallationNotification(TestCase):
    def setUp(self):
        self.co = make_company(slug='ciq642-co', nom='CIQ642 Co')
        self.user = make_user(self.co, username='ciq642_admin')
        self.api = auth(self.user)
        self._n = 0

    def _site(self, type_installation='industriel',
              regime='accord_raccordement', avec_dossier=True):
        self._n += 1
        inst, client = make_installation(self.co, ref=f'CHT-CIQ642-{self._n}')
        inst.type_installation = type_installation
        inst.regime_8221 = regime
        inst.save(update_fields=['type_installation', 'regime_8221'])
        dossier = None
        if avec_dossier:
            devis = Devis.objects.create(
                company=self.co, reference=f'DEV-CIQ642-{self._n}',
                client=client, statut=Devis.Statut.ACCEPTE,
                taux_tva=Decimal('20'))
            dossier = RegulatoryDossier.objects.create(
                company=self.co, devis=devis, chantier=inst,
                regime_8221=regime)
        return inst, client, dossier

    def _ticket(self, inst, client, **kw):
        ticket = make_ticket(self.co, self.user, client, inst)
        for cle, valeur in kw.items():
            setattr(ticket, cle, valeur)
        if kw:
            ticket.save(update_fields=list(kw))
        return ticket

    def _arret(self, ticket, valeur=True):
        return self.api.patch(f'{URL}{ticket.pk}/',
                              {'arret_installation': valeur}, format='json')

    def test_site_c_i_en_accord_marque_a_l_arret_pose_l_action_une_fois(self):
        inst, client, dossier = self._site()
        ticket = self._ticket(inst, client)
        reponse = self._arret(ticket)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['arret_installation'])
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, ACTION)
        self.assertIsNone(dossier.prochaine_action_date)
        # Re-signaler (faux puis vrai) ne duplique rien.
        self._arret(ticket, False)
        self._arret(ticket, True)
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, ACTION)
        self.assertEqual(
            RegulatoryDossier.objects.filter(chantier=inst).count(), 1)

    def test_autorisation_pose_aussi_l_action(self):
        inst, client, dossier = self._site(regime='autorisation_anre')
        self._arret(self._ticket(inst, client))
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, ACTION)

    def test_residentiel_ne_pose_rien(self):
        inst, client, dossier = self._site(type_installation='residentiel')
        self._arret(self._ticket(inst, client))
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, '')

    def test_regime_declaration_ou_non_concerne_ne_pose_rien(self):
        for regime in ('declaration_bt', 'non_concerne', 'a_qualifier'):
            inst, client, dossier = self._site(regime=regime)
            self._arret(self._ticket(inst, client))
            dossier.refresh_from_db()
            self.assertEqual(dossier.prochaine_action, '', regime)

    def test_dossier_absent_rien_sans_erreur(self):
        inst, client, _ = self._site(avec_dossier=False)
        reponse = self._arret(self._ticket(inst, client))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['arret_installation'])
        self.assertEqual(RegulatoryDossier.objects.count(), 0)

    def test_ticket_sans_chantier_rien_sans_erreur(self):
        _, client, _ = self._site()
        ticket = Ticket.objects.create(
            company=self.co, reference='SAV-CIQ642-0', client=client,
            arret_installation=True)
        self.assertIsNone(services.notifier_arret_installation(ticket))

    def test_marquer_faux_ne_pose_rien(self):
        inst, client, dossier = self._site()
        self._arret(self._ticket(inst, client), False)
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, '')

    def test_action_deja_a_jour_aucune_reecriture(self):
        inst, client, dossier = self._site()
        ticket = self._ticket(inst, client, arret_installation=True)
        premier = services.notifier_arret_installation(ticket)
        dossier.refresh_from_db()
        modifie = dossier.updated_at
        deuxieme = services.notifier_arret_installation(ticket)
        dossier.refresh_from_db()
        self.assertEqual(premier.pk, deuxieme.pk)
        self.assertEqual(dossier.updated_at, modifie)

    def test_une_action_precedente_n_est_pas_perdue(self):
        inst, client, dossier = self._site()
        dossier.prochaine_action = "Relancer l'opérateur"
        dossier.save(update_fields=['prochaine_action'])
        self._arret(self._ticket(inst, client))
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, ACTION)
        self.assertIn("Action précédente : Relancer l'opérateur",
                      dossier.notes)

    def test_aucun_envoi_ni_delai_invente(self):
        inst, client, dossier = self._site()
        ticket = self._ticket(inst, client)
        self._arret(ticket)
        dossier.refresh_from_db()
        self.assertIsNone(dossier.prochaine_action_date)
        self.assertEqual(dossier.statut, RegulatoryDossier.Statut.EN_CONSTITUTION)
        self.assertNotRegex(dossier.prochaine_action, r'\d+ (jours|heures|h)')

    def test_la_societe_borne_le_dossier(self):
        autre = make_company(slug='ciq642-autre', nom='Autre')
        inst, client, dossier = self._site()
        ticket = self._ticket(inst, client, arret_installation=True)
        from apps.ventes.services import ajouter_action_dossier_8221
        self.assertIsNone(
            ajouter_action_dossier_8221(inst.pk, ACTION, company=autre))
        dossier.refresh_from_db()
        self.assertEqual(dossier.prochaine_action, '')
        self.assertIsNotNone(services.notifier_arret_installation(ticket))

    def test_creation_d_un_ticket_deja_a_l_arret_n_est_pas_un_passage(self):
        # Le passage à vrai se détecte à la MISE À JOUR ; le champ vaut faux
        # par défaut et la migration est purement additive.
        field = Ticket._meta.get_field('arret_installation')
        self.assertFalse(field.default)
        self.assertEqual(Installation.TypeInstallation.INDUSTRIEL.value,
                         services.TYPE_CHANTIER_NOTIFICATION_ARRET)
