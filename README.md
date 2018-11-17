# BubbaGrump

The name comes from the pun on Bubba Gump, and the fact that this was a _massive pain in the ass project_ for a few reasons:

- There's a few that exist, but they are stale, and they both have so many forks that there's no clear indication of who is maintaining the best one.
- This was an ugly mix of first-order-logic, recursion, and a bunch of other methods.
- The AWS APIs, and the JSON definitions that exist in the official fist-party SDKs are still _wildly inconsistent_, and even the APIs themselves are inconsistent.

Now onto the good stuff.

## CAUTION (TLDR: Only run this under the Audit policy)

This tool uses automation and inference combined with a **hand built blacklist and multiple sets of transformatio heuristics** to call a _wide selection of methods_ in your AWS account.

I strongly recommend you only use this under the `arn:aws:iam::aws:policy/ReadOnlyAccess` pre-built policy document, with the caveats that that it does not support some services (as of 2018-09-24, it does not support AWS Certificate Manager Private Certificate Authority, for example).

## How does this work/what does it do

### The simple answer

This script attempts to use the Python SDK's included service descriptions to infer dependencies between API calls, and an order to call the methods in such that the output of one feeds the inputs of others.

For example: You want to describe all of the EBS volumes attached to all of your EC2 instances. To do this you would need to chain several API calls.

- Describe all of your EC2 instances
- Use each of your EC2 instance IDs to get the attached EBS volumes
- Use the EBS volume IDs to describe the volumes.

This tool aims to do this in an automated fashion, describe _every_ resources it can in _every region_ of your account. (Future feature) It stores every item it finds, and this linked database could then be queried via a graph database of some kind.

This functionality is very useful for security auditing, configuration management, and more.

### The complicated answer

The process is non-trivial, but simple enough.

- Crack open the service definition files included in `botocore`, and get the list of all operations for a given service
- Determine which operations are read-only (identified as those that satisfy `r"^(Get|List|Describe).*"`)
- Determine the starter operations, which are those that take no inputs (usually `List*` operations). There is _always_ at least one of these for a service.
- Create a domain of facts for first order logic inference and reasoning. As we call methods, the resulting objects will be added to this domain of facts.
- Iterate over the starter operations and track their outputs as axioms in the logic domain
- Iterate over the other operations, running ones that now have fulfilled inputs, and manifesting their outputs in the domain of facts. Repeat this until all methods have been run, or no more methods can be run (could occur if you don't use all of the resource types available to a service).

The current implementation is inefficient, but the performance of the logic is not the bottleneck, the API calls are. No effort has been made to thread the operations, which could significantly improve the performance, however the current goal is _correctness_.

## What's the hold-up?

Well, frankly, the AWS API is a _gorram shirtshow_. The methods _could_ be well-defined, and _could_ specify their inputs and outputs in a way that makes this process easy, but the **most certainly do not**.

So the current logic works correctly, however the relationship model is ambiguous and I am slowly building manual type wrappers to provide hints on how they relate.

For example, various API Gateway methods return shapes by the names of `RestApi`, `Authorizer`, and `GetSdkTypeRequest`, all of which have a property named `id`. Other methods, that operate on what those methods are returning, take in a property of `restApiId` or `authorizerId`. It should be obvious how this is a problem, since the outputs of one method give no hints as to how, or why, they would map to the inputs of another method.

A human can figure it out (and indeed, that's exactly what I am doing), and my solution is to provide type wrappers defined at the shape and method levels that wrap these shapes. These wrapper types provide a unified fact hierarchy where the ancestry trees of what we need and what we get meet at a point that isn't a base value type (such as `string`) and we can reason about fulfillment of these method requirements.
