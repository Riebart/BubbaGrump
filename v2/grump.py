#!/usr/bin/env python3

import botocore.session
import re

import kanren
from kanren import Relation, facts, var, conde, run

provides = Relation("provides")
requires = Relation("requires")


def satisfies(source, sink):
    pass


api_model = dict()
session = botocore.session.get_session()
for service_name in session.get_available_services():
    api_version = session.get_config_variable("api_versions").get(
        service_name, [None])[-1]
    regions = session.get_available_regions(service_name)
    api_model[service_name] = dict(regions=regions, operations=dict())
    for region in regions:
        service_model = session.get_service_model(service_name,
                                                  api_version=api_version)
        for op_name in [
                op for op in list(service_model.operation_names)
                if re.match(r"^(Get|List|Describe)", op)
        ]:
            op_model = service_model.operation_model(op_name)
            api_model[service_name]["operations"][op_name] = dict(
                model=op_model)
