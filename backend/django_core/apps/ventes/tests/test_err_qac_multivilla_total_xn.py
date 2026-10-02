"""ERR-QAC-MULTIVILLA-TOTAL-XN — un devis « ×N villas identiques » est FACTURÉ
au total ×N qu'il imprime (décision fondateur 30/09/2026, « ×N everywhere,
kWc total »).

Avant : le PDF imprimait ``display_total_multi`` (= total × N) pendant que
``Devis.total_ttc``, la liste, l'échéancier, le BC et l'acompte public
lisaient le total d'UNE villa. Désormais les deux enveloppes de la chaîne
canonique (``utils.options.option_totaux`` et ``domain.argent.totaux``)
multiplient par N ; le moteur PDF demande le total UNITAIRE
(``unitaire=True``) et garde sa propre mise à l'échelle — jamais ×N².

Les tests ``SimpleTestCase`` n'ont besoin d'aucune base (lignes et devis
factices) ; ``TestMultiVillaBout`` vérifie le chemin réel (CI).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase


def _ligne(total_ht, taux='20'):
    return SimpleNamespace(total_ht=Decimal(total_ht),
                           taux_tva_effectif=Decimal(taux))


def _devis(n=None, remise='0', kwc=None):
    etude = {}
    if n is not None:
        etude['nombre_proprietes'] = n
    if kwc is not None:
        etude['puissance_kwc'] = kwc
    return SimpleNamespace(remise_globale=Decimal(remise),
                           taux_tva=Decimal('20'), etude_params=etude,
                           option_acceptee='')


# Deux taux + une remise qui tombe sur un demi-centime : le cas où une mise à
# l'échelle naïve (recalcul sur des lignes ×N) s'écarterait du PDF.
LIGNES = [_ligne('14000.00', '20'), _ligne('10333.35', '10')]


class TestEchelleSelecteur(SimpleTestCase):
    def test_n1_rend_le_dict_tel_quel(self):
        from apps.ventes.selectors import totaux_multi_proprietes
        t = {'ttc': Decimal('10.00')}
        self.assertIs(totaux_multi_proprietes(t, 1), t)

    def test_chaque_etage_multiplie_et_chaine_tenue(self):
        from apps.ventes.selectors import (
            _canonical_totaux, totaux_multi_proprietes,
        )
        u = _canonical_totaux(LIGNES, remise_globale_pct=Decimal('7.5'),
                              fallback_taux=Decimal('20'))
        m = totaux_multi_proprietes(u, 3)
        for k in ('ht_brut', 'remise', 'ht_net', 'tva', 'ttc'):
            self.assertEqual(m[k], u[k] * 3, k)
        self.assertEqual(m['ht_net'] + m['tva'], m['ttc'])
        self.assertEqual(sum(b['montant'] for b in m['tva_par_taux']),
                         m['tva'])
        # L'entrée n'est jamais mutée.
        self.assertNotEqual(u['ttc'], m['ttc'])


class TestOptionTotaux(SimpleTestCase):
    def test_n1_inchange(self):
        from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
        from apps.ventes.selectors import _canonical_totaux
        from apps.ventes.utils.options import option_totaux
        # ARRONDI-100 : le total d'un devis porte le palier de 100 MAD ; la
        # référence N=1 est donc le noyau AVEC ce palier (28 166,69 exact →
        # 28 100,00), sinon on compare un total de devis à un brut.
        u = _canonical_totaux(LIGNES, remise_globale_pct=0,
                              fallback_taux=Decimal('20'),
                              arrondi_pas=PAS_ARRONDI_DEVIS)
        t = option_totaux(_devis(), option='', lignes=LIGNES)
        self.assertEqual(t['ttc'], u['ttc'])
        self.assertEqual(t['ht'], u['ht_net'])

    def test_n3_totaux_x3(self):
        from apps.ventes.utils.options import option_totaux
        un = option_totaux(_devis(remise='5'), option='', lignes=LIGNES)
        trois = option_totaux(_devis(3, remise='5'), option='', lignes=LIGNES)
        for k in ('ht', 'tva', 'ttc', 'ht_brut', 'remise', 'arrondi'):
            self.assertEqual(trois[k], un[k] * 3, k)


class TestArgentTotaux(SimpleTestCase):
    def test_n1_inchange_et_unitaire_neutre(self):
        from apps.ventes.domain.argent import Vue, totaux
        a = totaux(_devis(), vue=Vue.NET, lignes=LIGNES)
        b = totaux(_devis(), vue=Vue.NET, lignes=LIGNES, unitaire=True)
        self.assertEqual(a, b)

    def test_n3_x3_et_unitaire_pour_le_moteur(self):
        from apps.ventes.domain.argent import Vue, totaux
        d = _devis(3, remise='7.5')
        projet = totaux(d, vue=Vue.NET, lignes=LIGNES)
        unite = totaux(d, vue=Vue.AFFICHAGE, lignes=LIGNES, unitaire=True)
        self.assertEqual(unite, totaux(_devis(remise='7.5'),
                                       vue=Vue.AFFICHAGE, lignes=LIGNES))
        self.assertEqual(projet.ttc, unite.ttc * 3)
        self.assertEqual(projet.ht_net, unite.ht_net * 3)
        self.assertEqual(projet.ttc_affiche, projet.ttc)
        self.assertEqual(projet.ht_net + projet.tva, projet.ttc)

    def test_le_moteur_pdf_demande_le_total_unitaire(self):
        """Garde anti ×N² : le seul appel du moteur au noyau passe
        ``unitaire=True`` (le bloc QJ29 met à l'échelle lui-même)."""
        import inspect

        from apps.ventes.quote_engine import builder
        src = inspect.getsource(builder)
        i = src.index('vue = _totaux_noyau(')
        self.assertIn('unitaire=True', src[i:i + 400])


class TestEcheancier(SimpleTestCase):
    def _tranche(self, n):
        from apps.ventes.utils import echeancier
        tranches = [{'key': 'acompte', 'libelle': 'Acompte',
                     'valeur': Decimal('30'), 'unite': echeancier.UNITE_PCT},
                    {'key': 'solde', 'libelle': 'Solde',
                     'valeur': Decimal('70'), 'unite': echeancier.UNITE_PCT}]
        p1 = mock.patch.object(echeancier, 'tranches_normalisees',
                               return_value=tranches)
        p2 = mock.patch.object(echeancier, 'factures_actives',
                               return_value=[])
        with p1, p2:
            return echeancier.next_tranche(_devis(n), lignes=LIGNES, option='')

    def test_acompte_suit_le_total_x3(self):
        from decimal import ROUND_HALF_UP

        from apps.ventes.utils.options import option_totaux
        total_un = option_totaux(_devis(), option='', lignes=LIGNES)['ttc']
        attendu = (total_un * 3 * Decimal('0.3')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(self._tranche(3)['ttc'], attendu)
        self.assertNotEqual(self._tranche(None)['ttc'], attendu)


class TestPuissanceProjet(SimpleTestCase):
    def test_kwc_projet(self):
        from apps.ventes.selectors import puissance_kwc_projet
        self.assertEqual(puissance_kwc_projet(_devis(kwc=6.39)),
                         Decimal('6.39'))
        self.assertEqual(puissance_kwc_projet(_devis(3, kwc=6.39)),
                         Decimal('19.17'))
        self.assertIsNone(puissance_kwc_projet(_devis(3)))


class TestMultiVillaBout(TestCase):
    """Chemin réel : ORM + moteur PDF (DB — tourne en CI)."""

    def setUp(self):
        from apps.ventes.tests.test_qj29_multivilla import (
            make_client, make_company, make_user,
        )
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, etude, ref):
        from apps.ventes.tests.test_qj29_multivilla import _produit
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('5'), created_by=self.user,
            etude_params=etude)
        for desig, qty, pu in [('Onduleur réseau 8kW', '1', '14000'),
                               ('Panneau mono 550W', '10', '1400')]:
            LigneDevis.objects.create(
                devis=devis,
                produit=_produit(self.company, desig,
                                 f'{ref[-6:]}-{desig[:8]}', pu),
                designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), remise=Decimal('0'))
        return Devis.objects.get(pk=devis.pk)

    def test_pdf_pas_double_echelle_et_erp_suit_le_x3(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.builder import display_totals
        from apps.ventes.utils.options import option_totaux
        un = self._devis({'scenario': 'Sans batterie'}, 'DEV-XN-1')
        trois = self._devis({'scenario': 'Sans batterie',
                             'nombre_proprietes': 3}, 'DEV-XN-3')
        d1, d3 = build_quote_data(un), build_quote_data(trois)
        # Le document d'UNE villa est identique : pas de ×N² dans le PDF.
        self.assertEqual(d3['totaux_all']['ttc'], d1['totaux_all']['ttc'])
        self.assertEqual(d3['display_total_unitaire'], d1['display_total'])
        self.assertAlmostEqual(d3['totaux_multi']['all']['ttc'],
                               d1['totaux_all']['ttc'] * 3, places=2)
        # L'ERP facture le ×N imprimé, au centime.
        self.assertEqual(trois.total_ttc, un.total_ttc * 3)
        self.assertEqual(option_totaux(trois)['ttc'], un.total_ttc * 3)
        self.assertAlmostEqual(float(trois.total_ttc),
                               d3['display_total_multi'], places=2)
        self.assertAlmostEqual(display_totals(trois)['total'],
                               d3['display_total_multi'], places=2)
        self.assertEqual(display_totals(un)['total'], d1['display_total'])

    def test_prix_par_kwc_sur_le_kwc_projet(self):
        un = self._devis({'puissance_kwc': 5.5}, 'DEV-XN-K1')
        trois = self._devis({'puissance_kwc': 5.5, 'nombre_proprietes': 3},
                            'DEV-XN-K3')
        un.prix_par_kwc = None
        un.save()
        trois.prix_par_kwc = None
        trois.save()
        # TTC ×3 ÷ kWc ×3 = le même prix au kWc (jamais gonflé ×N).
        self.assertIsNotNone(un.prix_par_kwc)
        self.assertEqual(trois.prix_par_kwc, un.prix_par_kwc)

    def test_facture_consolidee_suit_le_x3(self):
        """Critique 30/09 — la facture consolidée (``consolider_factures``)
        reprend elle aussi chaque quantité ×N, comme la facture de BC."""
        from apps.ventes.domain.encaissements import consolider_factures
        from apps.ventes.models import Devis, FactureSource
        un = self._devis({'scenario': 'Sans batterie'}, 'DEV-XN-C1')
        trois = self._devis({'scenario': 'Sans batterie',
                             'nombre_proprietes': 3}, 'DEV-XN-C3')
        Devis.objects.filter(pk__in=[un.pk, trois.pk]).update(
            statut=Devis.Statut.ACCEPTE)
        facture = consolider_factures(
            company=self.company, devis_ids=[un.pk, trois.pk],
            user=self.user, created_by=self.user)
        sources = {s.devis_id: s.sous_total_ht
                   for s in FactureSource.objects.filter(facture=facture)}
        self.assertEqual(sources[trois.pk], sources[un.pk] * 3)
        qtes = sorted(lf.quantite for lf in facture.lignes.filter(
            source_devis=trois))
        self.assertEqual(qtes, [Decimal('3'), Decimal('30')])
