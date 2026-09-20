"""CAL8 — instantanés jamais réécrits, purge bornée et OFF par défaut.

Ce qui est prouvé ici :

* deux enregistrements SIGNIFICATIFS (empreintes différentes) produisent deux
  versions distinctes ;
* un enregistrement à l'empreinte IDENTIQUE n'en crée aucune (un double-clic
  ou un renvoi réseau ne pollue pas l'historique) ;
* une version n'est JAMAIS modifiable après sa création — le refus est sur le
  modèle, donc aucun chemin d'écriture ne le contourne ;
* la purge est DÉSACTIVÉE tant que la société n'a pas SAISI sa borne : rien
  n'est jamais retiré « par défaut » ;
* une borne saisie ne retire QUE les versions au-delà d'elle, et ce sont les
  plus RÉCENTES qui survivent ;
* l'isolation société tient (la version porte la société du calepinage).

Run :
    python manage.py test apps.calepinage.tests.test_versions -v2
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services import versions as svc
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.crm.models import Client
from authentication.models import Company


def empreinte(graine):
    """Une empreinte de 64 caractères, déterministe et lisible."""
    return (str(graine) * 64)[:64]


class BaseHistorique(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Historique Co',
                                              slug='historique-co')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.pivot = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            roof_layout={'zones': [1]}, layout_hash=empreinte('a'))

    def _enregistrer(self, graine, zones):
        self.pivot.roof_layout = {'zones': zones}
        self.pivot.layout_hash = empreinte(graine)
        self.pivot.save()
        return svc.enregistrer_version(self.pivot)


class EnregistrementTest(BaseHistorique):
    def test_deux_enregistrements_significatifs_deux_versions(self):
        self.assertIsNotNone(self._enregistrer('a', [1]))
        self.assertIsNotNone(self._enregistrer('b', [1, 2]))
        self.assertEqual(self.pivot.versions.count(), 2)

    def test_empreinte_identique_ne_cree_rien(self):
        self.assertIsNotNone(self._enregistrer('a', [1]))
        self.assertIsNone(self._enregistrer('a', [1]))
        self.assertEqual(self.pivot.versions.count(), 1)

    def test_societe_et_contenu_recopies(self):
        version = self._enregistrer('c', [1, 2, 3])
        self.assertEqual(version.company_id, self.company.pk)
        self.assertEqual(version.roof_layout, {'zones': [1, 2, 3]})
        self.assertEqual(version.layout_hash, empreinte('c'))

    def test_calepinage_non_enregistre_refuse_en_nommant_le_champ(self):
        with self.assertRaises(svc.VersionInvalide) as capture:
            svc.enregistrer_version(Calepinage(company=self.company,
                                               lead_id=1))
        self.assertEqual(capture.exception.champ, 'calepinage')


class JamaisReecriteTest(BaseHistorique):
    def test_modification_refusee(self):
        version = self._enregistrer('a', [1])
        version.libelle = 'retouche'
        with self.assertRaises(ValidationError):
            version.save()

    def test_contenu_intact_apres_tentative(self):
        version = self._enregistrer('a', [1])
        try:
            version.libelle = 'retouche'
            version.save()
        except ValidationError:
            pass
        relue = CalepinageVersion.objects.get(pk=version.pk)
        self.assertEqual(relue.libelle, '')


class PurgeTest(BaseHistorique):
    def _historiser(self, combien):
        for index in range(combien):
            self._enregistrer(index % 10, list(range(index + 1)))

    def test_purge_off_par_defaut(self):
        self._historiser(5)
        avant = self.pivot.versions.count()
        self.assertEqual(svc.purger_versions(self.pivot), 0)
        self.assertEqual(self.pivot.versions.count(), avant)

    def test_borne_de_purge_absente_vaut_off(self):
        self.assertIsNone(svc.borne_de_purge(self.company))

    def test_borne_saisie_lue_depuis_les_reglages(self):
        enregistrer_parametres(self.company,
                               {'presets': {svc.CLE_BORNE_PURGE: 3}})
        self.assertEqual(svc.borne_de_purge(self.company), 3)

    def test_borne_non_entiere_vaut_off(self):
        enregistrer_parametres(self.company,
                               {'presets': {svc.CLE_BORNE_PURGE: 'trois'}})
        self.assertIsNone(svc.borne_de_purge(self.company))

    def test_purge_retire_au_dela_de_la_borne(self):
        self._historiser(5)
        total = self.pivot.versions.count()
        retirees = svc.purger_versions(self.pivot, garder=2)
        self.assertEqual(retirees, total - 2)
        self.assertEqual(self.pivot.versions.count(), 2)

    def test_les_plus_recentes_survivent(self):
        self._historiser(4)
        recentes = list(self.pivot.versions.order_by('-created_at', '-id')
                        .values_list('pk', flat=True)[:2])
        svc.purger_versions(self.pivot, garder=2)
        self.assertEqual(
            sorted(self.pivot.versions.values_list('pk', flat=True)),
            sorted(recentes))

    def test_borne_invalide_refusee_en_nommant_le_champ(self):
        with self.assertRaises(svc.VersionInvalide) as capture:
            svc.purger_versions(self.pivot, garder=0)
        self.assertEqual(capture.exception.champ, svc.CLE_BORNE_PURGE)

    def test_purge_bornee_au_calepinage(self):
        """Purger un calepinage ne touche JAMAIS l'historique d'un autre."""
        autre = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            layout_hash=empreinte('z'))
        CalepinageVersion.objects.create(company=self.company,
                                         calepinage=autre,
                                         layout_hash=empreinte('z'))
        self._historiser(3)
        svc.purger_versions(self.pivot, garder=1)
        self.assertEqual(autre.versions.count(), 1)
