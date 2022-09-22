#!/usr/bin/env python3

"""
This module is used to obtain an access token for use with Graph API.
"""

from adal import AuthenticationContext


def obtain_access_token(client_id, client_secret, tenant_name):
    """Return an access token for use with Graph API."""

    auth_context = AuthenticationContext(
        "https://login.microsoftonline.com/" + tenant_name
    )

    token = auth_context.acquire_token_with_client_credentials(
        resource="https://graph.microsoft.com",
        client_id=client_id,
        client_secret=client_secret,
    )

    return token
