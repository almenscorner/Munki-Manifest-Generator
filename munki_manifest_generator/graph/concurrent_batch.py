import json
import concurrent.futures
import uuid
import time
import urllib.parse
import logging
import threading

from munki_manifest_generator.graph.make_api_request import make_api_request_Post
from munki_manifest_generator.logger import logger


batches = []


def get_data(ids: list, url: str, extra_url: str, batch_type: str, token: dict, method: str) -> dict:
    """Create a batch request to the Graph API"""

    # Remove empty strings and the default GUID from the list of ids
    unique_ids = set(ids) - {"00000000-0000-0000-0000-000000000000"} - {""}
    # Create a list of dictionaries with the id, method and url of the request
    if batch_type == "deviceId":
        requests = [{"id": i, "method": method, "url": f"{url}?$filter=deviceId eq '{i}'"} for i in unique_ids]
    elif batch_type == "upn":
        requests = [
            {
                "id": f"{i}_{int(time.time() * 1000)}",
                "method": method,
                "url": f"{url}?$filter=userPrincipalName eq '{urllib.parse.quote(i)}'",
            }
            for i in unique_ids
            if i
        ]
    elif batch_type == "user" or batch_type == "device":
        requests = [
            {
                "id": i,
                "method": method,
                "url": url + i + extra_url,
                "headers": {"ConsistencyLevel": "eventual"},
            }
            for i in unique_ids
        ]
    # If no batch type is specified, the ids are already in the correct format
    else:
        requests = [{"id": i, "method": method, "url": url + i + extra_url} for i in unique_ids]

    # Create a dictionary with the key "requests" and the value being the list of dictionaries
    batches.append(requests)
    json_data = json.dumps({"requests": requests})
    # Make the request to the Graph API
    return make_api_request_Post("https://graph.microsoft.com/beta/$batch", token, jdata=json_data)


def batch_request(
    data: list,
    url: str,
    extra_url: str,
    batch_type: str,
    token: dict,
    method="GET",
    retry_pool=None,
) -> list:
    """Create concurrent batch requests to the Graph API"""

    # If the type is "device" or "user", get the ids from the data
    get_ids = False
    if batch_type != "device" and batch_type != "user":
        pass
    else:
        get_ids = True

    if get_ids:
        ids = [
            val.get("id")  # Append the value associated with the "id" key to the ids list
            for l in data  # For each dictionary in the list of dictionaries
            for val in l["value"]  # For each dictionary in the "value" list of that dictionary
            if "id" in val.keys() and val.get("id") is not None  # If the dictionary contains a key "id"
        ]  # And if the value associated with the "id" key is not None

    # If the type is not "device" or "user", the ids are already in the correct format
    else:
        ids = data

    # Set the object type
    if batch_type == "device":
        object_type = "deviceId"
    elif batch_type == "user":
        object_type = "userPrincipalName"

    # Create a dictionary with the ids as keys and the object type as values
    if get_ids:
        id_to_object = {}
        for d in data:
            for val in d.get("value", []):
                if "id" in val and val["id"] is not None:
                    id_to_object[val["id"]] = val.get(object_type, "")

    responses = []
    retry_pool = []
    wait_time = 0
    batch_count = 20
    batch_list = [ids[i : i + batch_count] for i in range(0, len(ids), batch_count)]
    batch_id = 0

    def get_response_body(response) -> None:
        """Get the response body from the batch request"""

        # Make the retry_pool variable
        nonlocal retry_pool
        # Make the wait_time variable
        nonlocal wait_time

        for r in response:
            wait_time = 0  # Reset the wait time

            if r["body"].get("value") is not None:
                for val in r["body"]["value"]:
                    if val.get("accountEnabled") is False:
                        logger.info(f"Skipping disabled account: {val.get('userPrincipalName')}")
                        continue

            # if the status code is 200, append the response body to the responses list
            if r["status"] == 200:
                if get_ids:
                    r["body"][object_type] = id_to_object.get(r["id"], "")

                responses.append(r["body"])
            # if the status code is 429, append the id to the retry pool
            elif r["status"] == 429 or r["status"] == 503:
                if get_ids:
                    # Append the id and the object type to the retry pool
                    batch = {"value": [{"id": r["id"], object_type: id_to_object.get(r["id"], "")}]}
                    if retry_pool is not None:
                        retry_pool.append(batch)
                else:
                    # Append the id to the retry pool
                    batch = {"value": [{"id": r["id"]}]}
                    if retry_pool is not None:
                        retry_pool.append(batch)
                # Get the wait time from the response headers
                wait_time = int(r["headers"].get("Retry-After", 0))
            # Else, log the error
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    failed_batch_request = next(
                        (i for i in batches for j in i if any(v == r["id"] for k, v in j.items())),
                        None,
                    )

                    if failed_batch_request:
                        logger.debug("Failed batch request: %s" % failed_batch_request)
                logger.error(f'Request failed with status code {r["status"]} for {r["id"]}')

    # Create a thread pool and submit the requests
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_id = {
            executor.submit(get_data, batch, url, extra_url, batch_type, token, method): batch_id for batch in batch_list
        }
        # Get the responses from the requests
        for future in concurrent.futures.as_completed(future_to_id):
            # batch_id = future_to_id[future]
            try:
                response = future.result()["responses"]
                get_response_body(response)

            except Exception as exc:
                logger.warning(f"Exception {exc} for batch {batch_id} from thread {threading.current_thread().name}")

            batch_id += 1

    # If the retry pool is not empty, make another batch request
    if retry_pool is not None and retry_pool:  # check if the "value" key of retry_pool is not empty
        retry_batch = retry_pool
        if wait_time > 0:
            logger.info(f"Waiting {wait_time} seconds before retrying batch request")
            time.sleep(wait_time)
        responses += batch_request(
            retry_batch,
            url,
            extra_url,
            batch_type,
            token,
            method,
            retry_pool=retry_pool,
        )

    return responses
