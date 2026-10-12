"""ERR fuzz (achats) — mise à jour d'un retour fournisseur avec ses lignes.

``RetourFournisseurSerializer.lignes`` est imbriqué en écriture : DRF refuse
``ModelSerializer.update()`` dans ce cas (AssertionError -> HTTP 500 sur un PATCH
portant ``lignes``, trouvé par api-fuzz-pr). Ce mélange remplace les lignes du
retour (brouillon — le document figé est déjà refusé en amont par
``DocumentFigeMixin``) dans la même transaction que l'en-tête.
"""
from django.db import transaction


class RemplaceLignesRetourMixin:
    def update(self, instance, validated_data):
        lignes_data = validated_data.pop('lignes', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if lignes_data is not None:
                instance.lignes.all().delete()
                for ligne in lignes_data:
                    instance.lignes.create(**ligne)
        return instance
