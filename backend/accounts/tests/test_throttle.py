from .base import AuthAPITestCase

BODY = {
    "email": "x@example.com",
    "password": "sai",
    "otp": "123456",
    "purpose": "LOGIN",
    "full_name": "X",
}


class ThrottleTests(AuthAPITestCase):
    throttle_rate = "5/min"  # mức thật của dự án

    def test_each_public_endpoint_limited_to_5_per_minute_per_ip(self) -> None:
        for name in ("register", "verify-email", "resend-otp", "login", "login-verify"):
            with self.subTest(endpoint=name):
                for _ in range(5):
                    self.assertNotEqual(self.post(name, BODY).status_code, 429)
                res = self.post(name, BODY)
                self.assertEqual(res.status_code, 429)
                self.assertGreater(int(res["Retry-After"]), 0)
