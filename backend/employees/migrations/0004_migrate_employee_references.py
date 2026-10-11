from django.db import migrations


def migrate_employee_references(apps, schema_editor):
    """Copy legacy employee text fields to HR reference fields."""

    EmployeeProfile = apps.get_model(
        "employees",
        "EmployeeProfile",
    )

    Department = apps.get_model(
        "employees",
        "Department",
    )

    Position = apps.get_model(
        "employees",
        "Position",
    )

    for employee in EmployeeProfile.objects.all():
        department = Department.objects.filter(
            name=employee.department
        ).first()

        if not department:
            continue

        employee.department_ref_id = department.id

        position = Position.objects.filter(
            title=employee.job_title,
            department_id=department.id,
        ).first()

        if position:
            employee.position_ref_id = position.id

        employee.save(
            update_fields=[
                "department_ref",
                "position_ref",
            ]
        )


def reverse_migrate_employee_references(apps, schema_editor):
    """Restore legacy text fields from HR reference fields."""

    EmployeeProfile = apps.get_model(
        "employees",
        "EmployeeProfile",
    )

    for employee in EmployeeProfile.objects.select_related(
        "department_ref",
        "position_ref",
    ):
        if employee.department_ref:
            employee.department = employee.department_ref.name

        if employee.position_ref:
            employee.job_title = employee.position_ref.title

        employee.save(
            update_fields=[
                "department",
                "job_title",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0003_employeeprofile_department_ref_and_more"),
    ]

    operations = [
        migrations.RunPython(
            migrate_employee_references,
            reverse_migrate_employee_references,
        ),
    ]
