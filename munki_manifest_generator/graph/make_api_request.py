#!/usr/bin/env python3

"""
This module is used to make API requests to the Graph API.
"""

import requests
import json


def make_api_request(endpoint, token, q_param=None):
    """Makes a get request and returns the response."""
    # Create a valid header using the provided access token

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {0}".format(token["access_token"]),
    }

    # This section handles a bug with the Python requests module which
    # encodes blank spaces to plus signs instead of %20.  This will cause
    # issues with OData filters

    if q_param is not None:
        response = requests.get(endpoint, headers=headers, params=q_param)
    else:
        response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        json_data = json.loads(response.text)

        # This section handles paged results and combines the results
        # into a single JSON response.  This may need to be modified
        # if results are too large

        if "@odata.nextLink" in json_data.keys():
            record = make_api_request(json_data["@odata.nextLink"], token)
            entries = len(record["value"])
            count = 0
            while count < entries:
                json_data["value"].append(record["value"][count])
                count += 1
        return json_data

    else:
        raise Exception(
            "Request failed with ", response.status_code, " - ", response.text
        )
