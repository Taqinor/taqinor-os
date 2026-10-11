"""ACRM28 (C-ACRM-023) — UNE définition des leads visibles
(``selectors.leads_visibles`` : portée propriétaire ET périmètre d'entités)
lue par toutes les files.

Sonde V_VA LSEL-3 : un rôle borné à l'entité A, propriétaire d'un lead de
l'entité B en retard : ``GET`` du lead → 404, mais le lead sortait dans la
file « en retard » et dans « Ma file ». Désormais il est absent partout ; un
rôle sans entités visibles garde le comportement actuel.

Aucun mock : rôle, entités, leads et touches réels.
"""
import datetime
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.entites.models import Entite
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS)
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.selectors_cadence import details_par_panier
from apps.ventes.utils.options import deux_options_declarees

User = get_user_model()


class PerimetreEntiteFilesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM28 Solaire', slug='acrm28-entites')
        self.ent_a = Entite.objects.create(
            company=self.company, nom='Agence A', code='A')
        self.ent_b = Entite.objects.create(
            company=self.company, nom='Agence B', code='B')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial A',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.role.entites_visibles.set([self.ent_a])
        self.moi = User.objects.create_user(
            username='acrm28-moi', password='x', company=self.company,
            role=self.role)
        self.today = aujourd_hui_local()
        hier = self.today - datetime.timedelta(days=10)
        commun = dict(company=self.company, owner=self.moi,
                      stage=stages.CONTACTED, relance_date=hier, score=90,
                      contact_preference='phone_ok')
        self.lead_a = Lead.objects.create(nom='LeadA', entite=self.ent_a,
                                          **commun)
        self.lead_b = Lead.objects.create(nom='LeadB', entite=self.ent_b,
                                          **commun)
        # Valeurs posées SANS passer par save() (score recalculé, premier
        # contact horodaté) : le test fixe lui-même l'état observé.
        Lead.objects.filter(pk__in=[self.lead_a.pk, self.lead_b.pk]).update(
            score=90, first_contacted_at=None, relance_date=hier,
            contact_preference='phone_ok')
        RelanceEtape.objects.filter(company=self.company).delete()
        for lead in (self.lead_a, self.lead_b):
            RelanceEtape.objects.create(
                company=self.company, lead=lead, cadence='contact', ordre=1,
                canal=RelanceEtape.Canal.APPEL, libelle='Appeler',
                due_date=hier)

    def _ids_par_lecteur(self):
        today = self.today
        etapes, _resume = selectors.relance_etapes_periode(
            self.company, self.moi,
            date_debut=today - datetime.timedelta(days=30), date_fin=today)
        return {
            'relances_du_jour': {
                le.pk for le in selectors.relances_du_jour(
                    self.company, self.moi, scope='overdue', today=today)},
            'relance_etapes_dues': {
                e.lead_id for e in selectors.relance_etapes_dues(
                    self.company, self.moi, scope='all', today=today)},
            'relance_etapes_periode': {e.lead_id for e in etapes},
            'leads_chauds_non_contactes': {
                le.pk for le in selectors.leads_chauds_non_contactes(
                    self.company, self.moi)},
            'leads_rappel_demande': {
                le.pk for le in selectors.leads_rappel_demande(
                    self.company, self.moi)},
            'ma_file_commercial_items': {
                int(item['link'].rsplit('=', 1)[1])
                for item in selectors.ma_file_commercial_items(
                    self.company, self.moi, today=today)},
            'cadences_echues_a_clore': {
                ligne['lead_id'] for ligne in selectors.cadences_echues_a_clore(
                    self.company, self.moi, jours=1, today=today)},
        }

    def test_lead_hors_perimetre_absent_de_chaque_file(self):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.moi)}'))
        self.assertEqual(
            api.get(f'/api/django/crm/leads/{self.lead_b.pk}/').status_code,
            404)
        for lecteur, ids in self._ids_par_lecteur().items():
            self.assertNotIn(self.lead_b.pk, ids, lecteur)
            self.assertIn(self.lead_a.pk, ids, lecteur)
        cockpit = selectors.file_du_cockpit(self.company, self.moi,
                                            today=self.today)
        self.assertEqual(cockpit['maintenant'], 1)
        resp = api.get('/api/django/crm/leads/relances/?scope=overdue')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('LeadB', resp.content.decode())
        resp = api.get('/api/django/crm/relance-etapes/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('LeadB', resp.content.decode())

    def test_role_sans_entites_inchange(self):
        self.role.entites_visibles.clear()
        for lecteur, ids in self._ids_par_lecteur().items():
            self.assertIn(self.lead_b.pk, ids, lecteur)
            self.assertIn(self.lead_a.pk, ids, lecteur)


# ADEV64 (C-ADEV-025, volet cadence) — « Relances du jour »
# (``GET /ventes/devis/action-requise/``) est bornée à la PORTÉE de l'appelant.
#
# Sonde VA p9 : un Commercial de portée ``team`` (``records_scope_equipe``, sans
# superviseur commun) qui ne voit AUCUN devis dans la liste recevait
# ``action-requise 200 devis listés 3 tel présent True`` — les devis, les noms
# et les téléphones des clients de ses collègues. Désormais
# ``selectors_cadence.devis_action_requise`` passe chaque panier par
# ``core.scoping.scope_queryset`` (auteur du devis OU responsable du lead) :
# aucun devis hors portée, aucun téléphone ni e-mail de client hors portée ; ses
# propres devis apparaissent comme avant ; un Responsable de portée ``subtree``
# voit son équipe.
#
# Test-du-test : retirer ``scope_queryset`` du sélecteur ⇒
# ``test_commercial_team_hors_portee_absent`` échoue (les quatre devis du
# collègue reviennent dans leurs paniers, avec leur téléphone). Rôles canoniques
# réels, ``core.scoping`` réel, réponse HTTP réelle — aucun mock de portée.
#
# Run :
#     powershell -File scripts/test-backend.ps1 -RestoreDb \
#         -Modules "apps.crm.tests_acrm_perimetre_entite_files"

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


# APRF9 (C-APRF-004 + C-APRF-005) — « Relances du jour »
# (``GET /ventes/devis/action-requise/``) coûte un nombre de requêtes et
# d'octets de détail INDÉPENDANT du nombre de devis par panier.
#
# Sondes G/G2 de V_VA : requêtes 7 → 26 pour +10 devis deux options, +10 pour
# +10 mono ; octets 471 → 2 462, +199 par devis refusé sans motif, aucune
# borne : ``selectors_cadence.devis_action_requise`` construisait une ligne
# ``devis`` pour TOUS les ids cités, sur un ``prefetch_related('lignes')`` qui
# laissait ``Devis.total_ttc`` retomber sur une requête par devis (deux par
# devis à deux options). Désormais (contrat APRF1) : ``count``/``ids``
# complets, lignes pour les SEULS ``details_par_panier`` premiers ids de chaque
# panier, sur un queryset passé par ``devis_avec_totaux`` (APRF7).
#
# Test-du-test : reconstruire ``devis`` pour tous les ids cités ⇒ octets de
# détail linéaires, ``test_requetes_et_octets_constants`` échoue (et
# ``test_details_vingt_premiers``) ; repasser à ``prefetch_related('lignes')``
# ⇒ +1 ou +2 requêtes par devis détaillé, la mesure de base (12 lignes) diffère
# de +10/+30 (22 lignes), échec. Réponse HTTP réelle + ``CaptureQueriesContext``,
# aucun mock. ``20`` n'est jamais recopié : il est lu dans le contrat.
#
# Run :
#     powershell -File scripts/test-backend.ps1 -RestoreDb \
#         -Modules "apps.crm.tests_acrm_perimetre_entite_files"

CONTRAT = (Path(__file__).resolve().parents[1] / 'ventes'
           / 'contract_samples' / 'devis_action_requise.json')

MONO = [('Panneau Canadian Solar 550W', '10', '1400'),
        ('Onduleur réseau Deye 8kW', '1', '14000')]
DEUX = MONO + [('Onduleur hybride Deye 8kW', '1', '21000'),
               ('Batterie Dyness 5 kWh', '2', '12000')]


def _details_du_contrat():
    return json.loads(CONTRAT.read_text(encoding='utf-8'))[
        'details_par_panier']


class ActionRequiseBorneTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='APRF9 SARL')
        self.user = User.objects.create_user(
            username='aprf9_resp', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='APRF9', prenom='Client',
            email='aprf9@example.com', telephone='+212600000909')
        self.produits = {}
        for desig, _qty, pu in DEUX:
            self.produits[desig] = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'APRF9-{len(self.produits)}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=10)
        self.n = 0
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _devis(self, deux=False, **kwargs):
        self.n += 1
        kwargs.setdefault('statut', Devis.Statut.REFUSE)
        if kwargs['statut'] == Devis.Statut.REFUSE:
            kwargs.setdefault('motif_refus', '')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APRF9-{self.n:04d}',
            client=self.client_obj, created_by=self.user,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
            etude_params=({'scenario': 'Les deux (Sans + Avec)'}
                          if deux else {}),
            **kwargs)
        for desig, qty, pu in (DEUX if deux else MONO):
            LigneDevis.objects.create(
                devis=devis, produit=self.produits[desig], designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _refuses(self, combien):
        return [self._devis(deux=i % 2 == 1) for i in range(combien)]

    def _demo(self):
        """La « démo » : un envoyé sans réponse (lead + touche CRM À FAIRE),
        un accepté non facturé, et 10 refusés sans motif (moitié deux
        options)."""
        lead = Lead.objects.create(
            company=self.company, nom='APRF9', prenom='Prospect',
            client=self.client_obj)
        self.envoye = self._devis(
            statut=Devis.Statut.ENVOYE, lead=lead,
            date_envoi=timezone.now() - timedelta(days=9))
        due_at = timezone.now() + timedelta(days=2)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1, due_date=due_at.date(),
            due_at=due_at, canal='whatsapp', cadence='apres_devis',
            devis=self.envoye, statut=RelanceEtape.Statut.A_FAIRE)
        self.accepte = self._devis(
            deux=True, statut=Devis.Statut.ACCEPTE,
            date_acceptation=timezone.localdate() - timedelta(days=30))
        self._refuses(10)

    def _mesurer(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        data = resp.json()
        octets = len(json.dumps(data['devis'], sort_keys=True,
                                ensure_ascii=False).encode('utf-8'))
        return len(ctx.captured_queries), octets, data

    def _refuses_reels(self):
        return list(Devis.objects
                    .filter(company=self.company, statut=Devis.Statut.REFUSE)
                    .order_by('id').values_list('id', flat=True))

    def test_details_par_panier_lu_dans_le_contrat(self):
        self.assertEqual(details_par_panier(), _details_du_contrat())

    def test_requetes_et_octets_constants(self):
        self._demo()
        # Prémisse : les deux formes sont présentes parmi les refusés.
        formes = {deux_options_declarees(d) for d in Devis.objects.filter(
            company=self.company, statut=Devis.Statut.REFUSE)}
        self.assertEqual(formes, {True, False})
        self.api.get(URL)  # échauffement (caches de première requête)
        q_base, _o_base, base = self._mesurer()
        self._refuses(10)
        q10, o10, plus10 = self._mesurer()
        self._refuses(20)
        q30, o30, plus30 = self._mesurer()

        self.assertEqual(q_base, q10, f'requêtes {q_base} (démo) ≠ {q10} (+10)')
        self.assertEqual(q10, q30, f'requêtes {q10} (+10) ≠ {q30} (+30)')
        self.assertEqual(o10, o30, f'octets de détail {o10} (+10) ≠ {o30} (+30)')

        panier = plus30['buckets']['refuses_sans_motif']
        self.assertEqual(panier['count'], 40)
        self.assertEqual(panier['ids'], self._refuses_reels())
        # Totaux égaux au centime à avant ET à la lecture sans préchargement.
        for cle, ligne in base['devis'].items():
            self.assertEqual(plus30['devis'][cle]['total_ttc'],
                             ligne['total_ttc'], cle)
            self.assertEqual(plus10['devis'][cle]['total_ttc'],
                             ligne['total_ttc'], cle)
            self.assertEqual(
                ligne['total_ttc'],
                str(Devis.objects.get(pk=int(cle)).total_ttc), cle)
        touche = base['devis'][str(self.envoye.id)]['prochaine_touche_crm']
        self.assertIsNotNone(touche)
        self.assertEqual(
            plus30['devis'][str(self.envoye.id)]['prochaine_touche_crm'],
            touche)

    def test_details_vingt_premiers(self):
        n = _details_du_contrat()
        refuses = self._refuses(n + 5)
        envoye = self._devis(statut=Devis.Statut.ENVOYE,
                             date_envoi=timezone.now() - timedelta(days=9))
        _q, _o, data = self._mesurer()
        panier = data['buckets']['refuses_sans_motif']
        ids = [d.id for d in refuses]
        self.assertEqual(panier['count'], n + 5)
        self.assertEqual(panier['ids'], ids)
        self.assertEqual({int(i) for i in data['devis']},
                         set(ids[:n]) | {envoye.id})
        for cle, contenu in data['buckets'].items():
            for i in contenu['ids'][:n]:
                self.assertIn(str(i), data['devis'], cle)
