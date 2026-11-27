"""Profil société (revue) — les lectures du moteur de devis et des PDF ne
créent jamais le profil.

``CompanyProfile.get`` est un get_or_create : sur une société SANS profil,
accepter un devis (``accept_devis`` → ``build_quote_data`` pour détecter les
options, puis le rendu de l'exemplaire signé) écrivait la ligne au fuseau par
défaut, et toutes les simulations de calepinage de la société devenaient
périmées. Chaque lecteur passe par ``CompanyProfile.lire`` (lecture qui
n'écrit pas). Sans base : ``get`` lève, ``lire`` sert l'objet par défaut NON
enregistré, aux valeurs que l'ancien code lisait sur la ligne fraîchement
créée.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.parametres.models import CompanyProfile


def _societe():
    return SimpleNamespace(pk=7, id=7, nom='Sans Profil')


class LecturesMoteurSansCreationTests(SimpleTestCase):

    def _sans_get(self, lecture):
        """Lance ``lecture(company, defaut)`` avec ``get`` interdit ; rend
        ``(résultat, company, defaut, mock lire)``."""
        company = _societe()
        defaut = CompanyProfile(company_id=None, nom=company.nom)
        with mock.patch.object(CompanyProfile, 'get',
                               side_effect=AssertionError('get')) as get, \
                mock.patch.object(CompanyProfile, 'lire',
                                  return_value=defaut) as lu:
            resultat = lecture(company)
        get.assert_not_called()
        self.assertTrue(lu.called)
        servi = lu.call_args.kwargs.get('company') or lu.call_args.args[0]
        self.assertIs(servi, company)
        return resultat, defaut

    def test_langue_de_sortie_repli_societe(self):
        from apps.parametres.i18n_resolver import (
            LANGUE_PAR_DEFAUT, _valide, resolve_langue_sortie)
        langue, defaut = self._sans_get(
            lambda c: resolve_langue_sortie(client=None, company=c))
        attendu = _valide(defaut.langue_repli) or LANGUE_PAR_DEFAUT
        self.assertEqual(langue, attendu)

    def test_delais_commerciaux_du_devis(self):
        from apps.ventes.quote_engine import conditions_commerciales as cc

        def lecture(c):
            devis = SimpleNamespace(company=c, date_validite=None,
                                    date_creation=None)
            try:
                return cc.delais_validite_et_kit(
                    _blob={}, _items_libres=[], avec_items=False,
                    avec_lignes=False, avec_ok=False, client=None,
                    deux_options=False, devis=devis, has_batterie=False,
                    has_reseau=False, option_servie='', opts={},
                    sans_items=True, scenario='')
            except Exception:  # noqa: BLE001 — seul l'accès au profil compte
                return None
        self._sans_get(lecture)

    def test_logo_du_rendu_de_l_affiche(self):
        from apps.ventes.quote_engine.conditions_commerciales import (
            _entreprise_avec_logo)
        entreprise = {'nom': 'Sans Profil'}
        servi, defaut = self._sans_get(lambda c: _entreprise_avec_logo(
            SimpleNamespace(company=c), entreprise,
            {'_embed_roof_render': True}))
        self.assertFalse(defaut.logo_key)
        self.assertEqual(servi, entreprise)

    def test_duree_de_validite_du_devis(self):
        from apps.ventes.utils.expiry import _validity_days
        jours, defaut = self._sans_get(_validity_days)
        self.assertEqual(jours, int(defaut.quote_validity_days or 30))

    def test_contexte_societe_des_pdf(self):
        from apps.ventes.utils.pdf import _COULEUR_DEFAUT, _company_context
        ctx, defaut = self._sans_get(lambda c: _company_context(company=c))
        self.assertEqual(ctx['entreprise_nom'], 'Sans Profil')
        self.assertEqual(ctx['couleur_principale'],
                         defaut.couleur_principale or _COULEUR_DEFAUT)
        self.assertEqual(ctx['entreprise_ice'], defaut.ice)
        self.assertIsNone(ctx['logo_uri'])
        self.assertIsNone(ctx['signature_uri'])

    def test_identite_vendeur_figee(self):
        from apps.ventes.utils.pdf import identite_vendeur_courante
        identite, defaut = self._sans_get(identite_vendeur_courante)
        self.assertEqual(identite['entreprise_nom'], 'Sans Profil')
        self.assertEqual(identite['logo_key'], defaut.logo_key or '')
        self.assertEqual(identite['signature_key'], '')

    def test_nom_de_fichier_des_telechargements(self):
        from apps.ventes.utils.filenames import _company_slug
        slug, defaut = self._sans_get(_company_slug)
        self.assertEqual(slug, 'Sans-Profil')

    def test_pack_pays_de_la_facture_electronique(self):
        from apps.ventes.quote_engine.facturx import pack_pays_de
        pack, defaut = self._sans_get(pack_pays_de)
        self.assertEqual(pack, str(getattr(defaut, 'pack_pays', '') or '').upper())

    def test_dgi_profil_vendeur_export_et_validation(self):
        from apps.ventes.dgi import dgi_export, dgi_validator
        for module in (dgi_export, dgi_validator):
            servi, defaut = self._sans_get(
                lambda c, m=module: m._resolve_profile(
                    SimpleNamespace(company=c), None))
            self.assertIs(servi, defaut)

    def test_arrondi_caisse_et_credit_hold(self):
        from decimal import Decimal
        from apps.ventes.domain.encaissements import proposer_arrondi_caisse
        from apps.ventes.domain.recouvrement import verifier_credit_hold
        res, defaut = self._sans_get(lambda c: proposer_arrondi_caisse(
            SimpleNamespace(company=c), "virement", reste=Decimal("10")))
        self.assertFalse(res["applicable"])
        self.assertEqual(res["pas"], defaut.arrondi_caisse or Decimal("0"))
        res, defaut = self._sans_get(
            lambda c: verifier_credit_hold(SimpleNamespace(company=c)))
        self.assertIsNone(res)
        self.assertFalse(defaut.credit_hold_actif)

    def test_encaissement_et_anomalies_d_emission(self):
        # Fonctions à base de données : on inspecte leur code (les rejouer
        # demande la base, CI).
        import inspect
        from apps.ventes.domain import encaissements, recouvrement
        for fonction in (encaissements.encaisser_sur_facture,
                         recouvrement.anomalies_emission_facture):
            source = inspect.getsource(fonction)
            self.assertNotIn("CompanyProfile.get(", source)
            self.assertIn("CompanyProfile.lire(", source)
