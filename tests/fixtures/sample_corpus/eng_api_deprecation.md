# Public API Deprecation Policy

Any public API endpoint slated for removal is marked deprecated in its response headers and its OpenAPI spec at least one full release ahead of the change taking effect. From the day an endpoint is marked deprecated, callers are given a 180-day deprecation notice period before the endpoint returns a 410 Gone response. During that window, every response from a deprecated endpoint includes a Sunset header naming the exact retirement date, and the developer portal sends an email to every registered API key that has called the endpoint in the previous 30 days.

Breaking changes to a still-supported endpoint (as opposed to a full retirement) are never shipped in place; they are instead released as a new versioned path (for example /v2/), with the old version kept live for the remainder of its own deprecation window rather than mutated underneath existing callers.
