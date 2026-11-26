import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRoleAssignment
from apps.organizations.models import Department, Organization
from apps.plans.models import DailyReport


class ArchiveAndDeleteUserTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Institut", org_type="MAIN")
        self.dept = Department.objects.create(name="Bo'lim", organization=org)
        self.admin = User.objects.create_user(email="sa@test.uz", password="Parol-12345", is_active=True)
        UserRoleAssignment.objects.create(user=self.admin, role=UserRoleAssignment.Role.SUPER_ADMIN)
        self.emp = User.objects.create_user(
            email="xodim@test.uz", password="Parol-12345", is_active=True, first_name="Ali", last_name="Valiyev")
        UserRoleAssignment.objects.create(user=self.emp, role=UserRoleAssignment.Role.EMPLOYEE,
                                          organization=org, department=self.dept)
        DailyReport.objects.create(department=self.dept, author=self.emp,
                                   date=datetime.date(2026, 11, 26), content="ish")
        self.client = APIClient()

    def _login(self, email="xodim@test.uz", password="Parol-12345"):
        return APIClient().post("/api/auth/login/", {"email": email, "password": password}, format="json")

    def _archive(self):
        self.client.force_authenticate(self.admin)
        return self.client.post(f"/api/admin/users/{self.emp.pk}/archive/")

    # ── Arxivlash ────────────────────────────────────────────────
    def test_archive_blocks_login_with_clear_message(self):
        self.assertEqual(self._archive().status_code, 200)
        resp = self._login()
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data["code"], "account_archived")
        # Noto'g'ri parol bilan arxiv holati oshkor qilinmaydi
        self.assertNotEqual(self._login(password="xato").data.get("code"), "account_archived")

    def test_archive_revokes_existing_sessions(self):
        tokens = self._login().data
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(api.get("/api/auth/me/").status_code, 200)
        self._archive()
        self.assertEqual(api.get("/api/auth/me/").status_code, 401)  # access token darhol ishlamaydi
        resp = APIClient().post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(resp.status_code, 401)  # refresh blacklist'da

    def test_archived_email_cannot_register_again_any_case(self):
        self._archive()
        for email in ("xodim@test.uz", "XODIM@test.uz"):
            resp = APIClient().post("/api/auth/register/", {
                "email": email, "first_name": "A", "last_name": "B",
                "password": "Yangi-Parol-987", "password2": "Yangi-Parol-987"}, format="json")
            self.assertEqual(resp.status_code, 400, email)
            self.assertIn("email", resp.data)
        self.assertEqual(User.objects.filter(email__iexact="xodim@test.uz").count(), 1)

    def test_archived_hidden_from_list_and_cannot_toggle(self):
        self._archive()
        ids = {u["id"] for u in self.client.get("/api/admin/users/").data["results"]}
        self.assertNotIn(self.emp.pk, ids)
        ids = {u["id"] for u in self.client.get("/api/admin/users/?archived=1").data["results"]}
        self.assertIn(self.emp.pk, ids)
        self.assertEqual(self.client.post(f"/api/admin/users/{self.emp.pk}/toggle-active/").status_code, 400)
        self.emp.refresh_from_db()
        self.assertFalse(self.emp.is_active)

    def test_archive_keeps_data_and_unarchive_restores_login(self):
        self._archive()
        self.assertEqual(DailyReport.objects.filter(author=self.emp).count(), 1)
        self.assertEqual(self.client.post(f"/api/admin/users/{self.emp.pk}/unarchive/").status_code, 200)
        self.assertEqual(self._login().status_code, 200)

    def test_cannot_archive_or_delete_self(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/admin/users/{self.admin.pk}/archive/").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.admin.pk}/").status_code, 400)

    def test_only_super_admin(self):
        self.client.force_authenticate(self.emp)
        self.assertEqual(self.client.post(f"/api/admin/users/{self.admin.pk}/archive/").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.admin.pk}/").status_code, 403)

    # ── O'chirish ────────────────────────────────────────────────
    def test_delete_preview_lists_cascaded_data(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(f"/api/admin/users/{self.emp.pk}/delete-preview/")
        self.assertEqual(resp.status_code, 200)
        names = {row["name"]: row["count"] for row in resp.data["items"]}
        self.assertEqual(names.get("Kunlik hisobotlar"), 1)

    def test_delete_removes_user_and_frees_email(self):
        self.client.force_authenticate(self.admin)
        with self.assertLogs("audit", "INFO") as cm:
            self.assertEqual(self.client.delete(f"/api/admin/users/{self.emp.pk}/").status_code, 204)
        self.assertIn("event=user_deleted", cm.output[-1])
        self.assertFalse(User.objects.filter(pk=self.emp.pk).exists())
        self.assertEqual(DailyReport.objects.count(), 0)
