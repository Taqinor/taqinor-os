SONDE = {"constat": "C-APAR-VER-031", "sha": "56d5b623a",
         "attendu": "après APAR52, l'item onboarding premier_devis servi par GET /onboarding/progress/ se lit "
                    "« Envoyer votre 1er devis » sur une base déjà migrée (pas seulement sur une base neuve)"}


def sonde(ctx):
    from apps.onboarding.models import OnboardingChecklistItem
    from apps.onboarding.services import DEFAULT_ITEMS
    attendu = [lib for key, lib, *_ in DEFAULT_ITEMS if key == 'premier_devis'][0]
    item = OnboardingChecklistItem.objects.filter(key='premier_devis').first()
    servi = getattr(item, 'libelle', None)
    print(f'libellé en base (servi à l écran) = {servi!r} ; libellé du code DEFAULT_ITEMS = {attendu!r}')
    return {'repro': item is not None and servi != attendu, 'servi': servi, 'code': attendu}
