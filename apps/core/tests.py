from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRoleAssignment


@override_settings(ADMIN_URL="admin/", ADMIN_ALLOWED_IPS=["127.0.0.1"])
class NumericRouterTests(TestCase):
    """Mavjud bo'lmagan detail manzillar 403 emas, 404 qaytarishi kerak (pentest O3)."""

    def setUp(self):
        self.admin = User.objects.create_user(email="sa@test.uz", password="Parol-12345", is_active=True)
        UserRoleAssignment.objects.create(user=self.admin, role=UserRoleAssignment.Role.SUPER_ADMIN)
        self.client = APIClient()

    def test_non_numeric_id_is_404_for_anonymous(self):
        self.assertEqual(self.client.get("/api/admin/users/export/").status_code, 404)
        self.assertEqual(self.client.get("/api/tasks/export/").status_code, 404)

    def test_non_numeric_id_is_404_for_super_admin(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/admin/users/export/").status_code, 404)

    def test_numeric_id_still_works(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/admin/users/{self.admin.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 200)


@override_settings(ADMIN_URL="admin/", ADMIN_ALLOWED_IPS=["127.0.0.1"])
class AuditLogTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="sa@test.uz", password="Parol-12345", is_active=True)
        UserRoleAssignment.objects.create(user=self.admin, role=UserRoleAssignment.Role.SUPER_ADMIN)
        self.target = User.objects.create_user(email="new@test.uz", password="Parol-12345", is_active=False)
        self.client = APIClient()

    def _log(self, fn):
        with self.assertLogs("audit", "INFO") as cm:
            fn()
        return "\n".join(cm.output)

    def test_api_login_success_and_failure(self):
        out = self._log(lambda: self.client.post(
            "/api/auth/login/", {"email": "sa@test.uz", "password": "Parol-12345"}, format="json"))
        self.assertIn("event=login_success", out)
        self.assertIn("sa@test.uz", out)
        self.assertIn('via="api"', out)
        self.assertIn("ip=127.0.0.1", out)

        out = self._log(lambda: self.client.post(
            "/api/auth/login/", {"email": "sa@test.uz", "password": "xato"}, format="json"))
        self.assertIn("event=login_failed", out)
        self.assertIn('reason="bad_credentials"', out)
        self.assertNotIn("xato", out)  # parol logga tushmasligi kerak

    def test_log_injection_is_neutralized(self):
        out = self._log(lambda: self.client.post(
            "/api/auth/login/", {"email": "a@b.uz\nAUDIT event=fake", "password": "x"}, format="json"))
        self.assertEqual(out.count("\n"), 0)

    def test_activate_and_roles(self):
        self.client.force_authenticate(self.admin)
        out = self._log(lambda: self.client.post(f"/api/admin/users/{self.target.pk}/toggle-active/"))
        self.assertIn("event=user_activated", out)
        self.assertIn("new@test.uz", out)
        self.assertIn("sa@test.uz", out)  # kim qildi

        out = self._log(lambda: self.client.post(
            f"/api/admin/users/{self.target.pk}/assign-role/", {"role": "SUPER_ADMIN"}, format="json"))
        self.assertIn("event=role_assigned", out)
        self.assertIn('role="SUPER_ADMIN"', out)

        assignment = self.target.role_assignments.get()
        out = self._log(lambda: self.client.delete(
            f"/api/admin/users/{self.target.pk}/roles/{assignment.pk}/"))
        self.assertIn("event=role_removed", out)

    def test_django_admin_login_and_change(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        out = self._log(lambda: self.client.post(
            "/admin/login/", {"username": "sa@test.uz", "password": "xato"}))
        self.assertIn("event=login_failed", out)
        self.assertIn('via="admin"', out)

        out = self._log(lambda: self.client.post(
            "/admin/login/", {"username": "sa@test.uz", "password": "Parol-12345"}))
        self.assertIn("event=login_success", out)
        self.assertIn('via="admin"', out)

        out = self._log(lambda: LogEntry.objects.create(
            user=self.admin, content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.target.pk), object_repr="new@test.uz",
            action_flag=CHANGE, change_message='[{"changed": {"fields": ["is_active"]}}]'))
        self.assertIn("event=admin_change", out)
        self.assertIn('model="user"', out)
