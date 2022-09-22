#!/usr/bin/env python3

import os

"""
This module checks that all reuired environment variables are set.
"""


def check_env_vars():
    """Check that the required env vars are set."""
    # Get environment variables for use with authentication and Azure Storage
    if os.environ.get("TENANT_NAME") is None:
        raise Exception("TENANT_NAME environment variable is not set")

    if os.environ.get("CLIENT_ID") is None:
        raise Exception("CLIENT_ID environment variable is not set")

    if os.environ.get("CLIENT_SECRET") is None:
        raise Exception("CLIENT_SECRET environment variable is not set")

    if os.environ.get("CONTAINER_NAME") is None:
        raise Exception("CONTAINER_NAME environment variable is not set")

    if os.environ.get("AZURE_STORAGE_CONNECTION_STRING") is None:
        raise Exception(
            "AZURE_STORAGE_CONNECTION_STRING environment variable is not set"
        )
