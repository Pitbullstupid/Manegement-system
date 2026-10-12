"""Tiện ích dùng chung cho test."""
from django.test import override_settings

# Cache trong RAM (không đụng Redis dev) + hasher nhanh (test chạy nhanh hơn nhiều)
isolated_settings = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "epwms-tests",
        }
    },
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
