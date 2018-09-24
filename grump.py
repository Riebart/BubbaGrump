#!/usr/bin/env python3

import os
import json
import sys

from aws_service_model.service import AWSService
from aws_service_model.universe import Universe
from aws_service_model.exceptions import InsufficientMembersException

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

    # Define the universe of known entities, initialized to empty.
    𝕌 = Universe()

    # For each starter operation, these are handled separately, since it's a little more efficient especially for large numbers of operations.
    for op in starter_ops:
        # Call the operation over all constructed inputs
        for params in op.input().construct(𝕌):
            resp = op.call(params)
            # Pass the response and the universe to the output shape to populate the universe with entities we can derive from this response.
            op.output().populate(resp, 𝕌)
        
        # Remove the starter ops from the ops we'll try later.
        read_only_operations.remove(op)

    # Now, for every other operation, try to construct enough to satisfy the requirements for each.
    while read_only_operations != []:
        successes = []
        for rop in read_only_operations:
            try:
                population = rop.input().construct(𝕌)
                # If successful, do the same thing: call, populate entities.
                for params in population:
                    resp = rop.call(params)
                    rop.output().populate(resp, 𝕌)
                successes.append(rop)
            except InsufficientMembersException as e:
                print(e, file=sys.stderr)
        for op in successes:
            read_only_operations.remove(op)
        if successes == []:
            break
    
    print(𝕌)
