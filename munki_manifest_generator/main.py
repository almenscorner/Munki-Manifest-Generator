#!/usr/bin/env python3

"""
This module creates and updates manifests for macOS devices in Intune.
"""

import os
import json
import time
import argparse
import threading

from operator import itemgetter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from munki_manifest_generator.graph.concurrent_batch import batch_request

from munki_manifest_generator.logger import logger
from munki_manifest_generator.azstorage.az_storage_actions import (
    get_current_manifest_blobs,
    delete_manifest_blob,
    update_manifest_blob,
    update_current_upn,
    get_current_device_manifest,
    create_manifest_blob,
)


def main(**kwargs):
    # Start timer
    startTime = time.time()

    # Set variables to None
    j = None
    g = None
    s = None
    t = None
    d = None
    c = None
    i = None
    l = None

    # If no kwargs are passed, parse arguments
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
            "-g",
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
            "-d",
            "--default_catalog",
            help="Default catalog for all devices. If not specified, the default catalog will be 'Production'.",
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
        argparser.add_argument(
            "-v",
            "--version",
            action="version",
            version="%(prog)s (version {version})".format(version="0.0.1"),
        )
        argparser.add_argument(
            "-l",
            "--log",
            help="Log level, default is INFO",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        )

        args = argparser.parse_args()

        if args.log:
            for handler in logger.handlers:
                handler.setLevel(args.log.upper())

        if args.test:
            logger.info("*****Testing mode enabled, no changes will be made to manifests on Azure Storage*****")

    # Else, set variables to kwargs
    else:
        s = kwargs.get("serial_number")
        j = kwargs.get("json_file")
        g = kwargs.get("group_list")
        sm = kwargs.get("safe_manifest")
        t = kwargs.get("test")
        d = kwargs.get("default_catalog")
        c = kwargs.get("certauth")
        i = kwargs.get("interactiveauth")
        l = kwargs.get("log")

        # If log level is passed, set it
        if l:
            choices = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if l in choices:
                for handler in logger.handlers:
                    handler.setLevel(l.upper())
            else:
                raise Exception("Invalid log level, choose from: DEBUG, INFO, WARNING, ERROR, CRITICAL")

        # If testing is enabled, log it
        if t:
            logger.info("*****Testing mode enabled, no changes will be made to manifests on Azure Storage*****")

    def run(
        json_file,
        group_list,
        serial_number,
        SAFE_MANIFEST,
        TEST,
        DEFAULT_CATALOG,
        CERTAUTH,
        INTERACTIVEAUTH,
    ):
        # Check if required environment variables are set
        if not all(
            [
                os.environ.get("CONTAINER_NAME"),
                os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
            ]
        ):
            raise Exception("Missing required environment variables, stopping...")

        # Set variables
        CONTAINER_NAME = os.environ.get("CONTAINER_NAME")
        CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        ENDPOINT = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"

        # If certificate or interactive auth is enabled, set APP to False
        if CERTAUTH or INTERACTIVEAUTH:
            APP = False
        else:
            APP = True

        # Get authentication token
        TOKEN = getAuth(APP, CERTAUTH, INTERACTIVEAUTH)
        # Get current manifests from Azure Storage
        CURRENT_MANIFESTS = get_current_manifest_blobs(CONNECTION_STRING, CONTAINER_NAME)
        # If custom default catalog is passed, set it
        if DEFAULT_CATALOG:
            DEFAULT_CATALOG = DEFAULT_CATALOG
        else:
            DEFAULT_CATALOG = "Production"
        # If a serial number is passed, create or update a manifest for that device
        if serial_number:
            Q_PARAM = {"$filter": "serialNumber eq '%s'" % serial_number}
            DEVICES = make_api_request(ENDPOINT, TOKEN, Q_PARAM)

            # If two objects are found, get the latest enrolled device
            if DEVICES["@odata.count"] > 1:
                latest_enrolled = max(DEVICES["value"], key=lambda x: x["enrolledDateTime"])
                DEVICES["value"] = [latest_enrolled]
                DEVICES["@odata.count"] = 1

            # If no device is returned, stop script
            if DEVICES["@odata.count"] == 0:
                logger.error(f"Device with serial {serial_number} not found, stopping...")
                quit()

        # Else, create or update manifests for all devices
        else:
            Q_PARAM = {"$filter": "operatingSystem eq 'macOS'"}
            DEVICES = make_api_request(ENDPOINT, TOKEN, Q_PARAM)
            # Check if there are duplicate entries for a device
            for d in DEVICES["value"]:
                for index, value in enumerate(DEVICES["value"]):
                    if d["serialNumber"] == value["serialNumber"]:
                        # If the device is enrolled more than once, get the latest enrolled device
                        if d["enrolledDateTime"] > value["enrolledDateTime"]:
                            # Remove the older device from the list
                            DEVICES["value"].remove(DEVICES["value"][index])

            import re
            def contains_random_uuid(upn):
                # Construct a regular expression pattern that matches the specified format
                pattern = re.compile(r"[A-Za-z]+([0-9]+([A-Za-z]+[0-9]+)+).*@.*", re.IGNORECASE)

                # Use the re module to search for the pattern in the input string
                match = re.search(pattern, upn)

                # If a match is found, return True; otherwise, return False
                if match:
                    return True
                else:
                    return False

            # Remove devices that have a UPN that contains a random UUID
            DEVICES["value"] = [d for d in DEVICES["value"] for key, val in d.items() if "userPrincipalName" in key if val is not None if not contains_random_uuid(val)]

            logger.info("-" * 90)
            logger.info(f"Found {len(CURRENT_MANIFESTS)} current manifests")
            logger.info(f'Found {len(DEVICES["value"])} devices')




            logger.info("-" * 90)

        # Get serial numbers, AAD device IDs, and UPNs for all devices
        SERIAL_NUMBERS = [val for d in DEVICES["value"] for key, val in d.items() if "serialNumber" in key if val is not None]

        AAD_DEVICE_IDS = [
            val for d in DEVICES["value"] for key, val in d.items() if "azureADDeviceId" in key if val is not None
        ]

        UPNs = [val for d in DEVICES["value"] for key, val in d.items() if "userPrincipalName" in key if val is not None]

        # Get list of group manifests from json file or list
        if json_file:
            with open(json_file, "r") as f:
                GROUPS = json.load(f)
        elif group_list:
            GROUPS = group_list
        else:
            raise Exception("No JSON file or list provided")

        # Batch get group memberships for all devices and users
        group_search = []
        for group in GROUPS:
            group_search.append('"displayName:%s"' % group["name"])

        group_search_query = f'({" OR ".join(group_search)})'

        if "device" in map(itemgetter("type"), GROUPS):
            # Batch get ids for all devices and users
            device_id_responses = batch_request(AAD_DEVICE_IDS, "devices", "", "deviceId", TOKEN)
            device_group_responses = batch_request(
                device_id_responses, "devices/", "/transitiveMemberOf?$search=%s" % group_search_query, "device", TOKEN
            )

        if "user" in map(itemgetter("type"), GROUPS):
            device_upn_responses = batch_request(UPNs, "users", "", "upn", TOKEN)
            user_group_responses = batch_request(
                device_upn_responses,
                "users/",
                "/transitiveMemberOf?$select=id,displayName&$search=%s" % group_search_query,
                "user",
                TOKEN,
            )

        # If not passing a serial number, delete manifest for device if it is not in Intune
        if not serial_number:
            delete_manifest_blob(
                CONNECTION_STRING,
                CONTAINER_NAME,
                GROUPS,
                SERIAL_NUMBERS,
                SAFE_MANIFEST,
                TEST,
                CURRENT_MANIFESTS,
            )

        def process_device(device):
            """Process each device"""

            lock = threading.Lock()
            group_membership = []
            # If a manifest exists for the device, update it.
            if device["serialNumber"] in CURRENT_MANIFESTS:
                logger.debug("[%s] Manifest found, checking for updates..." % device["serialNumber"])
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

                if device_manifest.user != device["userPrincipalName"]:
                    update_current_upn(
                        CONNECTION_STRING,
                        CONTAINER_NAME,
                        device_manifest.serialnumber,
                        device["userPrincipalName"],
                        device_manifest.user,
                        TEST,
                    )
                    device_manifest.user = device["userPrincipalName"]

                # If device groups are in the JSON or list, get the groups the device is in
                if "device" in map(itemgetter("type"), GROUPS):
                    device_groups = get_device_group_membership(
                        device_group_responses,
                        device["azureADDeviceId"],
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if device_groups:
                        with lock:
                            group_membership += device_groups

                # If user groups are in the JSON or list, get the groups the device's user is in
                if "user" in map(itemgetter("type"), GROUPS):
                    user_groups = get_user_group_membership(
                        user_group_responses,
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if user_groups:
                        with lock:
                            group_membership += user_groups

                update_manifest_blob(
                    CONNECTION_STRING,
                    CONTAINER_NAME,
                    device["serialNumber"],
                    device_manifest,
                    group_membership,
                    GROUPS,
                    TEST,
                    DEFAULT_CATALOG,
                    CURRENT_MANIFESTS,  # noqa: F821
                )

            # If no manifest exists for the device, create one.
            else:
                logger.info("[%s] No manifest found, creating..." % device["serialNumber"])
                device_manifest = Manifest(
                    catalogs=[DEFAULT_CATALOG],
                    included_manifests=["site_default"],
                    display_name=device["serialNumber"],
                    serialnumber=device["serialNumber"],
                    user=device["userPrincipalName"],
                )

                # If device groups are in the JSON or list, get the groups the device is in
                if "device" in map(itemgetter("type"), GROUPS):
                    device_groups = get_device_group_membership(
                        device_group_responses,
                        device["azureADDeviceId"],
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if device_groups:
                        with lock:
                            group_membership += device_groups

                # If user groups are in the JSON or list, get the groups the device's user is in
                if "user" in map(itemgetter("type"), GROUPS):
                    user_groups = get_user_group_membership(
                        user_group_responses,
                        GROUPS,
                        CURRENT_MANIFESTS,
                        device_manifest,
                    )
                    if user_groups:
                        with lock:
                            group_membership += user_groups

                device_manifest.catalogs = get_device_catalogs(GROUPS, device_manifest, DEFAULT_CATALOG, add_catalogs=True)

                create_manifest_blob(
                    CONNECTION_STRING,
                    CONTAINER_NAME,
                    device["serialNumber"],
                    device_manifest,
                    TEST,
                )

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_device, device) for device in DEVICES["value"] if device["serialNumber"]]
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    logger.error(f"Exception: {e}")

    if not kwargs:
        run(
            args.json,
            args.group_list,
            args.serial_number,
            args.safe_manifest,
            args.test,
            args.default_catalog,
            args.certauth,
            args.interactiveauth,
        )
    else:
        run(j, g, s, sm, t, d, c, i)

    logger.debug("Finished in {0} seconds.".format(time.time() - startTime))


if __name__ == "__main__":
    main()
