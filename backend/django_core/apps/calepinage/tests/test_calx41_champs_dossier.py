"""CALX41 — enregistrer les champs à compléter d'un dossier réglementaire.

Ce qui est prouvé ici, SANS BASE (``SimpleTestCase``) :
1. un champ ABSENT du gabarit est refusé EN LE NOMMANT (l'ERP n'ajoute aucun
   champ à un formulaire officiel qu'il n'a pas reçu) ;
2. une valeur vide EFFACE la saisie au lieu d'inventer un défaut ;
3. un champ enregistré QUITTE « à compléter » et rejoint « déjà saisis », si
   bien que ``avancement_du_dossier`` en tient compte ;
4. la route existe, en POST, gardée par ``PeutGererCalepinage``, et chaque
   refus sort en 400 SOUS le champ qu'il nomme.
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.permissions import PeutGererCalepinage
from apps.calepinage.services.reglementaire import (
    ChampsDossierInvalides, avancement_du_dossier, composer_dossier,
    enregistrer_champs, _valider_champs_saisis,
)
from apps.calepinage.views.calepinages import CalepinageViewSet
from apps.calepinage.views.reglementaire import (
    MESSAGE_SANS_DESIGNATION, champs_dossier,
)

MODULE = 'apps.calepinage.views.reglementaire'

CHAMPS_GABARIT = [
    {'code': 'reference_dossier', 'libelle': 'Référence du dossier',
     'type': 'texte', 'obligatoire': True},
    {'code': 'puissance_declaree', 'libelle': 'Puissance déclarée',
     'type': 'nombre', 'obligatoire': True},
    {'code': 'nom_deposant', 'libelle': 'Nom du déposant',
     'type': 'texte', 'obligatoire': False},
]


def _entree(saisis=None):
    return {
        'id': 7, 'gabarit_id': 3, 'intitule': "Dossier d'essai",
        'gabarit': {'present': True, 'fichier': 'gabarit.pdf'},
        'pieces_attendues': [
            {'code': 'plan', 'intitule': 'Plan', 'obligatoire': True},
        ],
        'champs': [dict(champ) for champ in CHAMPS_GABARIT],
        'champs_saisis': dict(saisis or {}),
        'pieces_jointes': {'plan': {'fichier': 'plan.pdf'}},
    }


class _Gabarit:
    def __init__(self, champs=None):
        self.champs = champs if champs is not None else [
            dict(champ) for champ in CHAMPS_GABARIT]


class _Dossier:
    """Doublure de ``DossierReglementaire`` : aucune écriture en base."""

    def __init__(self, champs_saisis=None, gabarit=None, pk=7):
        self.pk = pk
        self.gabarit = gabarit or _Gabarit()
        self.champs_saisis = dict(champs_saisis or {})
        self.sauve = []

    def save(self, update_fields=None):
        self.sauve.append(tuple(update_fields or ()))


class _Requete:
    def __init__(self, data=None):
        self.data = data if data is not None else {}
        self.user = object()


class _Vue:
    def get_object(self):
        return object()


def _agregat(dossiers, message=None):
    return {'calepinage': 1, 'pays': 'MA', 'gabarits_deposes': len(dossiers),
            'message_aucun_gabarit': message, 'dossiers': list(dossiers)}


class ValidationTest(SimpleTestCase):
    """Le gabarit FAIT FOI, et le refus NOMME le champ."""

    def test_un_champ_inconnu_du_gabarit_est_refuse_en_le_nommant(self):
        with self.assertRaises(ChampsDossierInvalides) as refus:
            _valider_champs_saisis(CHAMPS_GABARIT, {'numero_cerfa': '14 000'})

        self.assertEqual(refus.exception.champ, 'numero_cerfa')
        self.assertIn('numero_cerfa', str(refus.exception))
        # Le message dit AUSSI ce que le gabarit déclare vraiment.
        self.assertIn('reference_dossier', str(refus.exception))

    def test_un_nombre_qui_n_en_est_pas_un_est_refuse_sous_son_champ(self):
        with self.assertRaises(ChampsDossierInvalides) as refus:
            _valider_champs_saisis(CHAMPS_GABARIT,
                                   {'puissance_declaree': 'beaucoup'})

        self.assertEqual(refus.exception.champ, 'puissance_declaree')
        self.assertIn('Puissance déclarée', str(refus.exception))

    def test_un_nombre_ecrit_a_la_francaise_est_normalise_pas_refuse(self):
        valide = _valider_champs_saisis(CHAMPS_GABARIT,
                                        {'puissance_declaree': '12,5'})

        self.assertEqual(valide, {'puissance_declaree': 12.5})

    def test_une_valeur_composee_est_refusee_sous_son_champ(self):
        with self.assertRaises(ChampsDossierInvalides) as refus:
            _valider_champs_saisis(CHAMPS_GABARIT,
                                   {'reference_dossier': {'x': 1}})

        self.assertEqual(refus.exception.champ, 'reference_dossier')

    def test_une_saisie_qui_n_est_pas_un_objet_est_refusee(self):
        with self.assertRaises(ChampsDossierInvalides) as refus:
            _valider_champs_saisis(CHAMPS_GABARIT, ['reference_dossier'])

        self.assertEqual(refus.exception.champ, 'champs')

    def test_une_valeur_vide_efface_au_lieu_d_inventer_un_defaut(self):
        self.assertEqual(_valider_champs_saisis(CHAMPS_GABARIT,
                                                {'nom_deposant': '   '}),
                         {'nom_deposant': None})


class EnregistrementTest(SimpleTestCase):
    """La saisie est FUSIONNÉE, jamais écrasée en silence."""

    def test_la_saisie_est_ecrite_sur_le_dossier(self):
        dossier = _Dossier()

        enregistrer_champs(dossier, {'reference_dossier': 'DP-2026-01'})

        self.assertEqual(dossier.champs_saisis,
                         {'reference_dossier': 'DP-2026-01'})
        self.assertEqual(dossier.sauve, [('champs_saisis',)])

    def test_un_champ_absent_de_l_envoi_garde_sa_valeur(self):
        dossier = _Dossier({'nom_deposant': 'Société d essai'})

        enregistrer_champs(dossier, {'reference_dossier': 'DP-2026-01'})

        self.assertEqual(dossier.champs_saisis['nom_deposant'],
                         'Société d essai')

    def test_une_valeur_vide_efface_la_saisie(self):
        dossier = _Dossier({'nom_deposant': 'Société d essai'})

        enregistrer_champs(dossier, {'nom_deposant': ''})

        self.assertNotIn('nom_deposant', dossier.champs_saisis)

    def test_rien_n_est_ecrit_quand_la_saisie_est_refusee(self):
        dossier = _Dossier({'nom_deposant': 'Société d essai'})

        with self.assertRaises(ChampsDossierInvalides):
            enregistrer_champs(dossier, {'numero_cerfa': '14 000'})

        self.assertEqual(dossier.sauve, [])
        self.assertEqual(dossier.champs_saisis,
                         {'nom_deposant': 'Société d essai'})


class AvancementTest(SimpleTestCase):
    """Un champ enregistré quitte « à compléter » — et l'avancement le voit."""

    def test_le_champ_saisi_change_de_liste(self):
        avant = composer_dossier(_entree(), {})
        apres = composer_dossier(
            _entree({'reference_dossier': 'DP-2026-01'}), {})

        self.assertEqual([c['code'] for c in avant['champs_a_completer']],
                         ['reference_dossier', 'puissance_declaree',
                          'nom_deposant'])
        self.assertEqual(avant['champs_saisis'], [])
        self.assertEqual([c['code'] for c in apres['champs_a_completer']],
                         ['puissance_declaree', 'nom_deposant'])
        self.assertEqual([c['code'] for c in apres['champs_saisis']],
                         ['reference_dossier'])
        # La valeur publiée est CELLE de l'utilisateur, jamais un défaut.
        self.assertEqual(apres['champs_saisis'][0]['valeur'], 'DP-2026-01')
        self.assertEqual(apres['champs_saisis'][0]['libelle'],
                         'Référence du dossier')

    def test_l_avancement_tient_compte_des_champs_saisis(self):
        avant = avancement_du_dossier(composer_dossier(_entree(), {}))
        apres = avancement_du_dossier(composer_dossier(
            _entree({'reference_dossier': 'DP-2026-01'}), {}))

        self.assertEqual(avant['champs_a_completer'], 3)
        self.assertEqual(avant['champs_saisis'], 0)
        self.assertEqual(apres['champs_a_completer'], 2)
        self.assertEqual(apres['champs_saisis'], 1)

    def test_les_deux_champs_obligatoires_saisis_rendent_generable(self):
        dossier = composer_dossier(_entree({
            'reference_dossier': 'DP-2026-01', 'puissance_declaree': 12.5,
        }), {})

        self.assertTrue(dossier['peut_generer'])
        self.assertEqual(dossier['motif_non_generable'], '')


class RoutageTest(SimpleTestCase):
    """La route est découverte par le routeur, avec sa garde."""

    def _action(self):
        for methode in CalepinageViewSet.get_extra_actions():
            if methode.url_path == 'champs-dossier':
                return methode
        return None

    def test_l_action_est_decouverte_en_post_et_gardee(self):
        methode = self._action()

        self.assertIsNotNone(methode)
        self.assertEqual(methode.mapping, {'post': 'champs_dossier'})
        self.assertEqual(methode.kwargs['permission_classes'],
                         [PeutGererCalepinage])
        self.assertEqual(champs_dossier.__name__, 'champs_dossier')
        self.assertIs(CalepinageViewSet.champs_dossier, champs_dossier)


class VueTest(SimpleTestCase):
    """Chaque refus sort SOUS le champ qu'il nomme, jamais en vrac."""

    def _compose(self):
        return composer_dossier(_entree(), {})

    def test_aucun_dossier_designe_le_dit_sous_le_champ_dossier(self):
        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([self._compose()])):
            reponse = champs_dossier(_Vue(), _Requete({'champs': {}}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'dossier': [MESSAGE_SANS_DESIGNATION]})

    def test_un_champ_inconnu_sort_en_400_sous_son_code(self):
        dossier = _Dossier()
        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([self._compose()])), \
                mock.patch(MODULE + '._dossier_en_base',
                           return_value=dossier):
            reponse = champs_dossier(_Vue(), _Requete({
                'dossier': 7, 'champs': {'numero_cerfa': '14 000'}}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data), ['numero_cerfa'])
        self.assertIn('numero_cerfa', reponse.data['numero_cerfa'][0])

    def test_la_saisie_acceptee_rend_l_agregat_recompose(self):
        dossier = _Dossier()
        agregat_apres = _agregat([composer_dossier(
            _entree({'reference_dossier': 'DP-2026-01'}), {})])
        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        side_effect=[_agregat([self._compose()]),
                                     agregat_apres]), \
                mock.patch(MODULE + '._dossier_en_base',
                           return_value=dossier):
            reponse = champs_dossier(_Vue(), _Requete({
                'dossier': 7,
                'champs': {'reference_dossier': 'DP-2026-01'}}))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data, agregat_apres)
        self.assertEqual(dossier.champs_saisis,
                         {'reference_dossier': 'DP-2026-01'})
