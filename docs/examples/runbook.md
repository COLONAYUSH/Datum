# Deploy Runbook

Deploy the service by running the deploy script against the production cluster.
Confirm the health check is green before moving traffic.

## Rollback

To revert the release, pin the previous image tag and redeploy the production cluster.
Traffic shifts back automatically once the older revision reports healthy.

## Incident response

Page the on-call engineer if the error rate stays above five percent for ten minutes.
Open an incident channel and record every action with a timestamp.
