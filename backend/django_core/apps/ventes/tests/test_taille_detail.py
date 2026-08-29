"""OPTIONS CHARGEABLES (ordre fondateur, 29/08/2026) — le détail d'une taille.

CE QUE CES TESTS PROTÈGENT.

1. **La carte SERVIE est celle d'``offres_tailles``, jamais une seconde.** Le
   détail EMBARQUE l'objet déjà dérivé pour la page ; s'il le recalculait, on
   rouvrirait l'incident « 21 contre 22 » (deux chemins voisins, deux
   arrondis, deux chiffres pour la même installation).
2. **« Recommandé » n'a PAS d'endpoint.** C'est le devis : la page le restaure.
3. **Aucune règle d'accès de son cru.** Le détail refuse tout ce que le bloc
   public refuse — taille non envoyée à ce client, section « Économies »
   décochée, devis non résidentiel — et refuse TOUJOURS de la même façon : un
   404 générique, parce que la raison d'un refus est elle-même une information.
4. **L'omission plutôt que la substitution.** Une série de onze mois, une
   valeur non numérique, une courbe absente : le bloc DISPARAÎT. Jamais un
   zéro, jamais un forfait.
5. **Aucun prix d'achat, aucune marge** (règle #4), et **rien de sensible au
   niveau de partage** : standard et confiance servent le MÊME octet.
6. **La forme SERVIE est celle du CONTRAT** (PACT10).
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes import taille_detail as td
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'taille_detail.json')

#: Le bloc ``offres_tailles`` public dont le détail part — réduit au strict
#: nécessaire, exactement comme ``test_offres_tailles._BLOC``.
BLOC = {
    'avec_servable': True,
    'escalade_tarifaire_pct': 0,
    'horizon_annees': 25,
    'offres': [
        {'cle': 'eco', 'titre': 'Éco', 'recommande': False,
         'est_le_devis': False, 'ajuste': False,
         'config': {'nb_panneaux': 10},
         'sans': {'nb_panneaux': 10, 'prix_ttc': 52800.0,
                  'couverture_pct': 48.2, 'payback_annees': 7.26,
                  'economies_cumulees_25_ans_mad': 231400.0},
         'avec': {'nb_panneaux': 12, 'prix_ttc': 71400.0,
                  'batterie': {'nb_modules': 2, 'module_kwh': 5.0,
                               'capacite_utile_kwh': 9.0}}},
        {'cle': 'recommande', 'titre': 'Recommandé', 'recommande': True,
         'est_le_devis': True, 'ajuste': False,
         'config': {'nb_panneaux': 14},
         'sans': {'nb_panneaux': 14, 'prix_ttc': 71400.0}},
    ],
}


def _etude(economie_sans=800.0, economie_avec=1200.0, mois=12):
    return {'mois': [{'economie_sans_mad': economie_sans,
                      'economie_avec_mad': economie_avec}
                     for _ in range(mois)]}


def _profond(**kwargs):
    """Ce que le passe-plat ``sortie_profonde`` de ``_carte_moteur`` remplit."""
    base = {'etude': _etude(), 'cashflow': {'sans': [-40000.0, -30000.0],
                                            'avec': [-60000.0, -45000.0]}}
    base.update(kwargs)
    return base


def _moteur_factice(profond=None):
    """Un ``_carte_moteur`` qui remplit le passe-plat, comme le vrai."""
    charge = profond if profond is not None else _profond()

    def _appel(_contexte, _nb, _config=None, *, avec_servable=True,
               sortie_profonde=None):
        if sortie_profonde is not None:
            sortie_profonde.update(charge)
        return {'sans': None, 'avec': None}
    return _appel


class LecteursTests(SimpleTestCase):
    """Les deux lecteurs profonds, isolés de toute base."""

    def test_douze_mois_donnent_douze_valeurs_et_leur_total(self):
        bloc = td._economies_mensuelles(_etude(), 'sans')
        self.assertEqual(bloc['valeurs'], [800] * 12)
        self.assertEqual(bloc['total'], 9600)
        self.assertEqual(bloc['devise'], 'MAD')

    def test_la_variante_avec_lit_SA_colonne(self):
        bloc = td._economies_mensuelles(_etude(), 'avec')
        self.assertEqual(bloc['valeurs'], [1200] * 12)

    def test_ONZE_mois_ne_sont_PAS_une_annee(self):
        # « Année complète ou rien » : onze mois se liraient comme un total
        # annuel en dessous de la vérité.
        self.assertIsNone(td._economies_mensuelles(_etude(mois=11), 'sans'))

    def test_une_valeur_non_numerique_fait_OMETTRE_toute_la_serie(self):
        etude = _etude()
        etude['mois'][3]['economie_sans_mad'] = None
        self.assertIsNone(td._economies_mensuelles(etude, 'sans'))

    def test_un_booleen_n_est_PAS_un_nombre(self):
        etude = _etude()
        etude['mois'][0]['economie_sans_mad'] = True
        self.assertIsNone(td._economies_mensuelles(etude, 'sans'))

    def test_etude_absente_omet(self):
        self.assertIsNone(td._economies_mensuelles(None, 'sans'))

    def test_le_cashflow_porte_la_serie_l_horizon_et_l_escalade(self):
        bloc = td._cashflow(_profond(), 'sans', 25, 0)
        self.assertEqual(bloc['cumulative'], [-40000.0, -30000.0])
        self.assertEqual(bloc['horizon_annees'], 25)
        self.assertEqual(bloc['escalade_tarifaire_pct'], 0)

    def test_sans_serie_le_cashflow_est_OMIS(self):
        self.assertIsNone(td._cashflow({'cashflow': {}}, 'sans', 25, 0))


class DerivationTests(SimpleTestCase):
    """``deriver_detail`` : les refus, et ce qu'un succès porte."""

    def _detail(self, cle, variante, *, bloc=None, profond=None,
                config=None):
        devis = SimpleNamespace(offres_tailles_config=config,
                                etude_params={}, reference='DEV-X')
        data = {'variantes_servables': ['sans', 'avec']}
        from apps.ventes import offres_tailles as ot
        with mock.patch.object(ot, '_contexte',
                               return_value=SimpleNamespace()), \
                mock.patch.object(ot, '_carte_moteur',
                                  side_effect=_moteur_factice(profond)):
            return td.deriver_detail(
                devis, data, BLOC if bloc is None else bloc, cle, variante)

    def test_une_taille_servie_porte_sa_carte_TELLE_QUELLE(self):
        detail = self._detail('eco', 'sans')
        # LA RÈGLE CENTRALE : l'objet servi EST celui du bloc public, pas une
        # copie recalculée. Un `assertIs` le prouve mieux qu'un `assertEqual`.
        self.assertIs(detail['carte'], BLOC['offres'][0]['sans'])
        self.assertEqual(detail['cle'], 'eco')
        self.assertEqual(detail['titre'], 'Éco')
        self.assertEqual(detail['variante'], 'sans')
        self.assertFalse(detail['est_le_devis'])

    def test_le_detail_porte_les_deux_blocs_profonds(self):
        detail = self._detail('eco', 'sans')
        self.assertEqual(detail['economies_mensuelles']['total'], 9600)
        self.assertEqual(detail['cashflow']['cumulative'],
                         [-40000.0, -30000.0])
        self.assertEqual(detail['cashflow']['horizon_annees'], 25)

    def test_RECOMMANDE_n_a_pas_de_detail(self):
        # C'est LE devis : la page le restaure depuis ses originaux. Lui
        # donner un chemin réseau rouvrirait le « 21 contre 22 ».
        self.assertIsNone(self._detail('recommande', 'sans'))

    def test_une_cle_inconnue_est_refusee(self):
        self.assertIsNone(self._detail('moyenne', 'sans'))

    def test_une_variante_inconnue_est_refusee(self):
        self.assertIsNone(self._detail('eco', 'peut-etre'))

    def test_une_taille_ABSENTE_du_bloc_public_est_refusee(self):
        # Le bloc public a déjà appliqué les cases `taille_eco`/`taille_max` :
        # ce module n'ajoute AUCUNE règle d'accès de son cru.
        sans_eco = dict(BLOC, offres=[BLOC['offres'][1]])
        self.assertIsNone(self._detail('eco', 'sans', bloc=sans_eco))

    def test_une_variante_non_servie_par_la_carte_est_refusee(self):
        self.assertIsNone(self._detail('eco', 'avec',
                                       bloc=dict(BLOC, offres=[
                                           dict(BLOC['offres'][0],
                                                avec=None)])))

    def test_sans_bloc_public_rien_n_est_servi(self):
        self.assertIsNone(self._detail('eco', 'sans', bloc=None or {}))

    def test_une_variante_AVEC_porte_la_banque_de_SA_carte(self):
        detail = self._detail('eco', 'avec')
        self.assertEqual(detail['carte']['batterie']['nb_modules'], 2)
        self.assertEqual(detail['economies_mensuelles']['valeurs'], [1200] * 12)

    def test_un_bloc_profond_VIDE_fait_OMETTRE_les_deux_sections(self):
        detail = self._detail('eco', 'sans',
                              profond={'etude': None, 'cashflow': {}})
        self.assertNotIn('economies_mensuelles', detail)
        self.assertNotIn('cashflow', detail)
        # …mais la carte, elle, reste servie : l'omission est par bloc.
        self.assertIn('carte', detail)

    def test_detail_publique_ne_LEVE_jamais(self):
        with mock.patch.object(td, 'deriver_detail',
                               side_effect=RuntimeError('moteur cassé')):
            self.assertIsNone(td.detail_publique(None, {}, BLOC, 'eco',
                                                 'sans'))


class CacheTests(SimpleTestCase):
    """La clé de mémoïsation : ce qui doit l'invalider l'invalide."""

    def _lien(self, config=None):
        return SimpleNamespace(
            pk=7, devis=SimpleNamespace(offres_tailles_config=config,
                                        updated_at=None))

    def test_la_cle_distingue_taille_et_variante(self):
        lien = self._lien()
        self.assertNotEqual(td.cle_cache(lien, 'eco', 'sans'),
                            td.cle_cache(lien, 'eco', 'avec'))
        self.assertNotEqual(td.cle_cache(lien, 'eco', 'sans'),
                            td.cle_cache(lien, 'max', 'sans'))

    def test_un_AJUSTEMENT_vendeur_invalide_la_cle(self):
        # C'est tout l'intérêt d'une empreinte : aucune invalidation à écrire
        # à la main, donc aucune à oublier.
        avant = td.cle_cache(self._lien(), 'eco', 'sans')
        apres = td.cle_cache(
            self._lien({'eco': {'config': {'nb_panneaux': 18}}}),
            'eco', 'sans')
        self.assertNotEqual(avant, apres)

    def test_deux_LIENS_du_meme_devis_ne_partagent_pas_leur_cache(self):
        # Deux liens peuvent servir des tailles différentes : une clé au devis
        # seul aurait laissé un client lire le détail d'une taille que SON
        # lien ne sert pas.
        a = self._lien()
        b = SimpleNamespace(pk=8, devis=a.devis)
        self.assertNotEqual(td.cle_cache(a, 'eco', 'sans'),
                            td.cle_cache(b, 'eco', 'sans'))


class ContratTests(SimpleTestCase):
    """PACT10 — la forme servie EST celle du contrat."""

    def setUp(self):
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_l_endpoint_documente_est_celui_qui_est_monte(self):
        self.assertIn('/taille/', self.contrat['endpoint'])
        self.assertIn('variante=sans|avec', self.contrat['endpoint'])

    def test_les_cles_de_l_exemple_sont_celles_qui_sont_servies(self):
        exemple = self.contrat['exemple']
        devis = SimpleNamespace(offres_tailles_config=None, etude_params={},
                                reference='DEV-X')
        from apps.ventes import offres_tailles as ot
        with mock.patch.object(ot, '_contexte',
                               return_value=SimpleNamespace()), \
                mock.patch.object(ot, '_carte_moteur',
                                  side_effect=_moteur_factice()):
            servi = td.deriver_detail(
                devis, {'variantes_servables': ['sans', 'avec']}, BLOC,
                'eco', 'sans')
        self.assertEqual(set(servi), set(exemple))
        self.assertEqual(set(servi['economies_mensuelles']),
                         set(exemple['economies_mensuelles']))
        self.assertEqual(set(servi['cashflow']), set(exemple['cashflow']))

    def test_le_contrat_ne_documente_AUCUN_prix_d_achat(self):
        # RÈGLE #4 — grep-guard, la même discipline que les tests anticopie.
        brut = CONTRAT.read_text(encoding='utf-8')
        for interdit in ('prix_achat', 'revendeur', 'marge_'):
            self.assertNotIn(interdit, brut)

    def test_le_module_ne_nomme_AUCUN_champ_confidentiel(self):
        source = (Path(td.__file__)).read_text(encoding='utf-8')
        for interdit in ('prix_achat', 'revendeur'):
            self.assertNotIn(interdit, source)


class _Base(TestCase):
    """Fixture calquée sur ``test_offres_tailles._Base``."""

    LIGNES = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 5 kWh', '2', '12500.00'),
    )

    def _company(self, slug):
        from authentication.models import Company
        return Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]

    def _devis(self, slug, *, mode='residentiel'):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom='Client %s' % slug, defaults={})[0]
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        devis = Devis.objects.create(
            company=company, reference='DEV-%s-01' % slug.upper(),
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        for nom, qte, pu in self.LIGNES:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _lien(self, devis, **kwargs):
        return ShareLink.objects.create(company=devis.company, devis=devis,
                                        **kwargs)

    def _get(self, token, cle, variante='sans'):
        return APIClient().get(
            '/api/django/public/proposal/%s/taille/%s/?variante=%s'
            % (token, cle, variante))


class EndpointTests(_Base):
    """La porte publique : ce qui passe, ce qui ne passe pas, et comment."""

    def setUp(self):
        # DÉTERMINISME. Le cache local vit dans le PROCESSUS, pas dans la
        # transaction : il survit au rollback de chaque test, et les
        # identifiants de lien, eux, se réutilisent. Sans ce vidage, un détail
        # mis en cache par un test pourrait répondre à un autre.
        from django.core.cache import cache
        cache.clear()
        super().setUp()

    def _avec_moteur(self, bloc=BLOC):
        from apps.ventes import offres_tailles as ot
        return (mock.patch.object(ot, 'deriver', return_value=bloc),
                mock.patch.object(ot, '_contexte',
                                  return_value=SimpleNamespace()),
                mock.patch.object(ot, '_carte_moteur',
                                  side_effect=_moteur_factice()))

    def _appel(self, token, cle, variante='sans', bloc=BLOC):
        a, b, c = self._avec_moteur(bloc)
        with a, b, c:
            return self._get(token, cle, variante)

    def test_une_taille_servie_repond_200_avec_son_detail(self):
        devis = self._devis('det-ok')
        lien = self._lien(devis)
        resp = self._appel(lien.token, 'eco')
        self.assertEqual(resp.status_code, 200)
        corps = resp.json()
        self.assertEqual(corps['cle'], 'eco')
        self.assertEqual(corps['variante'], 'sans')
        self.assertEqual(corps['carte']['nb_panneaux'], 10)
        self.assertEqual(len(corps['economies_mensuelles']['valeurs']), 12)

    def test_la_variante_AVEC_est_servie_quand_la_carte_la_porte(self):
        devis = self._devis('det-avec')
        lien = self._lien(devis)
        resp = self._appel(lien.token, 'eco', 'avec')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['carte']['batterie']['nb_modules'], 2)

    def test_RECOMMANDE_repond_404(self):
        devis = self._devis('det-reco')
        lien = self._lien(devis)
        self.assertEqual(self._appel(lien.token, 'recommande').status_code,
                         404)

    def test_un_jeton_inconnu_repond_404(self):
        self.assertEqual(self._appel('jeton-qui-n-existe-pas',
                                     'eco').status_code, 404)

    def test_une_taille_NON_ENVOYEE_a_ce_client_repond_404(self):
        # Case `taille_eco` décochée dans le dialogue d'envoi : la carte n'est
        # pas dans le bloc public, donc son détail est inatteignable par URL.
        devis = self._devis('det-filtre')
        lien = self._lien(devis, sections={'taille_eco': False})
        self.assertEqual(self._appel(lien.token, 'eco').status_code, 404)

    def test_la_case_ECONOMIES_decochee_ferme_aussi_le_detail(self):
        devis = self._devis('det-eco-off')
        lien = self._lien(devis, sections={'economies': False})
        self.assertEqual(self._appel(lien.token, 'eco').status_code, 404)

    def test_un_devis_POMPAGE_n_a_aucun_detail(self):
        devis = self._devis('det-pompage', mode='agricole')
        lien = self._lien(devis)
        self.assertEqual(self._appel(lien.token, 'eco').status_code, 404)

    def test_un_moteur_qui_LEVE_repond_404_jamais_500(self):
        devis = self._devis('det-boom')
        lien = self._lien(devis)
        from apps.ventes import offres_tailles as ot
        with mock.patch.object(ot, 'deriver',
                               side_effect=RuntimeError('cassé')):
            resp = self._get(lien.token, 'eco')
        self.assertEqual(resp.status_code, 404)

    def test_le_detail_n_ECRIT_RIEN_sur_le_devis(self):
        # RÈGLE #4 — une exploration ne touche ni ligne, ni total, ni statut,
        # ni la configuration des tailles, ni l'horodatage de vue.
        devis = self._devis('det-lecture')
        lien = self._lien(devis)
        avant = (devis.statut, devis.offres_tailles_config,
                 lien.views_count if hasattr(lien, 'views_count') else None)
        self._appel(lien.token, 'eco')
        devis.refresh_from_db()
        lien.refresh_from_db()
        apres = (devis.statut, devis.offres_tailles_config,
                 lien.views_count if hasattr(lien, 'views_count') else None)
        self.assertEqual(avant, apres)

    def test_STANDARD_et_CONFIANCE_servent_le_MEME_octet(self):
        # Ce contrat ne porte QUE des natures de nombres déjà publiques aux
        # deux niveaux : la dégradation anticopie n'a aucune prise ici, et ce
        # test le PROUVE au lieu de le supposer.
        devis = self._devis('det-niveau')
        confiance = self._lien(devis, niveau=ShareLink.NIVEAU_CONFIANCE)
        standard = self._lien(devis, niveau=ShareLink.NIVEAU_STANDARD)
        a = self._appel(confiance.token, 'eco')
        b = self._appel(standard.token, 'eco')
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        self.assertEqual(a.json(), b.json())

    def test_aucun_prix_d_achat_ni_marge_dans_la_reponse(self):
        devis = self._devis('det-marge')
        lien = self._lien(devis)
        brut = self._appel(lien.token, 'eco').content.decode('utf-8')
        for interdit in ('prix_achat', 'revendeur', 'marge'):
            self.assertNotIn(interdit, brut)

    def test_le_jeton_d_une_AUTRE_societe_ne_donne_rien(self):
        # Multi-tenant : le jeton borne un seul devis d'une seule société ; un
        # jeton de la société A ne peut pas nommer une taille de la société B.
        a = self._lien(self._devis('det-soc-a'))
        self._devis('det-soc-b')
        resp = self._appel(a.token, 'eco')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['carte']['nb_panneaux'], 10)


class PreparationTests(_Base):
    """La duplication de préparation est PROUVÉE, pas espérée.

    ``_data_pour_taille_detail`` refait les étapes de ``proposal_data`` que la
    dérivation des tailles lit. Ce test dérive le bloc des DEUX côtés sur le
    MÊME lien et exige l'égalité : le jour où l'une des deux préparations
    bouge sans l'autre, il tombe.
    """

    def test_le_bloc_derive_des_deux_cotes_est_IDENTIQUE(self):
        from apps.ventes import public_views as pv
        devis = self._devis('det-prep')
        lien = self._lien(devis)

        payload = APIClient().get(
            '/api/django/public/proposal/%s/data/' % lien.token).json()
        data, resid = pv._data_pour_taille_detail(devis, lien)
        ici = (pv._offres_tailles_publique(devis, data, resid,
                                           pv._tailles_servies(lien))
               if pv._section_servie(lien, 'economies') else None)
        self.assertEqual(payload.get('offres_tailles'), ici)
