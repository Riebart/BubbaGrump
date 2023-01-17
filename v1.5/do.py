#!/usr/bin/env python3

# Step 1: Get all List* and Describe* operations
# Step 2: Load all shapes

# For each operation:
# - Look in the paginators file to see if there is a defined paginator. if so, use pagniation when calling this to ensure we get all entries.
# - Look at the inputs, and determine any root types they depend on and are required.
# - Ignore non-required parameters.

import os
import json

SERVICE_NAME = "acm"
VERSION = None


def load_service_data(service_name,
                      version=None,
                      botocore_directory=os.path.join(os.getcwd(),
                                                      "botocore")):
    """
    Load the service and paginator data for a given service name. If no version is provided, the latest is used. If a provided service/version pair does not exist, exceptions are raised.

    This depends on having a local clone of botocore, which is assumed to be in `pwd`/botocore, or rooted at the location provided.
    """
    service_dir = os.path.join(botocore_directory, "botocore", "data",
                               service_name)

    versions = sorted(os.listdir(service_dir))
    if version is None:
        version = versions[-1]
    elif version not in version:
        raise ValueError("Provided version not in ")

    version_dir = os.path.join(service_dir, version)
    with open(os.path.join(version_dir, "service-2.json"), "r") as fp:
        service = json.loads(fp.read())

    try:
        with open(os.path.join(version_dir, "paginators-1.json"), "r") as fp:
            paginators = json.loads(fp.read())
    except:
        paginators = None

    return (service, paginators)


if __name__ == "__main__":
    service, paginators = load_service_data("acm")

    operations = service["operations"]
    shapes = service["shapes"]

    edges = list()

    for _, op in operations.items():
        pass
