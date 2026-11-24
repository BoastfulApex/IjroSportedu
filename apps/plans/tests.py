import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRoleAssignment
from apps.organizations.models import Department, Organization

from apps.plans.models import DailyReport, WeeklyReport, WorkPlan


class ReportVisibilityTests(TestCase):
    """Kunlik/haftalik hisobotlar: kim ko'radi, kim o'zgartira oladi."""

    def setUp(self):
        org = Organization.objects.create(name="Institut", org_type="MAIN")
        self.dept_a = Department.objects.create(name="A bo'lim", organization=org)
        self.dept_b = Department.objects.create(name="B bo'lim", organization=org)
        orders = Department.objects.create(name="Buyruqlar", organization=org, dept_type="ORDER_CONTROL")

        def user(email, role=UserRoleAssignment.Role.EMPLOYEE, dept=None, **flags):
            u = User.objects.create_user(email=email, password="Parol-12345", is_active=True)
            UserRoleAssignment.objects.create(user=u, role=role, organization=org, department=dept, **flags)
            return u

        self.author_a = user("a@test.uz", dept=self.dept_a)
        self.employee_b = user("b@test.uz", dept=self.dept_b)
        self.order_clerk = user("buyruq@test.uz", dept=orders)
        self.rector = user("rektor@test.uz", role=UserRoleAssignment.Role.INSTITUTE_LEADER)
        self.admin = user("sa@test.uz", role=UserRoleAssignment.Role.SUPER_ADMIN)

        self.report_a = DailyReport.objects.create(
            department=self.dept_a, author=self.author_a, date=datetime.date(2026, 11, 24), content="A ishi")
        self.weekly_a = WeeklyReport.objects.create(
            department=self.dept_a, year=2026, week_number=48,
            week_start=datetime.date(2026, 11, 23), week_end=datetime.date(2026, 11, 29))
        self.client = APIClient()

    def _ids(self, user, url):
        self.client.force_authenticate(user)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return {row["id"] for row in resp.data}

    def test_order_control_sees_other_departments(self):
        self.assertIn(self.report_a.id, self._ids(self.order_clerk, "/api/plans/daily-reports/"))
        self.assertIn(self.weekly_a.id, self._ids(self.order_clerk, "/api/plans/weekly-reports/"))

    def test_rector_and_admin_see_all(self):
        self.assertIn(self.report_a.id, self._ids(self.rector, "/api/plans/daily-reports/"))
        self.assertIn(self.report_a.id, self._ids(self.admin, "/api/plans/daily-reports/"))

    def test_regular_employee_sees_only_own_department(self):
        self.assertNotIn(self.report_a.id, self._ids(self.employee_b, "/api/plans/daily-reports/"))
        self.assertNotIn(self.weekly_a.id, self._ids(self.employee_b, "/api/plans/weekly-reports/"))

    def test_viewers_cannot_modify_other_departments(self):
        for viewer in (self.order_clerk, self.rector):
            self.client.force_authenticate(viewer)
            url = f"/api/plans/daily-reports/{self.report_a.id}/"
            self.assertEqual(self.client.patch(url, {"content": "x"}, format="json").status_code, 404)
            self.assertEqual(self.client.delete(url).status_code, 404)
            resp = self.client.post(f"/api/plans/weekly-reports/{self.weekly_a.id}/extras/",
                                    {"content": "begona band"}, format="json")
            self.assertEqual(resp.status_code, 404)
        self.report_a.refresh_from_db()
        self.assertEqual(self.report_a.content, "A ishi")
        self.assertEqual(self.weekly_a.extras.count(), 0)

    def test_author_and_super_admin_can_modify(self):
        self.client.force_authenticate(self.author_a)
        url = f"/api/plans/daily-reports/{self.report_a.id}/"
        self.assertEqual(self.client.patch(url, {"content": "yangilandi"}, format="json").status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_order_control_cannot_approve_work_plans(self):
        # Hisobotlarni ko'rish huquqi ish rejasini tasdiqlash huquqini bermaydi

        plan = WorkPlan.objects.create(department=self.dept_a, year=2026, created_by=self.author_a)
        self.client.force_authenticate(self.order_clerk)
        resp = self.client.post(f"/api/plans/work-plans/{plan.id}/approve/")
        self.assertIn(resp.status_code, (403, 404))
