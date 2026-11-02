# Operations and release procedure

Owner: JSON Jargon. Sparky coordinates; Sherman supports discovery measurement; Flinn supports automation.

## Release gate

Do not merge or enable production merely because tests pass. Commander must approve the exact
reviewed commit, Pages migration and the separate narrowly scoped Shopify theme patch.
Existing product launches and all commerce/channel settings are outside this change.

After approval:
1. Preserve the pre-release main commit and current Pages publishing configuration.
2. Merge the reviewed change, change Pages publishing source to GitHub Actions, and set repository
   variable DISCOVERY_DEPLOY_ENABLED=true. Use the github-pages environment with main-only deployment.
3. Dispatch publish.yml on main with bootstrap=true for the first health.json only.
4. Confirm source counts, all expected public bytes and actual Pages deployment success.
5. Re-fetch the current live theme. Apply only shopify/theme-discovery.patch if its base still matches;
   otherwise reconcile the patch. Preserve a full source backup and verify the installed diff.
6. Check homepage, a product, FAQ and Dad-a-Pedia page: no press/review links, all advertised URLs200,
   JSON parses, and no dateModified generated merely from today's date.
7. Test a controlled public-source update through the whole live cycle when an actual approved
   source update is available. Synthetic change/removal tests establish generator behavior only.
8. Record deployed commit, workflow run, observed counts, byte verification and theme readback
   in canonical Open Hub. Mark operational only after live verification.

## Refresh and failures

The proposed schedule rebuilds every two hours at minute17 UTC, independent of Eastern DST.
GitHub may delay scheduled jobs; this is a target cadence, not a publication deadline guarantee.
A separate check at minute47 every two hours fails on stale feeds (over8hours), bad JSON or failed endpoints.
It checks oldest source capture as well as build time. A drop of more than25percent in a core source count
blocks deployment for review. HTTP/parsing/coverage failure prevents upload/deployment and retains the last
successful site. A post-deploy mismatch fails visibly but does not automatically undo a deployed artifact;
investigate propagation or use the preserved rollback artifact.

Failures appear in Actions. Repository notification/watch settings must be verified for the accountable
owner before calling alerts operational; no email or external messages are sent by this implementation.
GitHub can disable public-repository scheduled workflows after60days of repository inactivity.
Use an independently scheduled monitor to check public health and workflow enabled state after release;
that monitor should remain quiet for unchanged healthy state and notify only on meaningful failure,
recovery or required user action.

## Rollback

Disable DISCOVERY_DEPLOY_ENABLED and stop/cancel active publishing runs. Redeploy the preserved last-good
Pages artifact (retained30days) or restore the recorded pre-release branch publishing configuration and
its exact commit. Revert the theme patch using the full verified backup after checking for intervening edits.
Do not regenerate from today's sources as a substitute for restoring an exact previous artifact.
Validate restored endpoints and record the recovery. No product status changes are required.

## Measurement

Feed health is separate from search performance. After release, identify the existing TDT Search Console
property and authorized account, inspect representative URLs and sitemap status, and establish a dated
baseline. Never use EDUHaHa property statistics as TDT evidence. No Search Console access or AI citations
are claimed by this build. Record periodic reproducible AI discovery prompts, date/platform, observed
mentions/citations and exact links without treating one result as universal visibility.

## Mandatory collection gate

Before deployment, verify every included collection has at least one current public catalog product. Empty and draft-only collections are excluded automatically on each rebuild. Do not publish or activate a collection to satisfy feed coverage. Existing published empty Shopify collections require a separate explicit decision before unpublishing.

Public source requests are paced to at most one start per second across workers. HTTP429 honors Retry-After up to60seconds (default30seconds); longer requested delays stop the build for later retry. Access challenges/403 do not trigger repeated challenge requests. Validation runs on pull requests only, avoiding duplicate push/PR source crawls.
