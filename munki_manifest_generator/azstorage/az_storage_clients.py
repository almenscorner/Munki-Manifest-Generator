#!/usr/bin/env python3

"""
This module is used to create clients for Azure Storage.
"""

from azure.storage.blob import BlobServiceClient, ContainerClient
from munki_manifest_generator.logger import logger


def az_container_client(connection_string: str, container_name: str) -> ContainerClient:
    """Create a container client to get the list of files in the container."""
    try:
        blob_source_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_source_service_client.get_container_client(container_name)

        return container_client

    except Exception as ex:
        logger.error("Error: " + str(ex))


def az_blob_client(connection_string: str, container_name: str, file_name: str) -> BlobServiceClient:
    """Create a blob client to get the file from the container."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        blob_client = blob_service_client.get_blob_client(container=container_name + "/manifests", blob=file_name)

        return blob_client

    except Exception as ex:
        logger.error("Error: " + str(ex))
