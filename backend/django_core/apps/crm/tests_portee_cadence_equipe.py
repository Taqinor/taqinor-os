"""ADEV64 (C-ADEV-025, volet cadence) — « Relances du jour »
(``GET /ventes/devis/action-requise/``) est bornée à la PORTÉE de l'appelant.

Sonde VA p9 : un Commercial de portée ``team`` (``records_scope_equipe``, sans
superviseur commun) qui ne voit AUCUN devis dans la liste recevait
``action-requise 200 devis listés 3 tel présent True`` — les devis, les noms
et les téléphones des clients de ses collègues. Désormais
``selectors_cadence.devis_action_requise`` passe chaque panier par
``core.scoping.scope_queryset`` (auteur du devis OU responsable du lead) :
aucun devis hors portée, aucun téléphone ni e-mail de client hors portée ; ses
propres devis apparaissent comme avant ; un Responsable de portée ``subtree``
voit son équipe.

Test-du-test : retirer ``scope_queryset`` du sélecteur ⇒
``test_commercial_team_hors_portee_absent`` échoue (les quatre devis du
collègue reviennent dans leurs paniers, avec leur téléphone). Rôles canoniques
réels, ``core.scoping`` réel, réponse HTTP réelle — aucun mock de portée.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_portee_cadence_equipe"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS)
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/devis/action-requise/'
TEL_HORS = '+212661640064'
EMAIL_HORS = 'hors.adev64@example.ma'
CLIENT_HORS = 'Zorglub64'
TEL_MOI = '+212661640099'


class PorteeCadenceTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ADEV64', slug='taqinor-adev64')
        self.today = timezone.localdate()
        role_com = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.role_resp = Role.objects.create(
            company=self.company, nom='Responsable commercial',
            permissions=list(COMMERCIAL_RESP_PERMISSIONS))
        # Portée ``team`` sans superviseur commun : chacun ne voit que soi.
        self.commercial = User.objects.create_user(
            username='adev64-com', password='x', company=self.company,
            role=role_com)
        self.collegue = User.objects.create_user(
            username='adev64-collegue', password='x', company=self.company,
            role=role_com)

        client_hors = Client.objects.create(
            company=self.company, nom=CLIENT_HORS, prenom='Hors',
            telephone=TEL_HORS, email=EMAIL_HORS)
        lead_hors = Lead.objects.create(
            company=self.company, nom=CLIENT_HORS, prenom='Hors',
            telephone=TEL_HORS, whatsapp=TEL_HORS, owner=self.collegue,
            client=client_hors)
        # Les devis du collègue, un par panier (hors portée du commercial).
        self.hors = {
            'envoyes_sans_reponse': self._devis(
                'DEV-HORS-6401', self.collegue, client_hors, lead_hors,
                statut=Devis.Statut.ENVOYE,
                date_envoi=timezone.now() - timedelta(days=9)),
            'refuses_sans_motif': self._devis(
                'DEV-HORS-6402', self.collegue, client_hors, lead_hors,
                statut=Devis.Statut.REFUSE, motif_refus=''),
            'acceptes_non_factures': self._devis(
                'DEV-HORS-6403', self.collegue, client_hors, lead_hors,
                statut=Devis.Statut.ACCEPTE,
                date_acceptation=self.today - timedelta(days=30)),
            'expirant_bientot': self._devis(
                'DEV-HORS-6404', self.collegue, client_hors, lead_hors,
                statut=Devis.Statut.ENVOYE,
                date_envoi=timezone.now() - timedelta(days=9),
                date_validite=self.today + timedelta(days=3)),
        }

        client_moi = Client.objects.create(
            company=self.company, nom='Dans', prenom='Portee',
            telephone=TEL_MOI)
        # Son propre devis (auteur) ...
        self.mien = self._devis(
            'DEV-MOI-6410', self.commercial, client_moi, None,
            statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=9))
        # ... et le devis d'un collègue sur un lead dont IL est responsable.
        lead_moi = Lead.objects.create(
            company=self.company, nom='Dans', prenom='Portee',
            telephone=TEL_MOI, owner=self.commercial, client=client_moi)
        self.sur_mon_lead = self._devis(
            'DEV-MOI-6411', self.collegue, client_moi, lead_moi,
            statut=Devis.Statut.REFUSE, motif_refus='')

    def _devis(self, ref, auteur, client, lead, **kwargs):
        return Devis.objects.create(
            company=self.company, reference=ref, client=client, lead=lead,
            created_by=auteur, taux_tva=Decimal('20'), **kwargs)

    def _get(self, user):
        api = APIClient()
        api.force_authenticate(user)
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp

    @staticmethod
    def _cites(data):
        return ({i for b in data['buckets'].values() for i in b['ids']}
                | {int(i) for i in data['devis']}
                | {int(i) for i in data['wa_drafts']})

    def test_commercial_team_hors_portee_absent(self):
        resp = self._get(self.commercial)
        data = resp.json()
        hors = {d.id for d in self.hors.values()}
        self.assertEqual(self._cites(data) & hors, set(), data)
        for panier, devis in self.hors.items():
            self.assertNotIn(devis.id, data['buckets'][panier]['ids'],
                             panier)
        texte = resp.content.decode('utf-8')
        for fuite in (TEL_HORS, EMAIL_HORS, CLIENT_HORS, 'DEV-HORS-'):
            self.assertNotIn(fuite, texte, fuite)

    def test_propres_devis_presents(self):
        data = self._get(self.commercial).json()
        self.assertEqual(data['buckets']['envoyes_sans_reponse']['ids'],
                         [self.mien.id])
        # Responsable du lead : le devis d'un collègue sur SON lead reste là.
        self.assertEqual(data['buckets']['refuses_sans_motif']['ids'],
                         [self.sur_mon_lead.id])
        ligne = data['devis'][str(self.mien.id)]
        self.assertEqual(ligne['reference'], 'DEV-MOI-6410')
        self.assertEqual(ligne['client_telephone'], TEL_MOI)
        self.assertEqual(self._cites(data),
                         {self.mien.id, self.sur_mon_lead.id})

    def test_responsable_subtree(self):
        responsable = User.objects.create_user(
            username='adev64-resp', password='x', company=self.company,
            role=self.role_resp)
        self.commercial.supervisor = responsable
        self.commercial.save(update_fields=['supervisor'])
        data = self._get(responsable).json()
        # Son équipe (le commercial) : son devis et celui de son lead.
        self.assertEqual(self._cites(data),
                         {self.mien.id, self.sur_mon_lead.id})
        self.assertEqual(
            data['devis'][str(self.mien.id)]['client_telephone'], TEL_MOI)
        # Le collègue hors de son sous-arbre : rien.
        self.assertNotIn(TEL_HORS, str(data))
