"""CAL174 — la planche se télécharge, bornée société et bornée permission.

Ce qui est prouvé ici :

* ``GET …/planche.svg`` rend le SVG SOURCE (celui que ``svgToPng.js`` convertit
  en PNG côté navigateur) avec un ``Content-Disposition`` nommé d'après le
  calepinage ;
* ``GET …/planche.pdf`` rend le PDF — le RENDU lui-même est simulé
  (``core.pdf.render_pdf`` a ses propres essais, et WeasyPrint est absent de
  certains postes) : ce qui est vérifié ici, c'est le CÂBLAGE, l'en-tête et le
  type MIME ;
* un calepinage d'une AUTRE société est introuvable (404), jamais « interdit » ;
* sans ``calepinage_voir``, c'est 403 ;
* un calepinage SANS conception refuse en 400 avec le motif du serveur, jamais
  un fichier vide ;
* AUCUNE route ``planche.png`` n'est ouverte côté serveur.

Run :
    python manage.py test apps.calepinage.tests.test_cal174_endpoints_planche -v2
"""
from unittest import mock

from apps.calepinage.models import Calepinage

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_cal171_planche import LAYOUT

PDF = b'%PDF-1.7 rendu simule'


def url_planche(pk, extension):
    # Le routeur DRF du module est un ``DefaultRouter`` : ses routes portent
    # TOUTES la barre finale. L'adresse canonique est donc
    # « …/planche.pdf/ » — sans elle, `CommonMiddleware` redirige (301) et le
    # client croirait à une route absente.
    return f'{url_detail(pk)}planche.{extension}/'


class EndpointsPlancheTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, layout_hash='a' * 64,
            version_moteur='calepinage-1.0.0')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=LAYOUT)
        self.sans_conception = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans tracé')

    # ── SVG ────────────────────────────────────────────────────────────────
    def test_le_svg_se_telecharge_et_porte_le_pied_de_planche(self):
        reponse = self.api.get(url_planche(self.calepinage.pk, 'svg'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], 'image/svg+xml')
        self.assertIn('attachment; filename="calepinage-%s'
                      % self.calepinage.pk, reponse['Content-Disposition'])
        corps = reponse.content.decode('utf-8')
        self.assertIn('width="420mm"', corps)
        self.assertIn('calepinage aaaaaaaaaaaa', corps)
        self.assertIn('moteur calepinage-1.0.0', corps)

    def test_le_svg_d_une_autre_societe_est_introuvable(self):
        # 404 et non 403 : un 403 confirmerait l'existence de l'objet.
        self.assertEqual(
            self.api.get(url_planche(self.etranger.pk, 'svg')).status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        self.assertEqual(
            self.api_sans.get(
                url_planche(self.calepinage.pk, 'svg')).status_code, 403)

    def test_un_calepinage_sans_conception_refuse_en_nommant_le_champ(self):
        reponse = self.api.get(url_planche(self.sans_conception.pk, 'svg'))
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('roof_layout', reponse.data)

    # ── PDF ────────────────────────────────────────────────────────────────
    def test_le_pdf_passe_par_la_plomberie_partagee(self):
        with mock.patch('core.pdf.render_pdf', return_value=PDF) as rendu:
            reponse = self.api.get(url_planche(self.calepinage.pk, 'pdf'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], 'application/pdf')
        self.assertEqual(reponse.content, PDF)
        self.assertTrue(reponse['Content-Disposition'].endswith('.pdf"'))
        # La société est POSÉE côté serveur, jamais lue d'un paramètre.
        self.assertEqual(rendu.call_args.kwargs['company'], self.company)
        self.assertIn('<svg', rendu.call_args.kwargs['html'])

    def test_le_pdf_d_une_autre_societe_est_introuvable(self):
        with mock.patch('core.pdf.render_pdf', return_value=PDF):
            reponse = self.api.get(url_planche(self.etranger.pk, 'pdf'))
        self.assertEqual(reponse.status_code, 404)

    # ── Le PNG reste une affaire de navigateur ─────────────────────────────
    def test_aucune_route_png_n_est_ouverte_par_le_serveur(self):
        # Aucun rasteriseur SVG n'est installé : ouvrir `planche.png` ici
        # obligerait à ajouter une dépendance pour un besoin déjà couvert par
        # `svgToPng.js` côté navigateur.
        for adresse in (url_planche(self.calepinage.pk, 'png'),
                        f'{url_detail(self.calepinage.pk)}planche.png'):
            self.assertIn(self.api.get(adresse).status_code, (301, 404, 405))
