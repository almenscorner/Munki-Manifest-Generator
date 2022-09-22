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


def get_current_manifest_blobs(connection_string, container_name):
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
        print("Error: " + str(ex))

    return CURRENT_MANIFESTS


def create_manifest_blob(connection_string, container_name, file_name, device, test):
    """Creates a blob with the given file name and data."""
    try:
        local_path = "./"
        upload_file_path = os.path.join(local_path, file_name)

        with open(upload_file_path, "wb") as _f:
            plistlib.dump(device.__dict__, _f)

        blob_client = az_blob_client(connection_string, container_name, file_name)

        if not test:
            with open(upload_file_path, "rb") as data:
                blob_client.upload_blob(data)
        os.remove(upload_file_path)

    except Exception as ex:
        print("Error: " + str(ex))


def delete_manifest_blob(
    connection_string, container_name, groups, serial_numbers, safe_manifest, test
):
    """Deletes blobs in the container if the device is not in Intune."""
    try:
        # Get the list of blobs in the container
        current_manifests = get_current_manifest_blobs(
            connection_string, container_name
        )
        # Get list of group names
        groups = [val for list in groups for key, val in list.items() if key == "name"]
        delete_manifests = []
        if safe_manifest:
            do_not_delete_manifest = safe_manifest.lower().split(",")
        else:
            do_not_delete_manifest = []

        for manifest in current_manifests:
            # If the manifest is not in the list of serial numbers, is not in the list of groups, is not site_defualt, and is not in the list of safe manifests, add it to the list of manifests to delete
            if (
                (manifest not in serial_numbers)
                and (manifest not in groups)
                and (manifest != "site_default")
                and (manifest.lower() not in do_not_delete_manifest)
            ):
                delete_manifests.append(manifest)

                blob_client = az_blob_client(
                    connection_string, container_name, manifest
                )
                if not test:
                    blob_client.delete_blob()

        if delete_manifests:
            print(("{0:-^{1}}".format(str(len(delete_manifests)) + " deleted manifests", 90)))
            print("\n".join(delete_manifests))

    except Exception as ex:
        print("Error: " + str(ex))


def get_current_device_manifest(connection_string, container_name, serial_number):
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
        print("Error: " + str(ex))


def update_manifest_blob(
    connection_string,
    container_name,
    file_name,
    device_manifest,
    group_membership,
    groups,
    test,
):
    """Updates the manifest with the given file name and data."""
    try:
        local_path = "./"
        download_file_path = os.path.join(local_path, file_name)

        current_manifests = get_current_manifest_blobs(
            connection_string, container_name
        )

        blob_client = az_blob_client(connection_string, container_name, file_name)

        with open(download_file_path, "wb") as _f:
            blob_data = blob_client.download_blob()
            data = blob_data.readall()
            plist_data = plistlib.loads(data)
            add_catalogs = False
            add_manifests = []
            remove_manifests = []

            # Get updates to device catalogs
            add_catalog = get_device_catalogs(
                groups, device_manifest, add_catalogs=True
            )
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
                if manifest not in current_manifests:
                    print("Manifest " + manifest + " not found, skipping")
                    # If the manifest not in the current manifest list, but in the device manifest list, add it to the list of manifests to remove
                    if manifest in device_manifest.included_manifests:
                        device_manifest.included_manifests.remove(manifest)
                        remove_manifests.append(manifest)
                    # If the manifest is not in the current manifest list, but in the add manifest list, remove it from the add manifest list
                    if manifest in add_manifests:
                        add_manifests.remove(manifest)

            # Check if the device is a member of any AAD group based included manifest but not the AAD group
            for group_manifest in plist_data["included_manifests"]:
                # If the AAD group based manifest is not in the device's membership list, add it to the list of manifests to remove
                if (group_manifest not in group_membership) and (
                    group_manifest != "site_default"
                ):
                    remove_manifests.append(group_manifest)

            # If there are manifests to remove, remove them
            if remove_manifests:
                for manifest in remove_manifests:
                    plist_data["included_manifests"].remove(manifest)
                    device_manifest.included_manifests = plist_data[
                        "included_manifests"
                    ]

            # Check if there are catalogs to remove
            remove_catalogs = get_device_catalogs(
                groups, device_manifest, remove_catalogs=True
            )

            plistlib.dump(device_manifest.__dict__, _f)

        if add_manifests or add_catalogs or remove_manifests or remove_catalogs:
            print("Manifests or catalogs changed, updating")
            if add_manifests:
                print("Manifests: \n" + " - " + "\n - ".join(add_manifests))
            if add_catalogs:
                print("Catalogs: \n" + " - " + "\n - ".join(add_catalog))
            if remove_manifests:
                print("Manifests removed: \n" + " - " + "\n - ".join(remove_manifests))
            if remove_catalogs:
                print("Catalogs removed: \n" + " - " + "\n - ".join(remove_catalogs))
            if not test:
                with open(download_file_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

        os.remove(download_file_path)

    except Exception as ex:
        print("Error: " + str(ex))
