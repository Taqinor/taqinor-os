from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0008_retention"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="alias_email",
            field=models.CharField(
                blank=True, default="", max_length=254, null=True
            ),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=~models.Q(alias_email__in=["", None]),
                fields=("company", "alias_email"),
                name="chat_conv_alias_email_uniq",
            ),
        ),
    ]
