# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_alter_chatconversation_course_offering'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentsubmission',
            name='grade',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
    ]
