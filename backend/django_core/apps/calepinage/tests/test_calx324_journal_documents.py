"""CALX324 — journaliser l'émission d'un document dans le fil du calepinage.

Ce qui est prouvé ici :

* ``journaliser_document_produit`` écrit UNE ligne « <document> produit
  (version N, langue X) » portant l'EMPREINTE — jamais un résumé du
  contenu (essai PUR, ``journal._ecrire`` espionné) ;
* un code SANS libellé enregistré ne fait jamais lever cette fonction : elle
  retombe sur le code brut (essai PUR) ;
* AUCUN mot de montant dans la ligne journalisée (essai PUR — même
  discipline D5 que le reste du module) ;
* ``enregistrer_version_document`` n'appelle JAMAIS le journal sur un refus
  de validation (calepinage non enregistré, code manquant, document vide —
  essais PURS, ``journaliser_document_produit`` espionné) ;
* en base (CI) : un téléchargement écrit UNE ligne et une seule au fil du
  calepinage, portant la version produite par CALX322 ; un refus (sans
  résultat) n'en écrit aucune.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx324_journal_documents.py -q
"""
from __future__ import annotations

import unittest
from unittest import mock

from apps.calepinage.services import journal
from apps.calepinage.services.documents.versions_document import (
    VersionDocumentRefuse, enregistrer_version_document,
)

#: Les jetons de montant bannis de TOUT texte du module (D5) — même liste
#: que la garde de dépôt ``test_aucun_prix_achat.py`` (appariement simple,
#: suffisant pour un texte de fil COURT et généré, sans mot composé piégeux).
MOTS_DE_MONTANT = ('mad', 'dh', 'prix', 'cout', 'coût', 'marge', 'remise',
                   'ttc', 'ht', '€')


class FauxCalepinage:
    pk = 1
    company = None


class JournaliserDocumentProduitTest(unittest.TestCase):
    """La ligne écrite — essai PUR (``journal._ecrire`` espionné)."""

    def _ecrire_espionne(self, *, retour=mock.sentinel.activite):
        return mock.patch('apps.calepinage.services.journal._ecrire',
                          return_value=retour)

    def test_la_ligne_nomme_le_titre_la_version_et_la_langue(self):
        with self._ecrire_espionne() as ecrire:
            journal.journaliser_document_produit(
                FauxCalepinage(), code='rapport_etude', numero=3,
                langue='fr', empreinte='ab12cd34')
        self.assertEqual(ecrire.call_count, 1)
        _calepinage, kind = ecrire.call_args.args
        self.assertEqual(kind, 'MODIFICATION')
        kwargs = ecrire.call_args.kwargs
        self.assertEqual(kwargs['field'], journal.CHAMP_DOCUMENT_PRODUIT)
        self.assertEqual(kwargs['old_value'], '')
        self.assertIn("Rapport d'étude", kwargs['new_value'])
        self.assertIn('version 3', kwargs['new_value'])
        self.assertIn('fr', kwargs['new_value'])
        self.assertIn('ab12cd34', kwargs['new_value'])

    def test_code_sans_libelle_retombe_sur_le_code_brut_sans_lever(self):
        with self._ecrire_espionne() as ecrire:
            journal.journaliser_document_produit(
                FauxCalepinage(), code='document_futur_sans_libelle',
                numero=1, langue='fr')
        self.assertIn('document_futur_sans_libelle',
                      ecrire.call_args.kwargs['new_value'])

    def test_sans_empreinte_la_ligne_reste_lisible(self):
        with self._ecrire_espionne() as ecrire:
            journal.journaliser_document_produit(
                FauxCalepinage(), code='rapport_etude', numero=1,
                langue='en', empreinte='')
        self.assertNotIn('—', ecrire.call_args.kwargs['new_value'])

    def test_aucun_mot_de_montant_dans_la_ligne(self):
        with self._ecrire_espionne() as ecrire:
            journal.journaliser_document_produit(
                FauxCalepinage(), code='rapport_etude', numero=1,
                langue='fr', empreinte='deadbeef · moteur calepinage-1.0.0')
        ligne = ecrire.call_args.kwargs['new_value'].lower()
        for mot in MOTS_DE_MONTANT:
            self.assertNotIn(mot, ligne, f'mot de montant trouvé : {mot!r}')


class RefusNEcritRienTest(unittest.TestCase):
    """Un refus de validation n'appelle JAMAIS le journal — essais PURS
    (aucune des trois validations n'atteint la base)."""

    def _journal_espionne(self):
        # ``journaliser_document_produit`` est importé FONCTION-LOCALEMENT
        # dans ``_journaliser_si_branche`` (jamais au chargement du module,
        # même discipline que le reste de ``services/documents``) : c'est
        # donc CETTE fonction, module-level, qu'on espionne — un import
        # local n'est pas un attribut patchable du module.
        return mock.patch(
            'apps.calepinage.services.documents.versions_document.'
            '_journaliser_si_branche')

    def test_calepinage_non_enregistre_n_ecrit_rien(self):
        with self._journal_espionne() as espion:
            with self.assertRaises(VersionDocumentRefuse):
                enregistrer_version_document(
                    None, code='rapport_etude', octets=b'%PDF-1.4 ...')
        espion.assert_not_called()

    def test_code_manquant_n_ecrit_rien(self):
        class Faux:
            pk = 2
            company = None

        with self._journal_espionne() as espion:
            with self.assertRaises(VersionDocumentRefuse):
                enregistrer_version_document(
                    Faux(), code='', octets=b'%PDF-1.4 ...')
        espion.assert_not_called()

    def test_octets_vides_n_ecrit_rien(self):
        class Faux:
            pk = 3
            company = None

        with self._journal_espionne() as espion:
            with self.assertRaises(VersionDocumentRefuse):
                enregistrer_version_document(
                    Faux(), code='rapport_etude', octets=b'')
        espion.assert_not_called()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════
# EN BASE (CI) — une ligne, et une seule, au fil réel
# ═══════════════════════════════════════════════════════════════════════
#
# Écrit ici mais NON EXÉCUTÉ localement (pas de Postgres/MinIO sur ce poste
# de lane) : la CI valide.

import copy  # noqa: E402 - après les essais purs

from django.contrib.contenttypes.models import ContentType  # noqa: E402

from apps.calepinage.models import Calepinage  # noqa: E402
from apps.records.models import Activity  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402
from .test_cal171_planche import LAYOUT  # noqa: E402
from .test_calx308_diagramme_pertes_svg import RESULTAT  # noqa: E402


class JournalEnBaseTest(BaseApiCalepinage):
    """``GET …/rapport-etude.pdf/`` écrit UNE ligne au fil — CI."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=copy.deepcopy(LAYOUT), layout_hash='a' * 64,
            version_moteur='calepinage-1.0.0',
            resultat=copy.deepcopy(RESULTAT))
        self.sans_resultat = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Vide',
            roof_layout=copy.deepcopy(LAYOUT))

    def _lignes_document(self, calepinage):
        ct = ContentType.objects.get_for_model(Calepinage)
        return Activity.objects.filter(
            content_type=ct, object_id=calepinage.pk,
            field=journal.CHAMP_DOCUMENT_PRODUIT)

    def test_un_telechargement_ecrit_une_ligne_et_une_seule(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=copy.deepcopy(RESULTAT)):
            reponse = self.api.get(
                f'{url_detail(self.calepinage.pk)}rapport-etude.pdf/')
        self.assertEqual(reponse.status_code, 200)
        lignes = self._lignes_document(self.calepinage)
        self.assertEqual(lignes.count(), 1)
        self.assertIn('version 1', lignes.first().new_value)

    def test_un_refus_n_ecrit_aucune_ligne(self):
        reponse = self.api.get(
            f'{url_detail(self.sans_resultat.pk)}rapport-etude.pdf/')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self._lignes_document(self.sans_resultat).count(), 0)
