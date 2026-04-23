import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_chair_linked_to_organization'),
        ('tasks', '0003_assignee_primary_leader_org'),
    ]

    operations = [
        # TaskAssignee ga chair FK qo'shamiz
        migrations.AddField(
            model_name='taskassignee',
            name='chair',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='task_assignees',
                to='organizations.chair',
            ),
        ),
        # TaskOrganizationTarget ga chair FK qo'shamiz
        migrations.AddField(
            model_name='taskorganizationtarget',
            name='chair',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='task_org_targets',
                to='organizations.chair',
            ),
        ),
    ]
