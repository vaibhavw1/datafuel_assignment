# AI Usage Log

## How I Used AI

I used ChatGPT during development to understand the assignment requirements, review parts of the Python code, identify possible edge cases, and improve the documentation. I used the suggestions as guidance and checked the important parts against the existing code and test results.

## Prompts I Used

1. "Review my inventory sweep code and identify problems with pagination, retries, and incomplete API responses."

2. "Help me calculate city-level OSA correctly using inventory observations stored in SQLite."

3. "Review my FastAPI endpoint and suggest test cases for invalid cities, dates, and missing data."

## Cases Where AI Suggestions Needed Checking

### 1. The suggested code was more complicated than necessary

One suggested rewrite was longer and more complicated than the code I wanted to maintain. I reviewed it and kept the implementation simpler, focusing on the requirements that actually mattered for the assignment.

### 2. The code needed to match the existing database structure

A code suggestion is not useful if it assumes different database columns or tables. I checked the queries against my actual SQLite schema and adjusted them to use the existing inventory and sweep structure.

### What I Learned

AI was useful for finding possible issues and speeding up development, but I still needed to understand the code, verify database assumptions, and run tests. I would not rely on an AI suggestion alone for inventory calculations or incomplete-data handling.