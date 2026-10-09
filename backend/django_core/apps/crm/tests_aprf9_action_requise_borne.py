"""APRF9 (C-APRF-004 + C-APRF-005) — « Relances du jour »
(``GET /ventes/devis/action-requise/``) coûte un nombre de requêtes et
d'octets de détail INDÉPENDANT du nombre de devis par panier.

Sondes G/G2 de V_VA : requêtes 7 → 26 pour +10 devis deux options, +10 pour
+10 mono ; octets 471 → 2 462, +199 par devis refusé sans motif, aucune
borne : ``selectors_cadence.devis_action_requise`` construisait une ligne
``devis`` pour TOUS les ids cités, sur un ``prefetch_related('lignes')`` qui
laissait ``Devis.total_ttc`` retomber sur une requête par devis (deux par
devis à deux options). Désormais (contrat APRF1) : ``count``/``ids``
complets, lignes pour les SEULS ``details_par_panier`` premiers ids de chaque
panier, sur un queryset passé par ``devis_avec_totaux`` (APRF7).

Test-du-test : reconstruire ``devis`` pour tous les ids cités ⇒ octets de
détail linéaires, ``test_requetes_et_octets_constants`` échoue (et
``test_details_vingt_premiers``) ; repasser à ``prefetch_related('lignes')``
⇒ +1 ou +2 requêtes par devis détaillé, la mesure de base (12 lignes) diffère
de +10/+30 (22 lignes), échec. Réponse HTTP réelle + ``CaptureQueriesContext``,
aucun mock. ``20`` n'est jamais recopié : il est lu dans le contrat.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_aprf9_action_requise_borne"
"""
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

from apps.crm.models import Client, Lead, RelanceEtape
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.selectors_cadence import details_par_panier
from apps.ventes.utils.options import deux_options_declarees
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/devis/action-requise/'
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
