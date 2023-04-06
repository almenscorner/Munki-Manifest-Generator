#!/usr/bin/env python3

"""
This module contains functions for interacting with the Azure Blob Storage
"""

import os
import plistlib

from munki_manifest_generator.azstorage.az_storage_clients import (
    az_blob_client,
    az_container_client,
)
from munki_manifest_generator.get_device_catalogs import get_device_catalogs
from munki_manifest_generator.logger import logger


def get_current_manifest_blobs(connection_string: str, container_name: str) -> list:
    """Returns a list of the blob names in the container."""
    CURRENT_MANIFESTS = []
    try:
        # Create the BlobServiceClient object which will be used to create a container client
        container_client = az_container_client(connection_string, container_name)
        # List the blobs in the container
        source_blob_list = container_client.list_blobs(name_starts_with="manifests/")
        # Get the name of each blob
        for blob in source_blob_list:
            blob_name = blob.name.rsplit("/", 1)[1]
            CURRENT_MANIFESTS.append(blob_name)

    except Exception as ex:
        logger.error("Error: " + str(ex))

    return CURRENT_MANIFESTS


def create_manifest_blob(connection_string: str, container_name: str, file_name: str, device: dict, test: bool):
    """Creates a blob with the given file name and data."""
    try:
        local_path = "./"
        upload_file_path = os.path.join(local_path, file_name)

        with open(upload_file_path, "wb") as _f:
            plistlib.dump(device.__dict__, _f)

        blob_client = az_blob_client(connection_string, container_name, file_name)

        if not test:
            with open(upload_file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
        os.remove(upload_file_path)

    except Exception as ex:
        logger.error("Error: " + str(ex))


def delete_manifest_blob(
    connection_string: str,
    container_name: str,
    groups: list,
    serial_numbers: list,
    safe_manifest: str,
    test: bool,
    current_manifest_list: list,
):
    """Deletes blobs in the container if the device is not in Intune."""

    try:
        # Get list of group names
        groups = [val for val in groups for key, val in val.items() if key == "name"]
        delete_manifests = []
        if safe_manifest:
            do_not_delete_manifest = safe_manifest.lower().split(",")
        else:
            do_not_delete_manifest = []

        for manifest in current_manifest_list:
            # If the manifest is not in the list of serial numbers,
            # is not in the list of groups, is not site_default,
            # and is not in the list of safe manifests, add it to the list of manifests to delete
            if (
                (manifest not in serial_numbers)
                and (manifest not in groups)
                and (manifest != "site_default")
                and (manifest.lower() not in do_not_delete_manifest)
            ):
                delete_manifests.append(manifest)

                blob_client = az_blob_client(connection_string, container_name, manifest)
                if not test:
                    blob_client.delete_blob()

        if delete_manifests:
            logger.info(("{0:-^{1}}".format(str(len(delete_manifests)) + " deleted manifests", 90)))
            logger.info(", ".join(delete_manifests))
            logger.info("-" * 90)

    except Exception as ex:
        logger.error("Error: " + str(ex))


def update_current_upn(connection_string: str, container_name: str, serial_number: str, upn: str, old_user: str, test: bool):
    """Updates the UPN in the manifest for the given serial number."""

    try:
        logger.info("[%s] Updating user to %s from %s", serial_number, upn, old_user)
        local_path = "./"
        download_file_path = os.path.join(local_path, serial_number)
        blob_client = az_blob_client(connection_string, container_name, serial_number)

        with open(download_file_path, "wb") as _f:
            blob_data = blob_client.download_blob()
            data = blob_data.readall()
            plist_data = plistlib.loads(data)

        plist_data["user"] = upn

        with open(download_file_path, "wb") as _f:
            plistlib.dump(plist_data, _f)

        blob_client = az_blob_client(connection_string, container_name, serial_number)

        if not test:
            with open(download_file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

        os.remove(download_file_path)

    except Exception as ex:
        logger.error("Error: " + str(ex))


def get_current_device_manifest(connection_string: str, container_name: str, serial_number: str) -> dict:
    """Returns the current manifest for the given serial number."""

    try:
        local_path = "./"
        download_file_path = os.path.join(local_path, serial_number)
        blob_client = az_blob_client(connection_string, container_name, serial_number)

        with open(download_file_path, "wb") as _f:
            blob_data = blob_client.download_blob()
            data = blob_data.readall()
            plist_data = plistlib.loads(data)

        os.remove(download_file_path)

        return plist_data

    except Exception as ex:
        logger.error("Error: " + str(ex))


def update_manifest_blob(
    connection_string: str,
    container_name: str,
    file_name: str,
    device_manifest: dict,
    group_membership: list,
    groups: list,
    test: bool,
    default_catalog: str,
    current_manifest_list: list,
) -> list:
    """Updates the manifest with the given file name and data."""

    try:
        local_path = "./"
        download_file_path = os.path.join(local_path, file_name)

        blob_client = az_blob_client(connection_string, container_name, file_name)

        with open(download_file_path, "wb") as _f:
            blob_data = blob_client.download_blob()
            data = blob_data.readall()
            plist_data = plistlib.loads(data)
            add_catalogs = False
            add_manifests = []
            remove_manifests = []

            # Get updates to device catalogs
            add_catalog = get_device_catalogs(groups, device_manifest, default_catalog, add_catalogs=True)
            # If updated catalogs are not equal to the current catalogs, update the manifest
            if add_catalog != device_manifest.catalogs:
                device_manifest.catalogs = add_catalog
                add_catalogs = True

            # Get updates to device manifests
            for manifest in device_manifest.included_manifests:
                # If manifest is not in the device's current manifest list, add it to the list of manifests to add
                if manifest not in plist_data["included_manifests"]:
                    add_manifests.append(manifest)
                # If manifest is in the current manifest list, remove it from the list of manifests to add
                if manifest not in current_manifest_list:
                    logger.info("[%s] Manifest %s not found, skipping", file_name, manifest)
                    # If the manifest not in the current manifest list,
                    # but in the device manifest list, add it to the list of manifests to remove
                    if manifest in device_manifest.included_manifests:
                        device_manifest.included_manifests.remove(manifest)
                        remove_manifests.append(manifest)
                    # If the manifest is not in the current manifest list, but in the add manifest list,
                    # remove it from the add manifest list
                    if manifest in add_manifests:
                        add_manifests.remove(manifest)

            # Check if the device is a member of any AAD group based included manifest but not the AAD group
            for group_manifest in plist_data["included_manifests"]:
                # If the AAD group based manifest is not in the device's membership list,
                # add it to the list of manifests to remove
                if (group_manifest not in group_membership) and (group_manifest != "site_default"):
                    remove_manifests.append(group_manifest)

            # If there are manifests to remove, remove them
            if remove_manifests:
                for manifest in remove_manifests:
                    plist_data["included_manifests"].remove(manifest)
                    device_manifest.included_manifests = plist_data["included_manifests"]

            # Check if there are catalogs to remove
            remove_catalogs = get_device_catalogs(groups, device_manifest, default_catalog, remove_catalogs=True)

            plistlib.dump(device_manifest.__dict__, _f)

        if add_manifests or add_catalogs or remove_manifests or remove_catalogs:
            # logger.info("[%s] Manifests or catalogs changed, updating..." % file_name)
            if add_manifests:
                logger.info("[%s] " % file_name + "New manifest list: " + ", ".join(add_manifests))
            if add_catalogs:
                logger.info("[%s] " % file_name + "New catalog list: " + ", ".join(add_catalog))
            if remove_manifests:
                logger.info("[%s] " % file_name + "Manifests removed: " + ", ".join(remove_manifests))
            if remove_catalogs:
                logger.info("[%s] " % file_name + "Catalogs removed: " + ", ".join(remove_catalogs))

            if not test:
                with open(download_file_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

        os.remove(download_file_path)

    except Exception as ex:
        logger.error("Error: " + str(ex))
