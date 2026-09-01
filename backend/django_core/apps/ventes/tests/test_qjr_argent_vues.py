# -*- coding: utf-8 -*-
"""QJR242 — la façade monnaie n'a plus que DEUX vues vivantes.

``Vue.BRUT`` et ``Vue.PAR_OPTION`` ont été SUPPRIMÉES (arbitrage « câbler ou
supprimer » = SUPPRIMER) :

* ``BRUT`` n'existait que pour rendre la bascule QJR51 (``Devis.total_*`` du
  brut vers le net) équivalente à un changement d'UN mot. Le mot a été changé
  le 29/08 ; aucun appelant de production ne subsistait.
* ``PAR_OPTION`` était CASSÉE : ``totaux(vue=PAR_OPTION, option=X, lignes=Y)``
  jetait l'option nommée EN SILENCE et rendait les totaux de tout le jeu de
  lignes fourni — la seule chose qu'elle existait pour empêcher. La question
  « totaux d'un panier d'option » est posée en plusieurs endroits, et tous
  passent par ``utils.options.option_totaux``.

CE FICHIER EST LA GARDE : le grep, exécuté, et la preuve qu'AUCUNE valeur
monétaire n'a bougé (``NET`` et ``AFFICHAGE`` sont intouchées).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_argent_vues -v 2
"""
import inspect
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.ventes.domain import argent as A
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import option_totaux

User = get_user_model()

#: ``apps/ventes`` — le SEUL endroit où ces noms ont jamais vécu (la façade,
#: ses appelants et ses tests). Scanner plus large ne prouverait rien de plus
#: et rendrait la garde lente.
RACINE = Path(__file__).resolve().parents[1]

#: Les deux noms qui ne doivent plus exister nulle part en code vivant.
DISPARUS = ('Vue.BRUT', 'Vue.PAR_OPTION', '_totaux_brut')


class LaFacadeNAPlusQueDeuxVues(SimpleTestCase):

    def test_l_enumeration_est_reduite_a_deux(self):
        self.assertEqual(sorted(v.name for v in A.Vue), ['AFFICHAGE', 'NET'])

    def test_les_deux_noms_ont_disparu_de_l_enumeration(self):
        for nom in ('BRUT', 'PAR_OPTION'):
            with self.subTest(nom=nom):
                self.assertFalse(hasattr(A.Vue, nom))

    def test_la_branche_brut_a_disparu_de_la_porte(self):
        source = inspect.getsource(A.totaux)
        self.assertNotIn('Vue.BRUT', source)
        self.assertNotIn('_totaux_brut', source)

    def test_le_message_de_refus_nomme_les_deux_vues_restantes(self):
        with self.assertRaises(TypeError) as leve:
            A.totaux(object(), vue='net')
        message = str(leve.exception)
        self.assertIn('NET', message)
        self.assertIn('AFFICHAGE', message)
        self.assertNotIn('BRUT', message)
        self.assertNotIn('PAR_OPTION', message)

    def test_le_grep_est_vide_dans_le_code_vivant(self):
        """Aucun appel résiduel : on scanne le CODE, jamais les commentaires."""
        residus = []
        for chemin in RACINE.rglob('*.py'):
            if '__pycache__' in chemin.parts:
                continue
            for numero, ligne in enumerate(
                    chemin.read_text(encoding='utf-8').splitlines(), start=1):
                nue = ligne.strip()
                if nue.startswith('#') or nue.startswith('*'):
                    continue
                for nom in DISPARUS:
                    # Un nom cité dans une docstring l'est entre doubles
                    # accents reST — c'est de la prose, pas un appel.
                    if nom in nue and '``' not in nue and "'" not in nue:
                        residus.append('%s:%s %s' % (chemin.name, numero, nue))
        self.assertEqual(residus, [], residus)


class AucuneValeurMonetaireNAChange(TestCase):
    """``NET`` et ``AFFICHAGE`` rendent EXACTEMENT ce qu'elles rendaient."""

    def setUp(self):
        from authentication.models import Company

        self.company = Company.objects.get_or_create(
            slug='qjr242-co', defaults={'nom': 'QJR242 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR242')

    def _devis(self, reference, *, remise=Decimal('0')):
        devis = Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20'), remise_globale=remise,
            mode_installation='residentiel', etude_params={})
        for designation, quantite, prix, taux in (
                ('Panneau 550 W', 14, '1166.67', None),
                ('Pose', 1, '9000', Decimal('10'))):
            LigneDevis.objects.create(
                devis=devis, designation=designation,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal(prix), remise=Decimal('0'),
                taux_tva=taux)
        return Devis.objects.get(pk=devis.pk)

    def test_net_egale_toujours_option_totaux_au_centime(self):
        devis = self._devis('DEV-QJR242-01', remise=Decimal('12.5'))
        attendu = option_totaux(devis)
        vue = A.totaux(devis, vue=A.Vue.NET)
        self.assertEqual(vue.ht_brut, attendu['ht_brut'])
        self.assertEqual(vue.remise, attendu['remise'])
        self.assertEqual(vue.ht_net, attendu['ht'])
        self.assertEqual(vue.tva, attendu['tva'])
        self.assertEqual(vue.ttc, attendu['ttc'])

    def test_affichage_porte_le_meme_argent_que_net(self):
        devis = self._devis('DEV-QJR242-02', remise=Decimal('7'))
        self.assertEqual(A.totaux(devis, vue=A.Vue.AFFICHAGE),
                         A.totaux(devis, vue=A.Vue.NET))

    def test_les_proprietes_du_modele_sont_intactes(self):
        devis = self._devis('DEV-QJR242-03', remise=Decimal('10'))
        vue = A.totaux(devis, vue=A.Vue.NET)
        self.assertEqual(devis.total_ht, vue.ht_net)
        self.assertEqual(devis.total_tva, vue.tva)
        self.assertEqual(devis.total_ttc, vue.ttc)
