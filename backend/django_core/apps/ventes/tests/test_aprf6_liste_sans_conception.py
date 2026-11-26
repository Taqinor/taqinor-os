"""APRF6 (C-APRF-003) — la conception électrique (``electrical_design``) est
absente de la représentation LISTE des devis (``GET /ventes/devis/``) et
servie identique, octet pour octet, au détail (``GET /ventes/devis/<id>/``).

Test-du-test : remettre le champ en liste ⇒ ``test_liste_sans_conception``
échoue ; le retirer aussi du détail ⇒ ``test_detail_avec_conception``
échoue. Réponses HTTP réelles, aucun mock.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

User = get_user_model()
URL = '/api/django/ventes/devis/'

CONCEPTION = {
    'version': 1,
    'chaines': [{'mppt': 1, 'panneaux': 9, 'voc_v': 412.5}],
    'protections': {'dc': 'Fusible 15 A', 'ac': 'Disjoncteur 32 A'},
    'cables': [{'troncon': 'DC', 'section_mm2': 6, 'longueur_m': 25}],
}


class ListeSansConceptionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APRF6 SARL')
        self.user = User.objects.create_user(
            username='aprf6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='APRF6')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-APRF6-0001', client=client,
            created_by=self.user, taux_tva=Decimal('20'),
            electrical_design=CONCEPTION,
            roof_layout={'result': {'panels': 9}})

    def _ligne_liste(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        lignes = data.get('results', data) if isinstance(data, dict) else data
        return next(r for r in lignes if r['id'] == self.devis.pk)

    def test_liste_sans_conception(self):
        ligne = self._ligne_liste()
        self.assertNotIn('electrical_design', ligne)
        # T4-X4-005 — le calepinage ne voyage plus en liste : la ligne dit
        # seulement qu'il existe (DevisRow.jsx lit ``a_plan_toiture``).
        self.assertNotIn('roof_layout', ligne)
        self.assertTrue(ligne['a_plan_toiture'])

    def test_detail_avec_conception(self):
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.dumps(resp.data['electrical_design'], sort_keys=True),
            json.dumps(CONCEPTION, sort_keys=True))

    def test_liste_puis_detail_conception_intacte(self):
        # CLAUSE PERSISTANCE — ouvrir le devis après la liste.
        self._ligne_liste()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.electrical_design, CONCEPTION)
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.data['electrical_design'], CONCEPTION)


# ---------------------------------------------------------------------------
# T4-X4-005 (S2) — sur une copie de la production, la liste des devis servait
# 52 à 82 Ko PAR devis (25 devis = 2,0 Mo) : le bloc d'étude ``etude_params``
# (profil horaire de 8 760 valeurs, simulation), les lignes et le calepinage
# voyageaient sur chaque ligne de liste. La LISTE sert une forme légère ; le
# DÉTAIL (et ``?forme=complete``, envoyé par le seul dialogue « Signé ») garde
# la forme complète. Réponses HTTP réelles, comptage des requêtes réel.
# ---------------------------------------------------------------------------
def _etude_reelle(i):
    """Un bloc d'étude de la taille de ceux de la production (≈ 60 Ko)."""
    return {
        'recommended_option': 'Avec batterie',
        'gamme': {'nom': 'Essentielle'},
        'scenario': 'Avec batterie',
        'profil_horaire': [round(0.31 + ((h + i) % 24) / 97, 4)
                           for h in range(8760)],
        'simulation': {'mensuel': [
            {'mois': m, 'production_kwh': 612.5 + m, 'pertes_pct': 14.2}
            for m in range(1, 13)], 'p50': 7420.4, 'p90': 6890.1},
    }


class ListeLegereT4X4005Tests(TestCase):
    """Le budget : une page de 25 devis pèse moins de 100 Ko, avec un nombre
    de requêtes qui ne grandit pas avec le nombre de devis."""

    def setUp(self):
        from apps.ventes.models import LigneDevis
        self.company = Company.objects.create(nom='T4X4005 SARL')
        self.admin = User.objects.create_user(
            username='t4x4005_admin', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='t4x4005_com', password='x', role_legacy='commercial',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Benali', prenom='Karim')
        self.autre_client = Client.objects.create(
            company=self.company, nom='Zerouali', prenom='Nadia')
        self._ligne = LigneDevis
        self.n = 0

    def _creer(self, nombre, client=None, created_by=None, **extra):
        crees = []
        for _ in range(nombre):
            self.n += 1
            d = Devis.objects.create(
                company=self.company, reference='DEV-T4X4-%04d' % self.n,
                client=client or self.client_obj,
                created_by=created_by or self.admin,
                taux_tva=Decimal('20'), etude_params=_etude_reelle(self.n),
                roof_layout={'version': 1, 'zones': [
                    {'id': 'z%d' % k, 'vertices': [[k, k + 0.5]] * 40}
                    for k in range(6)]},
                electrical_design=CONCEPTION, marge_snapshot=Decimal('23.5'),
                **extra)
            for k in range(12):
                self._ligne.objects.create(
                    devis=d, designation='Panneau 580 Wc %d' % k,
                    quantite=Decimal('2'), prix_unitaire=Decimal('1450'))
            crees.append(d)
        return crees

    def _page(self, api=None, **params):
        params.setdefault('page_size', 25)
        resp = (api or self.api).get(URL, params)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        return resp

    def test_page_de_25_sous_100_ko(self):
        self._creer(25)
        complete = self._page(forme='complete')
        legere = self._page()
        self.assertEqual(len(legere.json()['results']), 25)
        print('\nT4-X4-005 octets page 25 : complete=%d legere=%d' % (
            len(complete.content), len(legere.content)))
        self.assertLess(len(legere.content), 100_000)

    def test_nombre_de_requetes_constant_et_borne(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self._creer(5)
        self._page()  # premier appel : profils et réglages créés une fois
        with CaptureQueriesContext(connection) as a_cinq:
            self._page()
        self._creer(20)
        with CaptureQueriesContext(connection) as a_25:
            self._page()
        print('\nT4-X4-005 requetes : 5 devis=%d 25 devis=%d' % (
            len(a_cinq.captured_queries), len(a_25.captured_queries)))
        self.assertEqual(len(a_cinq.captured_queries),
                         len(a_25.captured_queries))
        self.assertLessEqual(len(a_25.captured_queries), 40)

    def test_forme_legere_dit_ce_que_la_ligne_montre(self):
        self._creer(1)
        ligne = self._page().json()['results'][0]
        for lourd in ('etude_params', 'lignes', 'roof_layout',
                      'pdf_render_meta', 'offres_tailles_config', 'overrides',
                      'clauses_appliquees', 'custom_data', 'electrical_design'):
            self.assertNotIn(lourd, ligne)
        self.assertTrue(ligne['detail_partiel'])
        self.assertTrue(ligne['a_plan_toiture'])
        self.assertEqual(ligne['etude_resume'], {
            'recommended_option': 'Avec batterie', 'gamme_nom': 'Essentielle',
            'a_etude': True})
        for lu in ('reference', 'client_nom', 'statut', 'total_affiche',
                   'nb_options', 'solde', 'vente', 'is_expired',
                   'date_expiration', 'bon_commande_etat', 'factures_liees',
                   'chantier', 'comparaison_options', 'modifiable',
                   'echeancier', 'mode_installation', 'is_active'):
            self.assertIn(lu, ligne)

    def test_detail_et_forme_complete_gardent_tout(self):
        (d,) = self._creer(1)
        detail = self.api.get('%s%s/' % (URL, d.pk)).json()
        self.assertEqual(detail['etude_params'], d.etude_params)
        self.assertEqual(len(detail['lignes']), 12)
        complete = self._page(forme='complete').json()['results'][0]
        self.assertEqual(len(complete['lignes']), 12)
        self.assertEqual(complete['etude_params'], d.etude_params)
        self.assertEqual(self.api.get(URL, {'forme': 'abc'}).status_code, 400)

    def test_marge_masquee_au_commercial(self):
        self._creer(1, created_by=self.commercial)
        api_com = APIClient()
        api_com.force_authenticate(user=self.commercial)
        resp = self._page(api=api_com)
        self.assertIsNone(resp.json()['results'][0]['marge_snapshot'])
        self.assertNotIn('prix_achat', resp.content.decode())
        ligne_admin = self._page().json()['results'][0]
        self.assertEqual(ligne_admin['marge_snapshot'], '23.50')

    def test_recherche_filtres_et_compte_par_le_serveur(self):
        from datetime import timedelta
        from django.utils import timezone
        jour = timezone.localdate()
        self._creer(1)
        (zero,) = self._creer(1, client=self.autre_client)
        (expire,) = self._creer(1, statut=Devis.Statut.ENVOYE,
                                date_validite=jour - timedelta(days=3))
        (envoye,) = self._creer(1, statut=Devis.Statut.ENVOYE,
                                date_validite=jour + timedelta(days=3))
        (remplace,) = self._creer(1, is_active=False)
        (du_com,) = self._creer(1, created_by=self.commercial)

        def ids(**p):
            data = self._page(**p).json()
            return {r['id'] for r in data['results']}, data['count']

        self.assertEqual(ids(q='zeroua')[0], {zero.pk})
        self.assertEqual(ids(q=zero.reference.lower())[0], {zero.pk})
        self.assertEqual(ids(statut_effectif='expire')[0], {expire.pk})
        self.assertEqual(ids(statut_effectif='envoye')[0], {envoye.pk})
        self.assertNotIn(remplace.pk, ids(actifs='1')[0])
        self.assertIn(remplace.pk, ids()[0])
        self.assertEqual(ids(auteurs=str(self.commercial.pk))[0], {du_com.pk})
        self.assertEqual(ids(page_size=2)[1], 6)
        self.assertEqual(len(ids(page_size=2)[0]), 2)
        self.assertEqual(self.api.get(URL, {'auteurs': 'x'}).status_code, 400)
        self.assertEqual(
            self.api.get(URL, {'statut_effectif': 'zz'}).status_code, 400)

    # ADEV162 — le total affiché RANGÉ sur le devis (cache de ``display_totals``
    # + empreinte de ce dont il a été calculé) remplace le cache de 6 h.
    def _synthese_espionnee(self):
        from unittest import mock
        from apps.ventes.quote_engine import builder
        with mock.patch.object(builder, 'display_totals',
                               wraps=builder.display_totals) as espion:
            data = self.api.get(URL + 'synthese/').json()
        return data, espion.call_count

    def _colonne(self):
        """La somme de la colonne « Total TTC » : la règle de la colonne,
        ``display_totals``, recalculée de zéro sur chaque devis en jeu."""
        from decimal import Decimal
        from core.money import quantize_mad
        from apps.ventes.quote_engine.builder import display_totals
        total = sum((Decimal(str(display_totals(d)['total'] or 0))
                     for d in Devis.objects.filter(company=self.company, is_active=True)),
                    Decimal('0'))
        return float(quantize_mad(total))

    def test_synthese_200_devis_cache_vide_sans_moteur_par_devis(self):
        """ADEV162 — 200 devis, cache vide : le calcul ne rappelle pas le
        moteur du devis pour chaque devis (0 appel, requêtes bornées — des
        comptes, jamais une horloge), mêmes totaux que la colonne."""
        import time
        from io import StringIO
        from django.core.cache import cache
        from django.core.management import call_command
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        for _ in range(200):
            self.n += 1
            d = Devis.objects.create(
                company=self.company, reference='DEV-ADEV162-%04d' % self.n,
                client=self.client_obj, created_by=self.admin,
                taux_tva=Decimal('20'), etude_params=_etude_reelle(self.n))
            for k in range(2):
                self._ligne.objects.create(
                    devis=d, designation='Panneau 580 Wc %d' % k,
                    quantite=Decimal('2'), prix_unitaire=Decimal('1450') + self.n)
        cache.clear()
        debut = time.perf_counter()
        _, avant = self._synthese_espionnee()
        froid_sans_range = time.perf_counter() - debut
        call_command('ranger_totaux_affiches', stdout=StringIO())
        cache.clear()
        debut = time.perf_counter()
        with CaptureQueriesContext(connection) as requetes:
            data, appels = self._synthese_espionnee()
        print('\nADEV162 synthese 200 devis : sans rangement=%.2f s (%d moteur) '
              'range=%.2f s (%d moteur, %d requetes) — mesure indicative' % (
                  froid_sans_range, avant, time.perf_counter() - debut, appels,
                  len(requetes.captured_queries)))
        self.assertEqual(avant, 200)
        self.assertEqual(appels, 0)
        self.assertLessEqual(len(requetes.captured_queries), 14)
        self.assertEqual(data['par_statut']['brouillon']['count'], 200)
        self.assertEqual(data['par_statut']['brouillon']['total'], self._colonne())

    def test_un_deploiement_du_moteur_perime_les_totaux_ranges(self):
        """ADEV162 (relecture) — le CODE est dans l'empreinte : des sources du
        total qui changent (un correctif du moteur déployé) et aucun total
        rangé n'est plus servi ; le balayage les range à nouveau."""
        from unittest import mock
        from apps.ventes import selectors_listes
        from apps.ventes.domain.etudes import ranger_totaux_affiches
        self._creer(2)
        self.assertEqual(ranger_totaux_affiches(Devis.objects.all()), 2)
        self.assertEqual(self._synthese_espionnee()[1], 0)
        with mock.patch.object(selectors_listes, 'empreinte_du_code', return_value='correctif'):
            data, appels = self._synthese_espionnee()
            self.assertEqual(appels, 2)
            self.assertEqual(data['par_statut']['brouillon']['total'], self._colonne())
            self.assertEqual(ranger_totaux_affiches(Devis.objects.all()), 2)
            self.assertEqual(self._synthese_espionnee()[1], 0)
        # Les sources réelles : tout apps/ventes (moteur, options, arrondis) et core.
        fichiers = {f.replace('\\', '/') for f in selectors_listes.fichiers_du_total()}
        for module in ('apps/ventes/quote_engine/builder.py', 'apps/ventes/utils/options.py',
                       'apps/ventes/domain/noyau_totaux.py', 'apps/ventes/domain/argent.py',
                       'apps/ventes/quote_engine/lignes_classement.py', 'apps/ventes/multivilla.py',
                       'apps/ventes/quote_engine/montants.py', 'core/money.py'):
            self.assertTrue(any(f.endswith(module) for f in fichiers), module)

    def test_total_de_repli_jamais_range(self):
        """ADEV162 (relecture) — moteur en échec : ``display_totals`` rend un
        total de REPLI ; il n'est jamais rangé (la synthèse recalculera)."""
        from unittest import mock
        from apps.ventes.domain.etudes import ranger_totaux_affiches
        from apps.ventes.quote_engine import builder
        (d,) = self._creer(1)
        with mock.patch.object(builder, 'build_quote_data', side_effect=RuntimeError('moteur')):
            self.assertEqual(ranger_totaux_affiches(Devis.objects.filter(pk=d.pk)), 0)
        d.refresh_from_db()
        self.assertIsNone(d.total_affiche_range)
        self.assertEqual(d.total_affiche_empreinte, '')

    def test_balayage_sans_changement_ne_charge_pas_les_etudes(self):
        """ADEV162 (relecture) — rien n'a bougé : le balayage ne lit que la
        forme légère (aucun relu complet, aucun moteur), en requêtes bornées."""
        from unittest import mock
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.ventes import selectors_listes
        from apps.ventes.domain.etudes import ranger_totaux_affiches
        self._creer(5)
        ranger_totaux_affiches(Devis.objects.all())
        with mock.patch.object(selectors_listes, 'devis_pour_les_totaux',
                               wraps=selectors_listes.devis_pour_les_totaux) as lecture, \
                CaptureQueriesContext(connection) as requetes:
            self.assertEqual(ranger_totaux_affiches(Devis.objects.all()), 0)
        self.assertEqual([c.kwargs.get('leger') for c in lecture.call_args_list], [True])
        self.assertLessEqual(len(requetes.captured_queries), 6)

    def test_mouvement_de_stock_ne_perime_pas_le_total(self):
        """ADEV162 (relecture) — une colonne de stock du produit (quantité,
        verrou, horodatage) bouge : le total rangé reste servi ; son prix de
        vente bouge : il est recalculé."""
        from apps.stock.models import Produit
        from apps.ventes.domain.etudes import ranger_totaux_affiches
        (d,) = self._creer(1)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 580', sku='ADEV162-S',
            prix_vente=Decimal('1450'), prix_achat=Decimal('1'), quantite_stock=10)
        self._ligne.objects.filter(devis=d).update(produit=produit)
        ranger_totaux_affiches(Devis.objects.filter(pk=d.pk))
        produit.quantite_stock = 3
        produit.save(update_fields=['quantite_stock'])
        Produit.objects.filter(pk=produit.pk).update(seuil_alerte=2, prix_achat=Decimal('2'))
        self.assertEqual(self._synthese_espionnee()[1], 0)
        Produit.objects.filter(pk=produit.pk).update(prix_vente=Decimal('1500'))
        self.assertEqual(self._synthese_espionnee()[1], 1)

    def test_total_range_jamais_servi_perime(self):
        """ADEV162 — Persistance : chaque écriture qui contourne ``save()``
        (``update()`` sur le devis, une ligne, le produit, le client, le
        profil société) change l'empreinte ; le total rangé n'est alors plus
        servi et la carte égale la colonne recalculée."""
        from apps.crm.models import Client as ClientModele
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import Produit
        from apps.ventes.domain.etudes import ranger_totaux_affiches
        (d,) = self._creer(1)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 580', sku='ADEV162-P',
            prix_vente=Decimal('1450'), prix_achat=Decimal('1'), quantite_stock=10)
        self._ligne.objects.filter(pk=d.lignes.first().pk).update(produit=produit)
        profil = CompanyProfile.get(self.company)
        ecritures = [
            lambda: Devis.objects.filter(pk=d.pk).update(remise_globale=Decimal('7')),
            lambda: self._ligne.objects.filter(devis=d).update(prix_unitaire=Decimal('999')),
            lambda: Produit.objects.filter(pk=produit.pk).update(nom='Batterie lithium 5 kWh'),
            lambda: ClientModele.objects.filter(pk=self.client_obj.pk).update(nom='Benali II'),
            lambda: CompanyProfile.objects.filter(pk=profil.pk).update(
                quote_validity_days=(profil.quote_validity_days or 30) + 5),
            lambda: Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ENVOYE),
        ]
        for ecrire in ecritures:
            self.assertEqual(ranger_totaux_affiches(Devis.objects.filter(pk=d.pk)), 1)
            _, appels = self._synthese_espionnee()
            self.assertEqual(appels, 0)  # rangé et concordant : servi
            ecrire()
            data, appels = self._synthese_espionnee()
            self.assertEqual(appels, 1)  # empreinte changée : recalculé
            (cellule,) = [v for v in data['par_statut'].values() if v['count']]
            self.assertEqual(cellule['total'], self._colonne())
        # Un GET n'écrit jamais : le devis lu périmé reste à ranger.
        self.assertEqual(ranger_totaux_affiches(Devis.objects.filter(pk=d.pk)), 1)

    def test_total_range_ecrit_apres_l_ecriture_du_devis(self):
        """ADEV162 — l'écrivain : ``finaliser_caches`` (édition, lignes) range
        après le commit ; le balayage planifié range un devis dont le statut a
        changé. Un devis envoyé ne voit bouger ni statut ni ``updated_at``,
        et les colonnes rangées ne sont servies ni en liste ni au détail."""
        from apps.ventes.domain.pipeline import finaliser_caches
        from apps.ventes.scheduled import ranger_totaux_affiches_planifie
        (d,) = self._creer(1)
        with self.captureOnCommitCallbacks(execute=True):
            finaliser_caches(d)
        self.assertEqual(self._synthese_espionnee()[1], 0)
        Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ENVOYE)
        d.refresh_from_db()
        avant = (d.statut, d.updated_at, d.total_ttc)
        self.assertEqual(ranger_totaux_affiches_planifie(), 1)
        self.assertEqual(ranger_totaux_affiches_planifie(), 0)  # idempotent
        d.refresh_from_db()
        self.assertEqual((d.statut, d.updated_at, d.total_ttc), avant)
        data, appels = self._synthese_espionnee()
        self.assertEqual(appels, 0)
        self.assertEqual(data['par_statut']['envoye']['total'], self._colonne())
        ligne = self._page().json()['results'][0]
        detail = self.api.get('%s%s/' % (URL, d.pk)).json()
        for cle in ('total_affiche_range', 'total_affiche_empreinte'):
            self.assertNotIn(cle, ligne)
            self.assertNotIn(cle, detail)

    def test_balayage_planifie_ignore_les_societes_suspendues(self):
        """ADEV162/AUD415 — le balayage planifié ne range que les devis des
        sociétés actives : un tenant suspendu n'est plus balayé."""
        from apps.ventes.scheduled import ranger_totaux_affiches_planifie
        (d,) = self._creer(1)
        Company.objects.filter(pk=self.company.pk).update(actif=False)
        self.assertEqual(ranger_totaux_affiches_planifie(), 0)
        d.refresh_from_db()
        self.assertIsNone(d.total_affiche_range)
        Company.objects.filter(pk=self.company.pk).update(actif=True)
        self.assertEqual(ranger_totaux_affiches_planifie(), 1)

    def _devis_espionne(self):
        """Un devis résidentiel à lead (étude sans ville figée : la branche
        qui lit le lead) et lignes à produits, relu par le jeu de la synthèse ;
        ``display_totals`` y est joué sous un relevé des colonnes du lead et
        des produits qu'il lit, et des fichiers source qu'il exécute."""
        import sys
        from apps.crm.models import Lead
        from apps.stock.models import Produit
        from apps.ventes.quote_engine.builder import display_totals
        from apps.ventes.selectors_listes import devis_pour_les_totaux
        lead = Lead.objects.create(company=self.company, nom='Espion', ville='Casablanca')
        (d,) = self._creer(1, lead=lead)
        for k, lg in enumerate(d.lignes.all()[:3]):
            lg.produit = Produit.objects.create(
                company=self.company, nom='Panneau 580 Wc %d' % k, sku='ESP-%d' % k,
                prix_vente=Decimal('1450'), prix_achat=Decimal('900'), quantite_stock=7)
            lg.save()
        devis = devis_pour_les_totaux(Devis.objects.filter(pk=d.pk)).get()
        lus = {'lead': set(), 'produit': set()}

        class Espion:
            def __init__(self, cible, cle):
                object.__setattr__(self, '_c', (cible, cle))

            def __getattr__(self, nom):
                cible, cle = object.__getattribute__(self, '_c')
                lus[cle].add(nom)
                return getattr(cible, nom)
        devis._state.fields_cache['lead'] = Espion(devis.lead, 'lead')
        for lg in devis.lignes.all():
            if lg.produit_id:
                lg._state.fields_cache['produit'] = Espion(lg.produit, 'produit')
        fichiers = set()
        sys.setprofile(lambda f, ev, a: fichiers.add(f.f_code.co_filename) if ev == 'call' else None)
        try:
            donnees = {}
            display_totals(devis, lignes_prechargees=True, donnees=donnees)
        finally:
            sys.setprofile(None)
        self.assertTrue(donnees)  # le moteur a vraiment tourné (pas le repli)
        return lus, fichiers

    #: Les colonnes de ``stock.Produit`` connues au 25/11/2026 : une colonne
    #: NOUVELLE fait échouer ce test — la décider (hachée par défaut, ou mise
    #: dans ``PRODUIT_HORS_EMPREINTE`` si le total ne la lit pas).
    COLONNES_PRODUIT = frozenset({
        'id', 'company_id', 'nom', 'sku', 'prix_achat', 'prix_vente', 'quantite_stock',
        'seuil_alerte', 'categorie_id', 'fournisseur_id', 'tva', 'is_archived', 'role_devis',
        'classe_danger', 'marque', 'description', 'garantie', 'photo_id', 'garantie_mois',
        'garantie_production_mois', 'prix_fixe_ht', 'prix_par_panneau_ht', 'pompe_cv', 'hmt_m',
        'pompe_kw', 'tension_v', 'courbe_pompe', 'role_pompage', 'type_pompe', 'alimentation',
        'courbe_source', 'courbe_frequence_hz', 'role_ci', 'type_pose', 'delai_appro_jours',
        'paliers_prix_vente', 'date_creation', 'date_mise_a_jour', 'custom_data',
        'quantite_reappro_cible', 'louable', 'tarif_location_jour', 'tarif_location_semaine',
        'tarif_location_mois', 'suivi_serie', 'code_barres', 'unite_stock', 'unite_id', 'code_sh',
        'pays_origine', 'politique_facturation_achat', 'est_recurrent', 'periodicite_defaut',
        'avertissement_vente', 'avertissement_bloquant', 'lock_version', 'entite_id',
        'debit_m3j',
        # D-ACAL-169 (26/11/2026) — décidée HORS empreinte (``PRODUIT_HORS_EMPREINTE``) :
        # le total d'un devis existant lit le panneau de ses lignes, jamais le désigné.
        'panneau_par_defaut'})

    def test_empreinte_couvre_ce_que_le_total_lit(self):
        """ADEV162 (relecture) — relevé sur un vrai passage du moteur : aucune
        colonne du produit lue n'est hors empreinte, les colonnes lues du lead
        sont celles hachées, et chaque fichier du dépôt exécuté est dans les
        sources de l'empreinte du code (hors journal d'audit, qui ne calcule
        rien)."""
        import os
        from django.conf import settings
        from apps.stock.models import Produit
        from apps.ventes import selectors_listes as sl
        lus, fichiers = self._devis_espionne()
        colonnes = {f.attname for f in Produit._meta.concrete_fields}
        self.assertEqual(colonnes - self.COLONNES_PRODUIT, set(), 'colonne de Produit à décider')
        lus_produit = {c[:-3] if c.endswith('_id') else c for c in lus['produit']}
        self.assertEqual(lus_produit & {c[:-3] if c.endswith('_id') else c
                                        for c in sl.PRODUIT_HORS_EMPREINTE}, set())
        self.assertLessEqual(lus['lead'] - {'pk', 'id'}, set(sl.LEAD_LU_PAR_LE_TOTAL))
        racine = os.path.normcase(str(settings.BASE_DIR))
        couverts = {os.path.normcase(f) for f in sl.fichiers_du_total()}
        hors = sorted(f for f in fichiers if os.path.normcase(f).startswith(racine)
                      and os.path.normcase(f) not in couverts
                      and not os.path.normcase(f).startswith(os.path.join(racine, 'apps', 'audit'))
                      and os.sep + 'tests' + os.sep not in f)
        self.assertEqual(hors, [])

    def test_synthese_nombre_de_requetes_constant(self):
        """Les cartes par statut : pas de requête par devis (5 devis = 50)."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from django.core.cache import cache
        self._creer(5)
        self.api.get(URL + 'synthese/')  # premier appel : réglages créés
        cache.clear()  # à froid : le budget vaut aussi sans totaux mémorisés
        with CaptureQueriesContext(connection) as a_cinq:
            self.api.get(URL + 'synthese/')
        self._creer(45)
        cache.clear()
        with CaptureQueriesContext(connection) as a_50:
            self.api.get(URL + 'synthese/')
        print('\nSYNTHESE requetes : 5 devis=%d 50 devis=%d' % (
            len(a_cinq.captured_queries), len(a_50.captured_queries)))
        self.assertEqual(len(a_cinq.captured_queries),
                         len(a_50.captured_queries))

    def test_synthese_compte_toute_la_portee(self):
        from datetime import timedelta
        from django.utils import timezone
        jour = timezone.localdate()
        self._creer(2)
        self._creer(1, statut=Devis.Statut.ENVOYE,
                    date_validite=jour - timedelta(days=3))
        (bientot,) = self._creer(1, statut=Devis.Statut.ENVOYE,
                                 date_validite=jour + timedelta(days=3))
        self._creer(1, statut=Devis.Statut.ACCEPTE,
                    option_acceptee='avec_batterie')
        self._creer(1, is_active=False)
        resp = self.api.get(URL + 'synthese/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        s = resp.json()
        self.assertEqual(s['total'], 6)
        self.assertEqual(s['remplaces'], 1)
        self.assertEqual(s['par_statut']['brouillon']['count'], 2)
        self.assertEqual(s['par_statut']['expire']['count'], 1)
        self.assertEqual(s['par_statut']['envoye']['count'], 1)
        self.assertEqual(s['par_statut']['accepte']['count'], 1)
        self.assertEqual(s['a_relancer'], [
            {'id': bientot.pk, 'reference': bientot.reference}])
        self.assertEqual(s['batterie'], {'avec': 1, 'sans': 0})
        # Le total d'argent est celui que la liste affiche (total_affiche).
        ligne = self._page(statut_effectif='accepte').json()['results'][0]
        self.assertAlmostEqual(
            s['par_statut']['accepte']['total'], float(ligne['total_affiche']))
        # Portée du rôle : la synthèse compte ce que la liste montre à ce rôle.
        self._creer(1, created_by=self.commercial)
        api_com = APIClient()
        api_com.force_authenticate(user=self.commercial)
        self.assertEqual(api_com.get(URL + 'synthese/').json()['total'],
                         self._page(api=api_com).json()['count'])
