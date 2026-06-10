# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_courseoffering_is_chat_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='coursechatmessage',
            name='is_edited',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='coursechatmessage',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]
