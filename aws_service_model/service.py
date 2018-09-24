import os
import json

import boto3

from .shapes import (Operation, Blob, Boolean, Double, Float, Integer, List,
                     Long, Map, String, Structure, Timestamp)
from .exceptions import UnknownServiceException
from .util import All, Filter
"""
A list of values that, for whatever reason, are invalid despite existing in the service model.
"""
BLACKLIST = {
    "acm": {
        "Includes": {
            "extendedKeyUsage":
            Filter([lambda val: [v for v in val if v not in ["CUSTOM"]]])
        }
    }
}


class AWSService(object):
    # Built programmatically:
    # find botocore/botocore/data/ -type f | grep service[^/]*json | xargs cat | jq -r '.shapes | to_entries | map(.value.type)[]' 2>/dev/null | sort | uniq | while read type; do echo "\"$type\": `echo $type | sed 's/^./\u&/'`,"; done
    SHAPE_TYPE_MAP = {
        "blob": Blob,
        "boolean": Boolean,
        "double": Double,
        "float": Float,
        "integer": Integer,
        "list": List,
        "long": Long,
        "map": Map,
        "string": String,
        "structure": Structure,
        "timestamp": Timestamp
    }

    def __init__(self,
                 service_name,
                 version=None,
                 botocore_directory=os.path.join(os.getcwd(), "botocore")):
        """
        Load the service and paginator data for a given service name. If no version is provided, the latest is used. If a provided service/version pair does not exist, exceptions are raised.

        This depends on having a local clone of botocore, which is assumed to be in `pwd`/botocore, or rooted at the location provided.
        """
        if service_name not in boto3.Session().get_available_services():
            raise UnknownServiceException(service_name)
        else:
            self.client = boto3.client(service_name)

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
            with open(os.path.join(version_dir, "paginators-1.json"),
                      "r") as fp:
                paginators = json.loads(fp.read())
        except:
            paginators = None

        self.service = service
        self.paginators = paginators

    def get_method_name(self, operation_name):
        for method, name in self.client.meta.method_to_api_mapping.items():
            if name == operation_name:
                return method
        return None

    def get_method(self, operation_name):
        return getattr(self.client, self.get_method_name(operation_name))

    def get_paginator(self, operation_name):
        return self.client.get_paginator(self.get_method_name(operation_name))

    def endpoint_prefix(self):
        return self.service["metadata"]["endpointPrefix"]

    def abbreviation(self):
        return self.service["metadata"]["serviceAbbreviation"]

    def name(self):
        return self.service["metadata"]["serviceFullName"]

    def get_shape(self, shape_name):
        raw_shape = self.raw_get_shape(shape_name)
        return self.SHAPE_TYPE_MAP.get(raw_shape["type"])(shape_name, self)

    def raw_get_shape(self, shape_name):
        return self.service["shapes"][shape_name]

    def get_operations(self, op_filter=lambda op: True):
        """
        Return all operations that are part of this service, filtered by the provided filter function.
        """
        return [
            Operation(op, self)
            for _, op in self.service["operations"].items() if op_filter(op)
        ]

    def blacklist(self, kwargs):
        bl = BLACKLIST.get(self.endpoint_prefix(), dict())
        # For each blacklist rule/pattern
        for k, v in bl.items():
            if isinstance(v, Filter):
                kwargs[k] = v.apply(kwargs[k])
            elif k in kwargs:
                kwargs[k] = self.__rblacklist(v, kwargs[k])
        return kwargs

    def __rblacklist(self, bl, kw):
        if isinstance(bl, Filter):
            kw = bl.apply(kw)
        else:
            for k, v in bl.items():
                if k in kw:
                    kw[k] = self.__rblacklist(v, kw[k])

        return kw
