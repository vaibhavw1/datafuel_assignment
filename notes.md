# Design Notes

## 1. Store Selection

I fetch the store list from the portal and keep only stores marked as active for inventory sweeps. Inactive stores are skipped because they should not contribute to the regular availability report. I also keep the store information in the database so the API can use it later.

I paginate through inventory responses instead of assuming that the first page contains all the products. If a request fails or the portal returns a partial or edge response, I avoid treating that response as a successful sweep. The sweep is marked incomplete with a reason so it can be checked or retried later.

I use the store ID and timestamp to identify a sweep. This also helps avoid creating duplicate records when the same timestamp is run again.

## 2. If Delhi OSA Drops from 92% to 41%

I would first check whether the drop is real or caused by missing or incomplete data. I would compare the latest sweep with the previous successful sweep and check the number of stores and SKUs covered, incomplete sweeps, API errors, and any changes in active stores.

If the data looks complete, I would look at the affected stores and products to see whether the drop is concentrated in a few locations or spread across the city. I would also compare stock quantities and recent inventory changes before concluding that availability has actually fallen.

## 3. City Sales Total Does Not Match Store Totals

If the dashboard reports ₹4.20 lakh while adding the individual stores gives ₹4.61 lakh, I would not immediately choose either number. I would first check whether both figures use the same date range, filters, and sales definition. I would also look for duplicate records, delayed updates, and differences in how returns or cancelled orders are handled.

Until the mismatch is explained, I would show the verified figure with a note that the totals are being reconciled rather than presenting an unverified number as final.

## 4. Where I Would Not Use AI

I would not use an LLM for basic calculations such as OSA percentages, inventory counts, pagination, or deciding whether a response is complete. These tasks have clear rules and are easier to test with normal Python code.

I would also avoid using an LLM to invent missing inventory values or decide that a missing product is out of stock. Missing data should be reported as missing, not guessed. AI could be useful later for summarising unusual trends, but the underlying calculations should remain deterministic.

## 5. Scaling to 20,000 Stores

If the system had to handle 20,000 stores every 30 minutes, I would move from a single sequential script to a scheduled job that puts store sweeps into a queue. Workers could process stores in parallel, with limits to avoid overwhelming the portal.

I would add monitoring for failed and incomplete sweeps, retry transient errors with backoff, and make every write safe to repeat. I would also review database indexing, retention, and query performance as the amount of inventory history grows. The system should track coverage and freshness so a report does not silently treat missing data as zero stock.