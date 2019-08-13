#!/usr/bin/env python3

import json
import botocore.session

from util import Any
from shapes import ShapeDomain, Lineage
from collections import namedtuple


class AWSAPIModel(object):
    def __init__(self, regions: list = [Any()], service_names: list = [Any()]):
        # Create a shape domain in which all shapes will be created. This handles identifying when two boto shapes are isomorphic, and implicitly takes care of merging them all together.
        self.𝕌 = dict()

        # Use the available botocore to provide the API model.
        self.session = botocore.session.get_session()

        # Select only the service names that are contained in the provided list.
        self.service_names = [
            name for name in self.session.get_available_services()
            if name in service_names
        ]

        # For each service, get the list of regions for that service, as not all services are available in all regions.
        self.service_regions = {
            service_name: [
                r
                for r in botocore.session.get_session().get_available_regions(
                    service_name) if r in regions
            ]
            for service_name in service_names
        }

        # Initialize the API model and universe of shape domains
        self.api_model = dict()
        self.𝕌 = dict()

        # For each service name, limited to the list provided...
        for service_name, regions in self.service_regions.items():
            self.api_model[service_name] = self.assemble_service(
                service_name, regions)

    def assemble_service(self, service_name, regions):
        # List all API versions, and only take the most recent one
        latest_api_version = sorted(
            self.session.get_config_variable("api_versions").get(
                service_name, [None]))[-1]

        # Get the service model for that region.
        service_model = self.session.get_service_model(
            service_name, api_version=latest_api_version)

        # Create a ShapeDomain for this service, which will create a separate namespace for the shapes and entities for this service disjoint from other services
        self.𝕌[service_name], shapes = self.assemble_shapes(service_model)

        operations = self.assemble_operations(service_model, regions)

        # The API model for a service is the regions it is in (limited to the acceptable regions provided), the operations, and the shapes.
        return dict(regions=regions, operations=operations, shapes=shapes)

    def assemble_operations(self, service_model, regions):
        operations = dict()
        for op_name in list(service_model.operation_names):
            op_model = service_model.operation_model(op_name)
            operations[op_name] = dict(model=op_model, func=dict())
            for region in regions:
                client = self.session.create_client(service_model.service_name,
                                                    region_name=region)
                method_name = [
                    method for method, name in
                    client.meta.method_to_api_mapping.items()
                    if name == op_name
                ][0]
                operations[op_name]["func"][region] = getattr(
                    client, method_name)

        return operations

    def assemble_shapes(self, service_model):
        𝔻 = ShapeDomain(
            Lineage(("service_name", service_model.service_name),
                    ("aspect", "shapes")))
        # For each shape, get the shape model, and then build a shape object around the botocore shape object.
        # The reason for building FROM the boto shape, and not using it directly, is that botocore does not differentiate between types of shapes other than Strings. All other shapes are just a Shape with a 'type' metadata value, which precludes reasoning around constraints (enum, min, max, pattern).

        return 𝔻, {
            shape_name: 𝔻[service_model.shape_for(shape_name)]
            for shape_name in list(service_model.shape_names)
        }

    def services(self):
        """
        Return the list of service names that this model covers.
        """
        return list(self.api_model.keys())

    def __construct_shape(self, shape_name, include_leaf_shapes=False):
        """
        Given a shape name, attempt to recursively go through every option for constructing it.
        """
        # The construction
        pass

    def build_execution_plan(self, service_name: str, op_filter: callable):
        """
        Build an execution plan by examining the operation and shape models, and build an order of operations
        """
        service_model = self.api_model[service_name]

        for region in service_model["regions"]:
            # For each operation, test the domain of entities for whether we can construct the inputshape of the operation.
            ops_remaining = set([
                o for o in list(self.api_model[service_name]
                                ["operations"].keys()) if op_filter(o)
            ])
            while ops_remaining != set():
                ops_succeeded = set()
                for op_name in ops_remaining:
                    op = self.api_model[service_name]["operations"][op_name]
                    # print(service_name, region, op_name)
                    in_shape = self.𝕌[service_name][op["model"].input_shape]
                    out_shape = self.𝕌[service_name][op["model"].output_shape]

                    for params in in_shape.reap(include_empty=True,
                                                lineage_filter=lambda l, r=
                                                region: l["region"] == r):
                        print(service_name, region, op_name, params)
                        try:
                            response = op["func"][region](**params)
                            print(response)
                            out_shape.sow(
                                Lineage(("service_name", service_name),
                                        ("region", region),
                                        ("operation_name", op_name),
                                        ("parameters", params),
                                        ("method_response", response)))
                            ops_succeeded.add(op_name)
                        except Exception as e:
                            print("EXCEPTION", service_name, region, op_name,
                                  e, str(e), repr(e), e.__dict__)
                            pass
                if ops_succeeded == set():
                    print("Unable to complete some operations:", service_name,
                          region, ops_remaining)
                    break
                else:
                    print("SUCCEEDED", service_name, region, ops_succeeded)
                    ops_remaining = ops_remaining.difference(ops_succeeded)
                    print("REMAINING", service_name, region, ops_remaining)
