#!/usr/bin/env python3

"""
This module is used to get the catalogs that should be added or removed from a device.
"""

from collections import defaultdict


def get_device_catalogs(
    groups, device_manifest, default_catalog, add_catalogs=False, remove_catalogs=False
) -> list:
    """Get the catalogs that should be added or removed from a device."""

    GROUP_CATALOGS = [
        val
        for list in groups
        for key, val in list.items()
        if "catalog" in key
        if val is not None
    ]

    if add_catalogs:
        catalogs = [default_catalog]

        for group in groups:
            if group["catalog"] is not None:
                if (
                    group["name"] in device_manifest.included_manifests
                    and group["catalog"] not in catalogs
                ):
                    catalogs.insert(0, group["catalog"])

        catalogs = list(set(catalogs))

        return catalogs

    if remove_catalogs:
        catalogs_to_remove = []

        grouped_by_catalog = defaultdict(list)
        for item in groups:
            grouped_by_catalog[item["catalog"]].append(item)

        multiple_result = dict(grouped_by_catalog)

        for catalog in device_manifest.catalogs:
            if catalog not in GROUP_CATALOGS and catalog != default_catalog:
                device_manifest.catalogs.remove(catalog)
                catalogs_to_remove.append(catalog)

        for group in groups:
            if group["catalog"] is None:
                continue
            if group["catalog"] in multiple_result:
                # get group names
                group_names = [
                    item["name"] for item in multiple_result[group["catalog"]]
                ]
                if group["name"] not in group_names:
                    device_manifest.catalogs.remove(group["catalog"])
                    catalogs_to_remove.append(group["catalog"])
            elif (
                group["name"] not in device_manifest.included_manifests
                and group["catalog"] in device_manifest.catalogs
            ):
                device_manifest.catalogs.remove(group["catalog"])
                catalogs_to_remove.append(group["catalog"])

        catalogs_to_remove = list(set(catalogs_to_remove))

        return catalogs_to_remove
