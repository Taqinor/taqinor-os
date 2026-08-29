"""QJR49 — ``domain/argent.py`` : la façade et ses vues NOMMÉES.

CE QUE CES TESTS TIENNENT.

1. **La forme est celle du contrat PACT10** ``contract_samples/devis_totaux.json``
   — clés et ordre de dérivation, entrées ``tva_par_taux`` en ``{taux, base,
   montant}``.
2. **``Vue.BRUT`` est le calcul d'HIER, conservé et NOMMÉ** : somme des lignes,
   remise par ligne honorée, ``remise_globale`` IGNORÉE, et sur un devis
   mono-taux la formule d'origine ``HT × taux`` SANS arrondi (là où le noyau
   canonique quantifie au centime). C'est ce qui rendait QJR50 sans effet sur
   les chiffres. **QJR51/D2 a ensuite basculé ``Devis.total_*`` sur
   ``Vue.NET``** : BRUT n'est donc plus l'ancre du modèle — sur un devis remisé
   ou mono-taux les deux DOIVENT diverger, et les tests pinnent chaque chaîne
   sur sa propre valeur dérivée.
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
    """``Vue.BRUT`` = le calcul d'HIER, conservé et NOMMÉ.

    QJR51 / décision fondateur D2 (29/08/2026) — L'ANCRE A BOUGÉ. Cette classe
    a été écrite pour QJR50, qui branchait ``Devis.total_*`` sur ``Vue.BRUT``
    « au bit » ; QJR51 les a basculées sur ``Vue.NET`` (remise globale honorée,
    option effective). Comparer BRUT à ``Devis.total_*`` ne prouve donc plus
    l'identité de BRUT : sur un devis remisé, ou mono-taux, les deux DOIVENT
    diverger. Les deux tests concernés pinnent désormais les DEUX chaînes,
    chacune sur sa propre valeur dérivée — c'est plus fort que l'égalité
    d'hier, pas plus faible.
    """

    def test_mono_taux_sans_remise(self):
        """Mono-taux : BRUT applique la formule d'origine (HT × taux, AUCUN
        arrondi), le noyau canonique quantifie au centime.

        Cette divergence est DOCUMENTÉE dans ``argent._totaux_brut`` — elle est
        la raison d'être de la vue BRUT (« passer par le noyau ferait bouger
        des montants, ce que QJR50 interdit »). Dérivation : 9 × 1 166,67 +
        14 000 = 24 500,03 HT ; TVA 20 % = **4 900,006** en BRUT, **4 900,01**
        une fois quantifiée par la chaîne canonique que lit ``total_tva``.
        """
        devis = self._devis('qjr49-brut1')
        self._ligne(devis, 'Panneau 550 W', 9, 1166.67)
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000)
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.BRUT)
        # Sans remise, le HT ne peut pas diverger : les deux chaînes partent
        # de la même somme de lignes.
        self.assertEqual(vue.ht_brut, Decimal('24500.03'))
        self.assertEqual(vue.ht_brut, devis.total_ht)
        # BRUT — la formule d'hier, non arrondie.
        self.assertEqual(vue.tva, Decimal('4900.006'))
        self.assertEqual(vue.ttc, Decimal('29400.036'))
        # NET (ce que lit le modèle depuis QJR51) — quantifiée au centime.
        self.assertEqual(devis.total_tva, Decimal('4900.01'))
        self.assertEqual(devis.total_ttc, Decimal('29400.04'))
        # …et l'écart reste STRICTEMENT sous le centime : c'est un arrondi,
        # jamais deux arithmétiques qui partiraient l'une de l'autre.
        self.assertLess(abs(devis.total_tva - vue.tva), Decimal('0.01'))

    def test_la_remise_globale_est_ignoree_par_la_vue_brut(self):
        """BRUT ignore ``remise_globale`` — et depuis QJR51 le modèle, lui, la
        HONORE : 10 000 HT ; BRUT = 10 000 + 2 000 = **12 000** ; NET =
        9 000 + 1 800 = **10 800,00**. C'est exactement le changement assumé
        par la décision D2, pinné des deux côtés.
        """
        devis = self._devis('qjr49-brut2', remise=Decimal('10'))
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.BRUT)
        self.assertEqual(vue.remise, Decimal('0'))
        self.assertEqual(vue.ht_net, vue.ht_brut)
        self.assertEqual(vue.ttc, Decimal('12000'))
        # Le modèle passe par Vue.NET : la remise est appliquée.
        self.assertEqual(devis.total_ttc, Decimal('10800.00'))
        self.assertEqual(totaux(devis, vue=Vue.NET).ttc, devis.total_ttc)

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


class DelegationDesProprietesTests(_ArgentBase):
    """QJR50 — ``Devis.total_*`` DÉLÈGUENT à la façade, sans changer un chiffre.

    Aucune assertion de montant du dépôt n'a été touchée par QJR50 : ces tests
    disent pourquoi — la vue BRUT reproduit la chaîne d'hier, y compris sa forme
    de sortie.
    """

    def test_tva_par_taux_garde_sa_forme_historique(self):
        """Les consommateurs (UBL, PDF facture, exports DGI/FEC) lisent
        ``base_ht`` : la propriété retraduit, elle ne renomme rien chez eux."""
        devis = self._devis('qjr50-forme')
        self._ligne(devis, 'Panneau 550 W', 10, 1000, taux_tva=Decimal('20'))
        self._ligne(devis, 'Pose', 1, 8000, taux_tva=Decimal('10'))
        devis = Devis.objects.get(pk=devis.pk)
        paniers = devis.tva_par_taux
        self.assertIsInstance(paniers, list)
        for panier in paniers:
            with self.subTest(taux=panier['taux']):
                self.assertEqual(set(panier), {'taux', 'base_ht', 'montant'})

    def test_les_proprietes_lisent_la_vue_net(self):
        """QJR51/D2 — la bascule est ici, et nulle part ailleurs."""
        devis = self._devis('qjr50-brut', remise=Decimal('15'))
        self._ligne(devis, 'Panneau 550 W', 11, 1166.67)
        self._ligne(devis, 'Pose', 1, 7000, taux_tva=Decimal('10'))
        devis = Devis.objects.get(pk=devis.pk)
        vue = totaux(devis, vue=Vue.NET)
        self.assertEqual(devis.total_ht, vue.ht_net)
        self.assertEqual(devis.total_tva, vue.tva)
        self.assertEqual(devis.total_ttc, vue.ttc)

    def test_le_total_ttc_reste_la_somme_ht_plus_tva(self):
        devis = self._devis('qjr50-somme')
        self._ligne(devis, 'Panneau 550 W', 9, 1166.67)
        devis = Devis.objects.get(pk=devis.pk)
        self.assertEqual(devis.total_ttc, devis.total_ht + devis.total_tva)

    def test_un_devis_sans_ligne_ne_leve_pas(self):
        devis = self._devis('qjr50-vide')
        self.assertEqual(devis.total_ht, 0)
        self.assertEqual(devis.total_ttc, devis.total_tva)

    def test_la_vue_brut_reutilise_un_prefetch(self):
        """NPLUS1 — la vue BRUT lit ``lignes.all()`` sans ``select_related``,
        donc RÉUTILISE le ``prefetch_related('lignes')`` de la liste des
        devis. Épinglé ici parce qu'un ``select_related`` y ferait un N+1."""
        devis = self._devis('qjr50-prefetch')
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        prefetche = Devis.objects.prefetch_related('lignes').get(pk=devis.pk)
        with self.assertNumQueries(0):
            self.assertEqual(totaux(prefetche, vue=Vue.BRUT).ttc,
                             Decimal('12000'))

    def test_la_vue_net_reutilise_aussi_un_prefetch(self):
        """NPLUS1 (29/08/2026) — MÊME GARDE POUR LA VUE NET, qui est celle que
        ``Devis.total_ttc`` lit depuis la décision D2.

        La bascule QJR51 avait fait payer DEUX requêtes par devis à toute liste
        préchargée (« 23 (5 leads) → 33 (10 leads) » sur ``LeadViewSet``) :
        ``deux_options_declarees`` sondait ``lignes.exclude(variante='')
        .exists()`` et la façade rechargeait ``lignes.select_related('produit')``
        — deux formes qui CLONENT le queryset et jettent le cache de prefetch.
        Un devis mono-option n'a aucun filtre d'option à appliquer, donc aucun
        besoin du produit : il doit se lire à ZÉRO requête, exactement comme la
        vue BRUT au-dessus."""
        devis = self._devis('qjr51-prefetch')
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        prefetche = Devis.objects.prefetch_related('lignes').get(pk=devis.pk)
        with self.assertNumQueries(0):
            self.assertEqual(totaux(prefetche, vue=Vue.NET).ttc,
                             Decimal('12000'))
            self.assertEqual(prefetche.total_ttc, Decimal('12000'))


class BasculeNetTests(_ArgentBase):
    """QJR51 / décision fondateur D2 — ``Devis.total_*`` passent au NET.

    Changement de comportement ASSUMÉ : le reporting, le Kanban et le CA d'un
    devis remisé BAISSENT (ils étaient faux). Ce qui est tenu ici :
    le devis et la facture qu'il engendre cessent de se contredire, un devis à
    deux options ne rend plus la somme des deux, et un devis SANS remise ni
    seconde option ne bouge PAS d'un centime.
    """

    def test_un_devis_sans_remise_ni_option_ne_bouge_pas(self):
        devis = self._devis('qjr51-neutre')
        self._ligne(devis, 'Panneau 550 W', 10, 1200)
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000)
        devis = Devis.objects.get(pk=devis.pk)
        brut = totaux(devis, vue=Vue.BRUT)
        self.assertEqual(devis.total_ttc, brut.ttc)
        self.assertEqual(devis.total_ht, brut.ht_brut)

    def test_la_tva_est_desormais_reconciliee_au_centime(self):
        """LE SEUL écart d'un devis SANS remise ni seconde option : la chaîne
        canonique RÉCONCILIE la TVA au centime (c'est ce que la FACTURE fait
        déjà), là où ``tva_buckets`` laissait passer des millièmes en
        mono-taux. Le devis et sa facture s'accordent donc au centime — c'est
        exactement l'objet de D2, et l'API rendait déjà 2 décimales."""
        devis = self._devis('qjr51-centime')
        self._ligne(devis, 'Panneau 550 W', 9, 1166.67)
        devis = Devis.objects.get(pk=devis.pk)
        self.assertEqual(devis.total_tva, Decimal('2100.01'))
        self.assertEqual(devis.total_tva, option_totaux(devis)['tva'])
        self.assertEqual(devis.total_tva.as_tuple().exponent, -2)

    def test_un_devis_remise_honore_sa_remise_globale(self):
        devis = self._devis('qjr51-remise', remise=Decimal('10'))
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        self.assertEqual(devis.total_ht, Decimal('9000.00'))
        self.assertEqual(devis.total_ttc, Decimal('10800.00'))
        # Et il BAISSE par rapport au brut d'hier — c'est le changement assumé.
        self.assertLess(devis.total_ttc, totaux(devis, vue=Vue.BRUT).ttc)

    def test_le_total_du_devis_egale_la_chaine_de_ses_factures(self):
        """``option_totaux`` est ce que l'échéancier / la facture consomment :
        le devis et sa facture cessent de se contredire."""
        devis = self._devis('qjr51-facture', remise=Decimal('12.5'))
        self._ligne(devis, 'Panneau 550 W', 14, 1166.67)
        self._ligne(devis, 'Pose', 1, 9000, taux_tva=Decimal('10'))
        devis = Devis.objects.get(pk=devis.pk)
        attendu = option_totaux(devis)
        self.assertEqual(devis.total_ht, attendu['ht'])
        self.assertEqual(devis.total_tva, attendu['tva'])
        self.assertEqual(devis.total_ttc, attendu['ttc'])

    def test_un_devis_a_deux_options_ne_somme_plus_les_deux(self):
        devis = self._devis('qjr51-deux')
        self._ligne(devis, 'Panneau 550 W', 12, 1200, variante='sans')
        self._ligne(devis, 'Onduleur réseau 5 kW', 1, 9000, variante='sans')
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000, variante='avec')
        self._ligne(devis, 'Batterie 10 kWh', 1, 25000, variante='avec')
        devis = Devis.objects.get(pk=devis.pk)
        somme_des_deux = totaux(devis, vue=Vue.BRUT).ttc
        self.assertLess(devis.total_ttc, somme_des_deux)
        self.assertEqual(devis.total_ttc,
                         totaux(devis, vue=Vue.PAR_OPTION,
                                option=AVEC_BATTERIE).ttc)

    def test_apres_acceptation_le_total_suit_l_option_acceptee(self):
        devis = self._devis('qjr51-acceptee')
        self._ligne(devis, 'Panneau 550 W', 12, 1200, variante='sans')
        self._ligne(devis, 'Onduleur réseau 5 kW', 1, 9000, variante='sans')
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000, variante='avec')
        self._ligne(devis, 'Batterie 10 kWh', 1, 25000, variante='avec')
        Devis.objects.filter(pk=devis.pk).update(option_acceptee=SANS_BATTERIE)
        devis = Devis.objects.get(pk=devis.pk)
        self.assertEqual(devis.total_ttc,
                         totaux(devis, vue=Vue.PAR_OPTION,
                                option=SANS_BATTERIE).ttc)

    def test_le_taux_de_remise_cpq_n_applique_plus_deux_fois_la_remise(self):
        """QJR51 — retrait d'une COMPENSATION : ``cpq.taux_remise_global``
        ré-appliquait ``remise_globale`` parce que ``total_ht`` l'ignorait."""
        from apps.cpq.services import taux_remise_global

        devis = self._devis('qjr51-cpq', remise=Decimal('10'))
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        # brut = 10 000 (aucune remise de ligne), net = 9 000 → 10 %, pas 19 %.
        self.assertEqual(taux_remise_global(devis), Decimal('10.00'))

    def test_le_taux_de_remise_cpq_compare_la_meme_option(self):
        devis = self._devis('qjr51-cpq2')
        self._ligne(devis, 'Panneau 550 W', 12, 1200, variante='sans')
        self._ligne(devis, 'Onduleur réseau 5 kW', 1, 9000, variante='sans')
        self._ligne(devis, 'Onduleur hybride 5 kW', 1, 14000, variante='avec')
        self._ligne(devis, 'Batterie 10 kWh', 1, 25000, variante='avec')
        devis = Devis.objects.get(pk=devis.pk)
        from apps.cpq.services import taux_remise_global
        # Aucune remise nulle part : le taux DOIT être 0, jamais l'écart entre
        # la somme des deux options et une seule.
        self.assertEqual(taux_remise_global(devis), Decimal('0.00'))
