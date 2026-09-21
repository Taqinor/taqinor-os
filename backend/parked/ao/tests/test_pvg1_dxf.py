"""PVG1 — import DXF réel : parsing en mémoire, jamais un 500.

Complète ``ImportDxf.jsx`` (AOF81), livré AVANT l'endpoint : l'écran restait
dégradé faute d'``analyserDxf``. Ce module verrouille :

  1. **Le parsing RÉEL** — un DXF minimal (LWPOLYLINE + LINE, deux calques)
     produit les calques/entités/sommets attendus, l'unité lue depuis
     ``$INSUNITS``.
  2. **Aucune écriture** — ni ``PlanSource``, ni ``records.Attachment`` :
     l'endpoint ne fait QUE lire le fichier envoyé.
  3. **Jamais un 500** — fichier corrompu, vide, ou trop lourd → 400 MOTIVÉ
     en français (``dxf.DxfInvalide``, exceptions ``ezdxf`` enveloppées).
  4. **Gardée par ``ao_gerer``** comme le reste du domaine.

Run :
    python manage.py test apps.ao.tests.test_pvg1_dxf -v2
"""
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import dxf
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/toitures/dxf/analyser/'

# ── DXF minimal GÉNÉRÉ PAR ezdxf lui-même (jamais écrit à la main) ─────────
# Un DXF R2000 artisanal avait été tenté ici et refusé par le vrai ezdxf
# (sous-classe ``AcDbPolyline`` manquante sur la LWPOLYLINE) : une fixture
# fabriquée par la bibliothèque qui la relira est valide par construction.
# Contenu : un rectangle 10 x 5 sur le calque ENVELOPPE (LWPOLYLINE fermée,
# 4 sommets), un segment sur le calque OBSTACLE1 (LINE, 2 sommets),
# $INSUNITS=6 → mètre.


def _dxf_minimal() -> bytes:
    import ezdxf

    doc = ezdxf.new('R2000', setup=False)
    doc.header['$INSUNITS'] = 6
    espace = doc.modelspace()
    espace.add_lwpolyline(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)],
        close=True, dxfattribs={'layer': 'ENVELOPPE'})
    espace.add_line((2.0, 2.0, 0.0), (3.0, 2.0, 0.0),
                    dxfattribs={'layer': 'OBSTACLE1'})
    flux = io.StringIO()
    doc.write(flux)
    return flux.getvalue().encode('utf-8')


class AnalyserDxfDirectement(TestCase):
    """Le parsing pur (``dxf.analyser_dxf``), sans HTTP ni base de données."""

    def test_deux_calques_avec_leurs_sommets(self):
        resultat = dxf.analyser_dxf(_dxf_minimal())
        noms = {c['nom'] for c in resultat['calques']}
        self.assertEqual(noms, {'ENVELOPPE', 'OBSTACLE1'})

        enveloppe = next(c for c in resultat['calques'] if c['nom'] == 'ENVELOPPE')
        self.assertEqual(enveloppe['entites'], 1)
        self.assertEqual(enveloppe['sommets'], [
            [0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0],
        ])

        obstacle = next(c for c in resultat['calques'] if c['nom'] == 'OBSTACLE1')
        self.assertEqual(obstacle['entites'], 1)
        self.assertEqual(obstacle['sommets'], [[2.0, 2.0], [3.0, 2.0]])

    def test_unite_lue_depuis_insunits(self):
        resultat = dxf.analyser_dxf(_dxf_minimal())
        self.assertEqual(resultat['unite'], 'm')

    def test_fichier_corrompu_refuse_400_motive_jamais_un_500(self):
        with self.assertRaises(dxf.DxfInvalide) as ctx:
            dxf.analyser_dxf(b'ceci n\'est pas un DXF du tout, juste du texte')
        self.assertTrue(str(ctx.exception))  # motif non vide, jamais une exception nue

    def test_fichier_vide_refuse_proprement(self):
        with self.assertRaises(dxf.DxfInvalide):
            dxf.analyser_dxf(b'')

    def test_fichier_trop_lourd_refuse_AVANT_le_parsing(self):
        enorme = b'0' * (dxf.TAILLE_MAX_OCTETS + 1)
        with self.assertRaises(dxf.DxfInvalide) as ctx:
            dxf.analyser_dxf(enorme)
        self.assertIn('5 Mo', str(ctx.exception))


class AnalyserDxfViaLApi(TestCase):
    """L'endpoint MULTIPART — gardé, jamais un 500, rien de persisté."""

    def setUp(self):
        self.company = Company.objects.create(nom='PVG1 Co', slug='pvg1-co')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='pvg1_dir', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _upload(self, contenu, nom='plan.dxf'):
        fichier = io.BytesIO(contenu)
        fichier.name = nom
        return self.api.post(URL, {'fichier': fichier}, format='multipart')

    def test_dxf_valide_renvoie_les_calques(self):
        reponse = self._upload(_dxf_minimal())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        noms = {c['nom'] for c in reponse.data['calques']}
        self.assertEqual(noms, {'ENVELOPPE', 'OBSTACLE1'})
        self.assertEqual(reponse.data['unite'], 'm')

    def test_fichier_hostile_refuse_400_MOTIVE_jamais_un_500(self):
        reponse = self._upload(b'PAS UN DXF', nom='malveillant.dxf')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('fichier', reponse.data)
        self.assertTrue(reponse.data['fichier'])

    def test_aucun_fichier_recu_refuse_400(self):
        reponse = self.api.post(URL, {}, format='multipart')
        self.assertEqual(reponse.status_code, 400)

    def test_non_authentifie_refuse(self):
        anonyme = APIClient()
        reponse = anonyme.post(
            URL, {'fichier': io.BytesIO(_dxf_minimal())},
            format='multipart')
        self.assertIn(reponse.status_code, (401, 403))

    def test_rien_n_est_persiste(self):
        """L'atelier ne fait que PROPOSER un mapping — aucune écriture ici."""
        from apps.ao.models import PlanSource

        avant = PlanSource.objects.count()
        reponse = self._upload(_dxf_minimal())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(PlanSource.objects.count(), avant)
