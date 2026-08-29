"""QJR44 — la MÊME estampille pour ``profils_comparatifs`` et ``etude_horaire``.

CE QUE CES TESTS TIENNENT.

* ``profils_comparatifs`` : sa garde ``force`` ne sautait que l'ÉCRITURE —
  ``calculer_profils_comparatifs`` tournait TOUJOURS, c'est-à-dire DEUX
  balayages de dimensionnement complets et deux études horaires, en synchrone
  dans le handler HTTP, à CHAQUE ajout / modification / suppression de ligne.
  L'estampille est désormais comparée AVANT le calcul.
* ``etude_horaire`` : ``_bloc_horaire_deja_a_jour`` (CONSERVÉ — il porte la
  tolérance ``pricing._HORAIRE_TOLERANCE_KWC``, délibérément la même que celle
  du document) ne regarde que la COMPOSITION. Une facture corrigée ne bougeait
  ni le kWc ni la capacité batterie : le bloc restait « à jour » alors que
  toutes ses économies étaient périmées. L'empreinte des entrées s'AJOUTE aux
  deux contrôles existants.

Fixtures calquées sur ``test_t5_dimensionnement_devis._DimensionnementBase``
(Casablanca, aucun accès réseau).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_empreintes_etudes -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.profils_comparatifs import (
    _empreinte_profils, rafraichir_profils_comparatifs_devis,
)
from apps.ventes.services import (
    _bloc_horaire_deja_a_jour, rafraichir_etude_horaire_devis,
    rafraichir_etudes_du_devis,
)

User = get_user_model()


class _EmpreintesBase(TestCase):
    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, facture_hiver=1800):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville='Casablanca',
            facture_hiver=facture_hiver, ete_differente=False)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={})
        produit = Produit.objects.create(
            company=company, nom='Panneau Canadien Solar 710W',
            prix_vente='1166.67', quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit,
            designation='Panneau Canadien Solar 710W',
            quantite=Decimal('14'), prix_unitaire=Decimal('1166.67'),
            remise=Decimal('0'))
        return devis

    def _espion_balayage(self):
        """Compte les appels RÉELS au balayage ``recommander_taille``."""
        from apps.ventes import dimensionnement as module_dim
        vrai = module_dim.recommander_taille
        appels = []

        def espion(*args, **kwargs):
            appels.append(1)
            return vrai(*args, **kwargs)

        return (mock.patch.object(module_dim, 'recommander_taille', espion),
                appels)


class ProfilsComparatifsEmpreinteTests(_EmpreintesBase):

    def test_sans_changement_aucun_balayage(self):
        """ROUGE avant QJR44 : le calcul tournait à chaque appel."""
        devis = self._devis('qjr44-stable')
        premier = rafraichir_profils_comparatifs_devis(devis)
        if premier is None:
            self.skipTest('catalogue trop pauvre pour composer les variantes')
        devis.refresh_from_db()

        patch, appels = self._espion_balayage()
        with patch:
            second = rafraichir_profils_comparatifs_devis(devis)
        self.assertEqual(appels, [])
        self.assertEqual(second['_empreinte'], premier['_empreinte'])

    def test_facture_modifiee_le_bloc_se_recalcule(self):
        devis = self._devis('qjr44-facture')
        premier = rafraichir_profils_comparatifs_devis(devis)
        if premier is None:
            self.skipTest('catalogue trop pauvre pour composer les variantes')
        empreinte_1 = premier['_empreinte']

        devis.lead.facture_hiver = 3400
        devis.lead.save(update_fields=['facture_hiver'])
        devis.refresh_from_db()

        second = rafraichir_profils_comparatifs_devis(devis)
        self.assertIsNotNone(second)
        self.assertNotEqual(second['_empreinte'], empreinte_1)

    def test_composition_modifiee_le_bloc_se_recalcule(self):
        """Le kWc vendu entre dans l'estampille : une ligne panneau qui change
        périme le bloc, exactement comme un profil qui change."""
        devis = self._devis('qjr44-compo')
        avant = _empreinte_profils(devis)
        self.assertIsNotNone(avant)
        ligne = devis.lignes.first()
        ligne.quantite = Decimal('20')
        ligne.save(update_fields=['quantite'])
        devis = Devis.objects.get(pk=devis.pk)
        self.assertNotEqual(_empreinte_profils(devis), avant)

    def test_bloc_sans_estampille_est_perime(self):
        devis = self._devis('qjr44-legacy')
        devis.etude_params = {'profils_comparatifs': {'sentinelle': True}}
        devis.save(update_fields=['etude_params'])
        resultat = rafraichir_profils_comparatifs_devis(devis, force=False)
        self.assertNotEqual(resultat, {'sentinelle': True})

    def test_empreinte_non_derivable_rend_none(self):
        devis = self._devis('qjr44-nonderiv', facture_hiver=None)
        self.assertIsNone(_empreinte_profils(devis))


class EtudeHoraireEmpreinteTests(_EmpreintesBase):

    def test_le_bloc_range_porte_son_estampille(self):
        devis = self._devis('qjr44-eh-pose')
        bloc = rafraichir_etude_horaire_devis(devis, force=True)
        if bloc is None:
            self.skipTest('étude horaire non calculable sur cette fixture')
        devis.refresh_from_db()
        self.assertTrue(
            devis.etude_params['etude_horaire'].get('_empreinte_entrees'))

    def test_facture_modifiee_le_bloc_n_est_plus_a_jour(self):
        """Le kWc n'a PAS bougé — seuls les contrôles historiques auraient dit
        « à jour » (ROUGE avant QJR44)."""
        devis = self._devis('qjr44-eh-facture')
        bloc = rafraichir_etude_horaire_devis(devis, force=True)
        if bloc is None:
            self.skipTest('étude horaire non calculable sur cette fixture')
        devis.refresh_from_db()
        kwc = devis.etude_params['etude_horaire']['kwc']
        self.assertTrue(_bloc_horaire_deja_a_jour(devis, kwc))

        devis.lead.facture_hiver = 3400
        devis.lead.save(update_fields=['facture_hiver'])
        devis = Devis.objects.get(pk=devis.pk)
        self.assertFalse(_bloc_horaire_deja_a_jour(devis, kwc))

    def test_bloc_sans_estampille_n_est_pas_a_jour(self):
        devis = self._devis('qjr44-eh-legacy')
        bloc = rafraichir_etude_horaire_devis(devis, force=True)
        if bloc is None:
            self.skipTest('étude horaire non calculable sur cette fixture')
        devis.refresh_from_db()
        kwc = devis.etude_params['etude_horaire']['kwc']
        etude = dict(devis.etude_params)
        horaire = dict(etude['etude_horaire'])
        horaire.pop('_empreinte_entrees', None)
        etude['etude_horaire'] = horaire
        devis.etude_params = etude
        devis.save(update_fields=['etude_params'])
        self.assertFalse(_bloc_horaire_deja_a_jour(devis, kwc))

    def test_le_bloc_range_porte_la_meme_date_que_le_moteur(self):
        """QJR45 — une seule lecture d'horloge : la date estampillée est celle
        contre laquelle le moteur a calculé."""
        devis = self._devis('qjr44-eh-date')
        bloc = rafraichir_etude_horaire_devis(devis, force=True)
        if bloc is None:
            self.skipTest('étude horaire non calculable sur cette fixture')
        from apps.ventes.domain.entrees import (
            empreinte_entrees, entrees_depuis_devis)
        devis.refresh_from_db()
        self.assertEqual(
            devis.etude_params['etude_horaire']['_empreinte_entrees'],
            empreinte_entrees(entrees_depuis_devis(devis)))

    def test_la_tolerance_kwc_du_moteur_est_conservee(self):
        """``_bloc_horaire_deja_a_jour`` n'est PAS retiré : sa tolérance reste
        celle de ``pricing._HORAIRE_TOLERANCE_KWC``."""
        from apps.ventes.quote_engine.pricing import _HORAIRE_TOLERANCE_KWC

        devis = self._devis('qjr44-eh-tol')
        bloc = rafraichir_etude_horaire_devis(devis, force=True)
        if bloc is None:
            self.skipTest('étude horaire non calculable sur cette fixture')
        devis.refresh_from_db()
        kwc = float(devis.etude_params['etude_horaire']['kwc'])
        dedans = kwc * (1 + _HORAIRE_TOLERANCE_KWC / 2)
        dehors = kwc * (1 + _HORAIRE_TOLERANCE_KWC * 3)
        self.assertTrue(_bloc_horaire_deja_a_jour(devis, dedans))
        self.assertFalse(_bloc_horaire_deja_a_jour(devis, dehors))


class ForceRetireTests(_EmpreintesBase):
    """QJR47 — les ``force=True`` des quatre chemins d'écriture sont retirés.

    Ils protégeaient contre un cache posé sur la PRÉSENCE de la clé. L'empreinte
    protège mieux : elle recalcule quand une entrée bouge, et seulement là.
    Coût mesuré par ces tests : ajouter cinq lignes ne déclenchait pas moins de
    TROIS balayages complets PAR LIGNE, tous synchrones dans le handler HTTP.
    """

    def test_ajouter_cinq_lignes_ne_declenche_plus_aucun_balayage(self):
        devis = self._devis('qjr47-cinq')
        rafraichir_etudes_du_devis(devis)
        devis = Devis.objects.get(pk=devis.pk)

        patch, appels = self._espion_balayage()
        with patch:
            for index in range(5):
                LigneDevis.objects.create(
                    devis=devis, designation='Câble solaire %d' % index,
                    quantite=Decimal('1'), prix_unitaire=Decimal('100'),
                    remise=Decimal('0'))
                devis = Devis.objects.get(pk=devis.pk)
                rafraichir_etudes_du_devis(devis)
        self.assertEqual(
            appels, [],
            'aucune de ces cinq lignes ne change le profil ni le kWc : '
            'aucun balayage ne doit être rejoué')

    def test_la_fraicheur_est_conservee_quand_la_composition_change(self):
        """Le recalcul a toujours lieu quand il DOIT avoir lieu."""
        devis = self._devis('qjr47-fraicheur')
        premier = rafraichir_etudes_du_devis(devis)
        if premier.get('etude_horaire') is None:
            self.skipTest('étude horaire non calculable sur cette fixture')
        devis = Devis.objects.get(pk=devis.pk)
        kwc_avant = devis.etude_params['etude_horaire']['kwc']

        ligne = devis.lignes.filter(designation__icontains='Panneau').first()
        ligne.quantite = Decimal('28')
        ligne.save(update_fields=['quantite'])
        devis = Devis.objects.get(pk=devis.pk)

        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        self.assertNotEqual(devis.etude_params['etude_horaire']['kwc'],
                            kwc_avant)

    def test_un_profil_modifie_recalcule_sans_force(self):
        devis = self._devis('qjr47-profil')
        rafraichir_etudes_du_devis(devis)
        devis = Devis.objects.get(pk=devis.pk)
        empreinte_avant = (devis.etude_params.get('dimensionnement') or {}
                           ).get('_empreinte')
        self.assertIsNotNone(empreinte_avant)

        devis.lead.facture_hiver = 3600
        devis.lead.save(update_fields=['facture_hiver'])
        devis = Devis.objects.get(pk=devis.pk)

        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        self.assertNotEqual(
            devis.etude_params['dimensionnement']['_empreinte'],
            empreinte_avant)
