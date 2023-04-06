#!/usr/bin/env python3

import logging

from munki_manifest_generator.logger import logger

"""
This module is used to get the user group membership and update included manifests.
"""


ENDPOINT = "https://graph.microsoft.com/v1.0/users"


def get_user_group_membership(responses, groups, current_manifests, device_manifest):
    """Returns a list of group names the user is a member of and updates the included manifests."""

    user = device_manifest.__dict__["user"]
    serial_number = device_manifest.__dict__["serialnumber"]
    memberOf = [val for val in responses if user in val["userPrincipalName"] for val in val["value"]]

    if memberOf:
        user_groups = []
        user_groups_name = []

        for group_id in memberOf:
            id = group_id["id"]
            user_groups.append(id)
            user_groups_name.append(group_id["displayName"])

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "[%s] User found in groups: %s",
                serial_number,
                ", ".join(user_groups_name),
            )
            logger.debug(
                "[%s] Groups from JSON or list: %s",
                serial_number,
                str(groups),
            )

        for group in groups:
            if group["type"] == "user":
                if group["id"] in user_groups:
                    if group["name"] in current_manifests:
                        if group["name"] not in device_manifest.included_manifests:
                            logger.info(
                                "[%s] User found in group for %s, adding included manifest for group",
                                serial_number,
                                group["name"],
                            )
                            device_manifest.included_manifests.append(group["name"])
                    else:
                        logger.info(
                            "[%s] User found in group for %s but manifest does not exist, skipping",
                            serial_number,
                            group["name"],
                        )

        return user_groups_name

    else:
        logger.warning(
            "[%s] User not found in any groups",
            serial_number,
        )
