"""NTGRC7 — dossier de notification CNDP d'une violation de données.

Garanties : les 8 rubriques réglementaires sont présentes dans l'ordre, le
dossier porte son horodatage de génération, le rendu passe par
``core.pdf.render_pdf`` (jamais le moteur de devis — règle #4) et l'action
journalise l'événement en ``audit.AuditLog``.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.grc.services import (
    RUBRIQUES_NOTIFICATION, contexte_dossier_notification, creer_violation,
    generer_dossier_notification,
)
from authentication.models import Company
from testkit.base import TenantAPITestCase


class ContenuDuDossierTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC7 SA', slug='ntgrc7')
        cls.violation = creer_violation(
            cls.company,
            date_detection=timezone.now(),
            date_incident=timezone.now() - timezone.timedelta(days=2),
            categories_donnees=['identite', 'contact'],
            nombre_personnes_estime=340,
            risque_personnes='Usurpation d\'identité possible.',
            mesures_prises='Mots de passe réinitialisés, accès révoqués.')

    def test_les_huit_rubriques_sont_presentes_dans_lordre(self):
        contexte = contexte_dossier_notification(self.violation)
        titres = [r['titre'] for r in contexte['rubriques']]
        self.assertEqual(titres, list(RUBRIQUES_NOTIFICATION))
        self.assertEqual(len(titres), 8)

    def test_le_dossier_porte_son_horodatage_de_generation(self):
        instant = timezone.now()
        contexte = contexte_dossier_notification(self.violation, now=instant)
        self.assertEqual(contexte['genere_le'], instant)
        self.assertEqual(contexte['reference'], self.violation.reference)

    def test_les_donnees_saisies_apparaissent_dans_les_rubriques(self):
        contexte = contexte_dossier_notification(self.violation)
        par_titre = {r['titre']: r['contenu'] for r in contexte['rubriques']}
        self.assertIn('340', par_titre[
            'Catégories et nombre de personnes concernées'])
        self.assertIn('identite', par_titre[
            'Catégories de données concernées'])
        self.assertIn('Usurpation', par_titre[
            'Conséquences probables pour les personnes'])

    def test_un_champ_vide_reste_vide_et_nest_jamais_invente(self):
        nue = creer_violation(self.company, date_detection=timezone.now())
        contexte = contexte_dossier_notification(nue)
        par_titre = {r['titre']: r['contenu'] for r in contexte['rubriques']}
        self.assertIn('non renseigné', par_titre['Mesures prises ou proposées'])

    def test_le_rendu_passe_par_core_pdf_jamais_le_moteur_de_devis(self):
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.4') as rendu:
            pdf, contexte = generer_dossier_notification(self.violation)
        self.assertEqual(pdf, b'%PDF-1.4')
        self.assertEqual(rendu.call_count, 1)
        html = rendu.call_args.kwargs['html']
        for titre in RUBRIQUES_NOTIFICATION:
            self.assertIn(titre, html)


class ActionDossierTests(TenantAPITestCase):
    def _admin(self):
        return self.client_as(role='admin')

    def test_action_renvoie_un_pdf_et_journalise_laudit(self):
        violation = creer_violation(
            self.company, date_detection=timezone.now())
        url = ('/api/django/grc/violations-donnees/'
               f'{violation.pk}/generer-dossier-notification/')
        avant = AuditLog.objects.filter(action=AuditLog.Action.PDF).count()
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.4'):
            r = self._admin().get(url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn('notification-cndp-', r['Content-Disposition'])
        apres = AuditLog.objects.filter(action=AuditLog.Action.PDF)
        self.assertEqual(apres.count(), avant + 1)
        self.assertEqual(
            apres.order_by('-id').first().detail,
            'Dossier de notification CNDP généré')

    def test_violation_dune_autre_societe_est_introuvable(self):
        etrangere = creer_violation(
            self.other_company, date_detection=timezone.now())
        url = ('/api/django/grc/violations-donnees/'
               f'{etrangere.pk}/generer-dossier-notification/')
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.4'):
            r = self._admin().get(url)
        self.assertEqual(r.status_code, 404)
