# BubbaGrump: AWS API Modeling Wrapper

## Implementation

The AWS API is modeled as JSON files included in all official SDKs (e.g. botocore, aws-sdk-cpp), however these models do not fully define the API, as the inputs and outputs are underspecified, necessitating an unreasonable (and for larger accounts, rapidly intracticable) number of calls that will fail.

The module ingests these JSON API models, and attempts to apply heuristics and hand-crafted rules to transform them into a well-defined dependency and satisfaction graph that permits reasoning and execution planning.

One such use case of this module is for AWS resource enumeration and reasoning about related and associated resources. For example, after enumerating all resources, one could ask a question of the resulting graph such as "Show me all resources that are exposed in this VPC subnet, and all EC2 instances resources that can access them.

## Approach

- Use the JSON models to determine the inputs each operation requires, and that each operation provides. Trace this ancestry through to the leaf types (e.g. String, Integer, Boolean) through any intermediary types (e.g. List, Map) and Structures.
  - This information is stored as a directed graph where A->B means A comes before B in any traversal.
  - With each entity stored in the universe, also store the genealogy (i.e. which Operation it came from). This is required to efficiently brute-force identifying which outputs can satisfy which inputs for an API call when the outputs and inputs are under-typed by the JSON models. For example: Two operations, OpA and OpB, may both return a `name`, and OpC may require a `name` argument, but it is not clear which of OpA and OpB can satisfy OpC. By testing one of OpA's outputs, an observation that it fails allows us to preclude any other OpA output for OpC's input based on the genealogy of those entities.
- At each step, canonicalize the names (see [Gotchas](#Gotchas)), applying the canonicalization transformation to all other known facts, inserting new facts in between any fact that references a canonicalizable noun and the parent/descendent facts.
- When building an execution plan, first consider any operations that do not require an input (only considering _required_ input shape members). This will prime the entities in the universe.
  - As entities are produced, store them as manifest within the universe at all levels. For example, if OpA produces an output shape, which in turn is made up of two structures, each with 3 strings, then the output of OpA will produce `1+2+(3+3)=9` manifest entities that are linked by genealogy.
- Iteratively determine which operations have their requirements satisfied by the entities within the universe, only traversing down as low as necessary in the genealogical tree.
  - As operations are satisfied with inputs, mark those input sets as complete so that they are not tried again, and link those input sets to the appropriate output.

## Gotchas

- Shape and structure names vary significantly, and are without any predictable semantic form. In an attempt to canonicalize them, the following transformations are applied:
  - `s/^(Get|List|Describe)(.*)(Request|Response)/$1/` (i.e. any `Get`, `List`, and `Descibe` prefix is stripped, and any `Request` or `Response` suffixes are stripped)
- Shape and structure naming consistency is nonexistent. `Stage`, `StageName`, and `ApiStage` are used interchangeably in the API Gateway model, and there would be no way to programmatically determine that these are the same species, and can be used to fulfill expectations of each other.
- IDs are usually insuffiently mapped, with inputs requiring a mix of `--id` and more specific ID names (e.g. `--rest-api-id`), and responses returning the same mix.
  - As a heuristic, whenever there is a shape or structure member that is the base `id`, wrap it in a virtual type that is `${ParentShapeName}Id`, and also take note to wrap any other members that match `${ParentShapeName}` in the same virtual Id type.
  - Other "blessed" member classes: `ID`, `NAME`, `TYPE`, `ARN`
