"""CAD82 — « Appeler » désactivé EXPLIQUÉ, préférence du client sur la touche.

Avant : ``lead_telephone`` valait '' aussi bien pour un lead SANS numéro que
pour un rôle privé de ``client_pii_voir`` — le bouton « Appeler » mourait sans
cause devinable — et ``contact_preference`` n'était pas servi : deux boutons
équivalents étaient proposés sans dire que ce client a demandé à n'être joint
que par écrit.

Done (moitié serveur) : la touche porte ``lead_pii_masquee`` (la cause d'un
numéro vide) et ``lead_contact_preference`` ; la ligne affiche la raison sous
le bouton désactivé et la mention « par écrit uniquement » (tests frontend).
Contrat partagé : les clés sont EXACTEMENT celles des lignes committées de
``relance_etape_v2.json`` (y compris ``exemple_pii_masquee`` et
``exemple_whatsapp_uniquement``).
"""
import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.serializers import RelanceEtapeSerializer
from apps.roles.models import Role

User = get_user_model()

JOUR = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class AppelerExpliqueTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD82 Solaire',
                                              slug='cad82')
        role_sans_pii = Role.objects.create(
            company=self.company, nom='CAD82 sans PII',
            permissions=['crm_voir'])
        role_pii = Role.objects.create(
            company=self.company, nom='CAD82 avec PII',
            permissions=['crm_voir', 'client_pii_voir'])
        self.sans_pii = User.objects.create_user(
            username='cad82-sans-pii', password='x', role=role_sans_pii,
            company=self.company)
        self.avec_pii = User.objects.create_user(
            username='cad82-avec-pii', password='x', role=role_pii,
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Amrani', prenom='Youssef',
            stage=stages.CONTACTED, telephone='+212661000450',
            whatsapp='+212661000450')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=2, canal=RelanceEtape.Canal.APPEL,
            libelle="Appel d'ouverture", template_cle='appel_ouverture',
            due_at=JOUR, due_date=JOUR.date())

    def _donnees(self, user):
        return RelanceEtapeSerializer(
            self.etape,
            context={'request': SimpleNamespace(user=user)}).data

    def test_numero_masque_par_les_droits_le_dit(self):
        donnees = self._donnees(self.sans_pii)
        self.assertEqual(donnees['lead_telephone'], '')
        self.assertIs(donnees['lead_pii_masquee'], True)

    def test_numero_visible_n_est_pas_masque(self):
        donnees = self._donnees(self.avec_pii)
        self.assertEqual(donnees['lead_telephone'], '+212661000450')
        self.assertIs(donnees['lead_pii_masquee'], False)

    def test_numero_absent_de_la_fiche_n_est_pas_un_masquage(self):
        self.lead.telephone = ''
        self.lead.whatsapp = ''
        self.lead.save(update_fields=['telephone', 'whatsapp'])
        donnees = self._donnees(self.avec_pii)
        self.assertEqual(donnees['lead_telephone'], '')
        self.assertIs(donnees['lead_pii_masquee'], False)

    def test_la_preference_whatsapp_uniquement_atteint_la_touche(self):
        self.lead.contact_preference = Lead.ContactPreference.WHATSAPP_ONLY
        self.lead.save(update_fields=['contact_preference'])
        self.assertEqual(self._donnees(self.avec_pii)[
            'lead_contact_preference'], 'whatsapp_only')

    def test_sans_preference_la_chaine_est_vide_jamais_null(self):
        self.assertEqual(
            self._donnees(self.avec_pii)['lead_contact_preference'], '')

    def test_la_forme_est_celle_du_contrat(self):
        contrat = _contrat('relance_etape_v2')
        attendu = set(contrat['exemple']['results'][0])
        self.assertEqual(set(self._donnees(self.avec_pii)), attendu)
        for variante in ('exemple_pii_masquee', 'exemple_whatsapp_uniquement'):
            self.assertEqual(set(contrat[variante]['results'][0]), attendu)
