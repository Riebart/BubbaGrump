#!/usr/bin/env python3

import os
import json
import sys

from aws_service_model.service import AWSService
from aws_service_model.domain import Domain
from aws_service_model.exceptions import InsufficientMembersException
from aws_service_model.util import json_repr_dump


def read_only_op_filter(op):
    """
    Filter operations to only those that start with List, Describe, or Get
    """
    if op.name().startswith("List") or op.name().startswith(
            "Describe") or op.name().startswith("Get"):
        return True
    else:
        return False


if __name__ == "__main__":
    service_name = sys.argv[1]
    botocore_directory = None if len(sys.argv) < 3 else sys.argv[2]

    # Create the service abstraction
    service = AWSService(
        service_name=service_name, botocore_directory=botocore_directory)

    operations = service.get_operations()

    # Look for all read-only operations
    read_only_operations = [op for op in operations if read_only_op_filter(op)]

    # Look for any operations where the requirements list is empty
    starter_ops = [op for op in read_only_operations if op.input().requirements() == dict()]

    # Define the domain of known entities, initialized to empty.
    𝕌 = Domain()
    region_domain = 𝕌.dimension(service.region())
    𝔻 = region_domain.dimension(service.name())

    # For each starter operation, these are handled separately, since it's a little more efficient especially for large numbers of operations.
    for op in starter_ops:
        # Call the operation over all constructed inputs
        input_shape = op.input()
        print(op, input_shape, file=sys.stderr)
        success = False
        for params in input_shape.construct(𝔻):
            print(op, input_shape, params, file=sys.stderr)
            resp = op.call(params)
            # Pass the response and the universe to the output shape to populate the universe with entities we can derive from this response.
            if resp is not None:
                op.output().populate(resp, 𝔻)
                success = True
        
        # Remove the starter ops that succeeded from the ops we'll try later.
        if success:
            read_only_operations.remove(op)

    # Now, for every other operation, try to construct enough to satisfy the requirements for each.
    while read_only_operations != []:
        successes = set()
        for rop in read_only_operations:
            try:
                input_shape = rop.input()
                population = input_shape.construct(𝔻)
                # If successful, do the same thing: call, populate entities.
                for params in population:
                    print(rop, input_shape, params, file=sys.stderr)
                    resp = rop.call(params)
                    if resp is not None:
                        rop.output().populate(resp, 𝔻)
                        # If we successfully did something with this, then count that as a success.
                        successes.add(rop)
            except InsufficientMembersException as e:
                print(e, file=sys.stderr)
        
        # For any operation that succeeded, remove it from the list and try the rest again.
        for op in successes:
            read_only_operations.remove(op)
        
        # If nothing succeeded this round, then nothing will succeed next round either, so quit.
        if successes == set():
            break
    
    # print(𝕌)
