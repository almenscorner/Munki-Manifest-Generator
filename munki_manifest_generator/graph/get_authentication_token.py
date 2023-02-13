#!/usr/bin/env python3

"""
This module is used to get the access token for the tenant.
"""

import os
import json

from munki_manifest_generator.graph.obtain_access_token import obtain_accesstoken_app, obtain_accesstoken_cert, obtain_accesstoken_interactive

def getAuth(app, certauth, interactiveauth):
    """
    This function authenticates to MS Graph and returns the access token.

    :param mode: The mode used when using this tool
    :param localauth: Path to dict with keys to authenticate
    :param tenant: Which tenant to authenticate to, PROD or DEV
    :return: The access token
    """

    if certauth:
        KEY_FILE = os.environ.get("KEY_FILE")
        THUMBPRINT = os.environ.get("THUMBPRINT")
        TENANT_NAME = os.environ.get("TENANT_NAME")
        CLIENT_ID = os.environ.get("CLIENT_ID")

        if not all([KEY_FILE, THUMBPRINT, TENANT_NAME, CLIENT_ID]):
            raise Exception("One or more os.environ variables not set")
        return obtain_accesstoken_cert(TENANT_NAME, CLIENT_ID, THUMBPRINT, KEY_FILE)

    if interactiveauth:
        TENANT_NAME = os.environ.get("TENANT_NAME")
        CLIENT_ID = os.environ.get("CLIENT_ID")

        if not all([TENANT_NAME, CLIENT_ID]):
            raise Exception("One or more os.environ variables not set")

        return obtain_accesstoken_interactive(TENANT_NAME, CLIENT_ID)

    if app:
        TENANT_NAME = os.environ.get("TENANT_NAME")
        CLIENT_ID = os.environ.get("CLIENT_ID")
        CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
        if not all([TENANT_NAME, CLIENT_ID, CLIENT_SECRET]):
            raise Exception("One or more os.environ variables not set")

        return obtain_accesstoken_app(TENANT_NAME, CLIENT_ID, CLIENT_SECRET)
