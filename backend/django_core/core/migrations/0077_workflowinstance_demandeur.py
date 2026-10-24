import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """APAR76 — ``WorkflowInstance.demandeur`` (séparation des tâches)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0076_alter_esignrequest_content_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowinstance',
            name='demandeur',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Demandeur'),
        ),
    ]
