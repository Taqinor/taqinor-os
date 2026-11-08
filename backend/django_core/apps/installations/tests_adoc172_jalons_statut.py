"""ADOC172 — le passage du chantier à ``materiel_commande`` puis ``installe``
publie les jalons « Matériel » / « Installation » du suivi client (phases
portail ``appro`` / ``pose``) via ``synchroniser_jalon_portail``."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation, JalonProjet
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class JalonsStatutTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADOC172 Co')
        self.user = User.objects.create_user(
            username='adoc172', password='x', company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ADOC172',
            telephone='+212600000172')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-ADOC17201',
            client=client, statut=Devis.Statut.ACCEPTE,
            date_acceptation=datetime.date(2026, 8, 26),
            taux_tva=Decimal('20'))
        self.link = ShareLink.for_devis(self.devis)
        self.chantier, _ = create_installation_from_devis(
            self.devis, self.user, self.company)
        self.api = APIClient()

    def _passer(self, statut):
        inst = Installation.objects.get(pk=self.chantier.pk)
        changer_statut_chantier(inst, statut, self.user, verifier_gates=False)

    def _suivi(self):
        resp = self.api.get(f'/api/django/ventes/suivi/{self.link.token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data, {m['key']: m for m in resp.data['milestones']}

    def test_materiel_commande_coche_materiel(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        _, ms = self._suivi()
        self.assertTrue(ms['materiel']['done'])
        self.assertTrue(ms['materiel']['date'])
        self.assertFalse(ms['installation']['done'])

    def test_installe_coche_installation(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        data, ms = self._suivi()
        self.assertTrue(ms['installation']['done'])
        self.assertTrue(ms['installation']['date'])
        self.assertEqual(data['mis_a_jour_le'], ms['installation']['date'])

    def test_annulation_decoche(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        Installation.objects.filter(pk=self.chantier.pk).update(annule=True)
        _, ms = self._suivi()
        self.assertFalse(ms['materiel']['done'])
        self.assertFalse(ms['installation']['done'])

    def test_idempotent(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        for phase in (JalonProjet.Phase.APPRO, JalonProjet.Phase.POSE):
            self.assertEqual(JalonProjet.objects.filter(
                installation=self.chantier, phase=phase).count(), 1)

    def test_retour_a_installe_defait_la_reception(self):
        """AARG46 — RÉCEPTIONNÉ → INSTALLÉ : jalon RÉCEPTION non atteint, plus
        de solde « à facturer », jalon portail non atteint ; nouvelle
        réception : atteint de nouveau, un seul jalon."""
        from apps.installations.services import chantiers_a_facturer
        from apps.portail.models import JalonChantierPortail

        def etat():
            jalons = JalonProjet.objects.filter(
                installation=self.chantier, phase=JalonProjet.Phase.RECEPTION)
            portail = JalonChantierPortail.objects.get(
                company=self.company, chantier_id=self.chantier.pk,
                cle_phase=JalonProjet.Phase.RECEPTION)
            a_facturer = any(
                c['installation_id'] == self.chantier.pk
                and c['jalon_id'] == jalons.get().pk for c in chantiers_a_facturer(self.company))
            return jalons.count(), jalons.get().atteint, portail.atteint, a_facturer

        self._passer(Installation.Statut.INSTALLE)
        self._passer(Installation.Statut.RECEPTIONNE)
        self.assertEqual(etat(), (1, True, True, True))
        self._passer(Installation.Statut.INSTALLE)
        self.assertEqual(etat(), (1, False, False, False))
        self._passer(Installation.Statut.RECEPTIONNE)
        self.assertEqual(etat(), (1, True, True, True))
        self._passer(Installation.Statut.CLOTURE)  # en avant : rien défait
        self.assertEqual(etat(), (1, True, True, True))

    def test_recul_defait_pose_et_appro(self):
        """ACSV3 (C-ACSV-004) — « Installé » ramené à « Planifié » : `pose`
        non atteint (interne + portail), `appro` atteint ; ramené à
        « Signé » : `appro` non atteint ; ré-avancer réatteint (un jalon par
        phase). ROUGE AVANT : `pose` atteint après le recul."""
        from apps.portail.models import JalonChantierPortail

        def etat(phase):
            jalon = JalonProjet.objects.get(
                installation=self.chantier, phase=phase)
            portail = JalonChantierPortail.objects.get(
                company=self.company, chantier_id=self.chantier.pk,
                cle_phase=phase)
            return jalon.atteint, portail.atteint

        Phase = JalonProjet.Phase
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        self.assertEqual(etat(Phase.POSE), (True, True))
        self._passer(Installation.Statut.PLANIFIE)
        self.assertEqual(etat(Phase.POSE), (False, False))
        self.assertEqual(etat(Phase.APPRO), (True, True))
        _, ms = self._suivi()
        self.assertFalse(ms['installation']['done'])
        self.assertTrue(ms['materiel']['done'])
        self._passer(Installation.Statut.SIGNE)
        self.assertEqual(etat(Phase.APPRO), (False, False))
        _, ms = self._suivi()
        self.assertFalse(ms['materiel']['done'])
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        self.assertEqual(etat(Phase.POSE), (True, True))
        self.assertEqual(etat(Phase.APPRO), (True, True))
        for phase in (Phase.APPRO, Phase.POSE):
            self.assertEqual(JalonProjet.objects.filter(
                installation=self.chantier, phase=phase).count(), 1)

    def test_recul_efface_la_reception_et_re_reception_recale_le_parc(self):
        """ACSV31 (C-ACSV-041) — recul depuis « Réceptionné » : dates de
        réception remises à nul (note), définitive refusée (409) ; une
        re-réception du jour recale pose et fin de garantie du parc.
        ROUGE AVANT : date du 08/08 gardée, définitive 200."""
        from apps.installations.models import InstallationActivity
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        admin = User.objects.create_user(
            username='adoc172-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api.force_authenticate(admin)
        ancienne = datetime.date(2026, 8, 8)
        self._passer(Installation.Statut.INSTALLE)
        self._passer(Installation.Statut.RECEPTIONNE)
        Installation.objects.filter(pk=self.chantier.pk).update(date_reception=ancienne)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur ACSV31', sku='OND-ACSV31',
            prix_achat=0, prix_vente=10, garantie_mois=120)
        eq = Equipement.objects.create(
            company=self.company, produit=produit, installation=self.chantier,
            numero_serie='SN-ACSV31', date_pose=ancienne)
        eq.recompute_garanties()
        eq.save()
        self._passer(Installation.Statut.INSTALLE)
        inst = Installation.objects.get(pk=self.chantier.pk)
        self.assertIsNone(inst.date_reception)
        self.assertIsNone(inst.date_reception_definitive)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=inst, body='Réception du 08/08/2026 défaite.').exists())
        r = self.api.post(
            f'/api/django/installations/chantiers/{inst.pk}/reception-definitive/')
        self.assertEqual(r.status_code, 409, getattr(r, 'data', r))
        self._passer(Installation.Statut.RECEPTIONNE)
        inst.refresh_from_db()
        aujourdhui = timezone.localdate()
        self.assertEqual(inst.date_reception, aujourdhui)
        eq.refresh_from_db()
        self.assertEqual(eq.date_pose, aujourdhui)
        self.assertEqual(eq.date_fin_garantie.year, aujourdhui.year + 10)
        self.assertNotIn('date_reception_defaite', inst.custom_data or {})

    def test_retour_arriere_ne_coche_rien(self):
        self._passer(Installation.Statut.INSTALLE)
        self._passer(Installation.Statut.SIGNE)
        self.assertFalse(JalonProjet.objects.filter(
            installation=self.chantier, phase=JalonProjet.Phase.APPRO,
            atteint=True).exists())
