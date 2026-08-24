"""L-ECO — le bloc public ``economies_periodes`` : décliner, jamais calculer.

Ce module épingle la moitié PURE (aucune base, aucun réseau) : les invariants
qui rendent le bandeau honnête.

  * l'ANNÉE est la SOMME des douze mois — c'est ce qui rend vraie la phrase
    « sur l'année : X DH », et c'est aussi ce qui prouve qu'elle NE BOUGE PAS
    quand le visiteur change de saison ;
  * le JOUR TYPE d'un mois est ce mois ÷ ses jours réels, à l'arrondi près ;
  * la SAISON est la somme de ses mois, son jour type la moyenne PONDÉRÉE par
    les jours ;
  * chaque valeur servie est une PASSE DIRECTE : les mois viennent du bloc
    ``economies_mensuelles`` déjà construit, le retour sur investissement de
    ``quote.roi_s``/``roi_a`` déjà servi — aucune troisième définition ;
  * omission PROPRE quand une période n'est pas dérivable.
"""
from django.test import SimpleTestCase

from apps.parametres.pvgis_profils import JOURS_PAR_MOIS
from apps.ventes.economies_periodes import construire_economies_periodes
from apps.ventes.etude_horaire import saison_du_mois

# Douze valeurs volontairement TOUTES DIFFÉRENTES : une somme correcte ne peut
# pas être obtenue par hasard, et un mois recopié à la place d'un autre se voit.
_SANS = [310, 340, 470, 560, 660, 690, 700, 620, 540, 430, 320, 300]
_AVEC = [420, 450, 590, 700, 810, 850, 860, 770, 670, 550, 430, 400]


def _economies(sans=None, avec=None):
    return {
        'sans': list(_SANS if sans is None else sans),
        'avec': None if avec is None else list(avec),
        'total_sans': sum(_SANS if sans is None else sans),
        'total_avec': None if avec is None else sum(avec),
        'devise': 'MAD',
        'modele': 'horaire',
        'estimation': False,
        'note': 'Calculé heure par heure.',
    }


class PeriodesDerivationTest(SimpleTestCase):
    """Année, mois, jour type : une seule série, trois lectures."""

    def _bloc(self, **kwargs):
        data = kwargs.pop('data', {'roi_s': 7.24, 'roi_a': 9.8})
        etude = kwargs.pop('etude_params', {})
        return construire_economies_periodes(
            data, _economies(**kwargs), etude)

    def test_l_annee_est_exactement_la_somme_des_douze_mois(self):
        bloc = self._bloc(avec=_AVEC)
        for variante, serie in (('sans', _SANS), ('avec', _AVEC)):
            with self.subTest(variante=variante):
                mois = bloc[variante]['mois']
                self.assertEqual(len(mois), 12)
                self.assertEqual([m['mad'] for m in mois], serie)
                self.assertEqual(bloc[variante]['annuel_mad'], sum(serie))
                self.assertEqual(
                    bloc[variante]['annuel_mad'],
                    sum(m['mad'] for m in mois))

    def test_l_annee_ne_depend_pas_de_la_saison(self):
        """INVARIANCE : la somme des saisons retombe sur l'annuel, donc aucune
        saison ne peut faire bouger le chiffre ancré « sur l'année »."""
        bloc = self._bloc(avec=_AVEC)
        for variante in ('sans', 'avec'):
            with self.subTest(variante=variante):
                saisons = bloc[variante]['saisons']
                self.assertEqual(sorted(saisons),
                                 ['ete', 'hiver', 'mi_saison'])
                self.assertEqual(sum(s['mad'] for s in saisons.values()),
                                 bloc[variante]['annuel_mad'])
                self.assertEqual(sum(s['jours'] for s in saisons.values()),
                                 sum(JOURS_PAR_MOIS))

    def test_le_jour_type_multiplie_par_les_jours_redonne_le_mois(self):
        bloc = self._bloc()
        for entree in bloc['sans']['mois']:
            with self.subTest(mois=entree['mois']):
                self.assertEqual(entree['jours'],
                                 JOURS_PAR_MOIS[entree['mois'] - 1])
                # Écart d'ARRONDI seulement (le jour type est au centime),
                # jamais un écart de méthode.
                self.assertLessEqual(
                    abs(entree['jour_mad'] * entree['jours'] - entree['mad']),
                    entree['jours'] * 0.005 + 1e-9)

    def test_la_saison_de_chaque_mois_est_celle_du_moteur(self):
        bloc = self._bloc()
        for entree in bloc['sans']['mois']:
            with self.subTest(mois=entree['mois']):
                self.assertEqual(entree['saison'],
                                 saison_du_mois(entree['mois']))

    def test_le_jour_type_saisonnier_est_pondere_par_les_jours(self):
        """Jamais la moyenne des moyennes : un février de 28 jours ne pèse pas
        autant qu'un juillet de 31."""
        bloc = self._bloc()
        for saison, valeurs in bloc['sans']['saisons'].items():
            attendu_mad = sum(
                _SANS[m - 1] for m in range(1, 13) if saison_du_mois(m) == saison)
            attendu_jours = sum(
                JOURS_PAR_MOIS[m - 1] for m in range(1, 13)
                if saison_du_mois(m) == saison)
            with self.subTest(saison=saison):
                self.assertEqual(valeurs['mad'], attendu_mad)
                self.assertEqual(valeurs['jours'], attendu_jours)
                self.assertAlmostEqual(valeurs['jour_mad'],
                                       round(attendu_mad / attendu_jours, 2),
                                       places=9)


class RetourInvestissementTest(SimpleTestCase):
    """Aucune TROISIÈME définition du payback : passe directe de ``quote.roi``."""

    def test_la_valeur_servie_est_celle_du_payload(self):
        bloc = construire_economies_periodes(
            {'roi_s': 7.24, 'roi_a': 9.81}, _economies(avec=_AVEC), {})
        self.assertEqual(bloc['sans']['retour_investissement_ans'], 7.2)
        self.assertEqual(bloc['avec']['retour_investissement_ans'], 9.8)
        self.assertEqual(bloc['source_retour_investissement'], 'quote.roi')

    def test_un_retour_non_calcule_est_omis_jamais_zero(self):
        """Le moteur rend ``0.0`` quand il n'a PAS pu calculer un retour :
        « remboursé en 0 an » serait un mensonge, la clé disparaît."""
        for valeur in (0, 0.0, -3, None, 'sept', float('nan')):
            with self.subTest(valeur=valeur):
                bloc = construire_economies_periodes(
                    {'roi_s': valeur}, _economies(), {})
                self.assertNotIn('retour_investissement_ans', bloc['sans'])


class OmissionPropreTest(SimpleTestCase):
    """Rien de dérivable ⇒ rien de servi. Jamais un zéro, jamais un tiret."""

    def test_sans_bloc_mensuel_le_bandeau_entier_est_absent(self):
        for economies in (None, {}, {'sans': None}, {'sans': [1, 2, 3]},
                          {'sans': ['a'] * 12}, 'texte'):
            with self.subTest(economies=economies):
                self.assertIsNone(
                    construire_economies_periodes({}, economies, {}))

    def test_avec_batterie_suit_exactement_la_garde_du_bloc_mensuel(self):
        """``avec`` à ``None`` (option non réellement vendable) ⇒ AUCUN chiffre
        « avec batterie » dans le bandeau non plus."""
        bloc = construire_economies_periodes(
            {'roi_s': 8.0, 'roi_a': 11.0}, _economies(), {})
        self.assertIn('sans', bloc)
        self.assertNotIn('avec', bloc)

    def test_ne_leve_jamais(self):
        self.assertIsNone(
            construire_economies_periodes(None, {'sans': object()}, None))


class ProfilsParPeriodeTest(SimpleTestCase):
    """Le changement de profil rebascule sur des séries SERVEUR, pas sur un
    produit en croix côté page."""

    def _etude(self, **surcharges):
        profils = [
            {'occupation': 'presence_jour', 'est_profil_reel': True,
             'economies_mois_sans': list(_SANS),
             'economies_mois_avec': list(_AVEC)},
            {'occupation': 'absence_jour', 'est_profil_reel': False,
             'economies_mois_sans': [v - 40 for v in _SANS],
             'economies_mois_avec': [v - 30 for v in _AVEC]},
        ]
        profils[0].update(surcharges)
        return {'profils_comparatifs': {'profils': profils}}

    def test_chaque_profil_porte_ses_propres_periodes(self):
        bloc = construire_economies_periodes(
            {'roi_s': 7.0}, _economies(avec=_AVEC), self._etude())
        profils = bloc['profils']
        self.assertEqual([p['occupation'] for p in profils],
                         ['presence_jour', 'absence_jour'])
        self.assertTrue(profils[0]['est_profil_reel'])
        self.assertEqual(profils[0]['sans']['annuel_mad'], sum(_SANS))
        self.assertEqual(profils[1]['sans']['annuel_mad'],
                         sum(v - 40 for v in _SANS))
        # Les économies affichées CHANGENT vraiment avec la silhouette.
        self.assertNotEqual(profils[0]['sans']['annuel_mad'],
                            profils[1]['sans']['annuel_mad'])
        for profil in profils:
            self.assertEqual(
                profil['sans']['annuel_mad'],
                sum(m['mad'] for m in profil['sans']['mois']))

    def test_un_profil_sans_serie_mensuelle_est_absent(self):
        """Bloc antérieur à cette couche : on omet ce profil plutôt que de
        l'afficher avec les chiffres d'un autre."""
        etude = self._etude()
        etude['profils_comparatifs']['profils'][0].pop('economies_mois_sans')
        bloc = construire_economies_periodes(
            {'roi_s': 7.0}, _economies(avec=_AVEC), etude)
        self.assertEqual([p['occupation'] for p in bloc['profils']],
                         ['absence_jour'])

    def test_sans_avec_vendable_aucun_profil_ne_porte_de_avec(self):
        bloc = construire_economies_periodes(
            {'roi_s': 7.0}, _economies(), self._etude())
        for profil in bloc['profils']:
            self.assertNotIn('avec', profil)

    def test_aucun_bloc_profils_quand_rien_n_est_persiste(self):
        for etude in (None, {}, {'profils_comparatifs': {}},
                      {'profils_comparatifs': {'profils': []}}):
            with self.subTest(etude=etude):
                bloc = construire_economies_periodes(
                    {'roi_s': 7.0}, _economies(), etude)
                self.assertNotIn('profils', bloc)
