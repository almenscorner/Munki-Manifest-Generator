#!/usr/bin/env python3

import logging

from munki_manifest_generator.logger import logger

"""
This module is used to get the device group membership and update included manifests.
"""


def get_device_group_membership(responses, aad_device_id, groups, current_manifests, device_manifest):
    """Returns a list of group names the device is a member of and updates the included manifests."""

    try:
        memberOf = [val for list in responses if aad_device_id in list["deviceId"] for val in list["value"]]
        serial_number = device_manifest.__dict__["serialnumber"]

        if memberOf:
            device_groups = []
            device_groups_name = []

            for group_id in memberOf:
                id = group_id["id"]
                device_groups.append(id)
                device_groups_name.append(group_id["displayName"])

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[%s] Device found in groups: %s",
                    serial_number,
                    ", ".join(device_groups_name),
                )
                logger.debug(
                    "[%s] Groups from JSON or list: %s",
                    serial_number,
                    str(groups),
                )

            for group in groups:
                if group["type"] == "device":
                    if group["id"] in device_groups:
                        if group["name"] in current_manifests:
                            if group["name"] not in device_manifest.included_manifests:
                                logger.info(
                                    "[%s] Device found in group for %s, adding included manifest for group",
                                    serial_number,
                                    group["name"],
                                )
                                device_manifest.included_manifests.append(group["name"])
                        else:
                            logger.info(
                                "[%s] Device found in group for %s but manifest does not exist, skipping",
                                serial_number,
                                group["name"],
                            )

            return device_groups_name

    except Exception as e:
        logger.error(f"Device Groups failed with: {e}")
