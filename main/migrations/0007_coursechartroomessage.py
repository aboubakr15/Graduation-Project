from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Migration to add CourseChatMessage table for real-time group chat.
    """

    dependencies = [
        ('main', '0006_assignment_file_studentsubmission_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender_role', models.CharField(default='STUDENT', max_length=20)),
                ('sender_name', models.CharField(default='', max_length=255)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course_offering', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_messages',
                    to='main.courseoffering',
                )),
                ('sender', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='course_chat_messages',
                    to='main.user',
                )),
            ],
            options={
                'db_table': 'course_chat_messages',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='coursechatmessage',
            index=models.Index(fields=['course_offering', 'created_at'], name='course_chat_offering_created_idx'),
        ),
    ]
