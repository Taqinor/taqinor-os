"""ACAL42 (C-ACAL-096) — le verrou du calepinage EST le prédicat ventes.

Ce qui est prouvé ici, par HTTP réel sur des devis réels :

* un devis lié ENVOYÉ jamais « déverrouillé » : POST layout/ → 200, une
  version (D-QJR5-5 : un envoyé se corrige) ;
* pour chaque statut (brouillon, envoyé, accepté, refusé, expiré, remplacé),
  ``est_verrouille(calepinage) == not devis_modifiabilite(devis,
  geste='CALEPINAGE')['modifiable']`` ;
* clos : 409 {roof_layout: [motif ventes]} et la porte ``deverrouiller/``
  n'existe plus (404) ;
* sync-layout d'un envoyé passe ; depuis ACAL96 (D-ACAL-1) la route écrit
  le calepinage lié (seul écrivain : enregistrer_layout) puis resynchronise ;
* ``design-context.modifiable == not est_verrouille``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_verrou_predicat_ventes -v2
"""
from decimal import Decimal

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import empreinte_document
from apps.calepinage.services.verrou import est_verrouille
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.selectors import devis_modifiabilite

from .test_api_liste import BaseApiCalepinage, url_detail


def _layout(panneaux):
    return {'scenario': 'reseau', 'panelWatt': 550,
            'result': {'panels': panneaux, 'kwc': round(panneaux * 0.55, 2),
                       'annualKwh': 9000, 'savings': 8000}}


class VerrouPredicatVentesTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL42-1', statut=Devis.Statut.BROUILLON)
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='ACAL42')

    def _statut(self, statut, *, actif=True):
        self.devis.statut = statut
        self.devis.is_active = actif
        self.devis.save(update_fields=['statut', 'is_active'])
        self.calepinage = Calepinage.objects.get(pk=self.calepinage.pk)

    def _poster_layout(self, document):
        jeton = empreinte_document(self.calepinage.roof_layout) or ''
        return self.api.post(f'{url_detail(self.calepinage.pk)}layout/',
                             document, format='json',
                             HTTP_IF_MATCH=f'"{jeton}"')

    def test_envoye_s_enregistre(self):
        self._statut(Devis.Statut.ENVOYE)
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        reponse = self._poster_layout({'panels': 4})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), avant + 1)
        # Enregistrer sans toucher ⇒ inchangé.
        self.calepinage.refresh_from_db()
        reponse = self._poster_layout({'panels': 4})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['inchange'])

    def test_parite_verrou_verdict_par_statut(self):
        cas = [(Devis.Statut.BROUILLON, True), (Devis.Statut.ENVOYE, True),
               (Devis.Statut.ACCEPTE, True), (Devis.Statut.REFUSE, True),
               (Devis.Statut.EXPIRE, True), (Devis.Statut.ENVOYE, False)]
        for statut, actif in cas:
            with self.subTest(statut=statut, actif=actif):
                self._statut(statut, actif=actif)
                verdict = devis_modifiabilite(self.devis, geste='CALEPINAGE')
                self.assertEqual(est_verrouille(self.calepinage),
                                 not verdict['modifiable'])
        self._statut(Devis.Statut.ACCEPTE)
        self.assertTrue(est_verrouille(self.calepinage))
        self._statut(Devis.Statut.ENVOYE)
        self.assertFalse(est_verrouille(self.calepinage))

    def test_clos_sans_porte_de_deverrouillage(self):
        self._statut(Devis.Statut.ACCEPTE)
        reponse = self._poster_layout({'panels': 4})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('roof_layout', reponse.data)
        self.assertIn('Devis accepté : révisez-le',
                      str(reponse.data['roof_layout']))
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}deverrouiller/', {},
            format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_design_context_egal_au_verrou(self):
        for statut in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE,
                       Devis.Statut.ACCEPTE, Devis.Statut.REFUSE,
                       Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                self._statut(statut)
                reponse = self.api.get(
                    f'{url_detail(self.calepinage.pk)}design-context/')
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.assertEqual(reponse.data['modifiable'],
                                 not est_verrouille(self.calepinage))


class MiroirEnvoyeTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        for nom, sku, prix in (
                ('Panneau Jinko 550W', 'A42-PAN', '1100'),
                ('Onduleur réseau Growatt 10kW', 'A42-OND', '14000')):
            Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)

    def test_miroir_d_un_envoye_passe(self):
        """ACAL42 — sync-layout d'un ENVOYÉ n'est plus refusé. ACAL96
        (D-ACAL-1) — la route écrit le calepinage lié par enregistrer_layout
        (le verrou = prédicat ventes, ouvert sur un envoyé), puis resynchronise
        le devis depuis lui."""
        from apps.ventes.services import build_devis_from_layout

        devis = build_devis_from_layout(
            layout=_layout(10), user=self.user, company=self.company,
            client=self.client_a)
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=devis,
            roof_layout=_layout(10), titre='Miroir ACAL42')
        Devis.objects.filter(pk=devis.pk).update(
            statut=Devis.Statut.ENVOYE)
        reponse = self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/sync-layout/',
            _layout(12), format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout, _layout(12))
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
