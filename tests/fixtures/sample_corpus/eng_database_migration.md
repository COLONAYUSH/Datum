# Zero-Downtime Database Migration Guide

Schema changes that add a new nullable column can be applied directly with a single ALTER TABLE statement, but backfilling that column for existing rows is never done in one pass. The backfill runs in batches of 5,000 rows, sleeping 200 milliseconds between batches, so the migration does not hold a long-running lock or saturate replication lag on the primary.

Renaming or dropping a column follows the expand-contract pattern: first add the new column and dual-write to both the old and new column from the application, then backfill history, then flip reads to the new column, and only drop the old column in a separate deploy at least one full release cycle later. This guide's target migration window is under 500 milliseconds of added p99 write latency during the backfill, measured continuously, with the batch job pausing automatically if that budget is exceeded.
