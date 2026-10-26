"""Social sign-in, starting with Google.

Facebook is deliberately not wired here yet: it uses the same
``SocialAccount`` table and the same complete-profile flow, so adding it
later means adding one provider module and two routes, not a new identity
model.  Provider secrets are never stored in the database; only the
provider name, the provider's user id and the verified email are kept,
which keeps a later move to Supabase Auth a swap of this boundary layer
instead of a rewrite of users, courses and enrollments.
"""

from __future__ import annotations

import os
import secrets
from urllib.parse import urlencode

import requests
from flask import session, url_for

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def google_configured() -> bool:
    """True only when a Google OAuth client is configured."""
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def safe_next(value: str | None) -> str | None:
    """Accept only a relative in-app path, never an external redirect."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    return value


def google_login_url(next_url: str | None = None) -> str:
    """Build the Google authorization URL and remember state + destination."""
    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state
    if next_url:
        session["google_oauth_next"] = next_url
    else:
        session.pop("google_oauth_next", None)
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": url_for("google_callback", _external=True),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return GOOGLE_AUTHORIZATION_URL + "?" + urlencode(params)


def exchange_google_code(code: str, state: str | None) -> dict:
    """Exchange an authorization code for a verified Google identity.

    Raises ValueError with a user-facing message on any failure, so the
    route layer can flash it instead of leaking provider details.
    """
    expected_state = session.pop("google_oauth_state", None)
    if not state or not expected_state or state != expected_state:
        raise ValueError("Phiên đăng nhập Google đã hết hạn. Vui lòng thử lại.")
    if not google_configured():
        raise ValueError("Đăng nhập Google chưa được cấu hình trên máy chủ này.")
    try:
        token_response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": url_for("google_callback", _external=True),
            },
            timeout=15,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise ValueError("Google không trả về mã truy cập.")
        user_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        user_response.raise_for_status()
        profile = user_response.json()
    except requests.RequestException:
        raise ValueError("Không kết nối được tới Google. Vui lòng thử lại sau.") from None
    provider_user_id = profile.get("sub")
    email = (profile.get("email") or "").strip().lower()
    verified = profile.get("email_verified") in (True, "true") or profile.get("verified_email") is True
    if not provider_user_id or not email or not verified:
        raise ValueError("Google chưa xác minh email của tài khoản này.")
    return {
        "provider": "google",
        "provider_user_id": str(provider_user_id),
        "email": email,
        "name": (profile.get("name") or "").strip(),
    }
