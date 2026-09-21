"""Garde : les enveloppes marketing gardent leurs actions ROUTÉES.

`CampagneViewSetAudite` (NTMKT45) et `EnqueteNPSViewSetNotifiant` (NTMKT44)
étendent des viewsets d'``apps.compta`` en surchargeant une action pour y
greffer un effet (journal d'audit, notification détracteur).

Piège attrapé le 14/08/2026 : surcharger la méthode SANS redéclarer
``@action`` écrase l'attribut ``.mapping`` posé par le décorateur de la classe
de base. ``get_extra_actions()`` de DRF ne voit alors plus l'action, le routeur
ne génère plus l'URL, et l'endpoint renvoie **404 en silence** — invisible pour
les tests existants, puisque la route legacy ``/compta/…`` sert toujours la
classe de base intacte. Seule la régénération du schéma OpenAPI l'avait révélé.

Ce test échoue si quelqu'un retire à nouveau le décorateur.
"""
from django.test import SimpleTestCase

from apps.marketing.views import (
    CampagneViewSetAudite,
    EnqueteNPSViewSetNotifiant,
)


class EnveloppesActionsRouteesTests(SimpleTestCase):
    def test_campagne_audite_expose_encore_envoyer(self):
        noms = [a.__name__ for a in CampagneViewSetAudite.get_extra_actions()]
        self.assertIn(
            'envoyer', noms,
            "CampagneViewSetAudite.envoyer n'est plus routée : redéclarez "
            "@action(detail=True, methods=['post']) sur la surcharge.")

    def test_enquete_notifiante_expose_encore_repondre(self):
        noms = [
            a.__name__ for a in EnqueteNPSViewSetNotifiant.get_extra_actions()
        ]
        self.assertIn(
            'repondre', noms,
            "EnqueteNPSViewSetNotifiant.repondre n'est plus routée : "
            "redéclarez @action(detail=True, methods=['post']).")

    def test_les_enveloppes_gardent_le_verbe_post(self):
        """La surcharge ne doit pas non plus changer la méthode HTTP."""
        for cls, nom in (
            (CampagneViewSetAudite, 'envoyer'),
            (EnqueteNPSViewSetNotifiant, 'repondre'),
        ):
            action = next(
                a for a in cls.get_extra_actions() if a.__name__ == nom)
            self.assertEqual(
                list(action.mapping), ['post'],
                f'{cls.__name__}.{nom} doit rester un POST détail.')
