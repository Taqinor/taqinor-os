"""APAR56 (C-APAR-045) — le texte personnalisé d'une touche part identique en
WhatsApp ET en e-mail.

Sonde VB p8 : avec `j9_validite` personnalisé par la société, la touche
WhatsApp rendait le texte de la société mais la touche e-mail rendait la
forme e-mail CODÉE (`MESSAGE_TEMPLATE_FORMES_EMAIL`). Désormais une
personnalisation prime ; l'objet reste celui de la forme. Sans
personnalisation, l'e-mail garde sa forme codée.

Source réelle : `MessageTemplate.get_corps` et `message_pour_etape` réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.cadence_messages import message_pour_etape
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models_messages import MessageTemplate, forme_email

User = get_user_model()

CUSTOM = 'CUSTOM APAR56 : votre proposition reste valable, {prenom}.'
#: Propre à la forme e-mail codée de j9_validite (absent du texte WhatsApp).
FRAGMENT_FORME = 'je vous joins de nouveau votre proposition'


class FormeEmailPersonnaliseeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='APAR56 Solaire', slug='apar56-forme-email')
        self.user = User.objects.create_user(
            username='apar56-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Nadia',
            telephone='+212661565656', email='nadia.apar56@example.com',
            owner=self.user)

    def _etape(self, canal):
        # ACRM55 — une seule touche OUVERTE par barreau : la touche du canal
        # précédent (déjà rendue) libère le barreau J9.
        RelanceEtape.objects.filter(
            lead=self.lead, cadence='apres_devis', ordre=9,
            statut=RelanceEtape.Statut.A_FAIRE).delete()
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=9, due_date=datetime.date(2026, 10, 20), canal=canal,
            libelle='J9 validité', template_cle='j9_validite')

    def _rendus(self):
        return {canal: message_pour_etape(self._etape(canal), user=self.user)
                for canal in (RelanceEtape.Canal.EMAIL,
                              RelanceEtape.Canal.WHATSAPP)}

    def test_personnalisation_identique_email_et_whatsapp(self):
        MessageTemplate.objects.create(
            company=self.company, cle='j9_validite', corps_fr=CUSTOM)
        rendus = self._rendus()
        for canal, rendu in rendus.items():
            self.assertIn('CUSTOM APAR56', rendu['message'], canal)
        self.assertEqual(rendus['email']['message'],
                         rendus['whatsapp']['message'])
        self.assertNotIn(FRAGMENT_FORME, rendus['email']['message'])

    def test_sans_personnalisation_email_garde_la_forme_codee(self):
        rendus = self._rendus()
        self.assertNotIn('CUSTOM', rendus['email']['message'])
        self.assertIn(FRAGMENT_FORME, forme_email('j9_validite')['corps'])
        self.assertIn(FRAGMENT_FORME, rendus['email']['message'])
        self.assertNotIn(FRAGMENT_FORME, rendus['whatsapp']['message'])
