"""CAL28 — le lien INVERSE : quel calepinage pilote ce devis ?

Ce qui est prouvé ici :

* un devis AVEC calepinage rend ``{id, titre, layout_hash, a_jour}`` ;
* un devis SANS calepinage rend ``None`` ;
* ``a_jour`` est une COMPARAISON des deux empreintes — jamais un recalcul de
  géométrie — et vaut ``None`` (inconnu) quand une empreinte manque ;
* un calepinage d'une AUTRE société n'est jamais rendu ;
* ``apps.ventes`` n'importe AUCUN modèle de ``apps.calepinage`` (la lecture
  passe par son ``selectors.py``) — ce que ``lint-imports`` garde en CI.

Run :
    python manage.py test apps.ventes.tests.test_selector_calepinage -v2
"""
import pathlib
import re

from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.selectors import calepinage_du_devis
from authentication.models import Company

RACINE_VENTES = pathlib.Path(__file__).resolve().parents[1]


class SelectorCalepinageTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cal28 Co',
                                              slug='cal28-co')
        self.autre = Company.objects.create(nom='Voisine Cal28',
                                            slug='voisine-cal28')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Atlas 28')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-202609-2800', layout_hash='a' * 64)

    def test_devis_sans_calepinage_rend_none(self):
        self.assertIsNone(calepinage_du_devis(self.devis))

    def test_devis_avec_calepinage_rend_le_bloc(self):
        Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='Villa Anfa', layout_hash='a' * 64)
        bloc = calepinage_du_devis(self.devis)
        self.assertEqual(set(bloc), {'id', 'titre', 'layout_hash', 'a_jour'})
        self.assertEqual(bloc['titre'], 'Villa Anfa')
        self.assertTrue(bloc['a_jour'])

    def test_empreintes_divergentes_a_jour_faux(self):
        Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='Villa Anfa', layout_hash='b' * 64)
        self.assertFalse(calepinage_du_devis(self.devis)['a_jour'])

    def test_empreinte_manquante_a_jour_inconnu(self):
        Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='Villa Anfa')
        bloc = calepinage_du_devis(self.devis)
        self.assertIsNone(bloc['a_jour'])
        self.assertIsNone(bloc['layout_hash'])

    def test_calepinage_d_une_autre_societe_jamais_rendu(self):
        Calepinage.objects.create(
            company=self.autre, lead_id=1, devis=self.devis,
            titre='Chez la voisine', layout_hash='a' * 64)
        self.assertIsNone(calepinage_du_devis(self.devis))

    def test_ventes_n_importe_aucun_modele_calepinage(self):
        motif = re.compile(r'from\s+apps\.calepinage\.models|'
                           r'import\s+apps\.calepinage\.models')
        for fichier in RACINE_VENTES.rglob('*.py'):
            if 'tests' in fichier.parts or 'migrations' in fichier.parts:
                continue
            self.assertIsNone(
                motif.search(fichier.read_text(encoding='utf-8')),
                f'{fichier.name} importe apps.calepinage.models : la lecture '
                'cross-app passe par son selectors.py.')


class SerializerCalepinageTest(TestCase):
    """CAL28/CAL40 — la clé ``calepinage`` est PUBLIÉE par la fiche devis.

    Le sélecteur existait déjà ; aucun sérialiseur ne le publiait, donc le
    bloc ``BlocCalepinageDevis`` (CAL40) ne recevait jamais sa donnée. La
    forme rendue est EXACTEMENT celle que le bloc lit
    (``{id, titre, layout_hash, a_jour}``) — pas une seconde forme.
    """

    def setUp(self):
        self.company = Company.objects.create(nom='Cal40 Co', slug='cal40-co')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Atlas 40')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-202609-4000', layout_hash='a' * 64)

    def _serialiser(self):
        from apps.ventes.serializers import DevisSerializer
        return DevisSerializer(self.devis).data

    def test_fiche_devis_publie_le_bloc(self):
        Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='Villa Anfa', layout_hash='a' * 64)
        bloc = self._serialiser()['calepinage']
        self.assertEqual(set(bloc), {'id', 'titre', 'layout_hash', 'a_jour'})
        self.assertEqual(bloc['titre'], 'Villa Anfa')
        self.assertTrue(bloc['a_jour'])

    def test_devis_sans_calepinage_publie_none(self):
        self.assertIsNone(self._serialiser()['calepinage'])

    def test_en_liste_la_cle_vaut_none_pas_une_requete_par_devis(self):
        from apps.ventes.serializers import DevisSerializer
        Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='Villa Anfa', layout_hash='a' * 64)
        lignes = DevisSerializer([self.devis], many=True).data
        self.assertIsNone(lignes[0]['calepinage'])

    def test_le_champ_est_en_lecture_seule(self):
        from apps.ventes.serializers import DevisSerializer
        self.assertTrue(DevisSerializer().fields['calepinage'].read_only)
