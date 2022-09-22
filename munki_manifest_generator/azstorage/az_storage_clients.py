#!/usr/bin/env python3

"""
This module is used to create clients for Azure Storage.
"""

from azure.storage.blob import BlobServiceClient


def az_container_client(connection_string, container_name):
    """Create a container client to get the list of files in the container."""
    try:
        blob_source_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        container_client = blob_source_service_client.get_container_client(
            container_name
        )

        return container_client

    except Exception as ex:
        print("Error: " + str(ex))


def az_blob_client(connection_string, container_name, file_name):
    """Create a blob client to get the file from the container."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        blob_client = blob_service_client.get_blob_client(
            container=container_name + "/manifests", blob=file_name
        )

        return blob_client

    except Exception as ex:
        print("Error: " + str(ex))
