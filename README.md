# BubbaGrump

The name comes from the pun on Bubba Gump, and the fact that this was a pain in the ass project for a few reasons:

- There's a few that exist, but their both stale, and they both have so many forks that there's no clear indication of who is maintaining the best one.
- This was an ugly mix of first-order-logic, recursion, and a bunch of other methods.

Now onto the good stuff.

## CAUTION (TLDR: Only run this under the Audit )

This tool uses automation and inference combined with a **hand built blacklist** to call a _wide selection of methods_ in your AWS account.

I strongly recommend you only use this under the `arn:aws:iam::aws:policy/ReadOnlyAccess` pre-built policy document, with the caveats that that it does not support some services (as of 2018-09-24, it does not support AWS Certificate Manager Private Certificate Authority, for example).

## 