#!/usr/bin/env python3

import json
from aws_api_model import AWSAPIModel
from util import json_str_dumps

service_names = ["acm", "apigateway"]
regions = ["ca-central-1", "us-east-1"]


def main():
    # First, ask for the global API model without specifying that it should be restricted to a region or a service.
    # This will trigger a parsing of the shapes and operations for each service.
    api_model = AWSAPIModel(service_names=service_names, regions=regions)

    # print(json_str_dumps(api_model.api_model))
    for service_name in service_names:
        api_model.build_execution_plan(
            service_name, lambda op_name: op_name.startswith("Get") or op_name.
            startswith("List") or op_name.startswith("Describe"))


if __name__ == "__main__":
    main()
