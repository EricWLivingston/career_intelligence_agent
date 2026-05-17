#!/usr/bin/env python3
"""Insert 5 fake jobs into the job_catalogue for testing."""
import sys
sys.path.insert(0, '/Users/ericlivingston/Documents/Projects/career_intelligence_agent')

from lib.tools import google_sheets_append, google_sheets_read
from datetime import datetime

SPREADSHEET_ID = "1wlXCsRVph7DKB_Jv0MaYlji9p_aUIUlC3QYfspJQMCc"
SHEET_NAME = "job_catalogue"

# First, read the sheet to understand current structure
print("Reading current job_catalogue...")
records = google_sheets_read(SPREADSHEET_ID, SHEET_NAME)
print(f"Current records: {records[:200]}...")  # Print first 200 chars

# Create 5 fake jobs at Apple
fake_jobs = [
    [
        "Senior Electrical Engineer - Power Systems",
        "Apple",
        "https://jobs.apple.com/fake1",
        datetime.now().strftime("%Y-%m-%d"),
        "applied",
        "Test job - fake entry"
    ],
    [
        "Hardware Design Engineer",
        "Apple",
        "https://jobs.apple.com/fake2",
        datetime.now().strftime("%Y-%m-%d"),
        "pending",
        "Test job - fake entry"
    ],
    [
        "Electrical Engineer - Chip Design",
        "Apple",
        "https://jobs.apple.com/fake3",
        datetime.now().strftime("%Y-%m-%d"),
        "applied",
        "Test job - fake entry"
    ],
    [
        "RF Hardware Engineer",
        "Apple",
        "https://jobs.apple.com/fake4",
        datetime.now().strftime("%Y-%m-%d"),
        "interested",
        "Test job - fake entry"
    ],
    [
        "Battery Systems Engineer",
        "Apple",
        "https://jobs.apple.com/fake5",
        datetime.now().strftime("%Y-%m-%d"),
        "applied",
        "Test job - fake entry"
    ],
]

print(f"\nInserting {len(fake_jobs)} fake jobs...")
for i, job in enumerate(fake_jobs, 1):
    result = google_sheets_append(SPREADSHEET_ID, SHEET_NAME, job)
    print(f"Job {i}: {result}")

print("\nFake jobs inserted successfully!")
