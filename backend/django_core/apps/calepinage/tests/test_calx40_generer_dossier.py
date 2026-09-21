"""CALX40 — la porte de génération d'un dossier réglementaire.

Ce qui est prouvé ici, SANS BASE (``SimpleTestCase``) : la route existe et
porte la bonne garde, et chacun des refus sort en 400 SOUS LE CHAMP qu'il
concerne, avec le motif du serveur — jamais un « non enregistré » générique.

Le service de production (``construire_pack_dossier``) a déjà ses propres
tests : il est ici REMPLACÉ par une doublure, parce que ce qu'on vérifie est
la PORTE (qui refuse quoi, et qui passe quoi au service), pas la fabrique.
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.permissions import PeutGererCalepinage
from apps.calepinage.services.reglementaire import (
    DossierRefuse, MESSAGE_AUCUN_GABARIT,
)
from apps.calepinage.views.calepinages import CalepinageViewSet
from apps.calepinage.views.reglementaire import (
    MESSAGE_SANS_DESIGNATION, generer_dossier,
)

MODULE = 'apps.calepinage.views.reglementaire'


class _Requete:
    """Le strict minimum d'une requête DRF pour cette vue."""

    def __init__(self, data=None):
        self.data = data if data is not None else {}
        self.user = object()


class _Dossier:
    """Doublure de ``DossierReglementaire`` : on n'écrit rien en base."""

    def __init__(self, pk=7):
        self.pk = pk
        self.document_id = None
        self.genere_le = None
        self.sauve = []

    def save(self, update_fields=None):
        self.sauve.append(tuple(update_fields or ()))


class _Vue:
    """Le ``self`` du viewset : la vue n'utilise que ``get_object()``."""

    def __init__(self, calepinage=None):
        self._calepinage = calepinage or object()

    def get_object(self):
        return self._calepinage


def _agregat(dossiers, message=None):
    return {'calepinage': 1, 'pays': 'MA', 'gabarits_deposes': len(dossiers),
            'message_aucun_gabarit': message, 'dossiers': list(dossiers)}


def _compose(**ecrase):
    compose = {
        'id': 7, 'gabarit_id': 3, 'intitule': "Dossier d'essai",
        'statut': 'complet', 'gabarit': {'present': True},
        'pieces': [], 'champs_a_completer': [],
        'peut_generer': True, 'motif_non_generable': '', 'genere_le': None,
    }
    compose.update(ecrase)
    return compose


class RoutageTest(SimpleTestCase):
    """La route est RÉELLEMENT découverte par le routeur, avec sa garde."""

    def _action(self):
        for methode in CalepinageViewSet.get_extra_actions():
            if methode.url_path == 'generer-dossier':
                return methode
        return None

    def test_l_action_est_decouverte_par_le_routeur(self):
        self.assertIsNotNone(
            self._action(),
            "« generer-dossier » n'est pas rattachée au CalepinageViewSet : "
            "le bouton de l'écran appellerait un chemin inexistant.")

    def test_elle_est_en_post_et_gardee_par_peut_gerer(self):
        methode = self._action()

        self.assertEqual(methode.mapping, {'post': 'generer_dossier'})
        self.assertEqual(methode.kwargs['permission_classes'],
                         [PeutGererCalepinage])

    def test_le_nom_de_l_attribut_est_celui_de_la_fonction(self):
        # DRF fige le nom de la méthode à la décoration : une greffe sous un
        # autre nom ferait disparaître la route.
        self.assertEqual(generer_dossier.__name__, 'generer_dossier')
        self.assertIs(CalepinageViewSet.generer_dossier, generer_dossier)


class RefusTest(SimpleTestCase):
    """Chaque refus NOMME son champ et recopie le motif du serveur."""

    def test_societe_sans_aucun_gabarit_refuse_en_nommant_le_gabarit(self):
        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([], MESSAGE_AUCUN_GABARIT)):
            reponse = generer_dossier(_Vue(), _Requete({'gabarit': 3}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'gabarit': [MESSAGE_AUCUN_GABARIT]})

    def test_aucun_dossier_designe_le_dit_sous_le_champ_dossier(self):
        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([_compose()])):
            reponse = generer_dossier(_Vue(), _Requete({}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'dossier': [MESSAGE_SANS_DESIGNATION]})

    def test_gabarit_declare_mais_non_depose_refuse_sous_gabarit(self):
        motif = "Le fichier de gabarit de la société n'a pas été déposé."
        compose = _compose(gabarit={'present': False}, peut_generer=False,
                           motif_non_generable=motif)

        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([compose])):
            reponse = generer_dossier(_Vue(), _Requete({'dossier': 7}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'gabarit': [motif]})

    def test_dossier_incomplet_refuse_avec_le_motif_du_serveur(self):
        motif = 'Champs obligatoires à compléter : Référence du dossier.'
        compose = _compose(peut_generer=False, motif_non_generable=motif)

        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([compose])):
            reponse = generer_dossier(_Vue(), _Requete({'dossier': 7}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'dossier': [motif]})

    def test_un_refus_du_service_sort_sous_le_code_de_sa_piece(self):
        refus = DossierRefuse("La pièce « Note de calcul » ne se rend pas.",
                              piece='note_calcul')

        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([_compose()])), \
                mock.patch(MODULE + '._dossier_en_base',
                           return_value=_Dossier()), \
                mock.patch(MODULE + '.construire_pack_dossier',
                           side_effect=refus):
            reponse = generer_dossier(_Vue(), _Requete({'dossier': 7}))

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, {'note_calcul': [str(refus)]})


class GenerationTest(SimpleTestCase):
    """Avec gabarit déposé : le document est composé et les pièces listées."""

    def _generer(self, dossier, pack, corps=None):
        with mock.patch(MODULE + '.dossiers_du_calepinage',
                        return_value=_agregat([_compose()])), \
                mock.patch(MODULE + '._dossier_en_base',
                           return_value=dossier), \
                mock.patch(MODULE + '.construire_pack_dossier',
                           return_value=pack) as fabrique:
            reponse = generer_dossier(_Vue(), _Requete(corps or {'dossier': 7}))
        return reponse, fabrique

    def test_le_document_et_les_pieces_sont_servis(self):
        dossier = _Dossier(pk=7)
        pack = {'document': mock.Mock(pk=42),
                'pieces': [('planche', 'Planche de calepinage'),
                           ('note_calcul', 'Note de calcul')],
                'signalements': ['« Schéma unifilaire » : absent du devis.'],
                'dossier': 7}

        reponse, _fabrique = self._generer(dossier, pack)

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['dossier'], 7)
        self.assertEqual(reponse.data['document'], 42)
        self.assertEqual(
            [piece['code'] for piece in reponse.data['pieces']],
            ['planche', 'note_calcul'])
        self.assertEqual(reponse.data['signalements'],
                         ['« Schéma unifilaire » : absent du devis.'])

    def test_la_generation_est_datee_et_le_document_retenu(self):
        dossier = _Dossier(pk=7)
        pack = {'document': mock.Mock(pk=42), 'pieces': [], 'signalements': []}

        reponse, _fabrique = self._generer(dossier, pack)

        self.assertEqual(dossier.document_id, 42)
        self.assertIsNotNone(dossier.genere_le)
        self.assertEqual(dossier.sauve, [('document_id', 'genere_le')])
        self.assertEqual(reponse.data['genere_le'], dossier.genere_le)

    def test_le_gabarit_seul_suffit_a_designer_le_dossier(self):
        dossier = _Dossier(pk=9)
        pack = {'document': mock.Mock(pk=1), 'pieces': [], 'signalements': []}

        reponse, fabrique = self._generer(dossier, pack, {'gabarit': 3})

        self.assertEqual(reponse.status_code, 200)
        # Le service reçoit LA ligne de base, jamais le dossier composé.
        self.assertEqual(fabrique.call_args.args, (dossier,))
