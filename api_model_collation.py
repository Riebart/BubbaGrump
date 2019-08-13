#!/usr/bin/env python3

#%%
import re
import json
import os, os.path, sys


#%%
def _get_package_paths(module_name,
                       module_filename="__init__.py",
                       version_variable="__version__"):
    module_paths = list()
    # For every path in the system path list
    for path in sys.path:
        try:
            # Try to stitch the package name to the path, and determine the version if it works.
            module_dir = os.path.join(path, module_name)
            os.stat(module_dir)
            with open(os.path.join(module_dir, module_filename), "r") as fp:
                # OPTDO: Convert this to actually interpreting the Python file, not just using regex
                lines = fp.readlines()
                version = sorted(
                    [l for l in lines if l.startswith(version_variable)])[0]
                version = tuple(
                    int(v) for v in version.strip().split(" ")[2].strip()
                    [1:-2].split("."))
            module_paths.append((version, module_dir))
        except:
            pass
    module_paths.sort(key=lambda i: i[1])
    return module_paths


#%%
def __merge_dicts(new, dst):
    for k, v in new.items():
        if isinstance(v, dict):
            if k not in dst:
                dst[k] = dict()
            __merge_dicts(v, dst[k])
        else:
            if isinstance(v, list):
                dst[k] += v
            else:
                dst[k] = v


#%%
def collate_api_models():
    """
    Load API models from Botocore directory
    Merge the API models into a structure that maps service names to versions to the
    service model, the paginator model, and anything else. Also handle the sdk-extra service model
    extensions.
    """
    api_model = dict()
    api_model["services"] = dict()
    service_models = api_model["services"]

    # Get the most path to the most recent botocore in the available Python package paths and use it
    # to construct the data directory (where the JSON models are kept)
    most_recent_path = _get_package_paths("botocore")[-1][1]
    botocore_data_dir = os.path.join(most_recent_path, "data")

    # For each service in the JSON model list (represented by folders in the data director)
    for service_name in os.listdir(botocore_data_dir):
        _parse_service_model(botocore_data_dir, service_name, service_models,
                             api_model)

    return api_model


def _parse_service_model(botocore_data_dir, service_name, service_models,
                         api_model):
    service_dir = os.path.join(botocore_data_dir, service_name)
    # If it is a directory, treat it as a service model
    if os.path.isdir(service_dir):
        service_models[service_name] = dict()
        api_versions = os.listdir(service_dir)
        # A service can have multiple versions, so handle them all.
        for api_version in api_versions:
            _parse_api_version(service_models, service_name, api_version,
                               service_dir)
        latest_version = sorted(api_versions)[-1]
        service_models[service_name]["latest"] = service_models[service_name][
            latest_version]
    else:
        # If it isn't a directory, just add it to the key next to "services" in the model, with a
        # key equal to the filename.
        print(service_dir, "is not a directory", file=sys.stderr)
        with open(service_dir, "r", encoding="utf-8") as fp:
            body = json.loads(fp.read())
        api_model[service_name] = body


def _parse_api_version(service_models, service_name, api_version, service_dir):
    service_models[service_name][api_version] = dict()
    api_version_dir = os.path.join(service_dir, api_version)
    # Sort the facets by the number of dot-separated parts, which will put the subfacets last
    facets = sorted(os.listdir(api_version_dir),
                    key=lambda fname: len(fname.split(".")))
    for facet_full in facets:
        _parse_api_facet(facet_full, api_version_dir, service_models,
                         service_name, api_version)


def _parse_api_facet(facet_full, api_version_dir, service_models, service_name,
                     api_version):
    # 2019-08-06 There are 4 known facet types and one known sub-facet.
    # - examples
    # - paginators
    # - waiters
    # - service
    #   > service.sdk-extras
    facet = facet_full.split("-", 1)[0]
    try:
        subfacet = re.match(r"[a-z]+-[0-9]+\.(.*)\.json", facet_full).group(1)
    except:
        subfacet = None
    with open(os.path.join(api_version_dir, facet_full), "r",
              encoding="utf-8") as fp:
        body = json.loads(fp.read())
    if subfacet:
        # The only known action of a subfacet is 'merge', which indicates that there is data that should have
        # been in the model facet, but the facet could not have been directly introduced for some reason.
        if "merge" in body:
            __merge_dicts(body["merge"],
                          service_models[service_name][api_version][facet])
            print("Merged in %s to %s for %s/%s" %
                  (subfacet, facet, service_name, api_version),
                  file=sys.stderr)
        else:
            pass
    else:
        service_models[service_name][api_version][facet] = body
