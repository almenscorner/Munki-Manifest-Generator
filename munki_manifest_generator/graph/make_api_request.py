#!/usr/bin/env python3

"""
This module is used to make API requests to the Graph API.
"""

import requests
import json

from retrying import retry


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
        raise Exception("Request failed with ", response.status_code, " - ", response.text)


@retry(
    wait_exponential_multiplier=1000,
    wait_exponential_max=10000,
    stop_max_attempt_number=5,
)
def make_api_request_Post(endpoint, token, q_param=None, jdata=None, status_code=200):
    """
    This function makes a POST request to the Microsoft Graph API.

    :param patchEndpoint: The endpoint to make the request to.
    :param token: The token to use for authenticating the request.
    :param q_param: The query parameters to use for the request.
    :param jdata: The JSON data to use for the request.
    :param status_code: The status code to expect from the request.
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {0}".format(token["access_token"]),
    }

    if q_param is not None:
        response = requests.post(endpoint, headers=headers, params=q_param, data=jdata)
    else:
        response = requests.post(endpoint, headers=headers, data=jdata)
    if response.status_code == status_code:
        if response.text:
            json_data = json.loads(response.text)
            return json_data
        else:
            pass

    else:
        raise Exception("Request failed with ", response.status_code, " - ", response.text)
