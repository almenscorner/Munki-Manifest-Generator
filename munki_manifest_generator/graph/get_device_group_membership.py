#!/usr/bin/env python3

"""
This module is used to get the device group membership and update included manifests.
"""

from munki_manifest_generator.graph.make_api_request import make_api_request

ENDPOINT = "https://graph.microsoft.com/v1.0/devices"


def get_device_group_membership(
    token, aad_device_id, groups, current_manifests, device_manifest
):
    """Returns a list of group names the device is a member of and updates the included manifests."""

    aad_device_object_id = None
    q_param_device = {"$filter": "deviceId eq " + "'" + aad_device_id + "'"}
    device_object = make_api_request(ENDPOINT, token, q_param_device)

    for id in device_object["value"]:
        object_id = id["id"]
        aad_device_object_id = object_id
    q_param_group = {"$select": "id,displayName"}

    # If Azure AD device id is none, skip getting groups
    if aad_device_object_id is None:
        print("AAD Device ID is null, skipping device group memberships")

    else:
        memberOf = make_api_request(
            ENDPOINT + "/" + aad_device_object_id + "/transitiveMemberOf", token, q_param_group
        )
            
        device_groups = []
        device_groups_name = []

        for group_id in memberOf["value"]:
            id = group_id["id"]
            device_groups.append(id)
            device_groups_name.append(group_id["displayName"])

        for group in groups:
            if group["type"] == "device":
                if group["id"] in device_groups:
                    if group["name"] in current_manifests:
                        if group["name"] not in device_manifest.included_manifests:
                            print(
                                "Device found in group for "
                                + group["name"]
                                + ", adding included manifest for group"
                            )
                            device_manifest.included_manifests.append(group["name"])
                    else:
                        print(
                            "Device found in group for "
                            + (group["name"])
                            + " but manifest does not exist, skipping"
                        )

        return device_groups_name
