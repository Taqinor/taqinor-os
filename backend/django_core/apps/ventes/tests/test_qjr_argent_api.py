"""QJR49 — ``domain/argent.py`` : la façade et ses vues NOMMÉES.

CE QUE CES TESTS TIENNENT.

1. **La forme est celle du contrat PACT10** ``contract_samples/devis_totaux.json``
   — clés et ordre de dérivation, entrées ``tva_par_taux`` en ``{taux, base,
   montant}``.
2. **``Vue.BRUT`` est le comportement d'AUJOURD'HUI, au bit** : elle rend
   exactement ce que ``Devis.total_ht/total_tva/total_ttc`` rendent — y compris
   sur le devis mono-taux, où le noyau canonique et ``tva_buckets`` divergent
   d'un arrondi. C'est ce qui rend QJR50 sans effet sur les chiffres.
3. **``Vue.NET`` / ``Vue.PAR_OPTION`` égalent ``option_totaux`` AU CENTIME** —
   la façade NOMME, elle ne recalcule pas.
4. **``ttc_affiche``** vaut ``ttc`` partout : aucune vue n'arrondit aujourd'hui.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_argent_api -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.domain.argent import Totaux, Vue, totaux
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, option_totaux,
)

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'devis_totaux.json')


class _ArgentBase(TestCase):
    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, remise=Decimal('0'), taux=Decimal('20')):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        return Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, statut='brouillon',
            taux_tva=taux, remise_globale=remise,
            mode_installation='residentiel', etude_params={})

    def _ligne(self, devis, designation, quantite, prix, **extra):
        return LigneDevis.objects.create(
            devis=devis, designation=designation,
            quantite=Decimal(str(quantite)), prix_unitaire=Decimal(str(prix)),
            remise=Decimal('0'), **extra)


class FormeDuContratTests(_ArgentBase):
    """PACT10 — la façade rend la forme committée, jamais une inventée."""

    def test_les_champs_sont_ceux_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        attendus = [c for c in contrat['exemple']
                    if c not in ('vue', 'option')]
        champs = [f for f in Totaux.__dataclass_fields__]
        self.assertEqual(sorted(champs), sorted(attendus))

    def test_l_entree_tva_porte_taux_base_montant(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        attendus = set(contrat['exemple']['tva_par_taux'][0])
        devis = self._devis('qjr49-forme')
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        vue = totaux(devis, vue=Vue.NET)
        self.assertEqual(set(vue.tva_par_taux[0]), attendus)

    def test_la_vue_est_obligatoire_et_nommee(self):
        devis = self._devis('qjr49-vue')
        with self.assertRaises(TypeError):
            totaux(devis)
        with self.assertRaises(TypeError):
            totaux(devis, vue='net')

    def test_les_totaux_sont_geles(self):
        devis = self._devis('qjr49-gel')
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        vue = totaux(devis, vue=Vue.BRUT)
        with self.assertRaises(Exception):
            vue.ttc = Decimal('1')


class VueBrutIdentiqueTests(_ArgentBase):
    """``Vue.BRUT`` = ce que ``Devis.total_*`` rend AUJOURD'HUI, au bit."""

    def test_mono_taux_sans_remise(self):
        devis = self._devis('qjr49-brut1')
        self._ligne(devis, 'Panneau 550 W', 9, 1166.67)
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000)
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.BRUT)
        self.assertEqual(vue.ht_brut, devis.total_ht)
        self.assertEqual(vue.tva, devis.total_tva)
        self.assertEqual(vue.ttc, devis.total_ttc)

    def test_la_remise_globale_est_ignoree_par_la_vue_brut(self):
        devis = self._devis('qjr49-brut2', remise=Decimal('10'))
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.BRUT)
        self.assertEqual(vue.remise, Decimal('0'))
        self.assertEqual(vue.ht_net, vue.ht_brut)
        self.assertEqual(vue.ttc, devis.total_ttc)

    def test_taux_mixtes(self):
        devis = self._devis('qjr49-brut3')
        self._ligne(devis, 'Panneau 550 W', 10, 1000,
                    taux_tva=Decimal('20'))
        self._ligne(devis, 'Pose', 1, 8000, taux_tva=Decimal('10'))
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.BRUT)
        self.assertEqual(vue.tva, devis.total_tva)
        self.assertEqual(vue.ttc, devis.total_ttc)
        self.assertEqual([e['taux'] for e in vue.tva_par_taux],
                         [Decimal('10'), Decimal('20')])

    def test_les_lignes_section_et_optionnelles_sont_exclues(self):
        devis = self._devis('qjr49-brut4')
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        LigneDevis.objects.create(
            devis=devis, designation='Équipements', type_ligne='section')
        self._ligne(devis, 'Extension garantie', 1, 5000, optionnelle=True)
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.BRUT)
        self.assertEqual(vue.ht_brut, Decimal('10000'))
        self.assertEqual(vue.ht_brut, devis.total_ht)


class VueNetEtParOptionTests(_ArgentBase):
    """La façade NOMME la chaîne canonique — elle ne la recalcule pas."""

    def test_net_egale_option_totaux_au_centime(self):
        devis = self._devis('qjr49-net', remise=Decimal('12.5'))
        self._ligne(devis, 'Panneau 550 W', 14, 1166.67)
        self._ligne(devis, 'Pose', 1, 9000, taux_tva=Decimal('10'))
        devis = Devis.objects.get(pk=devis.pk)
        attendu = option_totaux(devis)
        vue = totaux(devis, vue=Vue.NET)
        self.assertEqual(vue.ht_brut, attendu['ht_brut'])
        self.assertEqual(vue.remise, attendu['remise'])
        self.assertEqual(vue.ht_net, attendu['ht'])
        self.assertEqual(vue.tva, attendu['tva'])
        self.assertEqual(vue.ttc, attendu['ttc'])

    def test_la_remise_globale_est_honoree_par_la_vue_net(self):
        devis = self._devis('qjr49-net2', remise=Decimal('10'))
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.NET)
        self.assertEqual(vue.ht_brut, Decimal('10000.00'))
        self.assertEqual(vue.remise, Decimal('1000.00'))
        self.assertEqual(vue.ht_net, Decimal('9000.00'))
        self.assertEqual(vue.ttc, Decimal('10800.00'))

    def test_par_option_egale_option_totaux_de_la_meme_option(self):
        devis = self._devis('qjr49-opt', remise=Decimal('5'))
        self._ligne(devis, 'Panneau 550 W', 12, 1200, variante='sans')
        self._ligne(devis, 'Onduleur réseau 5 kW', 1, 9000, variante='sans')
        self._ligne(devis, 'Panneau 550 W', 16, 1200, variante='avec')
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000, variante='avec')
        self._ligne(devis, 'Batterie 10 kWh', 1, 25000, variante='avec')
        devis = Devis.objects.get(pk=devis.pk)
        for option in (SANS_BATTERIE, AVEC_BATTERIE):
            with self.subTest(option=option):
                attendu = option_totaux(devis, option)
                vue = totaux(devis, vue=Vue.PAR_OPTION, option=option)
                self.assertEqual(vue.ttc, attendu['ttc'])
                self.assertEqual(vue.ht_net, attendu['ht'])

    def test_les_deux_options_ne_sont_jamais_additionnees(self):
        devis = self._devis('qjr49-somme')
        self._ligne(devis, 'Panneau 550 W', 12, 1200, variante='sans')
        self._ligne(devis, 'Onduleur réseau 5 kW', 1, 9000, variante='sans')
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000, variante='avec')
        self._ligne(devis, 'Batterie 10 kWh', 1, 25000, variante='avec')
        devis = Devis.objects.get(pk=devis.pk)
        net = totaux(devis, vue=Vue.NET)
        brut = totaux(devis, vue=Vue.BRUT)
        self.assertLess(net.ht_net, brut.ht_brut)
        self.assertEqual(net.ttc, Decimal(str(option_totaux(devis)['ttc'])))

    def test_les_lignes_fournies_evitent_une_requete(self):
        devis = self._devis('qjr49-lignes')
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        chargees = list(devis.lignes.all())
        self.assertEqual(totaux(devis, vue=Vue.NET, lignes=chargees),
                         totaux(devis, vue=Vue.NET))


class TtcAfficheTests(_ArgentBase):
    """``ttc_affiche`` est le SEUL slot d'arrondi d'affichage — et il est vide."""

    def test_aucune_vue_n_arrondit_aujourd_hui(self):
        devis = self._devis('qjr49-affiche', remise=Decimal('7'))
        self._ligne(devis, 'Panneau 550 W', 13, 1166.67)
        devis = Devis.objects.get(pk=devis.pk)
        for vue in (Vue.BRUT, Vue.NET, Vue.PAR_OPTION, Vue.AFFICHAGE):
            with self.subTest(vue=vue):
                calcule = totaux(devis, vue=vue)
                self.assertEqual(calcule.ttc_affiche, calcule.ttc)

    def test_affichage_porte_le_meme_argent_que_net(self):
        devis = self._devis('qjr49-affiche2', remise=Decimal('7'))
        self._ligne(devis, 'Panneau 550 W', 13, 1166.67)
        devis = Devis.objects.get(pk=devis.pk)
        self.assertEqual(totaux(devis, vue=Vue.AFFICHAGE),
                         totaux(devis, vue=Vue.NET))
