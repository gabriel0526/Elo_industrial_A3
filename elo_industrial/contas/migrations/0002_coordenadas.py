from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='latitude',
            field=models.FloatField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='empresa',
            name='longitude',
            field=models.FloatField(blank=True, editable=False, null=True),
        ),
    ]
