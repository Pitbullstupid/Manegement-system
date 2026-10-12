from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from django.urls import reverse

from accounts.models import Role, User
from common.permissions import IsAdmin, IsManagerOrAdmin, IsOwnerOrReadOnly

from .base import EMAIL, AuthAPITestCase


class AdminEndpointTests(AuthAPITestCase):
    def get_users(self, user=None):
        self.client.force_authenticate(user=user)
        return self.client.get(reverse("user-list"))

    def test_anonymous_gets_401(self) -> None:
        self.assertEqual(self.get_users().status_code, 401)

    def test_employee_gets_403(self) -> None:
        self.assertEqual(self.get_users(self.create_user(role=Role.EMPLOYEE)).status_code, 403)

    def test_manager_gets_403(self) -> None:
        self.assertEqual(self.get_users(self.create_user(role=Role.MANAGER)).status_code, 403)

    def test_admin_gets_200(self) -> None:
        res = self.get_users(self.create_user(role=Role.ADMIN))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_role_change_takes_effect_without_new_token(self) -> None:
        self.create_user(role=Role.EMPLOYEE)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {self.login_tokens()['access']}"}
        self.assertEqual(self.client.get(reverse("user-list"), **auth).status_code, 403)
        User.objects.filter(email=EMAIL).update(role=Role.ADMIN)
        self.assertEqual(self.client.get(reverse("user-list"), **auth).status_code, 200)


def _req(role: str, method: str = "GET") -> SimpleNamespace:
    return SimpleNamespace(user=User(email="x@example.com", role=role), method=method)


class PermissionClassTests(SimpleTestCase):
    def test_is_admin(self) -> None:
        self.assertTrue(IsAdmin().has_permission(_req(Role.ADMIN), None))
        self.assertFalse(IsAdmin().has_permission(_req(Role.MANAGER), None))
        self.assertFalse(IsAdmin().has_permission(SimpleNamespace(user=AnonymousUser()), None))

    def test_is_manager_or_admin(self) -> None:
        perm = IsManagerOrAdmin()
        self.assertTrue(perm.has_permission(_req(Role.ADMIN), None))
        self.assertTrue(perm.has_permission(_req(Role.MANAGER), None))
        self.assertFalse(perm.has_permission(_req(Role.EMPLOYEE), None))

    def test_is_owner_or_read_only(self) -> None:
        owner = User(email="owner@example.com")
        other = User(email="other@example.com")
        obj = SimpleNamespace(owner=owner)
        view = SimpleNamespace()
        perm = IsOwnerOrReadOnly()
        self.assertTrue(perm.has_object_permission(SimpleNamespace(user=other, method="GET"), view, obj))
        self.assertFalse(perm.has_object_permission(SimpleNamespace(user=other, method="PATCH"), view, obj))
        self.assertTrue(perm.has_object_permission(SimpleNamespace(user=owner, method="PATCH"), view, obj))
