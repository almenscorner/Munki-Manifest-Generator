#!/usr/bin/env python3

"""
This module creates and updates manifests for macOS devices in Intune.
"""

import os
import json
import argparse

from operator import itemgetter
from munki_manifest_generator.manifest import Manifest
from munki_manifest_generator.graph.get_authentication_token import getAuth
from munki_manifest_generator.graph.make_api_request import make_api_request
from munki_manifest_generator.graph.get_device_group_membership import (
    get_device_group_membership,
)
from munki_manifest_generator.graph.get_user_group_membership import (
    get_user_group_membership,
)
from munki_manifest_generator.get_device_catalogs import get_device_catalogs
from munki_manifest_generator.azstorage.az_storage_actions import (
    get_current_manifest_blobs,
    delete_manifest_blob,
    update_manifest_blob,
    get_current_device_manifest,
    create_manifest_blob,
)


def main(**kwargs):

    j = None
    l = None
    s = None
    t = None
    c = None
    i = None

    if not kwargs:
        argparser = argparse.ArgumentParser()
        argparser.add_argument(
            "-s",
            "--serial_number",
            help="Serial number to create or update a manifest for",
        )
        argparser.add_argument(
            "-j",
            "--json",
            help="Path to JSON file containing AzureAD groups specifying manifests devices should be in.",
        )
        argparser.add_argument(
            "-l",
            "--group_list",
            help="List of dicts containing AzureAD groups specifying manifests devices should be in.",
        )
        argparser.add_argument(
            "-sm",
            "--safe_manifest",
            help="Manifests specified here are safe from deletion, site_default does not have to be specified.",
        )
        argparser.add_argument(
            "-t",
           "--test",
            help="Enable testing, no changes will be made to manifests on Azure Storage.",
            action="store_true",
        )
        argparser.add_argument(
            "-c",
            "--certauth",
            help="When using certificate auth, the following ENV variables is required: TENANT_NAME, CLIENT_ID, THUMBPRINT, KEY_FILE",
            action="store_true",
        )
        argparser.add_argument(
            "-i",
            "--interactiveauth",
            help="When using interactive auth, the following ENV variables is required: TENANT_NAME, CLIENT_ID",
            action="store_true",
        )

        args = argparser.parse_args()

        if args.test:
            print(
                "*****Testing mode enabled, no changes will be made to manifests on Azure Storage*****"
            )

    else:
        s = kwargs.get("serial_number")
        j = kwargs.get("json_file")
        l = kwargs.get("group_list")
        sm = kwargs.get("safe_manifest")
        t = kwargs.get("test")
        c = kwargs.get("certauth")
        i = kwargs.get("interactiveauth")

        if t:
            print(
                "*****Testing mode enabled, no changes will be made to manifests on Azure Storage*****"
            )


    def run(json_file, group_list, serial_number, SAFE_MANIFEST, TEST, CERTAUTH, INTERACTIVEAUTH):

        if not all([os.environ.get("CONTAINER_NAME"), os.environ.get("AZURE_STORAGE_CONNECTION_STRING")]):
            raise Exception("Missing required environment variables, stopping...")
        CONTAINER_NAME = os.environ.get("CONTAINER_NAME")
        CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        ENDPOINT = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
        if not CERTAUTH and not INTERACTIVEAUTH:
            APP = True
        else:
            APP = False
        TOKEN = getAuth(APP, CERTAUTH, INTERACTIVEAUTH)
        CURRENT_MANIFESTS = get_current_manifest_blobs(
            CONNECTION_STRING, CONTAINER_NAME
        )
        # If a serial number is passed, create or update a manifest for that device
        if serial_number:
            Q_PARAM = {"$filter": "serialNumber eq '%s'" % serial_number}
            DEVICES = make_api_request(ENDPOINT, TOKEN, Q_PARAM)

            # If two objects are found, get the latest enrolled device
            if DEVICES["@odata.count"] > 1:
                latest_enrolled = max(
                    DEVICES["value"], key=lambda x: x["enrolledDateTime"]
                )
                DEVICES["value"] = [latest_enrolled]
                DEVICES["@odata.count"] = 1

            # If no device is returned, stop script
            if DEVICES["@odata.count"] == 0:
                print(f"Device with serial {serial_number} not found, stopping...")
                quit()

        # Else, create or update manifests for all devices
        else:
            Q_PARAM = {"$filter": "operatingSystem eq 'macOS'"}
            DEVICES = make_api_request(ENDPOINT, TOKEN, Q_PARAM)
            # Check if there are duplicate entries for a device
            for d in DEVICES['value']:
                for index, value in enumerate(DEVICES['value']):
                    if d['serialNumber'] == value['serialNumber']:
                        # If the device is enrolled more than once, get the latest enrolled device
                        if d['enrolledDateTime'] > value['enrolledDateTime']:
                            # Remove the older device from the list
                            DEVICES['value'].remove(DEVICES['value'][index])

            print("-" * 90)
            print(f"Found {len(CURRENT_MANIFESTS)} current manifests")
            print(f"Found {DEVICES['@odata.count']} devices")

        SERIAL_NUMBERS = [
            val
            for d in DEVICES["value"]
            for key, val in d.items()
            if "serialNumber" in key
            if val is not None
        ]

        # Get list of group manifests from json file or list
        if json_file:
            with open(json_file, "r") as f:
                GROUPS = json.load(f)
        elif group_list:
            GROUPS = group_list
        else:
            raise Exception("No JSON file or list provided")

        # If not passing a serial number, delete manifest for device if it is not in Intune
        if not serial_number:
            delete_manifest_blob(
                CONNECTION_STRING, CONTAINER_NAME, GROUPS, SERIAL_NUMBERS, SAFE_MANIFEST, TEST
            )

        for device in DEVICES["value"]:

            if not device["serialNumber"]:
                continue

            group_membership = []
            # If a manifest exists for the device, update it.
            if device["serialNumber"] in CURRENT_MANIFESTS:
                
                print("{0:-^{1}}".format(device["serialNumber"], 90))
                print("Manifest found, checking for updates")

                current_device_manifest = get_current_device_manifest(
                    CONNECTION_STRING, CONTAINER_NAME, device["serialNumber"]
                )

                device_manifest = Manifest(
                    catalogs=current_device_manifest["catalogs"],
                    included_manifests=current_device_manifest["included_manifests"],
                    display_name=current_device_manifest["display_name"],
                    serialnumber=current_device_manifest["serialnumber"],
                    user=current_device_manifest["user"],
                )

                # If device groups are in the JSON or list, get the groups the device is in
                if "device" in map(itemgetter("type"), GROUPS):
                    device_groups = get_device_group_membership(
                        TOKEN,
                        device["azureADDeviceId"],
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if device_groups:
                        group_membership += device_groups

                # If user groups are in the JSON or list, get the groups the device's user is in
                if "user" in map(itemgetter("type"), GROUPS):
                    user_groups = get_user_group_membership(
                        TOKEN,
                        device["userPrincipalName"],
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if user_groups:
                        group_membership += user_groups

                update_manifest_blob(
                    CONNECTION_STRING,
                    CONTAINER_NAME,
                    device["serialNumber"],
                    device_manifest,
                    group_membership,
                    GROUPS,
                    TEST
                )

            # If no manifest exists for the device, create one.
            else:
                print("{0:-^{1}}".format(device["serialNumber"], 90))
                print("Manifest not found, creating")

                device_manifest = Manifest(
                    catalogs=["Production"],
                    included_manifests=["site_default"],
                    display_name=device["serialNumber"],
                    serialnumber=device["serialNumber"],
                    user=device["userPrincipalName"],
                )

                # If device groups are in the JSON or list, get the groups the device is in
                if "device" in map(itemgetter("type"), GROUPS):
                    device_groups = get_device_group_membership(
                        TOKEN,
                        device["azureADDeviceId"],
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if device_groups:
                        group_membership += device_groups

                # If user groups are in the JSON or list, get the groups the device's user is in
                if "user" in map(itemgetter("type"), GROUPS):
                    user_groups = get_user_group_membership(
                        TOKEN,
                        device["userPrincipalName"],
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if user_groups:
                        group_membership += user_groups

                device_manifest.catalogs = get_device_catalogs(
                    GROUPS, device_manifest, add_catalogs=True
                )

                create_manifest_blob(
                    CONNECTION_STRING,
                    CONTAINER_NAME,
                    device["serialNumber"],
                    device_manifest,
                    TEST
                )

    if not kwargs:
        run(args.json, args.group_list, args.serial_number, args.safe_manifest, args.test, args.certauth, args.interactiveauth)
    else:
        run(j, l, s, sm, t, c, i)


if __name__ == "__main__":
    main()
