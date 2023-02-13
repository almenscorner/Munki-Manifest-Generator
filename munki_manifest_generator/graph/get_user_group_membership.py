#!/usr/bin/env python3

"""
This module is used to get the user group membership and update included manifests.
"""

from munki_manifest_generator.graph.make_api_request import make_api_request

ENDPOINT = "https://graph.microsoft.com/v1.0/users"


def get_user_group_membership(token, upn, groups, current_manifests, device_manifest):
    """Returns a list of group names the user is a member of and updates the included manifests."""

    aad_user_object_id = None
    q_param_user = {"$filter": "userPrincipalName eq '%s'" % upn}
    user_object = make_api_request(ENDPOINT, token, q_param_user)

    for id in user_object["value"]:
        object_id = id["id"]
        aad_user_object_id = object_id
    q_param_group = {"$select": "id,displayName"}

    # If Azure AD user id is none, skip getting groups
    if aad_user_object_id is None:
        print("AAD User ID is null, skipping user group memberships")

    else:
        memberOf = make_api_request(
            ENDPOINT + "/" + aad_user_object_id + "/transitiveMemberOf", token, q_param_group
        )

        user_groups = []
        user_groups_name = []

        for group_id in memberOf["value"]:
            id = group_id["id"]
            user_groups.append(id)
            user_groups_name.append(group_id["displayName"])

        for group in groups:
            if group["type"] == "user":
                if group["id"] in user_groups:
                    if group["name"] in current_manifests:
                        if group["name"] not in device_manifest.included_manifests:
                            print(
                                "User found in group for "
                                + group["name"]
                                + ", adding included manifest for group"
                            )
                            device_manifest.included_manifests.append(group["name"])
                    else:
                        print(
                            "User found in group for "
                            + (group["name"])
                            + " but manifest does not exist, skipping"
                        )

        return user_groups_name
